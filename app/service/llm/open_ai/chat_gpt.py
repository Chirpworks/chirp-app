import json
import logging

from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str = None):
        """Initialize the OpenAI client with an API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = OpenAI(api_key=self.api_key)

    def send_prompt(self, prompt: str, model: str = "gpt-4o", max_tokens: int = 2000):
        """Send a prompt to OpenAI and return the response."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            if not response:
                logger.info("OpenAI response was empty or failed")
                raise Exception("OpenAI response was empty or failed")
            raw_response = response.choices[0].message.content
            content = self.clean_json_content(raw_response)
            return content
        except Exception as e:
            logger.error(f"Error communicating with OpenAI: {e}")
            raise e

    def clean_json_content(self, raw_response_string: str):
        # Step 1: Remove Markdown-style ```json and ```
        if raw_response_string.startswith("```json"):
            raw_response_string = raw_response_string.lstrip("`json").strip()
        if raw_response_string.endswith("```"):
            raw_response_string = raw_response_string[:-3].strip()

        # Step 2: Remove escaped newline and literal newline characters
        raw_response_string = raw_response_string.replace("\\n", "").replace("\n", "")

        # Step 3: Unescape quotes (\" → ")
        raw_response_string = raw_response_string.replace('\\"', '"')

        # Step 4: Remove double '"' symbols
        raw_response_string = raw_response_string.replace('""', '"')

        logger.info(f"raw response string: {raw_response_string}")
        # Step 4: Parse JSON
        try:
            r = json.loads(raw_response_string)
            logger.info(f"OpenAI returned {r}")
            return r
        except json.JSONDecodeError as e:
            logger.error("Failed to parse response JSON from OpenAI:", e)
            return None

    def polish_with_gpt(self, diarization) -> str:
        """
        Send `diarization` (a string) to GPT-3.5/4 to get a more fluent paraphrase.
        """
        prompt = [
            {
                "role": "system",
                "content": "You are a professional transliterator. Reformulate the given text such that any language other than English is transliterated into correct, fluent Latin script."
            },
            {
                "role": "user",
                "content": f"Please transliterate this in smooth English. Make sure to return the response as a JSON seralizable string that matches the input:\n\n\"{diarization}\""
            }
        ]
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",  # or "gpt-4"
            messages=prompt,
            temperature=0.3,  # lower temperature means more conservative rewriting
            max_tokens=len(str(diarization).split()) * 2  # budget ~ 2× word count
        )
        logger.info(f"transliteration returned by GPT = {response.choices[0].message.content}")
        return json.loads(response.choices[0].message.content.strip())


# Example Usage
if __name__ == "__main__":
    client = OpenAIClient(api_key="your_api_key_here")  # Replace with your actual API key
    response = client.send_prompt("Tell me a joke.")
    print(response)
