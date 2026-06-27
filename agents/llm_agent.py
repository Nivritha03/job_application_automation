import os
import json
from loguru import logger
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is not set. LLM features will fail.")
        else:
            self.client = OpenAI(api_key=self.api_key)

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            logger.debug(f"Calling OpenAI ({self.model}) with JSON response format")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to generate JSON from LLM: {e}")
            return {}

    def generate_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 150) -> str:
        try:
            logger.debug(f"Calling OpenAI ({self.model}) for text generation")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate text from LLM: {e}")
            return ""
