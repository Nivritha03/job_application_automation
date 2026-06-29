import os
from playwright.sync_api import sync_playwright, Playwright, BrowserContext
from loguru import logger

class PlaywrightManager:
    def __init__(self, user_data_dir: str = "./browser_data", headless: bool = False):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    def start(self) -> BrowserContext:
        if not os.path.exists(self.user_data_dir):
            os.makedirs(self.user_data_dir)
            
        logger.info(f"Starting Playwright with persistent context at {self.user_data_dir} (headless={self.headless})")
        self._playwright = sync_playwright().start()
        
        # Persistent context to keep login sessions active.
        # headless=False ensures we can see it during Phase 1
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport={"width": 1280, "height": 720},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ] 
        )
        return self._context

    def stop(self):
        if self._context:
            logger.info("Closing Playwright context")
            self._context.close()
        if self._playwright:
            self._playwright.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
