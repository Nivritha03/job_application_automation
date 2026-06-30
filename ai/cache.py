import os
import json
import hashlib
from loguru import logger

class AICache:
    def __init__(self, cache_file: str = "data/ai_cache.json", enabled: bool = True):
        self.cache_file = cache_file
        self.enabled = enabled
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if not self.enabled:
            return
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                logger.info(f"AICache: Loaded {len(self.cache)} entries from cache file.")
            except Exception as e:
                logger.error(f"AICache: Failed to load cache file: {e}")
                self.cache = {}

    def _save_cache(self):
        if not self.enabled:
            return
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"AICache: Failed to save cache file: {e}")

    def _generate_key(self, company: str, role: str, prompt_type: str, resume: str) -> str:
        # Standardize strings to lower and strip
        comp = str(company).lower().strip()
        r = str(role).lower().strip()
        pt = str(prompt_type).lower().strip()
        res = str(resume).lower().strip()
        raw_key = f"{comp}|{r}|{pt}|{res}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, company: str, role: str, prompt_type: str, resume: str) -> dict:
        if not self.enabled:
            return None
        key = self._generate_key(company, role, prompt_type, resume)
        if key in self.cache:
            logger.info(f"AICache: Hit for {company} | {role} | {prompt_type}")
            return self.cache[key]
        return None

    def set(self, company: str, role: str, prompt_type: str, resume: str, value: dict):
        if not self.enabled:
            return
        key = self._generate_key(company, role, prompt_type, resume)
        self.cache[key] = value
        self._save_cache()
        logger.debug(f"AICache: Saved entry for {company} | {role} | {prompt_type}")
