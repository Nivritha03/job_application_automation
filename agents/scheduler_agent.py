from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
import time

class SchedulerAgent:
    def __init__(self, job_func, interval_minutes: int = 120):
        self.scheduler = BackgroundScheduler()
        self.job_func = job_func
        self.interval_minutes = interval_minutes

    def start(self):
        # Calculate random jitter up to 15% of the scheduling interval to avoid rigid patterns
        jitter_sec = int(self.interval_minutes * 60 * 0.15)
        logger.info(f"Starting scheduler. Next run in {self.interval_minutes} minutes (with +/- {jitter_sec}s random jitter).")
        self.scheduler.add_job(self.job_func, 'interval', minutes=self.interval_minutes, jitter=jitter_sec)
        self.scheduler.start()

    def stop(self):
        logger.info("Stopping scheduler.")
        self.scheduler.shutdown()
        
    def wait(self):
        try:
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
