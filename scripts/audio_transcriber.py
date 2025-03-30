import os
import whisper


def run_transcription():
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    print(os.environ)
    os.environ['PATH'] += f':{os.path.dirname(ffmpeg_path)}'

    model = whisper.load_model("medium")
    result = model.transcribe("Road Number 62.m4a")
    # tokens = 0
    print(result['text'])


if __name__ == '__main__':
    run_transcription()
