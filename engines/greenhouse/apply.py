import os
import yaml
import time
from loguru import logger
from engines.apply.universal_engine import UniversalApplyEngine
from core.models import Job
from engines.forms.detector import FormDetector, FieldGroup
from engines.forms.mapper import FormMapper
from engines.forms.question_handler import QuestionHandler
from engines.greenhouse.selectors import FORM_SELECTOR, INPUTS_SELECTOR, SUBMIT_SELECTOR

class GreenhouseApply(UniversalApplyEngine):
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
            logger.error(f"GreenhouseApply: Failed to load answers config: {e}")

    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"GreenhouseApply: Starting application flow for {job.title!r} at {job.company}")
        try:
            # ── 1. Navigate to Apply URL ──────────────────────────────────────
            apply_url = self._resolve_apply_url(job)
            logger.info(f"GreenhouseApply: Navigating to apply page: {apply_url}")
            if self.page.url.rstrip("/") != apply_url.rstrip("/"):
                self.page.goto(apply_url)
            
            try:
                self.page.wait_for_selector(INPUTS_SELECTOR, timeout=12000)
            except Exception:
                logger.warning("GreenhouseApply: Timed out waiting for form fields — continuing.")
            time.sleep(1)

            # ── 2. Before-Fill Screenshot ─────────────────────────────────────
            self.take_screenshot("before_fill", job.title)

            # ── 3. Find and Map Fields ────────────────────────────────────────
            field_groups = self.find_fields()
            profile_fields, questions = self.find_questions(field_groups)

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
                self.submit(submit_selector=SUBMIT_SELECTOR)
                time.sleep(3.0)  # Wait for submission processing or redirects
                self.take_screenshot("after_submit", job.title)
                
                # Check for success/error indicator
                success = self._detect_success()
                if not success:
                    logger.warning("GreenhouseApply: Validation error or OTP challenge detected.")
                    return False
                return True
            else:
                logger.info(f"GreenhouseApply: [DRY RUN] Would submit application for {job.title}")
                return True

        except Exception as e:
            logger.error(f"GreenhouseApply: Application engine failed: {e}")
            self.take_screenshot("error", job.title)
            return False

    def find_fields(self):
        return self.detector.find_fields()

    def find_questions(self, field_groups):
        return self.mapper.map_fields(field_groups)

    def handle_resume(self, profile_fields, resume_used: str):
        if "resume" in profile_fields and resume_used:
            fg = profile_fields["resume"]
            resume_path = os.path.abspath(os.path.join("data", "resumes", resume_used))
            if os.path.exists(resume_path):
                self.upload_file(fg, resume_path)
            else:
                logger.error(f"GreenhouseApply: Resume file not found at {resume_path}")

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
            "degree":            self.answers.get("degree", ""),
            "discipline":        self.answers.get("discipline", ""),
            "school":            self.answers.get("school", ""),
            "country":           self.answers.get("country", ""),
        }

        for key, fg in profile_fields.items():
            if key == "resume":
                continue

            value = resolvers.get(key, self.answers.get(key, ""))
            if not value:
                continue

            # Route custom dropdown selections and locations
            if key == "location":
                city_prefix = value.split(',')[0].strip() if ',' in value else value
                self.fill_select(fg, value, search_prefix=city_prefix)
            elif key in ("degree", "discipline", "school", "country"):
                self.fill_select(fg, value)
            else:
                self.fill_text(fg, value)

    def _resolve_apply_url(self, job: Job) -> str:
        url = job.url.rstrip("/")
        if "/applications/new" in url or "/apply" in url:
            return url
        if "job-boards.greenhouse.io" in url:
            return url
        if "boards.greenhouse.io" in url:
            return f"{url}/applications/new"
        return url

    def _auto_check_consent(self):
        CONSENT_SELECTORS = [
            "input[type='checkbox'][name*='gdpr']",
            "input[type='checkbox'][name*='consent']",
            "input[type='checkbox'][id*='gdpr']",
            "input[type='checkbox'][id*='consent']",
            "input[type='checkbox'][name*='privacy']",
            "input[type='checkbox'][id*='privacy']",
        ]
        for selector in CONSENT_SELECTORS:
            try:
                boxes = self.page.locator(selector).all()
                for box in boxes:
                    try:
                        if not box.is_checked():
                            box.check(force=True)
                    except Exception:
                        # Fallback click associated label
                        try:
                            box_id = box.get_attribute("id")
                            if box_id:
                                self.page.locator(f"label[for='{box_id}']").click(force=True)
                        except Exception:
                            pass
            except Exception:
                pass

    def _detect_success(self) -> bool:
        # Check standard success URLs or headers
        current_url = self.page.url.lower()
        if "confirmation" in current_url or "thank-you" in current_url or "success" in current_url:
            return True
        # Check for visible confirmation headings
        for selector in ["h1", "h2", "h3", ".confirmation", ".thank-you"]:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    text = loc.first.inner_text().lower()
                    if "thank you" in text or "received" in text or "submitted" in text or "success" in text:
                        return True
            except Exception:
                pass
        return False
