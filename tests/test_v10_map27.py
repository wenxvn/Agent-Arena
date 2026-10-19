"""MAP-27 V10 原生 seed 化（DCR-V10-30）：实例、Oracle、消融与五态测试。"""

from __future__ import annotations

from agent_arena.v10.baselines import map27 as b27
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import (
    scenario_hash,
    seed_effective,
    seed_space,
    v10_class,
)
from agent_arena.v10.runtime.map27 import VARIANTS, Map27V10Environment

SEEDS = seed_space("MAP-27")


def test_four_registered_seeds_produce_distinct_instances() -> None:
    assert SEEDS == (0, 1, 2, 3)
    assert seed_effective("MAP-27")
    assert len({scenario_hash("MAP-27", seed) for seed in SEEDS}) == len(SEEDS)


def test_vehicle_parameters_are_seeded_and_public() -> None:
    for seed in SEEDS:
        environment = Map27V10Environment(seed=seed)
        observation = environment.observe()
        variant = VARIANTS[seed]
        assert observation["battery_capacity"] == variant.battery_capacity
        assert observation["cargo_capacity"] == variant.cargo_capacity
        assert observation["oxygen"] == variant.oxygen
        assert environment.scenario_descriptor()["charge_gain"] == variant.charge_gain


def test_sealed_truth_is_not_agent_visible() -> None:
    for seed in SEEDS:
        environment = Map27V10Environment(seed=seed)
        assert "reference_critical_path" in environment.sealed_truth()
        assert "reference_critical_path" not in environment.observe()


def test_oracle_succeeds_on_every_seed_with_mechanism() -> None:
    for seed in SEEDS:
        run = run_actions("MAP-27", b27.oracle_actions(seed), environment_seed=seed)
        assert run.success, seed
        assert run.mechanism_triggered is True, seed
        assert run.metrics["map27.v10.mission_success"]["value"] == 1
        assert run.metrics["map27.v10.joint_task_completion_rate"]["value"] == 1


def test_tight_battery_makes_relay_first_route_infeasible() -> None:
    """电量收紧的实例只允许 stabilize-first——这是实例难度而不是规则变化。"""

    from agent_arena.worlds.scenario_v8.maps.map27 import _RELAY_FIRST

    tight = [seed for seed in SEEDS if VARIANTS[seed].battery_capacity <= 12]
    assert tight
    for seed in tight:
        run = run_actions("MAP-27", list(_RELAY_FIRST), environment_seed=seed)
        assert not run.success, seed


def test_public_heuristic_solves_every_seed() -> None:
    for seed in SEEDS:
        run = run_policy(
            "MAP-27", b27.HEURISTIC(), environment_seed=seed, decision_budget=60
        )
        assert run.success, seed
        assert run.invalid_actions == 0


def test_ablations_lose_at_least_one_objective() -> None:
    for name, factory in b27.ABLATIONS.items():
        successes = 0
        for seed in SEEDS:
            run = run_policy(
                "MAP-27", factory(), environment_seed=seed, decision_budget=60
            )
            successes += int(run.success)
        assert successes < len(SEEDS), name


def test_overload_records_cargo_conflict_on_small_cargo() -> None:
    small = [seed for seed in SEEDS if VARIANTS[seed].cargo_capacity == 2]
    assert small
    for seed in small:
        run = run_policy(
            "MAP-27", b27.ABLATIONS["overload"](), environment_seed=seed, decision_budget=60
        )
        conflicts = run.metrics["map27.v10.resource_conflicts"]["value"] or 0
        cargo_errors = run.metrics["map27.v10.cargo_errors"]["value"] or 0
        assert conflicts + cargo_errors >= 1, seed


def test_metrics_five_states() -> None:
    spec_ids = {spec.metric_id for spec in v10_class("MAP-27").METRIC_SPECS}
    truncated = run_policy(
        "MAP-27", b27.LunarPolicy(name="idle"), environment_seed=0, decision_budget=2
    )
    assert truncated.status == "decision_budget_reached"
    assert truncated.metrics["map27.v10.mission_success"]["state"] == "CENSORED"
    failed = run_policy(
        "MAP-27", b27.ABLATIONS["skip_sample"](), environment_seed=0, decision_budget=60
    )
    assert failed.metrics["map27.v10.mission_success"]["state"] == "VALID"
    assert failed.metrics["map27.v10.mission_success"]["value"] == 0
    assert set(failed.metrics) == spec_ids
