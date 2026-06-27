from engines.apply.base import BaseApplyEngine
from core.models import Job
from loguru import logger


class UniversalApply(BaseApplyEngine):
    """
    Fallback apply engine for boards without a dedicated adapter.
    Assumes the current page IS the application form (no navigation needed).
    """

    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"UniversalApply: Starting for {job.title!r} at {job.company}")
        try:
            return self._run_form_pipeline(job, dry_run=dry_run, screenshot_cb=screenshot_cb)
        except Exception as e:
            logger.error(f"UniversalApply: Exception — {e}")
            return False
