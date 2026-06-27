from playwright.sync_api import Page
from loguru import logger
import time

class ApplyAgent:
    def __init__(self, page: Page):
        self.page = page

    def apply_to_job(self) -> bool:
        """Simulate applying to the currently open job page."""
        try:
            logger.info("Attempting to apply...")
            
            # Since this is a fake job board, there is no real form.
            # However, we will look for an 'Apply' button to simulate interaction.
            # Playwright handles clicking if it finds the button.
            apply_button = self.page.locator("a:has-text('Apply'), button:has-text('Apply')").first
            
            if apply_button.is_visible():
                # We won't actually click it if it navigates away from the fake site, 
                # but we'll mock the form fill for validation.
                logger.info("Located Apply button!")
                time.sleep(1)
                
                logger.info("Mocking form filling (Name, Email, Resume Upload)...")
                time.sleep(2) # Simulate typing and uploading
                
                logger.info("Application successfully submitted (Mock)!")
                return True
            else:
                logger.warning("No Apply button found on this page. Manual apply required.")
                return False
                
        except Exception as e:
            logger.error(f"Failed to apply: {e}")
            return False
