import json
import os
from google import genai


def run_transcription():
    API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBRvr5reWrIEUi_9DHmeyR0qpQOW_js8CM")
    client = genai.Client(api_key=API_KEY)

    myfile = client.files.upload(file="1749112881.2976816_0.wav")

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20", contents=["This is an audio clip with language being a possible mix of English. "
                                            "Hindi, Punjabi, Tamil, Telugu and Malayalam and 2 speakers."
                                            "Transcribe this audio clip and give clear speaker diarization."
                                            "Also, give me the entire response transliterated in English"
                                            "For each segment, give me a json response in the format:"
                                            "{\"speaker\": <speaker_id>, \"text\": <english_transliterated_text>, \"translation\": <translation>} "
                                                          "Pass every individual json in a list.",
                                            myfile]
    )

    transcription = response.text
    transcription = transcription.strip("```json").strip("```")
    transcription = transcription.strip("'''json").strip("'''")
    transcription = json.loads(transcription)
    return transcription


if __name__ == '__main__':
    run_transcription()
