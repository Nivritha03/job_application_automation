import time
import re
from loguru import logger
from core.interfaces import BaseJobParser
from core.models import Job

class LinkedInJobParser(BaseJobParser):
    def extract_details(self, job: Job) -> Job:
        logger.info(f"LinkedInJobParser: Extracting details for {job.url}")
        try:
            try:
                self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
            except Exception as goto_err:
                logger.warning(f"LinkedInJobParser: Page navigation warning (proceeding): {goto_err}")
                
            try:
                self.page.wait_for_selector(".job-details-jobs-unified-top-card__job-title, h1, #job-details", timeout=15000)
            except Exception as wait_err:
                logger.warning(f"LinkedInJobParser: Timeout waiting for selectors: {wait_err}")
            time.sleep(1)
            
            # Check login page redirects
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("LinkedInJobParser: User is not authenticated.")
                job.error_message = "LinkedIn redirected to login page. Please check authentication."
                return job
                
            # Title
            title_loc = self.page.locator(".job-details-jobs-unified-top-card__job-title, h1").first
            if title_loc.count() > 0:
                job.title = title_loc.inner_text().strip()
                
            # Company
            comp_loc = self.page.locator(".job-details-jobs-unified-top-card__company-name a, .jobs-unified-top-card__company-name a").first
            if comp_loc.count() > 0:
                job.company = comp_loc.inner_text().strip()
                
            # Location
            loc_loc = self.page.locator(".job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet, [class*='topcard__flavor--bullet']").first
            if loc_loc.count() > 0 and loc_loc.inner_text().strip():
                job.location = loc_loc.inner_text().strip()
            else:
                # Fallback: scan spans, paragraphs, and list items for India technology hubs or location patterns
                found_loc = ""
                INDIA_KEYWORDS = ["india", "bangalore", "bengaluru", "hyderabad", "pune", "chennai", "mumbai", "noida", "gurgaon", "gurugram", "delhi", "kolkata", "ahmedabad"]
                for selector in ["span", "p", "div", "a"]:
                    try:
                        for el in self.page.locator(selector).all():
                            try:
                                txt = el.inner_text().strip()
                                # Location is typically brief (under 60 chars) and contains a major city or "India"
                                if len(txt) > 2 and len(txt) < 60 and any(city in txt.lower() for city in INDIA_KEYWORDS):
                                    if "set alert" not in txt.lower() and "notification" not in txt.lower() and "jobs" not in txt.lower() and "applied" not in txt.lower():
                                        found_loc = txt
                                        break
                            except:
                                pass
                    except:
                        pass
                    if found_loc:
                        break
                job.location = found_loc or "Remote / United States"
                
            # Description & Requirements
            desc_loc = self.page.locator("#job-details, .jobs-description__content, .jobs-box__html-content, [class*='description']").first
            if desc_loc.count() > 0:
                job.description = desc_loc.inner_html().strip()
                text_content = desc_loc.inner_text()
                
                reqs = []
                lines = text_content.split("\n")
                in_reqs = False
                for line in lines:
                    if any(w in line.lower() for w in ["requirements", "qualifications", "what you need", "skills", "experience", "what you'll bring"]):
                        in_reqs = True
                        continue
                    if in_reqs and any(w in line.lower() for w in ["benefits", "about the company", "what we offer"]):
                        in_reqs = False
                    if in_reqs and (line.strip().startswith(("•", "-", "*", "1.", "2.")) or len(line.strip()) > 35):
                        reqs.append(line.strip())
                job.requirements = "\n".join(reqs) if reqs else text_content
            else:
                job.description = "No description available."
                job.requirements = ""
                
            # Salary
            salary_loc = self.page.locator(".job-details-jobs-unified-top-card__salary-information, .jobs-unified-top-card__salary-information").first
            if salary_loc.count() > 0:
                job.salary = salary_loc.inner_text().strip()
            else:
                body_text = self.page.locator("body").inner_text()
                salary_matches = re.findall(r'\$[0-9,]{4,7}|\$[0-9]{2,3}k', body_text, re.IGNORECASE)
                if salary_matches:
                    job.salary = " - ".join(list(set(salary_matches))[:2])
                else:
                    job.salary = "Not specified"
                    
        except Exception as e:
            logger.error(f"LinkedInJobParser: Failed to extract details: {e}")
            job.error_message = str(e)
            
        return job
