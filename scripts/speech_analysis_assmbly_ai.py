import assemblyai as aai

def transcribe():
    # Start by making sure the `assemblyai` package is installed.
    # If not, you can install it by running the following command:
    # pip install -U assemblyai
    #
    # Note: Some macOS users may need to use `pip3` instead of `pip`.

    import assemblyai as aai

    # Replace with your API key
    aai.settings.api_key = "502a7789a311434b832df67e5ceab553"

    # URL of the file to transcribe
    FILE_URL = "wav_sample.wav"

    # You can also transcribe a local file by passing in a file path
    # FILE_URL = './path/to/file.mp3'

    config = aai.TranscriptionConfig(speaker_labels=True, speakers_expected=2)

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(
        FILE_URL,
        config=config
    )

    for utterance in transcript.utterances:
        print(f"Speaker {utterance.speaker}: {utterance.text}")


if __name__ == "__main__":
    transcribe()
