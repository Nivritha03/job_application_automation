import os
import yaml
import time
from loguru import logger
from core.base_engine import UniversalApplyEngine
from core.models import Job
from engines.forms.detector import FormDetector, FieldGroup
from engines.forms.mapper import FormMapper
from engines.forms.question_handler import QuestionHandler

class AshbyApply(UniversalApplyEngine):
    def __init__(self, page):
        super().__init__(page)
        self.detector = FormDetector(page)
        self.mapper = FormMapper()
        self.question_handler = QuestionHandler()
        self.answers = {}
        self._load_answers()

    def _load_answers(self):
        try:
            with open("config/answers.yaml", "r", encoding="utf-8") as f:
                self.answers = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"AshbyApply: Failed to load answers config: {e}")

    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"AshbyApply: Starting application flow for {job.title!r} at {job.company}")
        try:
            # ── 1. Navigate to Apply URL ──────────────────────────────────────
            # Ashby job URL usually contains the apply form right on the page or inside iframe
            logger.info(f"AshbyApply: Navigating to page: {job.url}")
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                self.page.goto(job.url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

            # Wait for form or input fields to appear
            try:
                self.page.wait_for_selector("input, form, button", timeout=12000)
            except Exception:
                logger.warning("AshbyApply: Timed out waiting for form fields — continuing.")
            time.sleep(1)

            # ── 2. Before-Fill Screenshot ─────────────────────────────────────
            self.take_screenshot("before_fill", job.title)

            # ── 3. Find and Map Fields ────────────────────────────────────────
            field_groups = self.detector.find_fields()
            profile_fields, questions = self.mapper.map_fields(field_groups)

            # ── 4. Upload Resume & Cover Letter ────────────────────────────────
            self.handle_resume(profile_fields, job.resume_used)
            self.handle_cover_letter(profile_fields)

            # ── 5. Fill Profile Fields ────────────────────────────────────────
            self.handle_profile_fields(profile_fields)

            # ── 6. Answer Questions ───────────────────────────────────────────
            self.question_handler.answer_all(questions, self)

            # ── 7. After-Fill Screenshot ──────────────────────────────────────
            self.take_screenshot("after_fill", job.title)

            # ── 8. Check Consent Checkboxes ──────────────────────────────────
            self._auto_check_consent()

            # ── 9. Before-Submit Screenshot ───────────────────────────────────
            self.take_screenshot("before_submit", job.title)

            # ── 10. Click Submit Button ───────────────────────────────────────
            if not dry_run:
                # Ashby submit buttons are typically labeled 'Submit Application', 'Apply' or are input[type='submit']
                submit_selectors = [
                    "button:has-text('Submit')",
                    "button:has-text('Apply')",
                    "input[type='submit']",
                    "button[type='submit']"
                ]
                success_click = False
                for sel in submit_selectors:
                    try:
                        loc = self.page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.scroll_into_view_if_needed()
                            loc.first.click(timeout=5000)
                            success_click = True
                            break
                    except Exception:
                        continue
                        
                if not success_click:
                    logger.warning("AshbyApply: Submit button not matched. Falling back to universal submit.")
                    self.submit()
                    
                time.sleep(3.5)
                self.take_screenshot("after_submit", job.title)
                
                success = self._detect_success()
                if not success:
                    logger.warning("AshbyApply: Validation error or OTP challenge detected.")
                    return False
                return True
            else:
                logger.info(f"AshbyApply: [DRY RUN] Would submit application for {job.title}")
                return True

        except Exception as e:
            logger.error(f"AshbyApply: Application engine failed: {e}")
            self.take_screenshot("error", job.title)
            return False

    def handle_resume(self, profile_fields, resume_used: str):
        if "resume" in profile_fields and resume_used:
            fg = profile_fields["resume"]
            resume_path = os.path.abspath(os.path.join("data", "resumes", resume_used))
            if os.path.exists(resume_path):
                self.upload_file(fg, resume_path)
            else:
                logger.error(f"AshbyApply: Resume file not found at {resume_path}")

    def handle_cover_letter(self, profile_fields):
        if "cover_letter" in profile_fields:
            fg = profile_fields["cover_letter"]
            cover_letter_val = self.answers.get("cover_letter", "")
            if cover_letter_val:
                cl_path = os.path.abspath(os.path.join("data", "resumes", cover_letter_val))
                if os.path.exists(cl_path):
                    self.upload_file(fg, cl_path)
                else:
                    self.fill_text(fg, cover_letter_val)

    def handle_profile_fields(self, profile_fields):
        name_val = self.answers.get("name", "")
        first_name = self.answers.get("first_name") or (name_val.split()[0] if name_val else "")
        last_name  = self.answers.get("last_name")  or (name_val.split()[-1] if len(name_val.split()) > 1 else "")

        resolvers = {
            "first_name":        first_name,
            "last_name":         last_name,
            "name":              name_val,
            "email":             self.answers.get("email", ""),
            "phone":             self.answers.get("phone", ""),
            "location":          self.answers.get("location", ""),
            "linkedin":          self.answers.get("linkedin", ""),
            "github":            self.answers.get("github", ""),
            "portfolio":         self.answers.get("portfolio", ""),
            "website":           self.answers.get("website", ""),
            "cover_letter":      self.answers.get("cover_letter", ""),
            "current_salary":    self.answers.get("current_salary", ""),
            "expected_salary":   self.answers.get("expected_salary", ""),
        }

        for key, fg in profile_fields.items():
            if key in ("resume", "cover_letter"):
                continue

            value = resolvers.get(key, self.answers.get(key, ""))
            if not value:
                continue

            if key == "location":
                city_prefix = value.split(',')[0].strip() if ',' in value else value
                self.fill_select(fg, value, search_prefix=city_prefix)
            elif fg.field_type == "select":
                self.fill_select(fg, value)
            else:
                self.fill_text(fg, value)

    def _auto_check_consent(self):
        CONSENT_SELECTORS = [
            "input[type='checkbox'][name*='gdpr']",
            "input[type='checkbox'][name*='consent']",
            "input[type='checkbox'][id*='gdpr']",
            "input[type='checkbox'][id*='consent']",
            "input[type='checkbox'][name*='privacy']",
            "input[type='checkbox'][id*='privacy']",
            "input[type='checkbox']"
        ]
        for selector in CONSENT_SELECTORS:
            try:
                boxes = self.page.locator(selector).all()
                for box in boxes:
                    try:
                        box_label = box.locator("xpath=..").inner_text().lower()
                        if any(w in box_label for w in ["consent", "privacy", "gdpr", "agree", "policy"]):
                            if not box.is_checked():
                                box.check(force=True)
                    except Exception:
                        pass
            except Exception:
                pass

    def _detect_success(self) -> bool:
        current_url = self.page.url.lower()
        if "confirmation" in current_url or "thank-you" in current_url or "success" in current_url:
            return True
        for selector in ["h1", "h2", "h3", ".confirmation", ".thank-you", "[class*='success']"]:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    text = loc.first.inner_text().lower()
                    if any(w in text for w in ["thank you", "received", "submitted", "success"]):
                        return True
            except Exception:
                pass
        return False
