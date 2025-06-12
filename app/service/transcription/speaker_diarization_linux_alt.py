import json
import os

import logging
import subprocess
import tempfile
import shutil
from datetime import timedelta
from urllib.parse import urlparse

import boto3
import requests
import torch
import whisperx
from whisperx.diarize import DiarizationPipeline, assign_word_speakers
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import Job, Meeting  # Adjust import paths as needed
from app.models.job import JobStatus

from app.service.llm.open_ai.chat_gpt import OpenAIClient
import whisper

# ─── GLOBAL CONFIGURATION ──────────────────────────────────────────────────────

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
FLASK_API_URL = os.getenv("FLASK_API_URL")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")  # Hugging Face token for PyAnnote
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(handler)

# Load WhisperX ASR model once at startup
logger.info("Loading WhisperX ASR model...")
whisper_model = whisper.load_model("large-v2", device=DEVICE)
whisper_model.to(dtype=torch.float32)

# Database setup (SQLAlchemy)
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. "postgresql://user:pass@host:port/dbname"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# S3 client
s3_client = boto3.client("s3")

# Initialize SQLAlchemy session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    """
    Format a float-second timestamp as "HH:MM:SS".
    """
    return str(timedelta(seconds=round(seconds)))


def notify_flask_server(job_id: str):
    """
    Send a POST to the Flask backend to trigger downstream analysis.
    """
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    try:
        response = requests.post(url, json={"job_id": job_id})
        response.raise_for_status()
        logger.info(f"Notified Flask server for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify Flask server for job_id={job_id}: {e}")


def update_job_status(job_id: str, status):
    """
    Update the Job.status in the database.
    """
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = status
            session.commit()
            logger.info(f"Updated Job {job_id} status to {status}")
        session.close()
    except Exception as e:
        logger.exception(f"Error updating job status for {job_id}: {e}")


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Use ffmpeg to convert an MP3 file to WAV (16kHz mono) for WhisperX.
    Returns the new WAV file path.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    # 1) FFT-based noise reduction at –25 dB
    # 2) EBU-R128 loudness normalize
    # 3) resample to 16 kHz mono for WhisperX
    command = [
        "ffmpeg", "-y", "-i", mp3_path,
        "-af", "afftdn=nf=-25,loudnorm",
        "-ar", "16000", "-ac", "1",
        wav_path,
    ]
    subprocess.run(command, check=True)
    return wav_path


def get_audio_url(job_id):
    """
    Queries the database to get the S3 URL for the audio file for the given job_id.
    """
    job = session.query(Job).filter_by(id=job_id).first()
    if job and job.s3_audio_url:
        return job.s3_audio_url
    else:
        raise ValueError(f"No audio URL found for job_id {job_id}")


def split_audio(
    wav_path: str, chunk_duration: int = 30
) -> list[tuple[str, float]]:
    """
    Splits `wav_path` into multiple WAV chunks of length `chunk_duration` seconds,
    using ffmpeg. Returns a list of tuples: (chunk_path, start_offset_seconds).

    - Each chunk is re‐encoded to 16kHz mono to ensure WhisperX compatibility.
    - Filenames follow: <tempdir>/chunk_<index>.wav, where index starts at 0.
    """
    tmp_dir = tempfile.mkdtemp(prefix="audio_chunks_")
    # e.g., /tmp/audio_chunks_abcd1234
    # Use ffmpeg's segment muxer to split by time
    chunk_pattern = os.path.join(tmp_dir, "chunk_%04d.wav")

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        wav_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_duration),
        "-reset_timestamps",
        "1",
        chunk_pattern,
    ]
    logger.info(f"Splitting audio into {chunk_duration}s chunks: {' '.join(ffmpeg_cmd)}")
    subprocess.run(ffmpeg_cmd, check=True)

    # After splitting, collect all chunk files
    chunk_files = sorted(
        f for f in os.listdir(tmp_dir) if f.startswith("chunk_") and f.endswith(".wav")
    )
    result = []
    for filename in chunk_files:
        # Parse index from filename "chunk_0000.wav" → index 0
        index_str = filename.replace("chunk_", "").replace(".wav", "")
        index = int(index_str)
        offset = index * chunk_duration
        result.append((os.path.join(tmp_dir, filename), float(offset)))

    return result  # e.g. [("/tmp/.../chunk_0000.wav", 0.0), ("/tmp/.../chunk_0001.wav", 60.0), ...]


INITIAL_PROMPT = "You are transcribing a bilingual (Hindi and English) sales call between a company representative "\
                 "and a customer. The conversation covers product introductions, feature explanations, pricing "\
                 "discussions, negotiation, and objection handling. Accurately capture Hindi and English speech, "\
                 "preserving product names, proper nouns, and technical terms."


def transcribe_in_chunks(
    wav_path: str, chunk_duration: int = 60
) -> dict:
    """
    1. Split `wav_path` into fixed‐length chunks (via split_audio).
    2. For each chunk, run WhisperX transcription + forced alignment.
    3. Shift each segment's timestamps by the chunk's start offset.
    4. Concatenate all segments into a single `combined_result`.
    Returns:
      { "language": <first_chunk_lang>, "segments": [ <all shifted segments> ] }
    """
    logger.info("Splitting input audio for chunked transcription")
    chunks = split_audio(wav_path, chunk_duration=chunk_duration)
    all_segments = []

    try:
        for (chunk_path, offset) in chunks:
            logger.info(f"Transcribing chunk at offset {offset}s: {chunk_path}")
            # WhisperX auto‐detects language if not given
            transcription = whisper_model.transcribe(
                chunk_path,
                language='en',
                beam_size=5,  # explore top 5 beams
                best_of=5,  # pick the best result out of 5 candidates
                temperature=0.0,  # deterministic output
                initial_prompt=INITIAL_PROMPT
            )
            # Strip prompt from output if emitted
            raw_text = transcription.get("text", "")
            prompt_txt = INITIAL_PROMPT.strip()
            cleaned = raw_text.lstrip()

            if cleaned.lower().startswith(prompt_txt.lower()):
                cleaned = cleaned[len(prompt_txt):].lstrip(" \n\t:;,-")
            transcription = {
                "segments": transcription.get("segments", []),
                "text": cleaned,
                "language": transcription.get("language", "en")
            }

            logger.info(transcription)
            lang = transcription.get("language", "en")
            logger.info(f"Detected language for chunk: {lang}")

            # Forced alignment for this chunk
            model_a, metadata = whisperx.load_align_model(
                language_code=lang, device=DEVICE
            )
            aligned = whisperx.align(
                transcription["segments"], model_a, metadata, chunk_path, DEVICE
            )
            # aligned["segments"] is a list of segment dicts with "start", "end", "words" etc.

            # Shift timestamps by offset
            for seg in aligned["segments"]:
                seg["start"] += offset
                seg["end"] += offset
                if "words" in seg:
                    for word in seg["words"]:
                        if "start" in word and "end" in word:
                            word["start"] += offset
                            word["end"] += offset
                # Collect into our combined list
                all_segments.append(seg)

            # Clean up this chunk file
            try:
                os.remove(chunk_path)
            except Exception:
                pass

        # Sort combined segments by start time
        all_segments.sort(key=lambda s: s["start"])

        combined_result = {
            "language": "en",
            "segments": all_segments,
        }
        return combined_result

    finally:
        # Clean up the chunk directory
        chunk_dir = os.path.dirname(chunks[0][0]) if chunks else None
        if chunk_dir and os.path.isdir(chunk_dir):
            shutil.rmtree(chunk_dir, ignore_errors=True)


def transcribe_and_diarize(audio_path: str):
    """
    New pipeline:
      1. Transcribe entire audio in chunks -> combined_aligned.
      2. Run WhisperX's DiarizationPipeline on the full audio -> diarize_df.
      3. Merge combined_aligned with diarize_df -> aligned_with_speakers.
    Returns:
      - aligned_with_speakers (dict: segments with per-word "speaker")
      - diarize_df (DataFrame of pure diarization segments)
    """
    # ─── (1) Chunked transcription ──────────────────────────
    combined_aligned = transcribe_in_chunks(audio_path, chunk_duration=30)

    # ─── (2) Pure diarization on full audio ──────────────────
    logger.info("Running DiarizationPipeline on full audio for speaker segmentation")
    diarizer = DiarizationPipeline(
        model_name="pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN,
        device=DEVICE,
    )
    diarize_segments = diarizer(audio_path, num_speakers=2)

    # ─── (3) Merge transcription with speaker labels ─────────
    logger.info("Assigning speaker labels to each word in combined transcript")
    aligned_with_speakers = assign_word_speakers(
        diarize_segments, combined_aligned, fill_nearest=False
    )

    # for seg in aligned_with_speakers["segments"]:
    #     for w in seg.get("words", []):
    #         orig = w["word"]  # e.g. "विपक्ष"
    #         # Transliterate from Devanagari to plain ASCII IAST:
    #         w["word"] = transliterate(orig, DEVANAGARI, IAST)

    # Now aligned_with_speakers["segments"] has each segment dict plus "speaker",
    # and each word in aligned_with_speakers["segments"][i]["words"] also has "speaker".
    logger.info("Finished DiarizationPipeline")
    logger.info(f"aligned_with_speakers: {aligned_with_speakers}")
    return aligned_with_speakers, diarize_segments


def group_words_by_speaker(aligned_result: dict) -> list[dict]:
    merged = []
    for segment in aligned_result.get("segments", []):
        words = segment.get("words", [])
        for w in words:
            speaker = w.get("speaker", None)
            if speaker is None:
                continue
            word_text = w.get("word", "").strip()
            word_start = w.get("start", 0.0)
            word_end = w.get("end", 0.0)

            if not merged:
                merged.append({
                    "speaker": speaker,
                    "start": word_start,
                    "end": word_end,
                    "text": word_text
                })
            else:
                last_block = merged[-1]
                if speaker == last_block["speaker"]:
                    last_block["end"] = word_end
                    last_block["text"] += " " + word_text
                else:
                    merged.append({
                        "speaker": speaker,
                        "start": word_start,
                        "end": word_end,
                        "text": word_text
                    })
    return merged


def process_audio(job_id: str, bucket: str, key: str):
    """
    Main processing flow for a given job_id:
      1. Download MP3 from S3
      2. Convert to WAV
      3. Run chunked transcription + full-audio diarization
      4. Store results back in the DB
      5. Update job status
    """
    update_job_status(job_id, JobStatus.IN_PROGRESS)

    try:
        # 1. Download from S3
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            local_wav = tmp_file.name
        mp3_temp = local_wav.replace(".wav", ".mp3")

        logger.info(f"Downloading audio from s3://{bucket}/{key} to {mp3_temp}")
        s3_client.download_file(bucket, key, mp3_temp)

        # 2. Convert to WAV
        local_wav = convert_mp3_to_wav(mp3_temp)

        # 3 & 4. Transcribe in chunks + Diarize
        aligned_with_speakers, diarize_df = transcribe_and_diarize(local_wav)

        # 5. Update Meeting record in DB
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            # Store the full aligned transcript (with speaker tags) as JSON
            # (A) Store the full, word-level aligned output if needed:
            meeting.transcript = json.dumps(aligned_with_speakers, ensure_ascii=False)

            # (B) Build merged “speaker blocks” for diarization:
            blocks = group_words_by_speaker(aligned_with_speakers)

            # (C) Save those blocks as your diarization JSON:
            openai_client = OpenAIClient()
            diarization = openai_client.polish_with_gpt(blocks)
            meeting.diarization = diarization

            session.commit()
            logger.info(f"Updated Meeting {meeting.id} with transcript & diarization.")
            update_job_status(job_id, JobStatus.COMPLETED)
        else:
            logger.error(f"Meeting record not found for job_id={job_id}")
            update_job_status(job_id, JobStatus.FAILURE)

    except Exception as e:
        logger.exception(f"Error processing audio for job_id={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)


# ─── MAIN ENTRYPOINT ──────────────────────────────────────────────────────────

def run_diarization(job_id):
    job_id = os.getenv("JOB_ID") or job_id
    if not job_id:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        parsed = urlparse(s3_url)
        bucket, key = parsed.netloc, parsed.path.lstrip("/")
        process_audio(job_id, bucket, key)
    except Exception as e:
        logger.exception(f"Error in run_diarization for job_id={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    # Notify Flask server to trigger downstream analysis
    try:
        notify_flask_server(job_id)
    except Exception:
        pass


if __name__ == "__main__":
    run_diarization()
