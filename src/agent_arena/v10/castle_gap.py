"""古堡三图（MAP-28/29/30）的“距离完成还差什么”量化。

只读本地 MiMo trace 的最终 Observation：

- MAP-28：已记录证据 vs 必备关键证据、终局位置（提交点在 H）；
- MAP-29：已问/剩余问题、比对结果、终局位置（提交点在 Y）；
- MAP-30：案卷条目完成数、链条是否核对、终局位置 vs 法庭节点。

输出 ``docs/v10/castle-gap-analysis.md``。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v10.attribution import _trace_rows
from agent_arena.v10.paths import V10_DOCS

RUNS: dict[str, tuple[str, ...]] = {
    "MAP-28": ("V10-MAP-28-S0-i2", "V10-MAP-28-S1-i2", "V10-MAP-28-S2-i2"),
    "MAP-29": (
        "V10-MAP-29-S0-castle",
        "V10-MAP-29-S1-castle",
        "V10-MAP-29-S2-castle",
    ),
    "MAP-30": (
        "V10-MAP-30-S0-castle",
        "V10-MAP-30-S1-castle",
        "V10-MAP-30-S2-castle",
    ),
}


def _final_observation(run_id: str) -> dict[str, Any]:
    rows = _trace_rows(run_id)
    for item in reversed(rows):
        observation = item.get("observation_after")
        if observation:
            return dict(observation)
    return {}


def analyse_28(run_id: str) -> dict[str, Any]:
    observation = _final_observation(run_id)
    recorded = set(observation.get("recorded_evidence_ids") or [])
    required = set(observation.get("required_key_evidence") or [])
    return {
        "run_id": run_id,
        "tick": observation.get("tick"),
        "location": observation.get("location"),
        "recorded": len(recorded),
        "required": len(required),
        "missing": sorted(required - recorded),
        "terminal_reason": observation.get("terminal_reason"),
    }


def analyse_29(run_id: str) -> dict[str, Any]:
    observation = _final_observation(run_id)
    comparisons = observation.get("comparison_results") or {}
    return {
        "run_id": run_id,
        "tick": observation.get("tick"),
        "location": observation.get("location"),
        "questions_used": observation.get("questions_used"),
        "questions_remaining": observation.get("questions_remaining"),
        "heard": len(observation.get("heard_answers") or []),
        "comparisons": comparisons,
        "insufficient": sum(1 for value in comparisons.values() if value == "INSUFFICIENT"),
        "terminal_reason": observation.get("terminal_reason"),
    }


def analyse_30(run_id: str) -> dict[str, Any]:
    observation = _final_observation(run_id)
    casebook = observation.get("casebook") or {}
    requirements = observation.get("entry_requirements") or {}
    complete = sum(
        1 for entry, needed in requirements.items() if set(needed) <= set(casebook.get(entry, []))
    )
    return {
        "run_id": run_id,
        "tick": observation.get("tick"),
        "location": observation.get("location"),
        "courtroom": observation.get("courtroom_node"),
        "entries_complete": complete,
        "entries_required": len(requirements),
        "chain_reconciled": observation.get("chain_reconciled"),
        "terminal_reason": observation.get("terminal_reason"),
    }


def audit() -> dict[str, Any]:
    return {
        "MAP-28": [analyse_28(run_id) for run_id in RUNS["MAP-28"]],
        "MAP-29": [analyse_29(run_id) for run_id in RUNS["MAP-29"]],
        "MAP-30": [analyse_30(run_id) for run_id in RUNS["MAP-30"]],
    }


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# 古堡三图的“距离完成还差什么”",
        "",
        "- 由 `python -m agent_arena.v10.castle_gap` 生成；只读 MiMo trace 的最终 Observation。",
        "- 目的：判断预算耗尽时是“信息不够”还是“路线/顺序没走完”。",
        "",
        "## 1. MAP-28（证据 → H 提交）",
        "",
        "| run | tick | 终局位置 | 已记录/必备 | 缺失 |",
        "|---|---:|---|---:|---|",
    ]
    for row in payload["MAP-28"]:
        missing = "、".join(row["missing"]) or "—"
        lines.append(
            f"| `{row['run_id']}` | {row['tick']} | {row['location']} | "
            f"{row['recorded']}/{row['required']} | {missing} |"
        )
    lines += [
        "",
        "读法：seed 1 已凑齐全部必备证据，却停在 A（未回 H 提交）；seed 2 停在 H 但缺 1 条",
        "证人窗口证据；seed 0 同样凑齐并完成提交。失败是路线/顺序，不是信息不可得。",
        "",
        "## 2. MAP-29（提问/比对 → Y 提交）",
        "",
        "| run | tick | 终局位置 | 已问/剩余 | 听到答案 | 比对结果 |",
        "|---|---:|---|---:|---:|---|",
    ]
    for row in payload["MAP-29"]:
        comparisons = "、".join(f"{key}:{value}" for key, value in row["comparisons"].items())
        lines.append(
            f"| `{row['run_id']}` | {row['tick']} | {row['location']} | "
            f"{row['questions_used']}/{row['questions_remaining']} | {row['heard']} | "
            f"{comparisons or '—'} |"
        )
    lines += [
        "",
        "读法：三局都还有 4–6 次提问额度，却只做了 1 次比对且结果为 `INSUFFICIENT`；",
        "决策预算被移动/调查消耗，不是问题额度不足。",
        "",
        "## 3. MAP-30（案卷 → 法庭 J）",
        "",
        "| run | tick | 终局位置 | 法庭节点 | 案卷完成 | 链条核对 |",
        "|---|---:|---|---|---:|---|",
    ]
    for row in payload["MAP-30"]:
        lines.append(
            f"| `{row['run_id']}` | {row['tick']} | {row['location']} | {row['courtroom']} | "
            f"{row['entries_complete']}/{row['entries_required']} | {row['chain_reconciled']} |"
        )
    lines += [
        "",
        "读法：seed 0 三条事件案卷已齐但链条未核对、人还在 A；seed 1/2 分别缺 1–2 条案卷；",
        "三局都没有走到法庭节点 J。差距是“最后一步的路线与顺序”，不是案卷规模。",
        "",
        "## 4. 结论",
        "",
        "- 古堡三图的决策预算（30/38/46）都大于 Oracle 动作数（18/22/31）；",
        "  实际失败点集中在**回提交点/核对链条**之前的移动与重复调查。",
        "- 这不是预算不足，也不是信息缺失；属于策略/路线层，V11 若要改，应改提示或评估路线设计，",
        "  而不是继续加预算。",
        "- n=3、单 replicate，只作描述。",
        "",
        "## 5. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.castle_gap",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    payload = audit()
    (V10_DOCS / "castle-gap-analysis.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 0


__all__ = ["analyse_28", "analyse_29", "analyse_30", "audit", "render", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
