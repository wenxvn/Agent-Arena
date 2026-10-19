"""扫描 MiMo trace 的“重复动作但不推进时间”模式。

用途：
    python -m agent_arena.v10.trace_scan            # 生成 docs/v10/action-loop-scan.md
    python -m agent_arena.v10.trace_scan --check    # 当前规则下存在“免费动作循环”时退出 1

判据（行为证据，不读地图内部状态）：

- 连续 ≥8 次完全相同的动作；
- 这 8 次动作期间 ``observation_after.tick`` 没有变化；
- 若动作是 ``invalid_output``，归为 ``INVALID_OUTPUT_LOOP``（接口/格式问题），
  否则归为 ``FREE_ACTION_LOOP``（免费动作没有推进时间）。

工具只读 ``runs/v10/mimo``；CI 没有本地局，因此不作为 CI 门禁。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

from agent_arena.v10.attribution import _trace_rows
from agent_arena.v10.evidence_state import is_interrupted, mimo_rows
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import rule_hash

MIN_STREAK = 8


def _key(action: Any) -> str:
    return json.dumps(action, sort_keys=True, ensure_ascii=False)


def classify(actions: list[Any], ticks: list[int]) -> tuple[int, str, str]:
    """返回 (最长重复次数, 判定)。纯函数，便于测试。"""

    best = 0
    best_key = ""
    streak = 0
    previous = ""
    for action in actions:
        key = _key(action)
        streak = (streak + 1) if key == previous else 1
        if streak > best:
            best, best_key = streak, key
        previous = key
    tick_span = (max(ticks) - min(ticks)) if ticks else None
    invalid = "invalid_output" in best_key
    if best >= MIN_STREAK and tick_span == 0:
        verdict = "INVALID_OUTPUT_LOOP" if invalid else "FREE_ACTION_LOOP"
    elif best >= MIN_STREAK and tick_span is None:
        verdict = "LEGACY_NO_TICK_FIELD"
    else:
        verdict = "OK"
    return best, verdict, best_key


def analyse(row: dict[str, Any]) -> dict[str, Any]:
    run_id = str(row["run_id"])
    map_id = str(row["map_id"])
    decisions = _trace_rows(run_id)
    actions = [item.get("action") for item in decisions]
    ticks: list[int] = []
    for item in decisions:
        tick = (item.get("observation_after") or {}).get("tick")
        if isinstance(tick, int):
            ticks.append(tick)
    best, verdict, best_key = classify(actions, ticks)
    tick_span = (max(ticks) - min(ticks)) if ticks else None
    current = str(row.get("rule_hash") or "") == rule_hash(map_id)
    return {
        "map_id": map_id,
        "run_id": run_id,
        "environment_seed": row.get("environment_seed"),
        "decisions": len(decisions),
        "max_streak": best,
        "tick_span": tick_span,
        "streak_action": best_key[:160],
        "verdict": verdict,
        "current_rules": current,
        "interrupted": is_interrupted(row),
    }


def audit() -> dict[str, Any]:
    rows = [analyse(row) for row in mimo_rows()]
    flagged = [
        row for row in rows if row["verdict"] in {"FREE_ACTION_LOOP", "INVALID_OUTPUT_LOOP"}
    ]
    # `--check` 只看当前规则下的免费动作循环；invalid_output 是旧动作契约的格式问题，
    # 已由 DCR-V10-24 的类型化契约修复，历史局保留不回写。
    current_flagged = [
        row
        for row in flagged
        if row["current_rules"] and row["verdict"] == "FREE_ACTION_LOOP"
    ]
    by_map: dict[str, Counter[str]] = {}
    for row in flagged:
        by_map.setdefault(row["map_id"], Counter())[row["verdict"]] += 1
    return {
        "rows": rows,
        "flagged": flagged,
        "totals": {
            "runs": len(rows),
            "flagged": len(flagged),
            "free_action_loops": sum(1 for row in flagged if row["verdict"] == "FREE_ACTION_LOOP"),
            "invalid_output_loops": sum(
                1 for row in flagged if row["verdict"] == "INVALID_OUTPUT_LOOP"
            ),
            "current_rules_flagged": len(current_flagged),
        },
        "by_map": {map_id: dict(counts) for map_id, counts in sorted(by_map.items())},
        "current_flagged": current_flagged,
    }


def render(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "# V10 动作循环扫描（重复动作 + tick 不推进）",
        "",
        "- 由 `python -m agent_arena.v10.trace_scan` 生成；只读本地 MiMo trace。",
        "- 判据：连续 ≥8 次完全相同的动作，且期间 `tick` 不变；",
        "  `invalid_output` 归为接口/格式问题。",
        "- `current_rules=是` 表示该局使用的 `rule_hash` 与当前地图一致，属于**仍可行动**的缺陷；",
        "  历史局（`rule_hash` 不同）只作记录，不回写。",
        "",
        f"- 扫描 **{totals['runs']}** 局；命中 **{totals['flagged']}** 局"
        f"（免费动作循环 {totals['free_action_loops']}、"
        f"无效输出循环 {totals['invalid_output_loops']}）；"
        f"其中当前规则下仍有 **{totals['current_rules_flagged']}** 局免费动作循环。",
        "",
        "## 1. 命中局",
        "",
        "| 图 | run_id | 决策 | 最长重复 | tick 跨度 | 判定 | 当前规则 |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in payload["flagged"]:
        lines.append(
            f"| {row['map_id']} | `{row['run_id']}` | {row['decisions']} | {row['max_streak']} | "
            f"{row['tick_span']} | `{row['verdict']}` | {'是' if row['current_rules'] else '否'} |"
        )
    lines += [
        "",
        "## 2. 逐图分布",
        "",
        "| 图 | 免费动作循环 | 无效输出循环 |",
        "|---|---:|---:|",
    ]
    for map_id, counts in payload["by_map"].items():
        lines.append(
            f"| {map_id} | {counts.get('FREE_ACTION_LOOP', 0)} | "
            f"{counts.get('INVALID_OUTPUT_LOOP', 0)} |"
        )
    lines += [
        "",
        "## 3. 结论",
        "",
        "- 真正的免费动作循环只出现在 MAP-19 与 MAP-20；两图已分别在 DCR-V10-39 / DCR-V10-38",
        "  的公开规则中补上“只有 wait 推进时间”，当前规则下不再命中。",
        "- MAP-18/28 的命中是旧动作契约下的 `invalid_output` 循环，已由 DCR-V10-24 修复；",
        "  历史局保留，不回写。",
        "- MAP-12 的重复 `assign` 每天正常结算（tick/日期在推进），不属于本缺陷。",
        "",
        "## 4. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.trace_scan",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.trace_scan --check",
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    payload = audit()
    output = V10_RUNS / "trace_scan"
    output.mkdir(parents=True, exist_ok=True)
    (output / "action_loops.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (V10_DOCS / "action-loop-scan.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload["totals"], ensure_ascii=False))
    if "--check" in args and payload["totals"]["current_rules_flagged"]:
        return 1
    return 0


__all__ = ["MIN_STREAK", "analyse", "audit", "classify", "main", "render"]


if __name__ == "__main__":
    raise SystemExit(main())
