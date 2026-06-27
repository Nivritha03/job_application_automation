import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger

class NotificationDispatcher:
    def __init__(self, config: dict):
        self.config = config.get("notifications", {})
        self.enabled = self.config.get("enabled", False)
        self.to_email = self.config.get("to_email", "nivritha.pola@gmail.com")
        self.smtp_server = self.config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = self.config.get("smtp_port", 587)
        self.smtp_username = os.getenv("SMTP_USERNAME") or self.config.get("smtp_username", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD") or self.config.get("smtp_password", "")

    def send_summary(self, summary_text: str):
        # Always log to file first
        os.makedirs("logs", exist_ok=True)
        with open("logs/notifications.log", "a", encoding="utf-8") as f:
            f.write(summary_text + "\n" + "=" * 50 + "\n")

        logger.info("Notification Summary saved to logs/notifications.log")

        if not self.enabled:
            logger.info("Notifications are disabled in config.yaml. Skipping dispatch.")
            return

        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured. Skipping email dispatch.")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_username
            msg["To"] = self.to_email
            msg["Subject"] = "AI Job Agent - Run Summary"

            msg.attach(MIMEText(summary_text, "plain"))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.smtp_username, self.to_email, msg.as_string())
            server.quit()
            logger.info(f"Notification email successfully sent to {self.to_email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
