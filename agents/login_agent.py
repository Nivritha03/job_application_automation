from loguru import logger
from playwright.sync_api import Page
import time

class LoginAgent:
    def __init__(self, page: Page):
        self.page = page

    def verify_login(self, start_url: str = "https://redrob.ai/") -> bool:
        logger.info(f"Opening {start_url}")
        self.page.goto(start_url)
        
        # We wait a moment for redirects
        time.sleep(3)
        
        logger.info(f"Current URL is: {self.page.url}")
        
        # Check if we are on a login page, or ask user to verify
        print("\n" + "="*50)
        print("PHASE 1: LOGIN VERIFICATION")
        print("Please look at the Chrome window.")
        print("If you are NOT logged in, please log in manually now.")
        print("Once you are fully logged in and on the dashboard/homepage,")
        input("PRESS ENTER TO CONTINUE...")
        print("="*50 + "\n")
        
        logger.info("Login verified by user. Saving session state.")
        return True
