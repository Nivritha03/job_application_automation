import time
from loguru import logger
from engines.apply.universal_engine import UniversalApplyEngine
from core.models import Job

class IndeedApply(UniversalApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"IndeedApply: Processing application for {job.title!r} at {job.company}")
        try:
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"IndeedApply: Page navigation warning: {goto_err}")
                    
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("IndeedApply: Session expired or user not logged in.")
                job.failure_type = "LOGIN_REQUIRED"
                return False
                
            apply_btn = self.page.locator(".jobsearch-IndeedApplyButton-button, button:has-text('Indeed Apply'), #indeedApplyButton").first
            if apply_btn.count() == 0 or not apply_btn.is_visible():
                already_applied = self.page.locator("button:has-text('Applied'), span:has-text('Applied')").count() > 0
                if already_applied:
                    logger.info("IndeedApply: Already applied. Skipping.")
                    return True
                logger.warning("IndeedApply: Apply button not found or closed.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            if dry_run:
                logger.info(f"IndeedApply: [DRY RUN] Would click Apply for '{job.title}'")
                return True
                
            logger.info("IndeedApply: Clicking Indeed Apply button.")
            apply_btn.click()
            time.sleep(3)
            
            # Check for iframe or modal popup dialogs
            modal = self.page.locator("div.ia-Dialog, div.ia-Modal, div[role='dialog']").first
            if modal.count() > 0 and modal.is_visible():
                logger.info("IndeedApply: Quick apply modal detected. Completing steps...")
                # Loop through next / continue steps
                step_count = 1
                while step_count <= 6:
                    next_btn = modal.locator("button:has-text('Continue'), button:has-text('Next')").first
                    submit_btn = modal.locator("button:has-text('Submit'), button:has-text('Apply')").first
                    
                    if submit_btn.count() > 0 and submit_btn.is_visible():
                        submit_btn.click()
                        time.sleep(3)
                        break
                    elif next_btn.count() > 0 and next_btn.is_visible():
                        next_btn.click()
                        time.sleep(2)
                        step_count += 1
                    else:
                        break
                        
            return True
            
        except Exception as e:
            logger.error(f"IndeedApply: Application failed: {e}")
            job.failure_type = "UNKNOWN"
            return False
