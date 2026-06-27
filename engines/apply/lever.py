from engines.apply.base import BaseApplyEngine
from core.models import Job
from loguru import logger
import time


class LeverApply(BaseApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"LeverApply: Starting for {job.title!r} at {job.company}")
        try:
            # ── Step 1: Navigate to the application form ──────────────────────
            # Lever listing:  https://jobs.lever.co/{company}/{uuid}
            # Apply form:     https://jobs.lever.co/{company}/{uuid}/apply
            apply_url = self._resolve_apply_url(job)
            logger.info(f"LeverApply: Navigating to apply form: {apply_url}")
            self.page.goto(apply_url)

            # Wait for form fields to appear — NOT networkidle
            try:
                self.page.wait_for_selector(
                    "input[type='file'], input[name='name'], input[type='email'], form",
                    timeout=12000
                )
            except Exception:
                logger.warning("LeverApply: Timed out waiting for form selector — continuing.")
            time.sleep(1)

            # ── Step 2: Run shared form pipeline ─────────────────────────────
            return self._run_form_pipeline(job, dry_run=dry_run, screenshot_cb=screenshot_cb)

        except Exception as e:
            logger.error(f"LeverApply: Exception — {e}")
            return False

    def _resolve_apply_url(self, job: Job) -> str:
        """
        Derive the application form URL from the Lever listing URL.

        Lever listing:  https://jobs.lever.co/{company}/{uuid}
        Apply form:     https://jobs.lever.co/{company}/{uuid}/apply
        """
        url = job.url.rstrip("/")
        # If already on the apply page, use as-is
        if url.endswith("/apply"):
            return url
        return f"{url}/apply"
