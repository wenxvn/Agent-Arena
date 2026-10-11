"""Streamlit 研究可视化 MVP 的纯展示逻辑（不依赖 streamlit，可单测）。

只读：输入为已加载的 trace/benchmark 字典，不触碰 Runner/Provider/`.env`。
"""
from __future__ import annotations

from typing import Any


def autonomy_level(provenance: dict[str, Any]) -> str:
    """按 provenance 开关返回自主性等级标签（UI 必须原样显示）。"""
    agent = provenance.get("agent", "")
    if agent == "planner_assisted":
        return "planner_assisted｜辅助上界，非自主能力"
    if provenance.get("candidate_selection_enabled"):
        return "candidate_select｜受限候选选择"
    if provenance.get("planning_enabled"):
        return "planning｜显式规划（Planner+Executor 双成本）"
    if provenance.get("public_action_guard") or provenance.get("public_action_hints"):
        return "guarded｜公开规则保护"
    if provenance.get("public_phase_context_enabled"):
        return "world-declared phase guidance｜世界预定义任务辅助"
    if provenance.get("recent_history_enabled") or provenance.get("stuck_recovery_enabled"):
        return "observation-derived｜纯观察派生历史/恢复"
    return "纯 observation 自主"


def summarize_trace(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """把单局 trace 压成逐步骤回放行（只取白名单字段）。"""
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(trace.get("steps", []), start=1):
        action = step.get("action") or {}
        result = step.get("result") or {}
        observation = step.get("observation") or {}
        progress = step.get("progress") or {}
        rows.append(
            {
                "step": index,
                "event": step.get("event"),
                "room": observation.get("current_room"),
                "action": action.get("tool"),
                "target": action.get("target") or action.get("destination") or action.get("item"),
                "reason": result.get("reason"),
                "progress": progress.get("progress"),
                "decision_reason": (step.get("decision_reason") or "")[:280],
                "input_tokens": step.get("input_tokens"),
                "output_tokens": step.get("output_tokens"),
            }
        )
    return rows


def compare_conditions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """按行计算单个条件的聚合（成功率、步数、token），缺值记 N/A。"""
    outcomes = [row.get("outcome") for row in rows]
    successes = sum(1 for outcome in outcomes if outcome == "success")
    steps = [row.get("steps") for row in rows if isinstance(row.get("steps"), (int, float))]
    input_tokens = [row.get("input_tokens") for row in rows if isinstance(row.get("input_tokens"), (int, float))]
    output_tokens = [row.get("output_tokens") for row in rows if isinstance(row.get("output_tokens"), (int, float))]
    return {
        "attempts": len(rows),
        "successes": successes,
        "success_rate": (successes / len(rows)) if rows else "N/A",
        "mean_steps": (sum(steps) / len(steps)) if steps else "N/A",
        "max_steps": max(steps) if steps else "N/A",
        "mean_input_tokens": (sum(input_tokens) / len(input_tokens)) if input_tokens else "N/A",
        "mean_output_tokens": (sum(output_tokens) / len(output_tokens)) if output_tokens else "N/A",
    }
