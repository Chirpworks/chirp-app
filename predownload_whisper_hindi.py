# predownload_whisper.py

from faster_whisper import WhisperModel

# Even though we ultimately want to run on GPU at runtime, the Docker build itself
# has no GPU-visible driver. So we convert the HF weights on CPU here.
WhisperModel(
    "vasista22/whisper-hindi-large-v2",
    device="cpu",           # ← use CPU for conversion at build time
    compute_type="float32"  # or "int8" if you want an 8-bit conversion
)