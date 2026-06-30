import os
import yaml
import time
from loguru import logger
from core.base_engine import UniversalApplyEngine
from core.models import Job
from engines.forms.detector import FormDetector, FieldGroup
from engines.forms.mapper import FormMapper
from engines.forms.question_handler import QuestionHandler

class WorkableApply(UniversalApplyEngine):
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
            logger.error(f"WorkableApply: Failed to load answers config: {e}")

    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info(f"WorkableApply: Starting application flow for {job.title!r} at {job.company}")
        try:
            # ── 1. Navigate to Apply URL ──────────────────────────────────────
            # Workable apply pages are usually: job_url + "/apply/"
            apply_url = job.url.rstrip("/") + "/apply/"
            logger.info(f"WorkableApply: Navigating to apply page: {apply_url}")
            self.page.goto(apply_url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

            # Check if we landed on details page instead of apply page, look for "Apply" button to click
            apply_btn = self.page.locator("a[data-ui='apply-button'], button[data-ui='apply-button'], button:has-text('Apply')")
            if apply_btn.count() > 0 and apply_btn.first.is_visible():
                apply_btn.first.click()
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)

            # ── 2. Multi-step Form Filling Wizard ─────────────────────────────
            step_count = 1
            max_steps = 4
            
            while step_count <= max_steps:
                logger.info(f"WorkableApply: Processing Form Step {step_count}")
                self.take_screenshot(f"before_fill_step_{step_count}", job.title)

                # Scan current page fields
                field_groups = self.detector.find_fields()
                profile_fields, questions = self.mapper.map_fields(field_groups)

                # If no fields found at all, we might be on a confirmation page or submit redirect
                if not field_groups:
                    logger.info("WorkableApply: No input fields detected on this page step.")
                    break

                # Upload files on step 1 (usually resume/cv)
                if step_count == 1:
                    self.handle_resume(profile_fields, job.resume_used)
                    self.handle_cover_letter(profile_fields)

                # Fill profile fields on this step
                self.handle_profile_fields(profile_fields)

                # Answer questions on this step
                self.question_handler.answer_all(questions, self)

                # Check GDPR/privacy consents on this step
                self._auto_check_consent()

                self.take_screenshot(f"after_fill_step_{step_count}", job.title)

                # Find transition button (either Next, Continue, or Submit)
                next_selectors = [
                    "button[data-ui='next-step']",
                    "button:has-text('Next')",
                    "button:has-text('Continue')",
                    "button[type='submit']",
                    "button:has-text('Submit')"
                ]
                
                next_btn = None
                is_submit = False
                for sel in next_selectors:
                    try:
                        loc = self.page.locator(sel)
                        if loc.count() > 0 and loc.first.is_visible():
                            next_btn = loc.first
                            if "submit" in sel or "Submit" in loc.first.inner_text():
                                is_submit = True
                            break
                    except Exception:
                        continue

                if not next_btn:
                    logger.warning("WorkableApply: Could not identify Step navigation button.")
                    break

                if is_submit:
                    # If this is final submit step
                    if not dry_run:
                        logger.info("WorkableApply: Final step reached. Clicking Submit.")
                        next_btn.click()
                        time.sleep(4.0)
                        self.take_screenshot("after_submit", job.title)
                        return self._detect_success()
                    else:
                        logger.info(f"WorkableApply: [DRY RUN] Would click Submit on step {step_count}")
                        return True
                else:
                    logger.info(f"WorkableApply: Clicking Next to proceed to step {step_count + 1}")
                    next_btn.click()
                    time.sleep(2.0)
                    self.page.wait_for_load_state("networkidle")
                    step_count += 1

            # Fallback success check
            return self._detect_success()

        except Exception as e:
            logger.error(f"WorkableApply: Application engine failed: {e}")
            self.take_screenshot("error", job.title)
            return False

    def handle_resume(self, profile_fields, resume_used: str):
        if "resume" in profile_fields and resume_used:
            fg = profile_fields["resume"]
            resume_path = os.path.abspath(os.path.join("data", "resumes", resume_used))
            if os.path.exists(resume_path):
                self.upload_file(fg, resume_path)
            else:
                logger.error(f"WorkableApply: Resume file not found at {resume_path}")

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
            "input[type='checkbox'][name*='consent']",
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
        for selector in ["h1", "h2", "h3", ".confirmation", ".thank-you", "[data-ui='thank-you']"]:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    text = loc.first.inner_text().lower()
                    if any(w in text for w in ["thank you", "received", "submitted", "success"]):
                        return True
            except Exception:
                pass
        return False
