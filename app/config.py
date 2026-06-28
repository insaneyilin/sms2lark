from __future__ import annotations

import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    webhook_token: str = "changeme"

    # Registered phones: list of phone numbers allowed to forward SMS.
    # Only phones in this list are accepted.
    registered_phones: list[str] = []

    # Lark
    lark_cli_path: str = "/opt/homebrew/bin/lark-cli"
    default_subscribers: list[str] = []
    group_chat_ids: list[str] = []
    authorized_users: list[str] = []

    # Code store
    code_ttl_seconds: int = 300
    max_codes_per_device: int = 20

    # Server
    host: str = "0.0.0.0"
    port: int = 8900

    model_config = {"env_prefix": "VCA_", "env_file": str(PROJECT_ROOT / ".env")}

    @field_validator("registered_phones", "default_subscribers", "group_chat_ids", "authorized_users", mode="before")
    @classmethod
    def parse_list(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


settings = Settings()


def mask_phone(phone: str) -> str:
    if len(phone) >= 7:
        return phone[:3] + "****" + phone[-4:]
    return phone


def is_registered_phone(phone: str) -> bool:
    return phone in settings.registered_phones
