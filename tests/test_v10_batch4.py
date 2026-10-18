"""Batch 4：MAP-04（DCR-V10-08）。"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map04 as b04
from agent_arena.v10.baselines import map14 as b14
from agent_arena.v10.baselines import map19 as b19
from agent_arena.v10.baselines import map20 as b20
from agent_arena.v10.baselines import map23 as b23
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import scenario_hash
from agent_arena.v10.runtime.map04 import (
    FAILED_CROSSING_TICKS,
    VARIANTS,
    Map04V10Environment,
    oracle_actions,
)
from agent_arena.v10.runtime.map14 import VARIANTS as VARIANTS14
from agent_arena.v10.runtime.map14 import Map14V10Environment
from agent_arena.v10.runtime.map14 import oracle_actions as oracle14
from agent_arena.v10.runtime.map19 import VARIANTS as VARIANTS19
from agent_arena.v10.runtime.map19 import Map19V10Environment
from agent_arena.v10.runtime.map19 import oracle_actions as oracle19
from agent_arena.v10.runtime.map20 import DIRECT_MAX as DIRECT_MAX20
from agent_arena.v10.runtime.map20 import VARIANTS as VARIANTS20
from agent_arena.v10.runtime.map20 import Map20V10Environment
from agent_arena.v10.runtime.map20 import oracle_actions as oracle20
from agent_arena.v10.runtime.map23 import ENTRANCES as ENTRANCES23
from agent_arena.v10.runtime.map23 import TRUTH_BY_SEED as TRUTH_BY_SEED23
from agent_arena.v10.runtime.map23 import Map23V10Environment
from agent_arena.v10.runtime.map23 import oracle_actions as oracle23
from agent_arena.worlds.scenario_v8.models import V8Action


def _step(environment: Map04V10Environment, payload: dict[str, object]) -> str:
    return environment.step(V8Action.model_validate(payload, strict=True)).result


def test_v8_map04_rule_file_matches_freeze_manifest() -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    path = "src/agent_arena/worlds/scenario_v8/maps/map04.py"
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


def test_map04_seeds_are_distinct_instances() -> None:
    assert len(VARIANTS) == 6
    assert len({scenario_hash("MAP-04", seed) for seed in VARIANTS}) == 6
    assert any(variant.extra_detour for variant in VARIANTS.values())
    assert any(variant.initial_phase in variant.safe_phases for variant in VARIANTS.values())


def test_map04_failed_crossing_costs_three_ticks_and_pushes_back() -> None:
    variant = next(item for item in VARIANTS.values() if item.initial_phase not in item.safe_phases)
    environment = Map04V10Environment(
        seed=next(key for key, item in VARIANTS.items() if item is variant)
    )
    _step(environment, {"tool": "move", "edge_id": "T_S"})
    start_tick = environment.tick_count
    start_phase = environment.tide_phase
    result = _step(environment, {"tool": "move", "edge_id": "S_G"})
    assert result == "TIDE_WINDOW_CLOSED"
    assert environment.node == "S"
    assert environment.tick_count - start_tick == FAILED_CROSSING_TICKS
    assert environment.tide_phase == (start_phase + FAILED_CROSSING_TICKS) % variant.period


def test_map04_oracle_and_heuristic_succeed_on_every_seed() -> None:
    oracle_margins = []
    for seed in VARIANTS:
        oracle = run_actions("MAP-04", oracle_actions(seed), environment_seed=seed)
        assert oracle.success and oracle.mechanism_triggered
        oracle_margins.append(oracle.metrics["map04.v10.time_margin"]["value"])
        heuristic = run_policy("MAP-04", b04.HEURISTIC(), environment_seed=seed, decision_budget=30)
        assert heuristic.success
        assert (
            heuristic.metrics["map04.v10.time_margin"]["value"]
            <= oracle_margins[-1]
        )
        assert heuristic.metrics["map04.v10.window_hit_rate"]["value"] > 0


def test_map04_detour_is_legal_but_never_better_than_the_oracle() -> None:
    detour_margins = []
    for seed in VARIANTS:
        run = run_policy(
            "MAP-04", b04.ABLATIONS["detour_only"](), environment_seed=seed, decision_budget=30
        )
        assert run.success
        assert run.metrics["map04.v10.window_hit_rate"]["state"] == "NOT_APPLICABLE"
        assert run.metrics["map04.v10.detour_edges"]["value"] >= 12
        detour_margins.append(run.metrics["map04.v10.time_margin"]["value"])
    oracle_margins = [
        run_actions("MAP-04", oracle_actions(seed), environment_seed=seed).metrics[
            "map04.v10.time_margin"
        ]["value"]
        for seed in VARIANTS
    ]
    assert all(
        detour <= oracle for detour, oracle in zip(detour_margins, oracle_margins, strict=True)
    )


def test_map04_blind_retry_only_survives_a_safe_opening_phase() -> None:
    runs = {
        seed: run_policy(
            "MAP-04", b04.ABLATIONS["blind_retry"](), environment_seed=seed, decision_budget=30
        )
        for seed in VARIANTS
    }
    for seed, run in runs.items():
        variant = VARIANTS[seed]
        if run.success:
            assert variant.initial_phase in variant.safe_phases
    assert sum(run.success for run in runs.values()) <= 1


@pytest.mark.parametrize("name", ["excess_wait", "fixed_phase_script"])
def test_map04_other_ablations_fail(name: str) -> None:
    runs = [
        run_policy("MAP-04", b04.ABLATIONS[name](), environment_seed=seed, decision_budget=30)
        for seed in VARIANTS
    ]
    assert sum(run.success for run in runs) == 0


# --------------------------------------------------------------------------- MAP-19
def _step19(environment: Map19V10Environment, payload: dict[str, object]) -> str:
    return environment.step(V8Action.model_validate(payload, strict=True)).result


def test_v8_map19_rule_file_matches_freeze_manifest() -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    path = "src/agent_arena/worlds/scenario_v8/maps/map19.py"
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


def test_map19_seeds_differ_and_publish_exact_temperatures() -> None:
    assert len(VARIANTS19) == 4
    assert len({scenario_hash("MAP-19", seed) for seed in VARIANTS19}) == 4
    assert len({variant.tolerance for variant in VARIANTS19.values()}) >= 2
    observation = Map19V10Environment(seed=0).observe()
    assert observation["current_temperatures"] == dict(VARIANTS19[0].temperatures)
    assert observation["forecast_tolerance"] == VARIANTS19[0].tolerance
    assert observation["cooling_budget"] == VARIANTS19[0].cooling_budget


def test_map19_unpredicted_tick_voids_production() -> None:
    environment = Map19V10Environment(seed=0)
    before = environment.production
    _step19(environment, {"tool": "wait"})
    assert environment.production == before
    assert environment.unpredicted_ticks == 1
    assert environment.rejected_ticks == 1


def test_map19_wrong_forecast_is_rejected_and_visible() -> None:
    environment = Map19V10Environment(seed=0)
    _step19(environment, {"tool": "forecast_next", "forecast_next": [0, 0, 0]})
    _step19(environment, {"tool": "wait"})
    assert environment.rejected_ticks == 1
    assert environment.production == 0
    assert environment.last_error is not None and environment.last_error > VARIANTS19[0].tolerance


def test_map19_oracle_heuristic_and_ablations() -> None:
    for seed in VARIANTS19:
        oracle = run_actions("MAP-19", oracle19(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map19.v10.production_credit"]["value"] == 1.0
        assert oracle.metrics["map19.v10.rejected_ticks"]["value"] == 0
        heuristic = run_policy("MAP-19", b19.HEURISTIC(), environment_seed=seed, decision_budget=60)
        assert heuristic.success
        assert heuristic.metrics["map19.v10.mean_forecast_error"]["value"] == 0.0
    for name in ("no_forecast", "fixed_vector_no_lag", "max_loads_no_cooling"):
        runs = [
            run_policy("MAP-19", b19.ABLATIONS[name](), environment_seed=seed, decision_budget=60)
            for seed in VARIANTS19
        ]
        assert sum(run.success for run in runs) == 0, name
    naive = [
        run_policy(
            "MAP-19", b19.ABLATIONS["naive_forecast"](), environment_seed=seed, decision_budget=60
        )
        for seed in VARIANTS19
    ]
    assert sum(run.success for run in naive) <= 1


# --------------------------------------------------------------------------- MAP-23
def test_map23_seeds_cover_all_four_entrances() -> None:
    assert len(TRUTH_BY_SEED23) == 4
    assert set(TRUTH_BY_SEED23.values()) == set(ENTRANCES23)
    assert len({scenario_hash("MAP-23", seed) for seed in TRUTH_BY_SEED23}) == 4


def test_map23_investigate_requires_a_purchased_clue() -> None:
    environment = Map23V10Environment(seed=0)
    target = ENTRANCES23[0]
    environment.step(V8Action.model_validate({"tool": "move", "to": target}, strict=True))
    refused = environment.step(
        V8Action.model_validate({"tool": "investigate", "entrance": target}, strict=True)
    )
    assert refused.result == "CLUE_REQUIRED"
    assert environment.unjustified == 1
    environment.step(V8Action.model_validate({"tool": "move", "to": "A"}, strict=True))
    environment.step(V8Action.model_validate({"tool": "move", "to": "N"}, strict=True))
    environment.step(V8Action.model_validate({"tool": "scout"}, strict=True))
    excluded = [entry for entry in ENTRANCES23 if entry not in environment.candidates()]
    assert excluded
    environment.step(
        V8Action.model_validate({"tool": "mark", "choice": excluded[0]}, strict=True)
    )
    environment.step(V8Action.model_validate({"tool": "move", "to": "A"}, strict=True))
    environment.step(V8Action.model_validate({"tool": "move", "to": excluded[0]}, strict=True))
    blocked = environment.step(
        V8Action.model_validate({"tool": "investigate", "entrance": excluded[0]}, strict=True)
    )
    assert blocked.result == "MARK_EXCLUDED_BY_CLUE"


def test_map23_oracle_heuristic_and_ablations() -> None:
    for seed in TRUTH_BY_SEED23:
        oracle = run_actions("MAP-23", oracle23(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map23.v10.clue_utilization"]["state"] == "VALID"
        heuristic = run_policy("MAP-23", b23.HEURISTIC(), environment_seed=seed, decision_budget=38)
        assert heuristic.success
        assert heuristic.metrics["map23.v10.unjustified_investigations"]["value"] == 0
    for name in ("no_scout", "ignore_counterevidence", "scout_everything"):
        runs = [
            run_policy("MAP-23", b23.ABLATIONS[name](), environment_seed=seed, decision_budget=38)
            for seed in TRUTH_BY_SEED23
        ]
        assert sum(run.success for run in runs) == 0, name
    single = [
        run_policy(
            "MAP-23", b23.ABLATIONS["single_clue"](), environment_seed=seed, decision_budget=38
        )
        for seed in TRUTH_BY_SEED23
    ]
    assert sum(run.success for run in single) <= 2


# --------------------------------------------------------------------------- MAP-20
def test_v8_map20_rule_file_matches_freeze_manifest() -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    path = "src/agent_arena/worlds/scenario_v8/maps/map20.py"
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


def test_map20_seeds_rotate_hot_zones_and_publish_heat_schedule() -> None:
    assert len(VARIANTS20) == 4
    assert len({scenario_hash("MAP-20", seed) for seed in VARIANTS20}) == 4
    assert len({variant.hot_sequence for variant in VARIANTS20.values()}) == 4
    observation = Map20V10Environment(seed=0).observe()
    assert observation["heat_schedule"] == VARIANTS20[0].schedule
    assert observation["production_base"] == {"A": 4, "B": 3, "C": 2}
    assert max(max(values) for values in observation["heat_schedule"].values()) > 25


def test_map20_hot_zone_exceeds_direct_capacity() -> None:
    environment = Map20V10Environment(seed=1)
    hot = VARIANTS20[1].hot_sequence[0]
    assert environment.heat(hot) > DIRECT_MAX20
    result = environment.step(
        V8Action.model_validate({"tool": "wait"}, strict=True)
    )
    assert result.result != "THERMAL_OVERHEAT"


def test_map20_oracle_heuristic_and_ablations() -> None:
    for seed in VARIANTS20:
        oracle = run_actions("MAP-20", oracle20(seed), environment_seed=seed, name="oracle")
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map20.v10.production_credit"]["value"] == 1.0
        assert oracle.metrics["map20.v10.bypass_used_ticks"]["value"] > 0
        heuristic = run_policy("MAP-20", b20.HEURISTIC(), environment_seed=seed, decision_budget=56)
        assert heuristic.success
    for name, factory in b20.ABLATIONS.items():
        runs = [
            run_policy("MAP-20", factory(), environment_seed=seed, decision_budget=56)
            for seed in VARIANTS20
        ]
        assert sum(run.success for run in runs) == 0, name


# --------------------------------------------------------------------------- MAP-14
def test_v8_map14_rule_file_matches_freeze_manifest() -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    path = "src/agent_arena/worlds/scenario_v8/maps/map14.py"
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


def test_map14_seeds_differ_in_shape_not_only_names() -> None:
    assert len(VARIANTS14) == 6
    assert len({scenario_hash("MAP-14", seed) for seed in VARIANTS14}) == 6
    assert len({len(variant.configurations) for variant in VARIANTS14.values()}) >= 2
    partitions = {
        tuple(sorted(tuple(sorted(subset)) for _, subset in variant.claims.values()))
        for variant in VARIANTS14.values()
    }
    assert len(partitions) >= 4


def test_map14_rule_is_published_and_truth_is_not() -> None:
    environment = Map14V10Environment(seed=0)
    observation = environment.observe()
    assert "恰一名祭司" in str(observation["truth_rule"])
    assert any("恰有一人" in rule or "恰一名" in rule for rule in environment.public_rules())
    text = json.dumps(observation, ensure_ascii=False)
    assert "truth_seal" not in text
    assert "truthful_priest" not in text
    assert "minimum_queries" not in text


def test_map14_blind_submission_cannot_open_the_gate() -> None:
    environment = Map14V10Environment(seed=0)
    moves = [
        {"tool": "move", "edge_id": "P_A"},
        {"tool": "move", "edge_id": "A_O"},
        {"tool": "move", "edge_id": "O_J"},
    ]
    for payload in moves:
        environment.step(V8Action.model_validate(payload, strict=True))
    result = environment.step(
        V8Action.model_validate(
            {"tool": "submit_configuration", "choice": VARIANTS14[0].truth_configuration},
            strict=True,
        )
    )
    assert result.result == "NO_CONSISTENT_HYPOTHESIS"
    assert not environment.gate_open


def test_map14_oracle_heuristic_and_ablations() -> None:
    for seed in VARIANTS14:
        oracle = run_actions("MAP-14", oracle14(seed), environment_seed=seed)
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map14.v10.deduction_success"]["value"] == 1
        heuristic = run_policy("MAP-14", b14.HEURISTIC(), environment_seed=seed, decision_budget=38)
        assert heuristic.success
    for name in ("blind_two_submissions", "no_seal"):
        runs = [
            run_policy("MAP-14", b14.ABLATIONS[name](), environment_seed=seed, decision_budget=38)
            for seed in VARIANTS14
        ]
        assert sum(run.success for run in runs) == 0, name
    runs = [
        run_policy(
            "MAP-14",
            b14.ABLATIONS["one_question"](),
            environment_seed=seed,
            decision_budget=38,
        )
        for seed in VARIANTS14
    ]
    assert sum(run.success for run in runs) <= 2


def test_map14_waste_questions_opens_gate_but_scores_zero() -> None:
    runs = [
        run_policy(
            "MAP-14",
            b14.ABLATIONS["waste_questions"](),
            environment_seed=seed,
            decision_budget=38,
        )
        for seed in VARIANTS14
    ]
    assert all(run.metrics["map14.v10.queries_used"]["value"] >= 3 for run in runs)
    assert sum(run.metrics["map14.v10.deduction_success"]["value"] for run in runs) < len(runs)
