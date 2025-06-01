import os
import sys
import json
import tempfile
import traceback
from urllib.parse import urlparse

import torch
import subprocess
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import timedelta
import requests

from whisperx.diarize import DiarizationPipeline

from transformers import WhisperProcessor, WhisperForConditionalGeneration, GenerationConfig
import librosa

from app import Job, Meeting
from app.models.job import JobStatus

# Ensure Hugging Face cache directories
os.environ["HF_HOME"] = "/root/.cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"

# Model ID for Hindi‐English‐multilingual Whisper
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

# Choose device: GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# ----------------------------------------------------------------------
# Load Hugging Face Whisper model & processor once, at module load
# ----------------------------------------------------------------------
logger.info(f"Loading HF Whisper model '{WHISPER_MODEL}' on {device}…")
processor = WhisperProcessor.from_pretrained(WHISPER_MODEL)
whisper_model = WhisperForConditionalGeneration.from_pretrained(WHISPER_MODEL).to(device)
# We will use a standard generation config (you can tweak beam size, etc. if desired)
gen_config = GenerationConfig.from_pretrained(WHISPER_MODEL)
logger.info("HF Whisper model loaded successfully.")


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Convert an MP3 file to WAV (16 kHz, mono PCM).
    """
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = [
        'ffmpeg', '-y', '-i', mp3_path,
        '-ar', '16000', '-ac', '1',
        '-c:a', 'pcm_s16le', wav_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS.
    """
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id: str):
    """
    POST to Flask API to trigger next‐step analysis.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        requests.post(url, json={"job_id": job_id})
    except Exception as e:
        logger.exception(f"Error notifying Flask server for job {job_id}: {e}")


def update_job_status(job_id: str, status: JobStatus):
    """
    Update the JobStatus in the database.
    """
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = status
            session.commit()
        else:
            logger.error(f"Job {job_id} not found when updating status to {status}.")
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise ex


def parse_s3_url(s3_url: str):
    """
    Parse an S3 URL of the form s3://bucket/key and return (bucket, key).
    """
    try:
        parsed = urlparse(s3_url)
        if parsed.scheme != "s3":
            raise ValueError("Invalid S3 URL")
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        return bucket, key
    except Exception as e:
        logger.error(f"Error parsing S3 URL '{s3_url}': {e}")
        raise e


def get_audio_url(job_id: str) -> str:
    """
    Query the database for the S3 URL of the audio tied to job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def process_audio(job_id: str, bucket: str, key: str):
    """
    Download the MP3 from S3, convert to WAV, run Whisper transcription (HF model),
    run speaker diarization, and store both transcript & diarization in the DB.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)
        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Create a temp file path for WAV
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_wav:
            wav_path = tmp_wav.name

        # Download MP3 to a temp file, then convert:
        mp3_path = wav_path.replace('.wav', '.mp3')
        logger.info(f"Downloading MP3 to '{mp3_path}' …")
        s3_client.download_file(bucket, key, mp3_path)
        logger.info("Converting MP3 to WAV …")
        wav_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file ready at '{wav_path}'")

        # 1) HF Whisper transcription (multilingual)
        transcription_text, language_code = transcribe_with_whisper(havapath=wav_path)
        logger.info(f"Transcription (raw text): {transcription_text}")
        logger.info(f"Detected language: {language_code}")

        # 2) Speaker diarization (PyAnnote):
        diarization_segments = run_diarization_model(wav_path, hf_token="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", device=device)
        logger.info(f"Diarization segments: {diarization_segments}")

        # 3) Persist to DB: transcription + diarization
        meeting = None
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()

        if meeting:
            # Store transcript as a simple string
            meeting.transcription = transcription_text

            # For diarization, pickle out the segments list:
            # Each segment is a dict: {"start": float, "end": float, "speaker": "SPEAKER_00", ...}
            meeting.diarization = json.dumps(diarization_segments)
            session.commit()
            logger.info(f"Stored transcript & diarization for meeting ID {meeting.id}")
        else:
            logger.error(f"Meeting record not found for job {job_id}")

        update_job_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return


def transcribe_with_whisper(havapath: str):
    """
    Use the HuggingFace Whisper model (vasista22/whisper-hindi-large-v2) to transcribe.
    Returns (full_text: str, language_code: str).
    """
    # Load audio via librosa (16 kHz, mono)
    wav, sr = librosa.load(havapath, sr=16000)
    # Preprocess
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    # Generate token IDs
    with torch.no_grad():
        predicted_ids = whisper_model.generate(
            inputs,
            generation_config=gen_config,
            # You can set `return_dict_in_generate=True, output_scores=False` if needed
        )

    # Decode to text
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
    # language_code is returned in model output’s attributes, but HF wrapper does not expose it directly.
    # We'll fallback to "hi" if model_id contains "hindi"; otherwise "en".
    language_code = "hi" if "hindi" in WHISPER_MODEL.lower() else "en"

    return transcription, language_code


def run_diarization_model(havapath: str, hf_token: str = None, device: str = "cuda"):
    """
    Run PyAnnote diarization to segment speakers.
    Returns a list of dicts: [{"start": float, "end": float, "speaker": str}, …].
    """
    diarize_pipeline = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_result = diarize_pipeline(havapath)

    # Format into plain‐dict list
    segments = []
    for seg in diarize_result.get("segments", []):
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": seg["label"]
        })
    return segments


def run_diarization(job_id: str):
    """
    Entry point: fetch audio S3 URL, then process it.
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
        logger.exception(f"Error in parsing S3 audio URL: {s3_url} for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    # Process the audio file
    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")

    # Notify Flask server to proceed
    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")


if __name__ == "__main__":
    run_diarization()
