"""Replay the six reviewed V4 map oracles against the isolated runtime.

This is an offline, deterministic validator. It never creates a Provider and
never passes source traces, private state, or reference routes to an Agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.worlds.scenario_v4 import ScenarioV4Action, create_environment

ROOT = Path(__file__).resolve().parents[1]
WORLD_ROOT = ROOT / "worlds" / "v4"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _assert_subset(actual: Any, expected: Any, path: str = "$") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError(f"{path}: expected object, got {type(actual).__name__}")
        for key, value in expected.items():
            if key not in actual:
                raise AssertionError(f"{path}.{key}: expected key is missing")
            _assert_subset(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(f"{path}: list length/type mismatch")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            _assert_subset(left, right, f"{path}[{index}]")
        return
    if actual != expected:
        raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")


def _action(payload: dict[str, Any]) -> ScenarioV4Action:
    return ScenarioV4Action.model_validate(payload, strict=True)


def _replay_map08() -> int:
    rows = _rows(WORLD_ROOT / "MAP-08" / "oracle_trace.jsonl")
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        seed = row.get("seed_id", 0 if row["trace_id"] == "y_then_x_B" else None)
        if seed is None:
            raise AssertionError(f"MAP-08 trace row has no registered seed: {row['trace_id']}")
        groups.setdefault((row["trace_id"], seed), []).append(row)
    for (trace_id, seed), trace in groups.items():
        env = create_environment(
            "MAP-08", seed=seed, condition_id="no_hypothesis_table", step_limit=100
        )
        for row in trace:
            before = env.observe().model_dump(mode="json")
            assert before["location"] == row["location"], (trace_id, row["step"])
            assert before["current_tick"] == row["tick_before"], (trace_id, row["step"])
            env.step(_action(row["action"]))
            expected: dict[str, Any] = {}
            for item in row["expected"].split(";"):
                key, value = item.split("=", 1)
                expected[key] = value
            after = env.observe().model_dump(mode="json")
            translations = {
                "tick": "current_tick",
                "location": "location",
                "core_water": "current_core_water",
                "sealant_count": "sealant_count",
            }
            for key, value in expected.items():
                if key in translations:
                    actual = after[translations[key]]
                    if isinstance(actual, bool):
                        value = value.lower() == "true"
                    elif isinstance(actual, int):
                        value = int(value)
                    elif isinstance(actual, float):
                        value = float(value)
                    assert actual == value, (trace_id, row["step"], key, value, actual)
                elif key == "leak_sealed":
                    assert env.judge_state()["sealed"] is (value.lower() == "true")
                elif key == "terminal":
                    assert env.status.value == value, (trace_id, row["step"])
        assert env.is_success, (trace_id, seed, env.judge_state())
    return len(groups)


def _replay_map16() -> int:
    rows = _rows(WORLD_ROOT / "MAP-16" / "oracle_trace.jsonl")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["trace_id"], []).append(row)
    for trace_id, trace in groups.items():
        env = create_environment("MAP-16", seed=0, condition_id="react")
        for row in trace:
            env.step(_action(row["action"]))
            _assert_subset(
                env.observe().model_dump(mode="json"),
                row["expected_observation"],
                f"{trace_id}.step{row['step']}",
            )
        assert env.is_success, (trace_id, env.judge_state())
        assert env.metrics()["makespan_ticks"] == 6, trace_id
        assert env.metrics()["optimality_gap"] == 0, trace_id
    return len(groups)


def _replay_map18() -> int:
    rows = _rows(WORLD_ROOT / "MAP-18" / "oracle_trace.jsonl")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["trace_id"], []).append(row)
    for trace_id, trace in groups.items():
        condition = "alert_on" if trace_id == "alert_proactive_detour" else "alert_off"
        env = create_environment("MAP-18", seed=0, condition_id=condition)
        for row in trace:
            _assert_subset(
                env.observe().model_dump(mode="json"),
                row["observation_before"],
                f"{trace_id}.before{row['step']}",
            )
            env.step(_action(row["action"]))
            _assert_subset(
                env.observe().model_dump(mode="json"),
                row["expected_observation"],
                f"{trace_id}.after{row['step']}",
            )
        assert env.is_success, (trace_id, env.judge_state())
        assert env.metrics()["delivered_passengers"] >= 13, trace_id
    return len(groups)


_REVERSE_BEARING = {
    "N": "S",
    "NE": "SW",
    "E": "W",
    "SE": "NW",
    "S": "N",
    "SW": "NE",
    "W": "E",
    "NW": "SE",
}


def _replay_map22() -> int:
    hand_trace = json.loads(
        (WORLD_ROOT / "MAP-22" / "planning" / "hand_traces.json").read_text(encoding="utf-8")
    )
    route = hand_trace["strategies"]["external_graph_memory_euler_tour"]
    env = create_environment("MAP-22", seed=0, condition_id="history5_graph_memory")
    # The archived Oracle preloads all 27 graph facts in its first Observation,
    # including edges the Agent has not traversed yet. Insert a legal A-C-A
    # loop before the authored Euler route so every memory fact is grounded
    # before terminal return; the archived design remains untouched.
    directions = ["SE", "NW", *route["directions"]]
    recorded_nodes: set[str] = set()
    recorded_edges: set[frozenset[str]] = set()
    for index, bearing in enumerate(directions, start=1):
        env.step(_action({"tool": "observe_signpost"}))
        observation = env.observe()
        assert observation.inspected_current_sign_detail is not None
        origin_sign = observation.inspected_current_sign_detail["sign_id"]
        if origin_sign not in recorded_nodes:
            env.step(
                _action(
                    {
                        "tool": "write_memory",
                        "facts": [
                            {
                                "fact_type": "node_page",
                                "sign_id": origin_sign,
                                "exit_bearings": list(observation.visible_exit_bearings),
                            }
                        ],
                    }
                )
            )
            recorded_nodes.add(origin_sign)
        env.step(_action({"tool": "move", "bearing": bearing}))
        if env.is_terminal:
            break
        env.step(_action({"tool": "observe_signpost"}))
        arrival = env.observe()
        assert arrival.inspected_current_sign_detail is not None
        destination_sign = arrival.inspected_current_sign_detail["sign_id"]
        facts = []
        if destination_sign not in recorded_nodes:
            facts.append(
                {
                    "fact_type": "node_page",
                    "sign_id": destination_sign,
                    "exit_bearings": list(arrival.visible_exit_bearings),
                }
            )
            recorded_nodes.add(destination_sign)
        edge = frozenset((origin_sign, destination_sign))
        if edge not in recorded_edges:
            facts.append(
                {
                    "fact_type": "traversed_edge_page",
                    "from_sign_id": origin_sign,
                    "departure_bearing": bearing,
                    "to_sign_id": destination_sign,
                    "arrival_reverse_bearing": _REVERSE_BEARING[bearing],
                }
            )
            recorded_edges.add(edge)
        if facts:
            env.step(_action({"tool": "write_memory", "facts": facts}))
        assert env.tick == index, (index, env.tick)
    metrics = env.metrics()
    _assert_subset(
        metrics,
        {
            "movement_steps": 20,
            "unique_nodes_seen": 12,
            "unique_edges_traversed": 15,
            "repeated_node_visits": 9,
            "repeated_edge_traversals": 5,
            "memory_facts_written": 27,
            "shortest_route_gap": 12,
            "return_success": True,
        },
        "MAP-22.metrics",
    )
    assert env.is_success, env.judge_state()
    return 1


def _replay_hand_actions(map_id: str, condition_id: str) -> int:
    data = json.loads(
        (WORLD_ROOT / map_id / "planning" / "hand_traces.json").read_text(encoding="utf-8")
    )
    for route in data["routes"]:
        env = create_environment(map_id, seed=data.get("seed", 0), condition_id=condition_id)
        for action in route["actions"]:
            payload = {"tool": action["name"]}
            payload.update({key: value for key, value in action.items() if key != "name"})
            if action["name"] == "interview":
                payload.setdefault("shown_evidence_ids", [])
                payload.setdefault("shown_casebook_entry_ids", [])
            env.step(_action(payload))
        expected = route["expected"]
        actual = env.metrics()
        if map_id == "MAP-26":
            expected = {
                {
                    "tick": "finish_tick",
                    "uninstalled_spares_remaining": "spare_units_remaining",
                    "wrong_replacements": "wrong_replacement_attempts",
                }.get(key, key): value
                for key, value in expected.items()
            }
        _assert_subset(actual, expected, f"{map_id}.{route['id']}.metrics")
        assert env.is_success, (map_id, route["id"], env.judge_state())
    return len(data["routes"])


def main() -> None:
    counts = {
        "MAP-08": _replay_map08(),
        "MAP-16": _replay_map16(),
        "MAP-18": _replay_map18(),
        "MAP-22": _replay_map22(),
        "MAP-26": _replay_hand_actions("MAP-26", "recovery_full"),
        "MAP-30": _replay_hand_actions("MAP-30", "history5_casebook"),
    }
    print("V4 oracle replay passed:", json.dumps(counts, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
