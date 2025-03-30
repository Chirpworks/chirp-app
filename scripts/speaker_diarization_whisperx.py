import os
import time

import whisperx
import torch
import gc


def transcribe_and_diarize(audio_path, compute_type="float32"):
    """
    Transcribe audio and perform speaker diarization using WhisperX

    Parameters:
    audio_path (str): Path to audio file
    compute_type (str): Computing precision type ("float16" or "float32")

    Returns:
    dict: Diarized transcription results
    """
    try:
        # 1. Load the ASR model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        asr_model = whisperx.load_model("large-v1", device, compute_type=compute_type)

        # 2. Transcribe audio
        audio = whisperx.load_audio(audio_path)
        result = asr_model.transcribe(audio, batch_size=16, language='en')
        print("Transcription completed")
        print(result)

        # 3. Load alignment model and align whisper output
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
        print("Alignment completed")

        # 4. Clean up memory
        del model_a
        gc.collect()
        torch.cuda.empty_cache()

        # 5. Perform diarization
        diarize_model = whisperx.DiarizationPipeline(use_auth_token='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', device=device)
        diarize_segments = diarize_model(audio)
        print("Diarization completed")

        # 6. Assign speaker labels to the segments
        result = whisperx.assign_word_speakers(diarize_segments, result)

        return format_results(result)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


def format_results(result):
    """
    Format the WhisperX results into a more readable structure

    Parameters:
    result (dict): Raw WhisperX results

    Returns:
    dict: Formatted results with speaker segments and timestamps
    """
    formatted_output = {
        'segments': [],
        'speakers': {}
    }

    for segment in result["segments"]:
        # Format segment information
        formatted_segment = {
            'start': round(segment['start'], 2),
            'end': round(segment['end'], 2),
            'speaker': segment.get('speaker', 'UNKNOWN'),
            'text': segment['text'],
            'words': [{
                'word': word['word'],
                'start': round(word['start'], 2),
                'end': round(word['end'], 2),
                'speaker': word.get('speaker', 'UNKNOWN')
            } for word in segment.get('words', [])]
        }

        formatted_output['segments'].append(formatted_segment)

        # Collect speaker statistics
        speaker = formatted_segment['speaker']
        if speaker not in formatted_output['speakers']:
            formatted_output['speakers'][speaker] = {
                'total_time': 0,
                'word_count': 0,
                'segments': []
            }

        duration = formatted_segment['end'] - formatted_segment['start']
        formatted_output['speakers'][speaker]['total_time'] += duration
        formatted_output['speakers'][speaker]['word_count'] += len(formatted_segment['words'])
        formatted_output['speakers'][speaker]['segments'].append(formatted_segment)

    return formatted_output


def print_results(results):
    """
    Print the formatted results in a readable manner

    Parameters:
    results (dict): Formatted results from format_results
    """
    if not results:
        print("No results to display")
        return

    print("\nTranscription Results:")
    print("=" * 50)

    # Print speaker statistics
    print("\nSpeaker Statistics:")
    print("-" * 30)
    for speaker, stats in results['speakers'].items():
        print(f"\nSpeaker: {speaker}")
        print(f"Total speaking time: {round(stats['total_time'], 2)} seconds")
        print(f"Total words: {stats['word_count']}")

    # Print detailed segments
    print("\nDetailed Transcript:")
    print("-" * 30)
    for segment in results['segments']:
        print(f"\n[{segment['start']}s -> {segment['end']}s] {segment['speaker']}:")
        print(f"Text: {segment['text']}")


# Example usage
if __name__ == "__main__":
    AUDIO_PATH = "wav_sample.wav"

    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    print(os.environ)
    os.environ['PATH'] += f':{os.path.dirname(ffmpeg_path)}'

    # Install required packages if not already installed:
    # pip install git+https://github.com/m-bain/whisperx.git
    # pip install pyannote.audio
    start_time = time.time()

    results = transcribe_and_diarize(AUDIO_PATH)
    print_results(results)

    end_time = time.time()

    print(f"total_time_taken = {end_time-start_time}")
