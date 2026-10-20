"""跨进程单实例锁：防止两个网页服务同时写同一个 runs/web。

Windows 使用 ``msvcrt.locking``，POSIX 使用 ``fcntl.flock``；锁随进程退出自动释放。
锁文件只保存 PID 用于错误提示，不参与任何业务状态。
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, BinaryIO


class ServiceLockError(RuntimeError):
    """另一个服务实例已占用运行目录。"""


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            _lock(handle)
        except OSError as exc:
            owner = _owner_hint(handle)
            handle.close()
            raise ServiceLockError(
                "另一个 Agent Arena 网页实例正在使用该运行目录"
                + (f"（PID {owner}）" if owner else "")
                + "；请先关闭它，或设置 AGENT_ARENA_WEB_RUNS_DIR 到不同目录。"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            handle.seek(0)
            _unlock(handle)
        except OSError:
            pass
        finally:
            handle.close()

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


def _owner_hint(handle: BinaryIO) -> str:
    try:
        handle.seek(0)
        value = handle.read(32).decode("ascii", errors="ignore").strip()
        return value if value.isdigit() else ""
    except OSError:
        return ""


def _lock(handle: BinaryIO) -> None:
    if os.name == "nt":
        module: Any = importlib.import_module("msvcrt")
        module.locking(handle.fileno(), module.LK_NBLCK, 1)
    else:
        module = importlib.import_module("fcntl")
        module.flock(handle.fileno(), module.LOCK_EX | module.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    if os.name == "nt":
        module: Any = importlib.import_module("msvcrt")
        module.locking(handle.fileno(), module.LK_UNLCK, 1)
    else:
        module = importlib.import_module("fcntl")
        module.flock(handle.fileno(), module.LOCK_UN)


__all__ = ["ServiceLockError", "SingleInstanceLock"]
