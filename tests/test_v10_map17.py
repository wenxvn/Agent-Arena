"""MAP-17 V10 原生 seed 化（DCR-V10-34）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map17 as b17
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map17 import VARIANTS, Map17V10Environment

SEEDS = seed_space("MAP-17")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-17")
    assert len({scenario_hash("MAP-17", seed) for seed in SEEDS}) == len(SEEDS)


def test_threshold_and_horizon_are_seeded_and_public() -> None:
    for seed in SEEDS:
        environment = Map17V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["ticks_remaining"] == variant.horizon
        assert f"至少 {variant.threshold}/" in observation["goal"]
        descriptor = environment.scenario_descriptor()
        assert descriptor["threshold"] == variant.threshold
        assert descriptor["horizon"] == variant.horizon


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map17V10Environment(seed=seed)
        assert "schedule" in environment.sealed_truth()
        assert "schedule" not in environment.observe()


def test_oracle_succeeds_on_every_seed_with_mechanism() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-17", b17.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map17.v10.mission_success"]["value"] == 1
        assert run.metrics["map17.v10.service_rate"]["value"] == 1.0


def test_perfect_threshold_requires_full_delivery() -> None:
    """阈值 10 的实例不接受任何损失——同一份时刻表送满 10/10 才算成功。"""

    perfect = [seed for seed in SEEDS if VARIANTS[seed].threshold == 10]
    assert perfect
    for seed in perfect:
        run = run_policy(
            "MAP-17", b17.ABLATIONS["half_board"](), environment_seed=seed,
            decision_budget=40,
        )
        assert not run.success
        assert run.metrics["map17.v10.threshold_margin"]["value"] < 0


def test_ablations_break_the_schedule() -> None:
    for name, factory in b17.ABLATIONS.items():
        for seed in SEEDS:
            run = run_policy(
                "MAP-17", factory(), environment_seed=seed, decision_budget=40
            )
            assert not run.success, (name, seed)


def test_metrics_five_states() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-17").METRIC_SPECS}
    truncated = run_policy(
        "MAP-17", b17.ScriptedTimetable(name="idle", mutate="no_board"), environment_seed=0,
        decision_budget=2,
    )
    assert truncated.status == "decision_budget_reached"
    assert truncated.metrics["map17.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-17", b17.ABLATIONS["no_board"](), environment_seed=0, decision_budget=40
    )
    assert failed.metrics["map17.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map17.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
