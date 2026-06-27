from abc import ABC, abstractmethod
from typing import List
from core.models import Job
from playwright.sync_api import Page

class BaseSearchEngine(ABC):
    def __init__(self, page: Page):
        self.page = page
        
    @abstractmethod
    def search(self, query: str) -> List[Job]:
        """Discovers jobs on the platform and returns a list of Job objects with basic metadata."""
        pass

class BaseJobParser(ABC):
    def __init__(self, page: Page):
        self.page = page
        
    @abstractmethod
    def extract_details(self, job: Job) -> Job:
        """Navigates to the job URL and extracts description, skills, experience, etc."""
        pass

class BaseApplyEngine(ABC):
    def __init__(self, page: Page):
        self.page = page
        
    @abstractmethod
    def apply(self, job: Job) -> bool:
        """Attempts to apply for the job and returns True if successful."""
        pass
