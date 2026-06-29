import time
from loguru import logger
from engines.apply.universal_engine import UniversalApplyEngine
from core.models import Job

class HiristApply(UniversalApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"HiristApply: Processing application for {job.title!r} at {job.company}")
        try:
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"HiristApply: Page navigation warning: {goto_err}")
                    
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("HiristApply: Session expired or user not logged in.")
                job.failure_type = "LOGIN_REQUIRED"
                return False
                
            apply_btn = self.page.locator("button.apply-btn, button.apply, button:has-text('Apply')").first
            if apply_btn.count() == 0 or not apply_btn.is_visible():
                already_applied = self.page.locator("button:has-text('Applied'), span:has-text('Applied')").count() > 0
                if already_applied:
                    logger.info("HiristApply: Already applied. Skipping.")
                    return True
                logger.warning("HiristApply: Apply button not found or closed.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            if dry_run:
                logger.info(f"HiristApply: [DRY RUN] Would click Apply for '{job.title}'")
                return True
                
            logger.info("HiristApply: Clicking Apply button.")
            apply_btn.click()
            time.sleep(3)
            
            # Check for questionnaire popups
            modal = self.page.locator(".modal-dialog, div[role='dialog']").first
            if modal.count() > 0 and modal.is_visible():
                logger.info("HiristApply: Custom question popup detected inside modal.")
                submit_modal = modal.locator("button:has-text('Submit'), button:has-text('Apply')").first
                if submit_modal.count() > 0:
                    submit_modal.click()
                    time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"HiristApply: Application failed: {e}")
            job.failure_type = "UNKNOWN"
            return False
