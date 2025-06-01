import json
import os
import logging
import subprocess
import tempfile
from datetime import timedelta
from urllib.parse import urlparse

import boto3
import requests
import torch
import whisperx
from whisperx.diarize import DiarizationPipeline, assign_word_speakers
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import Job, Meeting  # Adjust import paths as needed
from app.models.job import JobStatus

# ─── GLOBAL CONFIGURATION ──────────────────────────────────────────────────────

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
FLASK_API_URL = os.getenv("FLASK_API_URL")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")  # Hugging Face token for PyAnnote models
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(handler)

# Load WhisperX ASR model once at startup
logger.info("Loading WhisperX ASR model...")
whisperx_model = whisperx.load_model("large-v3", device=DEVICE)

# Database setup (SQLAlchemy)
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. "postgresql://user:pass@host:port/dbname"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# S3 client
s3_client = boto3.client("s3")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    """
    Format a float‐second timestamp as "HH:MM:SS".
    """
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id: str):
    """
    Send a POST to the Flask backend to trigger downstream analysis.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        response = requests.post(url, json={"job_id": job_id})
        response.raise_for_status()
        logger.info(f"Notified Flask server for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job_id={job_id}: {e}")


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


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Use ffmpeg to convert an MP3 file to WAV (16kHz) for WhisperX.
    Returns the new WAV file path.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    command = [
        "ffmpeg",
        "-y",
        "-i", mp3_path,
        "-ar", "16000",  # WhisperX expects 16 kHz
        wav_path,
    ]
    subprocess.run(command, check=True)
    return wav_path


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


# ─── CORE TRANSCRIPTION + DIARIZATION ─────────────────────────────────────────

def transcribe_and_diarize(audio_path: str):
    """
    1. Run WhisperX transcription + forced alignment -> `aligned_result`.
    2. Instantiate WhisperX’s DiarizationPipeline -> `diarize_df` (DataFrame).
    3. Call assign_word_speakers(...) to merge words with speaker labels.
    Returns:
      - `aligned_with_speakers`: dict (aligned transcript, each word tagged with "speaker")
      - `diarize_df`: pandas.DataFrame of speaker segments
    """
    # ─── (A) Transcription + Alignment ─────────────────────
    logger.info("Running WhisperX transcription (auto‐detect language)")
    # If you omit `language=…`, WhisperX auto-detects the language.
    transcription = whisperx_model.transcribe(audio_path)
    detected_lang = transcription.get("language", "en")
    logger.info(f"Detected language = {detected_lang}")

    # Forced alignment step
    model_a, metadata = whisperx.load_align_model(
        language_code=detected_lang, device=DEVICE
    )
    aligned_result = whisperx.align(
        transcription["segments"], model_a, metadata, audio_path, DEVICE
    )
    # aligned_result is a dict with keys "segments" (each segment has "words": [{"word", "start", "end"}, …])

    # ─── (B) Diarization Pipeline ─────────────────────────
    logger.info("Running DiarizationPipeline on audio")
    diarizer = DiarizationPipeline(
        model_name="pyannote/speaker-diarization-3.1",  # adjust version as needed
        use_auth_token=HF_TOKEN,
        device=DEVICE,
    )
    diarize_df = diarizer(audio_path)
    # diarize_df columns: ["segment", "label", "speaker", "start", "end"]

    # ─── (C) Merge word‐timestamps with speaker segments ───
    logger.info("Assigning speaker labels to each word in the transcription")
    aligned_with_speakers = assign_word_speakers(
        diarize_df,
        aligned_result,
        fill_nearest=False
    )
    # Now aligned_with_speakers["segments"] has each segment dict plus "speaker",
    # and each word in aligned_with_speakers["segments"][i]["words"] also has "speaker".

    return aligned_with_speakers, diarize_df


def process_audio(job_id: str, bucket: str, key: str):
    """
    Main processing flow for a given job_id:
      1. Download MP3 from S3
      2. Convert to WAV
      3. Run transcription + diarization
      4. Store results back in the DB
      5. Update job status
    """
    session = SessionLocal()
    update_job_status(job_id, JobStatus.IN_PROGRESS)

    try:
        # 1. Download from S3
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            local_wav = tmp_file.name
        mp3_temp = local_wav.replace(".wav", ".mp3")

        logger.info(f"Downloading audio from s3://{bucket}/{key} to {mp3_temp}")
        s3_client.download_file(bucket, key, mp3_temp)

        # 2. Convert to WAV
        local_wav = convert_mp3_to_wav(mp3_temp)

        # 3. Transcribe + Diarize
        aligned_with_speakers, diarize_df = transcribe_and_diarize(local_wav)

        # 4. Update Meeting record in DB
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            # Store the full aligned transcript (with speaker tags) as JSON
            meeting.transcript = json.dumps(aligned_with_speakers)

            # Optionally, store the diarization DataFrame separately (as JSON records)
            meeting.diarization = diarize_df.to_json(orient="records")

            session.commit()
            logger.info(f"Updated Meeting {job_id} with transcript & diarization.")
            update_job_status(job_id, JobStatus.COMPLETED)
        else:
            logger.error(f"Meeting record not found for job_id={job_id}")
            update_job_status(job_id, JobStatus.FAILURE)

    except Exception as e:
        logger.exception(f"Error processing audio for job_id={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
    finally:
        session.close()


# ─── MAIN ENTRYPOINT ──────────────────────────────────────────────────────────

def run_diarization(job_id):
    job_id = os.getenv("JOB_ID") or job_id
    if not job_id:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        parsed = urlparse(s3_url)
        bucket, key = parsed.netloc, parsed.path.lstrip("/")
        process_audio(job_id, bucket, key)
    except Exception as e:
        logger.exception(f"Error in run_diarization for job_id={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    # 5. Notify Flask server to trigger downstream analysis
    try:
        notify_flask_server(job_id)
    except Exception:
        pass


if __name__ == "__main__":
    run_diarization()
