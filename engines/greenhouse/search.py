from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List
from loguru import logger
import time
import re

class GreenhouseSearch(BaseSearchEngine):
    def search(self, company: str, query: str = "") -> List[Job]:
        company_slug = company if company else "reddit"
        url = f"https://job-boards.greenhouse.io/{company_slug}"
        logger.info(f"GreenhouseSearch: Scraping board directly from {url}")
        
        jobs_found = []
        try:
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            # Use search inputs if present to filter by keyword
            try:
                search_inputs = self.page.locator("input[id*='search'], input[name*='search'], input[placeholder*='Search']").all()
                if search_inputs and query:
                    search_inputs[0].fill(query)
                    search_inputs[0].press("Enter")
                    self.page.wait_for_load_state("networkidle")
                    time.sleep(1.5)
            except Exception:
                pass
                
            # Scroll down to trigger any pagination or lazy loading
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            # Find all anchor tags on the page
            anchors = self.page.locator("a").all()
            for a in anchors:
                href = a.get_attribute("href") or ""
                # Match /jobs/ or /reddit/jobs/
                if "/jobs/" in href and (company_slug in href or href.startswith("/")):
                    # Construct absolute URL
                    if href.startswith("/"):
                        abs_url = f"https://job-boards.greenhouse.io{href}"
                    else:
                        abs_url = href
                        
                    # Extract job ID if possible
                    job_id = abs_url.split("/jobs/")[-1].split("?")[0]
                    title = a.inner_text().strip()
                    
                    # Clean title and avoid duplicates of same URL
                    if abs_url not in [j.url for j in jobs_found] and title:
                        if query and query.lower() not in title.lower():
                            continue
                            
                        # Clean any tags or "New" badges from title
                        clean_title = re.sub(r'\bNew\b', '', title, flags=re.IGNORECASE).strip()
                        jobs_found.append(Job(
                            id=job_id,
                            title=clean_title,
                            company=company_slug.title(),
                            url=abs_url
                        ))
        except Exception as e:
            logger.error(f"GreenhouseSearch: Failed to parse job links: {e}")
            
        logger.info(f"GreenhouseSearch: Found {len(jobs_found)} direct job listings for company '{company_slug}'.")
        return jobs_found
