from loguru import logger
from playwright.sync_api import Page
import urllib.parse

class ATSRouter:
    def __init__(self, page: Page):
        self.page = page

    def identify_ats(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        
        if "greenhouse.io" in domain:
            return "greenhouse"
        elif "lever.co" in domain:
            return "lever"
        elif "ashbyhq.com" in domain:
            return "ashby"
        elif "workable.com" in domain:
            return "workable"
        elif "linkedin.com" in domain:
            return "linkedin"
        elif "redrob.ai" in domain:
            return "redrob_internal"
        else:
            return "unknown"

    def apply(self, url: str, job_data: dict, resume_path: str, cover_letter: str) -> bool:
        ats_type = self.identify_ats(url)
        logger.info(f"Identified ATS type: {ats_type} for URL: {url}")
        
        if ats_type == "unknown":
            logger.warning(f"Unsupported ATS for {url}. Skipping automation.")
            return False
            
        # Example routing
        if ats_type == "redrob_internal":
            return self._apply_redrob(url, job_data, resume_path, cover_letter)
        elif ats_type == "greenhouse":
            return self._apply_greenhouse(url, job_data, resume_path, cover_letter)
        # Add other ATS handlers here
        
        return False
        
    def _apply_redrob(self, url, job_data, resume_path, cover_letter):
        logger.info("Handling Redrob internal application (Mock)")
        return True
        
    def _apply_greenhouse(self, url, job_data, resume_path, cover_letter):
        logger.info("Handling Greenhouse application (Mock)")
        return True
