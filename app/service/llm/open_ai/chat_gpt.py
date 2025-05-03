import openai
import os


class OpenAIClient:
    def __init__(self, api_key: str = None):
        """Initialize the OpenAI client with an API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required.")

    def send_prompt(self, prompt: str, model: str = "gpt-4o", max_tokens: int = 2000):
        """Send a prompt to OpenAI and return the response."""
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error communicating with OpenAI: {e}")
            return None


# Example Usage
if __name__ == "__main__":
    client = OpenAIClient(api_key="your_api_key_here")  # Replace with your actual API key
    response = client.send_prompt("Tell me a joke.")
    print(response)
