"""MAP-02 V10 原生 seed 化（DCR-V10-29）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map02 as b02
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map02 import VARIANTS, Map02V10Environment

SEEDS = seed_space("MAP-02")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-02")
    assert len({scenario_hash("MAP-02", seed) for seed in SEEDS}) == len(SEEDS)


def test_event_parameters_are_seeded_and_public() -> None:
    for seed in SEEDS:
        environment = Map02V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["deadline_tick"] == variant.global_deadline
        assert environment.scenario_descriptor()["leak_trigger_index"] == (
            variant.leak_trigger_index
        )
        assert environment.judge_state()["spread_ticks"] == variant.spread_ticks


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map02V10Environment(seed=seed)
        assert "event_order_seed" in environment.sealed_truth()
        assert "event_order_seed" not in environment.observe()


def test_oracle_plan_succeeds_on_every_seed() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-02", b02.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map02.v10.mission_success"]["value"] == 1
        assert run.metrics["map02.v10.dual_objective_completion"]["value"] == 1
        assert run.metrics["map02.v10.event_response_latency"]["value"] >= 0


def test_public_heuristic_reads_only_the_observation() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-02", b02.HEURISTIC(), environment_seed=seed, decision_budget=40
        )
        assert run.success, seed
        assert run.invalid_actions == 0


def test_ablations_break_the_mechanism() -> None:
    for name, factory in b02.ABLATIONS.items():
        successes = 0
        for seed in SEEDS:
            run = run_policy(
                "MAP-02", factory(), environment_seed=seed, decision_budget=40
            )
            successes += int(run.success)
        assert successes < len(SEEDS), name


def test_single_objective_is_not_success() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-02", b02.ABLATIONS["nav_only"](), environment_seed=seed,
            decision_budget=40,
        )
        assert not run.success
        assert run.metrics["map02.v10.dual_objective_completion"]["value"] <= 0.5


def test_metrics_five_states_on_truncation_and_failure() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-02").METRIC_SPECS}
    truncated = run_policy(
        "MAP-02", b02.ReplanPolicy(name="idle", delay_ticks=0), environment_seed=0,
        decision_budget=2,
    )
    assert truncated.status == "decision_budget_reached"
    assert truncated.metrics["map02.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-02", b02.ABLATIONS["late_react"](), environment_seed=0, decision_budget=40
    )
    assert failed.metrics["map02.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map02.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
