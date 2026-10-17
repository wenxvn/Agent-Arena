"""Offline checker for one V8 map: oracle replay, fixtures, leakage, metrics.

Usage: python scripts/check_v8_map.py MAP-07
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v7.metrics.registry import specs_for  # noqa: E402
from agent_arena.worlds.scenario_v8 import create_environment  # noqa: E402
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status  # noqa: E402
from agent_arena.worlds.scenario_v8.oracle import (  # noqa: E402
    load_oracle_groups,
    normalize_action_payload,
    replay_group,
)

CORE_KEYS = {"map_id", "terminal", "terminal_reason", "last_action_result"}


def module_for(map_id: str) -> Any | None:
    """Return the map module, or ``None`` for the six V4 adapter maps.

    MAP-08/16/18/22/26/30 reuse the frozen V4 runtimes through
    ``v4_adapter`` and therefore have no ``maps/mapXX.py`` of their own.
    """

    try:
        return importlib.import_module(
            f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}"
        )
    except ModuleNotFoundError:
        return None


def run_actions(map_id: str, actions: list[dict[str, Any]], *, seed: int = 0) -> Any:
    environment = create_environment(map_id, seed=seed)
    for payload in actions:
        action = V8Action.model_validate(normalize_action_payload(payload), strict=True)
        environment.step(action)
    return environment


def check_leakage(environment: Any) -> list[str]:
    public = set(environment.observe())
    allowed = set(environment.PUBLIC_FIELDS) | CORE_KEYS
    return sorted(public - allowed)


def check_metrics(environment: Any) -> list[str]:
    problems: list[str] = []
    known = {spec.metric_id for spec in specs_for(environment.map_id)}
    for metric_id in environment.metrics():
        if metric_id not in known:
            problems.append(f"unregistered metric id: {metric_id}")
    missing = known - set(environment.metrics())
    if missing:
        problems.append(f"missing metric ids: {sorted(missing)}")
    return problems


def adapter_cases_for(map_id: str) -> Any:
    from agent_arena.worlds.scenario_v8 import adapter_cases

    return adapter_cases


def main(map_id: str) -> int:
    module = module_for(map_id)
    problems: list[str] = []
    print(f"== {map_id} ==")

    custom = getattr(module, "ORACLE_CASES", None) if module else None
    if custom is None and module is None:
        custom = adapter_cases_for(map_id).oracle_cases(map_id)
    if custom is not None:
        for case in custom:
            environment = create_environment(map_id, seed=case.get("seed", 0))
            for payload in case["actions"]:
                environment.step(V8Action.model_validate(payload, strict=True))
            synthetic = [{"action": payload} for payload in case["actions"]]
            outcome = replay_group(map_id, synthetic, seed=case.get("seed", 0))
            print(
                f"oracle[{case.get('trace_id', 'custom')}] steps={len(case['actions'])}"
                f" status={environment.status.value} reason={environment.terminal_reason}"
            )
            if case.get("expect_success") and not environment.is_success:
                problems.append(f"oracle case {case.get('trace_id')} did not succeed")
            if outcome.failures:
                problems.extend(outcome.failures)
    else:
        for trace_id, rows in load_oracle_groups(map_id).items():
            outcome = replay_group(map_id, rows, trace_id=trace_id)
            print(
                f"oracle[{trace_id}] steps={outcome.actions} status={outcome.status}"
                f" reason={outcome.terminal_reason}"
            )
            problems.extend(f"{trace_id}: {failure}" for failure in outcome.failures)

    fixtures = getattr(module, "FIXTURES", ()) if module else ()
    if not fixtures and module is None:
        fixtures = adapter_cases_for(map_id).fixtures(map_id)
    for fixture in fixtures:
        environment = run_actions(
            map_id, fixture["actions"], seed=fixture.get("seed", 0)
        )
        metrics = environment.metrics()
        for metric_id, expected in fixture["expect"].items():
            value = metrics.get(metric_id)
            if isinstance(value, dict):
                value = (
                    round(value["numerator"] / value["denominator"], 6)
                    if value["denominator"]
                    else None
                )
            if value != expected:
                problems.append(
                    f"fixture {fixture['name']}: {metric_id} expected {expected}, got {value}"
                )
        print(f"fixture[{fixture['name']}] status={environment.status.value} OK")

    environment = create_environment(map_id)
    if environment.status is not V8Status.RUNNING:
        problems.append("fresh environment is not running")
    problems.extend(check_leakage(environment))
    problems.extend(check_metrics(environment))
    observation = environment.observe()
    print("public fields:", sorted(observation))
    print("metrics:", json.dumps(environment.metrics(), ensure_ascii=False, sort_keys=True))
    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print(" -", problem)
        return 1
    print(f"{map_id}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
