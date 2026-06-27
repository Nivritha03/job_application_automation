from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List
from loguru import logger
import time

class FallbackSearch(BaseSearchEngine):
    def search(self, query: str = "") -> List[Job]:
        url = "https://realpython.github.io/fake-jobs/"
        logger.info(f"Navigating to fallback search: {url}")
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        jobs_found = []
        try:
            cards = self.page.locator(".card")
            for index in range(min(5, cards.count())):
                el = cards.nth(index)
                title = el.locator("h2.title").inner_text().strip()
                company = el.locator("h3.company").inner_text().strip()
                link_el = el.locator("footer .card-footer-item").nth(1)
                job_url = link_el.get_attribute("href") if link_el.count() > 0 else ""
                
                # Instantiate strongly-typed Job object directly
                job = Job(
                    title=title,
                    company=company,
                    url=job_url
                )
                jobs_found.append(job)
        except Exception as e:
            logger.warning(f"Error during search: {e}")
            
        return jobs_found
