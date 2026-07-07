import time
import urllib.parse
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class InstahyreSearch(BaseSearchEngine):
    def search(self, company: str = "", query: str = "", location: str = "India") -> List[Job]:
        search_query = query or "software engineer"
        
        # Build search page URL
        q_encoded = urllib.parse.quote(search_query)
        url = f"https://www.instahyre.com/jobs-search/?keyword={q_encoded}"
        if location and location.lower() != "india":
            url += f"&location={urllib.parse.quote(location)}"
            
        logger.info(f"InstahyreSearch: Navigating to search URL: {url}")
        jobs_found = []
        
        try:
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                logger.warning(f"InstahyreSearch: Page goto warning: {e}")
                
            time.sleep(3)

            # Check if login is required
            current_url = self.page.url.lower()
            if "login" in current_url or "signin" in current_url:
                logger.error("InstahyreSearch: Redirected to login page. User is not logged in.")
                return []

            # Check for visible login link or button in nav
            nav_login = self.page.locator("nav a[href*='/login'], header a[href*='/login']")
            if nav_login.count() > 0 and nav_login.first.is_visible():
                logger.error("InstahyreSearch: Login link visible in nav. User is not logged in.")
                return []


            card_selectors = ["div.job-opportunity, div.opportunity-card, div.employer-block, div.job-card"]
            cards = []
            for sel in card_selectors:
                found = self.page.locator(sel).all()
                if len(found) > 0:
                    cards = found
                    break
                    
            logger.info(f"InstahyreSearch: Found {len(cards)} raw job cards.")
            
            for index, card in enumerate(cards[:15]):
                try:
                    title_elem = card.locator("a.job-title, [class*='job-title'], h2 a, a").first
                    if title_elem.count() == 0:
                        continue
                        
                    title = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href") or ""
                    
                    if not title or not href:
                        continue
                        
                    # Company
                    comp_elem = card.locator(".company-name, [class*='company-name'], h3").first
                    company_name = "Instahyre Employer"
                    if comp_elem.count() > 0:
                        company_name = comp_elem.inner_text().strip()
                        
                    # Location
                    loc_elem = card.locator(".job-location, [class*='location'], span.loc").first
                    job_loc = location
                    if loc_elem.count() > 0:
                        job_loc = loc_elem.inner_text().strip()
                        
                    # URL Normalization
                    abs_url = href.split("?")[0]
                    if abs_url.startswith("/"):
                        abs_url = f"https://www.instahyre.com{abs_url}"
                        
                    # Check query filter in title
                    if search_query.lower() not in title.lower():
                        continue
                        
                    job_id = abs_url.rstrip("/").split("/")[-1]
                    if not job_id.isdigit():
                        job_id = str(hash(abs_url))
                        
                    if abs_url not in [j.url for j in jobs_found]:
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company_name,
                            location=job_loc,
                            url=abs_url,
                            platform="instahyre"
                        ))
                except Exception as card_err:
                    logger.debug(f"InstahyreSearch: Error parsing card {index}: {card_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"InstahyreSearch: Search failed: {e}")
            
        logger.info(f"InstahyreSearch: Found {len(jobs_found)} matching jobs.")
        return jobs_found
