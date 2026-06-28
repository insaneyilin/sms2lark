from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Header, HTTPException

from .config import is_registered_phone, mask_phone, settings
from .lark_sender import lark_sender
from .models import CodeRecord, SmsPayload
from .parser import parse_sms
from .store import code_store
from .subscribers import subscriber_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_token(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or parts[1] != settings.webhook_token:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/webhook/sms")
async def receive_sms(payload: SmsPayload, authorization: str | None = Header(None)):
    _verify_token(authorization)

    ts = payload.timestamp
    if ts > 1_000_000_000_000:
        ts = ts / 1000
    if ts and abs(time.time() - ts) > 300:
        raise HTTPException(status_code=400, detail="Timestamp too old")

    phone = payload.phone or payload.device_id
    if not phone or not is_registered_phone(phone):
        logger.warning("Rejected unregistered phone: %s", phone)
        raise HTTPException(status_code=403, detail="Unregistered phone")

    device_label = mask_phone(phone)
    record = parse_sms(payload.content, payload.sender, phone, device_label)

    if not record:
        logger.info("No code pattern matched, ignoring SMS (phone=%s sender=%s)", device_label, payload.sender)
        return {"status": "ok", "code_found": False, "platform": ""}

    logger.info("Code extracted: %s from %s (phone=%s)", record.masked_code(), record.platform, device_label)
    code_store.add(record)

    subscribers = subscriber_manager.get_for_device(phone)
    all_targets = list(set(subscribers + settings.default_subscribers))
    if all_targets:
        asyncio.create_task(lark_sender.push_to_subscribers(all_targets, record))

    return {"status": "ok", "code_found": bool(record.code), "platform": record.platform}
