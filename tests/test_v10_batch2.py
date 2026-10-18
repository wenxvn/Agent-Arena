"""Batch 2：MAP-06（DCR-V10-03）、MAP-15（DCR-V10-04）、MAP-21（DCR-V10-05）。"""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map06 as b06
from agent_arena.v10.baselines import map15 as b15
from agent_arena.v10.baselines import map21 as b21
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import create_environment, scenario_hash
from agent_arena.v10.runtime.map06 import VARIANTS as WEATHER
from agent_arena.v10.runtime.map06 import simulate as simulate06
from agent_arena.v10.runtime.map15 import (
    FAMILIES,
    FAMILY_BY_SEED,
    Map15V10Environment,
    build_layout,
)
from agent_arena.v10.runtime.map21 import VARIANTS as ERUPTIONS
from agent_arena.v10.runtime.map21 import Map21V10Environment
from agent_arena.worlds.scenario_v8.models import V8Action

FROZEN = {
    "src/agent_arena/worlds/scenario_v8/maps/map06.py": "MAP-06",
    "src/agent_arena/worlds/scenario_v8/maps/map15.py": "MAP-15",
    "src/agent_arena/worlds/scenario_v8/maps/map21.py": "MAP-21",
}


def _step(environment: object, payload: dict[str, object]) -> str:
    return environment.step(V8Action.model_validate(payload, strict=True)).result  # type: ignore[attr-defined]


@pytest.mark.parametrize("path", sorted(FROZEN))
def test_v8_rule_files_match_freeze_manifest(path: str) -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    files = manifest["roots"]["src/agent_arena/worlds/scenario_v8"]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


# --------------------------------------------------------------------------- MAP-06
def test_map06_cohort_is_stratified_with_ten_seeds() -> None:
    assert len(WEATHER) == 10
    weather = Counter(item.weather for item in WEATHER.values())
    assert weather["long"] == 5 and weather["calm"] >= 1 and weather["short"] >= 1
    correct = sum(
        (item.forecast == "long") == (item.weather == "long") for item in WEATHER.values()
    )
    assert correct == 8
    assert len({scenario_hash("MAP-06", seed) for seed in WEATHER}) == 10


def test_map06_seed0_direct_route_no_longer_dominates_cohort() -> None:
    direct = [
        run_policy("MAP-06", b06.ABLATIONS["always_direct"](), environment_seed=s) for s in WEATHER
    ]
    assert sum(run.success for run in direct) == 5
    assert all(
        not run.success
        for run, s in zip(direct, WEATHER, strict=True)
        if WEATHER[s].weather == "long"
    )


def test_map06_short_storm_now_has_risk() -> None:
    environment = simulate06(1, b06.oracle_actions(1))
    assert environment.is_success and environment.risk == 3


def test_map06_forecast_aware_beats_fixed_strategies_on_cohort_utility() -> None:
    def mean(factory: type) -> float:
        runs = [run_policy("MAP-06", factory(), environment_seed=s) for s in WEATHER]
        return sum(float(run.primary_value or 0) for run in runs) / len(runs)

    aware = mean(b06.HEURISTIC)
    assert aware > mean(b06.ABLATIONS["always_direct"])
    assert aware > mean(b06.ABLATIONS["always_reinforce"])
    oracle = [run_actions("MAP-06", b06.oracle_actions(s), environment_seed=s) for s in WEATHER]
    assert all(run.success for run in oracle)
    assert all(run.metrics["map06.v10.utility_regret"]["value"] == 0 for run in oracle)


def test_map06_weather_is_never_observable() -> None:
    for seed in WEATHER:
        environment = create_environment("MAP-06", environment_seed=seed)
        for payload in b06.oracle_actions(seed):
            text = json.dumps(environment.observe())
            assert "weather" not in text and "calm" not in text and "cohort" not in text
            _step(environment, payload)


# --------------------------------------------------------------------------- MAP-15
def test_map15_goal_no_longer_leaks_rule() -> None:
    for seed in FAMILY_BY_SEED:
        environment = Map15V10Environment(seed=seed)
        text = json.dumps(environment.observe(), ensure_ascii=False)
        assert "互补" not in text and "偶数" not in text
        assert environment.family.rule_id not in text
        assert all(environment.family.rule_id not in rule for rule in environment.public_rules())


def test_map15_families_and_unseen_test_walls() -> None:
    assert set(FAMILY_BY_SEED.values()) == set(FAMILIES)
    for seed in FAMILY_BY_SEED:
        layout = build_layout(seed)
        training = {layout.walls[area] for area in ("A", "B", "C")}
        assert not training & {layout.walls["T1"], layout.walls["T2"]}


def test_map15_wrong_test_choice_does_not_flip_phase() -> None:
    environment = Map15V10Environment(seed=0)
    for payload in b15.oracle_actions(0):
        if environment.area == "T1":
            break
        _step(environment, payload)
    assert environment.area == "T1"
    tick = environment.tick_count
    doors = environment.layout.doors["T1"]
    wanted = b15.target_color(environment.family, environment.layout.walls["T1"], tick)
    wrong = next(index for index, color in enumerate(doors, 1) if color != wanted)
    assert _step(environment, {"tool": "choose_door", "slot_index": wrong}) == "INVALID_TRANSITION"
    assert environment.tick_count == tick
    assert _step(environment, {"tool": "choose_door", "slot_index": wrong}) == "INVALID_TRANSITION"
    assert environment.terminal_reason == "TEST_WRONG_LIMIT"


def test_map15_record_required_and_rule_format() -> None:
    environment = Map15V10Environment(seed=0)
    for _ in range(40):
        if environment.area == "C":
            break
        wanted = b15.target_color(
            environment.family, environment.layout.walls[environment.area], environment.tick_count
        )
        _step(
            environment,
            {
                "tool": "choose_door",
                "slot_index": environment.layout.doors[environment.area].index(wanted) + 1,
            },
        )
    assert environment.area == "C"
    assert _step(environment, {"tool": "choose_door", "slot_index": 1}) == "RULE_RECORD_REQUIRED"
    assert (
        _step(
            environment,
            {"tool": "record_rule", "rule_id": "even-same", "supporting_sample_ids": ["ARCHIVE_1"]},
        )
        == "RULE_FORMAT_INVALID"
    )


def test_map15_inductive_heuristic_generalizes_and_ablations_fail() -> None:
    seeds = tuple(FAMILY_BY_SEED)
    heuristic = [run_policy("MAP-15", b15.HEURISTIC(), environment_seed=s) for s in seeds]
    assert all(run.success for run in heuristic)
    assert all(run.metrics["map15.v10.rule_generalization"]["value"] == 1 for run in heuristic)
    for name, factory in b15.ABLATIONS.items():
        runs = [run_policy("MAP-15", factory(), environment_seed=s) for s in seeds]
        assert sum(run.success for run in runs) <= 1, name
    oracle = [run_actions("MAP-15", b15.oracle_actions(s), environment_seed=s) for s in seeds]
    assert all(run.success and run.mechanism_triggered for run in oracle)


# --------------------------------------------------------------------------- MAP-21
def test_map21_direct_evacuation_is_safe_but_not_full_score() -> None:
    for seed in ERUPTIONS:
        run = run_policy("MAP-21", b21.ABLATIONS["always_evac"](), environment_seed=seed)
        assert run.success
        assert run.metrics["map21.v10.science_completion"]["value"] == 0.0
        assert run.metrics["map21.v10.overall_utility"]["value"] == 0.5


def test_map21_cohort_covers_all_eruption_ticks_and_oracle_is_full_science() -> None:
    assert {tick for tick, _ in ERUPTIONS.values()} == {12, 16, 20}
    for seed in ERUPTIONS:
        run = run_actions("MAP-21", b21.oracle_actions(seed), environment_seed=seed)
        assert run.success
        assert run.metrics["map21.v10.science_completion"]["value"] == 1.0


def test_map21_greedy_collection_causes_catastrophe_on_early_eruption() -> None:
    deaths = [
        run_policy("MAP-21", b21.ABLATIONS["always_collect"](), environment_seed=s)
        for s in ERUPTIONS
    ]
    catastrophes = [run.metrics["map21.v10.catastrophe"]["value"] for run in deaths]
    assert sum(catastrophes) == sum(1 for tick, _ in ERUPTIONS.values() if tick == 12)
    aware = [run_policy("MAP-21", b21.HEURISTIC(), environment_seed=s) for s in ERUPTIONS]
    assert all(run.metrics["map21.v10.catastrophe"]["value"] == 0 for run in aware)
    mean = sum(float(run.primary_value) for run in aware) / len(aware)
    assert mean > 0.5


def test_map21_rejected_actions_cost_time() -> None:
    environment = Map21V10Environment(seed=0)
    assert _step(environment, {"tool": "move", "edge_id": "R_W"}) == "EDGE_NOT_ADJACENT"
    assert environment.tick_count == 1


def test_map21_eruption_tick_never_in_observation() -> None:
    environment = Map21V10Environment(seed=1)
    for payload in b21.oracle_actions(1):
        observation = environment.observe()
        assert "eruption_tick" not in observation
        _step(environment, payload)
