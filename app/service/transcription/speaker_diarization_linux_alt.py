import os
import sys
import json
import tempfile
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

from app import Job, Meeting
from app.models.job import JobStatus

os.environ["HF_HOME"] = "/root/.cache/huggingface"

WHISPER_MODEL = "large-v1"

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

# Define a path within the cache directory for the WHISPER model.
model_cache_path = os.path.join(cache_dir, WHISPER_MODEL)

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# Check if the model appears to be cached.
if not os.path.exists(model_cache_path):
    logger.info("Model not found in cache; downloading and caching the model...")
    model = whisperx.load_model(WHISPER_MODEL, device=device, compute_type="float32")
    # If the loaded model supports explicit saving, do so:
    try:
        model.save_pretrained(model_cache_path)
        logger.info(f"Model saved to cache at {model_cache_path}")
    except AttributeError:
        # If there's no save_pretrained method, rely on the default Transformers caching.
        logger.info("Model does not support explicit saving; relying on default caching.")
else:
    logger.info("Loading model from cache...")
    model = whisperx.load_model(WHISPER_MODEL, device=device, compute_type="float32")

logger.info(f"WhisperX {WHISPER_MODEL} model is loaded and ready.")


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

        logger.info(f"Downloading audio file from S3: bucket={bucket}, key={key}")
        mp3_path = local_audio_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)
        local_audio_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file downloaded to {local_audio_path}")

        transcription_aligned, language = transcribe_with_whisperx(local_audio_path)
        logger.info(f"trasnscription: {transcription_aligned}")
        logger.info(f"language: {language}")
        word_segs = transcription_aligned.get("word_segments", [])
        logger.info(f"WhisperX returned {len(word_segs)} word_segments")
        if word_segs:
            logger.info(f"First word segment: {word_segs[0]}")
        else:
            logger.warning("No word_segments to log; skipping first-item debug")
        speaker_words = diarize_and_assign_speakers(
            transcription_aligned, local_audio_path, device=device, hf_token="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"
        )
        diarization = group_words_into_segments(speaker_words)
        for segment in diarization:
            segment["language"] = language

    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        logger.error(f"Error while transcribing audio file for job_id: {job_id}. Error: {e}")
        raise e

    # Update the meetings table with the transcript and timestamp
    try:
        meeting = None
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            meeting.transcription = json.dumps(transcription_aligned)
            meeting.diarization = json.dumps(diarization)
            session.commit()
        else:
            logger.error(f"Meeting {job_id} not found.")

        logger.info(f"Updated meeting {job_id} with transcript.")

        # Update job status to COMPLETED
        update_job_status(job_id, JobStatus.COMPLETED)
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def transcribe_with_whisperx(wav_path, device="cuda"):
    # Load WhisperX model
    model = whisperx.load_model(WHISPER_MODEL, device, compute_type="float16" if device == "cuda" else "float32")

    # Transcribe
    transcription = model.transcribe(wav_path)
    logger.info(f"transcription is {transcription}")

    # Load alignment model
    align_model, metadata = whisperx.load_align_model(language_code=transcription["language"], device=device)
    segments_aligned, word_segments_aligned = whisperx.align(transcription["segments"], align_model, metadata, wav_path,
                                                             device=device)
    logger.info(f"Whisperx aligned segments: {segments_aligned}")
    logger.info(f"word_segments_aligned is {word_segments_aligned}")
    if isinstance(word_segments_aligned, str):
        word_segments_aligned = word_segments_aligned.strip()
        if word_segments_aligned:
            try:
                word_segments_aligned = json.loads(word_segments_aligned)
            except json.JSONDecodeError:
            # fallback to empty list if parsing fails
                word_segments_aligned = []
        else:
            word_segments_aligned = []

    transcription_aligned = {
        "segments": segments_aligned,
        "word_segments": word_segments_aligned
    }
    return transcription_aligned, transcription["language"]


def diarize_and_assign_speakers(result_aligned, wav_path, device="cuda", hf_token=None):
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)

    # Assign speakers to each word
    word_segs = result_aligned.get("word_segments", [])

    if not word_segs:
        logger.warning("No word_segments: skipping speaker assignment")
        speaker_aligned = []
    else:
        speaker_aligned = whisperx.assign_word_speakers(diarize_segments, word_segs)
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
        logger.exception(f"Error in parsing S3 audio URL: {s3_url} for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)
    try:
        logger.info(f"Processing job {job_id} for audio file {s3_url}")
        process_audio(job_id, bucket, key)
    except Exception as e:
        logger.error(f"Error in processing diarization for job {job_id}.")
        update_job_status(job_id, JobStatus.FAILURE)

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")


if __name__ == "__main__":
    run_diarization()
