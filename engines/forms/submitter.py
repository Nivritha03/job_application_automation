from playwright.sync_api import Page
from loguru import logger
import time


# URL fragments that signal a successful submission redirect
SUCCESS_URL_FRAGMENTS = [
    "confirmation", "thank-you", "thank_you", "thankyou",
    "success", "submitted", "complete", "done", "applied",
]

# Text patterns that appear on confirmation pages/messages
SUCCESS_TEXT_PATTERNS = [
    "application submitted",
    "thank you for applying",
    "thank you for your interest",
    "successfully submitted",
    "we've received your application",
    "your application has been received",
    "application received",
    "we received your application",
    "submitted successfully",
]


class FormSubmitter:
    def __init__(self, page: Page):
        self.page = page

    def submit(self, dry_run: bool = False) -> bool:
        """
        Locate and click the submit button, then detect success.
        In dry_run mode: locates the button, takes note, but does NOT click.
        Returns True if submitted (or would have submitted in dry_run).
        """
        submit_button = self._find_submit_button()

        if submit_button is None:
            logger.warning("FormSubmitter: Submit button not found or not visible.")
            return False

        if dry_run:
            logger.info("[DRY RUN] FormSubmitter: Submit button located — skipping click.")
            return True

        # ── Real submission ────────────────────────────────────────────────────
        url_before = self.page.url
        try:
            logger.info("FormSubmitter: Clicking submit button...")
            submit_button.click()
        except Exception as e:
            logger.error(f"FormSubmitter: Click failed: {e}")
            return False

        # Wait briefly for the page to react
        time.sleep(3)

        return self._detect_success(url_before)

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _find_submit_button(self):
        """
        Try multiple selector strategies to locate the submit button.
        Returns the first visible, enabled locator found, or None.
        """
        strategies = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
            "button:has-text('Apply Now')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "a:has-text('Submit Application')",
        ]
        for selector in strategies:
            try:
                loc = self.page.locator(selector).first
                if loc.count() > 0 and loc.is_visible() and loc.is_enabled():
                    logger.debug(f"FormSubmitter: Found submit via selector {selector!r}")
                    return loc
            except Exception:
                continue
        return None

    def _detect_success(self, url_before: str) -> bool:
        """
        After clicking submit, check for:
          1. URL change containing success fragments
          2. Confirmation text appearing on page
          3. Form disappearing
        """
        url_after = self.page.url

        # 1. URL change
        if url_after != url_before:
            url_lower = url_after.lower()
            for fragment in SUCCESS_URL_FRAGMENTS:
                if fragment in url_lower:
                    logger.info(f"FormSubmitter: ✓ Success detected via URL → {url_after}")
                    return True

        # 2. Confirmation text on page
        try:
            body_text = self.page.locator("body").inner_text().lower()
            for pattern in SUCCESS_TEXT_PATTERNS:
                if pattern in body_text:
                    logger.info(f"FormSubmitter: ✓ Success detected via page text: {pattern!r}")
                    return True
        except Exception:
            pass

        # 3. Form disappeared (a proxy for successful submission)
        try:
            form_count = self.page.locator("form").count()
            if form_count == 0:
                logger.info("FormSubmitter: ✓ Form no longer present — likely submitted.")
                return True
        except Exception:
            pass

        # Fallback: URL changed at all (some boards redirect without clear signals)
        if url_after != url_before:
            logger.info(
                f"FormSubmitter: ⚠ URL changed but no confirmation text found. "
                f"Marking as likely success. URL={url_after}"
            )
            return True

        logger.warning("FormSubmitter: Could not confirm submission success.")
        return False
