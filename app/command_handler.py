from __future__ import annotations

import logging
import re

from .config import mask_phone, settings
from .lark_sender import lark_sender
from .models import CodeRecord
from .store import code_store
from .subscribers import subscriber_manager

logger = logging.getLogger(__name__)

REQUEST_PATTERNS = [
    re.compile(r"验证码"),
    re.compile(r"最新.*码"),
    re.compile(r"发一下"),
    re.compile(r"code", re.IGNORECASE),
]

DEVICE_PATTERN = re.compile(r"(phone[-_]?\w+|手机\w+)")

SUBSCRIBE_PATTERNS = [re.compile(r"订阅"), re.compile(r"subscribe", re.IGNORECASE)]
UNSUBSCRIBE_PATTERNS = [re.compile(r"取消订阅"), re.compile(r"unsubscribe", re.IGNORECASE)]


def _is_authorized(user_id: str) -> bool:
    if not settings.authorized_users:
        return True
    return user_id in settings.authorized_users


def _match_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _extract_device_from_text(text: str) -> str | None:
    m = DEVICE_PATTERN.search(text)
    if m:
        return m.group(1)
    for phone in settings.registered_phones:
        if phone in text or mask_phone(phone) in text:
            return phone
    return None


def _format_code_reply(records: list[CodeRecord]) -> str:
    if not records:
        return "暂无最新验证码"
    parts = [lark_sender.format_code_message(r) for r in records]
    return "\n---\n".join(parts)


def _strip_mention(text: str) -> str:
    return re.sub(r"@\S+\s*", "", text).strip()


HELP_TEXT = """支持的指令：
• `订阅` — 订阅所有手机的验证码推送
• `订阅 138****1234` — 只订阅指定手机
• `取消订阅` — 取消全部订阅
• `验证码` — 查询最近 5 条验证码
• `帮助` / `help` — 显示本帮助"""

HELP_PATTERNS = [re.compile(r"帮助"), re.compile(r"help", re.IGNORECASE)]


async def handle_message(event: dict) -> None:
    sender_id = event.get("sender_id") or event.get("open_id", "")
    chat_id = event.get("chat_id", "")
    chat_type = event.get("chat_type", "")
    raw_text = event.get("text", "") or event.get("content", "")

    if not raw_text or not sender_id:
        return

    if chat_type == "group":
        await _handle_group(sender_id, chat_id, raw_text)
    elif chat_type == "p2p":
        await _handle_private(sender_id, raw_text)


async def _handle_private(sender_id: str, raw_text: str) -> None:
    text = _strip_mention(raw_text).strip() or "验证码"

    if not _is_authorized(sender_id):
        await lark_sender.send_private(sender_id, "无权限操作")
        return

    if _match_any(text, HELP_PATTERNS):
        await lark_sender.send_private(sender_id, HELP_TEXT)
        return

    if _match_any(text, UNSUBSCRIBE_PATTERNS):
        subscriber_manager.remove(sender_id)
        await lark_sender.send_private(sender_id, "已取消订阅")
        return

    if _match_any(text, SUBSCRIBE_PATTERNS):
        device = _extract_device_from_text(text) or "all"
        subscriber_manager.add(sender_id, device)
        await lark_sender.send_private(sender_id, f"已订阅验证码推送 ({device})")
        return

    if _match_any(text, REQUEST_PATTERNS):
        device = _extract_device_from_text(text)
        records = code_store.get_latest(device_id=device, n=5)
        reply = _format_code_reply(records)
        await lark_sender.send_private(sender_id, reply)
        return

    await lark_sender.send_private(sender_id, f"未识别的指令：「{text}」\n\n{HELP_TEXT}")


async def _handle_group(sender_id: str, chat_id: str, raw_text: str) -> None:
    if not chat_id:
        return

    if "@" not in raw_text:
        return

    text = _strip_mention(raw_text)

    if not text:
        text = "验证码"

    if chat_id not in settings.group_chat_ids and settings.group_chat_ids:
        return

    if _match_any(text, HELP_PATTERNS):
        if not _is_authorized(sender_id):
            return
        await lark_sender.send_to_group(chat_id, HELP_TEXT)
        return

    if _match_any(text, UNSUBSCRIBE_PATTERNS):
        if not _is_authorized(sender_id):
            return
        subscriber_manager.remove(sender_id)
        await lark_sender.send_to_group(chat_id, "已取消订阅")
        return

    if _match_any(text, SUBSCRIBE_PATTERNS):
        if not _is_authorized(sender_id):
            return
        device = _extract_device_from_text(text) or "all"
        subscriber_manager.add(sender_id, device)
        await lark_sender.send_to_group(chat_id, f"已订阅验证码推送 ({device})")
        return

    if _match_any(text, REQUEST_PATTERNS):
        if not _is_authorized(sender_id):
            await lark_sender.send_to_group(chat_id, "无权限查询")
            return
        device = _extract_device_from_text(text)
        records = code_store.get_latest(device_id=device, n=5)
        reply = _format_code_reply(records)
        logger.info("Replying to group %s: %s", chat_id, reply[:100])
        await lark_sender.send_to_group(chat_id, reply)
        return

    # 默认当作查验证码
    records = code_store.get_latest(n=5)
    reply = _format_code_reply(records)
    await lark_sender.send_to_group(chat_id, reply)
    logger.info("Default reply to group %s", chat_id)
