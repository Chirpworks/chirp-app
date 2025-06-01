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
import logging
from datetime import timedelta
import requests

from faster_whisper import WhisperModel
from whisperx.diarize import DiarizationPipeline

from app import Job, Meeting
from app.models.job import JobStatus

# ─── ENVIRONMENT SETUP ─────────────────────────────────────────────────────────

# Ensure HF caches everything under /model_cache (both Faster-Whisper conversion
# and any Transformers artifacts WhisperX might need).
os.environ["TRANSFORMERS_CACHE"] = "/model_cache"
os.environ["HF_HOME"] = "/model_cache"

# Choose the exact HF‐style identifier you want:
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"
# (You can swap to any other HF‐available Whisper model.)

# Decide on GPU vs. CPU:
device = "cuda" if torch.cuda.is_available() else "cpu"

# Logging:
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Using device: {device}")

# ─── LOAD THE FASTER‐WHISPER MODEL (ONCE) ─────────────────────────────────────────

# We instantiate a single WhisperModel from faster-whisper.  This will:
#  1) Download HF weights (if missing) into /model_cache/hub/models--vasista22--whisper-hindi-large-v2/…
#  2) Convert them to a CTranslate2 “model.bin” on GPU (if `device == "cuda"`).
#  3) Keep a handle in `fw_model` for fast transcription+language detection at runtime.
logger.info(f"Loading Faster‐Whisper model '{WHISPER_MODEL}' on {device} …")
fw_model = WhisperModel(
    WHISPER_MODEL,
    device=device,
    compute_type="float32"  # keep float32 so it’s compatible with GPU CTranslate2
)
logger.info(f"Successfully loaded Faster‐Whisper '{WHISPER_MODEL}'.")


# ─── AWS, DATABASE, AND FLASK SETUP ───────────────────────────────────────────────

# Environment variable for JOB_ID (injected by ECS or your serverless runner):
JOB_ID = os.environ.get("JOB_ID")

# You must set DATABASE_URL and FLASK_API_URL in your container environment:
DATABASE_URL = os.environ.get("DATABASE_URL")   # e.g. "postgresql://user:pass@host/db"
FLASK_API_URL = os.getenv("FLASK_API_URL")       # e.g. "https://your-flask/api"

# AWS S3 client (will use whatever IAM role or credentials are present):
s3_client = boto3.client("s3")

# SQLAlchemy session:
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────────

def update_job_status(job_id: str, status: JobStatus):
    """
    Update the status of a Job in the DB.
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
        raise


def parse_s3_url(s3_url: str):
    """
    Parse an s3://bucket/key URL and return (bucket, key).
    """
    parsed = urlparse(s3_url)
    if parsed.scheme != "s3":
        raise ValueError("Expected s3:// URL")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def get_audio_url(job_id: str) -> str:
    """
    Query the DB for this job_id’s S3 audio URL.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found in DB for job_id {job_id}")


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Use ffmpeg to convert an MP3 file to 16kHz mono WAV in-place.
    Returns the new .wav path.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    command = [
        "ffmpeg",
        "-y",
        "-i", mp3_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        wav_path,
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds: float) -> str:
    """
    Convert a float number of seconds into H:MM:SS (rounded) for logging or storage.
    """
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id: str):
    """
    Hit the Flask endpoint to let it know transcription+diarization is done.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        requests.post(url, json={"job_id": job_id})
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job {job_id}: {e}")


# ─── CORE: TRANSCRIBE + ALIGN (FULL AUDIO, NO SPLITTING) ──────────────────────────

def transcribe_with_whisper(wav_path: str):
    """
    1) Use Faster-Whisper (`fw_model`) to:
         • detect language (info.language)
         • produce a list of coarse segments (each with text, start, end)
    2) Convert those segments into the format WhisperX expects (list of dicts)
    3) Load WhisperX’s aligner and run `whisperx.align(...)` on the dictionary list
       to get word-level timestamps and the final “aligned” structure.
    Returns: (aligned_result, language_code)
    """
    # • Faster-Whisper’s `transcribe` automatically does language detection
    logger.info(f"Faster-Whisper: transcribing + detecting language on entire file…")
    segments, info = fw_model.transcribe(
        wav_path,
        beam_size=5,          # you can tune beam size
        temperature=0.0       # greedy / deterministic
        # You can pass `vad_filter=True` or other kwargs if desired
    )
    language = info.language  # e.g. 'hi' or 'en'

    # Construct a list of plain dicts for WhisperX alignment
    # Each `seg` from Faster-Whisper has `.start`, `.end`, `.text`.
    hf_segments = []
    for seg in segments:
        hf_segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text
        })

    # Now load WhisperX’s alignment model for the detected language:
    align_model, metadata = whisperx.load_align_model(
        language_code=language,
        device=device
    )

    # Align at word-level:
    logger.info(f"WhisperX: aligning {len(hf_segments)} segments to get word-level timestamps…")
    aligned_result = whisperx.align(
        hf_segments,
        align_model,
        metadata,
        wav_path,
        device=device,
        return_char_alignments=False
    )

    return aligned_result, language


# ─── CORE: DIARIZE & ASSIGN SPEAKER ────────────────────────────────────────────────

def diarize_and_assign_speakers(aligned_result, wav_path: str, hf_token: str = None):
    """
    1) Run pyannote.audio diarization on the full WAV.
    2) Assign each aligned word to a speaker using WhisperX’s helper.
    """
    # DiarizationPipeline needs an HF token if you’re using a private HF checkpoint.
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)

    # Now assign each word in aligned_result to the appropriate speaker:
    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, aligned_result)
    return speaker_aligned


def group_words_into_segments(words, max_gap: float = 1.0):
    """
    Take a flat list of word‐dicts (each with "start","end","word","speaker")
    and merge them into larger segments as long as:
      • the speaker didn’t change, and
      • the gap between words ≤ max_gap seconds.
    Returns a list of {"start":…, "end":…, "text":…, "speaker":…}.
    """
    segments = []
    if not words:
        return segments

    # Start the first segment
    current = {
        "start": words[0]["start"],
        "end": words[0]["end"],
        "text": words[0]["word"],
        "speaker": words[0]["speaker"]
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
                "speaker": w["speaker"]
            }
        else:
            # Extend the current segment
            current["end"] = w["end"]
            current["text"] += " " + w["word"]
    segments.append(current)
    return segments


# ─── MAIN AUDIO PROCESSING ───────────────────────────────────────────────────────

def process_audio(job_id: str, bucket: str, key: str):
    """
    1) Download MP3 from S3
    2) Convert to WAV
    3) Transcribe+align via Faster-Whisper → WhisperX
    4) Diarize + assign speakers
    5) Group words into speaker‐homogeneous segments
    6) Save results in DB and notify Flask
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio from S3: bucket={bucket}, key={key}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav_file:
            local_wav_path = tmp_wav_file.name

        # Actually download as MP3 first, then convert:
        mp3_path = local_wav_path.replace(".wav", ".mp3")
        s3_client.download_file(bucket, key, mp3_path)
        logger.info(f"Downloaded MP3 to '{mp3_path}', now converting to WAV…")
        local_wav_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio is ready at '{local_wav_path}'")

        # Transcribe + align:
        transcription_aligned, language = transcribe_with_whisper(local_wav_path)
        logger.info(f"Aligned transcription: (lang={language}) {transcription_aligned}")

        # Diarize and assign speakers:
        speaker_words = diarize_and_assign_speakers(
            transcription_aligned, local_wav_path, hf_token=os.getenv("HF_API_TOKEN")
        )
        logger.info(f"Speaker‐assigned words: {speaker_words}")

        # Flatten “segments → words” into a single word list
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))

        # Group flat words into larger speaker‐homogeneous segments
        diarization = group_words_into_segments(flat_words)
        # Annotate each segment with the detected language
        for seg in diarization:
            seg["language"] = language

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # ─── UPDATE MEETING RECORD & JOB STATUS ────────────────────────────────────
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = (
            session.query(Meeting).filter_by(id=job.meeting_id).first()
            if job else None
        )
        if meeting:
            meeting.transcription = json.dumps(transcription_aligned)
            meeting.diarization = json.dumps(diarization)
            session.commit()
            logger.info(f"Updated Meeting (id={meeting.id}) with transcript+diarization.")
            update_job_status(job_id, JobStatus.COMPLETED)
        else:
            logger.error(f"Meeting record not found for job_id={job_id}.")
            update_job_status(job_id, JobStatus.FAILURE)

    except Exception as e:
        logger.exception(f"Error saving transcript for job={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────────

def run_diarization(job_id: str):
    """
    1) Look up S3 URL
    2) Parse bucket/key
    3) Call process_audio
    4) Notify Flask
    """
    if not job_id:
        logger.error("Missing JOB_ID environment variable. Exiting.")
        sys.exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        logger.info(f"Found S3 URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    try:
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error parsing S3 URL {s3_url} for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    # Do the heavy lifting
    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"process_audio raised an exception for job_id={job_id}")
        # process_audio already updated the job status to FAILURE if needed.
        return

    # Finally, notify Flask that it can proceed to the next stage
    try:
        notify_flask_server(job_id)
        logger.info(f"Sent notification to Flask for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server after completing job {job_id}: {e}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
