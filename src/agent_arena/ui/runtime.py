"""进程级 RunService 单例。

Streamlit 每次 rerun 会重新执行入口脚本，``__main__`` 中的模块级变量会重置；
把单例放在被 import 的普通模块里，才能跨 rerun/会话复用同一个服务与文件锁。
"""

from __future__ import annotations

import threading
from pathlib import Path

from agent_arena.web.service import RunService

_LOCK = threading.Lock()
_SERVICE: RunService | None = None
_BASE: Path | None = None


def get_service(base: Path) -> RunService:
    global _SERVICE, _BASE
    resolved = base.resolve()
    with _LOCK:
        if _SERVICE is not None and _BASE == resolved:
            return _SERVICE
        if _SERVICE is not None:
            _SERVICE.shutdown()
        _SERVICE = RunService(resolved)
        _BASE = resolved
        return _SERVICE


def reset_service() -> None:
    global _SERVICE, _BASE
    with _LOCK:
        if _SERVICE is not None:
            _SERVICE.shutdown()
        _SERVICE = None
        _BASE = None


__all__ = ["get_service", "reset_service"]
