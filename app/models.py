from __future__ import annotations

from pydantic import BaseModel


class SmsPayload(BaseModel):
    sender: str = ""
    content: str
    timestamp: int = 0
    device_id: str = ""
    phone: str = ""


class CodeRecord(BaseModel):
    code: str
    platform: str
    sender: str
    device_id: str
    device_label: str = ""
    timestamp: float
    raw_message: str = ""

    def masked_code(self) -> str:
        if len(self.code) <= 4:
            return self.code[:1] + "**" + self.code[-1:]
        return self.code[:2] + "*" * (len(self.code) - 4) + self.code[-2:]
