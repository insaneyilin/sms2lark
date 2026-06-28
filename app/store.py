from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from .config import settings
from .models import CodeRecord


class CodeStore:
    def __init__(self, ttl: int = settings.code_ttl_seconds, max_per_device: int = settings.max_codes_per_device):
        self._store: dict[str, list[CodeRecord]] = defaultdict(list)
        self._ttl = ttl
        self._max_per_device = max_per_device
        self._cleanup_task: asyncio.Task | None = None

    def add(self, record: CodeRecord) -> None:
        device_codes = self._store[record.device_id]
        device_codes.append(record)
        if len(device_codes) > self._max_per_device:
            self._store[record.device_id] = device_codes[-self._max_per_device :]

    def get_latest(self, device_id: str | None = None, n: int = 1) -> list[CodeRecord]:
        now = time.time()
        if device_id:
            codes = [c for c in self._store.get(device_id, []) if now - c.timestamp < self._ttl]
        else:
            codes = [c for dev_codes in self._store.values() for c in dev_codes if now - c.timestamp < self._ttl]
        codes.sort(key=lambda c: c.timestamp, reverse=True)
        return codes[:n]

    def get_by_platform(self, platform: str, device_id: str | None = None) -> CodeRecord | None:
        now = time.time()
        candidates = self.get_latest(device_id, n=50)
        for c in candidates:
            if now - c.timestamp < self._ttl and platform.lower() in c.platform.lower():
                return c
        return None

    def count(self) -> int:
        return sum(len(v) for v in self._store.values())

    def _cleanup(self) -> None:
        now = time.time()
        for device_id in list(self._store.keys()):
            self._store[device_id] = [c for c in self._store[device_id] if now - c.timestamp < self._ttl]
            if not self._store[device_id]:
                del self._store[device_id]

    async def start_cleanup_loop(self) -> None:
        async def _loop():
            while True:
                await asyncio.sleep(30)
                self._cleanup()

        self._cleanup_task = asyncio.create_task(_loop())

    def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()


code_store = CodeStore()
