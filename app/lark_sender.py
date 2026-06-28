from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from .config import settings
from .models import CodeRecord

logger = logging.getLogger(__name__)


class LarkSender:
    def __init__(self, cli_path: str = settings.lark_cli_path):
        self.cli = cli_path

    async def _run_cli(self, *args: str) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return True, stdout.decode().strip()
            logger.error("lark-cli failed: %s", stderr.decode().strip())
            return False, stderr.decode().strip()
        except asyncio.TimeoutError:
            logger.error("lark-cli timed out")
            return False, "timeout"
        except Exception as e:
            logger.error("lark-cli error: %s", e)
            return False, str(e)

    async def send_private(self, user_id: str, markdown: str) -> bool:
        ok, _ = await self._run_cli("im", "+messages-send", "--user-id", user_id, "--markdown", markdown, "--as", "bot")
        return ok

    async def send_to_group(self, chat_id: str, markdown: str) -> bool:
        ok, _ = await self._run_cli("im", "+messages-send", "--chat-id", chat_id, "--markdown", markdown, "--as", "bot")
        return ok

    async def push_to_subscribers(self, subscriber_ids: list[str], record: CodeRecord) -> None:
        if not subscriber_ids:
            return
        msg = self.format_code_message(record)
        tasks = [self.send_private(uid, msg) for uid in subscriber_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = sum(1 for r in results if r is True)
        logger.info("Pushed to %d/%d subscribers (code: %s)", success, len(subscriber_ids), record.masked_code())

    @staticmethod
    def format_code_message(record: CodeRecord) -> str:
        device_info = record.device_label or record.device_id
        time_str = datetime.fromtimestamp(record.timestamp, tz=timezone(timedelta(hours=8))).strftime("%H:%M:%S")
        lines = [f"**📱 {device_info}** · {time_str}"]
        if record.sender:
            lines.append(f"发送方: {record.sender}")
        if record.code:
            lines.append(f"验证码: `{record.code}`")
            if record.platform:
                lines.append(f"平台: {record.platform}")
        lines.append("")
        lines.append(record.raw_message)
        return "\n".join(lines)


lark_sender = LarkSender()
