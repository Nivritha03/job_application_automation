from engines.apply.base import BaseApplyEngine
from core.models import Job
from loguru import logger
import time


class GreenhouseApply(BaseApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"GreenhouseApply: Starting for {job.title!r} at {job.company}")
        try:
            # ── Step 1: Navigate to the correct apply URL ─────────────────────
            apply_url = self._resolve_apply_url(job)
            logger.info(f"GreenhouseApply: Navigating to: {apply_url}")

            # Only navigate if we're not already there
            if self.page.url.rstrip("/") != apply_url.rstrip("/"):
                self.page.goto(apply_url)

            # ── Step 2: Wait for real form fields ────────────────────────────
            # job-boards.greenhouse.io embeds form on the listing page.
            # Wait for an input or file upload to appear — NOT networkidle.
            try:
                self.page.wait_for_selector(
                    "input[type='text'], input[type='email'], input[type='file'], "
                    "form#application_form, form",
                    timeout=15000
                )
            except Exception:
                logger.warning("GreenhouseApply: Timed out waiting for form fields — continuing.")
            time.sleep(1)

            # ── Step 3: Run shared form pipeline ─────────────────────────────
            return self._run_form_pipeline(job, dry_run=dry_run, screenshot_cb=screenshot_cb)

        except Exception as e:
            logger.error(f"GreenhouseApply: Exception — {e}")
            return False

    def _resolve_apply_url(self, job: Job) -> str:
        """
        Two different Greenhouse board URL formats:

        NEW boards (job-boards.greenhouse.io):
            Listing:  https://job-boards.greenhouse.io/{company}/jobs/{id}
            Form:     SAME URL — the application form is embedded on the listing page.

        OLD boards (boards.greenhouse.io):
            Listing:  https://boards.greenhouse.io/{company}/jobs/{id}
            Form:     https://boards.greenhouse.io/{company}/jobs/{id}/applications/new
        """
        url = job.url.rstrip("/")

        # Already on a form page
        if "/applications/new" in url or "/apply" in url:
            return url

        # NEW board: job-boards.greenhouse.io — form is embedded, use listing URL
        if "job-boards.greenhouse.io" in url:
            return url

        # OLD board: boards.greenhouse.io — form is at /applications/new
        if "boards.greenhouse.io" in url:
            return f"{url}/applications/new"

        # Fallback: return as-is
        return url
