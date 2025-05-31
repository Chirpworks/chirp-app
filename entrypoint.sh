#!/usr/bin/env bash
set -euo pipefail

#
# Step A: “Pre‐download+pre‐convert” the vasista22/whisper‐hindi‐large‐v2 model
#         *only if* it is not already on disk.  We FORCE CTranslate2→GPU here.
#

# If CTranslate2 has not yet generated a `model.bin` for this snapshot, do it now.
# Faster‐Whisper will:
#   1) download the HF PyTorch weights into $HF_HOME/hub/models--vasista22--whisper-hindi-large-v2/…
#   2) run CTranslate2’s GPU converter and write `model.bin` into that same snapshot folder.
if ! ls "$HF_HOME/hub/models--vasista22--whisper-hindi-large-v2"/snapshots/*/model.bin >/dev/null 2>&1; then
    python3 - << 'EOF'
from faster_whisper import WhisperModel

# Instantiating WhisperModel(...) at runtime will:
#   • download the HF weights into $HF_HOME/hub/models--vasista22--whisper-hindi-large-v2/…
#   • convert them to CTranslate2 format on GPU (writing model.bin)
WhisperModel(
    "vasista22/whisper-hindi-large-v2",
    device="cuda",
    compute_type="float32"
)
EOF
fi

#
# Step B: Once “model.bin” exists, we can start our serverless handler normally.
#
exec python3 app/serverless_handler.py