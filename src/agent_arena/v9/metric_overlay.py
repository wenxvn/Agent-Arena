"""V9 指标叠加层：修正/新增有明确证据的指标定义。

原则：
- 不修改 V8 的指标实现与 90 局结果；
- 旧值原样保留；V9 额外给出 ``overlay`` 字段与新的 schema hash；
- 每条叠加指标都能从 Trace 的公开 Observation 流或 judge_state 独立复算。
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

OVERLAY_SPECS: dict[str, list[dict[str, Any]]] = {
    "MAP-02": [
        {
            "metric_id": "map02.adaptive_response_within_2",
            "kind": "primary",
            "direction": "higher_is_better",
            "formula": (
                "1 if a plan-changing action (nav_core/center_gate) occurs "
                "within 2 decisions after the leak is public, else 0"
            ),
            "denominator": "episode with a public leak",
            "missing_rule": "no public leak -> not_applicable",
            "replaces": "map02.event_response_latency",
            "rationale": "旧指标把任何非 wait/inspect 动作都算作响应，所有策略恒为 1。",
        }
    ],
    "MAP-04": [
        {
            "metric_id": "map04.tide_route_used",
            "kind": "diagnostic",
            "direction": "higher_is_better",
            "formula": "1 if any S_G crossing attempt occurred, else 0",
            "denominator": "episode",
            "missing_rule": "never",
            "replaces": None,
            "rationale": "区分绕行成功与潮汐门成功；旧主指标在绕行成功时为 N/A。",
        },
        {
            "metric_id": "map04.stranded_ticks_status",
            "kind": "diagnostic",
            "direction": "lower_is_better",
            "formula": "unavailable: runtime has no stranded_ticks counter",
            "denominator": "episode",
            "missing_rule": "always unavailable",
            "replaces": "map04.stranded_ticks",
            "rationale": "旧实现直接返回 high_tide_entries，与护栏指标完全相同。",
        },
    ],
    "MAP-05": [
        {
            "metric_id": "map05.window_utilization_corrected",
            "kind": "primary",
            "direction": "higher_is_better",
            "formula": "effective_signals / 3 (same denominator as effective_signals)",
            "denominator": "3",
            "missing_rule": "never",
            "replaces": "map05.window_utilization",
            "rationale": (
                "旧 window_utilization 与 effective_signals 分子分母完全相同，是重复指标。"
            ),
        },
        {
            "metric_id": "map05.power_overcommit_status",
            "kind": "guardrail",
            "direction": "lower_is_better",
            "formula": "unavailable: runtime hardcodes 0",
            "denominator": "episode",
            "missing_rule": "always unavailable",
            "replaces": "map05.power_overcommit",
            "rationale": "旧护栏恒为 0，无法触发。",
        },
    ],
    "MAP-12": [
        {
            "metric_id": "map12.research_points_completion",
            "kind": "primary",
            "direction": "higher_is_better",
            "formula": "research_points / 12",
            "denominator": "12",
            "missing_rule": "never",
            "replaces": None,
            "rationale": "胜负判据是研究积分，旧五条指标均未投影该值。",
        }
    ],
    "MAP-21": [
        {
            "metric_id": "map21.scientific_units_evacuated",
            "kind": "primary",
            "direction": "higher_is_better",
            "formula": "success ? 1 + sample_collected + measurement_used : 0",
            "denominator": "3",
            "missing_rule": "never",
            "replaces": "map21.evacuation_coverage",
            "rationale": "旧 coverage 分母是已投入单位，直达撤离仍得 1.0，无法区分科研质量。",
        }
    ],
    "MAP-13": [
        {
            "metric_id": "map13.illegal_door_attempts_corrected",
            "kind": "guardrail",
            "direction": "lower_is_better",
            "formula": "count(result == ILLEGAL_DOOR); STATE_RESET is not an illegal door",
            "denominator": "episode",
            "missing_rule": "never",
            "replaces": "map13.illegal_door_attempts",
            "rationale": "旧实现把 STATE_RESET 也算进 ILLEGAL_DOOR；R0 报 3，字面只有 1。",
        }
    ],
    "MAP-14": [
        {
            "metric_id": "map14.query_gap_signed",
            "kind": "primary",
            "direction": "lower_is_better",
            "formula": "queries_used - minimum_queries (negative allowed)",
            "denominator": "episode",
            "missing_rule": "never",
            "replaces": "map14.minimum_query_gap",
            "rationale": "旧指标 max(0, gap) 把“一个都不问”变成最优。",
        }
    ],
    "MAP-19": [
        {
            "metric_id": "map19.exceedance_area_per_tick",
            "kind": "primary",
            "direction": "lower_is_better",
            "formula": "temperature_exceedance_area / valid_ticks",
            "denominator": "valid ticks",
            "missing_rule": "valid_ticks == 0 -> not_applicable",
            "replaces": "map19.temperature_exceedance_area",
            "rationale": "旧指标声明按 tick 归一，实现返回未归一化和，跨局不可比。",
        }
    ],
    "MAP-25": [
        {
            "metric_id": "map25.required_check_coverage_corrected",
            "kind": "primary",
            "direction": "higher_is_better",
            "formula": "(count(required_done - {diagnosed}) + int(diagnosed)) / 7",
            "denominator": "7",
            "missing_rule": "never",
            "replaces": "map25.required_check_coverage",
            "rationale": "旧口径把一次被拒的 diagnose 记为完成（R2 7/7 但 diagnosed=False）。",
        }
    ],
}

REQUIRED_CHECKS_25 = 7


def overlay_schema_hash(map_id: str) -> str:
    payload = json.dumps(OVERLAY_SPECS.get(map_id, []), ensure_ascii=False, sort_keys=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def _missing(status: str) -> dict[str, Any]:
    return {"status": status, "value": None, "denominator": None, "note": None}


def _value(value: Any, denominator: int | None = None) -> dict[str, Any]:
    return {"status": "valid", "value": value, "denominator": denominator, "note": None}


def _leak_index(rows: list[dict[str, Any]]) -> int | None:
    for index, row in enumerate(rows):
        after = row.get("observation_after") or {}
        if after.get("leak_active"):
            return index
    return None


def _map02(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    index = _leak_index(rows)
    if index is None:
        return {"map02.adaptive_response_within_2": _missing("not_applicable")}
    window = rows[index + 1 : index + 3]
    adaptive = 0
    for row in window:
        action = row.get("action") or {}
        target = str(action.get("target") or action.get("target_id") or "")
        if action.get("tool") == "interact" and target in {"nav_core", "center_gate"}:
            adaptive = 1
            break
        if action.get("tool") == "move" and action.get("edge_id") in {"C_R1", "C_L1"}:
            adaptive = 1
            break
    return {"map02.adaptive_response_within_2": _value(adaptive, 1)}


def _map04(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    used = int(
        any((row.get("action") or {}).get("edge_id") == "S_G" for row in rows)
    )
    return {
        "map04.tide_route_used": _value(used, 1),
        "map04.stranded_ticks_status": _missing("unavailable"),
    }


def _map05(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    transmitted = judge_state.get("transmitted") or {}
    sent = sum(1 for value in transmitted.values() if value)
    return {
        "map05.window_utilization_corrected": _value(round(sent / 3, 6), 3),
        "map05.power_overcommit_status": _missing("unavailable"),
    }


def _map12(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    points = judge_state.get("research_points")
    if not isinstance(points, int):
        return {"map12.research_points_completion": _missing("unavailable")}
    return {"map12.research_points_completion": _value(round(points / 12, 6), 12)}


def _map21(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    success = judge_state.get("status") == "scenario_success"
    sample = 1 if judge_state.get("carried_sample") else 0
    measured = 1 if judge_state.get("measurement_outcome") else 0
    evacuated = (1 + sample + measured) if success else 0
    return {"map21.scientific_units_evacuated": _value(evacuated, 3)}


def _map13(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    illegal = sum(1 for row in rows if row.get("result") == "ILLEGAL_DOOR")
    return {"map13.illegal_door_attempts_corrected": _value(illegal, 1)}


def _map14(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    asked = judge_state.get("asked_claim_ids")
    minimum = judge_state.get("minimum_queries")
    if not isinstance(minimum, int):
        return {"map14.query_gap_signed": _missing("unavailable")}
    used = len(asked) if isinstance(asked, list) else 0
    return {"map14.query_gap_signed": _value(used - minimum, 1)}


def _map19(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    from agent_arena.worlds.scenario_v8.maps.map19 import EXCEEDANCE_BASELINE

    states = judge_state.get("settled_states")
    if not isinstance(states, list) or not states:
        return {"map19.exceedance_area_per_tick": _missing("not_applicable")}
    area = sum(
        max(0, int(temperature) - EXCEEDANCE_BASELINE)
        for state in states
        for temperature in state.values()
    )
    return {
        "map19.exceedance_area_per_tick": _value(round(area / len(states), 6), len(states))
    }


def _map25(judge_state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    done = [str(item) for item in judge_state.get("required_done") or []]
    diagnosed = bool(judge_state.get("diagnosed"))
    completed = len([item for item in done if item != "diagnosed"]) + int(diagnosed)
    return {
        "map25.required_check_coverage_corrected": _value(
            round(completed / REQUIRED_CHECKS_25, 6), REQUIRED_CHECKS_25
        )
    }


_BUILDERS = {
    "MAP-02": _map02,
    "MAP-04": _map04,
    "MAP-05": _map05,
    "MAP-12": _map12,
    "MAP-13": _map13,
    "MAP-14": _map14,
    "MAP-19": _map19,
    "MAP-21": _map21,
    "MAP-25": _map25,
}


def overlay_metrics(
    map_id: str,
    judge_state: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    builder = _BUILDERS.get(map_id)
    return builder(judge_state, rows) if builder else {}


__all__ = [
    "OVERLAY_SPECS",
    "overlay_metrics",
    "overlay_schema_hash",
]
