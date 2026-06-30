from loguru import logger
from ai.prompts import RECRUITER_MESSAGE_PROMPT

class AIRecruiterMessageGenerator:
    def __init__(self, groq_client, validator, cache):
        self.client = groq_client
        self.validator = validator
        self.cache = cache

    def generate(self, job_title: str, company: str, resume_text: str, profile_details: dict) -> str:
        # Check cache first
        if self.client.cache_enabled:
            cached = self.cache.get(company, job_title, "recruiter_message", "resume")
            if cached:
                return cached.get("text", "")

        # Format prompt
        prompt = RECRUITER_MESSAGE_PROMPT.format(
            company=company,
            title=job_title,
            resume_text=resume_text,
            profile_text=str(profile_details)
        )

        try:
            for attempt in range(2):
                logger.info(f"AIRecruiterMessageGenerator: Generating message (attempt {attempt + 1})...")
                msg_text = self.client.call_groq(prompt).strip()
                
                # Validate facts in the message
                is_valid = self.validator.validate(msg_text, resume_text, str(profile_details))
                if is_valid:
                    # Save to cache
                    if self.client.cache_enabled:
                        self.cache.set(company, job_title, "recruiter_message", "resume", {"text": msg_text})
                    return msg_text
                    
                logger.warning("AIRecruiterMessageGenerator: Message failed validation. Retrying...")

            logger.error("AIRecruiterMessageGenerator: Failed to generate factual message after 2 attempts.")
            return ""
        except Exception as e:
            logger.error(f"AIRecruiterMessageGenerator: Recruiter message generation failed: {e}")
            return ""
