import time
import urllib.parse
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class GlassdoorSearch(BaseSearchEngine):
    def search(self, company: str = "", query: str = "", location: str = "India") -> List[Job]:
        search_query = query or "software engineer"
        
        q_encoded = urllib.parse.quote(search_query)
        url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={q_encoded}"
        if location:
            url += f"&locT=C&locId={urllib.parse.quote(location)}"
            
        logger.info(f"GlassdoorSearch: Navigating to URL: {url}")
        jobs_found = []
        
        try:
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"GlassdoorSearch: Page goto warning: {e}")
                
            time.sleep(3)
            
            # Selectors for job listing items on Glassdoor
            card_selectors = ["li[class*='JobCard']", "li.react-job-listing", "article.job-card", "li[data-id]"]
            cards = []
            for sel in card_selectors:
                found = self.page.locator(sel).all()
                if len(found) > 0:
                    cards = found
                    break
                    
            logger.info(f"GlassdoorSearch: Found {len(cards)} raw job cards.")
            
            for index, card in enumerate(cards[:15]):
                try:
                    title_elem = card.locator("a[data-test='job-link'], a.job-title, [class*='jobTitle'], a").first
                    if title_elem.count() == 0:
                        continue
                        
                    title = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href") or ""
                    
                    if not title or not href:
                        continue
                        
                    # Filter: Easy Apply Direct only
                    easy_apply_badge = card.locator("span[data-test='easy-apply'], span:has-text('Easy Apply'), [class*='easyApply']").count() > 0
                    if not easy_apply_badge:
                        logger.debug(f"GlassdoorSearch: Job '{title}' is not an Easy Apply job. Skipping.")
                        continue
                        
                    # Company
                    comp_elem = card.locator("[class*='employerName'], [class*='companyName'], [data-test='employer-name']").first
                    company_name = "Glassdoor Employer"
                    if comp_elem.count() > 0:
                        company_name = comp_elem.inner_text().strip()
                        
                    # Location
                    loc_elem = card.locator("[data-test='job-location'], [class*='location']").first
                    job_loc = location
                    if loc_elem.count() > 0:
                        job_loc = loc_elem.inner_text().strip()
                        
                    abs_url = href.split("?")[0]
                    if abs_url.startswith("/"):
                        abs_url = f"https://www.glassdoor.co.in{abs_url}"
                        
                    if search_query.lower() not in title.lower():
                        continue
                        
                    job_id = abs_url.rstrip("/").split("/")[-1].split(".")[0].split("_")[-1]
                    if not job_id.isdigit():
                        job_id = str(hash(abs_url))
                        
                    if abs_url not in [j.url for j in jobs_found]:
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company_name,
                            location=job_loc,
                            url=abs_url,
                            platform="glassdoor"
                        ))
                except Exception as card_err:
                    logger.debug(f"GlassdoorSearch: Error parsing card {index}: {card_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"GlassdoorSearch: Search failed: {e}")
            
        logger.info(f"GlassdoorSearch: Found {len(jobs_found)} matching jobs.")
        return jobs_found
