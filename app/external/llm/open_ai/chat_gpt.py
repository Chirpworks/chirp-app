import json
import logging
from typing import Optional

from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenAI client with an API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required.")
        self.client = OpenAI(api_key=self.api_key)

    def send_prompt(self, prompt: str, model: str = "gpt-4.1-mini", max_tokens: int = 2000):
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
            if raw_response is None:
                logger.error("OpenAI response content was None")
                return None
            content = self.clean_json_content(raw_response)
            return content
        except Exception as e:
            logger.error("Error communicating with OpenAI: %s", e)
            raise e

    def send_prompt_raw(self, prompt: str, model: str = "gpt-4.1-mini", max_tokens: int = 1000) -> Optional[str]:
        """Send a prompt and return the raw assistant message content (no JSON parsing)."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            if not response:
                logger.info("OpenAI response was empty or failed")
                return None
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Error communicating with OpenAI (raw): %s", e)
            return None

    def clean_json_content(self, raw_response_string: str):
        # Normalize whitespace for robust parsing
        raw = raw_response_string.strip()
        logger.info("raw response string: %s", raw)

        # If content is fenced as ```sql ... ``` or ``` ... ``` extract inner
        if raw.startswith("```") and raw.endswith("```"):
            inner = raw.strip("`")
            # handle leading language tag like sql
            if inner.lower().startswith("sql"):
                inner = inner[3:]
            inner = inner.strip()
            # If inner looks like SQL (starts with SELECT), return as dict
            if inner[:6].lower() == "select":
                return {"sql": inner}
            raw = inner

        # If content contains a SELECT, try to extract SQL substring
        low = raw.lower()
        if "select" in low and (" from " in low or low.startswith("select")):
            try:
                import re
                m = re.search(r"select[\s\S]*", raw, flags=re.IGNORECASE)
                if m:
                    sql_text = m.group(0).strip()
                    # strip trailing fences if any leftovers
                    sql_text = sql_text.replace("```", "").strip()
                    return {"sql": sql_text}
            except Exception:
                pass

        # Try strict JSON parsing
        try:
            parsed = json.loads(raw)
            logger.info("OpenAI returned %s", parsed)
            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse response JSON from OpenAI: %s", e)
            return None

    def polish_with_gpt(self, diarization) -> str:
        """
        Send `diarization` (a string) to GPT-3.5/4 to get a more fluent paraphrase.
        """
        sample_string = "[\
              {\
                \"speaker\": \"SPEAKER_01\",\
                \"start\": 0.723,\
                \"end\": 5.913,\
                \"text\": \"Hey Kunal, how are you doing?\"\
              },\
              {\
                \"speaker\": \"SPEAKER_00\",\
                \"start\": 7.657,\
                \"end\": 8.960,\
                \"text\": \"Hey Vidur, I'm doing good...\"\
              },\
            ]\
        "
        prompt = [
            {
                "role": "system",
                "content": "You are a professional transliterator. Reformulate the given text such that any language "
                           "other than English is transliterated into correct, fluent Latin script."
            },
            {
                "role": "user",
                "content": f"Please transliterate this in smooth English. If the sentence feels like it doesn't make "
                           f"complete sense then feel free to add words or change the text minimally for it "
                           f"to make logical sense. Make sure to return the response as a JSON serializable string that "
                           f"matches the input:\n\n\"{diarization}\" \n\n Please return exactly a JSON array of "
                           f"objects, e.g.: {sample_string}\n\n Use double quotes for every key and string value. Do "
                           f"not include any `np.float64(...)` wrappers; use plain numbers. Do not wrap the output in "
                           f"backticks or markdown fences—just output raw JSON."
            }
        ]
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",  # or "gpt-4"
            messages=prompt,  # type: ignore[arg-type]
            temperature=0.3,  # lower temperature means more conservative rewriting
            max_tokens=len(str(diarization).split()) * 2  # budget ~ 2× word count
        )
        logger.info(f"transliteration returned by GPT = {response.choices[0].message.content}")
        content = response.choices[0].message.content
        return content.strip() if content else ""


# Example Usage
if __name__ == "__main__":
    client = OpenAIClient(api_key="your_api_key_here")  # Replace with your actual API key
    response = client.send_prompt("Tell me a joke.")
    print(response)
