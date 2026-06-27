from core.interfaces import BaseJobParser
from core.models import Job
from loguru import logger
import time

class GreenhouseJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        if not job.url:
            return job
            
        logger.info(f"GreenhouseJobParser: Parsing details for: {job.title} at {job.company}")
        try:
            self.page.goto(job.url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Greenhouse specific selectors
            desc_locator = self.page.locator("div.job__description, div#content, section.app-body")
            if desc_locator.count() > 0:
                job.description = desc_locator.first.inner_text().strip()
            else:
                job.description = self.page.locator("body").inner_text().strip()
                
            loc_locator = self.page.locator("div.job__location, div.location")
            if loc_locator.count() > 0:
                job.location = loc_locator.first.inner_text().strip()
                
            # Parse requirements
            req_lines = []
            for item in self.page.locator("div.job__description ul li, div#content ul li, section.app-body ul li").all():
                text = item.inner_text().strip()
                if len(text) > 5:
                    req_lines.append(text)
            job.requirements = "\n".join(req_lines[:15])
            
        except Exception as e:
            logger.error(f"GreenhouseJobParser: Failed to parse: {e}")
            job.error_message = str(e)
            
        return job
