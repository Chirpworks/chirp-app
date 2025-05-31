# ✅ Use CUDA image with cuDNN runtime
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Prevent interactive prompts & enable unbuffered Python output
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 🧰 Install system dependencies (including Aeneas & eSpeak-NG prerequisites)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    python3.10 \
    python3.10-dev \
    python3-pip \
    default-jdk \
    libxml2-dev \
    gfortran \
    cmake \
    espeak \
    libespeak-dev \
    pkg-config \
    build-essential \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# 🔗 Make python3.10 & pip3 the defaults
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# ⬆️ Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools wheel

# ⚙️ Install GPU-compatible PyTorch (CUDA 11.8)
RUN pip install \
    torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# 🧠 Install WhisperX
RUN pip install git+https://github.com/m-bain/whisperx.git

# 🎙️ Install PyAnnote for diarization
RUN pip install pyannote.audio==3.0.1

# 🎓 Install Aeneas for forced alignment
RUN pip install aeneas

# 📦 Copy your application code
WORKDIR /app
COPY app/ ./app/

# 📦 Make your app/ importable
ENV PYTHONPATH=/app

# 📜 Install any additional Python dependencies
COPY requirements_speaker_diarization.txt .
RUN pip install -r requirements_speaker_diarization.txt

COPY requirements.txt .
RUN pip install -r requirements.txt

# 🚀 Default entrypoint for serverless runner
ENTRYPOINT ["python", "app/serverless_handler.py"]