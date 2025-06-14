import json
import subprocess
import tempfile
from urllib.parse import urlparse

import logging
import os
from google import genai
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import boto3
import requests

from app import Job
from app import Meeting
from app.models.job import JobStatus

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


def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = ['ffmpeg', '-y', '-i', mp3_path, '-ar', '16000', '-ac', '1', wav_path]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


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


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


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

        transcription, diarization = transcribe_and_diarize(local_audio_path)
    except Exception as e:
        logger.error(f"Error while transcribing audio file for job_id: {job_id}. Error: {e}")
        raise e

    # Update the meetings table with the transcript and timestamp
    try:
        meeting = None
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            meeting.transcription = json.dumps(transcription)
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


def transcribe_and_diarize(audio_file_path):
    API_KEY = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=API_KEY)

    audio_file = client.files.upload(file=audio_file_path)

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20", contents=["This is an audio clip with language being a possible mix of English. "
                                            "Hindi, Punjabi, Tamil, Telugu and Malayalam and 2 speakers."
                                            "Transcribe this audio clip and give clear speaker diarization."
                                            "Also, give me the entire response transliterated in English"
                                            "For each segment, give me a json response in the format:"
                                            "{\"speaker\": <speaker_id>, \"text\": <english_transliterated_text>, \"translation\": <translation>} "
                                                          "Pass every individual json in a list.",
                                            audio_file]
    )

    response_text = response.text
    logger.info(f"Transcription: {response_text}")
    response_text = response_text.split("```json")[1]
    response_text = response_text.strip("```json").strip("```")
    response_text = response_text.strip("'''json").strip("'''")
    logger.info(f"Transcription: {response_text}")
    response_text = json.loads(response_text)
    transcription = ''
    for segment in response_text:
        transcription += segment['text']
    diarization = response_text
    return transcription, diarization


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

