from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List
from loguru import logger
import time
import re

class LeverSearch(BaseSearchEngine):
    def search(self, company: str, query: str = "") -> List[Job]:
        company_slug = company if company else "entrata"
        url = f"https://jobs.lever.co/{company_slug}"
        logger.info(f"LeverSearch: Scraping board directly from {url}")
        
        jobs_found = []
        try:
            self.page.goto(url)
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.warning("LeverSearch: networkidle timeout exceeded on page load — proceeding.")
            time.sleep(2)
            
            # Find all anchor tags on the page
            anchors = self.page.locator("a").all()
            for a in anchors:
                href = a.get_attribute("href") or ""
                if f"jobs.lever.co/{company_slug}/" in href:
                    abs_url = href.split("?")[0]
                    job_id = abs_url.split(f"jobs.lever.co/{company_slug}/")[-1]
                    title = a.inner_text().strip()
                    
                    # Avoid duplicates of same URL and ignore "apply" link text
                    if abs_url not in [j.url for j in jobs_found] and title and title.lower() != "apply":
                        # Clean title by removing standard headers
                        clean_title = re.sub(r'\b(Apply|Hybrid|On-Site|Remote|Full-Time)\b', '', title, flags=re.IGNORECASE).strip()
                        jobs_found.append(Job(
                            id=job_id,
                            title=clean_title or "Developer",
                            company=company_slug.title(),
                            url=abs_url
                        ))
        except Exception as e:
            logger.error(f"LeverSearch: Failed to parse job links: {e}")
            
        logger.info(f"LeverSearch: Found {len(jobs_found)} direct job listings for company '{company_slug}'.")
        return jobs_found
