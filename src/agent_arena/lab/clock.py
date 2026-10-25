"""Lab 时间与 ID 工具（复用 V11 UTC 口径，避免两套时钟）。"""

from __future__ import annotations

from agent_arena.web.clock import compact_utc_now, utc_now

__all__ = ["compact_utc_now", "utc_now"]
