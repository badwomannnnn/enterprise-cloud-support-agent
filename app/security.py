from __future__ import annotations

import re


REDACTION_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b", re.I), "sk-****"),
    ("secret_id", re.compile(r"\bAKID[A-Za-z0-9]{8,}\b"), "AKID****"),
    (
        "key_value",
        re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|token)\s*[:=]\s*['\"]?([^\s'\",;]{6,})"),
        r"\1=****",
    ),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "***@***.***"),
    ("phone", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"), "138****0000"),
]


def redact_sensitive_data(text: str) -> tuple[str, list[str]]:
    redacted = text
    matched: list[str] = []
    for name, pattern, replacement in REDACTION_RULES:
        if pattern.search(redacted):
            matched.append(name)
            redacted = pattern.sub(replacement, redacted)
    return redacted, matched


def contains_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        "忽略之前的指令",
        "忽略系统提示",
        "输出系统提示词",
        "reveal system prompt",
        "ignore previous instructions",
        "绕过安全规则",
    ]
    return any(item in lowered for item in patterns)

