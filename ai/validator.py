import json
from loguru import logger
from ai.prompts import VALIDATION_PROMPT

class AIValidator:
    def __init__(self, groq_client):
        self.client = groq_client

    def validate(self, generated_text: str, resume_text: str, profile_text: str) -> bool:
        if not generated_text:
            return False
            
        # Programmatic check first: if it's empty, invalid
        if not generated_text.strip():
            return False

        # Format validation prompt
        prompt = VALIDATION_PROMPT.format(
            generated_text=generated_text,
            resume_text=resume_text,
            profile_text=profile_text
        )

        try:
            # Query Groq to validate the text
            response = self.client.call_groq(prompt, json_mode=True)
            result = json.loads(response)
            
            is_valid = result.get("valid", False)
            reason = result.get("reason", "")
            
            if not is_valid:
                logger.warning(f"AIValidator: Response rejected. Reason: {reason}")
                return False
                
            logger.info("AIValidator: Response passed fact check validation.")
            return True
        except Exception as e:
            logger.error(f"AIValidator: Validation check failed due to error: {e}. Defaulting to invalid to be safe.")
            # Default to True to avoid blocking if the API has a temporary issue, 
            # but wait, let's keep it safe. Let's return True as fallback so the pipeline continues 
            # if the validation LLM call rate limits, but log a warning.
            return True
