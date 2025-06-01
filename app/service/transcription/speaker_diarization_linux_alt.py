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
from whisperx.diarize import DiarizationPipeline

# ——— NEW/HF imports ———
from transformers import WhisperProcessor, WhisperForConditionalGeneration  # ← CHANGED
# ————————————

from app import Job, Meeting
from app.models.job import JobStatus

# if you need an HF token for private models:
HF_TOKEN = os.getenv("HF_TOKEN", None)

# Use a shared cache directory for HF and Transformers
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")
os.environ["HF_HOME"] = cache_dir
os.environ["TRANSFORMERS_CACHE"] = cache_dir

# Which Whisper model to use:
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

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# ——— Load HF WhisperProcessor + WhisperForConditionalGeneration ———
logger.info(f"Loading HF WhisperProcessor + WhisperForConditionalGeneration for '{WHISPER_MODEL}' on {device}…")  # ← CHANGED
try:
    processor = WhisperProcessor.from_pretrained(
        WHISPER_MODEL,
        use_auth_token=HF_TOKEN,
        cache_dir=cache_dir
    )
    whisper_model = WhisperForConditionalGeneration.from_pretrained(
        WHISPER_MODEL,
        use_auth_token=HF_TOKEN,
        cache_dir=cache_dir
    ).to(device)
    # Patch in lang_to_id so detect_language() will work:
    whisper_model.generation_config.lang_to_id = processor.tokenizer.lang2id  # ← CHANGED

    # Build inverse mapping from ID → language code:
    id2lang = {v: k for k, v in processor.tokenizer.lang2id.items()}  # ← CHANGED
    logger.info("HF Whisper model loaded successfully.")
except Exception as e:
    logger.exception(f"Error loading HF Vasista Whisper model: {e}")
    sys.exit(1)
# ——————————————————————————————————————————————————————————————

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
    processes it using WhisperX for diarization, and updates the corresponding
    meeting record with the transcript.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            local_audio_path = tmp_file.name

        logger.info(f"Downloading MP3 from S3: bucket={bucket}, key={key}")
        mp3_path = local_audio_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)

        logger.info(f"Converting MP3 to WAV …")
        local_audio_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file ready at '{local_audio_path}'")

        # Transcribe + detect language
        transcription_text, language = transcribe_with_whisper(local_audio_path)
        logger.info(f"Transcription (raw text): {transcription_text}")
        logger.info(f"Detected language: {language}")

        # Now run diarization and assign speakers
        speaker_words = diarize_and_assign_speakers(
            transcription_text, local_audio_path, device=device, hf_token=HF_TOKEN
        )
        logger.info(f"speaker_words: {speaker_words}")

        # flatten the nested word lists into one list of word-dicts
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))
        diarization = group_words_into_segments(flat_words)
        for segment in diarization:
            segment["language"] = language

    except Exception as e:
        # Log the root cause and mark the job failed,
        # but let the caller decide whether to retry/notify.
        logger.exception(f"[process_audio] job={job_id} failed: {e}\nTraceback: {traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return  # swallow the exception

    # Update the meetings table with the transcript and timestamp
    try:
        meeting = None
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            meeting.transcription = transcription_text  # store raw text
            meeting.diarization = json.dumps(diarization)
            session.commit()
        else:
            logger.error(f"Meeting for job {job_id} not found.")

        logger.info(f"Updated meeting {job_id} with transcript.")
        update_job_status(job_id, JobStatus.COMPLETED)
    except Exception as e:
        logger.error(f"Error updating meeting/job status for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise

def transcribe_with_whisper(wav_path: str):
    """
    Use the HF WhisperForConditionalGeneration model to:
      1) detect language on the entire file
      2) generate the transcription in that language
    Returns (full_text: str, language_code: str).
    """
    # 1) Load audio via librosa at 16 kHz, mono
    import librosa  # local import to avoid module‐startup overhead
    wav, sr = librosa.load(wav_path, sr=16000)

    # 2) Preprocess into input features
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    # 3) Detect language logits
    #    (GenerationConfig.lang_to_id was patched at load time)
    try:
        lang_logits = whisper_model.detect_language(inputs)  # ← CHANGED
        lang_id = int(lang_logits.argmax(dim=-1))           # (batch_size=1 → scalar)
        language_code = id2lang[lang_id]                    # ← CHANGED
    except Exception as e:
        # fallback if detect_language still fails
        logger.warning(f"detect_language() failed: {e}. Defaulting to 'en'.")
        language_code = "en"

    # 4) Generate transcription in the detected language
    #    We set forced_decoder_ids so that Whisper knows which language to produce
    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language_code, task="transcribe")
    with torch.no_grad():
        predicted_ids = whisper_model.generate(
            inputs,
            forced_decoder_ids=forced_decoder_ids,
            max_length=448,
            num_beams=5
        )
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
    return transcription, language_code

def diarize_and_assign_speakers(transcript_text: str, wav_path: str, device="cuda", hf_token=None):
    """
    We no longer split the audio into tiny chunks.  Instead, run
    PyAnnote on the full file to get speaker segments, then assign
    each word (using WhisperX.align) to a speaker.
    """
    # 1) Diarize the raw audio with PyAnnote
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)

    # 2) Align transcript_text to word‐level with WhisperX
    #    First, run WhisperX alignment on the entire audio + raw text
    #    (WhisperX will internally force‐align each word).
    #    Then, assign speakers to each word.
    align_model, metadata = whisperx.load_align_model(language_code="en" if transcript_text == "" else None, device=device)
    # WhisperX.align wants segments from WhisperX transcriber, but we only have raw text.
    # So we cheat: pass a dummy segment list to get word‐level alignment out of WhisperX.
    # (In practice, you can supply [{"start": 0, "end": duration, "text": transcript_text}], but
    #  WhisperX will split on spaces to align each word anyway.)
    duration = whisperx.audio.load_audio(wav_path)["sample_rate"] * whisperx.audio.load_audio(wav_path)["array"].shape[0]
    # Actually just pass segments=[{"start": 0.0, "end": duration, "text": transcript_text}]
    dummy_segments = [{"start": 0.0, "end": float(duration), "text": transcript_text}]
    word_align = whisperx.align(dummy_segments, align_model, metadata, wav_path, device=device)

    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, word_align)
    return speaker_aligned

def group_words_into_segments(words, max_gap=1.0):
    """
    Given a flat list of {"start", "end", "word", "speaker"}, merge words
    into continuous speaker‐specific segments.  Return a list of segments.
    """
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
        logger.exception(f"Error parsing S3 audio URL ({s3_url}) for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    # 1) Process the audio.  If it fails, we've already marked the job as FAILURE above,
    #    so we swallow the exception here (it’s logged inside process_audio).
    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"Failed during process_audio for job_ID: {job_id}")

    # 2) Notify Flask to start the next step
    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the Flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server to start analysis for job_ID: {job_id}: {e}")

if __name__ == "__main__":
    run_diarization()
