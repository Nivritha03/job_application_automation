import os
import yaml
import threading
import datetime
from loguru import logger
from notifications.telegram import TelegramNotifier
from notifications.formatter import (
    format_pipeline_start,
    format_job_found,
    format_job_matched,
    format_apply_success,
    format_apply_failed,
    format_retry_scheduled,
    format_daily_summary
)

class Notifier:
    def __init__(self, config_path: str = "config/notifications.yaml"):
        # Default config structure
        self.config = {
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            },
            "notifications": {
                "on_job_found": False,
                "on_match": False,
                "on_apply_success": True,
                "on_apply_failed": True,
                "on_retry": True,
                "on_pipeline_start": True,
                "on_pipeline_complete": True,
                "on_daily_summary": True
            }
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        # Deep merge configs
                        if "telegram" in file_config:
                            self.config["telegram"].update(file_config["telegram"])
                        if "notifications" in file_config:
                            self.config["notifications"].update(file_config["notifications"])
        except Exception as e:
            logger.error(f"Notifier: Failed to load config from {config_path}: {e}")
            
        # Support environment variables override
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or self.config["telegram"].get("bot_token") or ""
        chat_id = os.environ.get("TELEGRAM_CHAT_ID") or self.config["telegram"].get("chat_id") or ""
        enabled = self.config["telegram"].get("enabled", False)
        
        # Override values in internal config dictionary
        self.config["telegram"]["bot_token"] = bot_token
        self.config["telegram"]["chat_id"] = chat_id
        
        # Initialize TelegramNotifier
        self.telegram = TelegramNotifier(
            bot_token=bot_token,
            chat_id=chat_id,
            enabled=enabled
        )
        
        # Ensure log directory exists
        os.makedirs("logs", exist_ok=True)
        self.log_path = "logs/notifications.log"

    def _log_notification(self, message: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message.strip()}\n" + "-"*80 + "\n")
        except Exception as e:
            logger.error(f"Notifier: Failed to write to {self.log_path}: {e}")

    def _async_send(self, send_func, *args, **kwargs):
        # Asynchronously dispatch to avoid blocking playwright automation
        def run_thread():
            try:
                send_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Notifier: Asynchronous notification dispatch failed: {e}")
        threading.Thread(target=run_thread, daemon=True).start()

    def notify_pipeline_start(self, platforms: list, keywords: list, location: str, dry_run: bool):
        if not self.config["notifications"].get("on_pipeline_start", True):
            return
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = format_pipeline_start(time_str, platforms, keywords, location, dry_run)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)

    def notify_job_found(self, company: str, role: str, platform: str, location: str):
        if not self.config["notifications"].get("on_job_found", False):
            return
        msg = format_job_found(company, role, platform, location)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)

    def notify_job_matched(self, score: int, resume: str, company: str, role: str):
        if not self.config["notifications"].get("on_match", False):
            return
        msg = format_job_matched(score, resume, company, role)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)

    def notify_apply_success(self, company: str, role: str, platform: str, location: str, resume: str, url: str, score: int, screenshot_path: str = None, app_id: str = None):
        if not self.config["notifications"].get("on_apply_success", True):
            return
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = format_apply_success(company, role, platform, location, resume, time_str, url, score, app_id)
        
        self._log_notification(msg)
        if screenshot_path and os.path.exists(screenshot_path):
            self._async_send(self.telegram.send_photo, screenshot_path, msg)
        else:
            self._async_send(self.telegram.send, msg)

    def notify_apply_failed(self, company: str, role: str, reason: str, screenshot_path: str = None):
        if not self.config["notifications"].get("on_apply_failed", True):
            return
        msg = format_apply_failed(company, role, reason)
        
        self._log_notification(msg)
        if screenshot_path and os.path.exists(screenshot_path):
            self._async_send(self.telegram.send_photo, screenshot_path, msg)
        else:
            self._async_send(self.telegram.send, msg)

    def notify_retry_scheduled(self, company: str, reason: str, retry_after: datetime.datetime, attempt: int):
        if not self.config["notifications"].get("on_retry", True):
            return
        retry_after_str = retry_after.strftime("%Y-%m-%d %H:%M")
        msg = format_retry_scheduled(company, reason, retry_after_str, attempt)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)

    def notify_pipeline_complete(self, stats: dict):
        if not self.config["notifications"].get("on_pipeline_complete", True):
            return
        msg = f"🏁 *AI Job Agent Pipeline Complete*\n\n📊 *Final Metrics Summary:*\n" + format_daily_summary(stats)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)
        
    def notify_daily_summary(self, stats: dict):
        if not self.config["notifications"].get("on_daily_summary", True):
            return
        msg = format_daily_summary(stats)
        
        self._log_notification(msg)
        self._async_send(self.telegram.send, msg)
