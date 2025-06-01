import os
import sys
import json
import tempfile
import traceback
from urllib.parse import urlparse

import torch
import whisperx         # for alignment & speaker‐assignment
import subprocess
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
from datetime import timedelta
import requests
import librosa

# ── NEW: Hugging Face imports for the Vasista whisper‐hindi‐large-v2 model ──
from transformers import (
    WhisperProcessor,
    WhisperForConditionalGeneration,
    WhisperTokenizer
)

from whisperx.diarize import DiarizationPipeline

from app import Job, Meeting
from app.models.job import JobStatus

# ── ENVIRONMENT VARIABLES ──
os.environ["HF_HOME"] = "/root/.cache/huggingface"   # where HF caches models
HF_TOKEN = os.getenv("HF_TOKEN", None)               # Use this if you need an auth token for private models
WHISPER_MODEL = "vasista22/whisper-hindi-large-v2"

# ── Set up logging ──
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

# Where to cache Hugging Face models (persistent volume in production)
cache_dir = os.getenv("TRANSFORMERS_CACHE", "/model_cache")
model_cache_path = os.path.join(cache_dir, WHISPER_MODEL.replace("/", "_"))

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

# ── 1) LOAD AND CACHE VASISTA WHISPER │ HF PROCESSOR & MODEL ──
# We load both Processor and Generation model once at startup.
# If the files aren’t in cache, HF will grab them (and store under HF_HOME).
#
# We ALSO build id2lang from WhisperTokenizer’s class‐level map lang_code_to_id.

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

    # ── FIXED─ Retrieve the class‐level lang_code_to_id dict, then invert it ──
    # WhisperTokenizer.lang_code_to_id is a class attribute (not on the instance).
    id2lang = {v: k for k, v in WhisperTokenizer.lang_code_to_id.items()}

    logger.info("HF Vasista whisper-hindi-large-v2 loaded successfully.")
except Exception as e:
    logger.exception(f"Error loading HF Vasista Whisper model: {e}")
    sys.exit(1)


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
        logger.exception(f"Failed to notify Flask server for job_id: {job_id}")


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


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def process_audio(job_id, bucket, key):
    """
    Downloads the audio from S3, converts to WAV, does one-pass language detection +
    transcription via HF Vasista, then aligns + diarizes via whisperx.
    Finally, stores JSON blobs in the Meeting record.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # 1) Download to a temporary MP3 file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            local_wav_path = tmp.name  # we’ll overwrite this var after conversion

        mp3_path = local_wav_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)

        # 2) Convert to WAV (16 kHz mono)
        local_wav_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file ready at '{local_wav_path}'")

        # 3) Run one‐shot language detection + transcription
        transcription_full, language = transcribe_with_whisper(local_wav_path)
        logger.info(f"Full transcription text: {transcription_full}")
        logger.info(f"Detected language: {language}")

        # 4) Run diarization on the entire WAV, then assign words → speakers
        speaker_words = diarize_and_assign_speakers(
            transcription_full,  # we’ll pass the full‐transcript segments below
            local_wav_path,
            device=device,
            hf_token=HF_TOKEN
        )
        logger.info(f"speaker_words: {speaker_words}")

        # 5) Flatten word lists into a single list of word‐dicts (if segments contain "words")
        flat_words = []
        for seg in speaker_words.get("segments", []):
            flat_words.extend(seg.get("words", []))

        diarization = group_words_into_segments(flat_words)
        for seg in diarization:
            seg["language"] = language

    except Exception as e:
        logger.exception(f"[process_audio] job={job_id} failed: {e}\n{traceback.format_exc()}")
        update_job_status(job_id, JobStatus.FAILURE)
        return

    # 6) Write back to the Meeting + update job status
    try:
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = session.query(Meeting).filter_by(id=job.meeting_id).first() if job else None

        if meeting:
            # JSON‐serialize the aligned transcription & diarization
            meeting.transcription = json.dumps(transcription_full)  # this is full text + segment dictionaries
            meeting.diarization = json.dumps(diarization)
            session.commit()
            logger.info(f"Updated meeting {job_id} with transcript + diarization.")
            update_job_status(job_id, JobStatus.COMPLETED)
        else:
            logger.error(f"Meeting for job {job_id} not found.")
            update_job_status(job_id, JobStatus.FAILURE)

    except Exception as e:
        logger.exception(f"Error updating DB for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def transcribe_with_whisper(wav_path: str):
    """
    1) Load the entire WAV via librosa (16 kHz mono).
    2) Run HF Whisper’s built-in detect_language → get a language code (e.g. "hi" or "en").
    3) Do a single‐pass generate/transcribe (no splitting).
    4) Return (transcription_full: dict, language_code: str).

    The returned transcription_full is a dictionary with:
      - "text": the full concatenated string
      - "segments": a list of dicts {start, end, text} for each segment
      - "language": the detected language code
    """
    # 1) Load audio array
    wav_audio, sr = librosa.load(wav_path, sr=16000)

    # 2) Tokenizer + Model inputs
    #    WhisperProcessor does feature extraction + tokenization under the hood
    inputs = processor(
        wav_audio,                 # raw NumPy array
        sampling_rate=sr,
        return_tensors="pt"
    ).input_features.to(device)  # (1, seq_len)

    # 3) Detect language with HF Whisper
    #    whisper_model.detect_language(...) returns a logits‐vector shaped (1, n_langs)
    with torch.no_grad():
        lang_logits = whisper_model.detect_language(inputs)  # (1, n_languages)
        lang_id = torch.argmax(lang_logits, dim=-1).item()    # e.g. 15 → id2lang[15] = "hi"
        language = id2lang.get(lang_id, "en")                # default to "en" if unknown

    # 4) Generate transcription (use forced_decoder_ids to pin both language + "transcribe" tokens)
    forced_decoder_ids = processor.get_decoder_prompt_ids(
        language=language,        # e.g. "hi" or "en"
        task="transcribe"
    )

    with torch.no_grad():
        generated_ids = whisper_model.generate(
            inputs,
            forced_decoder_ids=forced_decoder_ids,
            max_length=448,        # you can tweak as needed
            num_beams=5,
            temperature=0.0
        )

    # 5) Decode full tokens → text
    transcription_text = processor.batch_decode(
        generated_ids, skip_special_tokens=True
    )[0].strip()

    # 6) (Optional) split the full_text into timestamped segments
    #    The HF generate call itself does not return a built‐in "segments" list with timestamps.
    #    If you absolutely need word timestamps, you would fall back to whisperx.align on
    #    audio + transcripts. For now, we’ll build rough segment‐level timestamps by re-running
    #    model.transcribe(...) with output “segments”. That call DOES chunk internally.
    #
    #    We only need segment‐level offsets for diarization alignment; whisperx.align
    #    will “snap” words to times.
    #
    hf_segmentation = whisper_model.transcribe(
        inputs,                # feature‐tensors
        return_dict_in_generate=True,
        output_attentions=False
    )

    segments_list = []
    if "segments" in hf_segmentation:
        # Each HF segment has: {"id", "seek", "start", "end", "text"}
        for seg in hf_segmentation["segments"]:
            segments_list.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip()
            })

    transcription_full = {
        "text": transcription_text,
        "segments": segments_list,
        "language": language
    }

    return transcription_full, language


def diarize_and_assign_speakers(transcription_full: dict, wav_path: str, device="cuda", hf_token=None):
    """
    1) Run a diarization pipeline (pyannote) on the entire WAV.
    2) whisperx.assign_word_speakers(...) expects “aligned” (word‐timestamp) output,
       but here transcription_full only has segment‐level offsets.
       So first we ALIGN word‐timing via whisperx.align, then assign speakers.
    """
    # 1) Perform speaker‐diarization on the raw WAV
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(wav_path)  # returns list of {start, end, speaker}

    # 2) Align words to audio times via whisperx.align (word‐level)
    align_model, metadata = whisperx.load_align_model(
        language_code=transcription_full["language"], device=device
    )

    word_aligned = whisperx.align(
        transcription_full["segments"],  # needs segment‐level timestamps
        align_model,
        metadata,
        wav_path,
        device=device,
        return_char_alignments=False
    )

    # 3) Assign each aligned word a speaker label
    speaker_aligned = whisperx.assign_word_speakers(
        diarize_segments,
        word_aligned
    )

    return speaker_aligned


def group_words_into_segments(words, max_gap=1.0):
    """
    Given a flat list of word‐dicts [{"word", "start", "end", "speaker"}, ...],
    group them into contiguous segments by speaker and small gaps.
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
            current["end"] = w["end"]
            current["text"] += " " + w["word"]

    segments.append(current)
    return segments


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
        logger.exception(f"Error parsing S3 audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    # 1) Process the audio → transcription + diarization + DB update
    try:
        process_audio(job_id, bucket, key)
    except Exception:
        logger.exception(f"Failed to process audio and diarization for job_ID: {job_id}")
        return

    # 2) Notify Flask that analysis is complete
    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")


if __name__ == "__main__":
    run_diarization()
