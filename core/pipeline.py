from core.browser import PlaywrightManager
from core.database import SessionLocal, init_db
from core.models import Job, DBJob, DBCompany, DBApplication, DBRun
from core.plugins import SEARCH_ENGINES, PARSER_ENGINES, APPLY_ENGINES
from engines.filter.eligibility import EligibilityFilter
from engines.resume.selector import ResumeSelector
from loguru import logger
import time

from core.notifications import NotificationDispatcher
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
        resume_otp_only: bool = False
    ):
        self.site = site
        self.search_query = search_query
        self.company = company
        self.limit = limit
        self.resume = resume
        self.location = location
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
        
        self.jobs_found = 0
        self.jobs_eligible = 0
        self.jobs_applied = 0
        self.jobs_skipped = 0
        self.errors = 0
        self.otp_pending = 0
        
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
                f.write(f) if hasattr(f, "write") else f.write(html_content)
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
            page.screenshot(path=path)
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
            targets = []
            if self.site and self.site != "all":
                if self.company:
                    targets.append((self.site, self.company))
                else:
                    companies = self.config.get("boards", {}).get(self.site, [])
                    for c in companies:
                        targets.append((self.site, c))
            else:
                for platform, companies in self.config.get("boards", {}).items():
                    for c in companies:
                        targets.append((platform, c))
                        
            if not targets:
                logger.warning("Pipeline: No active targets configured. Stopping execution.")
                return
                
            logger.info(f"Pipeline: Resolved targets for scanning: {targets}")
            
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

                search_class = SEARCH_ENGINES.get(platform)
                if not search_class:
                    logger.error(f"Search engine for platform '{platform}' not found. Skipping.")
                    continue
                    
                search_engine = search_class(page)
                
                logger.info(f"Pipeline: Running target scan on company '{company_slug}' via platform '{platform}'")
                try:
                    import inspect
                    sig = inspect.signature(search_engine.search)
                    if "location" in sig.parameters:
                        jobs = search_engine.search(company_slug, self.search_query, location=self.location or "India")
                    else:
                        jobs = search_engine.search(company_slug, self.search_query)
                    self._take_screenshot(page, "search", f"Search_{platform}_{company_slug}")
                except Exception as e:
                    logger.error(f"Pipeline: Failed scraping target board: {e}")
                    continue
                
                if self.limit > 0:
                    jobs = jobs[:self.limit]
                self.jobs_found += len(jobs)
                
                parser_class = PARSER_ENGINES.get(platform, PARSER_ENGINES["default"])
                parser = parser_class(page)
                
                apply_class = APPLY_ENGINES.get(platform, APPLY_ENGINES["universal"])
                apply_engine = apply_class(page)
                
                for job in jobs:
                    # ── Duplication Check (Never Apply Twice) ────────────────
                    import hashlib
                    norm = f"{job.company.strip().lower()}|{job.title.strip().lower()}|{job.url.strip().lower()}"
                    job_hash = hashlib.sha256(norm.encode('utf-8')).hexdigest()
                    
                    db_job = self.db.query(DBJob).filter(DBJob.job_hash == job_hash).first()
                    if db_job:
                        existing_app = self.db.query(DBApplication).filter(DBApplication.job_id == db_job.id).first()
                        if existing_app and (existing_app.applied or existing_app.status in ("applied", "dry_run", "pending_review", "otp_required")):
                            logger.info(f"Pipeline: Skipping duplicate job '{job.title}' (Already processed)")
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
                        logger.info(f"Pipeline: Skipping job at '{job.company}' - Daily company limit of {max_company} reached.")
                        self.jobs_skipped += 1
                        job.status = "skipped"
                        self._save_job_state(job)
                        continue
                        
                    try:
                        # Parse
                        job = parser.extract_details(job)
                        job.screenshot_path = self._take_screenshot(page, "job", job.title)
                        
                        # Filter
                        if self.location and self.location.lower() not in job.location.lower():
                            logger.info(f"Skipping job '{job.title}' - Location '{job.location}' mismatch.")
                            self.jobs_skipped += 1
                            job.status = "skipped"
                            self._save_job_state(job)
                            continue
                            
                        job = self.filter_engine.score_job(job)
                        if not job.would_apply:
                            self.jobs_skipped += 1
                            job.status = "skipped"
                            self._save_job_state(job)
                            continue
                            
                        self.jobs_eligible += 1
                        
                        # Resume Selector
                        if self.resume and self.resume.lower() != "auto":
                            job.resume_used = self.resume
                        else:
                            job = self.resume_engine.select(job)
                            
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
                            job.status = "dry_run"
                        elif self.review_required:
                            # Run form filling only (Review Queue)
                            logger.info(f"Pipeline: Review Required flag active. Stalling submission for {job.title}.")
                            success = apply_engine.apply(job, dry_run=True, screenshot_cb=screenshot_cb)
                            job.status = "pending_review"
                            job.screenshot_path = self._take_screenshot(page, "before_submit", job.title)
                        else:
                            success = apply_engine.apply(job, dry_run=False, screenshot_cb=screenshot_cb)
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
                            else:
                                failure_type = self._classify_failure(page)
                                job.failure_type = failure_type
                                job.error_message = failure_type
                                job.screenshot_path = self._take_screenshot(page, "error", job.title)
                                self._save_html_snapshot(page, "error", job.title)
                                
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
                        
                        from core.models import DBError
                        self.db.add(DBError(job_title=job.title, error_message=f"{failure_type}: {e}"))
                        self.db.commit()
                        
                # Random delay between company transitions (60-300 seconds)
                if not self.dry_run and len(targets) > 1 and (platform, company_slug) != targets[-1]:
                    import random
                    transition_delay = random.randint(60, 300)
                    logger.info(f"Pipeline: Completed board target '{company_slug}' via platform '{platform}'. Sleeping {transition_delay}s before the next company target...")
                    time.sleep(transition_delay)
                        
        self._record_run()
        self._dispatch_summary()
        logger.info("Pipeline Complete.")
