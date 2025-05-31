#!/usr/bin/env bash
set -euo pipefail

# Ensure HF_HOME is defined exactly as in your Dockerfile:
export HF_HOME=/model_cache
export TRANSFORMERS_CACHE=$HF_HOME

#
# 1) “If there is no model.bin yet, do a one‐time GPU conversion now.”
#
if ! ls "$HF_HOME/hub/models--vasista22--whisper-hindi-large-v2"/snapshots/*/model.bin >/dev/null 2>&1; then
    echo ">>> No model.bin found; downloading + converting on GPU..."
    python3 - << 'EOF'
import os
from faster_whisper import WhisperModel

# Set HF_HOME again inside Python (just in case):
os.environ["HF_HOME"] = "/model_cache"

# This call will:
#   1) download the PyTorch weights to HF_HOME/hub/models--vasista22--whisper-hindi-large-v2/…
#   2) run CTranslate2’s GPU converter → writing model.bin
WhisperModel(
    "vasista22/whisper-hindi-large-v2",
    device="cuda",
    compute_type="float32"
)
EOF
    echo ">>> Conversion complete. model.bin is in place."
else
    echo ">>> model.bin already exists. Skipping conversion."
fi

#
# 2) Now that model.bin is guaranteed to exist, start your app:
#
exec python3 app/serverless_handler.py