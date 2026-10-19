"""MAP-05 V10 原生 seed 化（DCR-V10-27）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map05 as b05
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map05 import VARIANTS, Map05V10Environment

SEEDS = seed_space("MAP-05")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-05")
    assert len({scenario_hash("MAP-05", seed) for seed in SEEDS}) == len(SEEDS)


def test_windows_are_seeded_and_published() -> None:
    for seed in SEEDS:
        environment = Map05V10Environment(seed=seed)
        observation = environment.observe()
        expected = {
            name: list(window) for name, window in VARIANTS[seed].windows.items()
        }
        assert observation["windows"] == expected
        # goal 文案必须来自本 seed 的窗口，不能写死 V8 的 15/18、22/25、29/35
        for name, (start, end) in VARIANTS[seed].windows.items():
            assert f"{name}[{start},{end}]" in observation["goal"]


def test_scenario_descriptor_is_public_and_sealed_truth_is_not() -> None:
    for seed in SEEDS:
        environment = Map05V10Environment(seed=seed)
        descriptor = environment.scenario_descriptor()
        assert set(descriptor) == {"label", "windows", "edge_cost"}
        assert "reference_completion_tick" in environment.sealed_truth()
        assert "reference_completion_tick" not in environment.observe()


def test_oracle_succeeds_with_mechanism_triggered_for_every_seed() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-05", b05.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map05.v10.mission_success"]["value"] == 1
        assert run.metrics["map05.v10.missed_windows"]["value"] == 0
        assert run.metrics["map05.v10.power_switches"]["value"] >= 3
        assert run.metrics["map05.v10.window_slack_ticks"]["value"] >= 0


def test_public_heuristic_reads_only_the_observation() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-05", b05.HEURISTIC(), environment_seed=seed, decision_budget=60
        )
        assert run.success, seed
        assert run.invalid_actions == 0


def test_ablations_break_the_mechanism() -> None:
    for name, factory in b05.ABLATIONS.items():
        for seed in SEEDS:
            run = run_policy(
                "MAP-05", factory(), environment_seed=seed, decision_budget=60
            )
            assert not run.success, (name, seed)


def test_shared_power_is_required() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-05", b05.ABLATIONS["no_power_switch"](), environment_seed=seed,
            decision_budget=60,
        )
        assert run.metrics["map05.v10.power_switches"]["value"] == 0
        assert run.metrics["map05.v10.missed_windows"]["value"] >= 1


def test_metrics_five_states_on_truncation_and_failure() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-05").METRIC_SPECS}
    truncated = run_policy(
        "MAP-05", b05.WindowPolicy(name="idle", use_power=False), environment_seed=0,
        decision_budget=5,
    )
    assert truncated.status == "decision_budget_reached"
    for metric_id in ("map05.v10.mission_success", "map05.v10.effective_signals"):
        assert truncated.metrics[metric_id]["state"] == "CENSORED", metric_id
    failed = run_policy(
        "MAP-05", b05.ABLATIONS["no_calibration"](), environment_seed=0, decision_budget=60
    )
    assert failed.metrics["map05.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map05.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
