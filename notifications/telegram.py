import os
import urllib.request
import urllib.parse
import json
import time
from loguru import logger

class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None, enabled: bool = True):
        # Read from environment variables if not passed directly, else fallback to empty
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID") or ""
        self.enabled = enabled
        
    def _send_request(self, method: str, payload: dict, files: dict = None) -> bool:
        if not self.enabled:
            return False
            
        if not self.bot_token or not self.chat_id:
            logger.warning(f"TelegramNotifier: Skipping notify. Token or Chat ID not configured (Token: {bool(self.bot_token)}, Chat ID: {bool(self.chat_id)}).")
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        
        # Exponential backoff retry logic (up to 3 attempts)
        for attempt in range(3):
            try:
                if files:
                    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
                    data = []
                    # Standard parameters
                    for k, v in payload.items():
                        if v is not None:
                            data.append(f'--{boundary}')
                            data.append(f'Content-Disposition: form-data; name="{k}"')
                            data.append('')
                            data.append(str(v))
                            
                    # File parameters
                    for field_name, file_info in files.items():
                        file_path, mime_type = file_info
                        if not os.path.exists(file_path):
                            logger.error(f"TelegramNotifier: File path does not exist for upload: {file_path}")
                            continue
                        filename = os.path.basename(file_path)
                        data.append(f'--{boundary}')
                        data.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"')
                        data.append(f'Content-Type: {mime_type}')
                        data.append('')
                        with open(file_path, 'rb') as f:
                            data.append(f.read())
                            
                    data.append(f'--{boundary}--')
                    data.append('')
                    
                    # Convert to bytes list
                    body_parts = []
                    for part in data:
                        if isinstance(part, str):
                            body_parts.append(part.encode('utf-8'))
                        else:
                            body_parts.append(part)
                    body = b'\r\n'.join(body_parts)
                    
                    headers = {
                        'Content-Type': f'multipart/form-data; boundary={boundary}',
                        'Content-Length': str(len(body))
                    }
                    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
                else:
                    # Send standard JSON request
                    body = json.dumps(payload).encode('utf-8')
                    headers = {
                        'Content-Type': 'application/json',
                        'Content-Length': str(len(body))
                    }
                    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
                    
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_body = response.read().decode('utf-8')
                    res_json = json.loads(res_body)
                    if res_json.get("ok"):
                        return True
                    else:
                        logger.error(f"TelegramNotifier: API returned error status: {res_body}")
                        return False
            except urllib.error.HTTPError as http_err:
                # Handle direct API credential failures immediately
                res = http_err.read().decode('utf-8')
                logger.error(f"TelegramNotifier: HTTP Error {http_err.code}: {res}")
                if http_err.code in [400, 401, 404]:
                    # Bad Request (invalid chat id / syntax) or Unauthorized (invalid token) - do not retry
                    return False
            except Exception as e:
                logger.warning(f"TelegramNotifier: Attempt {attempt + 1} request failure: {e}")
                
            # Backoff before retry
            if attempt < 2:
                time.sleep(2 ** attempt)
                
        logger.error(f"TelegramNotifier: Failed to execute API call '{method}' after 3 attempts.")
        return False
        
    def send(self, message: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2"
        }
        return self._send_request("sendMessage", payload)
        
    def send_photo(self, image_path: str, caption: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "caption": caption,
            "parse_mode": "MarkdownV2"
        }
        files = {
            "photo": (image_path, "image/png")
        }
        return self._send_request("sendPhoto", payload, files=files)
        
    def send_document(self, file_path: str, caption: str) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "caption": caption,
            "parse_mode": "MarkdownV2"
        }
        files = {
            "document": (file_path, "application/pdf")
        }
        return self._send_request("sendDocument", payload, files=files)
