"""只读历史记录装载：把 V12 导出的 CSV 归一成 V13 分析用 record。

为什么需要单独一层：

- V12 的 ``docs/v12/real-runs/*.csv`` 是**已脱敏、已公开**的逐局明细，是 V13 做
  历史再分析的唯一来源；直接读 ``runs/`` 会把本机真实账本拉进分析，既不可复现也
  有泄露风险；
- CSV 没有 ``prompt_hash`` / ``agent_config``，因此重复分析只能按
  ``(map, seed, agent_id)`` 分组并用 ``agent_config_hash`` 判断跨版本；
- 所有 record 都带 ``source="HISTORICAL"``，报告里必须显示，不能冒充 LIVE 新结果。

**不写任何文件，不改任何历史数据。**
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent_arena.lab.paths import REPO_ROOT

V12_REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"

#: 每份 CSV 的实验身份（人工登记；未登记的文件按 ad_hoc 处理）。
#: ``request_cap`` / ``input_token_cap`` / ``cost_cap_cny`` 来自对应脚本的显式预算，
#: 因为逐局 CSV 不落这三列；写进元数据后，MAP-30 的预算阶梯才能被还原。
V12_CSV_EXPERIMENTS: dict[str, dict[str, Any]] = {
    "main-54-runs.csv": {
        "experiment_id": "lab-20261025T120807Z-3aaedd0f",
        "label": "V12 主矩阵（六图 × 3 seed × 3 架构）",
        "kind": "matrix",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "replicate-16-18-runs.csv": {
        "experiment_id": "lab-20261026T012103Z-47f6701c",
        "label": "V12 重复实验 A",
        "kind": "replicate",
        "replicate_index": "1",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "replicate-16-18-b-runs.csv": {
        "experiment_id": "lab-20261026T020605Z-1b88a2ba",
        "label": "V12 重复实验 B",
        "kind": "replicate",
        "replicate_index": "2",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "map18-seed3-4-runs.csv": {
        "experiment_id": "lab-20261026T023641Z-4bb9b1e1",
        "label": "V12 MAP-18 seed 3/4 补充覆盖",
        "kind": "matrix",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "map22-contract2-runs.csv": {
        "experiment_id": "lab-20261025T132813Z-2b6ea6ae",
        "label": "V12 MAP-22 口径对齐（contract-2）",
        "kind": "version_rerun",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "map22-route-log-runs.csv": {
        "experiment_id": "lab-20261026T035514Z-30eb2d04",
        "label": "V12 MAP-22 route_log 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "map30-budget180-runs.csv": {
        "experiment_id": "lab-20261026T021401Z-7e1d2c94",
        "label": "V12 MAP-30 预算扩展（180 请求 / 200k token / ¥0.50）",
        "kind": "budget_extension",
        "replicate_index": "0",
        "request_cap": 180,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.50",
    },
    "map30-token600k-runs.csv": {
        "experiment_id": "lab-20261026T024803Z-b57d5bb9",
        "label": "V12 MAP-30 token 扩展（180 请求 / 600k token / ¥0.20）",
        "kind": "budget_extension",
        "replicate_index": "0",
        "request_cap": 180,
        "input_token_cap": 600_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-memory-on-runs.csv": {
        "experiment_id": "lab-20261026T040545Z-570cf40a",
        "label": "V12 memory on 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-memory-off-runs.csv": {
        "experiment_id": "lab-20261026T040545Z-570cf40a",
        "label": "V12 memory off 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-planning-on-runs.csv": {
        "experiment_id": "lab-20261026T040546Z-8c5b6a2f",
        "label": "V12 planning on 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-planning-off-runs.csv": {
        "experiment_id": "lab-20261026T040546Z-8c5b6a2f",
        "label": "V12 planning off 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-reflection-on-runs.csv": {
        "experiment_id": "lab-20261026T040547Z-1f9f0a3d",
        "label": "V12 reflection on 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
    "ablation-reflection-off-runs.csv": {
        "experiment_id": "lab-20261026T040547Z-1f9f0a3d",
        "label": "V12 reflection off 消融",
        "kind": "ablation",
        "replicate_index": "0",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "cost_cap_cny": "0.20",
    },
}

_NUMERIC = {
    "matrix_index",
    "environment_seed",
    "decisions",
    "requests",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "rejected_actions",
    "invalid_actions",
    "agent_events",
    "replicate_index",
    "request_cap",
    "decision_cap",
    "input_token_cap",
}
_FLOATS = {"cost_cny", "primary_value"}
_BOOLS = {"success", "cost_known"}


def _coerce(field: str, raw: str | None) -> Any:
    if raw is None or raw == "":
        return None
    if field in _BOOLS:
        return raw.strip().lower() in {"true", "1", "yes", "是"}
    if field in _NUMERIC:
        try:
            return int(float(raw))
        except ValueError:
            return None
    if field in _FLOATS:
        try:
            return float(raw)
        except ValueError:
            return None
    return raw


def load_csv(path: Path, *, source: str = "HISTORICAL") -> list[dict[str, Any]]:
    """读一份逐局 CSV，补上来源标签与重复编号。"""

    meta = V12_CSV_EXPERIMENTS.get(path.name, {})
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8-sig")
    for raw in csv.DictReader(text.splitlines()):
        record: dict[str, Any] = {
            key: _coerce(key, value) for key, value in raw.items()
        }
        record.setdefault("replicate_index", None)
        if record.get("replicate_index") is None:
            record["replicate_index"] = int(meta.get("replicate_index") or 0)
        record["source"] = source
        record["source_file"] = path.name
        record["experiment_id"] = meta.get("experiment_id", f"csv:{path.stem}")
        record["experiment_label"] = meta.get("label", path.stem)
        record["experiment_kind"] = meta.get("kind", "ad_hoc")
        record.setdefault("prompt_hash", "")
        record.setdefault("agent_config", {})
        # 逐局 CSV 不落单局预算上限；用登记元数据补齐，缺失就留 None（不编造）。
        for field, key in (
            ("request_cap", "request_cap"),
            ("input_token_cap", "input_token_cap"),
            ("cost_cap_cny", "cost_cap_cny"),
        ):
            if record.get(field) is None and meta.get(key) is not None:
                value = meta[key]
                record[field] = int(value) if field != "cost_cap_cny" else str(value)
        rows.append(record)
    return rows


def load_v12_history(
    *, base: Path | None = None, names: list[str] | None = None
) -> list[dict[str, Any]]:
    """装载 V12 真实逐局 CSV（默认全部登记过的文件）。"""

    directory = base or V12_REAL_RUNS
    selected = names or sorted(V12_CSV_EXPERIMENTS)
    records: list[dict[str, Any]] = []
    for name in selected:
        path = directory / name
        if not path.is_file():
            continue
        records.extend(load_csv(path))
    return records


def history_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    """历史概览：按实验分组，给出局数、成功、费用与时间范围。"""

    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("experiment_id") or "")
        bucket = groups.setdefault(
            key,
            {
                "experiment_id": key,
                "label": record.get("experiment_label"),
                "kind": record.get("experiment_kind"),
                "files": set(),
                "runs": 0,
                "successes": 0,
                "cost_cny": 0.0,
                "cost_known_runs": 0,
                "maps": set(),
            },
        )
        bucket["files"].add(str(record.get("source_file")))
        bucket["runs"] += 1
        bucket["successes"] += 1 if record.get("success") else 0
        bucket["maps"].add(str(record.get("map_id")))
        if record.get("cost_known") and record.get("cost_cny") is not None:
            bucket["cost_cny"] += float(record["cost_cny"])
            bucket["cost_known_runs"] += 1
    output: dict[str, Any] = {"runs": len(records), "experiments": {}}
    for key, bucket in sorted(groups.items()):
        output["experiments"][key] = {
            **bucket,
            "files": sorted(bucket["files"]),
            "maps": sorted(bucket["maps"]),
            "cost_cny": round(bucket["cost_cny"], 8),
        }
    return output


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "V12_CSV_EXPERIMENTS",
    "V12_REAL_RUNS",
    "history_index",
    "load_csv",
    "load_v12_history",
    "write_json",
]
