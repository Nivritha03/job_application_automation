import os
import time
import datetime
from abc import ABC
from playwright.sync_api import Page
from loguru import logger
from engines.forms.detector import FieldGroup

class UniversalApplyEngine(ABC):
    """
    Base Universal Apply Engine exposing low-level primitives:
      - fill_text(fg, value)
      - fill_select(fg, value)
      - fill_checkbox(fg, bool_val)
      - upload_file(fg, file_path)
      - submit()
      - take_screenshot(step)
    De-couples Playwright interactions from site adapter logic.
    """
    def __init__(self, page: Page):
        self.page = page

    def handle_redirect_tab(self) -> bool:
        """
        Checks if a click opened a new tab/window and switches self.page focus to it.
        """
        try:
            pages = self.page.context.pages
            if len(pages) > 1:
                new_page = pages[-1]
                if new_page != self.page:
                    logger.info(f"UniversalEngine: New tab detected (URL: {new_page.url}). Switching context focus to the new tab.")
                    self.page = new_page
                    try:
                        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    return True
        except Exception as e:
            logger.warning(f"UniversalEngine: Check for redirect tab failed: {e}")
        return False

    def fill_text(self, fg: FieldGroup, value: str):
        """Standard text input filling using sequential typing to trigger change events."""
        try:
            logger.info(f"UniversalEngine: fill_text label={fg.label_raw!r} value={value[:60]!r}")
            fg.locator.scroll_into_view_if_needed()
            fg.locator.click(timeout=3000, force=True)
            fg.locator.fill("")
            fg.locator.press_sequentially(value, delay=50)
        except Exception as e:
            logger.error(f"UniversalEngine: Failed fill_text on '{fg.label_raw}': {e}")
            raise e

    def fill_select(self, fg: FieldGroup, value: str, search_prefix: str = None) -> bool:
        """
        Handles React Select / Custom combobox dropdown selection.
        If search_prefix is provided, types that prefix to open suggestion portals.
        """
        try:
            logger.info(f"UniversalEngine: fill_select label={fg.label_raw!r} value={value[:60]!r}")
            
            # Native HTML select support
            try:
                tag_name = fg.locator.evaluate("e => e.tagName").lower()
                if tag_name == "select":
                    logger.info(f"UniversalEngine: Selecting native select option for '{fg.label_raw}'")
                    options = fg.locator.locator("option").all()
                    selected = False
                    for opt in options:
                        opt_text = opt.inner_text().strip()
                        opt_val = opt.get_attribute("value") or ""
                        if self._is_matching_option(opt_text, value) or self._is_matching_option(opt_val, value):
                            fg.locator.select_option(value=opt_val)
                            logger.info(f"UniversalEngine: Selected native select option: {opt_text} ({opt_val})")
                            selected = True
                            break
                    if not selected and len(options) > 1:
                        # Fallback select first option
                        opt_val = options[1].get_attribute("value") or ""
                        fg.locator.select_option(value=opt_val)
                    return True
            except Exception as select_err:
                logger.warning(f"UniversalEngine: Native select check failed/skipped: {select_err}")

            # Try to click the parent wrapper (e.g. .select__control or parent div) to open React Select dropdowns.
            clicked = False
            try:
                parent_wrapper = fg.locator.locator("xpath=..")
                for _ in range(4):
                    parent_class = parent_wrapper.get_attribute("class") or ""
                    if "control" in parent_class or "select__control" in parent_class:
                        break
                    parent_wrapper = parent_wrapper.locator("xpath=..")
                
                parent_wrapper.scroll_into_view_if_needed()
                parent_wrapper.click(timeout=1500, force=True)
                clicked = True
            except Exception:
                pass

            if not clicked:
                try:
                    fg.locator.scroll_into_view_if_needed()
                    fg.locator.click(timeout=3000, force=True)
                except Exception:
                    pass

            # Give dropdown transitions/animations a moment to settle
            time.sleep(0.6)

            # Determine string to search
            type_val = search_prefix if search_prefix else value
            fg.locator.fill("")
            fg.locator.press_sequentially(type_val, delay=60)
            time.sleep(1.2)  # wait for suggestions to load/render

            # Find options by selector
            opts = self.page.locator(
                "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
                "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
            ).all()

            for opt in opts:
                try:
                    opt_text = opt.inner_text()
                    if self._is_matching_option(opt_text, value):
                        opt.click(force=True)
                        logger.info(f"UniversalEngine: Clicked option matching {value!r} -> {opt_text.strip()!r}")
                        return True
                except Exception:
                    continue

            # Fallback arrow navigation
            fg.locator.press("ArrowDown")
            fg.locator.press("Enter")
            logger.warning(f"UniversalEngine: Selected option via ArrowDown + Enter fallback for '{fg.label_raw}'")
            return False
        except Exception as e:
            logger.error(f"UniversalEngine: Failed fill_select on '{fg.label_raw}': {e}")
            raise e

    def fill_checkbox(self, fg: FieldGroup, checked: bool):
        """Safely toggle checkbox state by clicking directly or targetting label if hidden."""
        try:
            logger.info(f"UniversalEngine: fill_checkbox label={fg.label_raw!r} value={checked}")
            # Try check() first
            try:
                if checked:
                    fg.locator.check(force=True)
                else:
                    fg.locator.uncheck(force=True)
            except Exception:
                # Fallback click associated label
                id_attr = fg.id_attr
                if id_attr:
                    label_loc = self.page.locator(f"label[for='{id_attr}']")
                    if label_loc.count() > 0:
                        label_loc.first.click(force=True)
                        return
                fg.locator.click(force=True)
        except Exception as e:
            logger.error(f"UniversalEngine: Failed fill_checkbox on '{fg.label_raw}': {e}")
            raise e

    def upload_file(self, fg: FieldGroup, file_path: str):
        """Uploads a file to a file input locator."""
        try:
            logger.info(f"UniversalEngine: upload_file label={fg.label_raw!r} path={file_path}")
            fg.locator.set_input_files(file_path)
            time.sleep(1.0)  # Wait for upload processing
        except Exception as e:
            logger.error(f"UniversalEngine: Failed upload_file on '{fg.label_raw}': {e}")
            raise e

    def submit(self, submit_selector: str = "button[type='submit'], input[type='submit']") -> bool:
        """Finds and clicks the submit button on the application form, handling interactive OTP code prompts if needed."""
        try:
            logger.info(f"UniversalEngine: submit using selector={submit_selector}")
            submit_btn = self.page.locator(submit_selector).first
            submit_btn.scroll_into_view_if_needed()
            submit_btn.click(timeout=5000)
            time.sleep(3.0)  # Wait for submission processing or transitions
            
            # Check and handle OTP code prompts if requested
            return self.handle_otp()
        except Exception as e:
            logger.error(f"UniversalEngine: Failed to submit form: {e}")
            return False

    def handle_otp(self) -> bool:
        """Checks if an OTP/verification code input box is visible on the page, and prompts for CLI input if interactive."""
        OTP_SELECTORS = [
            "input[name*='verification']",
            "input[name*='code']",
            "input[id*='verification']",
            "input[id*='code']",
            "input[placeholder*='code']",
            "input[placeholder*='verification']",
            "input[aria-label*='code']",
            "input[aria-label*='verification']",
        ]
        
        otp_input = None
        for selector in OTP_SELECTORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    otp_input = loc.first
                    break
            except Exception:
                pass
                
        if otp_input:
            logger.warning("UniversalEngine: Email OTP/Verification code prompt detected on page!")
            import sys
            # Display warning alert regardless of stdin type
            print("\n" + "!" * 80)
            print("  OTP REQUIRED: The job board has requested an email verification code.")
            print("  Please check the applicant email address for the code.")
            print("!" * 80 + "\n")
            
            # Direct terminal interactive input
            try:
                # Wait up to 5 minutes for manual code entry via stdin
                code = input(">>> Enter the verification code: ").strip()
                if code:
                    otp_input.fill("")
                    otp_input.fill(code)
                    time.sleep(0.5)
                    # Locate and click submit/verify
                    verify_btn = self.page.locator(
                        "button:has-text('verify'), button:has-text('submit'), "
                        "button:has-text('confirm'), input[type='submit']"
                    ).first
                    if verify_btn.count() > 0:
                        verify_btn.click(force=True)
                    else:
                        otp_input.press("Enter")
                    time.sleep(4.0)
                    logger.info("UniversalEngine: Verification code entered and submitted.")
                    return True
            except Exception as e:
                logger.error(f"UniversalEngine: Error during interactive OTP input: {e}")
                
            return False
            
        return True

    def take_screenshot(self, step: str, title: str) -> str:
        """
        Saves screenshots automatically into the structured taxonomy directory structure.
        Steps: search, job, before_fill, after_fill, before_submit, after_submit, error.
        """
        safe_title = "".join([c if c.isalnum() else "_" for c in title]).strip("_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{step}_{safe_title}_{timestamp}.png"
        
        # Taxonomy mapping to clean folders
        dir_path = os.path.abspath(os.path.join("screenshots", step))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        path = os.path.join(dir_path, filename)
        
        try:
            self.page.screenshot(path=path)
            logger.info(f"UniversalEngine: Screenshot saved under category '{step}' -> {path}")
            return path
        except Exception as e:
            logger.error(f"UniversalEngine: Failed to capture screenshot for '{step}': {e}")
            return ""

    def _is_matching_option(self, option_text: str, answer_text: str) -> bool:
        """Smart EEO and synonym matching for dropdown options."""
        opt_lower = option_text.lower()
        ans_lower = answer_text.lower()
        if ans_lower in opt_lower or opt_lower in ans_lower:
            return True
        # Smart decline EEO options matching (e.g. mapping 'Prefer not to say' to 'I don't wish to answer')
        decline_keywords = ["prefer not to", "decline to", "don't want to", "choose not to", "not disclose", "wish to answer", "don't wish"]
        is_ans_decline = any(kw in ans_lower for kw in ["prefer not to say", "prefer not to disclose", "decline", "not disclose", "don't wish to answer"])
        if is_ans_decline:
            if any(kw in opt_lower for kw in decline_keywords):
                return True
        return False
