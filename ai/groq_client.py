import os
import time
import yaml
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from loguru import logger

# Load environment variables
load_dotenv()

class GroqClient:
    def __init__(self, model_override=None, temperature_override=None, max_tokens_override=None):
        # Load config.yaml
        config_path = "config/config.yaml"
        self.config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"GroqClient: Failed to load config.yaml: {e}")

        ai_config = self.config.get("ai", {})
        
        # Resolve API Key
        # Priority: 1. Environment Variable 2. .env (via load_dotenv) 3. config.yaml
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            self.api_key = ai_config.get("api_key")
            # If it's a placeholder like "${GROQ_API_KEY}", check if it got resolved
            if self.api_key == "${GROQ_API_KEY}":
                self.api_key = None

        self.enabled = ai_config.get("enabled", True)
        self.provider = ai_config.get("provider", "groq")
        self.model = model_override or ai_config.get("model", "llama-3.3-70b-versatile")
        
        # Read temperature and max_tokens safely
        try:
            self.temperature = float(temperature_override if temperature_override is not None else ai_config.get("temperature", 0.2))
        except (ValueError, TypeError):
            self.temperature = 0.2
            
        try:
            self.max_tokens = int(max_tokens_override if max_tokens_override is not None else ai_config.get("max_tokens", 1024))
        except (ValueError, TypeError):
            self.max_tokens = 1024

        self.cache_enabled = ai_config.get("cache", True)

        if not self.api_key:
            logger.warning("GroqClient: GROQ_API_KEY is not configured. AI features will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.api_key
            )
            logger.info(f"GroqClient initialized successfully. Model: {self.model}")

    def call_groq(self, prompt: str, system_prompt: str = "You are a helpful job application assistant.", json_mode: bool = False) -> str:
        if not self.client:
            logger.error("GroqClient: Cannot call Groq, client is not initialized due to missing API key.")
            return ""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response_format = {"type": "json_object"} if json_mode else None

        start_time = time.time()
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format=response_format
            )
            latency = time.time() - start_time
            
            # Extract response and token metadata
            response_text = completion.choices[0].message.content
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            total_tokens = completion.usage.total_tokens

            # Cost estimation: llama-3.3-70b-versatile is approx $0.59/M input and $0.79/M output
            input_cost = (prompt_tokens / 1_000_000) * 0.59
            output_cost = (completion_tokens / 1_000_000) * 0.79
            estimated_cost = input_cost + output_cost

            # Log to logs/ai.log
            self._log_interaction(prompt, response_text, latency, prompt_tokens, completion_tokens, estimated_cost)
            
            return response_text
        except Exception as e:
            logger.error(f"GroqClient: API call failed: {e}")
            return ""

    def _log_interaction(self, prompt: str, response: str, latency: float, prompt_tokens: int, completion_tokens: int, cost: float):
        os.makedirs("logs", exist_ok=True)
        log_path = "logs/ai.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "model": self.model,
            "prompt": prompt,
            "response": response,
            "latency_seconds": round(latency, 3),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_estimate_usd": round(cost, 6)
        }
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"GroqClient: Failed to write to ai.log: {e}")

# Import json dynamically to avoid circular import issues
import json
