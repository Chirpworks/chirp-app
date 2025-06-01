import os
import sys
import json
import tempfile
import traceback
from urllib.parse import urlparse

import torch
import librosa                                            # ← NEW: for loading audio
from transformers import WhisperProcessor, WhisperForConditionalGeneration  # ← NEW: pure HF Whisper
import subprocess
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import timedelta
import requests

# We keep Pyannote-powered diarization exactly as before:
from whisperx.diarize import DiarizationPipeline             # ← unchanged from your prior implementations
import whisperx                                              # ← still needed for alignment + assign_word_speakers

from app import Job, Meeting
from app.models.job import JobStatus

# ──────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT + CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# (1) HuggingFace token (if your model is private or for “lazy” downloads at runtime)
HF_TOKEN = os.getenv("HF_TOKEN", None)                      # ← NEW: for loading "vasista22/whisper-hindi-large-v2"
if HF_TOKEN is None:
    logger = logging.getLogger(__name__)
    logger.warning("HF_TOKEN not set; loading will proceed anonymously if model is public.")

# (2) Where to cache HF/Transformers
os.environ["HF_HOME"] = os.getenv("HF_HOME", "/root/.cache/huggingface")
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")

# (3) Which Whisper model to use:
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"          # ← CHANGED: use “vasista22/whisper-hindi-large-v2”

# ──────────────────────────────────────────────────────────────────────────────
# LOGGER
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# LOAD HF WHISPER PROCESSOR + MODEL (PyTorch)
# ──────────────────────────────────────────────────────────────────────────────

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

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

    # ── BUILD LANGUAGE ↔ ID MAPPINGS ─────────────────────────────────────────────────────
    # In recent HF versions, `WhisperTokenizer.lang2id` or `lang_code_to_id` are gone.
    # Instead, we take `processor.tokenizer.lang_token_to_id` and strip off "<| |>".
    #
    # Example mapping that lives inside `lang_token_to_id`:
    #    { "<|en|>": 50358,  "<|hi|>": 50359,  … }
    #
    # We want: lang2id = { "en": 50358,  "hi": 50359, … }
    #          id2lang = { 50358: "en", 50359: "hi", … }
    #
    lang_token_to_id = processor.tokenizer.lang_token_to_id      # ← NEW
    lang2id = { token.strip("<|>"): idx for token, idx in lang_token_to_id.items() }  # ← NEW
    id2lang = { idx: token.strip("<|>") for token, idx in lang_token_to_id.items() }   # ← NEW

    # Finally, we must inform the model’s generation_config of our lang2id mapping,
    # so that `model.detect_language()` works correctly under the hood.
    whisper_model.generation_config.lang_to_id = lang2id      # ← NEW
    whisper_model.generation_config.id_to_lang = id2lang      # ← NEW

    logger.info(f"HF Whisper model loaded successfully.")
except Exception as e:
    logger.exception(f"Error loading HF Whisper model '{WHISPER_MODEL}': {e}")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# DATABASE + S3 + SESSION SETUP  (unchanged)
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
# HELPER FUNCTIONS: S3 URL parsing, JOB STATUS, etc.  (unchanged except tiny tweaks)
# ──────────────────────────────────────────────────────────────────────────────

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
        logger.error(f"Error parsing S3 url: {s3_url}: {e}")
        raise


def get_audio_url(job_id):
    """
    Queries the DB to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


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
        raise


def notify_flask_server(job_id):
    """
    Notify the Flask API that transcription & diarization are complete,
    so it can trigger downstream analysis.
    """
    try:
        url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
        requests.post(url, json={"job_id": job_id})
    except Exception as e:
        logger.exception(f"Failed to notify flask server for job_ID {job_id}: {e}")
        raise


def convert_mp3_to_wav(mp3_path):
    """
    Uses ffmpeg to convert an MP3 to a 16 kHz, mono WAV.
    """
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = [
        'ffmpeg', '-y', '-i', mp3_path,
        '-ar', '16000', '-ac', '1',
        '-c:a', 'pcm_s16le',
        wav_path
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def format_timestamp(seconds: float):
    return str(timedelta(seconds=round(seconds)))


# ──────────────────────────────────────────────────────────────────────────────
# TRANSCRIBE WITH PURE HF Whisper + LANGUAGE DETECTION  (REPLACES whisperx.load_model path)
# ──────────────────────────────────────────────────────────────────────────────

def transcribe_with_whisper(wav_path: str):
    """
    Load the entire WAV, detect language with HF Whisper, then transcribe with beam search.
    Returns:
      - transcription_text: str
      - language_code: str  (e.g. "hi" or "en" or "fr" etc.)
    """
    # 1) Load audio at 16 kHz mono
    wav, sr = librosa.load(wav_path, sr=16000)
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt")
    input_features = inputs.input_features.to(device)

    # 2) DETECT LANGUAGE
    #    whisper_model.detect_language(...) returns a logits tensor of shape [1, n_langs].
    with torch.no_grad():
        lang_logits = whisper_model.detect_language(input_features)   # shape (1, n_langs)
    predicted_id = torch.argmax(lang_logits, dim=-1).item()           # scalar int
    language_code = id2lang.get(predicted_id, "en")                   # default to "en" if missing
    logger.info(f"Detected language: {language_code}")

    # 3) FORCED DECODER PROMPT for "transcribe" in that language:
    #
    #    We ask the processor for the right “prefix token IDs” so that
    #    Whisper knows which language and which task.  (That’s exactly what
    #    HuggingFace’s `get_decoder_prompt_ids(...)` provides for us.)
    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language_code, task="transcribe")

    # 4) GENERATE transcription (beam search with 5 beams)
    with torch.no_grad():
        generated_ids = whisper_model.generate(
            input_features,
            forced_decoder_ids=forced_decoder_ids,
            max_length=448,      # you can tune this if needed
            num_beams=5,
        )
    transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    logger.info(f"Transcription (raw text): {transcription}")

    return transcription, language_code


# ──────────────────────────────────────────────────────────────────────────────
# DIARIZATION + WORD ASSIGNMENT  (unchanged from your prior whisperx-based flow)
# ──────────────────────────────────────────────────────────────────────────────

def diarize_and_assign_speakers(transcription_text: str, wav_path: str, language_code: str, device="cuda", hf_token=None):
    """
    1) Use WhisperX’s aligner to get word‐level timestamps from our HF transcription.
    2) Run the Pyannote diarization pipeline on the raw audio to get speaker‐time segments.
    3) Assign each word to a speaker using whisperx.assign_word_speakers(…).
    """
    # A) ALIGN THE WHISPER TRANSCRIPTION → word timestamps
    #    WhisperX needs a “segments” structure, so we give it one big segment [0..duration] + entire text.
    #    Then whisperx.align(...) will break it into word‐level alignments.
    #
    #    First, load a WhisperX alignment model:
    align_model, metadata = whisperx.load_align_model(language_code=language_code, device=device)

    #    For simplicity, we pretend the entire transcription is one “segment” from 0 → end_of_audio.
    #    We need the “end_of_audio” in seconds.  librosa can tell us that:
    wav, sr = librosa.load(wav_path, sr=16000)
    duration = len(wav) / sr

    initial_segments = [{
        "start": 0.0,
        "end": duration,
        "text": transcription_text
    }]

    result_aligned = whisperx.align(
        initial_segments,
        align_model,
        metadata,
        wav_path,
        device=device,
        return_char_alignments=False
    )

    # B) DIARIZE with Pyannote via WhisperX wrapper:
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)

    # C) ASSIGN each aligned word to a speaker
    speaker_aligned = whisperx.assign_word_speakers(diarize_segments, result_aligned)
    return speaker_aligned


def group_words_into_segments(words, max_gap=1.0):
    """
    Exactly your original logic:
    Take a list of word‐dicts with fields ["start","end","word","speaker"]
    and stitch them into larger “speaker segments.”
    """
    segments = []
    if not words:
        return segments

    current = {
        "start": words[0]["start"],
        "end":   words[0]["end"],
        "text":  words[0]["word"],
        "speaker": words[0]["speaker"]
    }

    for i in range(1, len(words)):
        word = words[i]
        gap = word["start"] - current["end"]
        if gap > max_gap or word["speaker"] != current["speaker"]:
            segments.append(current)
            current = {
                "start": word["start"],
                "end":   word["end"],
                "text":  word["word"],
                "speaker": word["speaker"]
            }
        else:
            current["end"] = word["end"]
            current["text"] += " " + word["word"]
    segments.append(current)
    return segments


# ──────────────────────────────────────────────────────────────────────────────
# MAIN AUDIO PROCESSING FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def process_audio(job_id, bucket, key):
    """
    1) Download MP3 from S3
    2) Convert to WAV
    3) Run HF Whisper (detect_language + transcribe)
    4) Run WhisperX‐based alignment + Pyannote diarization + word→speaker assignment
    5) Package up segments → store in DB
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")
        # Download MP3 → temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_wav:
            local_wav_path = tmp_wav.name  # create .wav filename, but we'll actually write .mp3 first

        mp3_path = local_wav_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)
        logger.info(f"Downloaded MP3 to '{mp3_path}', converting to WAV…")
        local_wav_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Converted and ready at '{local_wav_path}'")

        # ───────────────────────────────────────────────────────────────────
        # 3) TRANSCRIBE + DETECT LANGUAGE (pure HF Whisper)
        transcription_text, language = transcribe_with_whisper(local_wav_path)
        logger.info(f"transcription_text: {transcription_text}")
        logger.info(f"language: {language}")

        # ───────────────────────────────────────────────────────────────────
        # 4) DIARIZATION + WORD→SPEAKER
        speaker_words = diarize_and_assign_speakers(
            transcription_text,
            local_wav_path,
            language,
            device=device,
            hf_token=HF_TOKEN
        )
        logger.info(f"speaker_words: {speaker_words}")

        # Flatten the nested word lists into one list of word‐dicts
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))

        diarization = group_words_into_segments(flat_words)
        for segment in diarization:
            segment["language"] = language

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # ───────────────────────────────────────────────────────────────────
    # 5) WRITE BACK TO DATABASE
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
            if meeting:
                meeting.transcription = json.dumps(transcription_text)
                meeting.diarization = json.dumps(diarization)
                session.commit()
                logger.info(f"Updated meeting {job_id} with transcript & diarization.")
            else:
                logger.error(f"Meeting for job_id={job_id} not found.")
        else:
            logger.error(f"Job {job_id} not found.")

        update_job_status(job_id, JobStatus.COMPLETED)
    except Exception as e:
        logger.exception(f"Error writing to DB for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


# ──────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ──────────────────────────────────────────────────────────────────────────────

def run_diarization(job_id):
    if not job_id:
        logger.error("Missing required env var JOB_ID. Exiting.")
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
        logger.info(f"Parsing s3_audio_url: {s3_url}")
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error parsing S3 URL '{s3_url}' for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        sys.exit(1)

    try:
        process_audio(job_id, bucket, key)
    except Exception:
        # process_audio itself logs & sets status
        pass

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
