"""时间与 ID 工具：全部使用 UTC，避免本地时区影响 run_id。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def compact_utc_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def new_run_id() -> str:
    return f"web-{compact_utc_now()}-{uuid4().hex[:8]}"


def new_attempt_id() -> str:
    return f"att-{uuid4().hex[:12]}"


__all__ = ["compact_utc_now", "new_attempt_id", "new_run_id", "utc_now"]
