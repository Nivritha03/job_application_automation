import json
from loguru import logger
import re

class MatcherAgent:
    def __init__(self):
        # Load user profile and skills
        self.profile = self._load_json("data/profile.json")
        self.skills = self._load_json("data/skills.json")
        
        # Flatten candidate skills for easy comparison
        self.candidate_skills = set()
        if "languages" in self.skills:
            self.candidate_skills.update(s.lower() for s in self.skills["languages"])
        if "frameworks" in self.skills:
            self.candidate_skills.update(s.lower() for s in self.skills["frameworks"])
        if "tools" in self.skills:
            self.candidate_skills.update(s.lower() for s in self.skills["tools"])

        # Master list of common tech skills to look for in job descriptions
        self.known_tech_skills = {
            "python", "java", "c++", "javascript", "typescript", "ruby", "go", "rust",
            "fastapi", "django", "flask", "react", "node.js", "angular", "vue",
            "docker", "kubernetes", "aws", "gcp", "azure", "sql", "postgresql", 
            "mongodb", "redis", "linux", "git", "machine learning", "ai", "pandas"
        }

    def _load_json(self, filepath: str) -> dict:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {filepath}: {e}")
            return {}

    def extract_job_skills(self, text: str) -> set:
        """Scan text for known technical skills."""
        found = set()
        text_lower = text.lower()
        
        # Simple word boundary regex search for each known skill
        for skill in self.known_tech_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                found.add(skill)
                
        return found

    def match_job(self, job_details: dict) -> dict:
        logger.info(f"Deterministically evaluating: {job_details.get('title')}")
        
        # Extract skills from job description
        description = job_details.get('description', '')
        title = job_details.get('title', '')
        
        job_skills = self.extract_job_skills(description + " " + title)
        
        # Fallback if no skills are found directly
        if not job_skills:
            if "python" in title.lower():
                job_skills = {"python"}
            else:
                return {"score": 0, "reason": "No known skills found in job description."}
                
        # Calculate intersection
        matched_skills = self.candidate_skills.intersection(job_skills)
        missing_skills = job_skills.difference(self.candidate_skills)
        
        # Match = (Matched Skills / Required Skills) * 100
        score = int((len(matched_skills) / len(job_skills)) * 100)
        
        reason = f"Skills matched: {', '.join(matched_skills).title() if matched_skills else 'None'}."
        if missing_skills:
            reason += f" Missing: {', '.join(missing_skills).title()}."
            
        return {
            "score": score,
            "reason": reason,
            "matched_skills": list(matched_skills),
            "missing_skills": list(missing_skills)
        }
        
    def evaluate_decision(self, match_result: dict, job_details: dict) -> bool:
        """Phase 5: Decision Engine Rules"""
        score = match_result.get("score", 0)
        
        # Rule 1: Match must be >= 70%
        if score < 70:
            return False
            
        return True
