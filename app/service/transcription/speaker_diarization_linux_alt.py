import os
import sys
import json
import tempfile
import traceback
from urllib.parse import urlparse

import torch
import whisperx
import subprocess
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import timedelta
import requests

import librosa
from transformers import WhisperProcessor, WhisperForConditionalGeneration, GenerationConfig

from whisperx.diarize import DiarizationPipeline

from app import Job, Meeting
from app.models.job import JobStatus

os.environ["HF_HOME"] = "/root/.cache/huggingface"

WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variable for JOB_ID (provided by ECS via container overrides)
JOB_ID = os.environ.get("JOB_ID")
DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g., "postgresql://user:password@host/db"
FLASK_API_URL = os.getenv("FLASK_API_URL")

# Initialize AWS S3 client
s3_client = boto3.client("s3")

# Initialize SQLAlchemy session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Use the TRANSFORMERS_CACHE environment variable to control the cache directory.
# This directory should be a persistent volume (e.g., mounted via EFS) in production.
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")

# Define a path within the cache directory for the HF Whisper model.
model_cache_path = os.path.join(cache_dir, WHISPER_MODEL)

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# — LOAD HF WhisperProcessor + WhisperForConditionalGeneration for 'vasista22/whisper-hindi-large-v2'
logger.info(f"Loading HF WhisperProcessor + WhisperForConditionalGeneration for '{WHISPER_MODEL}' on {device}…")
processor = WhisperProcessor.from_pretrained(WHISPER_MODEL)
whisper_model = WhisperForConditionalGeneration.from_pretrained(WHISPER_MODEL).to(device)
# GenerationConfig.from_pretrained pulls in the correct lang_to_id mapping
gen_config = GenerationConfig.from_pretrained(WHISPER_MODEL)
# Build id→lang mapping for use after detect_language()
id2lang = {v: k for k, v in processor.tokenizer.lang_code_to_id.items()}
logger.info(f"HF Whisper model '{WHISPER_MODEL}' loaded successfully.")

if not os.path.exists(model_cache_path):
    logger.info("Model not found in cache; relying on Hugging Face’s default caching.")
else:
    logger.info("Model directory exists under TRANSFORMERS_CACHE / HF_HOME.")

logger.info(f"WhisperX (alignment/diarization) + HF Whisper '{WHISPER_MODEL}' are all ready.")


def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = ['ffmpeg', '-y', '-i', mp3_path, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', wav_path]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds):
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id):
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    requests.post(url, json={"job_id": job_id})


def update_job_status(job_id, status):
    """
    Updates the job status in the jobs table.
    """
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = status
            session.commit()
        else:
            logger.error(f"Job {job_id} not found.")
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise ex


def parse_s3_url(s3_url):
    """
    Parses an S3 URL in the form s3://bucket/key and returns (bucket, key).
    """
    try:
        parsed = urlparse(s3_url)
        if parsed.scheme != "s3":
            raise ValueError("Invalid S3 URL")
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        return bucket, key
    except Exception as e:
        logger.error(f"Error parsing S3 url: {s3_url}")
        raise e


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def process_audio(job_id, bucket, key):
    """
    Downloads the audio file from S3 using the URL retrieved from the database,
    transcribes it via HF Whisper (single‐shot, full‐file),
    then runs WhisperX for diarization & alignment, and finally updates the meeting record.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            local_audio_path = tmp_file.name

        logger.info(f"Downloading audio file from S3: bucket={bucket}, key={key}")
        mp3_path = local_audio_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)

        logger.info("Converting MP3 to WAV …")
        local_audio_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file ready at '{local_audio_path}'")

        # 1) Transcribe entire WAV at once & detect language
        transcription_text, language = transcribe_with_whisper(local_audio_path)
        logger.info(f"Transcription: {transcription_text}")
        logger.info(f"Detected language: {language}")

        # 2) Diarize + assign speakers using WhisperX
        speaker_words = diarize_and_assign_speakers(
            transcription_text,
            local_audio_path,
            device=device,
            hf_token="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"
        )
        logger.info(f"speaker_words (post‐assignment): {speaker_words}")

        # Flatten the nested word lists into one list of word‐dicts
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))
        diarization = group_words_into_segments(flat_words)

        for segment in diarization:
            segment["language"] = language

    except Exception as e:
        # Log the root cause and mark the job failed.
        logger.exception(f"[process_audio] job={job_id} failed: {e}\nTraceback:\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return  # swallow the exception

    # Update the meetings table with the transcript and diarization
    try:
        meeting = None
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            meeting.transcription = json.dumps({
                "text": transcription_text,
                "language": language
            })
            meeting.diarization = json.dumps(diarization)
            session.commit()
        else:
            logger.error(f"Meeting for job {job_id} not found.")

        logger.info(f"Updated meeting {job_id} with transcript + diarization.")
        update_job_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        logger.error(f"Error updating meeting for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def transcribe_with_whisper(wav_path):
    """
    Use the HuggingFace Whisper model (vasista22/whisper-hindi-large-v2) to transcribe
    the entire file at once and detect language. Returns (text: str, language_code: str).
    """
    # 1) Load full WAV via librosa (16 kHz, mono)
    wav, sr = librosa.load(wav_path, sr=16000)

    # 2) Language detection on the entire waveform
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)
    # Pass the model’s own config so that detect_language can find lang_to_id
    lang_logits = whisper_model.detect_language(inputs, generation_config=whisper_model.config)
    predicted_id = torch.argmax(lang_logits, dim=-1).item()
    language_code = id2lang[predicted_id]

    # 3) Single‐shot generation for the entire file
    input_features = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)
    with torch.no_grad():
        generated_ids = whisper_model.generate(input_features, generation_config=gen_config)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    return text, language_code


def diarize_and_assign_speakers(transcription_text, wav_path, device="cuda", hf_token=None):
    """
    Run PyAnnote‐based diarization to get speaker segments, then align Whisper‐
    timestamps (via WhisperX) and assign each word to a speaker.
    """
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)
    logger.info(f"Diarization segments: {diarize_segments}")

    # Align the HF‐generated text to timecodes (approximate) via WhisperX’s align
    align_model, metadata = whisperx.load_align_model(
        language_code=processor.tokenizer.lang2id.get(transcription_text, transcription_text),
        device=device
    )
    # We run a quick whisperx.transcribe to get “segments” with timestamps (ignoring its ASR text)
    dummy_asr = whisperx.transcribe(
        wav_path,
        model=None,       # let WhisperX pick its default “large” model for alignment
        language=processor.tokenizer.lang2id.get(transcription_text, transcription_text),
        device=device
    )
    result_aligned = whisperx.align(
        dummy_asr["segments"],
        align_model,
        metadata,
        wav_path,
        device=device,
        return_char_alignments=False
    )

    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, result_aligned)
    return speaker_aligned


def group_words_into_segments(words, max_gap=1.0):
    segments = []
    if not words:
        return segments

    current = {
        "start": words[0]["start"],
        "end": words[0]["end"],
        "text": words[0]["word"],
        "speaker": words[0]["speaker"]
    }

    for i in range(1, len(words)):
        word = words[i]
        gap = word["start"] - current["end"]
        if gap > max_gap or word["speaker"] != current["speaker"]:
            segments.append(current)
            current = {
                "start": word["start"],
                "end": word["end"],
                "text": word["word"],
                "speaker": word["speaker"]
            }
        else:
            current["end"] = word["end"]
            current["text"] += " " + word["word"]
    segments.append(current)
    return segments


def run_diarization(job_id):
    if not job_id:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        logger.info(f"Retrieved audio URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    try:
        logger.info(f"Parsing s3_audio_url: {s3_url}")
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error parsing S3 audio URL: {s3_url} for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"Failed to process job {job_id}")
        return

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent notification to Flask for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job_id={job_id}: {e}")


if __name__ == "__main__":
    run_diarization()
