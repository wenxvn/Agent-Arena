"""MAP-16 V10 原生 seed 化（DCR-V10-36）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map16 as b16
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map16 import VARIANTS, Map16V10Environment

SEEDS = seed_space("MAP-16")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-16")
    assert len({scenario_hash("MAP-16", seed) for seed in SEEDS}) == len(SEEDS)


def test_instance_parameters_are_public_and_match_descriptor() -> None:
    for seed in SEEDS:
        environment = Map16V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["train_positions"] == variant.start_positions
        assert observation["train_goals"] == variant.goals
        assert observation["siding_nodes"] == ["D"]
        descriptor = environment.scenario_descriptor()
        assert descriptor["label"] == variant.label
        assert descriptor["start_positions"] == variant.start_positions
        assert descriptor["goals"] == variant.goals


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map16V10Environment(seed=seed)
        truth = environment.sealed_truth()
        assert "shortest_makespan" in truth
        assert "shortest_makespan" not in environment.observe()


def test_oracle_succeeds_on_every_seed_with_mechanism() -> None:
    for seed in SEEDS:
        actions = b16.oracle_actions(seed)
        run = run_actions("MAP-16", actions, environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map16.v10.mission_success"]["value"] == 1
        assert run.metrics["map16.v10.node_capacity_conflicts"]["value"] == 0
        assert run.metrics["map16.v10.deadlock_count"]["value"] == 0


def test_public_heuristic_matches_oracle() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-16", b16.HEURISTIC(), environment_seed=seed, decision_budget=30
        )
        assert run.success, seed


def test_ablations_break_the_mechanism() -> None:
    for name, factory in b16.ABLATIONS.items():
        for seed in SEEDS:
            run = run_policy(
                "MAP-16", factory(), environment_seed=seed, decision_budget=30
            )
            assert not run.success, (name, seed)


def test_metrics_five_states() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-16").METRIC_SPECS}
    truncated = run_policy(
        "MAP-16", b16.HEURISTIC(), environment_seed=0, decision_budget=1
    )
    assert truncated.metrics["map16.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-16", b16.DoubleBookingPolicy(), environment_seed=0, decision_budget=30
    )
    assert failed.metrics["map16.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map16.v10.mission_success"]["value"] == 0
    assert failed.metrics["map16.v10.makespan_gap"]["state"] == "NOT_APPLICABLE"
    assert set(failed.metrics) == spec_ids
