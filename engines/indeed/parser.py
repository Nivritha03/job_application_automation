import time
from loguru import logger
from core.interfaces import BaseJobParser
from core.models import Job

class IndeedJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        logger.info(f"IndeedJobParser: Extracting details for {job.url}")
        try:
            try:
                self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"IndeedJobParser: Page goto warning: {e}")
                
            try:
                self.page.wait_for_selector("h1, #jobDescriptionText, .jobsearch-JobComponent-description", timeout=15000)
            except Exception as wait_err:
                logger.warning(f"IndeedJobParser: Selector wait timeout: {wait_err}")
                
            time.sleep(1)
            
            # Check login redirects
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("IndeedJobParser: Authentication required.")
                job.error_message = "Authentication required to view details."
                return job
                
            # Title
            title_loc = self.page.locator("h1, .jobsearch-JobInfoHeader-title").first
            if title_loc.count() > 0:
                job.title = title_loc.inner_text().strip()
                
            # Company
            comp_loc = self.page.locator("[data-testid='inlineHeader-companyName'], .jobsearch-CompanyReview--heading").first
            if comp_loc.count() > 0:
                job.company = comp_loc.inner_text().strip()
                
            # Location
            loc_loc = self.page.locator("[data-testid='inlineHeader-companyLocation'], .jobsearch-JobInfoHeader-subtitle").first
            if loc_loc.count() > 0:
                job.location = loc_loc.inner_text().strip()
                
            # Description
            desc_loc = self.page.locator("#jobDescriptionText, .jobsearch-JobComponent-description").first
            if desc_loc.count() > 0:
                job.description = desc_loc.inner_html().strip()
                text_content = desc_loc.inner_text()
                
                # Requirements
                reqs = []
                for line in text_content.split("\n"):
                    if any(w in line.lower() for w in ["requirements", "skills", "experience", "qualifications"]):
                        reqs.append(line.strip())
                job.requirements = "\n".join(reqs) if reqs else text_content
            else:
                job.description = self.page.locator("body").inner_text().strip()
                job.requirements = ""
                
        except Exception as e:
            logger.error(f"IndeedJobParser: Failed to extract details: {e}")
            job.error_message = str(e)
            
        return job
