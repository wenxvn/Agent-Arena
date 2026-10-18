"""MAP-18 V10（DCR-V10-02）：时钟分离、反抢跑与多 seed 恢复测试。"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map18 as baseline
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import scenario_hash, seed_effective
from agent_arena.v10.runtime.map18 import (
    ACTION_SLACK,
    VARIANTS,
    Map18V10Environment,
    affected_tasks,
)
from agent_arena.worlds.scenario_v8.models import V8Action

SEEDS = tuple(sorted(VARIANTS))
V4_RULE_HASH = "aa446dfaa631197cd1f46b66e5c481eef6a68da694f76776afd4567cd75c5d8e"


def _row(environment: Map18V10Environment, operations: dict[str, object]) -> str:
    payload = {"tool": "set_timetable", "tick": environment.current_tick, "operations": operations}
    return environment.step(V8Action.model_validate(payload, strict=True)).result


def test_v4_map18_rule_file_is_untouched() -> None:
    path = Path("src/agent_arena/worlds/scenario_v4/map18.py")
    assert sha256(path.read_bytes()).hexdigest() == V4_RULE_HASH


def test_action_budget_is_not_clamped_to_horizon() -> None:
    environment = Map18V10Environment(seed=0)
    assert environment.step_limit == environment.horizon + ACTION_SLACK
    assert _row(environment, {"T_R1": {"op": "release", "to": "R2"}}).startswith(
        "DISPATCH_WINDOW_VIOLATION"
    )
    assert environment.current_tick == 0 and environment.tick_count == 1
    for _ in range(environment.horizon):
        _row(environment, {})
    # 一次被拒仍能走完全部 horizon（V4 的 min(step_limit, horizon) 会在 tick 11 截尾）。
    assert environment.current_tick == environment.horizon
    assert environment.terminal_reason == "DEADLINE_SERVICE_BELOW_THRESHOLD"


def test_front_loading_bypass_is_rejected() -> None:
    environment = Map18V10Environment(seed=0)
    result = _row(
        environment,
        {"T_X": {"op": "release", "to": "B2"}, "T_B": {"op": "release", "to": "B2"}},
    )
    assert result == "DISPATCH_WINDOW_VIOLATION:T_X"
    assert environment.window_violations == 1
    assert environment.positions["T_X"] == "R2"


@pytest.mark.parametrize("seed", SEEDS)
def test_every_seed_has_an_unavoidable_fault(seed: int) -> None:
    assert affected_tasks(VARIANTS[seed])
    run = run_actions("MAP-18", baseline.oracle_actions(seed), environment_seed=seed)
    assert run.success
    assert run.mechanism_triggered
    assert run.decisions <= 46
    assert run.metrics["map18.v10.closed_entry_attempts"]["value"] == 0


def test_initial_observation_differs_only_by_public_alert() -> None:
    def strip(seed: int) -> dict[str, object]:
        observation = dict(Map18V10Environment(seed=seed).observe())
        observation.pop("alert_message_if_any")
        return observation

    first = strip(0)
    for seed in SEEDS[1:]:
        assert strip(seed) == first
    assert seed_effective("MAP-18", SEEDS)
    assert len({scenario_hash("MAP-18", seed) for seed in SEEDS}) == len(SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_fault_hidden_until_it_starts(seed: int) -> None:
    variant = VARIANTS[seed]
    environment = Map18V10Environment(seed=seed)
    while environment.current_tick < variant.start:
        assert environment.observe()["closed_segments"] == []
        _row(environment, {})
    assert environment.observe()["closed_segments"] == [environment.fault_edge_key]


def test_heuristic_and_ablations_are_separated() -> None:
    heuristic = [run_policy("MAP-18", baseline.HEURISTIC(), environment_seed=s) for s in SEEDS]
    assert all(run.success for run in heuristic)
    for name in ("no_replan", "greedy_dispatch", "ignore_windows"):
        runs = [run_policy("MAP-18", baseline.ABLATIONS[name](), environment_seed=s) for s in SEEDS]
        assert sum(run.success for run in runs) < len(SEEDS), name
    no_replan = run_policy("MAP-18", baseline.ABLATIONS["no_replan"](), environment_seed=0)
    assert no_replan.terminal_reason == "HEAD_ON_COLLISION"
    assert no_replan.metrics["map18.v10.closed_entry_attempts"]["value"] > 0


def test_long_closure_requires_cancel_and_relocation() -> None:
    no_cancel = baseline._search(3, allow_cancel=False)
    assert no_cancel[0][0] == 0
    run = run_actions("MAP-18", baseline.oracle_actions(3), environment_seed=3)
    assert run.success and run.metrics["map18.v10.service_rate"]["value"] == pytest.approx(15 / 18)


def test_recovery_metric_states() -> None:
    environment = Map18V10Environment(seed=0)
    for _ in range(environment.horizon):
        _row(environment, {})
    metrics = environment.v10_metrics()
    assert metrics["map18.v10.recovery_delay_ticks"].state.value == "CENSORED"
    assert metrics["map18.v10.service_rate"].value == 0.0
