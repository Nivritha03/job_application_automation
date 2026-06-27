from engines.apply.base import BaseApplyEngine
from core.models import Job
from loguru import logger

class LinkedInApply(BaseApplyEngine):
    def apply(self, job: Job, dry_run: bool = False, *args, **kwargs) -> bool:
        logger.warning("LinkedInApply: LinkedIn Apply is not yet supported. Postponed in architecture.")
        raise NotImplementedError("LinkedIn Easy Apply integration is postponed.")
