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

from transformers import WhisperProcessor, WhisperForConditionalGeneration

from app import Job, Meeting
from app.models.job import JobStatus

# ─── Configuration & Environment ──────────────────────────────────────────────

# If your HF model is gated, set HF_API_TOKEN in the environment.
HF_TOKEN = os.getenv("HF_API_TOKEN", None)

# Model to use:
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"

# Where HuggingFace and transformers will cache models:
CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/model_cache")
os.environ["HF_HOME"] = CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = CACHE_DIR

# Choose device:
device = "cuda" if torch.cuda.is_available() else "cpu"

# Logging setup:
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Using device: {device}")

# ─── Load HuggingFace Whisper (PyTorch) ────────────────────────────────────────

logger.info(f"Loading HF WhisperProcessor + WhisperForConditionalGeneration for '{WHISPER_MODEL}' on {device}…")
try:
    processor = WhisperProcessor.from_pretrained(
        WHISPER_MODEL,
        cache_dir=CACHE_DIR,
        use_auth_token=HF_TOKEN,
    )
    whisper_model = WhisperForConditionalGeneration.from_pretrained(
        WHISPER_MODEL,
        cache_dir=CACHE_DIR,
        use_auth_token=HF_TOKEN,
    ).to(device)
    logger.info("HF Whisper model loaded successfully.")
except Exception as e:
    logger.exception(f"Error loading HF Whisper model '{WHISPER_MODEL}': {e}")
    sys.exit(1)

# Build a mapping from language‐ID to language code:
#   WhisperProcessor.tokenizer.lang_code_to_id is a dict: { "en": 50358, "hi": 50359, … }
id2lang = {v: k for k, v in processor.tokenizer.lang_code_to_id.items()}


# ─── AWS / Database / S3 / Flask Setup ────────────────────────────────────────

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


# ─── Utility Functions ─────────────────────────────────────────────────────────

def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Convert an MP3 file to 16 kHz, mono WAV for Whisper.
    Returns the path to the WAV file.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    command = [
        "ffmpeg",
        "-y",
        "-i", mp3_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        wav_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds: float) -> str:
    """
    Convert a float number of seconds into HH:MM:SS format.
    """
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id: str):
    """
    Notify the Flask API that analysis is complete.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        requests.post(url, json={"job_id": job_id})
    except Exception as ex:
        logger.exception(f"Failed to POST to Flask API for job {job_id}: {ex}")


def update_job_status(job_id: str, status: JobStatus):
    """
    Update the status of the job in the database.
    """
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = status
            session.commit()
        else:
            logger.error(f"Job {job_id} not found in DB.")
    except Exception:
        logger.exception(f"Error updating job status for job {job_id}.")
        raise


def parse_s3_url(s3_url: str):
    """
    Parse S3 URL (s3://bucket/key) and return (bucket, key).
    """
    parsed = urlparse(s3_url)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URL: {s3_url}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def get_audio_url(job_id: str) -> str:
    """
    Query the database for the S3 URL of the audio for this job.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    raise ValueError(f"No audio URL found for job_id {job_id}.")


# ─── Transcription & Language Detection (HF Whisper) ──────────────────────────

def transcribe_with_hf_whisper(wav_path: str):
    """
    Transcribe an entire WAV file using HF WhisperForConditionalGeneration.
    1) Load audio with librosa
    2) Preprocess + detect language
    3) Generate transcription
    Returns: (transcription_text: str, language_code: str)
    """
    # 1) Load raw waveform at 16 kHz mono
    wav, sr = librosa.load(wav_path, sr=16000)
    # 2) Preprocess into input_features
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    # 3) Detect language logits (shape: [1, n_langs])
    with torch.no_grad():
        lang_logits = whisper_model.detect_language(inputs)[0]  # (n_langs,)
    lang_id = int(lang_logits.argmax().item())
    language_code = id2lang.get(lang_id, "en")

    logger.info(f"Detected language: {language_code}")

    # 4) Generate token IDs (no beam search args here, but you can pass generation_config overrides)
    with torch.no_grad():
        predicted_ids = whisper_model.generate(inputs)

    # 5) Decode IDs → text
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
    logger.info(f"Transcription (raw text): {transcription[:50]}…")

    return transcription, language_code


# ─── Alignment & Diarization Helpers ─────────────────────────────────────────

def diarize_and_assign_speakers(result_aligned: dict, wav_path: str, device="cuda", hf_token=None):
    """
    Run pyannote diarization on the WAV, then assign speakers to aligned tokens.
    Returns a dict with "segments" (each with words + speaker info).
    """
    diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)
    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, result_aligned)
    return speaker_aligned


def group_words_into_segments(words: list, max_gap: float = 1.0):
    """
    Take a flat list of word-dicts (each with start/end/word/speaker) and merge
    consecutive words by the same speaker if the gap ≤ max_gap seconds.
    Returns a list of segments: { "start", "end", "text", "speaker" }.
    """
    segments = []
    if not words:
        return segments

    current = {
        "start": words[0]["start"],
        "end": words[0]["end"],
        "text": words[0]["word"],
        "speaker": words[0]["speaker"],
    }

    for i in range(1, len(words)):
        w = words[i]
        gap = w["start"] - current["end"]
        if gap > max_gap or w["speaker"] != current["speaker"]:
            segments.append(current)
            current = {
                "start": w["start"],
                "end": w["end"],
                "text": w["word"],
                "speaker": w["speaker"],
            }
        else:
            current["end"] = w["end"]
            current["text"] += " " + w["word"]
    segments.append(current)
    return segments


# ─── Core: Download, Transcribe, Align, Diarize, Store ────────────────────────

def process_audio(job_id: str, bucket: str, key: str):
    """
    1) Mark job IN_PROGRESS
    2) Download audio from S3 (MP3 → WAV)
    3) Transcribe entire WAV with HF Whisper (language detection)
    4) Align tokens with WhisperX’s alignment model
    5) Diarize + assign speakers
    6) Persist transcription + diarization into DB
    7) Mark job COMPLETED (or FAILURE on exception)
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)
        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Download MP3 → save to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
            local_wav_path = tmp_wav.name  # placeholder; we'll overwrite after conversion

        mp3_path = local_wav_path.replace(".wav", ".mp3")
        logger.info(f"Downloading MP3 from S3 to '{mp3_path}'")
        s3_client.download_file(bucket, key, mp3_path)

        # Convert MP3 → aligned WAV
        logger.info(f"Converting MP3 → WAV at '{local_wav_path}'")
        local_wav_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file ready at '{local_wav_path}'")

        # 1) Transcribe & detect language on entire WAV
        transcription_text, language = transcribe_with_hf_whisper(local_wav_path)

        # 2) Split the transcription_text into “segments” manually:
        #    For simplicity, we’ll call once with beam search disabled:
        #    WhisperX’s align step expects a list of segments with start/end/text.
        #    Since we didn’t get segment‐level timestamps from HF directly, we let WhisperX
        #    re‐segment automatically via the “transcription_text → forced align” call.
        #
        #    Conveniently, whisperx.transcribe(...) can accept a raw str and will
        #    internally chunk + paginate. But we’ll do it “manually”:
        #
        transcription_segments = [{"start": 0.0, "end": 0.0, "text": transcription_text}]

        # 3) Alignment with WhisperX
        align_model, metadata = whisperx.load_align_model(
            language_code=language, device=device
        )
        result_aligned = whisperx.align(
            transcription_segments,
            align_model,
            metadata,
            local_wav_path,
            device=device,
            return_char_alignments=False
        )

        # 4) Diarize + assign speakers
        speaker_words = diarize_and_assign_speakers(
            result_aligned,
            local_wav_path,
            device=device,
            hf_token=HF_TOKEN
        )

        # Flatten word‐list:
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))

        diarization_segments = group_words_into_segments(flat_words)

        # Attach detected language to each segment
        for seg in diarization_segments:
            seg["language"] = language

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # ─── Persist transcription + diarization into DB ────────────────────────────
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()

        if meeting:
            meeting.transcription = json.dumps({
                "text": transcription_text,
                "language": language
            })
            meeting.diarization = json.dumps(diarization_segments)
            session.commit()
            logger.info(f"Updated meeting {meeting.id} with transcript & diarization.")
        else:
            logger.error(f"Meeting record for job_id={job_id} not found.")

        update_job_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        logger.exception(f"Error saving results for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def run_diarization(job_id: str):
    """
    Main entry: fetch S3 URL, then call process_audio → notify Flask.
    """
    if not job_id:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        sys.exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        logger.info(f"Retrieved audio URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    try:
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error parsing S3 URL '{s3_url}': {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"Error in process_audio for job {job_id}")
        # process_audio already set status=FAILURE if it raised.

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent notification to Flask for job_id={job_id}")
    except Exception:
        logger.exception(f"Failed to notify Flask for job_id={job_id}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
