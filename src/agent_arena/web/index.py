"""运行历史索引：分页、筛选与聚合的**有界内存**入口（V13-09-06 / V13-12-04）。

问题：``RunService.list_runs`` 每次调用都重新 ``discover()``——读全部 manifest 并解析
JSON。历史到 5 000 局时，页面每次刷新都要解析 5 000 个文件，且把全部 summary 放进
内存。

做法（不改变 V11 语义，只加一层只读索引）：

- 索引只保存**列表页需要的十几个字段**，不保存事件、不保存 trace；
- 目录 mtime + 文件数变化时才重建；否则直接命中缓存；
- 分页在索引上做（``offset`` / ``limit``），返回 ``total`` 与 ``has_more``；
- 聚合（按地图/状态计数）在索引上做，不读 replay。

明确边界：这不是数据库，也不是跨进程缓存；进程重启后第一次查询会重建索引，
这是预期行为，并在 ``stats`` 里如实报告重建耗时。
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_arena.web.safety import is_valid_run_id
from agent_arena.web.store import MANIFEST

#: 索引字段（只含列表与聚合需要的最小集合）。
INDEX_FIELDS: tuple[str, ...] = (
    "run_id",
    "map_id",
    "world",
    "mode",
    "provider_id",
    "model",
    "environment_seed",
    "state",
    "outcome",
    "success",
    "decisions",
    "decision_budget",
    "created_at",
    "finished_at",
    "cost_settled_cny",
    "cost_unknown",
    "rule_hash",
    "metric_hash",
    "metric_schema_hash",
    "experiment_id",
)


@dataclass
class IndexStats:
    runs: int = 0
    broken: int = 0
    rebuilds: int = 0
    last_rebuild_ms: float = 0.0
    cache_hits: int = 0
    bytes_estimate: int = 0
    #: 上次重建里复用（文件未变、未读盘）的条目数。
    reused_entries: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "runs": self.runs,
            "broken": self.broken,
            "rebuilds": self.rebuilds,
            "last_rebuild_ms": round(self.last_rebuild_ms, 2),
            "cache_hits": self.cache_hits,
            "bytes_estimate": self.bytes_estimate,
            "reused_entries": self.reused_entries,
        }


def _entry(manifest: dict[str, Any]) -> dict[str, Any]:
    raw_budget = manifest.get("budget")
    raw_hashes = manifest.get("hashes")
    budget: dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
    hashes: dict[str, Any] = raw_hashes if isinstance(raw_hashes, dict) else {}
    cost = budget.get("cost_settled_cny")
    try:
        cost_value = float(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost_value = None
    return {
        "run_id": str(manifest.get("run_id", "")),
        "map_id": str(manifest.get("map_id", "")),
        "world": str(manifest.get("world", "")),
        "mode": str(manifest.get("mode", "")),
        "provider_id": str(manifest.get("provider_id", "")),
        "model": str(manifest.get("model", "")),
        "environment_seed": int(manifest.get("environment_seed") or 0),
        "state": str(manifest.get("state", "")),
        "outcome": manifest.get("outcome"),
        "success": bool(manifest.get("success")),
        "decisions": int(manifest.get("decisions") or 0),
        "decision_budget": int(manifest.get("decision_budget") or 0),
        "created_at": str(manifest.get("created_at", "")),
        "finished_at": manifest.get("finished_at"),
        "cost_settled_cny": cost_value,
        "cost_unknown": bool(budget.get("cost_unknown")),
        "rule_hash": hashes.get("rule_hash"),
        "metric_hash": hashes.get("metric_hash"),
        "metric_schema_hash": hashes.get("metric_schema_hash"),
        "experiment_id": manifest.get("experiment_id"),
    }


@dataclass
class RunIndex:
    """``runs/web`` 的只读索引（有界内存 + 分页 + 增量刷新）。"""

    base: Path
    stats: IndexStats = field(default_factory=IndexStats)
    _entries: list[dict[str, Any]] = field(default_factory=list)
    _signature: tuple[int, float] | None = None
    _checked_at: float = 0.0
    #: run_id → (manifest mtime, entry)：增量刷新时只重读变化过的文件。
    _cache: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)

    #: 目录签名最多每 N 秒重算一次：本地单用户场景下足够新鲜，
    #: 又避免"每次分页都 stat 一遍全部目录"（5 000 局时这是主要开销）。
    #: 写入后调用 ``invalidate()`` 可以立刻让下一次查询重算。
    SIGNATURE_TTL_SECONDS = 30.0

    def _scan(self) -> list[tuple[str, float]]:
        """列目录并取每个 manifest 的 mtime（只 stat，不读内容）。

        用 ``os.scandir``：``entry.is_dir()`` 在 Windows 上直接来自目录枚举，
        **不额外 stat**；``pathlib.is_dir()`` 会为每个条目做一次 stat，5 000 局时
        光这一步就要 1.6 秒。
        """

        if not self.base.is_dir():
            return []
        found: list[tuple[str, float]] = []
        with os.scandir(self.base) as it:
            for entry in it:
                if not entry.is_dir() or not is_valid_run_id(entry.name):
                    continue
                try:
                    mtime = os.stat(os.path.join(entry.path, MANIFEST)).st_mtime
                except OSError:
                    continue
                found.append((entry.name, mtime))
        return found

    def _scan_names(self) -> list[str]:
        """只要 run_id（不 stat manifest）：用于懒加载第一页。"""

        if not self.base.is_dir():
            return []
        names: list[str] = []
        with os.scandir(self.base) as it:
            for entry in it:
                if entry.is_dir() and is_valid_run_id(entry.name):
                    names.append(entry.name)
        return names

    def _current_signature(self) -> tuple[int, float]:
        scanned = self._scan()
        if not scanned:
            return (0, 0.0)
        return (len(scanned), round(max(mtime for _, mtime in scanned), 3))

    def invalidate(self) -> None:
        """写入后调用：下一次查询强制重算签名。"""

        self._checked_at = 0.0

    def refresh(self, *, force: bool = False) -> IndexStats:
        now = time.monotonic()
        if (
            not force
            and self._signature is not None
            and (now - self._checked_at) < self.SIGNATURE_TTL_SECONDS
        ):
            self.stats.cache_hits += 1
            return self.stats
        started = time.perf_counter()
        scanned = self._scan()
        signature = (
            (0, 0.0)
            if not scanned
            else (len(scanned), round(max(mtime for _, mtime in scanned), 3))
        )
        if not force and signature == self._signature:
            self._checked_at = now
            self.stats.cache_hits += 1
            return self.stats
        entries: list[dict[str, Any]] = []
        broken = 0
        cache: dict[str, tuple[float, dict[str, Any]]] = {}
        reused = 0
        for run_id, mtime in scanned:
            cached = self._cache.get(run_id)
            if cached is not None and cached[0] == mtime:
                # 文件没变：直接复用上次解析结果，不读盘。
                cache[run_id] = cached
                entries.append(cached[1])
                reused += 1
                continue
            manifest_path = self.base / run_id / MANIFEST
            try:
                text = manifest_path.read_text(encoding="utf-8")
                manifest = json.loads(text)
            except (OSError, ValueError):
                broken += 1
                continue
            if not isinstance(manifest, dict) or manifest.get("run_id") != run_id:
                broken += 1
                continue
            entry = _entry(manifest)
            cache[run_id] = (mtime, entry)
            entries.append(entry)
        entries.sort(key=lambda item: (item["created_at"], item["run_id"]), reverse=True)
        self._cache = cache
        self._entries = entries
        self._signature = signature
        self._checked_at = time.monotonic()
        self.stats.runs = len(entries)
        self.stats.broken = broken
        self.stats.reused_entries = reused
        self.stats.rebuilds += 1
        self.stats.last_rebuild_ms = (time.perf_counter() - started) * 1000
        self.stats.bytes_estimate = len(entries) * 320
        return self.stats

    # ------------------------------------------------------------------ queries
    @property
    def entries(self) -> list[dict[str, Any]]:
        self.refresh()
        return self._entries

    def filter(
        self,
        *,
        map_id: str = "",
        state: str = "",
        mode: str = "",
        provider_id: str = "",
        model: str = "",
        query: str = "",
        since: str = "",
        success: bool | None = None,
    ) -> list[dict[str, Any]]:
        text = query.strip().lower()
        rows: list[dict[str, Any]] = []
        for entry in self.entries:
            if map_id and entry["map_id"] != map_id:
                continue
            if state and entry["state"] != state:
                continue
            if mode and entry["mode"] != mode:
                continue
            if provider_id and entry["provider_id"] != provider_id:
                continue
            if model and entry["model"] != model:
                continue
            if success is not None and bool(entry["success"]) is not success:
                continue
            if since and entry["created_at"][:10] < since[:10]:
                continue
            if text:
                haystack = " ".join(
                    (
                        entry["run_id"],
                        entry["map_id"],
                        entry["model"],
                        str(entry["outcome"] or ""),
                    )
                ).lower()
                if text not in haystack:
                    continue
            rows.append(entry)
        return rows

    def page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        lazy: bool = True,
        **filters: Any,
    ) -> dict[str, Any]:
        """服务端分页：只返回请求页，同时给出总数与是否还有更多。

        ``lazy=True`` 且**没有任何筛选**时走懒加载：只 stat 目录拿到总数，
        按 ``run_id``（内含 UTC 时间戳）排序后仅解析当前页的 manifest。
        这让"打开历史列表"不再随历史总量线性变慢。
        带筛选时必须读全部 manifest（筛选条件不在目录名里）。
        """

        offset = max(0, int(offset))
        limit = max(1, min(500, int(limit)))
        active = {key: value for key, value in filters.items() if value not in ("", None)}
        if lazy and not active and self._signature is None:
            lazy_page = self._lazy_page(offset=offset, limit=limit)
            if lazy_page is not None:
                return lazy_page
        rows = self.filter(**filters)
        window = rows[offset : offset + limit]
        return {
            "rows": window,
            "total": len(rows),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(rows),
            "stats": self.stats.as_dict(),
        }

    def _lazy_page(self, *, offset: int, limit: int) -> dict[str, Any] | None:
        """只读当前页的 manifest；run_id 不能排序时返回 ``None`` 回退全量。"""

        started = time.perf_counter()
        names = self._scan_names()
        if not names:
            return None
        # run_id 形如 web-YYYYMMDDTHHMMSSZ-xxxxxxxx：字典序 == 创建时间序。
        if not all(name.startswith("web-") for name in names):
            return None
        ordered = sorted(names, reverse=True)
        window_ids = ordered[offset : offset + limit]
        rows: list[dict[str, Any]] = []
        for run_id in window_ids:
            manifest_path = self.base / run_id / MANIFEST
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(manifest, dict):
                rows.append(_entry(manifest))
        self.stats.last_rebuild_ms = (time.perf_counter() - started) * 1000
        self.stats.runs = len(ordered)
        return {
            "rows": rows,
            "total": len(ordered),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(ordered),
            "lazy": True,
            "stats": self.stats.as_dict(),
        }

    def aggregate(self, **filters: Any) -> dict[str, Any]:
        """按地图 / 状态 / 模式聚合（不读 replay、不读事件）。"""

        rows = self.filter(**filters)
        by_map: dict[str, int] = {}
        by_state: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        successes = 0
        cost = 0.0
        cost_unknown = 0
        for row in rows:
            by_map[row["map_id"]] = by_map.get(row["map_id"], 0) + 1
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
            by_mode[row["mode"]] = by_mode.get(row["mode"], 0) + 1
            successes += 1 if row["success"] else 0
            if row["cost_unknown"]:
                cost_unknown += 1
            elif row["cost_settled_cny"] is not None:
                cost += float(row["cost_settled_cny"])
        return {
            "runs": len(rows),
            "successes": successes,
            "by_map": dict(sorted(by_map.items())),
            "by_state": dict(sorted(by_state.items())),
            "by_mode": dict(sorted(by_mode.items())),
            "cost_cny": round(cost, 8),
            "cost_unknown_runs": cost_unknown,
            "stats": self.stats.as_dict(),
        }


def page_rows(
    rows: Iterable[dict[str, Any]], *, offset: int, limit: int
) -> dict[str, Any]:
    """纯函数分页（供不依赖索引的调用方复用）。"""

    items = list(rows)
    offset = max(0, int(offset))
    limit = max(1, int(limit))
    window = items[offset : offset + limit]
    return {
        "rows": window,
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(items),
    }


__all__ = [
    "INDEX_FIELDS",
    "IndexStats",
    "RunIndex",
    "page_rows",
]
