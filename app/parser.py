from __future__ import annotations

import re
import time

from .models import CodeRecord

# 提取验证码的正则（尽量精确提取）
CODE_PATTERNS = [
    # 中文关键词 + 纯数字
    re.compile(r"验证码[为是：:\s]*(\d{4,8})"),
    re.compile(r"校验码[为是：:\s]*(\d{4,8})"),
    re.compile(r"动态密码[为是：:\s]*(\d{4,8})"),
    re.compile(r"认证码[为是：:\s]*(\d{4,8})"),
    re.compile(r"取件码[为是：:\s]*(\d{4,8})"),
    # 英文关键词 + 纯数字
    re.compile(r"(?:code|Code|CODE)\s*(?:is|:)?\s*(\d{4,8})"),
    re.compile(r"(?:verification|Verification)\s*(?:code|Code)?\s*(?:is|:)?\s*(\d{4,8})"),
    re.compile(r"(?:OTP|otp|pin|PIN)\s*(?:is|:)?\s*(\d{4,8})"),
    re.compile(r"(?:passcode|Passcode)\s*(?:is|:)?\s*(\d{4,8})"),
    # 中文关键词 + 字母数字混合码（如 A3F8K2）
    re.compile(r"验证码[为是：:\s]*([A-Za-z0-9]{4,8})"),
    re.compile(r"校验码[为是：:\s]*([A-Za-z0-9]{4,8})"),
    re.compile(r"动态密码[为是：:\s]*([A-Za-z0-9]{4,8})"),
    # 英文关键词 + 字母数字混合码
    re.compile(r"(?:code|Code|CODE)\s*(?:is|:)?\s*([A-Za-z0-9]{4,8})", re.IGNORECASE),
    re.compile(r"(?:OTP|otp|pin|PIN)\s*(?:is|:)?\s*([A-Za-z0-9]{4,8})"),
    re.compile(r"(?:passcode|Passcode)\s*(?:is|:)?\s*([A-Za-z0-9]{4,8})", re.IGNORECASE),
    # 中文语境 + 数字
    re.compile(r"(?:验证|校验|确认|登录|注册|绑定|认证|激活|找回|重置).*?(\d{4,8})"),
    # 数字在前的格式
    re.compile(r"(\d{4,8})\s*(?:为你的|是你的|为您的|是您的)"),
    re.compile(r"(\d{4,8})\s*[（(].*?(?:有效|分钟|min)"),
]

# 判断消息是否"像验证码短信"的宽松规则（高召回）
HINT_PATTERNS = [
    re.compile(r"验证码", re.IGNORECASE),
    re.compile(r"校验码"),
    re.compile(r"动态密码"),
    re.compile(r"认证码"),
    re.compile(r"取件码"),
    re.compile(r"(?:code|OTP|PIN|passcode)", re.IGNORECASE),
    re.compile(r"(?:verification|authenticate)", re.IGNORECASE),
    re.compile(r"(?:有效期|有效时间|分钟内|min).*\d"),
    re.compile(r"\d.*(?:有效期|有效时间|分钟内|min)"),
    re.compile(r"(?:登录|注册|绑定|找回|重置|激活|认证).*\d{4,8}"),
    re.compile(r"\d{4,8}.*(?:登录|注册|绑定|找回|重置|激活|认证)"),
    # 纯数字 4-8 位独立出现（前后不紧跟其他数字），且短信较短（像验证码短信）
    re.compile(r"(?<!\d)\d{4,8}(?!\d)"),
]


def _is_short_with_code_shape(content: str) -> bool:
    """短信较短且包含独立的 4-8 位数字/字母数字串，很可能是验证码"""
    if len(content) > 200:
        return False
    if re.search(r"(?<![A-Za-z0-9])[A-Za-z]\d{3,7}(?![A-Za-z0-9])", content):
        return True
    if re.search(r"(?<![A-Za-z0-9])\d[A-Za-z]\d{2,6}(?![A-Za-z0-9])", content):
        return True
    if re.search(r"(?<![A-Za-z0-9])[A-Za-z0-9]{4,8}(?![A-Za-z0-9])", content) and re.search(r"[A-Za-z]", content) and re.search(r"\d", content):
        if len(content) < 80:
            return True
    return False

PLATFORM_PATTERN = re.compile(r"[【\[](.*?)[】\]]")


def extract_platform(content: str, sender: str) -> str:
    m = PLATFORM_PATTERN.search(content)
    if m:
        return m.group(1)
    return sender or "未知"


def extract_code(content: str) -> str | None:
    for pattern in CODE_PATTERNS:
        m = pattern.search(content)
        if m:
            return m.group(1)
    return None


def looks_like_code_sms(content: str) -> bool:
    if any(p.search(content) for p in HINT_PATTERNS):
        return True
    if _is_short_with_code_shape(content):
        return True
    return False


def parse_sms(content: str, sender: str, device_id: str, device_label: str = "") -> CodeRecord | None:
    code = extract_code(content)
    if not code and not looks_like_code_sms(content):
        return None
    platform = extract_platform(content, sender)
    return CodeRecord(
        code=code or "",
        platform=platform,
        sender=sender,
        device_id=device_id,
        device_label=device_label,
        timestamp=time.time(),
        raw_message=content,
    )
