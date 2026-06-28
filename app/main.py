from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .command_handler import handle_message
from .config import settings
from .event_listener import EventListener
from .store import code_store
from .subscribers import subscriber_manager
from .webhook import router as webhook_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_start_time = time.time()
event_listener = EventListener(handler=handle_message)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting verification code forwarder...")
    logger.info("Registered phones: %d", len(settings.registered_phones))
    logger.info("Default subscribers: %d", len(settings.default_subscribers))

    await code_store.start_cleanup_loop()

    event_listener._task = asyncio.create_task(event_listener.start())
    logger.info("Event listener started (groups: %s)", settings.group_chat_ids or "none")

    yield

    event_listener.stop()
    code_store.stop()
    logger.info("Shutdown complete.")


app = FastAPI(title="Verification Code Forwarder", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - _start_time),
        "event_listener_alive": event_listener.is_alive,
        "codes_in_store": code_store.count(),
        "subscribers": subscriber_manager.count(),
        "registered_phones": len(settings.registered_phones),
    }
