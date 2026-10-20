"""历史筛选、版本对照与本地同模型成绩榜（纯函数，可单测）。"""

from __future__ import annotations

from typing import Any

from agent_arena.web.schemas import RunSummary


def filter_runs(
    rows: list[RunSummary],
    *,
    map_id: str = "",
    state: str = "",
    mode: str = "",
    provider_id: str = "",
    environment_seed: int | None = None,
    query: str = "",
    since: str = "",
) -> list[RunSummary]:
    text = query.strip().lower()
    selected: list[RunSummary] = []
    for row in rows:
        if map_id and row.map_id != map_id:
            continue
        if state and row.state != state:
            continue
        if mode and row.mode != mode:
            continue
        if provider_id and row.provider_id != provider_id:
            continue
        if environment_seed is not None and row.environment_seed != environment_seed:
            continue
        if since and row.created_at[:10] < since[:10]:
            continue
        if text:
            haystack = " ".join(
                (row.run_id, row.map_id, row.model, row.display_title, row.outcome or "")
            ).lower()
            if text not in haystack:
                continue
        selected.append(row)
    return selected


def compatibility(left: RunSummary, right: RunSummary) -> dict[str, Any]:
    """直接比较的硬条件：地图、规则版本、指标版本、评测模式。"""

    mismatches: list[str] = []
    if left.map_id != right.map_id:
        mismatches.append("地图不同")
    if left.rule_hash != right.rule_hash:
        mismatches.append("规则 hash 不同")
    if left.metric_hash != right.metric_hash:
        mismatches.append("指标 hash 不同")
    if left.metric_schema_hash != right.metric_schema_hash:
        mismatches.append("指标 schema 不同")
    if left.mode != right.mode:
        mismatches.append("评测模式不同")
    warnings: list[str] = []
    if left.model != right.model:
        warnings.append("模型不同，只能并排展示，不能当作同一模型对照")
    if left.environment_seed != right.environment_seed:
        warnings.append("环境 seed 不同，结果不具可比性")
    return {
        "compatible": not mismatches,
        "mismatches": mismatches,
        "warnings": warnings,
    }


def multi_comparison_rows(rows: list[RunSummary]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": row.run_id,
            "地图": row.map_id,
            "标题": row.display_title,
            "模型": row.model,
            "模式": row.mode,
            "seed": row.environment_seed,
            "状态": row.state,
            "结局": row.outcome or "—",
            "成功": row.success,
            "动作 / 预算": f"{row.decisions} / {row.decision_budget}",
            "费用 CNY": row.cost_settled_cny,
            "rule_hash": (row.rule_hash or "")[:12],
            "metric_hash": (row.metric_hash or "")[:12],
        }
        for row in rows
    ]


def compatibility_all(rows: list[RunSummary]) -> dict[str, Any]:
    if len(rows) < 2:
        return {"compatible": False, "mismatches": ["少于两局"], "warnings": []}
    mismatches: set[str] = set()
    warnings: set[str] = set()
    baseline = rows[0]
    for row in rows[1:]:
        verdict = compatibility(baseline, row)
        mismatches.update(str(item) for item in verdict["mismatches"])
        warnings.update(str(item) for item in verdict["warnings"])
    return {
        "compatible": not mismatches,
        "mismatches": sorted(mismatches),
        "warnings": sorted(warnings),
    }


def comparison_rows(left: RunSummary, right: RunSummary) -> list[dict[str, Any]]:
    def cell(value: Any) -> str:
        return "—" if value is None else str(value)

    return [
        {"字段": "run_id", "A": left.run_id, "B": right.run_id},
        {"字段": "地图", "A": left.map_id, "B": right.map_id},
        {"字段": "模型", "A": left.model, "B": right.model},
        {"字段": "模式", "A": left.mode, "B": right.mode},
        {"字段": "seed", "A": str(left.environment_seed), "B": str(right.environment_seed)},
        {"字段": "状态", "A": left.state, "B": right.state},
        {"字段": "结局", "A": cell(left.outcome), "B": cell(right.outcome)},
        {"字段": "成功", "A": str(left.success), "B": str(right.success)},
        {"字段": "动作数", "A": str(left.decisions), "B": str(right.decisions)},
        {
            "字段": "费用 CNY",
            "A": cell(left.cost_settled_cny),
            "B": cell(right.cost_settled_cny),
        },
        {"字段": "rule_hash", "A": cell(left.rule_hash), "B": cell(right.rule_hash)},
        {"字段": "metric_hash", "A": cell(left.metric_hash), "B": cell(right.metric_hash)},
    ]


def leaderboard(rows: list[RunSummary]) -> list[dict[str, Any]]:
    """同地图、同模型、同模式、同规则/指标版本的本地成绩榜。"""

    groups: dict[tuple[str, str, str, str, str], list[RunSummary]] = {}
    for row in rows:
        if row.state not in {"SUCCEEDED", "FAILED", "BUDGET_REACHED"}:
            continue
        if not row.rule_hash or not row.metric_hash:
            continue
        key = (
            row.map_id,
            row.model,
            row.mode,
            row.rule_hash,
            row.metric_hash,
        )
        groups.setdefault(key, []).append(row)

    output: list[dict[str, Any]] = []
    for (map_id, model, mode, rule_hash, metric_hash), items in sorted(groups.items()):
        items.sort(
            key=lambda item: (
                0 if item.success else 1,
                item.decisions,
                item.cost_settled_cny if item.cost_settled_cny is not None else 9_999,
            )
        )
        for rank, item in enumerate(items, start=1):
            output.append(
                {
                    "map_id": map_id,
                    "title": item.display_title,
                    "model": model,
                    "mode": mode,
                    "rank": rank,
                    "run_id": item.run_id,
                    "success": item.success,
                    "decisions": item.decisions,
                    "budget": item.decision_budget,
                    "seed": item.environment_seed,
                    "cost_cny": item.cost_settled_cny,
                    "rule_hash": rule_hash[:12],
                    "metric_hash": metric_hash[:12],
                }
            )
    return output


def unique_values(rows: list[RunSummary], field: str) -> list[str]:
    values = {str(getattr(row, field, "")) for row in rows}
    return sorted(value for value in values if value)


__all__ = [
    "comparison_rows",
    "compatibility",
    "compatibility_all",
    "filter_runs",
    "leaderboard",
    "multi_comparison_rows",
    "unique_values",
]
