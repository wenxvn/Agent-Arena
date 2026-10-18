"""Batch 5：MAP-08（DCR-V10-16）与 MAP-13（DCR-V10-15）。"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map08 as b08
from agent_arena.v10.baselines import map13 as b13
from agent_arena.v10.baselines import map26 as b26
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import scenario_hash
from agent_arena.v10.runtime.map08 import SITES as SITES08
from agent_arena.v10.runtime.map08 import VARIANTS as VARIANTS08
from agent_arena.v10.runtime.map08 import Map08V10Environment
from agent_arena.v10.runtime.map08 import oracle_actions as oracle08
from agent_arena.v10.runtime.map13 import SLOTS, VARIANTS, Map13V10Environment, oracle_actions
from agent_arena.v10.runtime.map26 import VARIANTS as VARIANTS26
from agent_arena.v10.runtime.map26 import Map26V10Environment
from agent_arena.v10.runtime.map26 import oracle_actions as oracle26
from agent_arena.worlds.scenario_v8.models import V8Action


# --------------------------------------------------------------------------- MAP-26
def test_map26_seeds_differ_and_publish_partitions() -> None:
    assert len(VARIANTS26) == 4
    assert len({scenario_hash("MAP-26", seed) for seed in VARIANTS26}) == 4
    assert len({variant.fault for variant in VARIANTS26.values()}) >= 2
    observation = Map26V10Environment(seed=3).observe()
    assert observation["spares"]["P3"] == 0
    assert observation["test_partitions"]


def test_map26_wrong_swap_costs_wear_and_rollback_keeps_spare_spent() -> None:
    environment = Map26V10Environment(seed=0)
    environment.step(V8Action.model_validate({"tool": "replace", "part_id": "P1"}, strict=True))
    assert environment.wear == 1
    assert environment.spares["P1"] == 0
    environment.step(V8Action.model_validate({"tool": "rollback"}, strict=True))
    assert environment.installed is None
    assert environment.spares["P1"] == 0
    environment.step(V8Action.model_validate({"tool": "replace", "part_id": "P3"}, strict=True))
    assert environment.is_terminal
    assert environment.terminal_reason == "UNIT_UNRECOVERABLE"


def test_map26_oracle_heuristic_and_ablations() -> None:
    for seed in VARIANTS26:
        oracle = run_actions("MAP-26", oracle26(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map26.v10.spares_used"]["value"] == 1
        assert oracle.metrics["map26.v10.wrong_swaps"]["value"] == 0
        heuristic = run_policy("MAP-26", b26.HEURISTIC(), environment_seed=seed, decision_budget=38)
        assert heuristic.success
        assert heuristic.metrics["map26.v10.diagnosis_precision"]["value"] == 1
    blind = [
        run_policy(
            "MAP-26", b26.ABLATIONS["no_diagnosis"](), environment_seed=seed, decision_budget=38
        )
        for seed in VARIANTS26
    ]
    assert sum(run.success for run in blind) <= 3
    assert max(
        run.metrics["map26.v10.spares_used"]["value"]
        for run in blind
        if run.success
    ) >= 2
    ignore = [
        run_policy(
            "MAP-26", b26.ABLATIONS["test_but_ignore"](), environment_seed=seed, decision_budget=38
        )
        for seed in VARIANTS26
    ]
    assert sum(run.success for run in ignore) == 0


# --------------------------------------------------------------------------- MAP-08
def test_map08_seeds_differ_in_partitions_and_min_tests() -> None:
    assert len(VARIANTS08) == 4
    assert len({scenario_hash("MAP-08", seed) for seed in VARIANTS08}) == 4
    assert len({variant.leak for variant in VARIANTS08.values()}) >= 3
    assert len({variant.minimum_tests() for variant in VARIANTS08.values()}) >= 2
    observation = Map08V10Environment(seed=0).observe()
    assert sorted(observation["candidate_sites"]) == sorted(SITES08)
    assert observation["test_partitions"]


def test_map08_seal_requires_unique_candidate_and_repair_requires_seal() -> None:
    environment = Map08V10Environment(seed=0)
    refused = environment.step(
        V8Action.model_validate({"tool": "seal_diagnosis", "diagnosis_code": "S1"}, strict=True)
    )
    assert refused.result == "DIAGNOSIS_INCOMPLETE"
    blocked = environment.step(
        V8Action.model_validate({"tool": "repair", "target_id": "S1"}, strict=True)
    )
    assert blocked.result == "DIAGNOSIS_REQUIRED"
    assert environment.unjustified == 1


def test_map08_oracle_and_ablations() -> None:
    for seed in VARIANTS08:
        oracle = run_actions("MAP-08", oracle08(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map08.v10.hypothesis_reduction"]["value"] == 1.0
        heuristic = run_policy("MAP-08", b08.HEURISTIC(), environment_seed=seed, decision_budget=20)
        assert heuristic.success
        assert heuristic.metrics["map08.v10.hypothesis_reduction"]["value"] == 1.0
    for name in ("no_hypothesis", "blind_repairs"):
        runs = [
            run_policy("MAP-08", b08.ABLATIONS[name](), environment_seed=seed, decision_budget=20)
            for seed in VARIANTS08
        ]
        assert sum(run.success for run in runs) == 0, name
    single = [
        run_policy(
            "MAP-08", b08.ABLATIONS["single_test"](), environment_seed=seed, decision_budget=20
        )
        for seed in VARIANTS08
    ]
    assert sum(run.success for run in single) <= 1


# --------------------------------------------------------------------------- MAP-13
def _step(environment: Map13V10Environment, payload: dict[str, object]) -> str:
    return environment.step(V8Action.model_validate(payload, strict=True)).result


def test_v8_map13_rule_file_matches_freeze_manifest() -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    path = "src/agent_arena/worlds/scenario_v8/maps/map13.py"
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


def test_map13_seeds_are_distinct_puzzles_with_unique_solutions() -> None:
    assert len(VARIANTS) == 4
    assert len({scenario_hash("MAP-13", seed) for seed in VARIANTS}) == 4
    assert len({variant.symbols for variant in VARIANTS.values()}) == 4
    targets = {tuple(sorted(variant.target.items())) for variant in VARIANTS.values()}
    assert len(targets) == 4
    for variant in VARIANTS.values():
        assert sorted(variant.target[slot] for slot in SLOTS) == sorted(variant.symbols)


def test_map13_record_is_required_before_layout_and_verify() -> None:
    environment = Map13V10Environment(seed=0)
    layout = dict(VARIANTS[0].target)
    blocked = _step(
        environment, {"tool": "set_trial_layout", "layout_by_room": layout}
    )
    assert blocked == "CONSTRAINTS_NOT_RECORDED"
    _step(environment, {"tool": "read_inscription", "room": "C"})
    _step(environment, {"tool": "record_constraint", "clue_id": "ORIENTATION_ORDER"})
    assert _step(
        environment, {"tool": "set_trial_layout", "layout_by_room": layout}
    ) == "trial_layout_set"
    assert _step(environment, {"tool": "verify_layout"}) == "CONSTRAINTS_NOT_RECORDED"


def test_map13_illegal_verify_is_counted_separately() -> None:
    environment = Map13V10Environment(seed=0)
    assert _step(environment, {"tool": "verify_layout"}) == "ILLEGAL_DOOR"
    assert environment.illegal_without_layout == 1
    assert environment.wrong_layout_attempts == 0


def test_map13_oracle_and_ablations() -> None:
    for seed in VARIANTS:
        oracle = run_actions("MAP-13", oracle_actions(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map13.v10.constraint_satisfaction_ratio"]["value"] == 1.0
        heuristic = run_policy("MAP-13", b13.HEURISTIC(), environment_seed=seed, decision_budget=30)
        assert heuristic.success
        assert heuristic.metrics["map13.v10.constraint_satisfaction_ratio"]["value"] == 1.0
    for name in ("no_record", "blind_guess", "record_only_nail"):
        runs = [
            run_policy("MAP-13", b13.ABLATIONS[name](), environment_seed=seed, decision_budget=30)
            for seed in VARIANTS
        ]
        assert sum(run.success for run in runs) == 0, name
    optional = [
        run_policy(
            "MAP-13",
            b13.ABLATIONS["no_direction_nail"](),
            environment_seed=seed,
            decision_budget=30,
        )
        for seed in VARIANTS
    ]
    assert all(run.success for run in optional)
    assert all(
        run.metrics["map13.v10.constraint_satisfaction_ratio"]["value"] == 0.8 for run in optional
    )


@pytest.mark.parametrize("seed", sorted(VARIANTS))
def test_map13_target_layout_never_published(seed: int) -> None:
    environment = Map13V10Environment(seed=seed)
    text = json.dumps(environment.observe(), ensure_ascii=False)
    assert "target_layout" not in text
    assert "truth_seal" not in text
