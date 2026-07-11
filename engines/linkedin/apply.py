import os
import yaml
import time
from loguru import logger
from core.base_engine import UniversalApplyEngine
from core.models import Job
from engines.forms.detector import FormDetector, FieldGroup
from engines.forms.mapper import FormMapper
from engines.forms.question_handler import QuestionHandler
from engines.linkedin.selectors import (
    MODAL, NEXT_BTN, SUBMIT_BTN, DISMISS_BTN, DISCARD_BTN, EXTERNAL_APPLY_BTN
)

class LinkedInApply(UniversalApplyEngine):
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
            logger.error(f"LinkedInApply: Failed to load answers config: {e}")

    def apply(self, job: Job, dry_run: bool = False, screenshot_cb=None) -> bool:
        logger.info("LINKEDIN APPLY ENGINE")
        logger.info(f"LinkedInApply: Starting Easy Apply flow for {job.title!r} at {job.company}")
        try:
            # ── 1. Navigate to Job View ───────────────────────────────────────
            if self.page.url.rstrip("/") != job.url.rstrip("/"):
                try:
                    self.page.goto(job.url, wait_until="domcontentloaded", timeout=15000)
                except Exception as goto_err:
                    logger.warning(f"LinkedInApply: Page navigation warning: {goto_err}")
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            
            # Check login redirect
            if "login" in self.page.url or "signin" in self.page.url:
                logger.error("LinkedInApply: User is not authenticated. Aborting application.")
                job.failure_type = "LOGIN_REQUIRED"
                return False

            # Check and click "Easy Apply" button
            easy_apply_btn = None
            for btn in self.page.locator("button.jobs-apply-button, button:has-text('Easy Apply'), button:has-text('Apply now')").all():
                try:
                    if btn.is_visible() and btn.is_enabled():
                        easy_apply_btn = btn
                        break
                except:
                    pass
                    
            if not easy_apply_btn:
                # Check for external apply button / link
                external_btn = self.page.locator(EXTERNAL_APPLY_BTN).first
                if external_btn.count() > 0 and external_btn.is_visible():
                    logger.info("LinkedInApply: External apply button detected. Setting status to external_redirect.")
                    job.status = "external_redirect"
                    job.failure_type = "external_redirect"
                    return False
                    
                logger.warning("LinkedInApply: Easy Apply button is not visible or enabled. Skipping.")
                job.failure_type = "APPLICATION_CLOSED"
                return False
                
            self.take_screenshot("before_fill", job.title)
            
            modal_selector = MODAL
            clicked_successfully = False
            for attempt in range(3):
                try:
                    logger.info(f"LinkedInApply: Attempting to click Easy Apply button (Attempt {attempt+1})")
                    easy_apply_btn.scroll_into_view_if_needed()
                    easy_apply_btn.click(force=True)
                    time.sleep(2)
                    self.handle_redirect_tab()
                    # Check if modal loaded
                    modal_check = self.page.locator(modal_selector).first
                    if modal_check.count() > 0 and modal_check.is_visible():
                        clicked_successfully = True
                        break
                except Exception as click_err:
                    logger.warning(f"LinkedInApply: Click attempt {attempt+1} warning: {click_err}")
                time.sleep(1.5)
                
            if not clicked_successfully:
                try:
                    self.page.wait_for_selector(modal_selector, timeout=5000)
                except Exception:
                    logger.error("LinkedInApply: Easy Apply modal failed to load after multiple click attempts.")
                    job.failure_type = "UNKNOWN_SELECTOR"
                    return False

            # ── 2. Interactive Multi-Step Form Automation Loop ────────────────
            step_count = 1
            max_steps = 10
            
            while step_count <= max_steps:
                logger.info(f"LinkedInApply: Processing Modal Step {step_count}")
                modal = self.page.locator(modal_selector).first
                
                # Check for Captcha / Cloudflare Challenge
                body_text = self.page.locator("body").inner_text().lower()
                if any(w in body_text for w in ["hcaptcha", "recaptcha", "cloudflare", "captcha", "security check", "confirm you're a human"]):
                    logger.error("LinkedInApply: CAPTCHA security challenge detected.")
                    job.failure_type = "CAPTCHA"
                    self.take_screenshot("captcha_error", job.title)
                    # Attempt to dismiss modal
                    self._dismiss_modal()
                    return False
                    
                # Check for Identity / Phone Verification prompts
                if any(w in body_text for w in ["phone verification", "verify your phone", "enter verification code", "verify your identity"]):
                    logger.error("LinkedInApply: Identity / phone verification challenge detected.")
                    job.failure_type = "CAPTCHA"
                    self.take_screenshot("verification_error", job.title)
                    self._dismiss_modal()
                    return False

                # Scan inputs inside modal only
                modal_detector = FormDetector(modal)
                field_groups = modal_detector.find_fields()
                profile_fields, questions = self.mapper.map_fields(field_groups)

                # Resume file upload on first step or when uploader is present
                if "resume" in profile_fields:
                    self.handle_resume(profile_fields, job.resume_used)

                # Fill profile inputs (name, email, phone, location)
                self.handle_profile_fields(profile_fields)

                # Answer simple form questions
                self.question_handler.answer_all(questions, self)

                # Auto check consent checkboxes
                self._auto_check_consent(modal)

                self.take_screenshot(f"fill_step_{step_count}", job.title)

                # Locate next step or submit button
                next_btn = modal.locator(NEXT_BTN).first
                submit_btn = modal.locator(SUBMIT_BTN).first

                if submit_btn.count() > 0 and submit_btn.is_visible():
                    if not dry_run:
                        logger.info("LinkedInApply: Final step. Submitting application.")
                        submit_btn.click()
                        time.sleep(3.5)
                        self.take_screenshot("after_submit", job.title)
                        
                        # Close the post-submit success confirmation modal
                        try:
                            close_confirm = self.page.locator("button[aria-label*='Dismiss'], button:has-text('Done')").first
                            if close_confirm.count() > 0 and close_confirm.is_visible():
                                close_confirm.click()
                        except:
                            pass
                            
                        return True
                    else:
                        logger.info(f"LinkedInApply: [DRY RUN] Would submit application on step {step_count}")
                        self._dismiss_modal()
                        return True
                        
                elif next_btn.count() > 0 and next_btn.is_visible():
                    logger.info("LinkedInApply: Clicking Next to proceed to next step.")
                    next_btn.click()
                    time.sleep(2)
                    step_count += 1
                else:
                    logger.warning("LinkedInApply: No primary action button matched. Aborting.")
                    job.failure_type = "UNKNOWN_SELECTOR"
                    self._dismiss_modal()
                    return False
                    
            logger.warning("LinkedInApply: Exceeded maximum multi-step loop count.")
            job.failure_type = "UNKNOWN_SELECTOR"
            self._dismiss_modal()
            return False

        except Exception as e:
            logger.error(f"LinkedInApply: Easy Apply flow failed: {e}")
            job.failure_type = "UNKNOWN"
            self.take_screenshot("error", job.title)
            self._dismiss_modal()
            return False

    def handle_resume(self, profile_fields, resume_used: str):
        if "resume" in profile_fields and resume_used:
            fg = profile_fields["resume"]
            resume_path = os.path.abspath(os.path.join("data", "resumes", resume_used))
            if os.path.exists(resume_path):
                self.upload_file(fg, resume_path)
            else:
                logger.error(f"LinkedInApply: Resume file not found at {resume_path}")

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
        }

        for key, fg in profile_fields.items():
            if key == "resume":
                continue

            value = resolvers.get(key, self.answers.get(key, ""))
            if not value and getattr(self, "ai_enabled", False) and getattr(self, "ai_question_answerer", None):
                value = self._resolve_profile_field_ai(key, fg)
            if not value:
                continue

            if key == "location":
                city_prefix = value.split(',')[0].strip() if ',' in value else value
                self.fill_select(fg, value, search_prefix=city_prefix)
            elif fg.field_type == "select":
                self.fill_select(fg, value)
            else:
                self.fill_text(fg, value)

    def _auto_check_consent(self, modal):
        try:
            boxes = modal.locator("input[type='checkbox']").all()
            for box in boxes:
                try:
                    if not box.is_checked():
                        box.check(force=True)
                except Exception:
                    pass
        except Exception:
            pass

    def _dismiss_modal(self):
        try:
            logger.info("LinkedInApply: Dismissing modal dialog.")
            dismiss_btn = self.page.locator(DISMISS_BTN).first
            if dismiss_btn.count() > 0:
                dismiss_btn.click()
                time.sleep(1.0)
                # Confirm discard if prompted
                discard_btn = self.page.locator(DISCARD_BTN).first
                if discard_btn.count() > 0:
                    discard_btn.click()
                    time.sleep(1.0)
        except Exception as e:
            logger.debug(f"LinkedInApply: Failed to dismiss modal: {e}")
