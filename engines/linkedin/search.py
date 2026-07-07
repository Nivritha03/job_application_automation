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
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as goto_err:
                logger.warning(f"LinkedInSearch: Page navigation warning (proceeding): {goto_err}")
            time.sleep(2)
            
            # Check if login is required — URL redirect or visible login elements
            current_url = self.page.url.lower()
            if "login" in current_url or "signin" in current_url or "authwall" in current_url:
                logger.error("LinkedInSearch: Redirected to login page. User is not logged in.")
                return []

            if self.page.locator("input#username").count() > 0 and self.page.locator("input#username").first.is_visible():
                logger.error("LinkedInSearch: Login form detected on page. User is not logged in.")
                return []

            if self.page.locator("a.nav__button-secondary").count() > 0 and self.page.locator("a.nav__button-secondary").first.is_visible():
                logger.error("LinkedInSearch: 'Join now' nav button visible — user is not logged in.")
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
                    if abs_url.startswith("/"):
                        abs_url = f"https://www.linkedin.com{abs_url}"
                        
                    if "/jobs/view/" not in abs_url:
                        continue
                        
                    job_id = abs_url.split("/view/")[-1].strip("/")
                    
                    # Click on card to load detail pane
                    card.scroll_into_view_if_needed()
                    try:
                        card.click(timeout=5000)
                    except Exception as click_err:
                        logger.warning(f"LinkedInSearch: Failed to click card: {click_err}")
                        continue
                        
                    # Wait up to 5 seconds for details/apply button to load
                    try:
                        self.page.wait_for_selector("button.jobs-apply-button", timeout=5000)
                    except Exception:
                        pass
                        
                    # Verify if "Easy Apply" button is present and is an Easy Apply flow
                    easy_apply_btn = self.page.locator("button.jobs-apply-button").first
                    if easy_apply_btn.count() == 0 or not easy_apply_btn.is_visible():
                        logger.debug(f"LinkedInSearch: Job '{title}' has no visible apply button. Skipping.")
                        continue
                        
                    btn_text = easy_apply_btn.inner_text().strip().lower()
                    if "easy apply" not in btn_text:
                        logger.debug(f"LinkedInSearch: Job '{title}' is not an Easy Apply job (btn text: '{btn_text}'). Skipping.")
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
