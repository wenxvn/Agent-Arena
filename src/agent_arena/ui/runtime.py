"""进程级 RunService / ExperimentService 单例。

Streamlit 每次 rerun 会重新执行入口脚本，``__main__`` 中的模块级变量会重置；
把单例放在被 import 的普通模块里，才能跨 rerun/会话复用同一个服务与文件锁。

Lab 服务必须复用同一个 ``RunService``，否则父子实验会各持一把实例锁。
"""

from __future__ import annotations

import threading
from pathlib import Path

from agent_arena.lab.experiment import ExperimentService
from agent_arena.web.service import RunService

_LOCK = threading.Lock()
_SERVICE: RunService | None = None
_BASE: Path | None = None

_LAB: ExperimentService | None = None
_LAB_RUN: RunService | None = None
_LAB_BASE: Path | None = None


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
    global _SERVICE, _BASE, _LAB, _LAB_RUN, _LAB_BASE
    with _LOCK:
        if _SERVICE is not None:
            _SERVICE.shutdown()
        _SERVICE = None
        _BASE = None
        _LAB = None
        _LAB_RUN = None
        _LAB_BASE = None


def get_lab_service(run_base: Path, lab_base: Path) -> ExperimentService:
    """返回复用当前 ``RunService`` 的父实验服务。"""

    global _LAB, _LAB_RUN, _LAB_BASE
    service = get_service(run_base)
    resolved_lab = lab_base.resolve()
    with _LOCK:
        if _LAB is not None and _LAB_RUN is service and _LAB_BASE == resolved_lab:
            return _LAB
        _LAB = ExperimentService(resolved_lab, run_service=service)
        _LAB_RUN = service
        _LAB_BASE = resolved_lab
        return _LAB


__all__ = ["get_lab_service", "get_service", "reset_service"]
