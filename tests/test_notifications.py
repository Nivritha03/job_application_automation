import os
import unittest
from unittest.mock import patch, MagicMock
from notifications.formatter import escape_markdown, format_pipeline_start, format_job_found, format_job_matched, format_apply_success, format_apply_failed, format_retry_scheduled, format_daily_summary
from notifications.telegram import TelegramNotifier
from notifications.notifier import Notifier

class TestNotifications(unittest.TestCase):
    def test_escape_markdown(self):
        text = "Hello! [World] *Bold* _Italic_ .!"
        escaped = escape_markdown(text)
        self.assertEqual(escaped, "Hello\\! \\[World\\] \\*Bold\\* \\_Italic\\_ \\.\\!")

    def test_formatters(self):
        start_msg = format_pipeline_start("2026-06-28 09:30", ["LinkedIn"], ["Python"], "India", False)
        self.assertIn("AI Job Agent Started", start_msg)
        self.assertIn("LinkedIn", start_msg)
        self.assertIn("Python", start_msg)

        found_msg = format_job_found("Reddit", "Software Engineer", "Greenhouse", "India")
        self.assertIn("New Job Found", found_msg)
        self.assertIn("Reddit", found_msg)

        matched_msg = format_job_matched(72, "backend.pdf", "OpenAI", "Backend Engineer")
        self.assertIn("Job Matched", matched_msg)
        self.assertIn("72", matched_msg)

        success_msg = format_apply_success("OpenAI", "Software Engineer", "Greenhouse", "India", "backend.pdf", "10:24 AM", "https://openai.com", 78)
        self.assertIn("Application Submitted Successfully", success_msg)
        self.assertIn("78", success_msg)

        failed_msg = format_apply_failed("Reddit", "Software Engineer", "Captcha")
        self.assertIn("Application Failed", failed_msg)
        self.assertIn("Captcha", failed_msg)

        retry_msg = format_retry_scheduled("Reddit", "Captcha", "11:24 AM", 2)
        self.assertIn("Retry Scheduled", retry_msg)
        self.assertIn("2", retry_msg)

        stats = {
            "found": 10,
            "parsed": 8,
            "matched": 5,
            "applied": 3,
            "skipped": 2,
            "failed": 1,
            "duplicates": 2,
            "top_companies": {"LinkedIn": 2, "Indeed": 1},
            "avg_runtime": 12,
            "avg_score": 82,
            "success_rate": 60
        }
        summary_msg = format_daily_summary(stats)
        self.assertIn("Daily Summary", summary_msg)
        self.assertIn("60%", summary_msg)

    @patch("urllib.request.urlopen")
    def test_telegram_notifier_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        notifier = TelegramNotifier(bot_token="fake_token", chat_id="fake_chat", enabled=True)
        res = notifier.send("Test message")
        self.assertTrue(res)

    @patch("urllib.request.urlopen")
    def test_telegram_notifier_backoff(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection Refused")

        notifier = TelegramNotifier(bot_token="fake_token", chat_id="fake_chat", enabled=True)
        with patch("time.sleep") as mock_sleep:
            res = notifier.send("Test message")
            self.assertFalse(res)
            self.assertEqual(mock_urlopen.call_count, 3)
            self.assertEqual(mock_sleep.call_count, 2)

    def test_notifier_disabled(self):
        notifier = Notifier()
        notifier.config["telegram"]["enabled"] = False
        notifier.telegram.enabled = False
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            notifier.notify_job_found("Company", "Role", "Platform", "Location")
            mock_urlopen.assert_not_called()
