"""
User Data Persistence Module.
Caches extracted ID information to avoid re-running OCR for known users.
Uses a JSON file for storage (simple and effective for MVP).
"""
import json
import os
from threading import Lock
from typing import Dict, Optional
from logger import GLOBAL_LOGGER as log

class UserStore:
    def __init__(self, storage_path: str = "data/user_cache.json"):
        self.storage_path = storage_path
        self.lock = Lock()
        self._ensure_storage()
        self.cache = self._load()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, 'w') as f:
                json.dump({}, f)

    def _load(self) -> Dict:
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load user cache: {e}")
            return {}

    def _save(self):
        try:
            with self.lock:
                with open(self.storage_path, 'w') as f:
                    json.dump(self.cache, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save user cache: {e}")

    def get_user_data(self, user_id: str) -> Optional[Dict]:
        """Retrieve cached data for a user."""
        return self.cache.get(user_id)

    def save_user_data(self, user_id: str, data: Dict):
        """Save/Update data for a user."""
        self.cache[user_id] = data
        self._save()
        log.info(f"Updated cache for user: {user_id}")

# Singleton instance
USER_STORE = UserStore()
