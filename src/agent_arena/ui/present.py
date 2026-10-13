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
                "scenario_event": step.get("scenario_event"),
                "scenario_status": step.get("scenario_status"),
                "failure_reason": step.get("failure_reason"),
                "score_components": step.get("score_components"),
                "decision_reason": (step.get("decision_reason") or "")[:280],
                "input_tokens": step.get("input_tokens"),
                "output_tokens": step.get("output_tokens"),
            }
        )
    return rows


def compare_conditions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """按行计算单个条件的聚合（成功率、步数、token），缺值记 N/A。"""
    outcomes = [row.get("outcome") for row in rows]
    successes = sum(1 for outcome in outcomes if outcome in {"success", "scenario_success"})
    steps = _numeric_values(rows, "steps")
    input_tokens = _numeric_values(rows, "input_tokens")
    output_tokens = _numeric_values(rows, "output_tokens")
    return {
        "attempts": len(rows),
        "successes": successes,
        "success_rate": (successes / len(rows)) if rows else "N/A",
        "mean_steps": (sum(steps) / len(steps)) if steps else "N/A",
        "max_steps": max(steps) if steps else "N/A",
        "mean_input_tokens": (sum(input_tokens) / len(input_tokens)) if input_tokens else "N/A",
        "mean_output_tokens": (sum(output_tokens) / len(output_tokens)) if output_tokens else "N/A",
    }


def trace_overview(trace: dict[str, Any]) -> dict[str, Any]:
    """单局头部总览（只取白名单字段；缺值记 N/A）。"""
    provenance = trace.get("provenance", {}) or {}
    steps = trace.get("steps", []) or []
    input_tokens = sum(s.get("input_tokens") or 0 for s in steps if isinstance(s, dict))
    output_tokens = sum(s.get("output_tokens") or 0 for s in steps if isinstance(s, dict))
    prompt_hash = str(provenance.get("base_prompt_hash") or "")
    return {
        "episode_id": trace.get("episode_id", "N/A"),
        "agent": trace.get("agent", "N/A"),
        "world_version": trace.get("world_version", "N/A"),
        "model": provenance.get("model_name", "N/A"),
        "seed": trace.get("seed", "N/A"),
        "outcome": trace.get("outcome", "N/A"),
        "scenario_id": trace.get("scenario_id", "N/A"),
        "scenario_status": trace.get("scenario_status", "N/A"),
        "failure_reason": trace.get("failure_reason", "N/A"),
        "scenario_family": provenance.get("scenario_family", "N/A"),
        "scenario_difficulty": provenance.get("scenario_difficulty", "N/A"),
        "mechanic_version": provenance.get("mechanic_version", "N/A"),
        "source_design_id": provenance.get("source_design_id", "N/A"),
        "score_components": trace.get("score_components", "N/A"),
        "steps": trace.get("executed_action_count", len(steps)),
        "invalid_outputs": trace.get("invalid_output_count", "N/A"),
        "rejected_actions": trace.get("rejected_action_count", "N/A"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": trace.get("latency_ms", "N/A"),
        "prompt_hash": prompt_hash[:8] if prompt_hash else "N/A",
        "autonomy": autonomy_level(provenance),
    }


def success_at_k(steps_list: list[int], budgets: list[int]) -> dict[int, float]:
    """离线 Success@K：步数 ≤K 视为该预算下成功（回放估计，非在线预算）。"""
    total = len(steps_list)
    return {
        budget: (sum(1 for steps in steps_list if steps <= budget) / total) if total else 0.0
        for budget in budgets
    }


def error_hotspots(trace: dict[str, Any]) -> dict[str, int]:
    """T4 三类错误计数（只用公开字段；旧 schema 缺字段时按 0 计）。"""
    steps = trace.get("steps", []) or []
    wrong_tool = 0
    code_reads = 0
    post_code_wander = 0
    seen_code = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        action = step.get("action") or {}
        result = step.get("result") or {}
        reason = result.get("reason")
        if action.get("tool") == "read_terminal" and reason == "wrong_target":
            wrong_tool += 1
        if reason == "code_read":
            code_reads += 1
            seen_code = True
        elif seen_code and (action.get("tool") in ("move", "look")):
            post_code_wander += 1
    return {
        "wrong_tool_at_terminal": wrong_tool,
        "code_reads": code_reads,
        "repeated_code_read": max(0, code_reads - 1),
        "post_code_moves": post_code_wander,
    }


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[int | float]:
    values: list[int | float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(value)
    return values


def aggregate_traces(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """多局 trace 按 world_version 聚合成矩阵行（成功 seed、均值、中位数）。"""
    groups: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        groups.setdefault(str(trace.get("world_version", "unknown")), []).append(trace)
    rows: list[dict[str, Any]] = []
    for version in sorted(groups):
        group = groups[version]
        successful_traces = [
            trace for trace in group if trace.get("outcome") in {"success", "scenario_success"}
        ]
        successes = sorted(
            seed for trace in successful_traces if isinstance(seed := trace.get("seed"), int)
        )
        steps = sorted(_numeric_values(successful_traces, "executed_action_count"))
        rows.append(
            {
                "world_version": version,
                "success": f"{len(successes)}/{len(group)}",
                "success_seeds": successes,
                "mean_steps": (sum(steps) / len(steps)) if steps else "N/A",
                "median_steps": (steps[len(steps) // 2]) if steps else "N/A",
                "attempts": len(group),
            }
        )
    return rows


def page_rows(rows: list[dict[str, Any]], page: int, size: int) -> list[dict[str, Any]]:
    """回放分页（page 从 1 起；越界返回空表，不抛错）。"""
    if page < 1 or size < 1:
        return []
    return rows[(page - 1) * size : page * size]
