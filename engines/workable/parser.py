import time
import re
from loguru import logger
from core.interfaces import BaseJobParser
from core.models import Job

class WorkableJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        logger.info(f"WorkableJobParser: Extracting details for {job.url}")
        try:
            self.page.goto(job.url)
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Title
            title_loc = self.page.locator("h1, [data-ui='job-title']").first
            if title_loc.count() > 0:
                job.title = title_loc.inner_text().strip()
                
            # Location
            loc_loc = self.page.locator("[data-ui='job-location'], [class*='location']").first
            if loc_loc.count() > 0:
                job.location = loc_loc.inner_text().strip()
            else:
                job.location = "Remote"
                
            # Description & Requirements
            desc_loc = self.page.locator("[data-ui='job-description'], [class*='description'], section[class*='job-section']").first
            if desc_loc.count() > 0:
                job.description = desc_loc.inner_html().strip()
                text_content = desc_loc.inner_text()
                
                # Try to extract requirements section specifically
                reqs = []
                lines = text_content.split("\n")
                in_reqs = False
                for line in lines:
                    if any(w in line.lower() for w in ["requirements", "what we're looking for", "skills", "experience", "what you need"]):
                        in_reqs = True
                        continue
                    if in_reqs and any(w in line.lower() for w in ["benefits", "about", "what we offer", "salary"]):
                        in_reqs = False
                    if in_reqs and (line.strip().startswith(("•", "-", "*", "1.", "2.")) or len(line.strip()) > 35):
                        reqs.append(line.strip())
                job.requirements = "\n".join(reqs) if reqs else text_content
            else:
                job.description = "No description available."
                job.requirements = ""
                
            # Parse salary info
            body_text = self.page.locator("body").inner_text()
            salary_matches = re.findall(r'\$[0-9,]{4,7}|\$[0-9]{2,3}k', body_text, re.IGNORECASE)
            if salary_matches:
                job.salary = " - ".join(list(set(salary_matches))[:2])
            else:
                job.salary = "Not specified"
                
        except Exception as e:
            logger.error(f"WorkableJobParser: Failed to parse details: {e}")
            job.error_message = str(e)
            
        return job
