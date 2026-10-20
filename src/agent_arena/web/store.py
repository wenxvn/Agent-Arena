"""V11 运行存储：原子 manifest + append-only JSONL + result.json。

跨平台要点：

- 原子写使用临时文件 + ``os.replace``，在 Windows 上对短暂占用做有限重试；
- JSONL 追加使用进程内锁 + ``flush`` + ``fsync``；
- 路径只允许 ``runs/web/<合法 run_id>/`` 下的固定文件名。
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from agent_arena.web.clock import utc_now
from agent_arena.web.safety import is_valid_run_id, safe_run_dir
from agent_arena.web.schemas import SCHEMA_VERSION

MANIFEST = "manifest.json"
EVENTS = "events.jsonl"
RESULT = "result.json"
BUDGET = "budget.jsonl"
GLOBAL_LEDGER_DIR = "_ledger"
GLOBAL_LEDGER = "web_ledger.jsonl"

_APPEND_LOCK = threading.Lock()


class StoreError(RuntimeError):
    """存储层错误的基类。"""


class RunNotFoundError(StoreError):
    """请求的 run_id 不存在。"""


class CorruptRunError(StoreError):
    """manifest 无法解析。"""


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """写 JSON：临时文件 + 原子替换；失败时清理临时文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    text = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=1, default=str
    ) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    with _APPEND_LOCK, path.open("ab") as stream:
        stream.write((line + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


class RunStore:
    """``runs/web/`` 的唯一读写入口。"""

    def __init__(self, base: Path) -> None:
        self.base = base.resolve()

    # ------------------------------------------------------------------ paths
    def ensure_base(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str, *, create: bool = False) -> Path:
        if create:
            self.ensure_base()
            if not is_valid_run_id(run_id):
                raise ValueError("非法的 run_id。")
            path = (self.base / run_id).resolve()
            if path.parent != self.base:
                raise ValueError("run 目录越界。")
            path.mkdir(parents=True, exist_ok=True)
            return path
        try:
            return safe_run_dir(self.base, run_id)
        except ValueError as exc:
            raise RunNotFoundError(f"找不到运行：{run_id}") from exc

    def list_run_ids(self) -> list[str]:
        if not self.base.is_dir():
            return []
        return sorted(
            path.name
            for path in self.base.iterdir()
            if path.is_dir() and is_valid_run_id(path.name) and not path.is_symlink()
        )

    # --------------------------------------------------------------- manifest
    def load_manifest(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / MANIFEST
        if not path.is_file():
            raise RunNotFoundError(f"运行缺少 manifest：{run_id}")
        text: str | None = None
        last_error: OSError | None = None
        for attempt in range(20):
            try:
                text = path.read_text(encoding="utf-8")
                break
            except PermissionError as exc:  # Windows 替换瞬间的共享冲突
                last_error = exc
                time.sleep(0.02 * (attempt + 1))
            except OSError as exc:
                last_error = exc
                break
        if text is None:
            raise CorruptRunError(f"manifest 无法读取：{run_id}") from last_error
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise CorruptRunError(f"manifest 损坏：{run_id}") from exc
        if not isinstance(payload, dict) or payload.get("run_id") != run_id:
            raise CorruptRunError(f"manifest 内容非法：{run_id}")
        return payload

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        run_id = str(manifest.get("run_id", ""))
        if not is_valid_run_id(run_id):
            raise ValueError("manifest 缺少合法 run_id。")
        payload = dict(manifest)
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload["updated_at"] = utc_now()
        atomic_write_json(self.run_dir(run_id, create=True) / MANIFEST, payload)

    def discover(self) -> tuple[list[dict[str, Any]], list[str]]:
        """返回可读 manifest 与损坏/缺文件的 run_id。"""

        manifests: list[dict[str, Any]] = []
        broken: list[str] = []
        for run_id in self.list_run_ids():
            try:
                manifests.append(self.load_manifest(run_id))
            except (RunNotFoundError, CorruptRunError):
                broken.append(run_id)
        manifests.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return manifests, broken

    def find_by_idempotency(self, key: str) -> str | None:
        if not key:
            return None
        manifests, _ = self.discover()
        for manifest in manifests:
            if manifest.get("idempotency_key") == key:
                return str(manifest.get("run_id"))
        return None

    # ----------------------------------------------------------------- events
    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("at", utc_now())
        append_jsonl(self.run_dir(run_id) / EVENTS, payload)

    def read_events(self, run_id: str) -> list[dict[str, Any]]:
        events, _ = self.read_events_with_diagnostics(run_id)
        return events

    def read_events_with_diagnostics(self, run_id: str) -> tuple[list[dict[str, Any]], int]:
        """容忍损坏行：跳过并返回跳过条数，保证部分回放仍可读。"""

        path = self.run_dir(run_id) / EVENTS
        if not path.is_file():
            return [], 0
        events: list[dict[str, Any]] = []
        skipped = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return [], 1
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                skipped += 1
                continue
            if not isinstance(item, dict) or not isinstance(item.get("event"), str):
                skipped += 1
                continue
            events.append(item)
        return events, skipped

    # ----------------------------------------------------------------- result
    def save_result(self, run_id: str, result: dict[str, Any]) -> None:
        atomic_write_json(self.run_dir(run_id) / RESULT, result)

    def load_result(self, run_id: str) -> dict[str, Any] | None:
        path = self.run_dir(run_id) / RESULT
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    # ----------------------------------------------------------- global ledger
    def append_global_ledger(self, payload: dict[str, Any]) -> None:
        append_jsonl(self.base / GLOBAL_LEDGER_DIR / GLOBAL_LEDGER, payload)

    def read_global_ledger(self) -> list[dict[str, Any]]:
        path = self.base / GLOBAL_LEDGER_DIR / GLOBAL_LEDGER
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows


__all__ = [
    "BUDGET",
    "EVENTS",
    "GLOBAL_LEDGER",
    "GLOBAL_LEDGER_DIR",
    "MANIFEST",
    "RESULT",
    "CorruptRunError",
    "RunNotFoundError",
    "RunStore",
    "StoreError",
    "append_jsonl",
    "atomic_write_json",
]
