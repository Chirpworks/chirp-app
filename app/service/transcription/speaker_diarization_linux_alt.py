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
# from whisperx.diarize import DiarizationPipeline, assign_word_speakers
from pyannote.audio.pipelines.utils.hook import ProgressHook

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import Job, Meeting  # Adjust import paths as needed
from app.models.job import JobStatus

from app.service.llm.open_ai.chat_gpt import OpenAIClient
from pyannote.audio import Pipeline


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
whisperx_model = whisperx.load_model("large-v2", device=DEVICE)

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
    command = [
        "ffmpeg",
        "-y",
        "-i",
        mp3_path,
        "-ar",
        "16000",  # WhisperX expects 16 kHz
        "-ac",
        "1",      # mono audio
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
    first_lang = None

    try:
        for (chunk_path, offset) in chunks:
            logger.info(f"Transcribing chunk at offset {offset}s: {chunk_path}")
            # WhisperX auto‐detects language if not given
            transcription = whisperx_model.transcribe(chunk_path)
            logger.info(transcription)
            lang = transcription.get("language", "en")
            if first_lang is None:
                first_lang = lang
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
        transcript_text, cleaned_diarization_segments = process_audio_pipeline(local_wav)
        logger.info(f"Transcript: {transcript_text}")
        logger.info(f"Cleaned diarization segments: {cleaned_diarization_segments}")

        # 5. Update Meeting record in DB
        job = session.query(Job).filter_by(id=job_id).first()
        meeting = None
        if job:
            meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
        if meeting:
            # Store the full aligned transcript (with speaker tags) as JSON
            # (A) Store the full, word-level aligned output if needed:
            meeting.transcript = json.dumps(transcript_text, ensure_ascii=False)
            meeting.diarization = json.dumps(cleaned_diarization_segments)

            session.commit()
            logger.info(f"Updated Meeting {meeting.id} with transcript & diarization.")
            update_job_status(job_id, JobStatus.COMPLETED)
        else:
            logger.error(f"Meeting record not found for job_id={job_id}")
            update_job_status(job_id, JobStatus.FAILURE)

    except Exception as e:
        logger.exception(f"Error processing audio for job_id={job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)

# ----------------- Diarization -----------------

def diarize_audio(audio_path: str, transcript_results) -> list:
    """
    Runs speaker diarization and returns list of dicts: start, end, speaker.
    """
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.0",
        use_auth_token="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"
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
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

    # Step 4: Match word segments to diarization labels
    logger.info("Aligning words with speaker segments...")
    speaker_segments = list(diarization.itertracks(yield_label=True))
    words = transcript_results.get("word_segments", [])

    if not words:
        logger.info("No word-level segments found in WhisperX output. Cannot align with diarization.")
        return []

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

    return combined_output

# ----------------- Diarization Refinement -----------------

def reduce_diarization_loss(diarization: list, min_duration: float = 0.5) -> list:
    """
    Merge segments shorter than min_duration into neighbors and merge adjacent same-speaker.
    """
    diarization = sorted(diarization, key=lambda x: x['start'])
    merged = []
    for seg in diarization:
        duration = seg['end'] - seg['start']
        if duration < min_duration and merged:
            merged[-1]['end'] = seg['end']
        else:
            merged.append(seg.copy())
    cleaned = []
    for seg in merged:
        if cleaned and cleaned[-1]['speaker'] == seg['speaker'] and abs(seg['start'] - cleaned[-1]['end']) < 0.2:
            cleaned[-1]['end'] = seg['end']
        else:
            cleaned.append(seg.copy())
    return cleaned

# ----------------- Speaker Assignment -----------------

def assign_speakers(segments: list, diarization: list) -> list:
    """
    Assign speaker labels to transcription segments by maximum overlap.
    """
    assigned = []
    for seg in segments:
        best, max_ov = None, 0.0
        for turn in diarization:
            ov = max(0, min(seg['end'], turn['end']) - max(seg['start'], turn['start']))
            if ov > max_ov:
                max_ov, best = ov, turn['speaker']
        assigned.append({**seg, 'speaker': best or 'Unknown'})
    return assigned


# ----------------- Grouping Words by Speaker -----------------

def group_words_by_speakers(assigned_segments: list) -> list:
    """
    Groups contiguous segments by speaker into larger utterances.
    Returns list of dicts: start, end, speaker, text.
    """
    grouped = []
    for seg in assigned_segments:
        if grouped and grouped[-1]['speaker'] == seg['speaker']:
            grouped[-1]['end'] = seg['end']
            grouped[-1]['text'] += ' ' + seg['text']
        else:
            grouped.append({
                'start': seg['start'],
                'end': seg['end'],
                'speaker': seg['speaker'],
                'text': seg['text']
            })
    return grouped

# ----------------- GPT-based Cleanup -----------------

def cleanup_with_gpt(assigned_segments: list, model: str = "gpt-4.1-mini") -> list:
    """
    Use GPT-4.1 to clean, translate Hindi->English, fix errors, return coherent JSON.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY for cleanup")
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    payload = json.dumps(assigned_segments, ensure_ascii=False)
    system_msg = "You are an expert assistant cleaning up bilingual sales call transcripts."
    user_prompt = (
        "Translate Hindi to English, approximate the meaning to the best of your ability based on the call context, "
        "preserve context, fix transcription errors, "
        "and output a JSON array of segments with start, end, speaker, text, "
        "keeping the same ordering preserved as the input.")
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_prompt + "\nSegments:\n" + payload}
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0
    )
    return json.loads(resp.choices[0].message.content)

# ----------------- Full Pipeline -----------------

def process_audio_pipeline(audio_path: str):
    """
    1) Convert MP3 to denoised, normalized WAV
    2) Transcribe using your existing WhisperX pipeline
    3) Diarize, refine, assign speakers
    4) Clean up via GPT for translation & coherence
    """

    # 2. Transcription via WhisperX
    result = transcribe_in_chunks(audio_path, chunk_duration=30)
    transcripts = result['segments']

    # Combine raw text from all chunks
    transcript_text = ' '.join([seg['text'].strip() for seg in transcripts])

    # 3. Diarization and smoothing
    raw_dia = diarize_audio(audio_path, transcripts)
    logger.info(f"raw_dia: {raw_dia}")

    smooth_dia = reduce_diarization_loss(raw_dia)
    logger.info(f"smooth_dia: {smooth_dia}")

    # 4. Assign speakers
    assigned = assign_speakers(transcripts, smooth_dia)
    logger.info(f"assigned: {assigned}")

    # 5. Group contiguous by speaker
    grouped = group_words_by_speakers(assigned)
    logger.info(f"grouped_segments: {grouped}")

    # 5. GPT-based cleanup
    final = cleanup_with_gpt(grouped)
    return transcript_text, final

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
