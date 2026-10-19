"""Batch 9 补充：MiMo 局的 trace 级失败归因。

`mimo-results.md` 给出逐局结果与结局分类，但不回答“为什么核心机制没被触发”。
本模块**逐局回放 trace 的动作序列**（`runs/v10/mimo/episodes/<run_id>/agent_trace.jsonl`），
按公开的机制动作集统计“是否尝试、是否被拒、是否被接受”，给出机器可读的归因标签：

| 标签 | 判据 |
|---|---|
| `TRIGGERED` | `mechanism_triggered=True` |
| `CONTRACT_ARTIFACT` | 非法动作占比 > 50%（接口假象，结论不可用） |
| `KEY_ACTION_NEVER_ATTEMPTED` | 机制动作一次都没调用 |
| `KEY_ACTION_ATTEMPTED_REJECTED` | 调用过机制动作，但全部被环境拒绝（前置条件不满足） |
| `KEY_ACTION_USED_NO_TRIGGER` | 机制动作被接受，但 `mechanism_triggered`
仍为假（阈值/时序没到位） |

`MECHANISM_TOOLS` 是逐图**机制动作集**：哪些工具的成功使用构成“核心机制被触发”，
依据各图 DCR 与 `runs/v10/baselines/mapXX.py` 的 oracle/消融实现。它是分析口径，不是环境真值。

用法：``python -m agent_arena.v10.attribution``
输出：``runs/v10/attribution/mimo_attribution.json`` 与 ``docs/v10/failure-attribution.md``。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_arena.v10.evidence_state import effective_mimo_rows, is_interrupted, mimo_rows
from agent_arena.v10.paths import REPO_ROOT, V10_DOCS, V10_RUNS

EPISODES = V10_RUNS / "mimo" / "episodes"
REJECT_PREFIXES = (
    "INVALID",
    "NO_",
    "NOT_",
    "UNKNOWN",
    "ALREADY",
    "TARGET_",
    "TASK_",
    "REQUIRES",
    "RULE_",
    "PREDICTION_",
    "QUESTION_",
    "OUT_OF",
    "TOO_",
    "MISSING",
    "FLOW_",
    "FEEDER_",
    "SOURCE_",
    "LOAD_",
    "BYPASS_",
    "INSPECTION_",
    "WINDOW",
    "OFF_ROUTE",
)

#: 逐图机制动作集（成功使用 = 核心机制被触发的主要途径）。
MECHANISM_TOOLS: dict[str, tuple[str, ...]] = {
    "MAP-03": ("write_memory", "submit"),
    "MAP-04": ("wait",),
    "MAP-06": ("interact",),
    "MAP-07": ("turn_valve",),
    "MAP-08": ("run_test", "seal_diagnosis"),
    "MAP-09": ("pump", "seal", "vent"),
    "MAP-10": ("load", "unload"),
    "MAP-11": ("search", "rescue"),
    "MAP-12": ("assign",),
    "MAP-13": ("record_constraint", "set_trial_layout", "verify_layout"),
    "MAP-14": ("compare_evidence", "submit_configuration"),
    "MAP-15": ("record_rule", "predict_transition"),
    "MAP-18": ("set_timetable",),
    "MAP-19": ("forecast_next",),
    "MAP-20": ("open_bypass",),
    "MAP-21": ("collect_and_carry_sample", "reinforce_sample_case"),
    "MAP-22": ("write_memory", "return_to_camp"),
    "MAP-23": ("scout", "mark"),
    "MAP-24": ("probe_bridge", "record_route", "measure_tide"),
    "MAP-26": ("run_test", "replace", "rollback"),
    "MAP-27": ("submit", "sample", "repair_relay"),
    "MAP-28": ("record", "read_record", "submit"),
    "MAP-29": ("ask", "compare_testimony", "submit"),
    "MAP-30": ("record", "compare_records", "formal_accuse"),
}


@dataclass
class RunAttribution:
    run_id: str
    map_id: str
    environment_seed: int
    valid: bool
    mechanism_triggered: bool
    decision_count: int
    invalid_ratio: float
    outcome: str
    termination: str
    primary_metric_value: Any
    key_tool_attempts: dict[str, int] = field(default_factory=dict)
    key_tool_rejected: dict[str, int] = field(default_factory=dict)
    tool_histogram: dict[str, int] = field(default_factory=dict)
    label: str = ""
    note: str = ""


def _trace_rows(run_id: str) -> list[dict[str, Any]]:
    """读取逐局动作序列；兼容两种产物布局。

    - 新布局（阶段 main 起）：``episodes/<run_id>/agent_trace.jsonl``；
    - 早期布局（最初 9 局）：``episodes/<run_id>.json`` 的单文件 ``history`` 字段
      （action + result，无 observation）。
    """

    path = EPISODES / run_id / "agent_trace.jsonl"
    if path.is_file():
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("event") == "decision":
                rows.append(payload)
        return rows
    legacy = EPISODES / f"{run_id}.json"
    if legacy.is_file():
        payload = json.loads(legacy.read_text(encoding="utf-8"))
        return [
            {"action": item.get("action"), "result": item.get("result")}
            for item in payload.get("history") or []
        ]
    return []


def _is_reject(result: str) -> bool:
    return result.startswith(REJECT_PREFIXES)


def attribute(row: dict[str, Any]) -> RunAttribution:
    run_id = str(row["run_id"])
    map_id = str(row["map_id"])
    decisions = int(row.get("decision_count") or 0)
    invalid = int(row.get("invalid_actions") or 0)
    invalid_ratio = (invalid / decisions) if decisions else 0.0
    key_tools = MECHANISM_TOOLS.get(map_id, ())
    attempts: dict[str, int] = {name: 0 for name in key_tools}
    rejected: dict[str, int] = {name: 0 for name in key_tools}
    histogram: dict[str, int] = {}
    for item in _trace_rows(run_id):
        action = item.get("action")
        if not isinstance(action, dict) or "invalid_output" in action:
            continue
        tool = str(action.get("tool") or "")
        if not tool:
            continue
        histogram[tool] = histogram.get(tool, 0) + 1
        if tool in attempts:
            attempts[tool] += 1
            if _is_reject(str(item.get("result") or "")):
                rejected[tool] += 1
    triggered = bool(row.get("mechanism_triggered"))
    if triggered:
        label, note = "TRIGGERED", "核心机制已触发"
    elif invalid_ratio > 0.5:
        label, note = "CONTRACT_ARTIFACT", "非法动作占比 > 50%，该局结论不可用"
    elif key_tools and all(attempts[name] == 0 for name in key_tools):
        label, note = "KEY_ACTION_NEVER_ATTEMPTED", "机制动作一次都没调用"
    elif key_tools and all(
        attempts[name] == 0 or rejected[name] == attempts[name] for name in key_tools
    ):
        label, note = "KEY_ACTION_ATTEMPTED_REJECTED", "机制动作全部被拒（前置条件未满足）"
    else:
        label, note = "KEY_ACTION_USED_NO_TRIGGER", "机制动作被接受，但触发条件未达成"
    return RunAttribution(
        run_id=run_id,
        map_id=map_id,
        environment_seed=int(row.get("environment_seed", 0)),
        valid=not is_interrupted(row),
        mechanism_triggered=triggered,
        decision_count=decisions,
        invalid_ratio=round(invalid_ratio, 3),
        outcome=str(row.get("outcome")),
        termination=str(row.get("termination")),
        primary_metric_value=row.get("primary_metric_value"),
        key_tool_attempts=attempts,
        key_tool_rejected=rejected,
        tool_histogram=dict(sorted(histogram.items())),
        label=label,
        note=note,
    )


def analyse() -> dict[str, Any]:
    rows = mimo_rows()
    effective_ids = {
        str(item["run_id"]) for items in effective_mimo_rows().values() for item in items
    }
    attributions = [attribute(row) for row in rows]
    return {
        "schema": "v10-mimo-attribution-1",
        "rows": [asdict(item) for item in attributions],
        "effective_run_ids": sorted(effective_ids),
        "labels": {
            label: sum(1 for item in attributions if item.label == label)
            for label in {
                item.label for item in attributions
            }
        },
    }


def _effective(payload: dict[str, Any]) -> list[dict[str, Any]]:
    keep = set(payload["effective_run_ids"])
    return [row for row in payload["rows"] if row["run_id"] in keep]


def render(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    effective = _effective(payload)
    labels = payload["labels"]
    lines = [
        "# V10 MiMo trace 级失败归因",
        "",
        "- 由 `python -m agent_arena.v10.attribution` 生成；逐局回放 `runs/v10/mimo/`",
        "  `episodes/` 的动作序列。",
        f"- 覆盖 **{len(rows)}** 局（其中有效局 {len(effective)}）；机制动作集见模块",
        "  `MECHANISM_TOOLS`。",
        "- 标签含义：`CONTRACT_ARTIFACT`（接口假象）｜`KEY_ACTION_NEVER_ATTEMPTED`｜"
        "`KEY_ACTION_ATTEMPTED_REJECTED`｜`KEY_ACTION_USED_NO_TRIGGER`｜`TRIGGERED`。",
        "",
        "## 1. 标签分布",
        "",
        "| 标签 | 局数 |",
        "|---|---:|",
    ]
    for label in sorted(labels):
        lines.append(f"| `{label}` | {labels[label]} |")
    lines += [
        "",
        "## 2. 逐局归因（有效局）",
        "",
        "| 图 | seed | run_id | 标签 | 决策数 | 非法率 | 机制动作（尝试/被拒） | 终止 | 主指标 |",
        "|---|---:|---|---|---:|---:|---|---|---|",
    ]
    for row in effective:
        attempts = "、".join(
            f"`{name}` {count}/{row['key_tool_rejected'].get(name, 0)}"
            for name, count in row["key_tool_attempts"].items()
        ) or "—"
        lines.append(
            f"| {row['map_id']} | {row['environment_seed']} | `{row['run_id']}` | "
            f"`{row['label']}` | {row['decision_count']} | {row['invalid_ratio']} | {attempts} | "
            f"{row['termination']} | {row['primary_metric_value']} |"
        )
    lines += [
        "",
        "## 3. 非触发局的归类",
        "",
        "| 图 | 局数 | 主因 | 说明 |",
        "|---|---:|---|---|",
    ]
    by_map: dict[str, list[dict[str, Any]]] = {}
    for row in effective:
        by_map.setdefault(row["map_id"], []).append(row)
    for map_id in sorted(by_map):
        items = by_map[map_id]
        untriggered = [item for item in items if item["label"] != "TRIGGERED"]
        if not untriggered:
            continue
        from collections import Counter

        counter = Counter(item["label"] for item in untriggered)
        main = counter.most_common(1)[0][0]
        lines.append(
            f"| {map_id} | {len(untriggered)}/{len(items)} | `{main}` | "
            f"{'；'.join(f'{k}×{v}' for k, v in counter.items())} |"
        )
    lines += [
        "",
        "## 4. 结论要点",
        "",
        "- `CONTRACT_ARTIFACT` 的局**不能**用于判断能力：必须在接口修复后重跑",
        "  （见 DCR-V10-24/25）。",
        "- `KEY_ACTION_NEVER_ATTEMPTED` 说明模型没有走到机制入口（多为策略/预算问题，",
        "  需结合动作直方图）；对应局的失败应记在“策略”而不是“环境”。",
        "- `KEY_ACTION_USED_NO_TRIGGER` 说明模型按机制动作操作，但阈值/时序没满足——这是",
        "  最有价值的“接近但未达成”信号，适合作为 V11 的难度与提示设计依据。",
        "",
        "## 5. 复算",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.attribution",
        "```",
        "",
        f"仓库根：`{REPO_ROOT}`。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = analyse()
    output = V10_RUNS / "attribution"
    output.mkdir(parents=True, exist_ok=True)
    (output / "mimo_attribution.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    (V10_DOCS / "failure-attribution.md").write_text(render(payload), encoding="utf-8")
    print(json.dumps(payload["labels"], ensure_ascii=False))


__all__ = ["MECHANISM_TOOLS", "RunAttribution", "analyse", "attribute", "main", "render"]


if __name__ == "__main__":
    main()
