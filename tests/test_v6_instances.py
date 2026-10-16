"""V6 instance, solver, and pairing tests (offline, deterministic)."""

from __future__ import annotations

import pytest

from agent_arena.v6.catalog import build_environment, get_scene, instance_manifest
from agent_arena.v6.scenes import all_scenes
from agent_arena.v6.solvers import solve
from agent_arena.worlds.scenario_v4 import ScenarioV4Action


def _seed_list(scene) -> list[int]:
    if scene.map_id == "MAP-08":
        return sorted(scene.leak_by_seed)
    return [0]


def test_every_instance_oracle_replays_to_success() -> None:
    for instance_id, scene in all_scenes().items():
        for seed in _seed_list(scene):
            result = solve(instance_id, seed=seed)
            assert result.actions, instance_id
            environment = build_environment(scene, scene.paired_conditions[0], seed=seed)
            for payload in result.actions:
                environment.step(ScenarioV4Action.model_validate(payload, strict=True))
            assert environment.is_success, (instance_id, seed, environment.terminal_reason)


def test_map16_makespan_matches_bfs_optimum() -> None:
    for instance_id, scene in all_scenes().items():
        if scene.map_id != "MAP-16":
            continue
        result = solve(instance_id)
        environment = build_environment(scene, scene.paired_conditions[0], seed=0)
        for payload in result.actions:
            environment.step(ScenarioV4Action.model_validate(payload, strict=True))
        assert environment.metrics()["makespan_ticks"] == result.optimum


def test_map22_moved_exactly_the_shortest_walk() -> None:
    for instance_id, scene in all_scenes().items():
        if scene.map_id != "MAP-22":
            continue
        result = solve(instance_id)
        assert len(result.actions) == result.optimum


def test_map22_non_memory_condition_returns_memory_disabled() -> None:
    scene = get_scene("map22_l3_original")
    environment = build_environment(scene, "history5", seed=0)
    result = environment.step(
        ScenarioV4Action.model_validate(
            {
                "tool": "write_memory",
                "facts": [{"fact_type": "node_page", "sign_id": "X", "exit_bearings": ["N"]}],
            },
            strict=True,
        )
    )
    assert result.result == "MEMORY_DISABLED"


def test_paired_conditions_share_rule_outcomes() -> None:
    for instance_id, scene in all_scenes().items():
        if len(scene.paired_conditions) < 2:
            continue
        actions = solve(instance_id, seed=_seed_list(scene)[0]).actions
        observations = []
        for condition in scene.paired_conditions:
            environment = build_environment(scene, condition, seed=_seed_list(scene)[0])
            for payload in actions:
                environment.step(ScenarioV4Action.model_validate(payload, strict=True))
            observations.append(environment.observe().model_dump(mode="json"))
        # Physical state fields must match across paired conditions; only
        # declared Agent-owned context (memory journal / casebook) may differ.
        first, *rest = observations
        for other in rest:
            for key in ("map_id", "terminal", "terminal_reason"):
                assert first[key] == other[key]
            if scene.map_id == "MAP-22":
                assert first["movement_steps"] == other["movement_steps"]
                assert first["current_coarse_silhouette"] == other["current_coarse_silhouette"]


def test_manifest_has_no_placeholder_values() -> None:
    for _instance_id, scene in all_scenes().items():
        manifest = instance_manifest(scene)
        for key in (
            "instance_id",
            "map_id",
            "rule_version",
            "level",
            "capability",
            "scenario_hash",
            "public_initial_state_hash",
            "private_truth_hash",
            "oracle_trace",
            "solver_result",
            "paired_conditions",
            "review_status",
        ):
            assert manifest[key]
            assert "<" not in str(manifest[key])
        assert manifest["review_status"] == "pending_human_review"


@pytest.mark.parametrize("instance_id", sorted(all_scenes()))
def test_scenario_hash_is_stable(instance_id: str) -> None:
    scene = get_scene(instance_id)
    assert instance_manifest(scene)["scenario_hash"] == instance_manifest(scene)["scenario_hash"]
