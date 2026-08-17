"""Shared text sanitization for prompts and persisted output."""

from __future__ import annotations

import re

_SENSITIVE_VALUE = re.compile(
    r"(?i)\b((?:[a-z0-9]+_)*(?:api[_-]?key|authorization|token|secret|password))\b"
    r"\s*[:=]\s*[^\s,;]+"
)


def sanitize_text(value: str, *, max_length: int = 1_000) -> str:
    """Redact secret shaped values and bound text before it crosses a boundary."""

    return _SENSITIVE_VALUE.sub(r"\1=[REDACTED]", value.strip())[:max_length]
