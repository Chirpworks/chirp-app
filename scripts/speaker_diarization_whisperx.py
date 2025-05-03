# import json
# import os
# import time
# import traceback
#
# import torchaudio
# import whisperx
# import torch
# import gc
# import torchaudio.transforms as T
#
#
# from pyannote.audio.pipelines import SpeakerDiarization
# from pyannote.audio.pipelines.utils.hook import ProgressHook
#
# TARGET_SAMPLE_RATE = 16000
#
# def preprocess_audio(audio_path):
#     """Load, resample, and pad audio to avoid tensor size mismatch errors."""
#     waveform, sample_rate = torchaudio.load(audio_path)
#
#     # ✅ Resample if necessary
#     if sample_rate != TARGET_SAMPLE_RATE:
#         print(f"Resampling audio from {sample_rate} Hz to {TARGET_SAMPLE_RATE} Hz...")
#         resampler = T.Resample(orig_freq=sample_rate, new_freq=TARGET_SAMPLE_RATE)
#         waveform = resampler(waveform)
#
#     # ✅ Ensure all chunks are the same length by padding
#     expected_length = TARGET_SAMPLE_RATE * 3  # 3 seconds per chunk
#     for i in range(len(waveform)):
#         if waveform[i].size(0) < expected_length:
#             padding = expected_length - waveform[i].size(0)
#             waveform[i] = torch.nn.functional.pad(waveform[i], (0, padding))
#
#     torchaudio.save("preprocessed.wav", waveform, sample_rate)
#
# def transcribe_and_diarize(audio_path, compute_type="float32"):
#     """
#     Transcribe audio and perform speaker diarization using WhisperX
#
#     Parameters:
#     audio_path (str): Path to audio file
#     compute_type (str): Computing precision type ("float16" or "float32")
#
#     Returns:
#     dict: Diarized transcription results
#     """
#     try:
#         # ✅ Preprocess audio
#         print("Preprocessing audio...")
#         preprocess_audio(audio_path)
#
#         # 1. Load the ASR model
#         device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#         asr_model = whisperx.load_model("large-v1", "cpu", compute_type=compute_type)
#
#         # 2. Transcribe audio
#         audio = whisperx.load_audio("preprocessed.wav")
#         result = asr_model.transcribe(audio, batch_size=16, language='en')
#         print("Transcription completed")
#         print(result)
#
#         # 3. Load alignment model and align whisper output
#         model_a, metadata = whisperx.load_align_model(language_code=result["language"], device="cpu")
#         result = whisperx.align(result["segments"], model_a, metadata, audio, 'cpu', return_char_alignments=False)
#         print("Alignment completed")
#
#         # 4. Clean up memory
#         del model_a
#         gc.collect()
#         torch.cuda.empty_cache()
#
#         # # 5. Perform diarization
#         # diarize_model = whisperx.DiarizationPipeline(use_auth_token='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', device=device)
#         # diarize_segments = diarize_model(audio)
#         # print("Diarization completed")
#         #
#         # # 6. Assign speaker labels to the segments
#         # result = whisperx.assign_word_speakers(diarize_segments, result)
#         # # print(result)
#
#         # return format_results(result)
#
#         diarization_pipeline = SpeakerDiarization.from_pretrained(
#             "pyannote/speaker-diarization",
#             use_auth_token="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"
#         )
#
#         # ✅ Load parameters from pretrained model
#         hyperparameters = {
#             "segmentation": {
#                 "threshold": 0.7,  # 🔥 Improves speaker separation
#                 "min_duration_off": 0.5  # 🔥 Prevents rapid speaker switching
#             },
#             "clustering": {
#                 "threshold": 0.5,  # 🔥 Tighter speaker grouping
#                 "method": "ward",  # 🔥 Better clustering approach
#                 "min_cluster_size": 15  # 🔥 Avoids small noise clusters
#             }
#         }
#
#         # ✅ APPLY PARAMETER CHANGES (FIXES ERROR)
#         diarization_pipeline.instantiate(hyperparameters)  # 🔥 Minimum samples for a cluster
#
#         # diarization_pipeline = diarization_pipeline.instantiate(params)  # ✅ Correct way to set parameters
#
#         # ✅ Run diarization with precomputed embeddings for faster processing
#         with ProgressHook() as hook:
#             diarization = diarization_pipeline.apply({"uri": "audio", "audio": "preprocessed.wav"}, num_speakers=2, hook=hook)
#
#         # ✅ Print diarization results
#         print("Diarization completed")
#         for turn, _, speaker in diarization.itertracks(yield_label=True):
#             print(f"Speaker {speaker}: {turn.start:.1f}s - {turn.end:.1f}s")
#
#     except Exception as e:
#         print(f"An error occurred: {str(e)}")
#         traceback.print_exc()
#         return None
#
#
# def format_results(result):
#     """
#     Format the WhisperX results into a more readable structure
#
#     Parameters:
#     result (dict): Raw WhisperX results
#
#     Returns:
#     dict: Formatted results with speaker segments and timestamps
#     """
#     formatted_output = {
#         'segments': [],
#         'speakers': {}
#     }
#     for segment in result['segments']:
#         print(segment)
#
#     for segment in result["segments"]:
#         # Format segment information
#         formatted_segment = {
#             'start': round(segment['start'], 2),
#             'end': round(segment['end'], 2),
#             'speaker': segment.get('speaker', 'UNKNOWN'),
#             'text': segment['text'],
#             'words': [{
#                 'word': word['word'],
#                 'speaker': word.get('speaker', 'UNKNOWN')
#             } for word in segment.get('words', [])]
#         }
#
#         formatted_output['segments'].append(formatted_segment)
#
#         # Collect speaker statistics
#         speaker = formatted_segment['speaker']
#         if speaker not in formatted_output['speakers']:
#             formatted_output['speakers'][speaker] = {
#                 'total_time': 0,
#                 'word_count': 0,
#                 'segments': []
#             }
#
#         duration = formatted_segment['end'] - formatted_segment['start']
#         formatted_output['speakers'][speaker]['total_time'] += duration
#         formatted_output['speakers'][speaker]['word_count'] += len(formatted_segment['words'])
#         formatted_output['speakers'][speaker]['segments'].append(formatted_segment)
#
#     return formatted_output
#
#
# def print_results(results):
#     """
#     Print the formatted results in a readable manner
#
#     Parameters:
#     results (dict): Formatted results from format_results
#     """
#     if not results:
#         print("No results to display")
#         return
#
#     print("\nTranscription Results:")
#     print("=" * 50)
#
#     # Print speaker statistics
#     print("\nSpeaker Statistics:")
#     print("-" * 30)
#     for speaker, stats in results['speakers'].items():
#         print(f"\nSpeaker: {speaker}")
#         print(f"Total speaking time: {round(stats['total_time'], 2)} seconds")
#         print(f"Total words: {stats['word_count']}")
#
#     # Print detailed segments
#     print("\nDetailed Transcript:")
#     print("-" * 30)
#     for segment in results['segments']:
#         print(f"\n[{segment['start']}s -> {segment['end']}s] {segment['speaker']}:")
#         print(f"Text: {segment['text']}")
#
#
# # Example usage
# if __name__ == "__main__":
#     AUDIO_PATH = "exotel_recording_1.wav"
#
#     ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
#     print(os.environ)
#     os.environ['PATH'] += f':{os.path.dirname(ffmpeg_path)}'
#
#     # Install required packages if not already installed:
#     # pip install git+https://github.com/m-bain/whisperx.git
#     # pip install pyannote.audio
#     start_time = time.time()
#
#     results = transcribe_and_diarize(AUDIO_PATH)
#     # print(results)
#     # print_results(results)
#
#     end_time = time.time()
#
#     print(f"total_time_taken = {end_time-start_time}")


import os
import torch
import torchaudio
import whisperx
from pyannote.audio import Pipeline
from datetime import timedelta

from pyannote.audio.pipelines.utils.hook import ProgressHook


def preprocess_audio(audio_path):
    print("Preprocessing audio...")
    waveform, sample_rate = torchaudio.load(audio_path)
    if sample_rate != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
        waveform = resampler(waveform)

    # Clip the first `trim_seconds` seconds
    start_sample = int(7 * sample_rate)
    if waveform.size(1) > start_sample:
        waveform = waveform[:, start_sample:]
    else:
        print(f"Warning: audio shorter than 4 seconds. Skipping trim.")

    torchaudio.save("preprocessed.wav", waveform, 16000)
    return "preprocessed.wav"


def format_timestamp(seconds):
    return str(timedelta(seconds=round(seconds)))


def transcribe_and_diarize(audio_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Step 1: Preprocess audio
    # audio_path = preprocess_audio(audio_path)

    # Step 2: Transcription with WhisperX
    print("Running transcription with WhisperX...")
    # asr_model = whisperx.load_model("large-v1", "cpu", compute_type=compute_type)
    #
    #         # 2. Transcribe audio
    #         audio = whisperx.load_audio("preprocessed.wav")
    #         result = asr_model.transcribe(audio, batch_size=16, language='en')
    model = whisperx.load_model("medium", device, compute_type="float32")
    result = model.transcribe(audio_path, language='en')

    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio_path, device)
    print(result)

    # Step 3: Diarization with PyAnnote
    print("Running speaker diarization with PyAnnote...")
    diarization_pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization@2.1",
        use_auth_token="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"
    )

    # ✅ Load parameters from pretrained model
    hyperparameters = {
        "segmentation": {
            "threshold": 0.7,  # 🔥 Improves speaker separation
            "min_duration_off": 0.5  # 🔥 Prevents rapid speaker switching
        },
        "clustering": {
            "threshold": 0.5,  # 🔥 Tighter speaker grouping
            "method": "ward",  # 🔥 Better clustering approach
            "min_cluster_size": 15  # 🔥 Avoids small noise clusters
        }
    }

    # ✅ APPLY PARAMETER CHANGES (FIXES ERROR)
    diarization_pipeline.instantiate(hyperparameters)  # 🔥 Minimum samples for a cluster

    # ✅ Run diarization with precomputed embeddings for faster processing
    with ProgressHook() as hook:
        diarization = diarization_pipeline.apply({"uri": "audio", "audio": "myoperator_sales_call.wav"}, num_speakers=2, hook=hook)

    # diarization = diarization_pipeline(audio_path)

    # Step 4: Match word segments to diarization labels
    print("Aligning words with speaker segments...")
    speaker_segments = list(diarization.itertracks(yield_label=True))
    words = result.get("word_segments", [])

    if not words:
        print("No word-level segments found in WhisperX output. Cannot align with diarization.")
        return

    combined_output = []
    for word_info in words:
        word_start = word_info.get("start")
        word_end = word_info.get("end")
        word_text = word_info.get("word")

        if word_start is None or word_end is None:
            continue

        for turn, _, speaker in speaker_segments:
            if word_start >= turn.start and word_end <= turn.end:
                combined_output.append({
                    "speaker": speaker,
                    "start": word_start,
                    "end": word_end,
                    "text": word_text
                })
                break

    # Group consecutive words by speaker and time window
    print("Final output:")
    final_transcript = []
    if combined_output:
        current_speaker = combined_output[0]["speaker"]
        current_start = combined_output[0]["start"]
        current_words = []

        for i, item in enumerate(combined_output):
            if item["speaker"] != current_speaker or (i > 0 and item["start"] - combined_output[i - 1]["end"] > 1.0):
                final_transcript.append({
                    "speaker": current_speaker,
                    "start": current_start,
                    "end": combined_output[i - 1]["end"],
                    "text": " ".join(current_words)
                })
                current_speaker = item["speaker"]
                current_start = item["start"]
                current_words = []

            current_words.append(item["text"])

        # Add last segment
        final_transcript.append({
            "speaker": current_speaker,
            "start": current_start,
            "end": combined_output[-1]["end"],
            "text": " ".join(current_words)
        })

    for segment in final_transcript:
        print(f"Speaker {segment['speaker']} [{format_timestamp(segment['start'])} - {format_timestamp(segment['end'])}]: {segment['text']}")


if __name__ == "__main__":
    input_audio = "myoperator_sales_call.wav"  # Replace with your actual audio file
    transcribe_and_diarize(input_audio)