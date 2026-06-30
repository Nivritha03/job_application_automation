import json
from loguru import logger
from ai.prompts import ANALYZER_PROMPT

class AIAnalyzer:
    def __init__(self, groq_client, cache):
        self.client = groq_client
        self.cache = cache

    def analyze_job(self, job_title: str, company: str, job_description: str, job_skills: str, job_requirements: str, candidate_profile: dict, resumes_data: dict) -> dict:
        # Try to look up in cache first
        if self.client.cache_enabled:
            cached = self.cache.get(company, job_title, "job_analysis", "all_resumes")
            if cached:
                return cached

        # Format prompt
        prompt = ANALYZER_PROMPT.format(
            candidate_profile=json.dumps(candidate_profile, indent=2),
            resumes_data=json.dumps(resumes_data, indent=2),
            title=job_title,
            company=company,
            description=job_description,
            skills=job_skills,
            requirements=job_requirements
        )

        try:
            # Query Groq
            response = self.client.call_groq(prompt, json_mode=True)
            result = json.loads(response)
            
            # Save to cache
            if self.client.cache_enabled:
                self.cache.set(company, job_title, "job_analysis", "all_resumes", result)
                
            return result
        except Exception as e:
            logger.error(f"AIAnalyzer: Failed to parse job analysis response: {e}")
            # Fallback response
            return {
                "match_score": 50,
                "reasoning": "Fallback analysis due to API failure.",
                "strengths": [],
                "missing_skills": [],
                "recommended_resume": "general",
                "should_apply": True
            }
