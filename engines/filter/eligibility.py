from core.models import Job
import yaml
import re
from loguru import logger

class EligibilityFilter:
    def __init__(self):
        with open("config/scoring.yaml", "r") as f:
            self.scoring = yaml.safe_load(f)
            
        self.positive_tech = self.scoring.get("positive", {})
        self.negative_tech = self.scoring.get("negative", {})
        
        # Load keywords from config.yaml for target matching
        try:
            with open("config/config.yaml", "r") as f:
                config = yaml.safe_load(f)
            self.apply_keywords = config.get("search_keywords", [])
            self.skip_keywords = config.get("skip_keywords", [])
        except Exception:
            self.apply_keywords = []
            self.skip_keywords = []
            
    def score_job(self, job: Job) -> Job:
        title_lower = job.title.lower()
        desc_lower = job.description.lower()
        full_text = f"{title_lower} {desc_lower}"
        
        # 1. Check title apply and skip rules
        matched_apply = [kw for kw in self.apply_keywords if kw.lower() in title_lower]
        matched_skip = [kw for kw in self.skip_keywords if kw.lower() in title_lower]
        
        # 2. Check negative tech keywords in full text
        matched_neg_tech = []
        for kw in self.negative_tech.keys():
            if re.search(r'\b' + re.escape(kw) + r'\b', full_text):
                matched_neg_tech.append(kw)
                
        # 3. Decision Logic
        would_apply = False
        reason = ""
        
        if not matched_apply:
            would_apply = False
            reason = "No target search keyword found in job title."
        elif matched_skip:
            would_apply = False
            reason = f"Title contains skip keywords: {matched_skip}"
        elif matched_neg_tech:
            would_apply = False
            reason = f"Job matches negative technical keywords: {matched_neg_tech}"
        else:
            would_apply = True
            reason = f"Matches target title keywords: {matched_apply}"
            
        job.would_apply = would_apply
        job.score = 100 if would_apply else (-50 if (matched_skip or matched_neg_tech) else 0)
        
        # Log beautiful breakdown
        logger.info("\n" + "="*60)
        logger.info(f"FILTER DECISION FOR: {job.title}")
        logger.info(f"Location: {job.location}")
        logger.info(f"Title Matches (Apply) : {matched_apply}")
        logger.info(f"Title Matches (Skip)  : {matched_skip}")
        logger.info(f"Negative Tech Matches : {matched_neg_tech}")
        logger.info(f"Decision              : {'APPLY' if would_apply else 'SKIP'}")
        logger.info(f"Reason                : {reason}")
        logger.info("="*60 + "\n")
        
        return job
