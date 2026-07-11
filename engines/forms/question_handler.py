import yaml
import time
from abc import ABC, abstractmethod
from loguru import logger
from engines.forms.detector import FieldGroup

class BaseQuestionHandler(ABC):
    def __init__(self, parent_handler):
        self.parent = parent_handler

    @abstractmethod
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        pass

    def _resolve_answer(self, label_lower: str, fg: FieldGroup) -> str:
        """Utility to look up the configured answer from standard categories."""
        # 1. Try compliance mapping
        ans = self.parent._match_compliance(label_lower)
        # 2. Try dropdown config
        if not ans:
            ans = self.parent._match_dict(label_lower, self.parent.dropdowns)
        # 3. Try free text
        if not ans:
            ans = self.parent._match_dict(label_lower, self.parent.free_text)
            
        # ── AI Fallback Form Assistant ──
        engine = getattr(self.parent, "engine", None)
        if not ans and engine and getattr(engine, "ai_enabled", False):
            ai_qa = getattr(engine, "ai_question_answerer", None)
            job = getattr(engine, "job", None)
            if ai_qa and job:
                resume_used = job.resume_used or "Resume.pdf"
                resume_text = ""
                try:
                    from ai.resume_ranker import AIResumeRanker
                    temp_ranker = AIResumeRanker(ai_qa.client, ai_qa.cache)
                    resume_text = temp_ranker._extract_pdf_text(resume_used)
                except Exception:
                    pass
                
                logger.info(f"QuestionHandler AI: Fallback answering '{fg.label_raw}' using Groq...")
                ans = ai_qa.answer_question(
                    question=fg.label_raw or label_lower,
                    field_type=fg.field_type,
                    job_details=f"Title: {job.title}\nDescription: {job.description}",
                    resume_text=resume_text,
                    profile_details=getattr(engine, "candidate_profile", {}),
                    company=job.company,
                    role=job.title
                )
                
                if ans == "REQUIRES_USER_INPUT":
                    html_context = f"name={fg.name_attr or ''} id={fg.id_attr or ''} placeholder={fg.placeholder or ''}"
                    assistant_res = ai_qa.form_assistant_fallback(
                        label=fg.label_raw or label_lower,
                        placeholder=fg.placeholder or "",
                        question=fg.label_raw or label_lower,
                        html_context=html_context,
                        job_description=job.description,
                        resume_text=resume_text,
                        profile_details=getattr(engine, "candidate_profile", {}),
                        company=job.company,
                        role=job.title
                    )
                    ans = assistant_res.get("answer", "REQUIRES_USER_INPUT")
                    
                if ans == "REQUIRES_USER_INPUT":
                    logger.warning(f"QuestionHandler AI: Question '{fg.label_raw}' requires user input.")
                    ans = ""
                else:
                    ans = str(ans)
                    logger.info(f"QuestionHandler AI: Answer resolved: {ans[:60]!r}")
        return ans

    def _answer_generic_field(self, label_lower: str, fg: FieldGroup, engine, answer_val: str) -> bool:
        """Generic input handling delegating to low-level engine operations."""
        if fg.field_type == "checkbox":
            checked = answer_val.lower() in ("yes", "true", "1", "i agree", "confirm")
            engine.fill_checkbox(fg, checked)
            return True
        elif fg.field_type == "radio":
            try:
                page = fg.locator.page
                group_name = fg.name_attr
                if group_name:
                    radios = page.locator(f"input[type='radio'][name='{group_name}']").all()
                    logger.debug(f"QuestionHandler: Found {len(radios)} radio buttons in group {group_name!r}")
                    
                    # Strategy 1: exact/substring match on label or parent text
                    for r in radios:
                        r_id = r.get_attribute("id")
                        r_val = (r.get_attribute("value") or "").lower().strip()
                        
                        label_text = ""
                        if r_id:
                            lbl = page.locator(f"label[for='{r_id}']").first
                            if lbl.count() > 0:
                                label_text = lbl.inner_text().lower().strip()
                        if not label_text:
                            try:
                                label_text = r.locator("xpath=..").inner_text().lower().strip()
                            except:
                                pass
                                
                        # Check match
                        ans_norm = answer_val.lower().strip()
                        if ans_norm == r_val or ans_norm in label_text or label_text in ans_norm:
                            r.check(force=True)
                            # Also click the label to trigger UI updates if input is hidden
                            if r_id:
                                try:
                                    page.locator(f"label[for='{r_id}']").first.click(force=True)
                                except:
                                    pass
                            logger.info(f"QuestionHandler: Checked radio matching {answer_val!r} via text {label_text!r} / value {r_val!r}")
                            return True
                            
                    # Strategy 2: fallback to matching value
                    for r in radios:
                        r_val = (r.get_attribute("value") or "").lower().strip()
                        ans_norm = answer_val.lower().strip()
                        if ans_norm in r_val or r_val in ans_norm:
                            r.check(force=True)
                            # Try clicking label if hidden
                            r_id = r.get_attribute("id")
                            if r_id:
                                try:
                                    page.locator(f"label[for='{r_id}']").first.click(force=True)
                                except:
                                    pass
                            logger.info(f"QuestionHandler: Checked radio matching {answer_val!r} via value fallback {r_val!r}")
                            return True
                            
                    # Strategy 3: if answer is Yes/No and we have 2 radios, map Yes -> index 0, No -> index 1
                    ans_norm = answer_val.lower().strip()
                    if ans_norm in ("yes", "no") and len(radios) == 2:
                        idx = 0 if ans_norm == "yes" else 1
                        radios[idx].check(force=True)
                        r_id = radios[idx].get_attribute("id")
                        if r_id:
                            try:
                                page.locator(f"label[for='{r_id}']").first.click(force=True)
                            except:
                                pass
                        logger.info(f"QuestionHandler: Checked radio index {idx} for binary Yes/No answer {answer_val!r}")
                        return True
            except Exception as e:
                logger.error(f"QuestionHandler: radio selection failed: {e}")
            return False
        elif fg.field_type == "select":
            return engine.fill_select(fg, answer_val)
        else:
            # text, textarea, email, etc.
            engine.fill_text(fg, answer_val)
            # Try to match select options after typing (custom select widget)
            time.sleep(0.4)
            opts = engine.page.locator(
                "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
                "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
            ).all()
            for opt in opts:
                try:
                    opt_text = opt.inner_text()
                    if engine._is_matching_option(opt_text, answer_val):
                        opt.click(force=True)
                        logger.info(f"QuestionHandler: Clicked option after typing -> {opt_text.strip()!r}")
                        return True
                except Exception:
                    continue
            return True

# ─── Specialized Handlers ───────────────────────────────────────────────────

class WorkAuthorizationHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Yes"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class VisaHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "No"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class RelocationHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "No"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class RemoteHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Yes"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class SalaryHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "0"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class NoticePeriodHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Immediate"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class ExperienceHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "0"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class EducationHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Bachelor's Degree"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class DisabilityHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Prefer not to say"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class VeteranHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Prefer not to say"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class EthnicityHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Prefer not to say"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class GenderHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Prefer not to say"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class PronounsHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "Prefer not to say"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class SecurityClearanceHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg) or "No"
        return self._answer_generic_field(label_lower, fg, engine, ans)

class LocationHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg)
        if not ans:
            return False
        if fg.field_type not in ("checkbox", "radio", "select"):
            prefix = ans.split(',')[0].strip() if ',' in ans else ans
            engine.fill_select(fg, ans, search_prefix=prefix)
            return True
        return self._answer_generic_field(label_lower, fg, engine, ans)

class DefaultHandler(BaseQuestionHandler):
    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        label_lower = label.lower()
        ans = self._resolve_answer(label_lower, fg)
        if not ans:
            if fg.options:
                prefer = [o for o in fg.options if "prefer not" in o.lower() or "decline" in o.lower()]
                ans = prefer[0] if prefer else fg.options[0]
            else:
                ans = "N/A"
        return self._answer_generic_field(label_lower, fg, engine, ans)

# ─── Classifier ──────────────────────────────────────────────────────────────

class QuestionClassifier:
    @staticmethod
    def classify(label: str) -> str:
        label_lower = label.lower()
        if "pronoun" in label_lower:
            return "PRONOUNS"
        if any(w in label_lower for w in ["gender", "sex", "male", "female", "transgender"]):
            return "GENDER"
        if any(w in label_lower for w in ["ethnicity", "race", "origin", "background"]):
            return "ETHNICITY"
        if any(w in label_lower for w in ["veteran", "military", "armed forces"]):
            return "VETERAN"
        if any(w in label_lower for w in ["disability", "handicap", "disable"]):
            return "DISABILITY"
        if any(w in label_lower for w in ["education", "degree", "school", "university", "gpa"]):
            return "EDUCATION"
        if any(w in label_lower for w in ["authorized to work", "right to work", "work in the u.s.", "authorized to"]):
            return "WORK_AUTHORIZATION"
        if any(w in label_lower for w in ["sponsorship", "require visa", "h1b", "immigration", "visa"]):
            return "VISA"
        if any(w in label_lower for w in ["relocate", "relocation"]):
            return "RELOCATION"
        if any(w in label_lower for w in ["location", "live in", "address", "city", "state", "country", "reside"]):
            return "LOCATION"
        if any(w in label_lower for w in ["salary", "compensation", "expectations", "ctc"]):
            return "SALARY"
        if any(w in label_lower for w in ["notice period", "start date", "availability"]):
            return "NOTICE_PERIOD"
        if any(w in label_lower for w in ["years of experience", "how many years", "experience in", "years do you have"]):
            return "EXPERIENCE"
        if any(w in label_lower for w in ["remote", "work from home", "wfh", "hybrid"]):
            return "REMOTE"
        if any(w in label_lower for w in ["clearance", "security clearance", "active clearance"]):
            return "SECURITY_CLEARANCE"
        return "DEFAULT"

# ─── Main Orchestrator ────────────────────────────────────────────────────────

class QuestionHandler:
    def __init__(self, answers_path: str = "config/answers.yaml"):
        self.compliance: dict = {}
        self.free_text: dict = {}
        self.dropdowns: dict = {}
        self._load(answers_path)
        
        # Instantiate handlers map for each target category
        self.handlers = {
            "WORK_AUTHORIZATION": WorkAuthorizationHandler(self),
            "VISA": VisaHandler(self),
            "RELOCATION": RelocationHandler(self),
            "REMOTE": RemoteHandler(self),
            "SALARY": SalaryHandler(self),
            "NOTICE_PERIOD": NoticePeriodHandler(self),
            "EXPERIENCE": ExperienceHandler(self),
            "EDUCATION": EducationHandler(self),
            "DISABILITY": DisabilityHandler(self),
            "VETERAN": VeteranHandler(self),
            "ETHNICITY": EthnicityHandler(self),
            "GENDER": GenderHandler(self),
            "PRONOUNS": PronounsHandler(self),
            "SECURITY_CLEARANCE": SecurityClearanceHandler(self),
            "LOCATION": LocationHandler(self),
            "DEFAULT": DefaultHandler(self)
        }

    def _load(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.compliance = {k.lower(): v for k, v in (data.get("compliance") or {}).items()}
            self.free_text  = {k.lower(): v for k, v in (data.get("free_text") or {}).items()}
            self.dropdowns  = {k.lower(): v for k, v in (data.get("dropdowns") or {}).items()}
            logger.info(
                f"QuestionHandler: Loaded {len(self.compliance)} compliance, "
                f"{len(self.free_text)} free-text, {len(self.dropdowns)} dropdown answers."
            )
        except Exception as e:
            logger.error(f"QuestionHandler: Failed to load answers config: {e}")

    def answer_all(self, questions: dict, engine) -> dict:
        results = {}
        for label, fg in questions.items():
            answered = self.answer(label, fg, engine)
            results[label] = "answered" if answered else "unanswered"
        return results

    def answer(self, label: str, fg: FieldGroup, engine) -> bool:
        category = QuestionClassifier.classify(label)
        handler = self.handlers.get(category, self.handlers["DEFAULT"])
        logger.debug(f"QuestionHandler: Classifying {label!r} -> Category: {category} (Handler: {handler.__class__.__name__})")
        self.engine = engine
        return handler.answer(label, fg, engine)

    # ─── Matching Helpers ──────────────────────────────────────────────────────

    def _match_compliance(self, label_lower: str) -> str:
        for keyword, answer in self.compliance.items():
            normalized = keyword.replace("_", " ")
            if normalized in label_lower or keyword in label_lower:
                return answer
        return ""

    def _match_dict(self, label_lower: str, config_dict: dict) -> str:
        best_key = ""
        best_val = ""
        for key, val in config_dict.items():
            if key in label_lower or label_lower in key:
                if len(key) > len(best_key):
                    best_key = key
                    best_val = str(val)
        return best_val
