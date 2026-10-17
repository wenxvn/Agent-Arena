"""独立复算：MAP-01…MAP-06、MAP-10…MAP-12。

每个函数只读 Trace 的公开 Observation 流或 judge_state，按公式重新计算，
不调用地图的 ``metrics()``、V7 extractor 或 V8 投影。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v9.metric_checks.base import Check, EvidenceRun


def _count_result(run: EvidenceRun, *codes: str) -> int:
    return sum(1 for result in run.results() if result in codes)


def _decision_ticks(run: EvidenceRun) -> list[int]:
    ticks: list[int] = []
    for item in run.decisions:
        observation = item.get("observation_after") or {}
        tick = observation.get("tick", observation.get("current_tick"))
        if isinstance(tick, int):
            ticks.append(tick)
    return ticks


# --------------------------------------------------------------------- MAP-01
def map01_dependency_rate(run: EvidenceRun) -> float | None:
    dependencies = run.judge_state.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        return None
    return sum(1 for value in dependencies.values() if value) / len(dependencies)


def map01_oxygen_guardrail(run: EvidenceRun) -> int:
    return int(
        _terminal(run) in {"OXYGEN_RESERVE_EXHAUSTED", "OXYGEN_SUPPLY_INTERRUPTION_LIMIT"}
    )


def _terminal(run: EvidenceRun) -> str | None:
    value = run.judge_state.get("terminal_reason")
    if isinstance(value, str):
        return value
    for item in reversed(run.decisions):
        observation = item.get("observation_after") or {}
        if isinstance(observation.get("terminal_reason"), str):
            return str(observation["terminal_reason"])
    return None


# --------------------------------------------------------------------- MAP-02
def map02_dual_objective(run: EvidenceRun) -> float:
    final = run.final
    nav = bool(final.get("nav_core_secured") or run.judge_state.get("nav_core_secured"))
    crew = bool(
        final.get("crew_in_escape_pod") or run.judge_state.get("crew_in_escape_pod")
    )
    return (int(nav) + int(crew)) / 2


def map02_stale_actions(run: EvidenceRun) -> int:
    stale = 0
    seen_leak = False
    for item in run.decisions:
        observation = item.get("observation_after") or {}
        if observation.get("leak_active"):
            seen_leak = True
        if not seen_leak or observation.get("crew_in_escape_pod"):
            continue
        action = item.get("action") or {}
        edge = str(action.get("edge_id") or "")
        target = str(action.get("target") or action.get("target_id") or "")
        destination = {
            "C_R1": "R1",
            "R1_R2": "R2",
            "R2_R1": "R1",
            "R1_C": "C",
        }.get(edge)
        if destination == "R1" or (
            action.get("tool") == "interact" and target in {"nav_core", "core_cradle"}
        ):
            stale += 1
    return stale


# --------------------------------------------------------------------- MAP-03
def map03_phase_coverage(run: EvidenceRun) -> float | None:
    milestones = run.judge_state.get("milestones")
    if not isinstance(milestones, dict) or not milestones:
        return None
    return sum(1 for value in milestones.values() if value) / len(milestones)


def map03_sample_lost(run: EvidenceRun) -> int:
    return int(_terminal(run) == "SAMPLE_COLD_WINDOW_EXPIRED")


# --------------------------------------------------------------------- MAP-04
def map04_window_hit_rate(run: EvidenceRun) -> float | None:
    attempts = 0
    successes = 0
    for item in run.decisions:
        action = item.get("action") or {}
        if action.get("edge_id") != "S_G":
            continue
        attempts += 1
        if not str(item.get("result", "")).startswith("TIDE_WINDOW_CLOSED"):
            successes += 1
    return successes / attempts if attempts else None


def map04_high_tide_entries(run: EvidenceRun) -> int:
    return _count_result(run, "TIDE_WINDOW_CLOSED")


# --------------------------------------------------------------------- MAP-05
def map05_effective_signals(run: EvidenceRun) -> float | None:
    transmitted = run.judge_state.get("transmitted")
    if not isinstance(transmitted, dict) or not transmitted:
        return None
    return sum(1 for value in transmitted.values() if value) / 3


def map05_missed_windows(run: EvidenceRun) -> int:
    windows = run.initial.get("windows") or {}
    final_transmitted = run.final.get("transmitted") or run.judge_state.get("transmitted") or {}
    final_tick = run.final.get("tick")
    if not isinstance(final_tick, int):
        final_tick = 0
    missed = 0
    for name, span in windows.items():
        end = int(span[1])
        if not final_transmitted.get(name) and final_tick > end:
            missed += 1
    return missed


# --------------------------------------------------------------------- MAP-06
def map06_task_success(run: EvidenceRun) -> float:
    return float(bool(run.final.get("lamp_restored") or run.judge_state.get("lamp_restored")))


def map06_observation_cost(run: EvidenceRun) -> int:
    return 2 * sum(
        1
        for item in run.decisions
        if (item.get("action") or {}).get("target_id") == "forecast"
    )


# -------------------------------------------------------------------- MAP-10
def map10_fuel_consumed(run: EvidenceRun) -> int:
    final = run.final
    depot = int(final.get("fuel_depot", run.judge_state.get("fuel_depot", 0)))
    carried = int(final.get("carried_fuel", run.judge_state.get("carried_fuel", 0)))
    return 12 - (depot + carried)


def map10_base_frozen(run: EvidenceRun) -> int:
    return int(_terminal(run) == "BASE_FROZEN")


# -------------------------------------------------------------------- MAP-11
def map11_rescue_count(run: EvidenceRun) -> int:
    return int(bool(run.final.get("teammate_rescued") or run.judge_state.get("teammate_rescued")))


def map11_first_clue_delay(run: EvidenceRun) -> int | None:
    for item in run.decisions:
        if (item.get("action") or {}).get("tool") == "scout":
            tick = (item.get("observation_after") or {}).get("tick")
            return int(tick) if isinstance(tick, int) else None
    return None


# -------------------------------------------------------------------- MAP-12
def map12_fuel_consumed(run: EvidenceRun) -> int:
    final = run.final
    fuel = final.get("fuel_E")
    if not isinstance(fuel, int):
        fuel = run.judge_state.get("fuel_E")
    return 40 - int(fuel or 0)


def map12_research_points(run: EvidenceRun) -> int | None:
    final = run.final
    points = final.get("research_points", run.judge_state.get("research_points"))
    return int(points) if isinstance(points, int) else None


def map12_survival_days(run: EvidenceRun) -> float | None:
    snapshots = run.judge_state.get("snapshots")
    if not isinstance(snapshots, list):
        return None
    return sum(1 for row in snapshots if row.get("heat_ok") and row.get("food_ok")) / 30


CHECKS: dict[str, list[Check]] = {
    "MAP-01": [
        Check(
            "map01.dependency_satisfaction_rate",
            map01_dependency_rate,
            "judge_state 依赖布尔计数/6",
        ),
        Check(
            "map01.oxygen_guardrail_violations",
            map01_oxygen_guardrail,
            "终止码映射",
            kind="guardrail",
        ),
    ],
    "MAP-02": [
        Check("map02.dual_objective_completion", map02_dual_objective, "两目标布尔和/2"),
        Check(
            "map02.stale_plan_actions_after_leak",
            map02_stale_actions,
            "泄漏后仍指向 R1/nav_core 的动作计数",
            kind="diagnostic",
        ),
    ],
    "MAP-03": [
        Check("map03.phase_completion_coverage", map03_phase_coverage, "里程碑布尔计数/总数"),
        Check("map03.lost_sample", map03_sample_lost, "终止码映射", kind="diagnostic"),
    ],
    "MAP-04": [
        Check("map04.window_hit_rate", map04_window_hit_rate, "S_G 尝试成功数/尝试数"),
        Check(
            "map04.high_tide_entries",
            map04_high_tide_entries,
            "TIDE_WINDOW_CLOSED 计数",
            kind="guardrail",
        ),
    ],
    "MAP-05": [
        Check("map05.effective_signals", map05_effective_signals, "transmitted 布尔计数/3"),
        Check("map05.missed_windows", map05_missed_windows, "未发射窗口计数", kind="diagnostic"),
    ],
    "MAP-06": [
        Check("map06.task_success_rate", map06_task_success, "lamp_restored 布尔值"),
        Check(
            "map06.observation_cost",
            map06_observation_cost,
            "inspect forecast 次数×2",
            kind="diagnostic",
        ),
    ],
    "MAP-10": [
        Check("map10.fuel_consumed", map10_fuel_consumed, "12−(油库+随身)"),
        Check("map10.base_frozen", map10_base_frozen, "终止码映射", kind="guardrail"),
    ],
    "MAP-11": [
        Check("map11.rescue_count", map11_rescue_count, "teammate_rescued 布尔值"),
        Check(
            "map11.first_clue_delay",
            map11_first_clue_delay,
            "首个 scout 的公开 tick",
            kind="diagnostic",
        ),
    ],
    "MAP-12": [
        Check("map12.fuel_consumed", map12_fuel_consumed, "40−终局 fuel_E"),
        Check("map12.survival_days", map12_survival_days, "snapshots 中双约束满足天数/30"),
    ],
}


def extra_metrics(run: EvidenceRun) -> dict[str, Any]:
    """V9 建议新增/修正的诊断值（不属于 V8 已登记指标）。"""

    values: dict[str, Any] = {}
    if run.map_id == "MAP-12":
        values["map12.research_points"] = map12_research_points(run)
    if run.map_id == "MAP-04":
        values["map04.tide_route_used"] = int(
            any((item.get("action") or {}).get("edge_id") == "S_G" for item in run.decisions)
        )
    if run.map_id == "MAP-06":
        values["map06.forecast_used"] = int(
            any((item.get("action") or {}).get("target_id") == "forecast" for item in run.decisions)
        )
    return values


__all__ = ["CHECKS", "extra_metrics"]
