# speaker_diarization_linux_alt.py

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
import librosa

from whisperx.diarize import DiarizationPipeline
from transformers import WhisperProcessor, WhisperForConditionalGeneration

from app import Job, Meeting
from app.models.job import JobStatus

# ──────────────────────────────────────────────────────────────────────────────
# 1) ENVIRONMENT & LOGGING
# ──────────────────────────────────────────────────────────────────────────────

# Force HF to cache under /model_cache
os.environ["HF_HOME"] = "/model_cache"
os.environ["TRANSFORMERS_CACHE"] = "/model_cache"

# If you have a HF token, make sure it's in the environment
#   e.g. export HUGGINGFACE_HUB_TOKEN="hf_xxx"
HF_TOKEN = os.environ.get("HUGGINGFACE_HUB_TOKEN", "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")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The Vasista Hindi‐Large‐V2 model identifier
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"

# DEVICE: cuda if available, else cpu
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# ──────────────────────────────────────────────────────────────────────────────
# 2) LOAD HF Whisper (Vasista) ONCE
# ──────────────────────────────────────────────────────────────────────────────
#
# We explicitly load the HF “vasista22/whisper-hindi-large-v2” model + processor here.
# WhisperForConditionalGeneration supports both `predict_language(...)` and `generate(...)`.
# We will call `predict_language` first to get “hi” vs “en” for each recording.

try:
    logger.info(f"Loading HF WhisperProcessor + WhisperForConditionalGeneration for '{WHISPER_MODEL}' on {device}…")
    processor = WhisperProcessor.from_pretrained(WHISPER_MODEL, use_auth_token=HF_TOKEN)
    whisper_model = WhisperForConditionalGeneration.from_pretrained(
        WHISPER_MODEL, use_auth_token=HF_TOKEN
    ).to(device)
    whisper_model.eval()
    logger.info("HF Vasista whisper‐hindi‐large‐v2 loaded successfully.")
except Exception as e:
    logger.exception(f"Failed to load HF model '{WHISPER_MODEL}': {e}")
    raise


# ──────────────────────────────────────────────────────────────────────────────
# 3) OTHER SETUP (S3, DATABASE, etc.)
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# 4) HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = [
        'ffmpeg',
        '-y',
        '-i', mp3_path,
        '-ar', '16000',
        '-ac', '1',
        '-c:a', 'pcm_s16le',
        wav_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds):
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id):
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        requests.post(url, json={"job_id": job_id})
    except Exception:
        logger.exception(f"Failed to notify Flask server for job_id={job_id}")


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
            logger.error(f"Job {job_id} not found in database.")
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise


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
        raise


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def group_words_into_segments(words, max_gap=1.0):
    """
    From a flat list of aligned words (with 'start', 'end', 'word', 'speaker'),
    produce speaker‐segmented chunks.
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


# ──────────────────────────────────────────────────────────────────────────────
# 5) TRANSCRIPTION: HF Vasista + LANGUAGE DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def transcribe_with_whisper(havapath: str):
    """
    Use HF Vasista whisper-hindi-large-v2 to:
      1) Load raw audio (librosa @ 16kHz, mono)
      2) Predict language via whisper_model.predict_language(...)
      3) Generate full transcription via whisper_model.generate(...)
      4) Decode to plain text
    Returns:
      transcription (str), detected_language (str, e.g. "hi" or "en")
    """
    # 1) Load audio via librosa (16 kHz mono)
    wav, sr = librosa.load(havapath, sr=16000)

    # 2) Preprocess for the HF model
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    # 3) Language detection
    with torch.no_grad():
        lang_logits = whisper_model.predict_language(inputs)  # (batch_size=1, n_langs)
        lang_probs = torch.softmax(lang_logits, dim=-1)
        lang_id = torch.argmax(lang_probs, dim=-1).item()
        # The tokenizer’s vocab: id→token string (e.g. "en", "hi", ...)
        detected_lang_token = processor.tokenizer.decoder.lang_token_to_id.get(lang_id, None)
        # Actually, HF’s WhisperForConditionalGeneration.predict_language returns a tensor of shape (1, lang_vocab_size),
        # so lang_id itself is already the index in the lang‐vocab. We can decode via:
        detected_language = processor.tokenizer.decode([lang_id]).strip()
        if detected_language == "":
            # Fallback if decode didn’t yield a clean code
            detected_language = "en"

    logger.info(f"⮞ Detected language: {detected_language}  (prob={lang_probs[0,lang_id].item():.3f})")

    # 4) Generate transcription tokens. We do *not* force a language token here,
    #    because HF’s default setup will emit “<|lang|> … actual text …” anyway.
    with torch.no_grad():
        predicted_ids = whisper_model.generate(
            inputs,
            # generation parameters can be tuned; we leave defaults except beam_size:
            num_beams=5,
            eos_token_id=processor.tokenizer.eos_token_id,
            forced_decoder_ids=None,  # let the model pick its own <|lang|> token
        )

    # 5) Decode to plain text
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()

    return transcription, detected_language


# ──────────────────────────────────────────────────────────────────────────────
# 6) DIARIZATION & ASSIGN SPEAKERS
# ──────────────────────────────────────────────────────────────────────────────

def diarize_and_assign_speakers(result_aligned, wav_path, device="cuda", hf_token=None):
    """
    Runs pyannote diarization, then aligns words→speakers.
    """
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)
    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, result_aligned)
    return speaker_aligned


# ──────────────────────────────────────────────────────────────────────────────
# 7) MAIN PROCESSING PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

def process_audio(job_id, bucket, key):
    """
    Downloads from S3, converts to WAV, transcribes+aligns with HF Vasista,
    runs diarization, writes results back to DB.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)
        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Download into a temporary .mp3 → .wav
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
            local_wav_path = tmp_wav.name

        local_mp3_path = local_wav_path.replace(".wav", ".mp3")
        s3_client.download_file(bucket, key, local_mp3_path)
        logger.info(f"Downloaded MP3 to '{local_mp3_path}', converting to WAV…")
        local_wav_path = convert_mp3_to_wav(local_mp3_path)
        logger.info(f"Converted and ready at '{local_wav_path}'")

        # 1) Transcribe + language‐detect
        transcription_text, language = transcribe_with_whisper(local_wav_path)
        logger.info(f"⮞ Raw transcription: {transcription_text}")
        logger.info(f"⮞ Final detected language: {language}")

        # 2) Load WhisperX alignment model (per detected_language)
        align_model, metadata = whisperx.load_align_model(
            language_code=language, device=device
        )
        result_aligned = whisperx.align(
            # We need WhisperX segments as input—instead of leaving it to WhisperX’s own .transcribe(),
            # we just supply “fake segments” so that align_model can align word‐level timing. Evil hack:
            #   We split `transcription_text` into one big segment at [0, duration], so alignment still works.
            #
            # Actually: WhisperX expects a `segments` list where each seg is: {"start", "end", "text"}.
            # We do a single segment from 0→∞ to force align_model to align all words.
            # (Better: You could break up `transcription_text` by sentences; but this works.)
            [{"start": 0.0, "end": 9999.0, "text": transcription_text}],
            align_model,
            metadata,
            local_wav_path,
            device=device,
            return_char_alignments=False
        )

        # 3) Speaker diarization + word→speaker
        speaker_words = diarize_and_assign_speakers(
            result_aligned, local_wav_path, device=device, hf_token=HF_TOKEN
        )
        logger.info(f"⮞ speaker_words has '{len(speaker_words.get('segments', []))}' segments")

        # 4) Flatten to a list of word‐dicts, then group into speaker‐based text segments
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))

        diarization = group_words_into_segments(flat_words)
        for seg in diarization:
            seg["language"] = language

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\nTraceback:\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # ──────────────────────────────────────────────────────────────────────────
    # 5) WRITE RESULTS BACK TO DB
    # ──────────────────────────────────────────────────────────────────────────
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()

        if meeting:
            meeting.transcription = json.dumps({
                "text": transcription_text,
                "language": language
            })
            meeting.diarization = json.dumps(diarization)
            session.commit()
            logger.info(f"Updated meeting {job_id} (ID={meeting.id}) with transcript+diarization.")
        else:
            logger.error(f"Meeting for job {job_id} not found in DB.")

        update_job_status(job_id, JobStatus.COMPLETED)
    except Exception as e:
        logger.exception(f"Error saving results for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def run_diarization(job_id):
    """
    Entrypoint: called by serverless_handler.py → this downloads via S3 URL,
    calls process_audio, and then notifies Flask for post‐processing.
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
        logger.exception(f"Error parsing S3 URL {s3_url}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    try:
        process_audio(job_id, bucket, key)
    except Exception:
        # process_audio already logs + sets FAILURE if anything goes wrong
        pass

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent notification to Flask for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job {job_id}: {e}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
