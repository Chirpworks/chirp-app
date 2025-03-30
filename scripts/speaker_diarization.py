import os
import time

import torch
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook
import wave
import contextlib
from pydub import AudioSegment


def convert_to_wav(input_file, output_file):
    """
    Converts an audio file to .wav format.

    Args:
        input_file (str): Path to the input audio file.
        output_file (str): Path to save the converted .wav file.
    """
    try:
        # Load the audio file
        audio = AudioSegment.from_file(input_file)

        # Export as .wav
        audio.export(output_file, format="wav")
        print(f"File converted successfully to {output_file}")
    except Exception as e:
        print(f"Error: {e}")


def get_audio_duration(audio_path):
    """Get duration of audio file in seconds."""
    with contextlib.closing(wave.open(audio_path, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
        return duration


def perform_diarization(audio_path, auth_token):
    """
    Perform speaker diarization on an audio file.

    Parameters:
    audio_path (str): Path to the audio file
    auth_token (str): HuggingFace authentication token

    Returns:
    dict: Dictionary containing speaker segments
    """
    try:
        # Initialize the pipeline
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token=auth_token
        )

        # If you have GPU, use it
        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))

        # Get audio duration
        duration = get_audio_duration(audio_path)
        torch.backends.cudnn.benchmark = True

        # Process the audio file
        diarization = pipeline(
            audio_path,
            min_speakers=1,
            max_speakers=2
        )

        # Process and format results
        speaker_segments = {}
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []

            segment = {
                'start': round(turn.start, 2),
                'end': round(turn.end, 2),
                'duration': round(turn.end - turn.start, 2)
            }
            speaker_segments[speaker].append(segment)

        # Add summary statistics
        for speaker in speaker_segments:
            total_duration = sum(seg['duration'] for seg in speaker_segments[speaker])
            percentage = (total_duration / duration) * 100
            speaker_segments[speaker] = {
                'segments': speaker_segments[speaker],
                'total_speaking_time': round(total_duration, 2),
                'speaking_percentage': round(percentage, 2)
            }

        return speaker_segments

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


def print_diarization_results(results):
    """Pretty print the diarization results."""
    if not results:
        print("No results to display")
        return

    print("\nDiarization Results:")
    print("=" * 50)

    for speaker, data in results.items():
        print(f"\n{speaker}:")
        print(f"Total speaking time: {data['total_speaking_time']} seconds")
        print(f"Speaking percentage: {data['speaking_percentage']}%")
        print("\nSegments:")
        for segment in data['segments']:
            print(f"  {segment['start']}s -> {segment['end']}s (duration: {segment['duration']}s)")
        print("-" * 30)


# Example usage
if __name__ == "__main__":
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    print(os.environ)
    os.environ['PATH'] += f':{os.path.dirname(ffmpeg_path)}'

    # You'll need to get this token from HuggingFace
    start_time = time.time()
    AUTH_TOKEN = "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"
    input_file = "Road Number 62.m4a"
    output_file = "wav_sample.wav"
    convert_to_wav(input_file, output_file)

    results = perform_diarization(output_file, AUTH_TOKEN)
    print_diarization_results(results)

    end_time = time.time()
    total_time = end_time - start_time
    print(total_time)
