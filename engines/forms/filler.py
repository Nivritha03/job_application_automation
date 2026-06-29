import os
import yaml
from loguru import logger
from engines.forms.detector import FieldGroup
from engines.forms.question_handler import QuestionHandler


class FormFiller:
    """
    Fills standard profile fields and delegates Q&A questions to QuestionHandler.
    All values come from config/answers.yaml — nothing is hardcoded here.
    """

    def __init__(self, page):
        self.page = page
        self.answers: dict = {}
        self.question_handler = QuestionHandler()
        self._load_answers()

    def _load_answers(self):
        try:
            with open("config/answers.yaml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # Only keep top-level scalar fields (not the nested dicts)
            self.answers = {
                k: v for k, v in data.items()
                if not isinstance(v, dict)
            }
            logger.info(
                f"FormFiller: Loaded {len(self.answers)} profile answer keys from answers.yaml."
            )
        except Exception as e:
            logger.error(f"FormFiller: Failed to load answers.yaml: {e}")

    # ─── Public API ────────────────────────────────────────────────────────────

    def fill(self, profile_fields: dict, questions: dict, resume_filename: str, engine=None):
        """
        Fill standard profile fields, upload resume, and answer Q&A questions.

        Args:
            profile_fields: {field_key: FieldGroup}  from FormMapper
            questions:      {label_text: FieldGroup} from FormMapper
            resume_filename: filename inside data/resumes/
        """
        self._fill_profile(profile_fields, resume_filename)
        self._answer_questions(questions, engine)

    # ─── Profile field filling ─────────────────────────────────────────────────

    def _fill_profile(self, profile_fields: dict, resume_filename: str):
        name_val = self.answers.get("name", "")
        first_name = self.answers.get("first_name") or (name_val.split()[0] if name_val else "")
        last_name  = self.answers.get("last_name")  or (name_val.split()[-1] if len(name_val.split()) > 1 else "")

        # Runtime resolver so 'name' splits are derived from config, not profile.json
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
            if key == "resume":
                self._upload_resume(fg, resume_filename)
                continue

            value = resolvers.get(key, self.answers.get(key, ""))
            if not value:
                logger.debug(f"FormFiller: No value configured for profile field '{key}' — skipping.")
                continue

            self._fill_text(fg, key, str(value))
    def _fill_text(self, fg: FieldGroup, key: str, value: str):
        try:
            import time
            time.sleep(0.6)  # allow previous actions/dropdown closings to settle

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
                fg.locator.scroll_into_view_if_needed()
                fg.locator.click(timeout=3000, force=True)

            # For custom dropdown profile fields (like country, school, degree, discipline)
            # React Select needs us to click the option.
            # Try to match and click an option BEFORE typing first.
            import time
            time.sleep(0.4)
            option_clicked = False
            
            dropdown_keys = ["country", "school", "degree", "discipline"]
            if key in dropdown_keys:
                try:
                    page = fg.locator.page
                    # Restrict dropdown options to classes containing 'menu' or 'listbox' to bypass the phone country code list
                    opts = page.locator(
                        "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
                        "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
                    ).all()
                    for opt in opts:
                        try:
                            if self._is_matching_option(opt.inner_text(), value):
                                opt.click(force=True)
                                logger.info(f"FormFiller: [profile ] {key:<20s} = {value[:60]!r} (option selected)")
                                option_clicked = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
            
            if option_clicked:
                return

            fg.locator.fill("")

            # Location fields use Google Places Autocomplete — press keys sequentially to trigger typing events,
            # then click the matching suggestion from the dropdown menu.
            if key == "location":
                # Type only the city name (before the comma) to trigger suggestions.
                # Google Places Autocomplete often returns zero matches if a comma and region are typed.
                search_prefix = value.split(',')[0].strip() if ',' in value else value
                fg.locator.press_sequentially(search_prefix, delay=60)
                time.sleep(1.5)  # wait for Places suggestions dropdown
                
                option_clicked = False
                try:
                    page = fg.locator.page
                    opts = page.locator(
                        "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
                        "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
                    ).all()
                    for opt in opts:
                        try:
                            opt_text = opt.inner_text()
                            if self._is_matching_option(opt_text, value):
                                opt.click(force=True)
                                logger.info(f"FormFiller: [profile ] {key:<20s} = {value[:60]!r} (autocomplete option clicked)")
                                option_clicked = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
                
                if not option_clicked:
                    fg.locator.press("ArrowDown")
                    fg.locator.press("Enter")
                    logger.info(f"FormFiller: [profile ] {key:<20s} = {value[:60]!r} (fallback ArrowDown+Enter)")
                return

            fg.locator.fill(value)

            # Try to select option after typing
            if key in dropdown_keys:
                time.sleep(0.4)
                try:
                    page = fg.locator.page
                    opts = page.locator(
                        "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
                        "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
                    ).all()
                    for opt in opts:
                        try:
                            if self._is_matching_option(opt.inner_text(), value):
                                opt.click(force=True)
                                logger.info(f"FormFiller: [profile ] {key:<20s} = {value[:60]!r} (option selected after typing)")
                                return
                        except Exception:
                            continue
                except Exception:
                    pass

            logger.info(f"FormFiller: [profile ] {key:<20s} = {value[:60]!r}")
        except Exception as e:
            logger.error(f"FormFiller: Failed to fill '{key}': {e}")

    def _is_matching_option(self, option_text: str, answer_text: str) -> bool:
        """Helper to check if an option text matches a desired answer string,
        including smart synonym logic for decline/privacy fields.
        """
        opt_lower = option_text.lower()
        ans_lower = answer_text.lower()
        if ans_lower in opt_lower or opt_lower in ans_lower:
            return True
        decline_keywords = ["prefer not to", "decline to", "don't want to", "choose not to", "not disclose", "wish to answer", "don't wish"]
        is_ans_decline = any(kw in ans_lower for kw in ["prefer not to say", "prefer not to disclose", "decline", "not disclose", "don't wish to answer"])
        if is_ans_decline:
            if any(kw in opt_lower for kw in decline_keywords):
                return True
        return False


    def _upload_resume(self, fg: FieldGroup, resume_filename: str):
        resume_path = os.path.abspath(os.path.join("data", "resumes", resume_filename))
        if os.path.exists(resume_path):
            try:
                fg.locator.set_input_files(resume_path)
                # Wait for Greenhouse's async resume upload to complete.
                # Playwright's set_input_files() already fires the change event;
                # adding dispatch_event("change") on file inputs can block.
                import time; time.sleep(2.0)
                logger.info(f"FormFiller: [resume  ] Uploaded {resume_filename}")
            except Exception as e:
                logger.error(f"FormFiller: Failed to upload resume: {e}")
        else:
            logger.warning(
                f"FormFiller: Resume file not found at {resume_path}. "
                f"Create the file or update config/answers.yaml."
            )

    # ─── Question answering ────────────────────────────────────────────────────

    def _answer_questions(self, questions: dict, engine=None):
        if not questions:
            return
        logger.info(f"FormFiller: Answering {len(questions)} form question(s)...")
        results = self.question_handler.answer_all(questions, engine)

        unanswered = [q for q, status in results.items() if status == "unanswered"]
        if unanswered:
            logger.warning(
                f"FormFiller: {len(unanswered)} unanswered question(s). "
                f"Add answers to config/answers.yaml: {unanswered}"
            )
        answered_count = len(results) - len(unanswered)
        logger.info(
            f"FormFiller: Questions answered={answered_count}, "
            f"unanswered={len(unanswered)}."
        )
