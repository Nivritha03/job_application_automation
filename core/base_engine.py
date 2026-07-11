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
            # Check if this is a phone field
            is_phone = fg.field_type == "tel" or any(p in (fg.label or "").lower() for p in ["phone", "mobile", "telephone", "cell", "tel"])
            if is_phone:
                value = self._normalize_phone(fg, value)
            logger.info(f"UniversalEngine: fill_text label={fg.label_raw!r} value={value[:60]!r}")
            fg.locator.scroll_into_view_if_needed()
            fg.locator.click(timeout=3000, force=True)
            fg.locator.fill("")
            fg.locator.press_sequentially(value, delay=50)
        except Exception as e:
            logger.error(f"UniversalEngine: Failed fill_text on '{fg.label_raw}': {e}")
            raise e

    def _normalize_phone(self, fg: FieldGroup, value: str) -> str:
        # Strip all non-digit characters except maybe '+'
        cleaned = "".join([c for c in value if c.isdigit() or c == '+'])
        
        # Determine format based on field constraints
        max_len = None
        try:
            max_len_attr = fg.locator.get_attribute("maxlength")
            if max_len_attr:
                max_len = int(max_len_attr)
        except Exception:
            pass
            
        # Get 10-digit raw number
        raw_10 = cleaned
        if cleaned.startswith("+91"):
            raw_10 = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            raw_10 = cleaned[2:]
            
        if max_len == 10:
            logger.info(f"Phone normalization: Max length is 10. Normalizing to 10-digit raw: {raw_10}")
            return raw_10
            
        # Check placeholder or label constraints
        placeholder = (fg.placeholder or "").lower()
        label = (fg.label or "").lower()
        
        if "10 digit" in placeholder or "10-digit" in placeholder or "10 digit" in label:
            logger.info(f"Phone normalization: Placeholder/label specifies 10 digits. Normalizing: {raw_10}")
            return raw_10
            
        if "country code" in label or "country code" in placeholder:
            logger.info(f"Phone normalization: Country code requested. Normalizing: {cleaned}")
            return cleaned
            
        pattern = ""
        try:
            pattern = fg.locator.get_attribute("pattern") or ""
        except Exception:
            pass
            
        if pattern and "+" not in pattern:
            no_plus = cleaned.lstrip("+")
            logger.info(f"Phone normalization: Pattern '{pattern}' does not allow '+'. Normalizing: {no_plus}")
            return no_plus
            
        logger.info(f"Phone normalization: Defaulting to original cleaned: {cleaned}")
        return cleaned

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
            
            # Check state first to see if we need to toggle
            is_currently_checked = False
            try:
                is_currently_checked = fg.locator.is_checked()
            except:
                pass
                
            if is_currently_checked == checked:
                logger.info("UniversalEngine: Checkbox is already in correct state.")
                return

            # Try direct check/uncheck
            success = False
            try:
                if checked:
                    fg.locator.check(force=True, timeout=2000)
                else:
                    fg.locator.uncheck(force=True, timeout=2000)
                success = True
            except Exception:
                pass
                
            if not success or (checked != fg.locator.is_checked() if hasattr(fg.locator, "is_checked") else False):
                # Fallback to clicking the label or the locator directly
                id_attr = fg.id_attr
                if id_attr:
                    label_loc = self.page.locator(f"label[for='{id_attr}']").first
                    if label_loc.count() > 0 and label_loc.is_visible():
                        label_loc.click(force=True)
                        return
                
                # Check parent wrapper text and click it
                try:
                    parent_label = fg.locator.locator("xpath=ancestor::label").first
                    if parent_label.count() > 0 and parent_label.is_visible():
                        parent_label.click(force=True)
                        return
                except:
                    pass
                    
                fg.locator.click(force=True)
        except Exception as e:
            logger.error(f"UniversalEngine: Failed fill_checkbox on '{fg.label_raw}': {e}")
            raise e

    def upload_file(self, fg: FieldGroup, file_path: str):
        """Uploads a file to a file input locator and verifies filename visibility."""
        try:
            logger.info(f"UniversalEngine: upload_file label={fg.label_raw!r} path={file_path}")
            fg.locator.set_input_files(file_path)
            time.sleep(1.5)  # Wait for upload processing
            
            # Verify filename appears on the page
            filename = os.path.basename(file_path)
            is_visible = False
            for _ in range(3):
                try:
                    if self.page.locator(f"text={filename}").count() > 0:
                        is_visible = True
                        break
                except Exception:
                    pass
                time.sleep(1.0)
                
            if not is_visible:
                logger.warning(f"UniversalEngine: Filename '{filename}' not detected after upload. Retrying upload once...")
                fg.locator.set_input_files(file_path)
                time.sleep(2.5)
                try:
                    if self.page.locator(f"text={filename}").count() > 0:
                        logger.info("UniversalEngine: Upload verified on second attempt.")
                    else:
                        logger.warning("UniversalEngine: Upload filename still not detected, but continuing.")
                except Exception:
                    pass
            else:
                logger.info("UniversalEngine: Upload filename verification successful.")
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
        """Smart EEO and synonym matching for dropdown options with strict boundary priority."""
        opt_lower = option_text.lower().strip()
        ans_lower = answer_text.lower().strip()
        
        # 1. Try exact match first
        if opt_lower == ans_lower:
            return True
            
        # 2. Match with word boundaries to avoid things like "India" matching "British Indian Ocean Territory"
        import re
        pattern = r'\b' + re.escape(ans_lower) + r'\b'
        if re.search(pattern, opt_lower):
            return True
            
        # 3. Smart decline EEO options matching (e.g. mapping 'Prefer not to say' to 'I don't wish to answer')
        decline_keywords = ["prefer not to", "decline to", "don't want to", "choose not to", "not disclose", "wish to answer", "don't wish"]
        is_ans_decline = any(kw in ans_lower for kw in ["prefer not to say", "prefer not to disclose", "decline", "not disclose", "don't wish to answer"])
        if is_ans_decline:
            if any(kw in opt_lower for kw in decline_keywords):
                return True
                
        # 4. Fallback matching as a last resort
        if len(ans_lower) >= 4 and (ans_lower in opt_lower or opt_lower in ans_lower):
            # Exclude known false positives: India matching British Indian Ocean Territory
            if ans_lower == "india" and "british indian ocean" in opt_lower:
                return False
            return True
            
        return False

    def _resolve_profile_field_ai(self, key: str, fg: FieldGroup) -> str:
        """Uses Groq AI API to dynamically resolve standard profile field values when not configured statically."""
        ai_qa = getattr(self, "ai_question_answerer", None)
        job = getattr(self, "job", None)
        if ai_qa and job:
            resume_used = job.resume_used or "Resume.pdf"
            resume_text = ""
            try:
                from ai.resume_ranker import AIResumeRanker
                temp_ranker = AIResumeRanker(ai_qa.client, ai_qa.cache)
                resume_text = temp_ranker._extract_pdf_text(resume_used)
            except Exception:
                pass
            
            logger.info(f"UniversalEngine AI: Resolving profile field '{key}' ('{fg.label_raw}') using Groq...")
            ans = ai_qa.answer_question(
                question=fg.label_raw or key,
                field_type=fg.field_type,
                job_details=f"Title: {job.title}\nDescription: {job.description}",
                resume_text=resume_text,
                profile_details=getattr(self, "candidate_profile", {}),
                company=job.company,
                role=job.title
            )
            if ans == "REQUIRES_USER_INPUT" and fg.field_type not in ("checkbox", "radio"):
                html_context = f"name={fg.name_attr or ''} id={fg.id_attr or ''} placeholder={fg.placeholder or ''}"
                assistant_res = ai_qa.form_assistant_fallback(
                    label=fg.label_raw or key,
                    placeholder=fg.placeholder or "",
                    question=fg.label_raw or key,
                    html_context=html_context,
                    job_description=job.description,
                    resume_text=resume_text,
                    profile_details=getattr(self, "candidate_profile", {}),
                    company=job.company,
                    role=job.title
                )
                ans = assistant_res.get("answer", "REQUIRES_USER_INPUT")
                
            if ans == "REQUIRES_USER_INPUT":
                return ""
            return ans
        return ""
