import os
import json
import yaml
import PyPDF2
from loguru import logger
from ai.prompts import RESUME_RANKER_PROMPT

class AIResumeRanker:
    def __init__(self, groq_client, cache, resumes_yaml_path: str = "config/resumes.yaml"):
        self.client = groq_client
        self.cache = cache
        self.resumes_config = {}
        self.resumes_text_cache = {}
        
        # Load resumes yaml configuration
        if os.path.exists(resumes_yaml_path):
            try:
                with open(resumes_yaml_path, "r", encoding="utf-8") as f:
                    self.resumes_config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"AIResumeRanker: Failed to load {resumes_yaml_path}: {e}")

    def _extract_pdf_text(self, filename: str) -> str:
        # Check cache first
        if filename in self.resumes_text_cache:
            return self.resumes_text_cache[filename]
            
        filepath = os.path.join("data", "resumes", filename)
        if not os.path.exists(filepath):
            logger.warning(f"AIResumeRanker: PDF file not found at {filepath}")
            return ""

        text = ""
        try:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            self.resumes_text_cache[filename] = text
            logger.info(f"AIResumeRanker: Extracted {len(text)} chars from {filename}")
            return text
        except Exception as e:
            logger.error(f"AIResumeRanker: Failed to extract text from {filepath}: {e}")
            return ""

    def resolve_resume(self, recommended_key: str) -> str:
        """Maps a recommended key (like 'backend') to the actual PDF filename."""
        key = recommended_key.lower().strip()
        if key in self.resumes_config:
            return self.resumes_config[key].get("resume", "Resume.pdf")
        # Fallback search if matching by substring
        for k, v in self.resumes_config.items():
            if k in key or key in k:
                return v.get("resume", "Resume.pdf")
        return "Resume.pdf"

    def rank_resumes(self, job_description: str, company: str, role: str) -> dict:
        # Check cache
        if self.client.cache_enabled:
            cached = self.cache.get(company, role, "resume_ranking", "all_resumes")
            if cached:
                return cached

        # Prepare available resumes text contents
        resumes_content = {}
        for key, details in self.resumes_config.items():
            resume_filename = details.get("resume", "Resume.pdf")
            text = self._extract_pdf_text(resume_filename)
            resumes_content[key] = {
                "skills": details.get("skills", []),
                "resume_text_excerpt": text[:1500]  # Pass a large chunk of the text
            }

        # Format prompt
        prompt = RESUME_RANKER_PROMPT.format(
            job_description=job_description,
            resumes_content=json.dumps(resumes_content, indent=2)
        )

        try:
            response = self.client.call_groq(prompt, json_mode=True)
            result = json.loads(response)
            
            if self.client.cache_enabled:
                self.cache.set(company, role, "resume_ranking", "all_resumes", result)
                
            return result
        except Exception as e:
            logger.error(f"AIResumeRanker: Failed to rank resumes: {e}")
            # Fallback to general resume
            return {
                "resume": "general",
                "confidence": 50,
                "reason": "Fallback to default resume due to API failure."
            }
