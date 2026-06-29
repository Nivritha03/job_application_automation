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
    
    target_site = "all" if args.all else (args.site or "all")
    
    def job_func():
        logger.info(f"Scheduler: Starting automated job search cycle for site '{target_site}'")
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
            review_required=args.review,
            headless=True,
            global_search=args.global_search
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
    parser.add_argument("--search", type=str, default="", help="Search query for job openings (loads keywords from config.yaml if empty)")
    parser.add_argument("--company", type=str, default="", help="Target company slug for direct scraping (e.g., reddit, entrata)")
    parser.add_argument("--limit", type=int, default=5, help="Limit number of jobs to process")
    parser.add_argument("--resume", type=str, default="auto", help="Resume selection category or filepath override")
    parser.add_argument("--location", type=str, default="", help="Filter jobs matching specific location")
    parser.add_argument("--remote-only", action="store_true", help="Filter and apply only to remote-friendly roles")
    parser.add_argument("--dry-run", action="store_true", help="Run the pipeline without submitting applications")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dashboard", action="store_true", help="Show the metrics dashboard")
    parser.add_argument("--scheduler", action="store_true", help="Run in scheduler mode")
    parser.add_argument("--global-search", action="store_true", help="Skip India location constraints")
    parser.add_argument("--debug", action="store_true", help="Enable debug level output logs")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose outputs")
    parser.add_argument("--max-pages", type=int, default=1, help="Max pages of listings to traverse")
    parser.add_argument("--review", action="store_true", help="Enable human review queue before submission")
    parser.add_argument("--resume-otp", action="store_true", help="Resume applications currently stalled waiting for email verification codes")
    parser.add_argument("--test-telegram", action="store_true", help="Verify Telegram configuration and send a test message")
    
    args = parser.parse_args()
    
    if args.debug or args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
        logger.debug("Debug logging enabled.")
        
    if getattr(args, "test_telegram", False):
        import os
        from notifications.notifier import Notifier
        logger.info("Telegram Notifications Verification Mode Active")
        notifier = Notifier()
        
        bot_token = notifier.config["telegram"].get("bot_token")
        chat_id = notifier.config["telegram"].get("chat_id")
        enabled = notifier.config["telegram"].get("enabled")
        
        print("\n" + "=" * 50)
        print("TELEGRAM NOTIFICATION DIAGNOSTICS REPORT")
        print("=" * 50)
        print(f"Enabled in Config : {enabled}")
        print(f"Bot Token Configured: {bool(bot_token)} (Length: {len(bot_token) if bot_token else 0})")
        print(f"Chat ID Configured  : {bool(chat_id)} (Value: {chat_id if chat_id else 'None'})")
        print("-" * 50)
        
        if not bot_token or not chat_id:
            print("ERROR: Bot Token or Chat ID is missing! Make sure to configure them in config/notifications.yaml or set environment variables.")
            sys.exit(1)
            
        print("Sending test message...")
        test_msg = "🧪 *AI Job Agent Test Notification*\n\nIf you receive this message, your Telegram configuration is working correctly\\!"
        
        success = notifier.telegram.send(test_msg)
        if success:
            print("SUCCESS: Test text message delivered to Telegram.")
        else:
            print("FAILED: Text message delivery failed. Check bot token, chat ID, and connection logs.")
            sys.exit(1)
            
        print("\nUploading sample screenshot...")
        test_img_path = "screenshots/test_telegram_screenshot.png"
        os.makedirs("screenshots", exist_ok=True)
        try:
            found_png = None
            for root, dirs, files_list in os.walk("screenshots"):
                for f_name in files_list:
                    if f_name.lower().endswith(".png") and f_name != "test_telegram_screenshot.png":
                        found_png = os.path.join(root, f_name)
                        break
                if found_png:
                    break
                    
            if found_png:
                import shutil
                shutil.copy(found_png, test_img_path)
                print(f"Using existing screenshot for test upload: {found_png}")
            else:
                png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x02\x00\x00\x00\x02\x80\xb1\xe2\x00\x00\x00\x0cIDATx\x9cc`\xa0\x1c\x00\x00\x00\n\x00\x01\x12\x18qR\x00\x00\x00\x00IEND\xaeB`\x82'
                with open(test_img_path, "wb") as f:
                    f.write(png_bytes)
                print("Generated a 10x10 fallback PNG for test upload.")
                
            photo_success = notifier.telegram.send_photo(
                image_path=test_img_path,
                caption="🖼️ *AI Job Agent Sample Screenshot*\n\nTesting binary screenshot upload\\!"
            )
            if photo_success:
                print("SUCCESS: Sample screenshot uploaded successfully.")
            else:
                print("FAILED: Photo upload failed.")
        except Exception as img_err:
            print(f"FAILED to generate or upload sample image: {img_err}")
        finally:
            if os.path.exists(test_img_path):
                os.remove(test_img_path)
                
        print("=" * 50 + "\n")
        sys.exit(0)
    
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
        resume_otp_only=args.resume_otp,
        global_search=args.global_search
    )
    
    pipeline.run()
    logger.info("Pipeline run finished. Exiting.")

if __name__ == "__main__":
    main()
