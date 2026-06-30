import time
from loguru import logger
from core.base_engine import UniversalApplyEngine
from core.models import Job
from engines.instahyre.selectors import (
    APPLY_BTN, ALREADY_APPLIED, MODAL, SUBMIT_MODAL, EXTERNAL_APPLY_BTN
)

class InstahyreApply(UniversalApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"InstahyreApply: Processing application for {job.title!r} at {job.company}")
        try:
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"InstahyreApply: Page navigation warning: {goto_err}")
                    
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("InstahyreApply: Session expired or user not logged in.")
                job.failure_type = "LOGIN_REQUIRED"
                return False
                
            apply_btn = self.page.locator(APPLY_BTN).first
            if apply_btn.count() == 0 or not apply_btn.is_visible():
                # Check for external apply button / link
                external_btn = self.page.locator(EXTERNAL_APPLY_BTN).first
                if external_btn.count() > 0 and external_btn.is_visible():
                    logger.info("InstahyreApply: External apply detected. Setting status to external_redirect.")
                    job.status = "external_redirect"
                    job.failure_type = "external_redirect"
                    return False
                    
                already_applied = self.page.locator(ALREADY_APPLIED).count() > 0
                if already_applied:
                    logger.info("InstahyreApply: Already applied. Skipping.")
                    return True
                logger.warning("InstahyreApply: Apply button not found or closed.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            if dry_run:
                logger.info(f"InstahyreApply: [DRY RUN] Would click Apply for '{job.title}'")
                return True
                
            logger.info("InstahyreApply: Clicking Apply button.")
            apply_btn.click()
            time.sleep(3)
            
            # Check for questionnaire / multi-step popups
            modal = self.page.locator(MODAL).first
            if modal.count() > 0 and modal.is_visible():
                logger.info("InstahyreApply: Recruiter questionnaire detected inside modal.")
                submit_modal = modal.locator(SUBMIT_MODAL).first
                if submit_modal.count() > 0:
                    submit_modal.click()
                    time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"InstahyreApply: Application failed: {e}")
            job.failure_type = "UNKNOWN"
            return False
