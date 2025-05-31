# predownload_whisper.py

from faster_whisper import WhisperModel

# Instantiating WhisperModel(...) during build will:
#   1) download the HF weights under /model_cache/hub/models--vasista22--whisper-hindi-large-v2/…
#   2) convert them with CTranslate2, writing model.bin into that same snapshot folder.
# We choose device='cuda' and compute_type='float32' so that the GPU-compatible CTranslate2 conversion runs.
WhisperModel(
    "vasista22/whisper-hindi-large-v2",
    device="cuda",
    compute_type="float32"
)