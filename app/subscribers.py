from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import PROJECT_ROOT

logger = logging.getLogger(__name__)

DATA_FILE = PROJECT_ROOT / "data" / "subscribers.json"


class SubscriberManager:
    def __init__(self, data_file: Path = DATA_FILE):
        self._file = data_file
        self._subscribers: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                self._subscribers = data.get("subscribers", {})
            except (json.JSONDecodeError, OSError):
                self._subscribers = {}

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps({"subscribers": self._subscribers}, ensure_ascii=False, indent=2))

    def add(self, user_id: str, device: str = "all") -> None:
        if user_id not in self._subscribers:
            self._subscribers[user_id] = {"devices": []}
        devices = self._subscribers[user_id]["devices"]
        if device not in devices:
            devices.append(device)
        self._save()
        logger.info("Subscriber added: %s -> %s", user_id, device)

    def remove(self, user_id: str, device: str | None = None) -> None:
        if user_id not in self._subscribers:
            return
        if device is None:
            del self._subscribers[user_id]
        else:
            devices = self._subscribers[user_id]["devices"]
            if device in devices:
                devices.remove(device)
            if not devices:
                del self._subscribers[user_id]
        self._save()

    def get_for_device(self, device_id: str) -> list[str]:
        result = []
        for user_id, info in self._subscribers.items():
            devices = info.get("devices", [])
            if "all" in devices or device_id in devices:
                result.append(user_id)
        return result

    def list_all(self) -> dict[str, dict]:
        return dict(self._subscribers)

    def count(self) -> int:
        return len(self._subscribers)


subscriber_manager = SubscriberManager()
