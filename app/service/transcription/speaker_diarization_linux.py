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
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import Job
from app import Meeting
from app.models.job import JobStatus
import os
# Added: Set Hugging Face cache directory
os.environ["HF_HOME"] = "/root/.cache/huggingface"


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

# Define a path within the cache directory for the 'large-v1' model.
model_cache_path = os.path.join(cache_dir, "large-v1")

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# Check if the model appears to be cached.
if not os.path.exists(model_cache_path):
    logger.info("Model not found in cache; downloading and caching the model...")
    model = whisperx.load_model("large-v1", device=device, compute_type="float32")
    # If the loaded model supports explicit saving, do so:
    try:
        model.save_pretrained(model_cache_path)
        logger.info(f"Model saved to cache at {model_cache_path}")
    except AttributeError:
        # If there's no save_pretrained method, rely on the default Transformers caching.
        logger.info("Model does not support explicit saving; relying on default caching.")
else:
    logger.info("Loading model from cache...")
    model = whisperx.load_model("large-v1", device=device, compute_type="float32")

logger.info("WhisperX large-v1 model is loaded and ready.")


def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = ['ffmpeg', '-y', '-i', mp3_path, '-ar', '16000', '-ac', '1', wav_path]
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


# def preprocess_audio(audio_path):
#     logger.info("Preprocessing audio...")
#     waveform, sample_rate = torchaudio.load(audio_path)
#     if sample_rate != 16000:
#         resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
#         waveform = resampler(waveform)
#
#     # Clip the first `trim_seconds` seconds
#     start_sample = int(6 * sample_rate)
#     if waveform.size(1) > start_sample:
#         waveform = waveform[:, start_sample:]
#     else:
#         logger.info(f"Warning: audio shorter than 6 seconds. Skipping trim.")
#
#     torchaudio.save("preprocessed.wav", waveform, 16000)
#     return "preprocessed.wav"


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

        transcripion, diarization = transcribe_and_diarize(local_audio_path)
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
            meeting.transcription = json.dumps(transcripion)
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


def transcribe_and_diarize(audio_path):
    logger.info("Running transcription with WhisperX")
    # Run diarization using WhisperX

    transcription = model.transcribe(audio_path, language='en')
    model_a, metadata = whisperx.load_align_model(language_code=transcription["language"], device=device)
    result = whisperx.align(transcription["segments"], model_a, metadata, audio_path, device)

    # Step 3: Diarization with PyAnnote
    logger.info("Running speaker diarization with PyAnnote...")
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.0",
        use_auth_token="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"
    )
    diarization_pipeline.to(torch.device(device))

    # ✅ Load parameters from pretrained model
    hyperparameters = {
        "segmentation": {
            "min_duration_off": 0.5  # 🔥 Prevents rapid speaker switching
        },
        "clustering": {
            "method": "ward",  # 🔥 Better clustering approach
            "min_cluster_size": 15  # 🔥 Avoids small noise clusters
        }
    }

    # ✅ APPLY PARAMETER CHANGES (FIXES ERROR)
    diarization_pipeline.instantiate(hyperparameters)  # 🔥 Minimum samples for a cluster

    # ✅ Run diarization with precomputed embeddings for faster processing
    with ProgressHook() as hook:
        diarization = diarization_pipeline.apply({"uri": "audio", "audio": audio_path}, num_speakers=2,
                                                 hook=hook)

    # diarization = diarization_pipeline(audio_path)

    # Step 4: Match word segments to diarization labels
    logger.info("Aligning words with speaker segments...")
    speaker_segments = list(diarization.itertracks(yield_label=True))
    words = result.get("word_segments", [])

    if not words:
        logger.info("No word-level segments found in WhisperX output. Cannot align with diarization.")
        return

    combined_output = []
    for word_info in words:
        word_start = word_info.get("start")
        word_end = word_info.get("end")
        word_text = word_info.get("word")

        if word_start is None or word_end is None:
            continue

        for turn, _, speaker in speaker_segments:
            if word_start >= turn.start and word_end <= turn.end:
                combined_output.append({
                    "speaker": speaker,
                    "start": word_start,
                    "end": word_end,
                    "text": word_text
                })
                break

    # Group consecutive words by speaker and time window
    logger.info("Final output:")
    diarization = []
    if combined_output:
        current_speaker = combined_output[0]["speaker"]
        current_start = combined_output[0]["start"]
        current_words = []

        for i, item in enumerate(combined_output):
            if item["speaker"] != current_speaker or (i > 0 and item["start"] - combined_output[i - 1]["end"] > 1.0):
                diarization.append({
                    "speaker": current_speaker,
                    "start": current_start,
                    "end": combined_output[i - 1]["end"],
                    "text": " ".join(current_words)
                })
                current_speaker = item["speaker"]
                current_start = item["start"]
                current_words = []

            current_words.append(item["text"])

        # Add last segment
        diarization.append({
            "speaker": current_speaker,
            "start": current_start,
            "end": combined_output[-1]["end"],
            "text": " ".join(current_words)
        })

    for segment in diarization:
        logger.info(f"Speaker {segment['speaker']} [{format_timestamp(segment['start'])} - {format_timestamp(segment['end'])}]: {segment['text']}")

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
