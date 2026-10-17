"""离线验收：30 图注册、Oracle、fixture、指标与泄漏边界。"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from agent_arena.v7.metrics.registry import specs_for
from agent_arena.worlds.scenario_v8 import adapter_cases, create_environment
from agent_arena.worlds.scenario_v8.catalog import CONDITIONS, MAP_IDS
from agent_arena.worlds.scenario_v8.models import V8Action
from agent_arena.worlds.scenario_v8.oracle import load_oracle_groups, normalize_action_payload

CORE_KEYS = {"map_id", "terminal", "terminal_reason", "last_action_result"}
V4_RUNTIME_MAPS = frozenset(CONDITIONS)


def module_for(map_id: str) -> Any | None:
    try:
        return importlib.import_module(f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}")
    except ModuleNotFoundError:
        return None


def oracle_cases(map_id: str) -> list[dict[str, Any]]:
    module = module_for(map_id)
    custom = getattr(module, "ORACLE_CASES", None) if module else None
    if custom:
        return [dict(case) for case in custom]
    if map_id in V4_RUNTIME_MAPS:
        return [dict(case) for case in adapter_cases.oracle_cases(map_id)]
    return [
        {
            "trace_id": trace_id,
            "seed": 0,
            "actions": [row["action"] for row in rows],
            "expect_success": True,
        }
        for trace_id, rows in load_oracle_groups(map_id).items()
    ]


def fixtures(map_id: str) -> list[dict[str, Any]]:
    module = module_for(map_id)
    if module is not None:
        return [dict(case) for case in getattr(module, "FIXTURES", ())]
    return [dict(case) for case in adapter_cases.fixtures(map_id)]


def replay(map_id: str, actions: list[dict[str, Any]], seed: int = 0) -> Any:
    environment = create_environment(map_id, seed=seed)
    for payload in actions:
        environment.step(V8Action.model_validate(normalize_action_payload(payload), strict=True))
    return environment


def test_catalog_has_thirty_maps() -> None:
    assert len(MAP_IDS) == 30
    assert set(CONDITIONS) <= set(MAP_IDS)


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_oracle_replays_to_success(map_id: str) -> None:
    cases = oracle_cases(map_id)
    assert cases, f"{map_id} has no oracle case"
    for case in cases:
        environment = replay(map_id, case["actions"], case.get("seed", 0))
        assert environment.is_success, (
            map_id,
            case.get("trace_id"),
            environment.status.value,
            environment.terminal_reason,
        )


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_replay_is_deterministic(map_id: str) -> None:
    case = oracle_cases(map_id)[0]
    first = replay(map_id, case["actions"], case.get("seed", 0))
    second = replay(map_id, case["actions"], case.get("seed", 0))
    assert first.state_hash() == second.state_hash()
    assert first.observe() == second.observe()


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_terminal_state_is_immutable(map_id: str) -> None:
    environment = replay(map_id, oracle_cases(map_id)[0]["actions"])
    assert environment.is_terminal
    before = (environment.state_hash(), environment.tick_count, environment.observe())
    result = environment.step(V8Action.model_validate({"tool": "wait", "turns": 1}, strict=True))
    assert result.result == "ALREADY_TERMINAL"
    assert (environment.state_hash(), environment.tick_count, environment.observe()) == before


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_public_observation_stays_inside_allowlist(map_id: str) -> None:
    environment = create_environment(map_id)
    public = set(environment.observe())
    assert public <= set(environment.PUBLIC_FIELDS) | CORE_KEYS


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_metrics_match_registry(map_id: str) -> None:
    registered = {spec.metric_id for spec in specs_for(map_id)}
    assert registered
    fresh = create_environment(map_id)
    assert set(fresh.metrics()) == registered
    environment = replay(map_id, oracle_cases(map_id)[0]["actions"])
    assert set(environment.metrics()) == registered


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_hand_fixtures_pass(map_id: str) -> None:
    cases = fixtures(map_id)
    assert len(cases) >= 2, f"{map_id} needs at least two hand-computed fixtures"
    for case in cases:
        environment = replay(map_id, case["actions"], case.get("seed", 0))
        metrics = environment.metrics()
        for metric_id, expected in case["expect"].items():
            value = metrics.get(metric_id)
            if isinstance(value, dict):
                value = (
                    round(value["numerator"] / value["denominator"], 6)
                    if value["denominator"]
                    else None
                )
            assert value == expected, (map_id, case["name"], metric_id, expected, value)
