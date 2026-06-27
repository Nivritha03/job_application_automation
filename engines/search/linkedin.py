from core.interfaces import BaseSearchEngine
from core.models import Job
from typing import List
from loguru import logger

class LinkedInSearch(BaseSearchEngine):
    def search(self, query: str = "") -> List[Job]:
        logger.warning("LinkedInSearch: LinkedIn search is not yet supported. Postponed in architecture.")
        raise NotImplementedError("LinkedIn search integration is postponed.")
