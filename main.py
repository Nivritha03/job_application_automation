import argparse
import yaml
from core.pipeline import Pipeline
from dashboard.terminal import show_dashboard
from loguru import logger
from agents.scheduler_agent import SchedulerAgent

def run_scheduler(args):
    try:
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}
        
    sched_config = config.get("scheduler", {})
    interval = sched_config.get("every_minutes", 120)
    
    def job_func():
        logger.info(f"Scheduler: Starting automated job search cycle for site '{args.site or 'greenhouse'}'")
        pipeline = Pipeline(
            site=args.site or "greenhouse",
            search_query=args.search,
            company=args.company,
            limit=args.limit,
            resume=args.resume,
            location=args.location,
            remote_only=args.remote_only,
            debug=args.debug or args.verbose,
            headless=True
        )
        pipeline.run()
        
    # Execute immediately once
    job_func()
    
    scheduler = SchedulerAgent(job_func, interval_minutes=interval)
    scheduler.start()
    scheduler.wait()

def main():
    import sys
    parser = argparse.ArgumentParser(description="Modular AI Job Agent")
    parser.add_argument("--site", type=str, default="", help="Job board to target (e.g. fallback, greenhouse, lever, linkedin, all)")
    parser.add_argument("--all", action="store_true", help="Scrape and process all configured platforms/companies")
    parser.add_argument("--search", type=str, default="python", help="Search query for job openings")
    parser.add_argument("--company", type=str, default="", help="Target company slug for direct scraping (e.g., reddit, entrata)")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of jobs to process")
    parser.add_argument("--resume", type=str, default="auto", help="Resume selection category or filepath override")
    parser.add_argument("--location", type=str, default="", help="Filter jobs matching specific location")
    parser.add_argument("--remote-only", action="store_true", help="Filter and apply only to remote-friendly roles")
    parser.add_argument("--dry-run", action="store_true", help="Run the pipeline without submitting applications")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dashboard", action="store_true", help="Show the metrics dashboard")
    parser.add_argument("--scheduler", action="store_true", help="Run in scheduler mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug level output logs")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose outputs")
    parser.add_argument("--max-pages", type=int, default=1, help="Max pages of listings to traverse")
    parser.add_argument("--review", action="store_true", help="Enable human review queue before submission")
    parser.add_argument("--resume-otp", action="store_true", help="Resume applications currently stalled waiting for email verification codes")
    
    args = parser.parse_args()
    
    if args.debug or args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
        logger.debug("Debug logging enabled.")
    
    if args.scheduler:
        run_scheduler(args)
        return
        
    target_site = "all" if args.all else args.site
    
    if args.dashboard or (not target_site and not args.resume_otp):
        show_dashboard()
        return
        
    logger.info(f"Initializing engine for site: {target_site or 'OTP Resumption Mode'}")
    
    pipeline = Pipeline(
        site=target_site,
        search_query=args.search,
        company=args.company,
        limit=args.limit,
        resume=args.resume,
        location=args.location,
        remote_only=args.remote_only,
        debug=args.debug or args.verbose,
        dry_run=args.dry_run,
        headless=args.headless,
        review_required=args.review,
        resume_otp_only=args.resume_otp
    )
    
    pipeline.run()
    show_dashboard()

if __name__ == "__main__":
    main()
