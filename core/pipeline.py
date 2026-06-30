from core.browser import PlaywrightManager
from core.database import SessionLocal, init_db
from core.models import Job, DBJob, DBCompany, DBApplication, DBRun
from core.plugins import SEARCH_ENGINES, PARSER_ENGINES, APPLY_ENGINES
from engines.filter.eligibility import EligibilityFilter
from engines.resume.selector import ResumeSelector
from loguru import logger
import time

from core.notifications import NotificationDispatcher
from notifications.notifier import Notifier
import yaml

class Pipeline:
    def __init__(
        self,
        site: str,
        search_query: str = "python",
        company: str = "",
        limit: int = 5,
        resume: str = "auto",
        location: str = "",
        remote_only: bool = False,
        debug: bool = False,
        dry_run: bool = False,
        headless: bool = False,
        review_required: bool = False,
        resume_otp_only: bool = False,
        global_search: bool = False,
        ai_enabled: bool = None,
        groq_model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        self.site = site
        self.search_query = search_query
        self.company = company
        self.limit = limit
        self.resume = resume
        self.global_search = global_search
        self.location = location
        if not self.location and not self.global_search:
            self.location = "India"
        self.remote_only = remote_only
        self.debug = debug
        self.dry_run = dry_run
        self.headless = headless
        self.review_required = review_required
        self.resume_otp_only = resume_otp_only
        
        # Load config.yaml
        try:
            with open("config/config.yaml", "r") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception:
            self.config = {}

        # AI Configuration Initialization
        ai_cfg = self.config.get("ai", {})
        if ai_enabled is not None:
            self.ai_enabled = ai_enabled
        else:
            self.ai_enabled = ai_cfg.get("enabled", False)

        if self.ai_enabled:
            from ai.groq_client import GroqClient
            from ai.cache import AICache
            from ai.validator import AIValidator
            from ai.analyzer import AIAnalyzer
            from ai.resume_ranker import AIResumeRanker
            from ai.cover_letter import AICoverLetterGenerator
            from ai.question_answerer import AIQuestionAnswerer
            from ai.recruiter_message import AIRecruiterMessageGenerator

            self.groq_client = GroqClient(
                model_override=groq_model,
                temperature_override=temperature,
                max_tokens_override=max_tokens
            )
            self.ai_cache = AICache(enabled=ai_cfg.get("cache", True))
            self.ai_validator = AIValidator(self.groq_client)
            self.ai_analyzer = AIAnalyzer(self.groq_client, self.ai_cache)
            self.ai_resume_ranker = AIResumeRanker(self.groq_client, self.ai_cache)
            self.ai_cover_letter = AICoverLetterGenerator(self.groq_client, self.ai_validator, self.ai_cache)
            self.ai_question_answerer = AIQuestionAnswerer(self.groq_client, self.ai_validator, self.ai_cache)
            self.ai_recruiter_message = AIRecruiterMessageGenerator(self.groq_client, self.ai_validator, self.ai_cache)

            # Load candidate profiles and resumes configs for AI usage
            try:
                with open("config/answers.yaml", "r", encoding="utf-8") as f:
                    self.candidate_profile = yaml.safe_load(f) or {}
            except Exception:
                self.candidate_profile = {}
                
            try:
                with open("config/resumes.yaml", "r", encoding="utf-8") as f:
                    self.resumes_config = yaml.safe_load(f) or {}
            except Exception:
                self.resumes_config = {}
        else:
            self.groq_client = None

        if not self.company and self.site and self.site != "all":
            if self.site == "greenhouse":
                self.company = "reddit"
            elif self.site == "lever":
                self.company = "entrata"

        init_db()
        self.db = SessionLocal()
        
        self.filter_engine = EligibilityFilter()
        self.resume_engine = ResumeSelector()
        self.notifier = NotificationDispatcher(self.config)
        self.telegram_notifier = Notifier()
        
        self.jobs_found = 0
        self.jobs_eligible = 0
        self.jobs_applied = 0
        self.jobs_skipped = 0
        self.errors = 0
        self.otp_pending = 0
        
    def _check_login_status(self, platform: str, page) -> bool:
        url = page.url.lower()
        
        # Define keywords that indicate authentication, signup, checkpoints, OTP, or verification challenges
        auth_keywords = [
            "login", "signin", "signup", "register", "join", "auth",
            "challenge", "checkpoint", "verify", "verification", 
            "otp", "security", "captcha", "mfa", "confirm"
        ]
        
        if any(kw in url for kw in auth_keywords):
            return False
            
        try:
            # Check if body text contains verification or OTP prompts
            body_text = page.locator("body").inner_text().lower()
            if any(w in body_text for w in ["verification code", "security code", "confirm you're a human", "otp", "enter the code", "checkpoint"]):
                return False
                
            if platform == "linkedin":
                if page.locator("input#username").count() > 0 or \
                   page.locator("a:has-text('Sign in')").first.is_visible() or \
                   page.locator("a[href*='/login']").first.is_visible():
                    return False
            elif platform == "naukri":
                if page.locator("a#login_Layer").first.is_visible() or \
                   page.locator("a:has-text('Login')").first.is_visible():
                    return False
            elif platform == "instahyre":
                if page.locator("a[href*='/login']").first.is_visible() or \
                   page.locator("a:has-text('Login')").first.is_visible():
                    return False
            elif platform == "wellfound":
                if page.locator("a[href*='/login']").first.is_visible() or \
                   page.locator("a:has-text('Log In')").first.is_visible():
                    return False
            elif platform == "hirist":
                if page.locator("a[href*='/login']").first.is_visible() or \
                   page.locator("a:has-text('Login')").first.is_visible():
                    return False
            elif platform == "cutshort":
                if page.locator("a:has-text('Login')").first.is_visible() or \
                   page.locator("button:has-text('Login')").first.is_visible():
                    return False
            elif platform == "indeed":
                if page.locator("a[href*='/login']").first.is_visible() or \
                   page.locator("a:has-text('Sign in')").first.is_visible():
                    return False
            elif platform == "foundit":
                if page.locator("a[href*='/login']").first.is_visible() or \
                   page.locator("a:has-text('Login')").first.is_visible():
                    return False
            elif platform == "glassdoor":
                if page.locator("button[data-test='sign-in-button']").first.is_visible() or \
                   page.locator("a:has-text('Sign In')").first.is_visible():
                    return False
        except Exception as e:
            logger.debug(f"Error checking login status selectors: {e}")
        return True

    def __del__(self):
        try:
            self.db.close()
        except:
            pass
            
    def _get_or_create_company(self, company_name: str) -> DBCompany:
        company = self.db.query(DBCompany).filter(DBCompany.name == company_name).first()
        if not company:
            company = DBCompany(
                name=company_name,
                otp_required=False,
                supports_easy_apply=True,
                resume_upload_first=(self.site == "greenhouse"),
                questions_count=0,
                average_completion_time=0.0
            )
            self.db.add(company)
            self.db.commit()
            self.db.refresh(company)
        return company

    def _save_job_state(self, job: Job):
        import datetime
        import hashlib
        company = self._get_or_create_company(job.company)
        
        norm = f"{job.company.strip().lower()}|{job.title.strip().lower()}|{job.url.strip().lower()}"
        job_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
            
        db_job = self.db.query(DBJob).filter(DBJob.job_hash == job_hash).first()
        if not db_job:
            db_job = DBJob(
                title=job.title,
                company_id=company.id,
                location=job.location,
                salary=job.salary,
                description=job.description,
                requirements=job.requirements,
                skills=",".join(job.skills),
                url=job.url,
                site=self.site,
                apply_url=job.url,
                search_keyword=self.search_query,
                job_hash=job_hash,
                date_found=datetime.datetime.utcnow()
            )
            self.db.add(db_job)
            self.db.commit()
            self.db.refresh(db_job)
            
        # Check retry count
        retry_count = 0
        existing_app = self.db.query(DBApplication).filter(DBApplication.job_id == db_job.id).first()
        if existing_app:
            retry_count = (existing_app.retry_count or 0) + 1
            
        date_applied = datetime.datetime.utcnow() if job.applied else None
        
        # Check failure_type and retry_after attributes on Job object
        failure_type = getattr(job, "failure_type", None)
        retry_after  = getattr(job, "retry_after", None)
        
        if existing_app:
            existing_app.resume_used = job.resume_used
            existing_app.match_score = job.score
            existing_app.applied = job.applied
            existing_app.status = job.status
            existing_app.error_message = job.error_message
            existing_app.failure_type = failure_type
            existing_app.screenshot_path = job.screenshot_path
            existing_app.date_applied = date_applied
            existing_app.retry_count = retry_count
            existing_app.retry_after = retry_after
        else:
            app = DBApplication(
                job_id=db_job.id,
                resume_used=job.resume_used,
                match_score=job.score,
                applied=job.applied,
                status=job.status,
                error_message=job.error_message,
                failure_type=failure_type,
                screenshot_path=job.screenshot_path,
                date_applied=date_applied,
                retry_count=retry_count,
                retry_after=retry_after
            )
            self.db.add(app)
        self.db.commit()

    def _save_html_snapshot(self, page, step: str, title: str) -> str:
        import os
        import datetime
        safe_title = "".join([c if c.isalnum() else "_" for c in title]).strip("_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{step}_{safe_title}_{timestamp}.html"
        dir_path = os.path.abspath(os.path.join("screenshots", step))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        path = os.path.join(dir_path, filename)
        try:
            html_content = page.content()
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"HTML snapshot saved: {path}")
            return path
        except Exception as e:
            logger.error(f"Failed to save HTML snapshot: {e}")
            return ""

    def _classify_failure(self, page, exception=None) -> str:
        if exception:
            err_msg = str(exception).lower()
            if "timeout" in err_msg:
                return "NETWORK_ERROR"
            if "resume" in err_msg or "file" in err_msg or "upload" in err_msg:
                return "UPLOAD_FAILED"
            if "selector" in err_msg or "locator" in err_msg or "not found" in err_msg:
                return "UNKNOWN_SELECTOR"
            if "login" in err_msg or "signin" in err_msg:
                return "LOGIN_REQUIRED"
        
        try:
            body_text = page.locator("body").inner_text().lower()
            if any(w in body_text for w in ["verification code", "security code", "confirm you're a human", "otp"]):
                return "OTP_REQUIRED"
            if any(w in body_text for w in ["hcaptcha", "recaptcha", "cloudflare", "captcha", "challenge"]):
                return "CAPTCHA"
            if any(w in body_text for w in ["is required", "field is required", "please enter", "required."]):
                return "VALIDATION_ERROR"
            if any(w in body_text for w in ["rate limit", "too many requests", "blocked", "access denied"]):
                return "RATE_LIMIT"
            if any(w in body_text for w in ["no longer accepting", "application closed", "closed", "position closed"]):
                return "APPLICATION_CLOSED"
            if any(w in body_text for w in ["login", "sign in", "authenticate", "password"]):
                return "LOGIN_REQUIRED"
        except Exception:
            pass
            
        return "UNKNOWN"
        
    def _record_run(self):
        run = DBRun(
            site=self.site,
            jobs_found=self.jobs_found,
            jobs_eligible=self.jobs_eligible,
            jobs_applied=self.jobs_applied,
            jobs_skipped=self.jobs_skipped,
            errors=self.errors
        )
        self.db.add(run)
        self.db.commit()

    def _take_screenshot(self, page, step: str, title: str) -> str:
        import os
        import datetime
        from core.models import DBScreenshot
        
        safe_title = "".join([c if c.isalnum() else "_" for c in title]).strip("_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{step}_{safe_title}_{timestamp}.png"
        dir_path = os.path.abspath(os.path.join("screenshots", step))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        path = os.path.join(dir_path, filename)
        try:
            page.screenshot(path=path, timeout=5000)
            logger.info(f"Screenshot saved: {path}")
            
            # Save to DB
            screenshot_db = DBScreenshot(
                job_title=title,
                step=step,
                path=path
            )
            self.db.add(screenshot_db)
            self.db.commit()
            return path
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return ""

    def _process_retry_queue(self, page):
        from datetime import datetime, timedelta
        logger.info("Pipeline: Checking retry queue for pending jobs...")
        pending_retries = self.db.query(DBApplication).filter(
            DBApplication.status == "failed_retry",
            DBApplication.retry_after <= datetime.utcnow()
        ).all()
        
        if not pending_retries:
            logger.info("Pipeline: No pending retries to process.")
            return

        logger.info(f"Pipeline: Found {len(pending_retries)} jobs in retry queue.")
        for app in pending_retries:
            db_job = app.job
            if not db_job:
                continue
            
            logger.info(f"Pipeline: Retrying job '{db_job.title}' at '{db_job.company.name}' (Attempt {app.retry_count + 1})")
            job = Job(
                id=db_job.external_job_id,
                title=db_job.title,
                company=db_job.company.name,
                location=db_job.location,
                salary=db_job.salary,
                description=db_job.description,
                requirements=db_job.requirements,
                url=db_job.url,
                skills=db_job.skills.split(",") if db_job.skills else [],
                resume_used=app.resume_used
            )
            
            try:
                apply_class = APPLY_ENGINES.get(db_job.site, APPLY_ENGINES["universal"])
                apply_engine = apply_class(page)
                
                # Attach job and AI properties
                apply_engine.job = job
                apply_engine.ai_enabled = self.ai_enabled
                if self.ai_enabled:
                    apply_engine.ai_question_answerer = self.ai_question_answerer
                    apply_engine.candidate_profile = self.candidate_profile
                    apply_engine.resumes_config = self.resumes_config
                    # Generate/Retrieve cover letter if enabled
                    resume_text = self.ai_resume_ranker._extract_pdf_text(job.resume_used)
                    cover_letter = self.ai_cover_letter.generate(
                        job_title=job.title,
                        company=job.company,
                        job_description=job.description,
                        resume_text=resume_text,
                        profile_details=self.candidate_profile
                    )
                    if cover_letter:
                        job.cover_letter = cover_letter
                        job.cover_letter_generated = True
                        if hasattr(apply_engine, "answers") and isinstance(apply_engine.answers, dict):
                            apply_engine.answers["cover_letter"] = job.cover_letter
                        if hasattr(apply_engine, "filler") and hasattr(apply_engine.filler, "answers") and isinstance(apply_engine.filler.answers, dict):
                            apply_engine.filler.answers["cover_letter"] = job.cover_letter

                start_time = time.time()
                success = apply_engine.apply(job, dry_run=self.dry_run)
                duration = time.time() - start_time
                
                company_db = self._get_or_create_company(job.company)
                
                if success:
                    app.applied = True
                    app.status = "applied"
                    app.error_message = ""
                    app.failure_type = None
                    app.date_applied = datetime.utcnow()
                    logger.info(f"Pipeline: Retry successful for job '{job.title}'!")
                else:
                    failure_type = self._classify_failure(page)
                    app.retry_count += 1
                    app.failure_type = failure_type
                    
                    if app.retry_count >= 3:
                        app.status = "failed_permanently"
                        app.error_message = f"Max retries exceeded: {failure_type}"
                        logger.warning(f"Pipeline: Retry failed permanently for job '{job.title}'.")
                    else:
                        app.status = "failed_retry"
                        interval = 3600 if app.retry_count == 1 else 86400
                        app.retry_after = datetime.utcnow() + timedelta(seconds=interval)
                        app.error_message = f"Attempt {app.retry_count} failed: {failure_type}"
                        logger.warning(f"Pipeline: Retry attempt {app.retry_count} failed. Rescheduled.")
                        
                self.db.commit()
            except Exception as e:
                logger.error(f"Pipeline: Retry process error: {e}")

    def _resume_otp_applications(self, page):
        from datetime import datetime
        logger.info("Pipeline: Resuming OTP/verification code applications...")
        otp_apps = self.db.query(DBApplication).filter(
            DBApplication.status == "otp_required"
        ).all()
        
        if not otp_apps:
            logger.info("Pipeline: No applications pending OTP verification.")
            return
            
        logger.info(f"Pipeline: Found {len(otp_apps)} applications pending OTP.")
        for app in otp_apps:
            db_job = app.job
            if not db_job:
                continue
                
            logger.info(f"Pipeline: Opening OTP verification page for '{db_job.title}' at '{db_job.company.name}'")
            job = Job(
                id=db_job.external_job_id,
                title=db_job.title,
                company=db_job.company.name,
                location=db_job.location,
                salary=db_job.salary,
                description=db_job.description,
                requirements=db_job.requirements,
                url=db_job.url,
                skills=db_job.skills.split(",") if db_job.skills else [],
                resume_used=app.resume_used
            )
            
            try:
                apply_class = APPLY_ENGINES.get(db_job.site, APPLY_ENGINES["universal"])
                apply_engine = apply_class(page)
                
                # Attach job and AI properties
                apply_engine.job = job
                apply_engine.ai_enabled = self.ai_enabled
                if self.ai_enabled:
                    apply_engine.ai_question_answerer = self.ai_question_answerer
                    apply_engine.candidate_profile = self.candidate_profile
                    apply_engine.resumes_config = self.resumes_config
                    
                success = apply_engine.apply(job, dry_run=False)
                if success:
                    app.applied = True
                    app.status = "applied"
                    app.error_message = ""
                    app.failure_type = None
                    app.date_applied = datetime.utcnow()
                    logger.info(f"Pipeline: OTP application completed successfully for '{job.title}'!")
                else:
                    failure_type = self._classify_failure(page)
                    app.failure_type = failure_type
                    if failure_type != "OTP_REQUIRED":
                        app.status = "failed_retry"
                        app.retry_after = datetime.utcnow() + datetime.timedelta(hours=1)
                        app.retry_count = 0
                self.db.commit()
            except Exception as e:
                logger.error(f"Pipeline: OTP resumption failed: {e}")

    def _dispatch_summary(self):
        summary = (
            f"AI Job Agent Run Summary - {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"--------------------------------------------------\n"
            f"ATS Boards Scanned:  {self.site or 'all'}\n"
            f"Jobs Discovered:     {self.jobs_found}\n"
            f"Eligible Matches:    {self.jobs_eligible}\n"
            f"Applied:             {self.jobs_applied}\n"
            f"OTP Pending:         {self.otp_pending}\n"
            f"Skipped / Throttled: {self.jobs_skipped}\n"
            f"Errors Encountered:  {self.errors}\n"
            f"--------------------------------------------------\n"
        )
        self.notifier.send_summary(summary)

    def run(self):
        logger.info("=" * 50)
        logger.info(f"STARTING PIPELINE for site '{self.site or 'all'}'")
        logger.info("=" * 50)
        
        with PlaywrightManager(headless=self.headless) as context:
            page = context.new_page()
            
            # ── A. OTP Resumption Mode ───────────────────────────────────────
            if self.resume_otp_only:
                self._resume_otp_applications(page)
                logger.info("Pipeline OTP Resumption Finished.")
                return

            # ── B. Retry Queue Execution ──────────────────────────────────────
            self._process_retry_queue(page)
            
            # ── C. Multi-Board Target Matrix Resolving ────────────────────────
            keywords = []
            if self.search_query:
                keywords = [self.search_query]
            else:
                keywords = self.config.get("search_keywords", [])
                if not keywords:
                    keywords = ["engineer"]

            ORDERED_PLATFORMS = [
                "naukri",
                "instahyre",
                "wellfound",
                "hirist",
                "cutshort",
                "indeed",
                "foundit",
                "glassdoor",
                "linkedin",
                "greenhouse",
                "lever",
                "ashby",
                "workable"
            ]
            
            targets = []
            if self.site and self.site != "all":
                if self.company:
                    targets.append((self.site, self.company))
                else:
                    companies = self.config.get("boards", {}).get(self.site, [])
                    for c in companies:
                        targets.append((self.site, c))
            else:
                for platform in ORDERED_PLATFORMS:
                    companies = self.config.get("boards", {}).get(platform, [])
                    for c in companies:
                        targets.append((platform, c))
                        
            if not targets:
                logger.warning("Pipeline: No active targets configured. Stopping execution.")
                return
                
            logger.info(f"Pipeline: Resolved targets for scanning: {targets}")
            
            platforms_list = list(set([t[0] for t in targets]))
            self.telegram_notifier.notify_pipeline_start(
                platforms=platforms_list,
                keywords=keywords,
                location=self.location,
                dry_run=self.dry_run
            )
            
            for platform, company_slug in targets:
                # Check Daily and Hourly Throttle limits
                from datetime import datetime, timedelta
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                daily_applied = self.db.query(DBApplication).filter(
                    DBApplication.applied == True,
                    DBApplication.timestamp >= today_start
                ).count()
                
                max_daily = self.config.get("limits", {}).get("max_daily_applications", 15)
                if daily_applied >= max_daily:
                    logger.warning(f"Pipeline: Daily limit of {max_daily} applications reached. Throttling active.")
                    break
                    
                hour_ago = datetime.utcnow() - timedelta(hours=1)
                hourly_applied = self.db.query(DBApplication).filter(
                    DBApplication.applied == True,
                    DBApplication.timestamp >= hour_ago
                ).count()
                
                max_hourly = self.config.get("limits", {}).get("max_hourly_applications", 3)
                if hourly_applied >= max_hourly:
                    logger.warning(f"Pipeline: Hourly limit of {max_hourly} applications reached. Throttling active.")
                    break

                # Verify login status for job boards before searching
                PORTAL_HOMEPAGES = {
                    "linkedin": "https://www.linkedin.com",
                    "naukri": "https://www.naukri.com",
                    "instahyre": "https://www.instahyre.com",
                    "wellfound": "https://wellfound.com",
                    "hirist": "https://www.hirist.com",
                    "cutshort": "https://cutshort.io",
                    "indeed": "https://www.indeed.com",
                    "foundit": "https://www.foundit.in",
                    "glassdoor": "https://www.glassdoor.com"
                }
                
                if platform in PORTAL_HOMEPAGES:
                    homepage_url = PORTAL_HOMEPAGES[platform]
                    logger.info(f"Pipeline: Verifying user session login for '{platform}' at {homepage_url}")
                    try:
                        page.goto(homepage_url, wait_until="domcontentloaded", timeout=15000)
                        time.sleep(2)
                        
                        is_logged_in = self._check_login_status(platform, page)
                        if not is_logged_in:
                            alert_msg = f"🔑 *{platform.capitalize()} Login Required*\n\nPlease log in manually in the browser window\\."
                            logger.warning(f"Pipeline: User not logged in on '{platform}'. Prompting for manual login...")
                            self.telegram_notifier.telegram.send(alert_msg)
                            
                            # Wait up to 120 seconds checking login status every 3 seconds
                            login_success = False
                            for elapsed in range(0, 120, 3):
                                logger.info(f"Pipeline: Waiting for manual login on '{platform}' ({elapsed}s elapsed)...")
                                time.sleep(3)
                                if self._check_login_status(platform, page):
                                    # Double check after a short delay to ensure any page redirections are settled
                                    time.sleep(4)
                                    if self._check_login_status(platform, page):
                                        login_success = True
                                        break
                                    
                            if login_success:
                                logger.info(f"Pipeline: Manual login detected for '{platform}'! Continuing.")
                                self.telegram_notifier.telegram.send(f"✅ *{platform.capitalize()} Connected*")
                            else:
                                logger.error(f"Pipeline: Login timeout for '{platform}'. Skipping platform.")
                                self.telegram_notifier.telegram.send(f"❌ *{platform.capitalize()} Login Timeout*\n\nSkipping platform target\\.")
                                continue
                        else:
                            logger.info(f"Pipeline: Active login session verified for '{platform}'.")
                    except Exception as check_err:
                        logger.warning(f"Pipeline: Failed to check login status for '{platform}': {check_err}")

                search_class = SEARCH_ENGINES.get(platform)
                if not search_class:
                    logger.error(f"Search engine for platform '{platform}' not found. Skipping.")
                    continue
                    
                search_engine = search_class(page)
                
                logger.info(f"Pipeline: Running target scan on company '{company_slug}' via platform '{platform}'")
                
                # Fetch jobs for all search keywords and aggregate them
                all_discovered_jobs = []
                seen_urls = set()
                
                for kw in keywords:
                    logger.info(f"Pipeline: Scanning company '{company_slug}' via platform '{platform}' using keyword '{kw}'")
                    try:
                        import inspect
                        sig = inspect.signature(search_engine.search)
                        if "location" in sig.parameters:
                            jobs_for_kw = search_engine.search(company_slug, kw, location=self.location or "India")
                        else:
                            jobs_for_kw = search_engine.search(company_slug, kw)
                            
                        for j in jobs_for_kw:
                            if j.url not in seen_urls:
                                seen_urls.add(j.url)
                                all_discovered_jobs.append(j)
                                self.telegram_notifier.notify_job_found(
                                    company=j.company,
                                    role=j.title,
                                    platform=platform,
                                    location=j.location
                                )
                    except Exception as e:
                        logger.error(f"Pipeline: Failed scraping keyword '{kw}': {e}")
                
                self._take_screenshot(page, "search", f"Search_{platform}_{company_slug}")
                jobs = all_discovered_jobs
                
                if self.limit > 0:
                    jobs = jobs[:self.limit]
                self.jobs_found += len(jobs)
                
                parser_class = PARSER_ENGINES.get(platform)
                if not parser_class:
                    logger.error(f"Pipeline: Parser for platform '{platform}' not found. Skipping.")
                    continue
                parser = parser_class(page)
                
                apply_class = APPLY_ENGINES.get(platform)
                if not apply_class:
                    logger.error(f"Pipeline: Apply engine for platform '{platform}' not found. Skipping.")
                    continue
                apply_engine = apply_class(page)
                
                for job in jobs:
                    # ── Duplication Check (Never Apply Twice) ────────────────
                    import hashlib
                    norm = f"{job.company.strip().lower()}|{job.title.strip().lower()}|{job.url.strip().lower()}"
                    job_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
                    
                    db_job = self.db.query(DBJob).filter(DBJob.job_hash == job_hash).first()
                    if db_job:
                        existing_app = self.db.query(DBApplication).filter(DBApplication.job_id == db_job.id).first()
                        if existing_app:
                            # 1. If it was already applied for real, skip it
                            if existing_app.applied or existing_app.status == "applied":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Already applied")
                                self.jobs_skipped += 1
                                continue
                            # 2. If it was a dry-run and we are still doing dry-runs, skip it
                            if existing_app.status == "dry_run" and self.dry_run:
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Already dry-runned")
                                self.jobs_skipped += 1
                                continue
                            # 3. If it is pending review and we are still in review mode, skip it
                            if existing_app.status == "pending_review" and self.review_required:
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Already pending review")
                                self.jobs_skipped += 1
                                continue
                            
                    # ── Company daily limits check ──────────────────────────
                    company_db = self._get_or_create_company(job.company)
                    day_ago = datetime.utcnow() - timedelta(days=1)
                    company_applied = self.db.query(DBApplication).join(DBJob).filter(
                        DBJob.company_id == company_db.id,
                        DBApplication.applied == True,
                        DBApplication.timestamp >= day_ago
                    ).count()
                    
                    max_company = self.config.get("limits", {}).get("max_applications_per_company", 2)
                    if company_applied >= max_company:
                        logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Daily company limit reached")
                        self.jobs_skipped += 1
                        job.status = "skipped"
                        self._save_job_state(job)
                        continue
                        
                    try:
                        # Parse
                        job = parser.extract_details(job)
                        job.screenshot_path = self._take_screenshot(page, "job", job.title)
                        
                        if getattr(job, "status", "") == "external_redirect":
                            logger.info(f"Pipeline: Skipped '{job.title}' - Reason: External redirect")
                            self.jobs_skipped += 1
                            self._save_job_state(job)
                            continue
                            
                        if getattr(job, "status", "") == "no_auto_apply":
                            logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Platform does not support auto-apply")
                            self.jobs_skipped += 1
                            self._save_job_state(job)
                            continue
                            
                        if job.error_message:
                            logger.error(f"Pipeline: Parsing failed for '{job.title}': {job.error_message}")
                            self.errors += 1
                            job.status = "error"
                            self._save_job_state(job)
                            
                            from core.models import DBError
                            self.db.add(DBError(job_title=job.title, error_message=job.error_message))
                            self.db.commit()
                            continue
                        
                        # Filter
                        is_location_mismatch = False
                        if self.location:
                            loc_query = self.location.lower().strip()
                            job_loc = job.location.lower().strip()
                            if loc_query == "india":
                                INDIA_LOCATIONS = [
                                    "india",
                                    "bangalore",
                                    "bengaluru",
                                    "hyderabad",
                                    "pune",
                                    "chennai",
                                    "mumbai",
                                    "gurgaon",
                                    "gurugram",
                                    "noida",
                                    "delhi",
                                    "kolkata",
                                    "ahmedabad",
                                    "remote - india",
                                ]
                                # Allow remote, wfh, anywhere, or empty locations to bypass strict location filters
                                if job_loc == "" or any(term in job_loc for term in ["remote", "anywhere", "wfh", "work from home"]):
                                    is_location_mismatch = False
                                elif not any(l_token in job_loc for l_token in INDIA_LOCATIONS):
                                    is_location_mismatch = True
                            else:
                                if job_loc != "" and loc_query not in job_loc and not any(term in job_loc for term in ["remote", "anywhere"]):
                                    is_location_mismatch = True
                                    
                        if is_location_mismatch:
                            logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Location mismatch")
                            self.jobs_skipped += 1
                            job.status = "skipped"
                            self._save_job_state(job)
                            continue
                            
                        job = self.filter_engine.score_job(job)
                        if not job.would_apply:
                            logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Keyword mismatch ({getattr(job, 'filter_reason', 'No match')})")
                            self.jobs_skipped += 1
                            job.status = "skipped"
                            self._save_job_state(job)
                            continue
                            
                        self.jobs_eligible += 1
                        
                        # ── AI Flow ──────────────────────────────────────────
                        if self.ai_enabled and self.groq_client and self.groq_client.client:
                            # 1. AI Job Analyzer
                            ai_analysis = self.ai_analyzer.analyze_job(
                                job_title=job.title,
                                company=job.company,
                                job_description=job.description,
                                job_skills=job.skills,
                                job_requirements=job.requirements,
                                candidate_profile=self.candidate_profile,
                                resumes_data=self.resumes_config
                            )
                            
                            job.score = ai_analysis.get("match_score", job.score)
                            job.ai_reasoning = ai_analysis.get("reasoning", "")
                            job.ai_strengths = ai_analysis.get("strengths", [])
                            job.ai_missing_skills = ai_analysis.get("missing_skills", [])
                            
                            should_apply = ai_analysis.get("should_apply", True)
                            if not should_apply:
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: AI match score {job.score} too low")
                                self.jobs_skipped += 1
                                job.status = "skipped"
                                self._save_job_state(job)
                                continue
                                
                            logger.info(f"Pipeline: AI approved job '{job.title}' (AI Match Score: {job.score})")
                            
                            # 2. AI Resume Selector / Ranker
                            rank_result = self.ai_resume_ranker.rank_resumes(
                                job_description=job.description,
                                company=job.company,
                                role=job.title
                            )
                            recommended_key = rank_result.get("resume", "general")
                            job.resume_used = self.ai_resume_ranker.resolve_resume(recommended_key)
                            logger.info(f"Pipeline: AI selected resume: {job.resume_used} (Reason: {rank_result.get('reason')})")
                            
                            # 3. Cover Letter Generation
                            job.cover_letter_generated = False
                            resume_text = self.ai_resume_ranker._extract_pdf_text(job.resume_used)
                            cover_letter = self.ai_cover_letter.generate(
                                job_title=job.title,
                                company=job.company,
                                job_description=job.description,
                                resume_text=resume_text,
                                profile_details=self.candidate_profile
                            )
                            if cover_letter:
                                job.cover_letter = cover_letter
                                job.cover_letter_generated = True
                                logger.info("Pipeline: AI successfully generated a cover letter.")
                        else:
                            # Resume Selector (Deterministic)
                            if self.resume and self.resume.lower() != "auto":
                                job.resume_used = self.resume
                            else:
                                job = self.resume_engine.select(job)
                                
                        # Attach job and AI properties to the apply engine
                        apply_engine.job = job
                        apply_engine.ai_enabled = self.ai_enabled
                        if self.ai_enabled:
                            apply_engine.ai_question_answerer = self.ai_question_answerer
                            apply_engine.candidate_profile = self.candidate_profile
                            apply_engine.resumes_config = self.resumes_config
                            if job.cover_letter_generated and job.cover_letter:
                                if hasattr(apply_engine, "answers") and isinstance(apply_engine.answers, dict):
                                    apply_engine.answers["cover_letter"] = job.cover_letter
                                if hasattr(apply_engine, "filler") and hasattr(apply_engine.filler, "answers") and isinstance(apply_engine.filler.answers, dict):
                                    apply_engine.filler.answers["cover_letter"] = job.cover_letter
                            
                        self.telegram_notifier.notify_job_matched(
                            score=job.score,
                            resume=job.resume_used or "Resume.pdf",
                            company=job.company,
                            role=job.title,
                            reasoning=getattr(job, "ai_reasoning", ""),
                            cover_letter_generated=getattr(job, "cover_letter_generated", False)
                        )
                            
                        # Mimic human actions delay before applying
                        if not self.dry_run and self.config.get("scheduler", {}).get("random_delay", True):
                            import random
                            delay = random.randint(
                                self.config.get("scheduler", {}).get("delay_min", 30),
                                self.config.get("scheduler", {}).get("delay_max", 180)
                            )
                            logger.info(f"Pipeline: Sleeping {delay}s for human-like timing rhythm...")
                            time.sleep(delay)
                            
                        def screenshot_cb(step: str):
                            self._take_screenshot(page, step, job.title)
                            
                        # Apply Execution phase
                        start_time = time.time()
                        
                        if self.dry_run:
                            success = apply_engine.apply(job, dry_run=True, screenshot_cb=screenshot_cb)
                            if getattr(job, "status", "") == "external_redirect":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: External redirect")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            if getattr(job, "status", "") == "no_auto_apply":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Platform does not support auto-apply")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            job.status = "dry_run"
                        elif self.review_required:
                            # Run form filling only (Review Queue)
                            logger.info(f"Pipeline: Review Required flag active. Stalling submission for {job.title}.")
                            success = apply_engine.apply(job, dry_run=True, screenshot_cb=screenshot_cb)
                            if getattr(job, "status", "") == "external_redirect":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: External redirect")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            if getattr(job, "status", "") == "no_auto_apply":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Platform does not support auto-apply")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            job.status = "pending_review"
                            job.screenshot_path = self._take_screenshot(page, "before_submit", job.title)
                        else:
                            success = apply_engine.apply(job, dry_run=False, screenshot_cb=screenshot_cb)
                            if getattr(job, "status", "") == "external_redirect":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: External redirect")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            if getattr(job, "status", "") == "no_auto_apply":
                                logger.info(f"Pipeline: Skipped '{job.title}' - Reason: Platform does not support auto-apply")
                                self.jobs_skipped += 1
                                self._save_job_state(job)
                                continue
                            duration = time.time() - start_time
                            
                            if success:
                                self.jobs_applied += 1
                                job.applied = True
                                job.status = "applied"
                                job.screenshot_path = self._take_screenshot(page, "after_submit", job.title)
                                
                                old_avg = company_db.average_completion_time or 0.0
                                if old_avg == 0.0:
                                    company_db.average_completion_time = duration
                                else:
                                    company_db.average_completion_time = (old_avg * 4 + duration) / 5
                                    
                                self.telegram_notifier.notify_apply_success(
                                    company=job.company,
                                    role=job.title,
                                    platform=platform,
                                    location=job.location,
                                    resume=job.resume_used or "Resume.pdf",
                                    url=job.url,
                                    score=job.score,
                                    screenshot_path=job.screenshot_path
                                )
                            else:
                                failure_type = self._classify_failure(page)
                                job.failure_type = failure_type
                                job.error_message = failure_type
                                job.screenshot_path = self._take_screenshot(page, "error", job.title)
                                self._save_html_snapshot(page, "error", job.title)
                                
                                self.telegram_notifier.notify_apply_failed(
                                    company=job.company,
                                    role=job.title,
                                    reason=failure_type,
                                    screenshot_path=job.screenshot_path
                                )
                                
                                if failure_type == "OTP_REQUIRED":
                                    job.status = "otp_required"
                                    self.otp_pending += 1
                                    company_db.otp_required = True
                                    logger.warning(f"Pipeline: Application verification code required for '{job.company}'")
                                else:
                                    job.status = "failed_retry"
                                    self.errors += 1
                                    job.retry_after = datetime.utcnow() + timedelta(hours=1)
                                    logger.warning(f"Pipeline: Application failed with {failure_type}. Added to retry queue.")
                                    
                                    # Calculate retry attempt number
                                    retry_attempt = 1
                                    try:
                                        db_j = self.db.query(DBJob).filter(DBJob.external_job_id == job.id).first()
                                        if db_j:
                                            ex_app = self.db.query(DBApplication).filter(DBApplication.job_id == db_j.id).first()
                                            if ex_app:
                                                retry_attempt = (ex_app.retry_count or 0) + 1
                                    except:
                                        pass
                                        
                                    self.telegram_notifier.notify_retry_scheduled(
                                        company=job.company,
                                        reason=failure_type,
                                        retry_after=job.retry_after,
                                        attempt=retry_attempt
                                    )
                                    
                        # Update company profile stats
                        if hasattr(apply_engine, "question_handler"):
                            company_db.questions_count = len(getattr(apply_engine, "question_handler").dropdowns) + \
                                                         len(getattr(apply_engine, "question_handler").free_text)
                                                         
                        self.db.commit()
                        self._save_job_state(job)
                        
                    except Exception as e:
                        logger.error(f"Pipeline error on job {job.title}: {e}")
                        self.errors += 1
                        try:
                            self._take_screenshot(page, "error", job.title)
                            self._save_html_snapshot(page, "error", job.title)
                        except:
                            pass
                            
                        failure_type = self._classify_failure(page, e)
                        job.status = "failed_retry"
                        job.failure_type = failure_type
                        job.error_message = f"{failure_type}: {e}"
                        
                        from datetime import datetime, timedelta
                        job.retry_after = datetime.utcnow() + timedelta(hours=1)
                        self._save_job_state(job)
                        
                        self.telegram_notifier.notify_apply_failed(
                            company=job.company,
                            role=job.title,
                            reason=f"{failure_type}: {e}",
                            screenshot_path=getattr(job, "screenshot_path", None)
                        )
                        
                        retry_attempt = 1
                        try:
                            db_j = self.db.query(DBJob).filter(DBJob.external_job_id == job.id).first()
                            if db_j:
                                ex_app = self.db.query(DBApplication).filter(DBApplication.job_id == db_j.id).first()
                                if ex_app:
                                    retry_attempt = (ex_app.retry_count or 0) + 1
                        except:
                            pass
                            
                        self.telegram_notifier.notify_retry_scheduled(
                            company=job.company,
                            reason=f"{failure_type}: {e}",
                            retry_after=job.retry_after,
                            attempt=retry_attempt
                        )
                        
                        from core.models import DBError
                        self.db.add(DBError(job_title=job.title, error_message=f"{failure_type}: {e}"))
                        self.db.commit()
                        
                # Random delay between company transitions (10-30 seconds with progress updates)
                if not self.dry_run and len(targets) > 1 and (platform, company_slug) != targets[-1]:
                    import random
                    transition_delay = random.randint(10, 30)
                    logger.info(f"Pipeline: Completed board target '{company_slug}' via platform '{platform}'. Sleeping {transition_delay}s before the next company target...")
                    for remaining in range(transition_delay, 0, -5):
                        logger.info(f"Pipeline: Continuing in {remaining}s...")
                        time.sleep(min(5, remaining))
                        
        self._record_run()
        self._dispatch_summary()
        
        # Build run statistics for Telegram notifications
        top_platforms = {}
        if 'targets' in locals() and targets:
            for platform, _ in targets:
                top_platforms[platform] = top_platforms.get(platform, 0) + 1
                
        success_rate = int((self.jobs_applied / self.jobs_eligible) * 100) if self.jobs_eligible > 0 else 0
        parsed_count = self.jobs_eligible + self.jobs_skipped + self.errors
        
        stats = {
            "found": self.jobs_found,
            "parsed": parsed_count,
            "matched": self.jobs_eligible,
            "applied": self.jobs_applied,
            "skipped": self.jobs_skipped,
            "failed": self.errors,
            "duplicates": self.jobs_skipped,
            "top_companies": top_platforms,
            "avg_runtime": 5,
            "avg_score": 75 if self.jobs_eligible > 0 else 0,
            "success_rate": success_rate
        }
        
        self.telegram_notifier.notify_pipeline_complete(stats)
        self.telegram_notifier.notify_daily_summary(stats)
        
        logger.info("Pipeline Complete.")
