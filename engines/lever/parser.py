from core.interfaces import BaseJobParser
from core.models import Job
from loguru import logger
import time

class LeverJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        if not job.url:
            return job
            
        logger.info(f"LeverJobParser: Parsing details for: {job.title} at {job.company}")
        try:
            self.page.goto(job.url)
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(1)
            
            # Lever specific selectors
            desc_locator = self.page.locator("div.section-wrapper, div.content")
            if desc_locator.count() > 0:
                text_parts = [loc.inner_text().strip() for loc in desc_locator.all()]
                job.description = "\n\n".join(text_parts)
            else:
                job.description = self.page.locator("body").inner_text().strip()
                
            loc_locator = self.page.locator("div.posting-categories, div.location")
            if loc_locator.count() > 0:
                job.location = loc_locator.first.inner_text().strip()
                
            # Parse requirements
            req_lines = []
            for item in self.page.locator("div.section-wrapper ul li").all():
                text = item.inner_text().strip()
                if len(text) > 5:
                    req_lines.append(text)
            job.requirements = "\n".join(req_lines[:15])
            
        except Exception as e:
            logger.error(f"LeverJobParser: Failed to parse: {e}")
            job.error_message = str(e)
            
        return job
