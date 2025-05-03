FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg libsndfile1 python3.10 python3-pip build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN python -m pip install --upgrade pip

RUN pip install torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0 --extra-index-url https://download.pytorch.org/whl/cu118
RUN pip install git+https://github.com/m-bain/whisperx.git
RUN pip install pyannote.audio==3.0.1

COPY requirements_call_analysis.txt .
RUN pip install -r requirements_call_analysis.txt

WORKDIR /app
COPY . .

ENTRYPOINT ["python", "app/serverless_handler.py"]