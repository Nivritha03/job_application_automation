import json
from loguru import logger
from ai.prompts import QUESTION_ANSWERER_PROMPT, FORM_ASSISTANT_PROMPT

class AIQuestionAnswerer:
    def __init__(self, groq_client, validator, cache):
        self.client = groq_client
        self.validator = validator
        self.cache = cache

    def answer_question(self, question: str, field_type: str, job_details: str, resume_text: str, profile_details: dict, company: str, role: str) -> str:
        # Check cache first
        if self.client.cache_enabled:
            cached = self.cache.get(company, role, f"qa_{question}", "resume")
            if cached:
                return cached.get("answer", "REQUIRES_USER_INPUT")

        # Format prompt
        prompt = QUESTION_ANSWERER_PROMPT.format(
            question=question,
            field_type=field_type,
            resume_text=resume_text,
            profile_text=str(profile_details),
            job_details=job_details
        )

        try:
            for attempt in range(2):
                logger.info(f"AIQuestionAnswerer: Generating answer for question: {question!r} (attempt {attempt + 1})...")
                answer = self.client.call_groq(prompt).strip()
                
                # Check for direct user input request
                if "REQUIRES_USER_INPUT" in answer:
                    return "REQUIRES_USER_INPUT"
                    
                # Validate answer factuality
                is_valid = self.validator.validate(answer, resume_text, str(profile_details))
                if is_valid:
                    # Save to cache
                    if self.client.cache_enabled:
                        self.cache.set(company, role, f"qa_{question}", "resume", {"answer": answer})
                    return answer
                    
                logger.warning(f"AIQuestionAnswerer: Answer failed validation for question: {question!r}. Retrying...")
                
            logger.error(f"AIQuestionAnswerer: Failed to generate factual answer after 2 attempts for: {question!r}")
            return "REQUIRES_USER_INPUT"
        except Exception as e:
            logger.error(f"AIQuestionAnswerer: Question answering failed: {e}")
            return "REQUIRES_USER_INPUT"

    def form_assistant_fallback(self, label: str, placeholder: str, question: str, html_context: str, job_description: str, resume_text: str, profile_details: dict, company: str, role: str) -> dict:
        # Check cache first
        cache_key = f"fallback_{label}_{placeholder}_{question}"
        if self.client.cache_enabled:
            cached = self.cache.get(company, role, cache_key, "resume")
            if cached:
                return cached

        # Format prompt
        prompt = FORM_ASSISTANT_PROMPT.format(
            label=label,
            placeholder=placeholder,
            question=question,
            html_context=html_context,
            job_description=job_description,
            resume_text=resume_text,
            profile_text=str(profile_details)
        )

        try:
            response = self.client.call_groq(prompt, json_mode=True)
            result = json.loads(response)
            
            # Validate answer if it is not REQUIRES_USER_INPUT
            answer = result.get("answer", "")
            if answer and answer != "REQUIRES_USER_INPUT":
                is_valid = self.validator.validate(answer, resume_text, str(profile_details))
                if not is_valid:
                    logger.warning(f"AIFormAssistant: Fallback answer '{answer}' failed validation. Overriding to REQUIRES_USER_INPUT.")
                    result["answer"] = "REQUIRES_USER_INPUT"
                    result["confidence"] = 0
                    result["reason"] = "Failed validation check."
            
            # Save to cache
            if self.client.cache_enabled:
                self.cache.set(company, role, cache_key, "resume", result)
                
            return result
        except Exception as e:
            logger.error(f"AIFormAssistant: Fallback form assistant call failed: {e}")
            return {
                "answer": "REQUIRES_USER_INPUT",
                "confidence": 0,
                "reason": f"Fallback error: {e}"
            }
