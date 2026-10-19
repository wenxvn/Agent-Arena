"""MAP-25 V10 原生 seed 化（DCR-V10-33）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map25 as b25
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map25 import VARIANTS, Map25V10Environment

SEEDS = seed_space("MAP-25")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-25")
    assert len({scenario_hash("MAP-25", seed) for seed in SEEDS}) == len(SEEDS)


def test_start_and_oxygen_are_seeded_and_public() -> None:
    for seed in SEEDS:
        environment = Map25V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["location"] == variant.start
        assert observation["oxygen_remaining"] == variant.oxygen
        descriptor = environment.scenario_descriptor()
        assert descriptor["start"] == variant.start
        assert descriptor["oxygen"] == variant.oxygen


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map25V10Environment(seed=seed)
        assert "eva" in environment.sealed_truth()
        assert "eva" not in environment.observe()


def test_oracle_succeeds_on_every_seed() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-25", b25.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map25.v10.mission_success"]["value"] == 1
        assert run.metrics["map25.v10.required_check_coverage"]["value"] == 1


def test_public_heuristic_solves_every_seed() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-25", b25.HEURISTIC(), environment_seed=seed, decision_budget=40
        )
        assert run.success, seed
        assert run.invalid_actions == 0


def test_ablations_break_the_eva_chain() -> None:
    for name, factory in b25.ABLATIONS.items():
        for seed in SEEDS:
            run = run_policy(
                "MAP-25", factory(), environment_seed=seed, decision_budget=40
            )
            assert not run.success, (name, seed)


def test_no_tether_records_unsafe_eva() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-25", b25.ABLATIONS["no_tether"](), environment_seed=seed,
            decision_budget=40,
        )
        assert run.metrics["map25.v10.unsafe_eva_attempts"]["value"] >= 1


def test_metrics_five_states() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-25").METRIC_SPECS}
    truncated = run_policy(
        "MAP-25", b25.EvaPolicy(name="idle", tether=False), environment_seed=0,
        decision_budget=2,
    )
    assert truncated.status == "decision_budget_reached"
    assert truncated.metrics["map25.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-25", b25.ABLATIONS["no_tether"](), environment_seed=0, decision_budget=40
    )
    assert failed.metrics["map25.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map25.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
