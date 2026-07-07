import time
import re
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class WorkableSearch(BaseSearchEngine):
    def search(self, company: str, query: str = "") -> List[Job]:
        company_slug = company.strip().lower()
        url = f"https://apply.workable.com/{company_slug}/"
        logger.info(f"WorkableSearch: Scraping board directly from {url}")
        
        jobs_found = []
        try:
            self.page.goto(url)
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.warning("WorkableSearch: networkidle timeout exceeded on page load — proceeding.")
            time.sleep(2.5)
            
            # Handle Workable "Show more" pagination load-more button
            for _ in range(5):  # click up to 5 times to reveal listing extensions
                try:
                    load_more = self.page.locator("button[data-ui='load-more']")
                    if load_more.count() > 0 and load_more.first.is_visible():
                        load_more.first.scroll_into_view_if_needed()
                        load_more.first.click()
                        time.sleep(1.5)
                    else:
                        break
                except Exception:
                    break
                    
            anchors = self.page.locator("a").all()
            for a in anchors:
                href = a.get_attribute("href") or ""
                # Workable job link href format looks like "/posthog/j/7E8DFA63"
                if "/j/" in href and (company_slug in href.lower() or href.startswith("/")):
                    if href.startswith("/"):
                        abs_url = f"https://apply.workable.com{href}"
                    else:
                        abs_url = href
                        
                    title = a.inner_text().strip()
                    if not title:
                        try:
                            title = a.locator("h2, h3, h4, span").first.inner_text().strip()
                        except:
                            pass
                            
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    if abs_url not in [j.url for j in jobs_found] and title:
                        job_id = abs_url.rstrip("/").split("/j/")[-1]
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company.title(),
                            url=abs_url
                        ))
        except Exception as e:
            logger.error(f"WorkableSearch: Failed to parse job links: {e}")
            
        logger.info(f"WorkableSearch: Found {len(jobs_found)} direct job listings for company '{company_slug}'.")
        return jobs_found
