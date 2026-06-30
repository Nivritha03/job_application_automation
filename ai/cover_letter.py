from loguru import logger
from ai.prompts import COVER_LETTER_PROMPT

class AICoverLetterGenerator:
    def __init__(self, groq_client, validator, cache):
        self.client = groq_client
        self.validator = validator
        self.cache = cache

    def generate(self, job_title: str, company: str, job_description: str, resume_text: str, profile_details: dict) -> str:
        # Check cache
        if self.client.cache_enabled:
            cached = self.cache.get(company, job_title, "cover_letter", "resume")
            if cached:
                return cached.get("text", "")

        # Format prompt
        prompt = COVER_LETTER_PROMPT.format(
            title=job_title,
            company=company,
            description=job_description,
            resume_text=resume_text,
            profile_text=str(profile_details)
        )

        try:
            # Generate cover letter (maximum 3 attempts if validation fails)
            for attempt in range(3):
                logger.info(f"AICoverLetterGenerator: Generating cover letter (attempt {attempt + 1})...")
                cover_letter_text = self.client.call_groq(prompt)
                
                # Clean prompt artifacts if any (e.g. quotes or markdown wrapper)
                cover_letter_text = cover_letter_text.strip()
                if cover_letter_text.startswith("```"):
                    # remove backticks code block wrappers
                    lines = cover_letter_text.splitlines()
                    if len(lines) > 2:
                        cover_letter_text = "\n".join(lines[1:-1])

                # Validate facts in cover letter
                is_valid = self.validator.validate(cover_letter_text, resume_text, str(profile_details))
                if is_valid:
                    # Save to cache
                    if self.client.cache_enabled:
                        self.cache.set(company, job_title, "cover_letter", "resume", {"text": cover_letter_text})
                    return cover_letter_text
                    
                logger.warning("AICoverLetterGenerator: Cover letter failed fact validation. Retrying generation...")

            logger.error("AICoverLetterGenerator: Failed to generate a valid, factual cover letter after 3 attempts.")
            return ""
        except Exception as e:
            logger.error(f"AICoverLetterGenerator: Cover letter generation failed: {e}")
            return ""
