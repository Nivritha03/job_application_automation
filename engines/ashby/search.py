import time
import re
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class AshbySearch(BaseSearchEngine):
    def search(self, company: str, query: str = "") -> List[Job]:
        company_slug = company.strip().lower()
        url = f"https://jobs.ashbyhq.com/{company_slug}"
        logger.info(f"AshbySearch: Scraping board directly from {url}")
        
        jobs_found = []
        try:
            self.page.goto(url)
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.warning("AshbySearch: networkidle timeout exceeded on page load — proceeding.")
            time.sleep(2.5)
            
            # Auto scroll to trigger any lazy loading
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            anchors = self.page.locator("a").all()
            for a in anchors:
                href = a.get_attribute("href") or ""
                # Ashby URLs usually look like "/company_slug/job-id" or "https://jobs.ashbyhq.com/company_slug/job-id"
                if company_slug in href.lower() and len(href.strip("/").split("/")) >= 2:
                    if href.startswith("/"):
                        abs_url = f"https://jobs.ashbyhq.com{href}"
                    else:
                        abs_url = href
                        
                    # Filter out non-job URLs
                    if any(x in abs_url.lower() for x in ["/terms", "/privacy", "/cookies", "/about", "ashbyhq.com/careers"]):
                        continue
                        
                    title = a.inner_text().strip()
                    if not title:
                        try:
                            title = a.locator("h1, h2, h3, h4, h5, span").first.inner_text().strip()
                        except:
                            pass
                            
                    # Clean title
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    if abs_url not in [j.url for j in jobs_found] and title:
                        job_id = abs_url.rstrip("/").split("/")[-1]
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company.title(),
                            url=abs_url
                        ))
        except Exception as e:
            logger.error(f"AshbySearch: Failed to parse job links: {e}")
            
        logger.info(f"AshbySearch: Found {len(jobs_found)} direct job listings for company '{company_slug}'.")
        return jobs_found
