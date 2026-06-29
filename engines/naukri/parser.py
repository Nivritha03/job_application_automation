import time
from loguru import logger
from core.interfaces import BaseJobParser
from core.models import Job

class NaukriJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        logger.info(f"NaukriJobParser: Extracting details for {job.url}")
        try:
            try:
                self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"NaukriJobParser: Goto page warning: {e}")
                
            try:
                self.page.wait_for_selector("h1, section.job-desc, .jd-header-title", timeout=15000)
            except Exception as wait_err:
                logger.warning(f"NaukriJobParser: Selector wait timeout: {wait_err}")
                
            time.sleep(1)
            
            # Check login page redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("NaukriJobParser: Authentication required.")
                job.error_message = "Authentication required to view details."
                return job
                
            # Title
            title_loc = self.page.locator("h1.jd-header-title, h1, [class*='jd-header-title']").first
            if title_loc.count() > 0:
                job.title = title_loc.inner_text().strip()
                
            # Company
            comp_loc = self.page.locator(".jd-header-comp-name a, [class*='jd-header-comp-name']").first
            if comp_loc.count() > 0:
                job.company = comp_loc.inner_text().strip()
                
            # Location
            loc_loc = self.page.locator(".jd-header-comp-name .location, span.location, [class*='location']").first
            if loc_loc.count() > 0:
                job.location = loc_loc.inner_text().strip()
                
            # Description
            desc_loc = self.page.locator("section.job-desc, .job-desc, .jd-desc").first
            if desc_loc.count() > 0:
                job.description = desc_loc.inner_html().strip()
                text_content = desc_loc.inner_text()
                
                # Try parsing requirements
                reqs = []
                for line in text_content.split("\n"):
                    if any(w in line.lower() for w in ["requirements", "skills", "experience", "qualifications"]):
                        reqs.append(line.strip())
                job.requirements = "\n".join(reqs) if reqs else text_content
            else:
                job.description = self.page.locator("body").inner_text().strip()
                job.requirements = ""
                
            # Skills tags
            skills_loc = self.page.locator(".key-skill a, a.key-skill, span.key-skill").all()
            if skills_loc:
                job.skills = [s.inner_text().strip() for s in skills_loc if s.inner_text().strip()]
                
        except Exception as e:
            logger.error(f"NaukriJobParser: Failed to extract details: {e}")
            job.error_message = str(e)
            
        return job
