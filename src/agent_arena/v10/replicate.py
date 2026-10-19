"""重复运行一致性：同一 (map, seed) 的首局 vs 第二局（replicate 1）。

只读本地 ``runs/v10/mimo/results.json``；阶段 15（`-x2-v2`）为第二局。
输出 ``docs/v10/replicate-analysis.md``。

n=2，只作描述：成功是否翻转、主指标绝对差、非法动作变化；不做显著性检验。
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from agent_arena.v10.evidence_state import effective_mimo_rows, is_interrupted, mimo_rows
from agent_arena.v10.paths import V10_DOCS


def _primary(row: dict[str, Any]) -> float | None:
    if str(row.get("primary_metric_state") or "") != "VALID":
        return None
    value = row.get("primary_metric_value")
    return float(value) if value is not None else None


def pairs() -> list[dict[str, Any]]:
    first: dict[tuple[str, int], dict[str, Any]] = {}
    for map_id, rows in effective_mimo_rows().items():
        for row in rows:
            first[(map_id, int(row.get("environment_seed") or 0))] = row
    second: dict[tuple[str, int], dict[str, Any]] = {}
    for row in mimo_rows():
        if int(row.get("replicate") or 0) == 0:
            continue
        if is_interrupted(row):
            continue
        if not str(row.get("run_id", "")).endswith("-v2"):
            continue
        second[(str(row["map_id"]), int(row.get("environment_seed") or 0))] = row
    result: list[dict[str, Any]] = []
    for key in sorted(set(first) & set(second)):
        one, two = first[key], second[key]
        result.append(
            {
                "map_id": key[0],
                "seed": key[1],
                "world": one.get("world"),
                "difficulty": one.get("difficulty"),
                "run_a": one.get("run_id"),
                "run_b": two.get("run_id"),
                "success_a": bool(one.get("success")),
                "success_b": bool(two.get("success")),
                "primary_a": _primary(one),
                "primary_b": _primary(two),
                "invalid_a": int(one.get("invalid_actions") or 0),
                "invalid_b": int(two.get("invalid_actions") or 0),
                "decisions_a": int(one.get("decision_count") or 0),
                "decisions_b": int(two.get("decision_count") or 0),
                "cost_a": float(one.get("cost_settled") or 0),
                "cost_b": float(two.get("cost_settled") or 0),
            }
        )
    return result


def audit() -> dict[str, Any]:
    rows = pairs()
    both = [row for row in rows if row["success_a"] and row["success_b"]]
    neither = [row for row in rows if not row["success_a"] and not row["success_b"]]
    flips_up = [row for row in rows if row["success_b"] and not row["success_a"]]
    flips_down = [row for row in rows if row["success_a"] and not row["success_b"]]
    deltas = [
        abs(row["primary_a"] - row["primary_b"])
        for row in rows
        if row["primary_a"] is not None and row["primary_b"] is not None
    ]
    by_world: dict[str, Counter[str]] = {}
    for row in rows:
        counter = by_world.setdefault(str(row["world"]), Counter())
        counter["pairs"] += 1
        counter["agree"] += int(row["success_a"] == row["success_b"])
        counter["flips"] += int(row["success_a"] != row["success_b"])
    all_second = [
        row for row in mimo_rows() if int(row.get("replicate") or 0) == 1
    ]
    interrupted = [row for row in all_second if is_interrupted(row)]
    return {
        "pairs": rows,
        "coverage": {
            "planned": 90,
            "second_runs": len(all_second),
            "interrupted_second": len(interrupted),
            "maps": sorted({row["map_id"] for row in rows}),
            "stopped": "GLOBAL_REQUEST_LIMIT" if interrupted else "",
        },
        "totals": {
            "pairs": len(rows),
            "both_success": len(both),
            "neither_success": len(neither),
            "flip_up": len(flips_up),
            "flip_down": len(flips_down),
            "success_agreement": round((len(both) + len(neither)) / len(rows), 4) if rows else None,
            "mean_abs_primary_delta": round(sum(deltas) / len(deltas), 6) if deltas else None,
            "primary_pairs": len(deltas),
            "cost_second": round(sum(row["cost_b"] for row in rows), 8),
        },
        "by_world": {world: dict(counter) for world, counter in sorted(by_world.items())},
    }


def render(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "# V10 重复运行一致性（同一 map/seed 的第二局）",
        "",
        "- 由 `python -m agent_arena.v10.replicate` 生成；只读本地 MiMo 结果。",
        "- 首局 = 有效证据（replicate 0），第二局 = 阶段 15（`-x2-v2`，replicate 1）。",
        "- temperature=0、环境确定；差异只来自 provider 非确定性。n=2，只作描述。",
        "",
        (
            f"- 计划 {payload['coverage']['planned']} 对；实际第二局 "
            f"{payload['coverage']['second_runs']} 局"
            f"（中断 {payload['coverage']['interrupted_second']}），"
            f"有效配对 **{totals['pairs']}** 个，覆盖 "
            f"{payload['coverage']['maps'][0]}–{payload['coverage']['maps'][-1]}。"
        ),
        (
            "- 阶段 15 因全局请求上限（`GLOBAL_REQUEST_LIMIT`）停止；未运行的部分不回写、不补跑，"
            "本表只描述已完成的配对。"
            if payload["coverage"]["stopped"]
            else "- 阶段 15 完整运行。"
        ),
        f"- 两局都成功 {totals['both_success']}、都不成功 {totals['neither_success']}；",
        f"  成功翻转 {totals['flip_up']} 升 / {totals['flip_down']} 降；"
        f"成功率一致 **{totals['success_agreement']}**。",
        f"- 两局都 `VALID` 的主指标配对 {totals['primary_pairs']} 个，"
        f"平均绝对差 `{totals['mean_abs_primary_delta']}`。",
        f"- 第二局结算 CNY `{totals['cost_second']:.8f}`。",
        "",
        "## 1. 逐世界一致性",
        "",
        "| 世界 | 配对 | 成功一致 | 翻转 |",
        "|---|---:|---:|---:|",
    ]
    for world, counter in payload["by_world"].items():
        lines.append(
            f"| {world} | {counter.get('pairs', 0)} | {counter.get('agree', 0)} | "
            f"{counter.get('flips', 0)} |"
        )
    lines += [
        "",
        "## 2. 发生翻转的配对",
        "",
        "| 图 | seed | 首局 | 第二局 | 首局主指标 | 第二局主指标 |",
        "|---|---:|---|---|---:|---:|",
    ]
    flips = [row for row in payload["pairs"] if row["success_a"] != row["success_b"]]
    for row in flips:
        outcome_a = "成功" if row["success_a"] else "失败"
        outcome_b = "成功" if row["success_b"] else "失败"
        lines.append(
            f"| {row['map_id']} | {row['seed']} | {outcome_a} | {outcome_b} | "
            f"{row['primary_a']} | {row['primary_b']} |"
        )
    if not flips:
        lines.append("| — | — | — | — | — | — |")
    lines += [
        "",
        "## 3. 逐配对明细",
        "",
        "| 图 | seed | 首局成功 | 第二局成功 | Δ主指标 | Δ非法动作 | Δ决策 |",
        "|---|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["pairs"]:
        delta = (
            round(abs(row["primary_a"] - row["primary_b"]), 6)
            if row["primary_a"] is not None and row["primary_b"] is not None
            else None
        )
        lines.append(
            f"| {row['map_id']} | {row['seed']} | {row['success_a']} | {row['success_b']} | "
            f"{delta} | {row['invalid_b'] - row['invalid_a']} | "
            f"{row['decisions_b'] - row['decisions_a']} |"
        )
    lines += [
        "",
        "## 4. 结论与边界",
        "",
        "- 一致性只说明「同实例、同温度下重复运行的可重复程度」，不替代多 seed 或跨模型证据。",
        "- 翻转与主指标差都只作描述；n=2 不足以估计方差或做显著性检验。",
        "",
        "## 5. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.replicate",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    payload = audit()
    (V10_DOCS / "replicate-analysis.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload["totals"], ensure_ascii=False))
    return 0


__all__ = ["audit", "pairs", "render", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
