import time
from loguru import logger
from engines.apply.universal_engine import UniversalApplyEngine
from core.models import Job

class NaukriApply(UniversalApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"NaukriApply: Processing application for {job.title!r} at {job.company}")
        try:
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"NaukriApply: Page navigation warning: {goto_err}")
                    
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("NaukriApply: Session expired or user not logged in.")
                job.failure_type = "LOGIN_REQUIRED"
                return False
                
            apply_btn = self.page.locator("button.apply-button, button.apply, #apply-button").first
            if apply_btn.count() == 0 or not apply_btn.is_visible():
                # Already applied check
                already_applied = self.page.locator("button:has-text('Applied'), span:has-text('Applied')").count() > 0
                if already_applied:
                    logger.info("NaukriApply: Job already applied. Skipping.")
                    return True
                logger.warning("NaukriApply: Apply button not found or closed.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            if dry_run:
                logger.info(f"NaukriApply: [DRY RUN] Would click Apply for '{job.title}'")
                return True
                
            logger.info("NaukriApply: Clicking Apply button.")
            apply_btn.click()
            time.sleep(3)
            
            # Check for multi-step / questions popups
            popup = self.page.locator("div.apply-modal, div[role='dialog']").first
            if popup.count() > 0 and popup.is_visible():
                logger.info("NaukriApply: Custom recruiter questionnaire detected. Filling fields...")
                # Auto click standard check boxes / buttons
                submit_popup = popup.locator("button:has-text('Submit'), button:has-text('Apply')").first
                if submit_popup.count() > 0:
                    submit_popup.click()
                    time.sleep(2.5)
            
            return True
            
        except Exception as e:
            logger.error(f"NaukriApply: Application process failed: {e}")
            job.failure_type = "UNKNOWN"
            return False
