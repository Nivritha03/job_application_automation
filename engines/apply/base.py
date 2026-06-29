from abc import ABC, abstractmethod
from playwright.sync_api import Page
from core.models import Job
from engines.forms.detector import FormDetector
from engines.forms.mapper import FormMapper
from engines.forms.filler import FormFiller
from engines.forms.submitter import FormSubmitter
from engines.apply.universal_engine import UniversalApplyEngine


class BaseApplyEngine(UniversalApplyEngine):
    def __init__(self, page: Page):
        super().__init__(page)
        self.detector = FormDetector(page)
        self.mapper = FormMapper()
        self.filler = FormFiller(page)
        self.submitter = FormSubmitter(page)

    def _run_form_pipeline(self, job: Job, dry_run: bool, screenshot_cb=None) -> bool:
        """
        Shared form-filling pipeline used by all site adapters.
        Steps: Detect → Map → Screenshot → Fill → Screenshot → Submit
        """
        # 1. Detect
        field_groups = self.detector.find_fields()

        # 2. Map
        profile_fields, questions = self.mapper.map_fields(field_groups)
        from loguru import logger
        logger.info(
            f"Apply: profile_fields={list(profile_fields.keys())}  "
            f"questions={list(questions.keys())[:5]}"
        )

        # 3. Before-fill screenshot
        if screenshot_cb:
            screenshot_cb("before_fill")

        # 4. Fill
        self.filler.fill(profile_fields, questions, job.resume_used, engine=self)

        # 5. After-fill + before-submit screenshots
        if screenshot_cb:
            screenshot_cb("after_fill")

        # 6. Auto-check required consent / GDPR checkboxes
        self._auto_check_consent()

        # 7. Before-submit screenshot
        if screenshot_cb:
            screenshot_cb("before_submit")

        # 8. Submit
        return self.submitter.submit(dry_run=dry_run)

    def _auto_check_consent(self):
        """
        Auto-check any required consent/GDPR checkboxes.
        Custom checkboxes are often CSS-hidden (is_visible() returns False);
        we attempt check() directly and fall back to clicking the label.
        """
        from loguru import logger
        CONSENT_SELECTORS = [
            "input[type='checkbox'][name*='gdpr']",
            "input[type='checkbox'][name*='consent']",
            "input[type='checkbox'][id*='gdpr']",
            "input[type='checkbox'][id*='consent']",
            "input[type='checkbox'][name*='privacy']",
            "input[type='checkbox'][id*='privacy']",
        ]
        checked = 0
        for selector in CONSENT_SELECTORS:
            try:
                boxes = self.page.locator(selector).all()
                for box in boxes:
                    try:
                        if box.is_checked():
                            continue  # already checked
                    except Exception:
                        pass
                    try:
                        box.check(force=True)  # force=True bypasses visibility
                        checked += 1
                        logger.info(f"BaseApply: Auto-checked consent checkbox [{selector}]")
                    except Exception:
                        # Fallback: click the associated <label> element
                        try:
                            box_id = box.get_attribute("id")
                            if box_id:
                                label = self.page.locator(f"label[for='{box_id}']")
                                label.click(force=True)
                                checked += 1
                                logger.info(f"BaseApply: Clicked consent label [for='{box_id}']")
                        except Exception:
                            pass
            except Exception:
                pass
        if checked:
            logger.info(f"BaseApply: Checked {checked} consent checkbox(es).")

    @abstractmethod
    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        """Runs the application adapter flow and returns True if successful."""
        pass
