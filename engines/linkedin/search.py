import time
from loguru import logger
from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List

class LinkedInSearch(BaseSearchEngine):
    def search(self, company: str = "", query: str = "", location: str = "India") -> List[Job]:
        # LinkedIn Easy Apply search URL (f_LF=f_AL is Easy Apply filter)
        search_term = query or "software engineer"
        url = f"https://www.linkedin.com/jobs/search/?keywords={search_term}&f_LF=f_AL"
        if location:
            url += f"&location={location}"
        if company and company.lower() != "easyapply":
            url += f"&keywords={company}%20{search_term}"
            
        logger.info(f"LinkedInSearch: Navigating to job search url: {url}")
        
        jobs_found = []
        try:
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(3.5)
            
            # Check if login is required
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("LinkedInSearch: Authentication required. User is not logged into persistent profile.")
                return []
                
            # Scroll job listings list to load all items
            try:
                listings_pane = self.page.locator(".jobs-search-results-list")
                if listings_pane.count() > 0:
                    listings_pane.first.evaluate("el => el.scrollTop = el.scrollHeight")
                    time.sleep(1.5)
            except Exception:
                pass
                
            # Find job cards
            cards = self.page.locator("a.job-card-list__title, a.job-card-container__link").all()
            logger.info(f"LinkedInSearch: Found {len(cards)} raw job links on search page.")
            
            for index, card in enumerate(cards):
                try:
                    title = card.inner_text().strip()
                    href = card.get_attribute("href") or ""
                    
                    if not title or not href:
                        continue
                        
                    # Normalize URL to prevent query duplicates
                    abs_url = href.split("?")[0]
                    if "/jobs/view/" not in abs_url:
                        continue
                        
                    job_id = abs_url.split("/view/")[-1].strip("/")
                    
                    # Click on card to load detail pane
                    card.scroll_into_view_if_needed()
                    card.click()
                    time.sleep(1.5)
                    
                    # Verify if "Easy Apply" button is present on detail pane
                    easy_apply_btn = self.page.locator("button.jobs-apply-button")
                    if easy_apply_btn.count() == 0 or not easy_apply_btn.first.is_visible():
                        logger.debug(f"LinkedInSearch: Job '{title}' is not an Easy Apply job. Skipping.")
                        continue
                        
                    # Extract company name from active detail pane
                    company_name = "LinkedIn Company"
                    try:
                        company_loc = self.page.locator(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name").first
                        if company_loc.count() > 0:
                            company_name = company_loc.inner_text().strip()
                    except:
                        pass
                        
                    if abs_url not in [j.url for j in jobs_found]:
                        jobs_found.append(Job(
                            id=job_id,
                            title=title,
                            company=company_name,
                            url=abs_url
                        ))
                        
                except Exception as card_err:
                    logger.debug(f"LinkedInSearch: Error checking card {index}: {card_err}")
                    continue
                    
        except Exception as e:
            logger.error(f"LinkedInSearch: Failed to execute search: {e}")
            
        logger.info(f"LinkedInSearch: Found {len(jobs_found)} Easy Apply job listings.")
        return jobs_found
