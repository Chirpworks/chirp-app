import os
import logging
import tempfile
from datetime import datetime
from urllib.parse import urlparse

import boto3
import requests
import torch
import whisperx
from sqlalchemy import create_engine, text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variable for JOB_ID (provided by ECS via container overrides)
JOB_ID = os.environ.get("JOB_ID")
DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g., "postgresql://user:password@host/db"
FLASK_API_URL = os.getenv("FLASK_API_URL")

# Initialize AWS S3 client
s3_client = boto3.client("s3")

# Initialize SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Use the TRANSFORMERS_CACHE environment variable to control the cache directory.
# This directory should be a persistent volume (e.g., mounted via EFS) in production.
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")

# Define a path within the cache directory for the 'large-v1' model.
model_cache_path = os.path.join(cache_dir, "large-v1")

# Check if the model appears to be cached.
if not os.path.exists(model_cache_path):
    print("Model not found in cache; downloading and caching the model...")
    model = whisperx.load_model("large-v1", device="cuda")
    # If the loaded model supports explicit saving, do so:
    try:
        model.save_pretrained(model_cache_path)
        print(f"Model saved to cache at {model_cache_path}")
    except AttributeError:
        # If there's no save_pretrained method, rely on the default Transformers caching.
        print("Model does not support explicit saving; relying on default caching.")
else:
    print("Loading model from cache...")
    model = whisperx.load_model("large-v1", device="cuda", compute_type='float32')

print("WhisperX large-v1 model is loaded and ready.")


def notify_flask_server(job_id):
    url = f"{FLASK_API_URL}/trigger_analysis"
    requests.post(url, json={"job_id": job_id})


def update_job_status(job_id, status):
    """
    Updates the job status in the jobs table.
    """
    try:
        with engine.connect() as connection:
            update_query = text("""
                UPDATE jobs
                SET status = :status, updated_at = :now
                WHERE id = :job_id
            """)
            connection.execute(update_query, {
                "status": status,
                "job_id": job_id,
                "now": datetime.utcnow()
            })
            connection.commit()
        logger.info(f"Updated job {job_id} to status: {status}")
    except Exception as e:
        logger.exception(f"Error updating job status for job {job_id}: {e}")
        raise


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    query = text("SELECT s3_audio_url FROM meetings WHERE id = :job_id")
    with engine.connect() as connection:
        result = connection.execute(query, {"job_id": job_id}).fetchone()
    if result and result[0]:
        return result[0]
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def parse_s3_url(s3_url):
    """
    Parses an S3 URL in the form s3://bucket/key and returns (bucket, key).
    """
    parsed = urlparse(s3_url)
    if parsed.scheme != "s3":
        raise ValueError("Invalid S3 URL")
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    return bucket, key


def process_audio(job_id, bucket, key):
    """
    Downloads the audio file from S3 using the URL retrieved from the database,
    processes it using WhisperX for diarization, and updates the corresponding
    meeting record with the transcript.
    """
    update_job_status(job_id, "IN_PROGRESS")

    logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

    # Create a temporary file to store the audio
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        local_audio_path = tmp_file.name

    logger.info(f"Downloading audio file from S3: bucket={bucket}, key={key}")
    s3_client.download_file(bucket, key, local_audio_path)
    logger.info(f"Audio file downloaded to {local_audio_path}")

    # Run diarization using WhisperX
    logger.info("Starting diarization...")
    result = model.transcribe(local_audio_path)
    transcript = result.get("text", "")
    logger.info("Diarization complete.")

    # Remove the temporary file
    os.remove(local_audio_path)

    # Update the meetings table with the transcript and timestamp
    try:
        with engine.connect() as connection:
            update_query = text("""
                UPDATE meetings
                SET transcription = :transcript,
                    updated_at = :now
                WHERE id = :job_id
            """)
            connection.execute(update_query, {
                "transcript": transcript,
                "job_id": job_id,
                "now": datetime.utcnow()
            })
            connection.commit()
        logger.info(f"Updated meeting {job_id} with transcript.")

        # Update job status to COMPLETED
        update_job_status(job_id, "COMPLETED")
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        update_job_status(job_id, "FAILURE")
        raise


if __name__ == "__main__":
    if not JOB_ID:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        exit(1)

    try:
        logger.info(f"Fetching audio URL for job {JOB_ID}")
        s3_url = get_audio_url(JOB_ID)
        logger.info(f"Retrieved audio URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {JOB_ID}: {e}")
        update_job_status(JOB_ID, "FAILURE")
        exit(1)
    try:
        logger.info(f"Parsing s3_audio_url: {s3_url}")
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error in parsing S3 audio URL: {s3_url} for job {JOB_ID}: {e}")
        update_job_status(JOB_ID, "FAILURE")
        exit(1)

    try:
        logger.info(f"Processing job {JOB_ID} for audio file {s3_url}")
        process_audio(JOB_ID, bucket, key)
    except Exception as e:
        logger.error(f"Error in processing diarization for job {JOB_ID}.")
        update_job_status(JOB_ID, "FAILURE")

    try:
        notify_flask_server(JOB_ID)
        logger.info(f"Sent a message to the flask server to start transcription for job_id: {JOB_ID}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start transcription for job_ID: {JOB_ID}")
        