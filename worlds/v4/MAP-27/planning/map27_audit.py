"""Hand-authored offline replay audit for MAP-27; not an environment or agent test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
EDGES = {
    frozenset(("B", "S")): {"ticks": 1, "battery": 1, "oxygen": 1},
    frozenset(("S", "R")): {"ticks": 2, "battery": 2, "oxygen": 2},
    frozenset(("R", "P")): {"ticks": 2, "battery": 2, "oxygen": 2},
    frozenset(("P", "E")): {"ticks": 4, "battery": 4, "oxygen": 4},
    frozenset(("S", "E")): {"ticks": 1, "battery": 1, "oxygen": 1},
}
ITEM_SLOTS = {"sample_container": 1, "medical_kit": 1, "relay_repair_kit": 1}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def min_energy_to_base(node: str) -> int:
    costs = {node: 0}
    todo = [(0, node)]
    while todo:
        todo.sort(reverse=True)
        cost, here = todo.pop()
        if cost != costs[here]:
            continue
        if here == "B":
            return cost
        for edge, data in EDGES.items():
            if here not in edge:
                continue
            there = next(n for n in edge if n != here)
            candidate = cost + data["battery"]
            if candidate < costs.get(there, 10**9):
                costs[there] = candidate
                todo.append((candidate, there))
    raise AssertionError(f"base is disconnected from {node}")


class JointReplay:
    def __init__(self):
        self.tick = 0
        self.node = "B"
        self.battery = 14
        self.oxygen = 18
        self.cargo: list[str] = []
        self.sample_container_at_b = 1
        self.medical_kits_at_s = 1
        self.relay_kits_at_s = 1
        self.charge_cells_at_s = 1
        self.relay = "OFFLINE"
        self.sample = "UNSAMPLED"
        self.survivor = "UNSUPPORTED"
        self.crew_alive = True
        self.terminal_reason: str | None = None
        self.latest_result = "INITIAL"
        self.cargo_peak_slots = 0
        self.cargo_capacity_errors = 0
        self.kit_failures = 0
        self.error_codes: list[str] = []
        self.charge_cells_used = 0
        self.battery_used_from_driving = 0
        self.oxygen_used_from_driving = 0
        self.records: list[dict[str, Any]] = []
        self._record("INITIAL")

    def adjacent(self, node: str) -> bool:
        return frozenset((self.node, node)) in EDGES

    def observation(self) -> dict[str, Any]:
        neighbors = []
        for edge, data in EDGES.items():
            if self.node in edge:
                neighbor = next(n for n in edge if n != self.node)
                neighbors.append({"node": neighbor, **data})
        cargo_rows = [{"item_id": item, "slots": ITEM_SLOTS[item]} for item in self.cargo]
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "local_drive_edges_with_costs": sorted(neighbors, key=lambda row: row["node"]),
            "battery_remaining": self.battery,
            "oxygen_remaining": self.oxygen,
            "cargo_ids_and_slots": cargo_rows,
            "supply_remaining_here": {
                "sample_container": self.sample_container_at_b if self.node == "B" else None,
                "medical_kit": self.medical_kits_at_s if self.node == "S" else None,
                "relay_repair_kit": self.relay_kits_at_s if self.node == "S" else None,
            },
            "charger_cells_remaining": self.charge_cells_at_s if self.node == "S" else None,
            "relay_state": self.relay,
            "sample_state": self.sample,
            "survivor_state": self.survivor,
            "crew_alive": self.crew_alive,
            "last_action_result": self.latest_result,
            "terminal": self.terminal_reason is not None,
            "terminal_reason": self.terminal_reason,
        }

    def _record(self, result: str) -> None:
        self.records.append({"result": result, "observation": self.observation()})

    def step(self, action: dict[str, Any]) -> None:
        if self.terminal_reason is not None:
            raise AssertionError("hand trace continues after terminal state")
        name = action["name"]
        result = ""
        duration = 0
        if name == "load":
            item = action["item_id"]
            if item not in ITEM_SLOTS:
                raise AssertionError(f"invalid hand-authored cargo ID {item}")
            stock_ok = ((item == "sample_container" and self.node == "B" and self.sample_container_at_b > 0)
                        or (item == "medical_kit" and self.node == "S" and self.medical_kits_at_s > 0)
                        or (item == "relay_repair_kit" and self.node == "S" and self.relay_kits_at_s > 0))
            if not stock_ok:
                result = "ITEM_NOT_AVAILABLE_HERE"
                self.error_codes.append(result)
            elif sum(ITEM_SLOTS[cargo_item] for cargo_item in self.cargo) + ITEM_SLOTS[item] > 2:
                result = "CARGO_CAPACITY_EXCEEDED"
                self.cargo_capacity_errors += 1
                self.error_codes.append(result)
            else:
                self.cargo.append(item)
                if item == "sample_container":
                    self.sample_container_at_b -= 1
                elif item == "medical_kit":
                    self.medical_kits_at_s -= 1
                else:
                    self.relay_kits_at_s -= 1
                duration = 1
                result = f"LOAD_SUCCEEDED:{item}"
                self._update_cargo_peak()
        elif name == "drive":
            target = action["to"]
            assert target in {"B", "S", "R", "P", "E"} and self.adjacent(target)
            edge = EDGES[frozenset((self.node, target))]
            if self.battery < edge["battery"]:
                result = "BATTERY_INSUFFICIENT"
                self.error_codes.append(result)
                self.terminal_reason = "VEHICLE_STRANDED"
            elif self.oxygen <= edge["oxygen"]:
                self.battery -= edge["battery"]
                self.oxygen -= edge["oxygen"]
                self.battery_used_from_driving += edge["battery"]
                self.oxygen_used_from_driving += edge["oxygen"]
                self.tick += edge["ticks"]
                self.node = target
                self.crew_alive = False
                result = "CREW_OXYGEN_DEPLETED"
                self.terminal_reason = "CREW_OXYGEN_DEPLETED"
            else:
                self.battery -= edge["battery"]
                self.oxygen -= edge["oxygen"]
                self.battery_used_from_driving += edge["battery"]
                self.oxygen_used_from_driving += edge["oxygen"]
                self.tick += edge["ticks"]
                self.node = target
                duration = 0
                result = "DRIVE_SUCCEEDED"
                if self.node != "B" and min_energy_to_base(self.node) > self.battery:
                    result = "VEHICLE_STRANDED"
                    self.terminal_reason = "VEHICLE_STRANDED"
        elif name == "charge":
            if self.node != "S":
                result = "INVALID_LOCATION"
                self.error_codes.append(result)
            elif self.charge_cells_at_s == 0:
                result = "CHARGER_EMPTY"
                self.error_codes.append(result)
            elif self.battery >= 14:
                result = "BATTERY_ALREADY_FULL"
                self.error_codes.append(result)
            else:
                self.battery += min(4, 14 - self.battery)
                self.charge_cells_at_s -= 1
                self.charge_cells_used += 1
                duration = 2
                result = "CHARGED"
        elif name == "repair_relay":
            if self.node != "R":
                result = "INVALID_LOCATION"
                self.kit_failures += 1
                self.error_codes.append(result)
            elif self.relay == "ONLINE":
                result = "RELAY_ALREADY_ONLINE"
                self.error_codes.append(result)
            elif "relay_repair_kit" not in self.cargo:
                result = "RELAY_TOOL_REQUIRED"
                self.kit_failures += 1
                self.error_codes.append(result)
            else:
                self.cargo.remove("relay_repair_kit")
                self.relay = "ONLINE"
                duration = 2
                result = "RELAY_REPAIRED"
        elif name == "sample":
            if self.node != "P" or "sample_container" not in self.cargo or self.sample != "UNSAMPLED":
                result = "SAMPLE_CONTAINER_REQUIRED"
                self.kit_failures += 1
                self.error_codes.append(result)
            else:
                self.sample = "SEALED"
                duration = 1
                result = "SAMPLE_SEALED"
        elif name == "rescue":
            mode = action["mode"]
            if mode == "field_stabilize":
                if self.node != "E":
                    result = "INVALID_LOCATION"
                    self.kit_failures += 1
                    self.error_codes.append(result)
                elif "medical_kit" not in self.cargo:
                    result = "MEDICAL_KIT_REQUIRED"
                    self.kit_failures += 1
                    self.error_codes.append(result)
                elif self.survivor != "UNSUPPORTED":
                    result = "CASUALTY_ALREADY_STABILIZED"
                    self.error_codes.append(result)
                else:
                    self.cargo.remove("medical_kit")
                    self.survivor = "STABILIZED"
                    duration = 1
                    result = "CASUALTY_STABILIZED"
            elif mode == "remote_evacuation":
                if self.node not in {"R", "E"}:
                    result = "INVALID_LOCATION"
                    self.kit_failures += 1
                    self.error_codes.append(result)
                elif self.relay != "ONLINE":
                    result = "RELAY_OFFLINE"
                    self.kit_failures += 1
                    self.error_codes.append(result)
                elif self.survivor != "STABILIZED":
                    result = "CASUALTY_NOT_STABILIZED"
                    self.kit_failures += 1
                    self.error_codes.append(result)
                else:
                    self.survivor = "RESCUED"
                    duration = 1
                    result = "REMOTE_EVACUATION_COMPLETE"
            else:
                raise AssertionError(f"unknown rescue mode {mode}")
        elif name == "submit":
            assert self.node == "B"
            if self.sample == "SEALED" and self.survivor == "RESCUED" and self.relay == "ONLINE" and self.crew_alive and self.oxygen > 0:
                result = "ALL_OBJECTIVES_COMPLETE"
                self.terminal_reason = "ALL_OBJECTIVES_COMPLETE"
            else:
                result = "OBJECTIVES_INCOMPLETE_AT_BASE"
                self.terminal_reason = "OBJECTIVES_INCOMPLETE_AT_BASE"
        else:
            raise AssertionError(f"unknown hand-authored action {name}")

        self.tick += duration
        if sum(ITEM_SLOTS[cargo_item] for cargo_item in self.cargo) > 2:
            raise AssertionError("cargo exceeds two slots")
        self.latest_result = result
        self._record(result)

    def _update_cargo_peak(self) -> None:
        slots = sum(ITEM_SLOTS[item] for item in self.cargo)
        self.cargo_peak_slots = max(self.cargo_peak_slots, slots)

    def run(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            self.step(action)

    def metrics(self) -> dict[str, Any]:
        complete_count = sum((self.sample == "SEALED", self.survivor == "RESCUED", self.relay == "ONLINE", self.crew_alive and self.oxygen > 0))
        return {
            "finish_tick": self.tick,
            "terminal_reason": self.terminal_reason,
            "success": self.terminal_reason == "ALL_OBJECTIVES_COMPLETE",
            "location": self.node,
            "battery_remaining": self.battery,
            "battery_consumed": self.battery_used_from_driving,
            "oxygen_remaining": self.oxygen,
            "oxygen_consumed": self.oxygen_used_from_driving,
            "charge_cells_used": self.charge_cells_used,
            "charge_cells_remaining": self.charge_cells_at_s,
            "cargo_peak_slots": self.cargo_peak_slots,
            "cargo_capacity_errors": self.cargo_capacity_errors,
            "tools_or_kit_failures": self.kit_failures,
            "action_errors": list(self.error_codes),
            "relay_state": self.relay,
            "sample_state": self.sample,
            "survivor_state": self.survivor,
            "crew_alive": self.crew_alive,
            "objective_coverage": f"{complete_count}/4",
            "action_rows": len(self.records) - 1,
        }


def oracle_bytes(records: list[dict[str, Any]]) -> bytes:
    rows = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return ("\n".join(rows) + "\n").encode("utf-8")


def audit() -> dict[str, Any]:
    spec = read_yaml(ROOT / "map_spec.yaml")
    hand = read_json(ROOT / "planning" / "hand_traces.json")
    cases = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    replay_spec = read_yaml(ROOT / "planning" / "seed_replay.yaml")
    assert spec["status"] in {"DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"}
    assert spec["initial_state"]["vehicle_battery"] == 14 and spec["initial_state"]["crew_oxygen"] == 18
    assert spec["cargo"]["capacity_slots"] == 2 and spec["charging"]["units_at_start"] == 1
    assert set(cases["boundaries"]) == {"B01_charge_cap_and_one_use", "B02_cargo_exact_capacity",
                                        "B03_short_versus_remote_road", "B04_exact_return_energy",
                                        "B05_positive_oxygen_at_submit", "B06_seed0_replay"}
    assert EDGES[frozenset(("P", "E"))] == {"ticks": 4, "battery": 4, "oxygen": 4}
    assert EDGES[frozenset(("S", "E"))] == {"ticks": 1, "battery": 1, "oxygen": 1}

    routes: dict[str, Any] = {}
    first_oracle: bytes | None = None
    for route in hand["routes"]:
        replay = JointReplay()
        replay.run(route["actions"])
        metrics = replay.metrics()
        expected = route["expected"]
        for field in ("finish_tick", "battery_remaining", "oxygen_remaining", "charge_cells_used", "cargo_peak_slots", "relay_state", "sample_state", "survivor_state", "success"):
            assert metrics[field] == expected[field], (route["id"], field, metrics, expected)
        assert metrics["success"] and metrics["terminal_reason"] == "ALL_OBJECTIVES_COMPLETE"
        assert metrics["cargo_peak_slots"] <= 2 and metrics["oxygen_remaining"] > 0
        routes[route["id"]] = metrics
        if route["id"] == "relay_first_remote_road":
            first_oracle = oracle_bytes(replay.records)

    assert first_oracle is not None
    second = JointReplay()
    second.run(hand["routes"][0]["actions"])
    assert oracle_bytes(second.records) == first_oracle
    (ROOT / "oracle_trace.jsonl").write_bytes(first_oracle)

    failures: dict[str, Any] = {}
    for case_id, case in cases["cases"].items():
        replay = JointReplay()
        replay.run(case["actions"])
        metrics = replay.metrics()
        expected = case["expected"]
        for field, expected_field in (("terminal_reason", "terminal_reason"), ("finish_tick", "finish_tick"),
                                      ("battery_remaining", "battery_remaining"), ("oxygen_remaining", "oxygen_remaining"),
                                      ("location", "node"), ("relay_state", "relay_state"),
                                      ("sample_state", "sample_state"), ("survivor_state", "survivor_state")):
            if expected_field in expected:
                assert metrics[field] == expected[expected_field], (case_id, field, metrics, expected)
        if "action_errors" in expected:
            assert metrics["action_errors"] == expected["action_errors"], (case_id, metrics["action_errors"])
        if "minimum_energy_to_B" in expected:
            assert min_energy_to_base(metrics["location"]) == expected["minimum_energy_to_B"]
        failures[case_id] = metrics

    # Charge cap/one-use boundary: at S with 13, the single cell restores only one unit; next call cannot add power.
    charger = JointReplay()
    charger.node = "S"
    charger.battery = 13
    charger.step({"name": "charge"})
    assert (charger.battery, charger.charge_cells_at_s, charger.tick) == (14, 0, 2)
    before = (charger.battery, charger.tick)
    charger.step({"name": "charge"})
    assert charger.records[-1]["result"] == "CHARGER_EMPTY" and (charger.battery, charger.tick) == before

    # Cargo capacity is an actual rejected transition that leaves the existing load untouched.
    cargo = JointReplay()
    cargo.run([{"name": "load", "item_id": "sample_container"}, {"name": "drive", "to": "S"},
               {"name": "load", "item_id": "medical_kit"}])
    before_cargo, before_tick = list(cargo.cargo), cargo.tick
    cargo.step({"name": "load", "item_id": "relay_repair_kit"})
    assert cargo.records[-1]["result"] == "CARGO_CAPACITY_EXCEEDED"
    assert cargo.cargo == before_cargo and cargo.tick == before_tick

    # Exact return energy and oxygen-zero boundaries.
    assert min_energy_to_base("E") == 2
    stranded = JointReplay()
    stranded.node, stranded.battery = "E", 1
    assert min_energy_to_base(stranded.node) > stranded.battery
    exact_return = JointReplay()
    exact_return.node, exact_return.battery, exact_return.oxygen = "E", 2, 5
    exact_return.step({"name": "drive", "to": "S"})
    exact_return.step({"name": "drive", "to": "B"})
    assert exact_return.node == "B" and exact_return.battery == 0 and exact_return.oxygen == 3
    oxygen = JointReplay()
    oxygen.oxygen = 1
    oxygen.step({"name": "drive", "to": "S"})
    assert oxygen.terminal_reason == "CREW_OXYGEN_DEPLETED" and not oxygen.crew_alive

    # Replay declaration and public trace are deterministic, with no seed or future outcome in observations.
    assert replay_spec["seed"] == hand["seed"] == 0
    assert routes["relay_first_remote_road"]["finish_tick"] == replay_spec["expected_same_seed_invariants"]["first_route_tick"]
    assert routes["stabilize_first_short_road"]["finish_tick"] == replay_spec["expected_same_seed_invariants"]["second_route_tick"]
    text = first_oracle.decode("utf-8")
    assert "seed" not in text.lower() and "future" not in text.lower()
    assert len(first_oracle.splitlines()) == 18
    reference = {
        "map_id": "MAP-27",
        "result": "MAP27_TWO_ORDERED_JOINT_OPERATION_PLANS_REPLAYED",
        "runtime_verified": False,
        "routes": routes,
        "failures": failures,
        "boundaries": {
            "charge_first": {"battery": 14, "cells": 0, "tick_cost": 2},
            "charge_second": "CHARGER_EMPTY_NO_COST",
            "cargo_overflow": "CARGO_CAPACITY_EXCEEDED_NO_MUTATION",
            "minimum_energy_E_to_B": 2,
            "E_battery_1": "VEHICLE_STRANDED",
            "E_battery_2_exact_return": {"node": exact_return.node, "battery": exact_return.battery, "oxygen": exact_return.oxygen},
            "oxygen_zero": oxygen.terminal_reason,
        },
        "oracle_rows": len(first_oracle.splitlines()),
        "oracle_sha256": hashlib.sha256(first_oracle).hexdigest().upper(),
    }
    (ROOT / "planning" / "map27_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return reference


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
