"""Batch 9 补强：`KEY_ACTION_USED_NO_TRIGGER` 的逐局判读。

`failure-attribution.md` 给出标签分布，但不回答“为什么机制没触发”。本模块对每个
**有效但未触发机制**的局做三项机械判读（只用 trace 与结果记录）：

1. **预算**：决策数是否已用完该图的决策预算；
2. **阈值**：终止码是否属于“撞到规则阈值”（窗口错过、容量、压力、扩散、电量等）；
3. **入口**：机制动作是否尝试过、被拒多少次、最后一条动作是什么。

输出 `docs/v10/trigger-gap-analysis.md`：每一局的判读 + 逐图主因 + Oracle 预算余量。
这不是新的模型实验，只是对既有 trace 的二次判读。

用法：``python -m agent_arena.v10.trigger_gap``
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from agent_arena.v10.attribution import MECHANISM_TOOLS, _trace_rows
from agent_arena.v10.evidence_state import effective_mimo_rows
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.validation import _baseline, _budget

THRESHOLD_MARKERS = (
    "WINDOW",
    "CAPACITY",
    "COLLISION",
    "FLOOD",
    "STRAND",
    "PRESSURE",
    "OXYGEN",
    "LIMIT",
    "MISSED",
    "DEPLETED",
    "DISPATCH",
    "SEGMENT",
    "STATION",
    "RETURN",
    "TIMEOUT",
)


@dataclass
class TriggerGap:
    run_id: str
    map_id: str
    seed: int
    decisions: int
    budget: int
    termination: str
    primary: Any
    key_tools: list[str]
    attempts: dict[str, int]
    rejected: dict[str, int]
    last_action: str
    last_result: str
    judgement: str
    note: str


def _judge(row: dict[str, Any], gap: TriggerGap) -> tuple[str, str]:
    if gap.decisions >= gap.budget:
        return (
            "BUDGET",
            "决策预算用尽时仍未触发机制：需要更大预算或更快的策略",
        )
    if any(marker in gap.termination.upper() for marker in THRESHOLD_MARKERS):
        return (
            "THRESHOLD",
            "撞到规则阈值（窗口/容量/压力/电量等）而终局：属真实失败路径",
        )
    if not gap.attempts or all(count == 0 for count in gap.attempts.values()):
        return (
            "ENTRY_NOT_ATTEMPTED",
            "机制动作一次都没尝试：策略没有走到机制入口",
        )
    attempted = {name: count for name, count in gap.attempts.items() if count}
    if attempted and all(
        count == gap.rejected.get(name, 0) for name, count in attempted.items()
    ):
        return (
            "ENTRY_REJECTED",
            "机制动作全部被拒：前置条件（工具/位置/状态）未满足",
        )
    return (
        "USED_NO_THRESHOLD",
        "机制动作被接受但阈值未达成：预算、时序或数量不足",
    )


def analyse() -> dict[str, Any]:
    rows: list[TriggerGap] = []
    for map_id, items in sorted(effective_mimo_rows().items()):
        budget = _budget(map_id)
        key_tools = list(MECHANISM_TOOLS.get(map_id, ()))
        for row in items:
            if row.get("mechanism_triggered"):
                continue
            trace = _trace_rows(str(row["run_id"]))
            attempts = {name: 0 for name in key_tools}
            rejected = {name: 0 for name in key_tools}
            last_action = ""
            last_result = ""
            for item in trace:
                action = item.get("action")
                result = str(item.get("result") or "")
                if isinstance(action, dict) and "invalid_output" not in action:
                    tool = str(action.get("tool") or "")
                    last_action = tool
                    last_result = result
                    if tool in attempts:
                        attempts[tool] += 1
                        rejected_prefix = (
                            "INVALID",
                            "NO_",
                            "NOT_",
                            "UNKNOWN",
                            "ALREADY",
                            "TARGET_",
                        )
                        if result.startswith(rejected_prefix):
                            rejected[tool] += 1
                else:
                    last_action = "invalid_output"
                    last_result = result
            gap = TriggerGap(
                run_id=str(row["run_id"]),
                map_id=map_id,
                seed=int(row.get("environment_seed", 0)),
                decisions=int(row.get("decision_count") or 0),
                budget=budget,
                termination=str(row.get("termination")),
                primary=row.get("primary_metric_value"),
                key_tools=key_tools,
                attempts=attempts,
                rejected=rejected,
                last_action=last_action,
                last_result=last_result,
                judgement="",
                note="",
            )
            gap.judgement, gap.note = _judge(row, gap)
            rows.append(gap)
    by_map: dict[str, list[TriggerGap]] = {}
    for gap in rows:
        by_map.setdefault(gap.map_id, []).append(gap)
    summary: dict[str, dict[str, Any]] = {}
    for map_id, gaps in sorted(by_map.items()):
        counts: dict[str, int] = {}
        for gap in gaps:
            counts[gap.judgement] = counts.get(gap.judgement, 0) + 1
        payload = _baseline(map_id)
        oracle_actions = max(
            (int(row.get("decisions") or 0) for row in payload.get("oracle", [])), default=0
        )
        summary[map_id] = {
            "untriggered": len(gaps),
            "judgements": counts,
            "budget": _budget(map_id),
            "oracle_actions": oracle_actions,
            "budget_headroom": _budget(map_id) - oracle_actions,
            "decisions": sorted(gap.decisions for gap in gaps),
        }
    return {
        "schema": "v10-trigger-gap-1",
        "rows": [asdict(gap) for gap in rows],
        "summary": summary,
        "totals": {
            "maps": len(by_map),
            "runs": len(rows),
            "judgements": _count([gap.judgement for gap in rows]),
        },
    }


def _count(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def render(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "# V10 未触发机制局的逐局判读",
        "",
        "- 由 `python -m agent_arena.v10.trigger_gap` 生成；只读既有 MiMo trace 与基线产物。",
        f"- 覆盖 **{totals['runs']}** 局（{totals['maps']} 张图），",
        "  全部是“有效但 `mechanism_triggered=False`”。",
        "- 判读规则：`BUDGET`（预算用尽）｜`THRESHOLD`（撞规则阈值）｜",
        "`ENTRY_NOT_ATTEMPTED`（没尝试机制动作）｜`ENTRY_REJECTED`（机制动作全被拒）｜",
        "`USED_NO_THRESHOLD`（用了但没达成）。",
        "",
        "## 1. 分布",
        "",
        "| 判读 | 局数 |",
        "|---|---:|",
    ]
    for name, count in sorted(totals["judgements"].items()):
        lines.append(f"| `{name}` | {count} |")
    lines += [
        "",
        "## 2. 逐图",
        "",
        "| 图 | 未触发局 | 判读 | 决策预算 | Oracle 动作 | 预算余量 | 决策数 |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for map_id, item in payload["summary"].items():
        judgements = "；".join(
            f"`{name}`×{count}" for name, count in sorted(item["judgements"].items())
        )
        lines.append(
            f"| {map_id} | {item['untriggered']} | {judgements} | {item['budget']} | "
            f"{item['oracle_actions']} | {item['budget_headroom']} | "
            f"{', '.join(str(value) for value in item['decisions'])} |"
        )
    lines += [
        "",
        "## 3. 逐局明细",
        "",
        "| 图 | seed | run_id | 判读 | 决策/预算 | 终止 |",
        "机制动作（尝试/被拒） | 最后动作 → 结果 |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        attempts = "、".join(
            f"`{name}` {count}/{row['rejected'].get(name, 0)}"
            for name, count in row["attempts"].items()
        ) or "—"
        lines.append(
            f"| {row['map_id']} | {row['seed']} | `{row['run_id']}` | `{row['judgement']}` | "
            f"{row['decisions']}/{row['budget']} | {row['termination']} | {attempts} | "
            f"`{row['last_action']}` → {row['last_result']} |"
        )
    lines += [
        "",
        "## 4. 结论",
        "",
        "- `BUDGET` 的图：预算与 Oracle 动作数的余量足够，模型仍用尽预算 ⇒",
        "  属**策略效率**问题，不是预算过紧。",
        "- `THRESHOLD` 的图：终止码是规则阈值，说明模型确实进入了机制路径但在时序/容量上失败。",
        "- `ENTRY_NOT_ATTEMPTED` 的图：模型从未尝试机制动作 ⇒ 需要检查公开规则是否",
        "  把入口讲清楚（V10 已补 MAP-02/05/27/01 的 `public_rules()`）。",
        "- `USED_NO_THRESHOLD` 的图：最接近“能力边界”，适合作为 V11 的难度与提示设计依据。",
        "",
        "## 5. 复算",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.trigger_gap",
        "```",
    ]
    return "\n".join(lines) + "\n"


def castle_budget() -> dict[str, Any]:
    """古堡三图的决策预算剖面：预算 vs Oracle 动作数、动作直方图、最后 5 个动作。"""

    rows: list[dict[str, Any]] = []
    for map_id in ("MAP-28", "MAP-29", "MAP-30"):
        payload = _baseline(map_id)
        oracle_actions = max(
            (int(row.get("decisions") or 0) for row in payload.get("oracle", [])), default=0
        )
        for row in effective_mimo_rows().get(map_id, []):
            histogram: dict[str, int] = {}
            tail: list[str] = []
            for item in _trace_rows(str(row["run_id"])):
                action = item.get("action")
                if isinstance(action, dict) and "invalid_output" not in action:
                    tool = str(action.get("tool") or "")
                    histogram[tool] = histogram.get(tool, 0) + 1
                    tail.append(f"{tool}→{item.get('result')}")
                    tail = tail[-5:]
            rows.append(
                {
                    "map_id": map_id,
                    "seed": int(row.get("environment_seed", 0)),
                    "run_id": str(row["run_id"]),
                    "decisions": int(row.get("decision_count") or 0),
                    "budget": _budget(map_id),
                    "oracle_actions": oracle_actions,
                    "termination": str(row.get("termination")),
                    "mechanism_triggered": bool(row.get("mechanism_triggered")),
                    "primary": row.get("primary_metric_value"),
                    "histogram": dict(sorted(histogram.items())),
                    "tail": tail,
                }
            )
    return {"schema": "v10-castle-budget-1", "rows": rows}


def render_castle(payload: dict[str, Any]) -> str:
    lines = [
        "# V10 古堡三图的决策预算剖面",
        "",
        "- 由 `python -m agent_arena.v10.trigger_gap` 生成；只读既有 MiMo trace 与基线产物。",
        "- 目的：判断 28/29/30 的失败是“预算过紧”还是“策略在案卷链上打转”。",
        "",
        "| 图 | seed | 决策/预算 | Oracle 动作 | 终止 | 机制触发 | 主指标 | 动作直方图 |",
        "|---|---:|---|---:|---|---|---|---|",
    ]
    for row in payload["rows"]:
        histogram = "、".join(f"`{name}`×{count}" for name, count in row["histogram"].items())
        lines.append(
            f"| {row['map_id']} | {row['seed']} | {row['decisions']}/{row['budget']} | "
            f"{row['oracle_actions']} | {row['termination']} | "
            f"{'是' if row['mechanism_triggered'] else '否'} | {row['primary']} | {histogram} |"
        )
    lines += [
        "",
        "## 最后 5 个动作（每局）",
        "",
    ]
    for row in payload["rows"]:
        lines.append(f"- `{row['run_id']}`：")
        for item in row["tail"]:
            lines.append(f"  - {item}")
    lines += [
        "",
        "## 判读",
        "",
        "- 若 `决策/预算` 用满且 Oracle 动作数明显更少 ⇒ 预算是绑定约束，",
        "  但“更少的动作就能完成”说明",
        "  模型在案卷链上打转（重复 investigate / move / record），属策略问题而非地图不可解。",
        "- 若主指标已非 0（如 MAP-30 的 0.5–0.75）而终止是预算耗尽 ⇒ 目标是可被部分完成的，",
        "  缺的是“收尾提交”这一步。",
        "- 结论用于 V11 的预算与提示设计，不改变本阶段的难度标签。",
        "",
        "## 复算",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.trigger_gap",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = analyse()
    output = V10_RUNS / "trigger_gap"
    output.mkdir(parents=True, exist_ok=True)
    (output / "trigger_gap.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (V10_DOCS / "trigger-gap-analysis.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    castle = castle_budget()
    (output / "castle_budget.json").write_text(
        json.dumps(castle, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (V10_DOCS / "castle-budget-analysis.md").write_text(
        render_castle(castle), encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload["totals"], ensure_ascii=False))


__all__ = ["TriggerGap", "analyse", "castle_budget", "main", "render", "render_castle"]


if __name__ == "__main__":
    main()
