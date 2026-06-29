import time
import re
import urllib.parse
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class NaukriSearch(BaseSearchEngine):
    def search(self, company: str = "", query: str = "", location: str = "India") -> List[Job]:
        search_query = query or "software engineer"
        loc = location or "India"
        
        # Format Naukri search URL
        q_encoded = urllib.parse.quote(search_query)
        l_encoded = urllib.parse.quote(loc)
        url = f"https://www.naukri.com/{q_encoded}-jobs-in-{l_encoded}"
        
        logger.info(f"NaukriSearch: Navigating to search URL: {url}")
        jobs_found = []
        
        try:
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"NaukriSearch: Page goto warning: {e}")
                
            time.sleep(3)
            
            # Selectors for job cards on Naukri list page
            card_selectors = ["article.jobTuple", "div.srp-jobtuple", "[class*='jobTuple']", "article"]
            cards = []
            for sel in card_selectors:
                found = self.page.locator(sel).all()
                if len(found) > 0:
                    cards = found
                    break
                    
            logger.info(f"NaukriSearch: Found {len(cards)} raw job cards.")
            
            for index, card in enumerate(cards[:15]):
                try:
                    # Title & Link
                    title_elem = card.locator("a.title, a.job-title, [class*='title']").first
                    if title_elem.count() == 0:
                        continue
                    title = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href") or ""
                    
                    if not title or not href:
                        continue
                        
                    # Company
                    comp_elem = card.locator("a.subTitle, [class*='company'], [class*='subTitle']").first
                    company_name = "Naukri Employer"
                    if comp_elem.count() > 0:
                        company_name = comp_elem.inner_text().strip()
                        
                    # Location
                    loc_elem = card.locator(".location, [class*='location'], [class*='loc']").first
                    job_loc = loc
                    if loc_elem.count() > 0:
                        job_loc = loc_elem.inner_text().strip()
                        
                    # URL Normalization
                    abs_url = href.split("?")[0]
                    if abs_url.startswith("/"):
                        abs_url = f"https://www.naukri.com{abs_url}"
                        
                    # Check query filter in title
                    if search_query.lower() not in title.lower():
                        continue
                        
                    job_id = abs_url.rstrip("/").split("-")[-1]
                    if not job_id.isdigit():
                        job_id = str(hash(abs_url))
                        
                    if abs_url not in [j.url for j in jobs_found]:
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company_name,
                            location=job_loc,
                            url=abs_url,
                            platform="naukri"
                        ))
                except Exception as card_err:
                    logger.debug(f"NaukriSearch: Error parsing card {index}: {card_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"NaukriSearch: Search failed: {e}")
            
        logger.info(f"NaukriSearch: Found {len(jobs_found)} matching jobs.")
        return jobs_found
