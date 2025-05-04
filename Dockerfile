FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

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

# Use python3.10 as default
RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN python -m pip install --upgrade pip

# Install PyTorch (CUDA 11.8 build)
RUN pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0 --extra-index-url https://download.pytorch.org/whl/cu118

# Set working directory
WORKDIR /app

# Set Python path so app/ is importable
ENV PYTHONPATH=/app

# Copy only relevant contents
COPY app/ ./app/

# Optional: install other Python packages you use
COPY requirements_speaker_diarization.txt .
RUN pip install -r requirements_speaker_diarization.txt

# Optional: install other Python packages you use
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN pip uninstall -y onnxruntime
RUN pip install onnxruntime-gpu

# Run your serverless handler
ENTRYPOINT ["python", "app/serverless_handler.py"]
