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
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
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
    Updates the job status via API endpoint.
    """
    try:
        # Use API endpoint to update job status
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/update_status"
        
        payload = {
            "job_id": job_id,
            "status": status.value
        }
        
        response = requests.post(endpoint, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Updated job {job_id} with status {status.value} via API")
        else:
            logger.error(f"Failed to update job {job_id} status via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database update if API fails
            logger.info(f"Falling back to direct database update for job {job_id}")
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = status
                session.commit()
                logger.info(f"Updated job {job_id} with status {status.value} via database fallback")
            else:
                logger.error(f"Job {job_id} not found in database fallback")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database update if API request fails
        logger.info(f"Falling back to direct database update for job {job_id}")
        try:
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = status
                session.commit()
                logger.info(f"Updated job {job_id} with status {status.value} via database fallback")
            else:
                logger.error(f"Job {job_id} not found in database fallback")
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            raise db_ex
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise ex


def get_audio_url(job_id):
    """
    Gets the S3 URL for the audio file for the given job_id via API endpoint.
    """
    try:
        # Use API endpoint to get audio URL
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/{job_id}/audio_url"
        
        response = requests.get(endpoint, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Retrieved audio URL for job {job_id} via API")
            return data['s3_audio_url']
        else:
            logger.error(f"Failed to get audio URL for job {job_id} via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database query if API fails
            logger.info(f"Falling back to direct database query for job {job_id}")
            job = session.query(Job).filter_by(id=job_id).first()
            if job and job.s3_audio_url:
                logger.info(f"Retrieved audio URL for job {job_id} via database fallback")
                return job.s3_audio_url
            else:
                raise ValueError(f"No audio URL found for job_id {job_id}")


    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database query if API request fails
        logger.info(f"Falling back to direct database query for job {job_id}")
        try:
            job = session.query(Job).filter_by(id=job_id).first()
            if job and job.s3_audio_url:
                logger.info(f"Retrieved audio URL for job {job_id} via database fallback")
                return job.s3_audio_url
            else:
                raise ValueError(f"No audio URL found for job_id {job_id}")
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            raise db_ex
    except Exception as ex:
        logger.exception(f"Error getting audio URL for job {job_id}: {ex}")
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
        # Use API endpoint to update meeting transcription
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/{job_id}/meeting/transcription"
        
        payload = {
            "transcription": json.dumps(diarization)
        }
        
        response = requests.put(endpoint, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Updated meeting transcription for job {job_id} via API")
            logger.info(f"Transcription completed for job {job_id}. Job remains in IN_PROGRESS status pending analysis.")
        else:
            logger.error(f"Failed to update meeting transcription for job {job_id} via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database update if API fails
            logger.info(f"Falling back to direct database update for job {job_id}")
            meeting = None
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
            if meeting:
                meeting.transcription = json.dumps(diarization)
                session.commit()
                logger.info(f"Updated meeting {meeting.id} with transcript via database fallback.")
                logger.info(f"Transcription completed for job {job_id}. Job remains in IN_PROGRESS status pending analysis.")
            else:
                logger.error(f"Meeting not found for job {job_id}.")
                update_job_status(job_id, JobStatus.FAILURE)

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database update if API request fails
        logger.info(f"Falling back to direct database update for job {job_id}")
        try:
            meeting = None
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
            if meeting:
                meeting.transcription = json.dumps(diarization)
                session.commit()
                logger.info(f"Updated meeting {meeting.id} with transcript via database fallback.")
                logger.info(f"Transcription completed for job {job_id}. Job remains in IN_PROGRESS status pending analysis.")
            else:
                logger.error(f"Meeting not found for job {job_id}.")
                update_job_status(job_id, JobStatus.FAILURE)
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            update_job_status(job_id, JobStatus.FAILURE)
            raise db_ex
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def transcribe_and_diarize(audio_file_path):
    API_KEY = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=API_KEY)

    audio_file = client.files.upload(file=audio_file_path)

    prompt = """You are a professional call transcription and analysis expert. Please transcribe and analyze this business call recording.

CONTEXT: This is a business call between a seller (sales representative) and a buyer (potential customer). The call may contain sales discussions, product presentations, negotiations, or customer service interactions.

TASK: Please provide a detailed transcription with speaker diarization and classification.

REQUIREMENTS:
1. Transcribe the audio accurately, handling multiple languages (English, Hindi, Punjabi, Tamil, Telugu, Malayalam)
2. Provide English transliteration for all non-English speech
3. Identify and separate speakers clearly
4. Classify each speaker as either "buyer" or "seller" based on context clues
5. Provide English translation for non-English segments
6. Maintain chronological order of speech

OUTPUT FORMAT: Return ONLY a valid JSON array with this exact structure:
[
  {
    "speaker_id": "speaker_1",
    "speaker_role": "buyer|seller",
    "text": "English transliteration of what was said",
    "translation": "English translation if original was not in English",
    "timestamp_start": "approximate_start_time",
    "timestamp_end": "approximate_end_time",
    "confidence": "high|medium|low"
  }
]

CLASSIFICATION GUIDELINES:
- SELLER: Person presenting products/services, asking qualifying questions, discussing pricing, following up on leads
- BUYER: Person asking about products/services, expressing needs/concerns, negotiating terms, making purchasing decisions

IMPORTANT: 
- Return ONLY the JSON array, no additional text or markdown formatting
- Ensure JSON is properly formatted and valid
- If uncertain about speaker role, use context clues from the conversation
- Handle overlapping speech by creating separate entries
- Mark unclear speech with low confidence"""

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20", 
        contents=[prompt, audio_file]
    )

    # Improved JSON parsing
    response_text = response.text
    if response_text is None:
        raise ValueError("Empty response from Gemini API")
    response_text = response_text.strip()
    logger.info(f"Raw Gemini response: {response_text}")
    
    # Remove any markdown formatting if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1]
    
    response_text = response_text.strip()
    logger.info(f"Cleaned response text: {response_text}")
    
    try:
        parsed_response = json.loads(response_text)
        
        # Validate and process the response
        transcription = ''
        diarization = []
        
        for segment in parsed_response:
            # Build full transcription
            transcription += segment.get('text', '') + ' '
            
            # Validate and clean segment
            clean_segment = {
                'speaker': segment.get('speaker_id', 'unknown'),
                'role': segment.get('speaker_role', 'unknown'),
                'text': segment.get('text', ''),
                'translation': segment.get('translation', ''),
                'confidence': segment.get('confidence', 'medium')
            }
            diarization.append(clean_segment)
        
        logger.info(f"Successfully processed {len(diarization)} segments")
        return transcription.strip(), diarization
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Raw response: {response_text}")
        raise ValueError(f"Invalid JSON response from Gemini: {e}")


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
    run_diarization(JOB_ID)
