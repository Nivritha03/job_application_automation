import time
from loguru import logger
from engines.apply.universal_engine import UniversalApplyEngine
from core.models import Job

class GlassdoorApply(UniversalApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"GlassdoorApply: Processing application for {job.title!r} at {job.company}")
        try:
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"GlassdoorApply: Page navigation warning: {goto_err}")
                    
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("GlassdoorApply: Session expired or user not logged in.")
                job.failure_type = "LOGIN_REQUIRED"
                return False
                
            apply_btn = self.page.locator("button[data-test='easy-apply-button'], button:has-text('Easy Apply'), button.easy-apply").first
            if apply_btn.count() == 0 or not apply_btn.is_visible():
                already_applied = self.page.locator("button:has-text('Applied'), span:has-text('Applied')").count() > 0
                if already_applied:
                    logger.info("GlassdoorApply: Already applied. Skipping.")
                    return True
                logger.warning("GlassdoorApply: Apply button not found or closed.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            if dry_run:
                logger.info(f"GlassdoorApply: [DRY RUN] Would click Apply for '{job.title}'")
                return True
                
            logger.info("GlassdoorApply: Clicking Easy Apply button.")
            apply_btn.click()
            time.sleep(3)
            
            # Auto fill multi-step dialogs if they load inside an iframe/modal
            modal = self.page.locator(".modal-content, div[role='dialog']").first
            if modal.count() > 0 and modal.is_visible():
                logger.info("GlassdoorApply: Simple application dialog detected.")
                submit_modal = modal.locator("button:has-text('Submit'), button:has-text('Apply'), button:has-text('Continue')").first
                if submit_modal.count() > 0:
                    submit_modal.click()
                    time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"GlassdoorApply: Application failed: {e}")
            job.failure_type = "UNKNOWN"
            return False
