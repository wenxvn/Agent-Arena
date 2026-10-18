"""Batch 5：MAP-13（DCR-V10-15）。"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map13 as b13
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import scenario_hash
from agent_arena.v10.runtime.map13 import SLOTS, VARIANTS, Map13V10Environment, oracle_actions
from agent_arena.worlds.scenario_v8.models import V8Action


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
