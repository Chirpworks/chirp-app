# speaker_diarization_linux_alt.py

import os
import sys
import json
import tempfile
import traceback
from urllib.parse import urlparse

import torch
import torch.nn.functional as F
import subprocess
import boto3
import logging
from datetime import timedelta
import requests
import librosa

from transformers import WhisperProcessor, WhisperForConditionalGeneration

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from whisperx.diarize import DiarizationPipeline

from app import Job, Meeting
from app.models.job import JobStatus

# ——————————————————————————————————————————
# ENVIRONMENT & CACHE SETUP
# ——————————————————————————————————————————

os.environ["HF_HOME"] = "/root/.cache/huggingface"

# If you need to pass a Hugging Face token at runtime for private models:
HF_TOKEN = os.getenv("HF_TOKEN", None)

# The model ID we want to use:
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"

# Use a persistent volume for Transformers/HF caching:
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")
# Make sure HF_HOME also points to the same cache directory:
os.environ["TRANSFORMERS_CACHE"] = cache_dir
os.environ["HF_HOME"] = cache_dir

# DEVICE
device = "cuda" if torch.cuda.is_available() else "cpu"

# ——————————————————————————————————————————
# LOGGER SETUP
# ——————————————————————————————————————————

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Using device: {device}")

# ——————————————————————————————————————————
# DATABASE & S3 CLIENT SETUP
# ——————————————————————————————————————————

# Environment variables provided at container‐runtime
JOB_ID = os.environ.get("JOB_ID")
DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g. "postgresql://user:pass@host/db"
FLASK_API_URL = os.getenv("FLASK_API_URL")

# Initialize AWS S3 client
s3_client = boto3.client("s3")

# Initialize SQLAlchemy session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# ——————————————————————————————————————————
# LOAD HF WHISPER – PURE PYTORCH (NO CTRANSLATE2)
# ——————————————————————————————————————————

try:
    logger.info(f"Loading HF WhisperProcessor + WhisperForConditionalGeneration for '{WHISPER_MODEL}' on {device}…")
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
    # We will also reference model.config.language_codes (list of strings) for language‐id → code mapping.
    logger.info("HF Whisper model loaded successfully.")
except Exception as e:
    logger.exception(f"Error loading HF Whisper ({WHISPER_MODEL}): {e}")
    sys.exit(1)


# ——————————————————————————————————————————
# UTILITY FUNCTIONS
# ——————————————————————————————————————————

def format_timestamp(seconds: float) -> str:
    return str(timedelta(seconds=round(seconds)))


def parse_s3_url(s3_url: str):
    """
    Parses an S3 URL of the form s3://bucket/key and returns (bucket, key).
    """
    parsed = urlparse(s3_url)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URL: {s3_url}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def update_job_status(job_id: str, status: JobStatus):
    """
    Updates the 'status' field of Job in the database.
    """
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = status
            session.commit()
        else:
            logger.error(f"Job {job_id} not found when trying to update status to {status}.")
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise ex


def get_audio_url(job_id: str) -> str:
    """
    Queries the Job table to fetch the S3 URL for the audio file.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Uses ffmpeg to convert a downloaded .mp3 into a 16 kHz, mono .wav.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    cmd = [
        "ffmpeg", "-y", "-i", mp3_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def notify_flask_server(job_id: str):
    """
    Notify our Flask API that transcription+diarization is done.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        requests.post(url, json={"job_id": job_id})
    except Exception as e:
        logger.exception(f"Unable to POST to Flask API at {url}: {e}")


# ——————————————————————————————————————————
# TRANSCRIPTION (PURE HF) + LANGUAGE DETECTION
# ——————————————————————————————————————————

def transcribe_with_whisper(wav_path: str):
    """
    1) Load the entire .wav file via librosa at 16 kHz.
    2) Run HF WhisperForConditionalGeneration.detect_language(...) to pick the language.
    3) Build the forced‐decoder prompt for transcription.
    4) Generate full transcript in one shot.

    Returns:
        (transcription_text: str, language_code: str)
    """
    try:
        # Load audio at 16 kHz, mono
        wav, sr = librosa.load(wav_path, sr=16000)
    except Exception as e:
        logger.exception(f"Error loading audio for transcription: {e}")
        raise

    # Processor → input_features (shape: (1, num_frames))
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    # — Detect language logits (shape: (1, n_langs)) via the built‐in method
    with torch.no_grad():
        # This returns raw logits; we pick argmax over dimension –1
        lang_logits = whisper_model.detect_language(inputs)
    lang_id = torch.argmax(lang_logits, dim=-1).item()

    # Map language ID → code via model.config.language_codes
    try:
        language = whisper_model.config.language_codes[lang_id]
    except Exception:
        # Fallback: if something goes wrong, default to English
        language = "en"
    logger.info(f"Detected language: {language}")

    # — Build the forced‐decoder prompt for transcription in that language
    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language, task="transcribe")

    # — Generate (beam search with up to 5 beams)
    with torch.no_grad():
        generated_ids = whisper_model.generate(
            inputs,
            forced_decoder_ids=forced_decoder_ids,
            num_beams=5,
            max_length=448,         # typical max_length for Whisper transcripts
            early_stopping=True
        )

    # Decode back to text
    transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    logger.info(f"Full transcript: {transcription[:100]}{'...' if len(transcription)>100 else ''}")

    return transcription, language


# ——————————————————————————————————————————
# DIARIZATION (PYANNOTE)
# ——————————————————————————————————————————

def diarize_audio(wav_path: str, device="cuda", hf_token=None):
    """
    Run pyannote.audio's DiarizationPipeline over the entire .wav.
    Returns the raw list of speaker segments.
    """
    diarization_pipeline = DiarizationPipeline(use_auth_token=hf_token, device=device)
    try:
        diarization = diarization_pipeline(wav_path)
    except Exception as e:
        logger.exception(f"Error running diarization pipeline: {e}")
        raise
    return diarization  # this is a pyannote Note:Segment-->{"start":..., "end":..., "speaker":...}


# ——————————————————————————————————————————
# MAIN AUDIO PROCESSING LOGIC
# ——————————————————————————————————————————

def process_audio(job_id: str, bucket: str, key: str):
    """
    1) Download the .mp3 from S3
    2) Convert to .wav
    3) Transcribe + detect language (entire file)
    4) Diarize (entire file)
    5) Write back to database: Meeting.transcription (full text) and Meeting.diarization (JSON‐serialized speaker segments)
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: s3://{bucket}/{key}")

        # Download to a temp .mp3 file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
            local_mp3_path = tmp_mp3.name

        s3_client.download_file(bucket, key, local_mp3_path)
        logger.info(f"Downloaded MP3 to '{local_mp3_path}'")

        # Convert to WAV
        local_wav_path = convert_mp3_to_wav(local_mp3_path)
        logger.info(f"Converted to WAV: '{local_wav_path}'")

        # — Transcribe + detect language (one shot)
        transcription_text, language = transcribe_with_whisper(local_wav_path)
        logger.info(f"Transcription complete. Detected language='{language}'")

        # — Diarize to get speaker‐level segments
        diarization_segments = diarize_audio(local_wav_path, device=device, hf_token=HF_TOKEN)
        logger.info(f"Diarization returned {len(diarization_segments)} segments.")

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # ——————————————————————————————————————————
    # WRITE TRANSCRIPTION & DIARIZATION TO THE DATABASE
    # ——————————————————————————————————————————
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()

        if meeting:
            # Store full transcript as a single string
            meeting.transcription = transcription_text
            # Store speaker‐segments as JSON: each segment has start, end, speaker label
            # We need to convert pyannote “Annotation” object to a plain list of dicts
            plain_segments = []
            for turn, _, speaker in diarization_segments.itertracks(yield_label=True):
                plain_segments.append({
                    "start": float(turn.start),  # convert to plain float
                    "end": float(turn.end),
                    "speaker": speaker
                })
            meeting.diarization = json.dumps(plain_segments)
            session.commit()
            logger.info(f"Updated meeting {meeting.id} with transcription + diarization.")
        else:
            logger.error(f"Meeting record for job_id={job_id} not found.")
            update_job_status(job_id, JobStatus.FAILURE)
            return

        update_job_status(job_id, JobStatus.COMPLETED)

    except Exception as e:
        logger.exception(f"Error writing results for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        return


# ——————————————————————————————————————————
# ENTRY POINT
# ——————————————————————————————————————————

def run_diarization(job_id: str):
    if not job_id:
        logger.error("Missing JOB_ID environment variable. Exiting.")
        sys.exit(1)

    # 1) Look up the audio URL for this job
    try:
        s3_url = get_audio_url(job_id)
        logger.info(f"Retrieved audio URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    # 2) Parse the S3 URL
    try:
        bucket, key = parse_s3_url(s3_url)
        logger.info(f"Parsed S3 URL → bucket='{bucket}', key='{key}'")
    except Exception as e:
        logger.exception(f"Error parsing S3 URL '{s3_url}' for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    # 3) Process (download, transcribe, diarize, store)
    try:
        process_audio(job_id, bucket, key)
    except Exception:
        # process_audio already logs & sets FAILURE if it crashes
        pass

    # 4) Notify Flask that we're done
    try:
        notify_flask_server(job_id)
        logger.info(f"Notified Flask to start analysis for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job {job_id}: {e}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
