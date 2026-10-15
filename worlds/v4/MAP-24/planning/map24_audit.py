"""Offline replay of MAP-24's hand-drawn route updates, time gates, and boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ITEMS = {"relic_C", "supply_case_D"}
EXPECTED_EDGES = {
    ("A", "B"): (1, "bridge_B"), ("B", "C"): (1, "bridge_B"),
    ("C", "D"): (1, "always_open"), ("D", "E"): (1, "tide_window"),
    ("E", "A"): (1, "always_open"), ("A", "F"): (2, "always_open"),
    ("F", "C"): (2, "always_open"),
}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class World:
    def __init__(self, spec: dict[str, Any], offset: int, *, tick: int = 0, node: str = "A",
                 carried: set[str] | None = None):
        self.spec = spec
        self.offset = offset
        self.tick = tick
        self.node = node
        self.bridge_collapsed = tick >= 8
        self.available = {"relic_C": "C", "supply_case_D": "D"}
        self.carried = set(carried or ())
        self.node_visits: dict[str, int] = {node: 1}
        self.notes: dict[str, dict[str, Any]] = {}
        self.latest_tide: dict[str, Any] | None = None
        self.bridge_probe: dict[str, Any] | None = None
        self.probe_used = False
        self.tide_measurements = 0
        self.failed_moves = 0
        self.stale_route_attempts = 0
        self.records: list[dict[str, Any]] = []
        self.terminal = False
        self.reason: str | None = None
        self.success = False
        if self.bridge_collapsed and self.node == "B":
            self._end(False, "STRANDED_ON_BRIDGE")

    def tide_open(self, tick: int) -> bool:
        return (tick + self.offset) % 4 in (0, 1)

    def connections(self, node: str) -> list[dict[str, Any]]:
        rows = []
        for (left, right), (duration, gate) in EXPECTED_EDGES.items():
            if node not in (left, right):
                continue
            neighbor = right if node == left else left
            if gate == "bridge_B":
                status = "COLLAPSED" if self.bridge_collapsed else "OPEN"
            elif gate == "tide_window":
                reading = self.latest_tide
                status = reading["status"] if reading and reading["node"] == node and reading["tick"] == self.tick else "UNKNOWN_TIDE"
            else:
                status = "OPEN"
            rows.append({"neighbor": neighbor, "duration_ticks": duration, "gate": gate, "status": status})
        return sorted(rows, key=lambda row: row["neighbor"])

    def observation(self) -> dict[str, Any]:
        here = sorted(item for item, location in self.available.items() if location == self.node)
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "locally_visible_connections_and_durations": self.connections(self.node),
            "visible_item_here": here,
            "carried_items": sorted(self.carried),
            "latest_local_tide_reading": self.latest_tide,
            "bridge_probe_result_if_obtained": self.bridge_probe,
            "agent_route_notes": [self.notes[key] for key in sorted(self.notes)],
            "terminal": self.terminal,
            "terminal_reason": self.reason,
        }

    def _end(self, success: bool, reason: str) -> None:
        self.terminal = True
        self.success = success
        self.reason = reason

    def _advance_one(self, arrival_node: str | None = None) -> None:
        self.tick += 1
        if arrival_node is not None:
            self.node = arrival_node
            self.node_visits[arrival_node] = self.node_visits.get(arrival_node, 0) + 1
        if self.tick == 8:
            self.bridge_collapsed = True
            if self.node == "B":
                self._end(False, "STRANDED_ON_BRIDGE")
                return
        if self.tick > 24:
            self._end(False, "DEADLINE_EXCEEDED")
            return
        if self.node == "A" and REQUIRED_ITEMS <= self.carried:
            self._end(True, "ALL_ITEMS_DELIVERED")

    def _advance(self, duration: int, *, arrival_node: str | None = None) -> None:
        for step in range(duration):
            final_arrival = arrival_node if step == duration - 1 else None
            self._advance_one(final_arrival)
            if self.terminal:
                break

    def _gate_open(self, node: str, target: str, departure_tick: int) -> tuple[bool, str]:
        pair = frozenset((node, target))
        if pair in (frozenset(("A", "B")), frozenset(("B", "C"))):
            return not self.bridge_collapsed, "bridge_B"
        if pair == frozenset(("D", "E")):
            return self.tide_open(departure_tick), "tide_window"
        return True, "always_open"

    def perform(self, action: dict[str, Any]) -> None:
        if self.terminal:
            raise AssertionError(f"Action continues after terminal state {self.reason}")
        before = self.observation()
        tick_before = self.tick
        kind = action["action"]
        result: dict[str, Any]
        if kind == "move":
            target = action["to"]
            edge = next(((duration, gate) for (a, b), (duration, gate) in EXPECTED_EDGES.items()
                         if {a, b} == {self.node, target}), None)
            if edge is None:
                raise AssertionError(f"Invalid non-neighbor move {self.node}->{target}")
            duration, gate = edge
            open_now, actual_gate = self._gate_open(self.node, target, self.tick)
            if actual_gate != gate:
                raise AssertionError("Route graph gate lookup disagrees with authored topology")
            if not open_now:
                self.failed_moves += 1
                if gate == "bridge_B":
                    self.stale_route_attempts += 1
                self._advance(1)
                result = {"result": "MOVE_FAILED_EDGE_CLOSED", "gate": gate, "remained_at": self.node, "duration_ticks": 1}
            else:
                start = self.node
                self._advance(duration, arrival_node=target)
                result = {"result": "MOVE_SUCCEEDED", "from": start, "to": target, "duration_ticks": duration}
        elif kind == "probe_bridge":
            if self.node != "B" or self.probe_used:
                raise AssertionError("Bridge probe must be used once at B")
            self.probe_used = True
            self.bridge_probe = {"condition": "PASSABLE_WITH_HAIRLINE_FRACTURES", "observed_at_tick": self.tick}
            result = dict(self.bridge_probe)
            self._advance(2)
        elif kind == "measure_tide":
            if self.node not in ("D", "E"):
                raise AssertionError("Tide may only be measured at D or E")
            self.tide_measurements += 1
            self._advance(1)
            status = "OPEN" if self.tide_open(self.tick) else "CLOSED"
            self.latest_tide = {"node": self.node, "status": status, "tick": self.tick}
            result = dict(self.latest_tide)
        elif kind == "record_route":
            snapshot = {"node": self.node, "recorded_at_tick": self.tick,
                        "connections": self.connections(self.node)}
            self.notes[self.node] = snapshot
            result = {"saved_node": self.node, "source_tick": self.tick,
                      "saved_connection_count": len(snapshot["connections"])}
            self._advance(1)
        elif kind == "take":
            item = action["item"]
            if item not in self.available or self.available[item] != self.node or item in self.carried:
                raise AssertionError(f"Cannot take {item} at {self.node}")
            del self.available[item]
            self.carried.add(item)
            result = {"result": "ITEM_COLLECTED", "item": item}
            self._advance(1)
        elif kind == "wait":
            result = {"result": "WAITED", "duration_ticks": 1}
            self._advance(1)
        else:
            raise AssertionError(f"Unknown MAP24 action {kind}")

        after = self.observation()
        public_action = {key: value for key, value in action.items() if key != "private_expectation"}
        self.records.append({"observation_before": before, "action": public_action,
                             "action_result": result, "observation_after": after,
                             "tick_before": tick_before, "tick_after": self.tick})


def actions_until_tide_open(world: World) -> None:
    while not world.terminal:
        world.perform({"action": "measure_tide"})
        if world.latest_tide and world.latest_tide["status"] == "OPEN":
            return
    raise AssertionError("Tide route terminated before receiving an open local reading")


def run_actions(spec: dict[str, Any], offset: int, actions: list[dict[str, Any]], *, tick: int = 0,
                node: str = "A", carried: set[str] | None = None) -> World:
    world = World(spec, offset, tick=tick, node=node, carried=carried)
    for action in actions:
        world.perform(action)
        if world.terminal:
            if action is not actions[-1]:
                raise AssertionError(f"Hand-authored route continues after {world.reason}")
    return world


def expand_failure(case: dict[str, Any], hand_routes: dict[str, Any]) -> list[dict[str, Any]]:
    actions = list(case.get("actions", case.get("prefix_actions", [])))
    if "prefix_route" in case:
        actions.extend(hand_routes[case["prefix_route"]]["actions"])
    repeat = case.get("repeat_after_prefix")
    if repeat:
        actions.extend([{"action": repeat["action"], **{key: value for key, value in repeat.items() if key not in {"action", "count"}}}
                        for _ in range(repeat["count"])])
    return actions


def contains_private_key(value: Any) -> bool:
    private = {"bridge_collapse_tick", "tide_phase_offset", "unseen_tide_phase", "future_event_log",
               "future_tide_windows", "globally_updated_map", "private_fixture_only"}
    if isinstance(value, dict):
        return any(str(key).lower() in private or contains_private_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_private_key(child) for child in value)
    return False


def main() -> None:
    spec = load_yaml(ROOT / "map_spec.yaml")
    if spec["runtime_verified"] is not False or spec["status"] not in ("DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"):
        raise AssertionError("Offline route audit must not claim runtime verification")
    loaded_edges = {}
    for edge in spec["topology"]["undirected_edges"]:
        pair = tuple(sorted((edge["a"], edge["b"])))
        loaded_edges[pair] = (edge["duration_ticks"], edge["gate"])
    expected_edges = {tuple(sorted(pair)): value for pair, value in EXPECTED_EDGES.items()}
    if loaded_edges != expected_edges:
        raise AssertionError("Hand-authored route graph disagrees with map_spec")
    if spec["topology"]["bridge_collapse"]["private_event_tick"] != 8 or spec["resources"]["deadline_tick_inclusive"] != 24:
        raise AssertionError("Bridge event/deadline differ from the MAP24 design")

    hand = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    seed = load_yaml(ROOT / "planning" / "private_seed_reference.yaml")
    if seed["seed"] != 0 or seed["bridge_collapse_tick"] != 8 or seed["tide_phase_offset"] != 0:
        raise AssertionError("Seed0 private fixture drifted")
    route_results = {}
    for name, route in hand["routes"].items():
        world = run_actions(spec, seed["tide_phase_offset"], route["actions"])
        expected = route["expected"]
        if (world.success is not expected["success"] or world.tick != expected["finish_tick"]
                or world.stale_route_attempts != expected["stale_route_attempts"]
                or world.failed_moves != expected["failed_moves"] or REQUIRED_ITEMS - world.carried):
            raise AssertionError(f"Hand route {name} differs from its manual tick/item ledger")
        if expected.get("measured_status") and (world.latest_tide is None or world.latest_tide["status"] != expected["measured_status"]):
            raise AssertionError("Hand-authored tide route did not act on its specified local reading")
        route_results[name] = {"success": world.success, "finish_tick": world.tick,
                               "failed_moves": world.failed_moves, "stale_route_attempts": world.stale_route_attempts,
                               "tide_measurements": world.tide_measurements,
                               "unique_nodes_visited": len(world.node_visits),
                               "repeated_node_visits": sum(count - 1 for count in world.node_visits.values()),
                               "carried_items": sorted(world.carried), "terminal_reason": world.reason}
        if name in ("bridge_probe_then_update", "stale_note_then_recover"):
            seen_index = next((index for index, row in enumerate(world.records)
                               if row["observation_after"]["current_node"] == "C"
                               and any(edge["neighbor"] == "B" and edge["status"] == "COLLAPSED"
                                       for edge in row["observation_after"]["locally_visible_connections_and_durations"])), None)
            if seen_index is None:
                raise AssertionError("The bridge update must become locally visible at C after the event")
            seen_tick = world.records[seen_index]["observation_after"]["current_tick"]
            if name == "bridge_probe_then_update" and seen_tick != expected["collapse_observed_at_tick"]:
                raise AssertionError("The bridge update was first observed at an unexpected tick")
            replan_index = next((index for index, row in enumerate(world.records[seen_index + 1:], start=seen_index + 1)
                                 if row["action"].get("action") == "move" and row["action"].get("to") == "F"), None)
            if replan_index is None:
                raise AssertionError("Updated plan must depart C along the permanent F bypass")
            route_results[name]["collapse_observed_tick"] = seen_tick
            route_results[name]["actions_until_F_departure"] = replan_index - seen_index
        if name == "stale_note_then_recover" and world.failed_moves != 1:
            raise AssertionError("Stale-note comparison must pay exactly one failed-move tick before recovery")

    phase_rows = []
    mountain_prefix = hand["routes"]["mountain_tide"]["actions"][:6]
    for offset in range(4):
        world = World(spec, offset)
        for action in mountain_prefix:
            world.perform(action)
        measurement_ticks = 0
        while not (world.latest_tide and world.latest_tide["status"] == "OPEN"):
            world.perform({"action": "measure_tide"})
            measurement_ticks += 1
            if measurement_ticks > 4:
                raise AssertionError("An open tide state must be found within one cycle")
        world.perform({"action": "move", "to": "E"})
        world.perform({"action": "move", "to": "A"})
        if not world.success or world.tick > 24:
            raise AssertionError(f"Measure-until-open policy failed at tide phase {offset}")
        phase_rows.append({"private_phase_offset_for_audit": offset, "measurements_until_open": measurement_ticks,
                           "finish_tick": world.tick, "success": world.success})

    cases = load_yaml(ROOT / "failure_traces" / "cases.yaml")
    failure_results = {}
    for case in cases["cases"]:
        actions = expand_failure(case, hand["routes"])
        world = run_actions(spec, seed["tide_phase_offset"], actions)
        expected = case["expected"]
        if (world.reason != expected["terminal_reason"] or world.node != expected["final_node"]
                or world.tick != expected["finish_tick"] or world.success is not expected["success"]
                or world.carried != set(expected["carried_items"])):
            raise AssertionError(f"Failure case {case['id']} final state differs: {world.observation()}")
        if case["id"] == "F02" and world.stale_route_attempts != expected["stale_route_attempts"]:
            raise AssertionError("F02 repeat count and bridge failure count disagree")
        if case["id"] == "F03" and world.tide_measurements != expected["tide_measurements"]:
            raise AssertionError("F03 repeated measurement count differs")
        failure_results[case["id"]] = {"terminal_reason": world.reason, "finish_tick": world.tick,
                                        "location": world.node, "failed_moves": world.failed_moves,
                                        "tide_measurements": world.tide_measurements}

    boundary_rows = {row["id"]: row for row in cases["boundary_cases"]}
    b01 = boundary_rows["B01"]
    world = run_actions(spec, 0, [b01["action"]], tick=b01["initial"]["tick"], node=b01["initial"]["node"])
    if world.reason != "STRANDED_ON_BRIDGE" or world.tick != b01["expected"]["arrival_tick"]:
        raise AssertionError("B01 tick-8 arrival at B must strand after the event")
    b02 = boundary_rows["B02"]
    world = run_actions(spec, 0, [b02["action"]], tick=b02["initial"]["tick"], node=b02["initial"]["node"])
    if world.node != "A" or world.tick != b02["expected"]["arrival_tick"] or world.terminal:
        raise AssertionError("B02 must arrive at A before bridge isolation is assessed")
    b03 = boundary_rows["B03"]["departures"]
    if [(row["tick"], "OPEN" if World(spec, 0).tide_open(row["tick"]) else "CLOSED") for row in b03] != [(row["tick"], row["expected"]) for row in b03]:
        raise AssertionError("B03 tide window endpoints do not match phase zero")
    b05 = boundary_rows["B05"]
    world = run_actions(spec, 0, [b05["action"]], tick=b05["initial"]["tick"], node=b05["initial"]["node"])
    if (world.node != b05["expected"]["node"] or world.tick != b05["expected"]["tick"]
            or world.failed_moves != b05["expected"]["failed_moves"]
            or world.records[0]["action_result"]["result"] != b05["expected"]["action_result"]):
        raise AssertionError("B05 closed-tide movement must stay in place and consume exactly one tick")
    b04 = boundary_rows["B04"]["states"]
    for row in b04:
        expected = row["expected"]
        world = run_actions(spec, 0, [row["action"]], tick=row["tick"], node=row["node"], carried=set(row["carried_items"]))
        if world.tick != expected["tick"] or world.success is not expected["success"]:
            raise AssertionError("B04 inclusive deadline boundary differs")
        if not expected["success"] and world.reason != expected["terminal_reason"]:
            raise AssertionError("B04 tick-25 state must fail by deadline")

    oracle_route = hand["routes"]["bridge_probe_then_update"]
    oracle_world = run_actions(spec, seed["tide_phase_offset"], oracle_route["actions"])
    fields = set(spec["public_observation_fields"])
    oracle_rows = []
    for row in oracle_world.records:
        for name in ("observation_before", "observation_after"):
            observation = row[name]
            if set(observation) != fields or contains_private_key(observation):
                raise AssertionError("Public MAP24 Oracle observation has a field mismatch or private key")
        if contains_private_key(row["action_result"]):
            raise AssertionError("Public MAP24 Oracle result contains evaluator-only keys")
        oracle_rows.append({key: row[key] for key in ("observation_before", "action", "action_result", "observation_after")})
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in oracle_rows), encoding="utf-8")

    reference = {"map_id": "MAP-24", "kind": "offline_hand_route_and_event_replay",
                 "seed0_private_fixture": seed, "manual_route_results": route_results,
                 "tide_phase_policy_results_private_for_audit": phase_rows,
                 "failure_results": failure_results, "boundary_results": {"B01": "STRANDED_ON_BRIDGE",
                    "B02": "SAFE_AT_A_AFTER_TICK_8", "B03": "OPEN_CLOSED_ENDPOINTS_MATCH",
                    "B04": "24_SUCCESS_25_FAIL", "B05": "CLOSED_TIDE_FAILED_MOVE_COSTS_ONE_TICK"},
                 "public_oracle_rows": len(oracle_rows), "runtime_verified": False}
    (ROOT / "planning" / "map24_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "MAP24_HAND_AUTHORED_ROUTES_AND_BOUNDARIES_REPLAYED", "runtime_verified": False,
                      "manual_routes": route_results, "tide_phase_policy": phase_rows,
                      "failures": failure_results, "oracle_rows": len(oracle_rows),
                      "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
