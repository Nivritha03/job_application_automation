from core.models import Job
import yaml
import re
from loguru import logger

class ResumeSelector:
    def __init__(self):
        with open("config/resumes.yaml", "r") as f:
            self.mapping = yaml.safe_load(f)
        # Use the first entry's resume as the default fallback
        self._default = next(iter(self.mapping.values()))["resume"]
        self._cache = {}  # Cache key: normalized job title -> resume path
            
    def select(self, job: Job) -> Job:
        cache_key = job.title.strip().lower()
        if cache_key in self._cache:
            job.resume_used = self._cache[cache_key]
            logger.info(f"ResumeSelector (cache hit): Selected {job.resume_used} for title {job.title!r}")
            return job

        text = (job.title + " " + (job.description or "") + " " + (job.requirements or "")).lower()
        
        best_match = None
        highest_score = -1
        
        for category, data in self.mapping.items():
            # Match concrete skills (weight: 2)
            skill_hits = sum(1 for skill in data.get("skills", []) if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text))
            # Match keywords (weight: 1)
            keyword_hits = sum(1 for kw in data.get("keywords", []) if re.search(r'\b' + re.escape(kw.lower()) + r'\b', text))
            
            score = (skill_hits * 2) + keyword_hits
            if score > highest_score:
                highest_score = score
                best_match = data["resume"]
                
        if highest_score > 0:
            job.resume_used = best_match
        else:
            job.resume_used = self._default
            
        self._cache[cache_key] = job.resume_used
        logger.info(f"ResumeSelector (cache miss): Selected resume {job.resume_used} (Match Score: {highest_score})")
        return job
