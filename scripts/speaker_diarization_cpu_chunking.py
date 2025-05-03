import os
import re
import json
import torch
import torchaudio
import whisperx
import tempfile
import subprocess
import numpy as np
from pyannote.audio import Pipeline as DiarizationPipeline
from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding
from pyannote.audio.pipelines.utils.hook import ProgressHook
from sklearn.metrics.pairwise import cosine_similarity

# Constants
TARGET_CHUNK_LENGTH = 60  # seconds
SILENCE_THRESHOLD = "-20dB"
SILENCE_DURATION = "0.5"
HF_TOKEN = "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"
DEVICE = "cpu"

# Silence detection using ffmpeg
def detect_silences(audio_path):
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={SILENCE_THRESHOLD}:d={SILENCE_DURATION}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    output = result.stderr
    return [float(m.group(1)) for m in re.finditer(r"silence_end: (\d+\.\d+)", output)]

# Choose split points based on silence
def choose_split_points(duration, silence_ends):
    split_points = [0.0]
    next_target = TARGET_CHUNK_LENGTH
    for t in silence_ends:
        if t >= next_target:
            split_points.append(t)
            next_target = t + TARGET_CHUNK_LENGTH
    if split_points[-1] < duration:
        split_points.append(duration)
    return split_points

# Split audio into chunk files using ffmpeg
def split_audio_by_silence(audio_path):
    result = subprocess.run([
        "ffprobe", "-i", audio_path, "-show_entries", "format=duration",
        "-v", "quiet", "-of", "csv=p=0"
    ], stdout=subprocess.PIPE, text=True)
    duration = float(result.stdout.strip())

    silence_ends = detect_silences(audio_path)
    split_points = choose_split_points(duration, silence_ends)

    chunks = []
    for i in range(len(split_points) - 1):
        start = split_points[i]
        end = split_points[i + 1]
        chunk_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start), "-to", str(end),
            "-c", "copy", chunk_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chunks.append((chunk_path, start))
    print(chunks)
    return chunks

# Process each chunk (reusing loaded models)
def process_chunk(chunk_path, offset, whisper_model, diarization_pipeline, embedding_model):
    print("Transcribing")
    result = whisper_model.transcribe(chunk_path)
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=DEVICE)
    result = whisperx.align(result["segments"], model_a, metadata, chunk_path, DEVICE)
    print(result)

    # ✅ Load parameters from pretrained model
    hyperparameters = {
        "segmentation": {
            "threshold": 0.7,  # 🔥 Improves speaker separation
            "min_duration_off": 0.5  # 🔥 Prevents rapid speaker switching
        },
        "clustering": {
            "threshold": 0.5,  # 🔥 Tighter speaker grouping
            "method": "ward",  # 🔥 Better clustering approach
            "min_cluster_size": 15  # 🔥 Avoids small noise clusters
        }
    }

    # ✅ APPLY PARAMETER CHANGES (FIXES ERROR)
    diarization_pipeline.instantiate(hyperparameters)  # 🔥 Minimum samples for a cluster

    with ProgressHook() as hook:
        diarization = diarization_pipeline.apply({"uri": "audio", "audio": chunk_path}, num_speakers=2, hook=hook)

    segments = []
    speaker_embeddings = {}

    for turn, _, speaker in diarization.itertracks(yield_label=True):
        chunk_segments = []
        for seg in result["segments"]:
            if seg["start"] >= turn.start and seg["end"] <= turn.end:
                chunk_segments.append(seg["text"])

        if chunk_segments:
            waveform, sample_rate = torchaudio.load(chunk_path)
            start_sample = int(turn.start * sample_rate)
            end_sample = int(turn.end * sample_rate)
            segment_waveform = waveform[:, start_sample:end_sample]
            if segment_waveform.numel() == 0:
                return [], {}  # Skip empty segments

            embedding = embedding_model(segment_waveform.unsqueeze(0))
            speaker_embeddings.setdefault(speaker, []).append(embedding)
            segments.append({
                "start": turn.start + offset,
                "end": turn.end + offset,
                "speaker": speaker,
                "text": " ".join(chunk_segments)
            })

    os.remove(chunk_path)

    averaged_embeddings = {
        spk: torch.mean(torch.stack([torch.from_numpy(e) for e in embs]), dim=0).numpy()
        for spk, embs in speaker_embeddings.items()
    }

    print(segments)
    return segments, averaged_embeddings


# Unify speaker labels across chunks
def unify_speakers(all_segments_with_embeddings):
    global_segments = []
    speaker_registry = {}
    global_speaker_id = 0

    for segments, spk_embs in all_segments_with_embeddings:
        local_to_global = {}
        for local_spk, local_emb in spk_embs.items():
            best_match = None
            best_sim = 0.8  # threshold

            for global_spk, global_emb in speaker_registry.items():
                sim = cosine_similarity(
                    local_emb.reshape(1, -1), global_emb.reshape(1, -1)
                )[0][0]
                if sim > best_sim:
                    best_match = global_spk
                    best_sim = sim

            if best_match:
                local_to_global[local_spk] = best_match
            else:
                speaker_registry[f"SPEAKER_{global_speaker_id}"] = local_emb
                local_to_global[local_spk] = f"SPEAKER_{global_speaker_id}"
                global_speaker_id += 1

        for seg in segments:
            seg["speaker"] = local_to_global.get(seg["speaker"], seg["speaker"])
            global_segments.append(seg)

    return sorted(global_segments, key=lambda x: x["start"])


# Save final result
def save_output(segments, out_path="diarized_output.json"):
    with open(out_path, "w") as f:
        json.dump(segments, f, indent=2)
    print(f"✅ Saved diarized output to {out_path}")


# Main pipeline
def run_diarization_pipeline(audio_file):
    print("🔍 Chunking audio by silence...")
    chunks = split_audio_by_silence(audio_file)

    print("📦 Loading models once...")
    whisper_model = whisperx.load_model("medium", DEVICE, compute_type="float32")
    diarization_pipeline = DiarizationPipeline.from_pretrained(
        "pyannote/speaker-diarization@2.1", use_auth_token=HF_TOKEN
    )
    # from pyannote.audio import Inference

    embedding_model = PretrainedSpeakerEmbedding(
        "speechbrain/spkrec-ecapa-voxceleb", device="cpu"
    )

    all_outputs = []
    for chunk_path, offset in chunks:
        print(f"🎙️  Processing chunk at offset {offset:.2f}s...")
        segs, spk_embs = process_chunk(
            chunk_path, offset, whisper_model, diarization_pipeline, embedding_model
        )
        all_outputs.append((segs, spk_embs))

    print("🔁 Unifying speaker labels across chunks...")
    final_segments = unify_speakers(all_outputs)

    save_output(final_segments)


# CLI
if __name__ == "__main__":
    # import argparse
    # parser = argparse.ArgumentParser()
    # parser.add_argument("audio_file", help="Path to input audio file (.wav)")
    # args = parser.parse_args()
    audio_file_path = 'myoperator_sales_call.wav'
    run_diarization_pipeline(audio_file_path)
