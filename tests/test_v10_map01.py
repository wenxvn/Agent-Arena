"""MAP-01 V10 原生 seed 化（DCR-V10-31）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map01 as b01
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map01 import VARIANTS, Map01V10Environment

SEEDS = seed_space("MAP-01")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-01")
    assert len({scenario_hash("MAP-01", seed) for seed in SEEDS}) == len(SEEDS)


def test_life_support_parameters_are_seeded_and_public() -> None:
    for seed in SEEDS:
        environment = Map01V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["oxygen_reserve"] == variant.oxygen_reserve
        assert environment.judge_state()["oxygen_off_limit"] == variant.off_limit
        # 配电图必须反映本实例的参数
        environment.node = "H"
        diagram = environment.step(
            __import__(
                "agent_arena.worlds.scenario_v8.models", fromlist=["V8Action"]
            ).V8Action(tool="inspect", target="power_diagram")
        ).result
        assert f"capacity={variant.capacity}" in diagram
        assert f"arm={variant.arm_load}" in diagram


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map01V10Environment(seed=seed)
        assert "life_support" in environment.sealed_truth()
        assert "life_support" not in environment.observe()


def test_oracle_succeeds_on_every_seed_with_mechanism() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-01", b01.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map01.v10.mission_success"]["value"] == 1
        assert run.metrics["map01.v10.dependency_satisfaction_rate"]["value"] == 1


def test_public_heuristic_solves_every_seed() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-01", b01.HEURISTIC(), environment_seed=seed, decision_budget=40
        )
        assert run.success, seed
        assert run.invalid_actions == 0


def test_ablations_break_the_dependency_chain() -> None:
    for name, factory in b01.ABLATIONS.items():
        for seed in SEEDS:
            run = run_policy(
                "MAP-01", factory(), environment_seed=seed, decision_budget=40
            )
            assert not run.success, (name, seed)


def test_not_restoring_support_trips_the_outage_guardrail() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-01", b01.ABLATIONS["no_support_restore"](), environment_seed=seed,
            decision_budget=40,
        )
        assert run.metrics["map01.v10.oxygen_guardrail_violations"]["value"] == 1
        assert run.metrics["map01.v10.longest_oxygen_outage_ticks"]["value"] > (
            VARIANTS[seed].off_limit
        )


def test_metrics_five_states() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-01").METRIC_SPECS}
    truncated = run_policy(
        "MAP-01", b01.LifeSupportPolicy(name="idle"), environment_seed=0,
        decision_budget=2,
    )
    assert truncated.status == "decision_budget_reached"
    assert truncated.metrics["map01.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-01", b01.ABLATIONS["no_support_restore"](), environment_seed=0,
        decision_budget=40,
    )
    assert failed.metrics["map01.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map01.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
