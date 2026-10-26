"""性能压力测试：1 000 / 5 000 条历史的分页、筛选、聚合与导出（P2-2）。

安全约束：

- **只在临时目录**生成压力数据；如果目标路径落在仓库的 ``runs/`` 下，直接拒绝；
- 合成 manifest 带 ``"stress_data": true``，永远不会被当成真实账本；
- 不启动服务、不发请求、不写付费账本。

测量项：冷启动索引耗时、热分页耗时、筛选、聚合、导出字节数与峰值内存
（``tracemalloc``）。所有数字都是**本机实测**，报告里注明环境。
"""

from __future__ import annotations

import json
import platform
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.v10.runtime.catalog import MAP_IDS
from agent_arena.web.index import RunIndex

STATES = ("SUCCEEDED", "FAILED", "BUDGET_REACHED", "CANCELLED", "PROVIDER_ERROR")
MODES = ("live", "simulated")
MODELS = ("mimo-v2.6-flash", "simulated-agent-policy")
DEFAULT_COUNTS: tuple[int, ...] = (1_000, 5_000)


def _guard(path: Path) -> None:
    resolved = path.resolve()
    real_runs = (REPO_ROOT / "runs").resolve()
    if resolved == real_runs or real_runs in resolved.parents:
        raise ValueError("压力测试不得写入仓库 runs/：请使用临时目录。")


def synthesize_history(
    base: Path, count: int, *, seed: int = 0, events_per_run: int = 0
) -> dict[str, Any]:
    """生成 ``count`` 条合成 run（manifest + 可选事件文件）。"""

    _guard(base)
    base.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(count):
        created = start + timedelta(minutes=index)
        stamp = created.strftime("%Y%m%dT%H%M%SZ")
        serial = index + seed * 7_919
        run_id = f"web-{stamp}-{serial:08x}"
        map_id = MAP_IDS[(index + seed) % len(MAP_IDS)]
        state = STATES[index % len(STATES)]
        mode = MODES[index % len(MODES)]
        model = MODELS[0] if mode == "live" else MODELS[1]
        manifest = {
            "schema_version": "v11-web-1",
            "run_id": run_id,
            "map_id": map_id,
            "world": "stress",
            "mode": mode,
            "provider_id": "openai_compatible" if mode == "live" else "simulated_scripted",
            "model": model,
            "environment_seed": index % 5,
            "state": state,
            "outcome": "success" if state == "SUCCEEDED" else "scenario_failure",
            "success": state == "SUCCEEDED",
            "decisions": 10 + index % 40,
            "decision_budget": 90,
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "finished_at": created.isoformat().replace("+00:00", "Z"),
            "budget": {
                "requests": 10 + index % 60,
                "cost_settled_cny": f"{(index % 97) / 1000:.8f}",
                "cost_unknown": index % 211 == 0,
            },
            "hashes": {
                "rule_hash": f"rule-{map_id}",
                "metric_hash": f"metric-{map_id}",
                "metric_schema_hash": "schema-1",
            },
            "experiment_id": f"lab-stress-{index // 50:04d}",
            "stress_data": True,
        }
        directory = base / run_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        if events_per_run:
            with (directory / "events.jsonl").open("w", encoding="utf-8") as handle:
                for step in range(events_per_run):
                    handle.write(
                        json.dumps(
                            {
                                "event": "decision",
                                "decision_index": step + 1,
                                "result": "ok",
                            }
                        )
                        + "\n"
                    )
    return {
        "base": str(base),
        "count": count,
        "events_per_run": events_per_run,
        "label": "STRESS_DATA",
    }


@dataclass
class Timing:
    label: str
    milliseconds: float
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "milliseconds": round(self.milliseconds, 2),
            "detail": self.detail,
        }


@dataclass
class StressResult:
    count: int
    timings: list[Timing] = field(default_factory=list)
    peak_kib: float = 0.0
    index_bytes: int = 0
    export_bytes: int = 0
    environment: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "v13-performance-1",
            "runs": self.count,
            "timings": [item.as_dict() for item in self.timings],
            "peak_memory_kib": round(self.peak_kib, 2),
            "index_bytes_estimate": self.index_bytes,
            "export_bytes": self.export_bytes,
            "environment": self.environment,
        }


def _time(label: str, function: Any, *, detail: str = "") -> tuple[Any, Timing]:
    started = time.perf_counter()
    value = function()
    elapsed = (time.perf_counter() - started) * 1000
    return value, Timing(label=label, milliseconds=elapsed, detail=detail)


def stress_index(base: Path, *, label: str = "") -> StressResult:
    """对一个历史目录做冷/热分页、筛选、聚合与导出测量。

    计时**不**在 tracemalloc 下进行（tracemalloc 会把分配放大数倍，测出的耗时
    不可用）；峰值内存单独用第二个索引实例测量，并注明包含索引构建。

    **预热**：测量前先把全部 manifest 读一遍（不计时）。压力数据是刚写入的临时
    文件，首次读取会触发杀毒/索引扫描，代价可达常态的 10–80 倍；不预热会把
    "安全软件扫描"误读成"我们的代码慢"。预热后仍保留 `index_cold_build` 一项，
    但它同样发生在预热之后，读作"文件已在页缓存时的解析成本"。
    """

    # 预热（不计时）：让 OS 页缓存与安全软件扫描先发生。
    for directory in base.iterdir():
        manifest = directory / "manifest.json"
        if manifest.is_file():
            try:
                manifest.read_text(encoding="utf-8")
            except OSError:
                continue

    index = RunIndex(base)
    result = StressResult(
        count=0,
        environment={
            "platform": platform.platform(),
            "python": platform.python_version(),
            "label": label or "STRESS_DATA",
        },
    )
    _, cold = _time(
        "index_cold_build",
        index.refresh,
        detail="首次构建（文件已在页缓存；含 JSON 解析）",
    )
    result.timings.append(cold)
    _, rebuild = _time(
        "index_rebuild_incremental",
        lambda: index.refresh(force=True),
        detail="强制重建：只重读 mtime 变化的文件",
    )
    result.timings.append(rebuild)
    _, warm = _time("page_first_50", lambda: index.page(offset=0, limit=50))
    result.timings.append(warm)
    # 全新实例的第一页（懒加载）：只 stat 目录 + 读当前页，模拟"用户打开历史列表"。
    fresh = RunIndex(base)
    _, lazy_first = _time(
        "page_first_50_lazy_new_index",
        lambda: fresh.page(offset=0, limit=50),
        detail="全新索引的第一页（只读当前页 manifest）",
    )
    result.timings.append(lazy_first)
    _, page_mid = _time(
        "page_offset_1000",
        lambda: index.page(offset=min(1_000, max(0, index.stats.runs - 1)), limit=50),
    )
    result.timings.append(page_mid)
    _, filtered = _time(
        "filter_map_state", lambda: index.filter(map_id="MAP-16", state="FAILED")
    )
    result.timings.append(filtered)
    _, aggregate = _time("aggregate", index.aggregate)
    result.timings.append(aggregate)
    rows = index.entries

    def _export_bytes() -> int:
        return len(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")
        )

    export_bytes, export = _time("export_json_bytes", _export_bytes)
    result.timings.append(export)

    # 峰值内存：独立实例 + tracemalloc，只用于内存口径。
    tracemalloc.start()
    probe = RunIndex(base)
    probe.refresh(force=True)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result.peak_kib = peak / 1024
    result.count = index.stats.runs
    result.index_bytes = index.stats.bytes_estimate
    result.export_bytes = int(export_bytes)
    return result


def run_stress(
    counts: tuple[int, ...] = DEFAULT_COUNTS, *, events_per_run: int = 0
) -> dict[str, Any]:
    """在临时目录跑完整压力测试，返回可写文档的报告。"""

    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-stress-") as temporary:
        root = Path(temporary)
        for count in counts:
            base = root / f"history-{count}"
            synthesize_history(base, count, events_per_run=events_per_run)
            results.append(stress_index(base, label=f"STRESS_DATA:{count}").as_dict())
    return {
        "schema": "v13-performance-report-1",
        "counts": list(counts),
        "events_per_run": events_per_run,
        "results": results,
        "note": (
            "压力数据是合成的，放在临时目录，永不进入真实账本；"
            "所有耗时为本机实测，不代表 CI 或用户机器。"
        ),
    }


def performance_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 性能压力测试（合成历史）",
        "",
        f"- 数据：{report.get('counts')} 条合成 run（`STRESS_DATA`，临时目录）",
        f"- 事件文件：每局 {report.get('events_per_run')} 条",
        f"- 说明：{report.get('note')}",
        "",
    ]
    # 关键数字（横向对比，便于一眼看出规模效应）
    results = report.get("results") or []
    if results:
        labels = [
            "index_cold_build",
            "index_rebuild_incremental",
            "page_first_50_lazy_new_index",
            "page_first_50",
            "aggregate",
        ]
        lines += [
            "## 关键数字（横向对比）",
            "",
            "| 操作 | " + " | ".join(f"{item.get('runs')} 条" for item in results) + " |",
            "|---" * (len(results) + 1) + "|",
        ]
        for label in labels:
            cells: list[str] = []
            for item in results:
                value = next(
                    (
                        timing["milliseconds"]
                        for timing in item.get("timings") or []
                        if timing["label"] == label
                    ),
                    None,
                )
                cells.append("—" if value is None else f"{value} ms")
            lines.append(f"| `{label}` | " + " | ".join(cells) + " |")
        lines.append(
            "| 峰值内存 | "
            + " | ".join(f"{item.get('peak_memory_kib')} KiB" for item in results)
            + " |"
        )
        lines.append("")
    for result in report.get("results") or []:
        env = result.get("environment") or {}
        lines += [
            f"## {result.get('runs')} 条历史",
            "",
            f"- 环境：{env.get('platform')} / Python {env.get('python')}",
            f"- 峰值内存：{result.get('peak_memory_kib')} KiB",
            f"- 索引内存估算：{result.get('index_bytes_estimate')} B",
            f"- 导出字节数：{result.get('export_bytes')} B",
            "",
            "| 操作 | 耗时 ms | 说明 |",
            "|---|---:|---|",
        ]
        for item in result.get("timings") or []:
            lines.append(
                f"| `{item['label']}` | {item['milliseconds']} | {item.get('detail') or '—'} |"
            )
        lines.append("")
    lines += [
        "## 结论口径",
        "",
        "- 分页只返回请求页，内存不随历史总量线性增长（索引只存列表字段）；",
        "- 冷启动需要解析全部 manifest，这是 O(n) 的一次性成本；热查询命中索引；",
        "- 事件文件不进入索引，回放时才按 run 读取，避免页面一次加载全部轨迹。",
        "",
        "### 测量方法（先读这一节）",
        "",
        "- 测量前先把全部 manifest 读一遍**预热**（不计时）：压力数据是刚写入的临时",
        "  文件，首次读取会触发杀毒/索引扫描，单文件代价可达常态的 10–80 倍；",
        "  不预热会把「安全软件扫描」误读成「我们的代码慢」。",
        "- 因此 `index_cold_build` 读作「文件已在页缓存时的解析成本」，",
        "  而不是「首次安装后第一次打开页面的耗时」。",
        "- `page_first_50_lazy_new_index` 是「全新索引 + 只读当前页」的路径：",
        "  目录只 stat、只解析 50 个 manifest，条目数与历史总量无关。",
        "- `page_offset_1000` / `filter_map_state` / `aggregate` 在同一个已建索引上，",
        "  读作「日常翻页/筛选/汇总」成本。",
        "- 目录签名有 30 秒 TTL：TTL 内不重新 stat 全部目录；写入新 run 时",
        "  `RunService.invalidate_index()` 会立刻失效缓存。",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_COUNTS",
    "StressResult",
    "Timing",
    "performance_markdown",
    "run_stress",
    "stress_index",
    "synthesize_history",
]
