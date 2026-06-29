import time
import urllib.parse
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class HiristSearch(BaseSearchEngine):
    def search(self, company: str = "", query: str = "", location: str = "India") -> List[Job]:
        search_query = query or "software engineer"
        
        q_encoded = urllib.parse.quote(search_query)
        url = f"https://www.hirist.com/search.html?keyword={q_encoded}"
        if location and location.lower() != "india":
            url += f"&location={urllib.parse.quote(location)}"
            
        logger.info(f"HiristSearch: Navigating to URL: {url}")
        jobs_found = []
        
        try:
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"HiristSearch: Page goto warning: {e}")
                
            time.sleep(3)
            
            # Selectors for job cards on Hirist
            card_selectors = ["div.job-box, div.job-card, .job-item, div.oportunity-box"]
            cards = []
            for sel in card_selectors:
                found = self.page.locator(sel).all()
                if len(found) > 0:
                    cards = found
                    break
                    
            logger.info(f"HiristSearch: Found {len(cards)} raw job cards.")
            
            for index, card in enumerate(cards[:15]):
                try:
                    title_elem = card.locator("a.job-title, a[class*='title'], h2 a, a").first
                    if title_elem.count() == 0:
                        continue
                        
                    title = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href") or ""
                    
                    if not title or not href:
                        continue
                        
                    # Company
                    comp_elem = card.locator(".company-name, [class*='company'], .recruiter-name").first
                    company_name = "Hirist Employer"
                    if comp_elem.count() > 0:
                        company_name = comp_elem.inner_text().strip()
                        
                    # Location
                    loc_elem = card.locator(".location, [class*='location'], span.loc").first
                    job_loc = location
                    if loc_elem.count() > 0:
                        job_loc = loc_elem.inner_text().strip()
                        
                    abs_url = href.split("?")[0]
                    if abs_url.startswith("/"):
                        abs_url = f"https://www.hirist.com{abs_url}"
                        
                    if search_query.lower() not in title.lower():
                        continue
                        
                    job_id = abs_url.rstrip("/").split("/")[-1].split(".")[0]
                    if not job_id.replace("-", "").isdigit():
                        job_id = str(hash(abs_url))
                        
                    if abs_url not in [j.url for j in jobs_found]:
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company_name,
                            location=job_loc,
                            url=abs_url,
                            platform="hirist"
                        ))
                except Exception as card_err:
                    logger.debug(f"HiristSearch: Error parsing card {index}: {card_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"HiristSearch: Search failed: {e}")
            
        logger.info(f"HiristSearch: Found {len(jobs_found)} matching jobs.")
        return jobs_found
