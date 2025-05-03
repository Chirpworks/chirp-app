# Use GPU-compatible base image with cuDNN
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsndfile1 \
    python3.10 \
    python3-pip \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Make python3.10 the default
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install GPU-compatible PyTorch and related packages
RUN pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0 --extra-index-url https://download.pytorch.org/whl/cu118

# Install WhisperX from GitHub
RUN pip install git+https://github.com/m-bain/whisperx.git

# Install compatible version of PyAnnote
RUN pip install pyannote.audio==3.0.1

# Optional: install other Python packages you use
COPY requirements_speaker_diarization.txt .
RUN pip install -r requirements_speaker_diarization.txt

# Optional: install other Python packages you use
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the full app source code
WORKDIR /app
COPY . .

# Set default entrypoint for RunPod serverless execution
ENTRYPOINT ["python", "app/serverless_handler.py"]
