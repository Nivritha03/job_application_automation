from core.interfaces import BaseJobParser
from core.models import Job
from loguru import logger
import time
import re

class DefaultJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        if not job.url:
            return job
            
        logger.info(f"DefaultJobParser: Parsing details for: {job.title} at {job.company}")
        try:
            self.page.goto(job.url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(1)
            
            # Smart fallback selectors for generic pages
            body_text = ""
            for selector in ["div.content", "div.description", "section.job-description", "div.job-details", "body"]:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    text = loc.first.inner_text().strip()
                    if len(text) > 100:
                        body_text = text
                        break
            
            job.description = body_text or "No description found"
            
            # Simple rules for requirements
            lines = job.description.split("\n")
            reqs = []
            capture = False
            for line in lines:
                if re.search(r'\b(requirements|qualifications|what you bring|experience|skills)\b', line.lower()):
                    capture = True
                    continue
                if capture:
                    if len(line.strip()) > 0:
                        reqs.append(line.strip())
                    if len(reqs) > 15 or (len(line.strip()) == 0 and len(reqs) > 5):
                        break
            job.requirements = "\n".join(reqs)
            
        except Exception as e:
            logger.error(f"DefaultJobParser: Failed to parse: {e}")
            job.error_message = str(e)
            
        return job

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

class LeverJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        if not job.url:
            return job
            
        logger.info(f"LeverJobParser: Parsing details for: {job.title} at {job.company}")
        try:
            self.page.goto(job.url)
            self.page.wait_for_load_state("networkidle")
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
