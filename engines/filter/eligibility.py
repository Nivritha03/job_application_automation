from core.models import Job
import yaml
import re
from loguru import logger

class EligibilityFilter:
    def __init__(self):
        with open("config/scoring.yaml", "r") as f:
            self.scoring = yaml.safe_load(f)
            
        self.positive = self.scoring.get("positive", {})
        self.negative = self.scoring.get("negative", {})
        
    def score_job(self, job: Job) -> Job:
        score = 0
        text = (job.title + " " + job.description).lower()
        
        for keyword, points in self.positive.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                score += points
                job.skills.append(keyword)
                
        for keyword, points in self.negative.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                score += points
                job.skills.append(f"NOT {keyword}")
                
        job.score = score
        
        # Arbitrary rule for Phase 6
        job.would_apply = score >= 5
        
        logger.info(f"Scored {job.title}: {score} points -> Would Apply: {job.would_apply}")
        return job
