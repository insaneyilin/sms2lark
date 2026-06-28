from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Awaitable

from .config import settings

logger = logging.getLogger(__name__)


class EventListener:
    def __init__(self, handler: Callable[[dict], Awaitable[None]], cli_path: str = settings.lark_cli_path):
        self.cli = cli_path
        self.handler = handler
        self._process: asyncio.subprocess.Process | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                logger.info("Starting lark-cli event listener...")
                self._process = await asyncio.create_subprocess_exec(
                    self.cli,
                    "event",
                    "+subscribe",
                    "--event-types",
                    "im.message.receive_v1",
                    "--compact",
                    "--quiet",
                    "--as",
                    "bot",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await self._read_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Event listener error: %s, restarting in 5s", e)
            if self._running:
                await asyncio.sleep(5)

    async def _read_loop(self) -> None:
        if not self._process or not self._process.stdout:
            return
        async for line in self._process.stdout:
            if not self._running:
                break
            text = line.decode().strip()
            if not text:
                continue
            try:
                event = json.loads(text)
                logger.info("Event received: %s", json.dumps(event, ensure_ascii=False)[:500])
                await self.handler(event)
            except json.JSONDecodeError:
                logger.debug("Non-JSON line from event stream: %s", text[:100])
            except Exception as e:
                logger.error("Error handling event: %s", e)

    def stop(self) -> None:
        self._running = False
        if self._process and self._process.returncode is None:
            self._process.terminate()
        if self._task:
            self._task.cancel()
