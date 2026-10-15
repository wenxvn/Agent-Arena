"""Offline replay of MAP-25's exact tool dependencies, EVA ordering, and oxygen ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FAULT = "FUSE_BANK_B_OPEN"
TOOLS = {"eva_suit", "diagnostic_unit", "wrench", "safety_tether"}
REQUIRED_REPAIR_TOOLS = {"diagnostic_unit", "wrench"}
INTERIOR = {frozenset(("H", "T")), frozenset(("T", "A"))}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class World:
    def __init__(self, spec: dict[str, Any], *, initial: dict[str, Any] | None = None):
        self.spec = spec
        state = {"node": "H", "tick": 0, "oxygen": 12, "pressure": "PRESSURIZED", "outer_closed": True, "inner_locked": False,
                 "suit": False, "diagnostic": False, "wrench": False, "tether": False,
                 "equipment_inspected": False, "array_inspected": False, "diagnosis": None,
                 "repaired": False, "available": {"eva_suit", "diagnostic_unit", "wrench"},
                 "tether_available": True, "terminal": False, "reason": None, "success": False,
                 "last_error": None, "executed_tool_errors": 0, "valid_tool_calls": 0,
                 "schema_errors": 0, "oxygen_used_outside": 0, "records": []}
        state["tool_call_attempts"] = 0
        if initial:
            for key, value in initial.items():
                target_key = {"current_node": "node", "oxygen_remaining": "oxygen", "airlock_pressure": "pressure",
                              "suit_worn": "suit", "tether_attached": "tether", "array_inspected": "array_inspected",
                              "array_diagnosed": "diagnosis", "diagnosis_code": "diagnosis",
                              "diagnostic_unit_carried": "diagnostic", "wrench_carried": "wrench",
                              "array_repaired": "repaired"}.get(key, key)
                state[target_key] = value
        self.state = state
        self.records = state["records"]

    @property
    def oxygen_used_outside(self) -> int:
        return self.state["oxygen_used_outside"]

    def observation(self) -> dict[str, Any]:
        s = self.state
        visible = []
        if s["node"] == "T":
            visible.extend(sorted(s["available"]))
        if s["node"] == "A" and s["tether_available"]:
            visible.append("safety_tether")
        return {
            "current_tick": s["tick"],
            "current_node": s["node"],
            "oxygen_remaining": s["oxygen"],
            "airlock_pressure": s["pressure"],
            "inner_hatch_locked": s["inner_locked"],
            "suit_worn": s["suit"],
            "tether_attached": s["tether"],
            "carried_tools": sorted(tool for tool, held in (("diagnostic_unit", s["diagnostic"]), ("wrench", s["wrench"])) if held),
            "visible_equipment_here": visible,
            "array_surface_symptom": "ARRAY_OUTPUT_ZERO" if s["array_inspected"] else None,
            "diagnosis_code_if_obtained": s["diagnosis"],
            "array_repaired": s["repaired"],
            "terminal": s["terminal"],
            "terminal_reason": s["reason"],
            "last_action_error_code": s["last_error"],
        }

    def _end(self, success: bool, reason: str) -> None:
        s = self.state
        s["terminal"] = True
        s["success"] = success
        s["reason"] = reason

    def _inside_tick(self) -> None:
        s = self.state
        s["tick"] += 1
        if s["node"] == "H":
            if s["repaired"]:
                self._end(True, "ALL_OBJECTIVES_COMPLETE")
            elif s["oxygen"] == 0:
                self._end(False, "OBJECTIVE_INCOMPLETE_AT_H")

    def _outside_tick(self, *, arrival_node: str | None = None) -> None:
        s = self.state
        s["tick"] += 1
        s["oxygen"] -= 1
        s["oxygen_used_outside"] += 1
        if arrival_node:
            s["node"] = arrival_node
        if s["node"] == "S" and s["oxygen"] == 0:
            self._end(False, "OXYGEN_DEPLETED")
        elif s["node"] == "H":
            if s["repaired"]:
                self._end(True, "ALL_OBJECTIVES_COMPLETE")
            elif s["oxygen"] == 0:
                self._end(False, "OBJECTIVE_INCOMPLETE_AT_H")

    def _outside_action(self, duration: int, *, arrival_node: str | None = None) -> None:
        for step in range(duration):
            self._outside_tick(arrival_node=arrival_node if step == duration - 1 else None)
            if self.state["terminal"]:
                break

    def _inside_action(self, duration: int = 1) -> None:
        for _ in range(duration):
            self._inside_tick()
            if self.state["terminal"]:
                break

    def _tool_error(self, code: str, *, duration: int = 0) -> dict[str, Any]:
        s = self.state
        s["last_error"] = code
        if duration:
            s["executed_tool_errors"] += 1
            if s["oxygen"] < duration:
                self._end(False, "OXYGEN_DEPLETED")
            else:
                self._outside_action(duration)
        elif code in {"INVALID_TOOL_ID", "INVALID_TARGET_ID", "INVALID_DIAGNOSIS_CODE"}:
            s["schema_errors"] += 1
        return {"error_code": code, "executed": duration > 0, "duration_ticks": duration,
                "oxygen_cost": duration}

    def perform(self, action: dict[str, Any]) -> None:
        s = self.state
        if s["terminal"]:
            raise AssertionError(f"Action continues after terminal {s['reason']}")
        before = self.observation()
        tick_before, oxygen_before = s["tick"], s["oxygen"]
        s["last_error"] = None
        kind = action["action"]
        if kind in {"equip", "diagnose", "repair"}:
            s["tool_call_attempts"] += 1
        result: dict[str, Any]
        if kind == "move":
            target = action["to"]
            pair = frozenset((s["node"], target))
            if (pair not in INTERIOR or s["node"] == "A" and s["pressure"] != "PRESSURIZED"
                    or pair == frozenset(("T", "A")) and s["inner_locked"]):
                result = self._tool_error("INVALID_ACTION")
            else:
                origin = s["node"]
                s["node"] = target
                result = {"result": "MOVED", "from": origin, "to": target, "duration_ticks": 1}
                self._inside_action()
        elif kind == "inspect":
            target = action["target"]
            if target == "equipment" and s["node"] == "T":
                s["equipment_inspected"] = True
                equipped = ({"eva_suit"} if s["suit"] else set()) | ({"diagnostic_unit"} if s["diagnostic"] else set()) | ({"wrench"} if s["wrench"] else set())
                result = {"result": "EQUIPMENT_INSPECTED", "equipment_ids": sorted(s["available"] | equipped)}
                self._inside_action()
            elif target == "array" and s["node"] == "S":
                s["array_inspected"] = True
                result = {"result": "ARRAY_OUTPUT_ZERO"}
                self._outside_action(1)
            else:
                result = self._tool_error("INVALID_INSPECT_TARGET")
        elif kind == "equip":
            item = action["item_id"]
            if item not in TOOLS:
                result = self._tool_error("INVALID_TOOL_ID")
            elif item == "safety_tether":
                if s["node"] != "A" or action.get("target_id") != "anchor" or not s["tether_available"]:
                    result = self._tool_error("EQUIPMENT_NOT_AVAILABLE_HERE")
                else:
                    s["tether"] = True
                    s["tether_available"] = False
                    s["valid_tool_calls"] += 1
                    result = {"result": "TETHER_ATTACHED", "anchor_id": "anchor"}
                    self._inside_action()
            elif s["node"] != "T" or item not in s["available"]:
                result = self._tool_error("EQUIPMENT_NOT_AVAILABLE_HERE")
            else:
                s["available"].remove(item)
                if item == "eva_suit":
                    s["suit"] = True
                elif item == "diagnostic_unit":
                    s["diagnostic"] = True
                elif item == "wrench":
                    s["wrench"] = True
                s["valid_tool_calls"] += 1
                result = {"result": "SUIT_EQUIPPED" if item == "eva_suit" else "TOOL_EQUIPPED", "item_id": item}
                self._inside_action()
        elif kind == "depressurize":
            if s["node"] != "A" or not s["suit"] or s["pressure"] != "PRESSURIZED" or not s["outer_closed"]:
                result = self._tool_error("AIRLOCK_PRECONDITION_FAILED")
            else:
                s["pressure"] = "VACUUM"
                s["inner_locked"] = True
                result = {"result": "AIRLOCK_DEPRESSURIZED"}
                self._inside_action()
        elif kind == "eva_exit":
            if not s["suit"]:
                self._end(False, "UNSUITED_EVA")
                result = {"error_code": "UNSUITED_EVA", "terminal": True}
            elif not s["tether"]:
                self._end(False, "UNSAFE_UNTETHERED_EVA")
                result = {"error_code": "UNSAFE_UNTETHERED_EVA", "terminal": True}
            elif s["node"] != "A" or s["pressure"] != "VACUUM" or not s["outer_closed"]:
                result = self._tool_error("AIRLOCK_NOT_DEPRESSURIZED")
            elif s["oxygen"] < 1:
                self._end(False, "OXYGEN_DEPLETED")
                result = {"error_code": "OXYGEN_DEPLETED", "terminal": True}
            else:
                s["outer_closed"] = False
                result = {"result": "EVA_STARTED", "oxygen_cost": 1}
                self._outside_action(1, arrival_node="S")
        elif kind == "diagnose":
            if s["node"] != "S":
                result = self._tool_error("WRONG_LOCATION")
            elif action["device_id"] not in TOOLS:
                result = self._tool_error("INVALID_TOOL_ID")
            elif action["device_id"] != "diagnostic_unit" or not s["diagnostic"]:
                result = self._tool_error("MISSING_REQUIRED_TOOL:diagnostic_unit", duration=1)
            elif not s["array_inspected"]:
                result = self._tool_error("INSPECTION_REQUIRED", duration=1)
            else:
                s["diagnosis"] = FAULT
                s["valid_tool_calls"] += 1
                result = {"result": "DIAGNOSIS_COMPLETE", "diagnosis_code": FAULT}
                self._outside_action(1)
        elif kind == "repair":
            tool_ids = action.get("tool_ids", [])
            diagnosis_code = action.get("diagnosis_code")
            if any(tool not in TOOLS for tool in tool_ids):
                result = self._tool_error("INVALID_TOOL_ID")
            elif action.get("target_id") != "array_fuse_B":
                result = self._tool_error("INVALID_TARGET_ID")
            elif diagnosis_code is not None and diagnosis_code != FAULT:
                result = self._tool_error("INVALID_DIAGNOSIS_CODE")
            elif s["node"] != "S":
                result = self._tool_error("WRONG_LOCATION")
            elif s["oxygen"] < 1:
                self._end(False, "OXYGEN_DEPLETED")
                result = {"error_code": "OXYGEN_DEPLETED", "executed": False, "oxygen_cost": 0}
            elif s["oxygen"] < 3:
                result = self._tool_error("OXYGEN_RESERVE_REQUIRED_FOR_RETURN")
            elif s["diagnosis"] is None:
                result = self._tool_error("DIAGNOSIS_REQUIRED", duration=2)
            elif "diagnostic_unit" not in tool_ids:
                result = self._tool_error("MISSING_REQUIRED_TOOL:diagnostic_unit", duration=2)
            elif "wrench" not in tool_ids:
                result = self._tool_error("MISSING_REQUIRED_TOOL:wrench", duration=2)
            elif set(tool_ids) != REQUIRED_REPAIR_TOOLS:
                result = self._tool_error("TOOL_SET_MISMATCH", duration=2)
            else:
                s["repaired"] = True
                s["valid_tool_calls"] += 1
                result = {"result": "ARRAY_REPAIRED", "target_id": "array_fuse_B", "duration_ticks": 2, "oxygen_cost": 2}
                self._outside_action(2)
        elif kind == "return_to_A":
            if s["node"] != "S" or not s["suit"] or not s["tether"]:
                result = self._tool_error("RETURN_PRECONDITION_FAILED")
            elif s["oxygen"] < 1:
                self._end(False, "OXYGEN_DEPLETED")
                result = {"error_code": "OXYGEN_DEPLETED", "executed": False, "oxygen_cost": 0}
            else:
                result = {"result": "RETURNED_TO_A", "oxygen_cost": 1}
                self._outside_action(1, arrival_node="A")
                s["outer_closed"] = True
        elif kind == "pressurize":
            if s["node"] != "A" or not s["outer_closed"] or s["pressure"] != "VACUUM":
                result = self._tool_error("PRESSURIZATION_PRECONDITION_FAILED")
            else:
                s["pressure"] = "PRESSURIZED"
                s["inner_locked"] = False
                result = {"result": "AIRLOCK_PRESSURIZED"}
                self._inside_action()
        else:
            result = self._tool_error("INVALID_ACTION")

        after = self.observation()
        self.records.append({"observation_before": before, "action": action, "action_result": result,
                             "observation_after": after, "tick_before": tick_before, "tick_after": s["tick"],
                             "oxygen_before": oxygen_before, "oxygen_after": s["oxygen"]})


def run(spec: dict[str, Any], actions: list[dict[str, Any]], initial: dict[str, Any] | None = None) -> World:
    world = World(spec, initial=initial)
    for index, action in enumerate(actions):
        world.perform(action)
        if world.state["terminal"] and index != len(actions) - 1:
            raise AssertionError(f"Actions continue after terminal reason {world.state['reason']}")
    return world


def expand_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    actions = list(case.get("actions", []))
    repeat = case.get("repeat")
    if repeat:
        actions.extend([{"action": repeat["action"], **{key: value for key, value in repeat.items() if key not in {"action", "count"}}}
                        for _ in range(repeat["count"])])
    return actions


def contains_private_key(value: Any) -> bool:
    private = {"latent_array_fault", "private_fixture_only", "evaluator_seed_fixture", "unperformed_action_outcomes"}
    if isinstance(value, dict):
        return any(str(key).lower() in private or contains_private_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_private_key(child) for child in value)
    return False


def main() -> None:
    spec = read_yaml(ROOT / "map_spec.yaml")
    if spec["runtime_verified"] is not False or spec["status"] not in ("DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"):
        raise AssertionError("MAP25 audit only establishes a pending-runtime design")
    if spec["topology"]["nodes"] != ["H", "T", "A", "S"] or spec["initial_state"]["oxygen_remaining"] != 12:
        raise AssertionError("Fixed MAP25 topology or initial oxygen changed")
    if (spec["array"]["fixed_seed0_diagnosis_code"] != FAULT
            or set(spec["array"]["repair_tool_ids_exact_set"]) != REQUIRED_REPAIR_TOOLS
            or spec["array"]["repair_duration_ticks"] != 2
            or spec["array"]["minimum_oxygen_before_repair"] != spec["array"]["repair_duration_ticks"] + 1
            or spec["airlock"]["return_to_A"]["oxygen_cost"] != 1):
        raise AssertionError("Exact tool pair or repair/return oxygen reserve differs from the design ledger")
    seed = read_yaml(ROOT / "planning" / "private_seed_reference.yaml")
    if seed["seed"] != 0 or seed["latent_array_fault"] != FAULT or seed["public_inspection_symptom"] != "ARRAY_OUTPUT_ZERO":
        raise AssertionError("Seed0 hidden-diagnosis fixture drifted")
    hand = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    success_results = {}
    for name, route in hand["routes"].items():
        world = run(spec, route["actions"])
        state, expected = world.state, route["expected"]
        if (state["success"] is not expected["success"] or state["tick"] != expected["finish_tick"]
                or state["oxygen"] != expected["oxygen_remaining"] or world.oxygen_used_outside != expected["oxygen_used"]
                or state["tool_call_attempts"] != expected["tool_call_attempts"]
                or state["valid_tool_calls"] != expected["valid_tool_calls"]
                or state["executed_tool_errors"] != expected["executed_tool_errors"]
                or state["repaired"] is not True or state["node"] != "H"):
            raise AssertionError(f"Successful manual EVA route {name} violates its oxygen or procedure ledger")
        success_results[name] = {"success": state["success"], "finish_tick": state["tick"],
                                 "oxygen_used": world.oxygen_used_outside, "oxygen_remaining": state["oxygen"],
                                 "tool_call_attempts": state["tool_call_attempts"], "valid_tool_calls": state["valid_tool_calls"],
                                 "typed_tool_call_validity_rate": state["valid_tool_calls"] / state["tool_call_attempts"],
                                 "executed_tool_errors": state["executed_tool_errors"],
                                 "terminal_reason": state["reason"]}

    failures = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    failure_results = {}
    for case in failures["cases"]:
        world = run(spec, expand_case(case))
        state, expected = world.state, case["expected"]
        if (state["reason"] != expected["terminal_reason"] or state["node"] != expected["final_node"]
                or state["oxygen"] != expected["oxygen_remaining"] or state["repaired"] is not expected["array_repaired"]
                or state["success"] is not expected["success"]
                or state["executed_tool_errors"] != expected.get("executed_tool_errors", 0)
                or state["tool_call_attempts"] != expected.get("tool_call_attempts", 0)
                or state["valid_tool_calls"] != expected.get("valid_tool_calls", 0)):
            raise AssertionError(f"Failure case {case['id']} final state differs from authored expectation")
        if case["id"] == "F01" and (state["suit"] or state["oxygen"] != 12):
            raise AssertionError("F01 must fail before suit/oxygen/EVA state changes")
        if case["id"] == "F02" and (not state["suit"] or state["tether"] or state["oxygen"] != 12):
            raise AssertionError("F02 must be suited and depressurized but untethered without oxygen loss")
        if case["id"] == "F03" and (state["diagnosis"] != FAULT or world.oxygen_used_outside != 12):
            raise AssertionError("F03 must expose diagnosis only after the diagnostic action and spend exactly the available oxygen")
        failure_results[case["id"]] = {"terminal_reason": state["reason"], "finish_tick": state["tick"],
                                        "node": state["node"], "oxygen_remaining": state["oxygen"],
                                        "oxygen_used_outside": world.oxygen_used_outside,
                                        "tool_call_attempts": state["tool_call_attempts"],
                                        "valid_tool_calls": state["valid_tool_calls"],
                                        "executed_tool_errors": state["executed_tool_errors"]}

    boundary_rows = {row["id"]: row for row in failures["boundary_cases"]}
    boundary_results = {}
    b01 = boundary_rows["B01"]
    world = run(spec, b01["actions"], b01["initial"])
    if world.state["reason"] != b01["expected"]["terminal_reason"] or world.state["oxygen"] != 0 or world.state["node"] != "H":
        raise AssertionError("B01 exact-one-oxygen return must reach safe H at zero")
    boundary_results["B01"] = world.state["reason"]
    b02 = boundary_rows["B02"]
    world = run(spec, b02["actions"], b02["initial"])
    if world.state["reason"] != b02["expected"]["terminal_reason"] or world.state["node"] != "S":
        raise AssertionError("B02 zero-oxygen EVA state must not move to A")
    boundary_results["B02"] = world.state["reason"]
    for case_id in ("B03", "B04"):
        row = boundary_rows[case_id]
        world = run(spec, [row["action"]], row["initial"])
        record = world.records[0]
        expected = row["expected"]
        if (record["action_result"].get("error_code") != expected["error_code"]
                or record["tick_after"] - record["tick_before"] != expected["tick_cost"]
                or record["oxygen_before"] - record["oxygen_after"] != expected["oxygen_cost"]
                or world.state["oxygen"] != expected["oxygen_remaining"]):
            raise AssertionError(f"{case_id} invalid-enum versus executed-tool cost boundary differs")
        boundary_results[case_id] = record["action_result"]["error_code"]
    for case_id in ("B05", "B06"):
        row = boundary_rows[case_id]
        world = run(spec, [row["action"]], row["initial"])
        record = world.records[0]
        expected = row["expected"]
        if (record["action_result"].get("error_code") != expected["error_code"]
                or record["tick_after"] - record["tick_before"] != expected["tick_cost"]
                or record["oxygen_before"] - record["oxygen_after"] != expected["oxygen_cost"]
                or world.state["oxygen"] != expected["oxygen_remaining"]):
            raise AssertionError(f"{case_id} invalid-enum or oxygen-reserve boundary differs")
        boundary_results[case_id] = record["action_result"]["error_code"]

    route = hand["routes"]["inspect_then_equip"]
    oracle_world = run(spec, route["actions"])
    fields = set(spec["public_observation_fields"])
    oracle_rows = []
    diagnosis_seen = False
    for row in oracle_world.records:
        diagnose_this_action = row["action"]["action"] == "diagnose" and row["action_result"].get("diagnosis_code") == FAULT
        for key in ("observation_before", "observation_after"):
            observation = row[key]
            if set(observation) != fields or contains_private_key(observation):
                raise AssertionError("MAP25 Oracle observation leaks private evaluator fields")
            allowed_after_diagnose = key == "observation_after" and diagnose_this_action
            if not diagnosis_seen and not allowed_after_diagnose and observation["diagnosis_code_if_obtained"] is not None:
                raise AssertionError("Diagnosis code was visible before diagnose action")
        if contains_private_key(row["action_result"]):
            raise AssertionError("MAP25 public Oracle action result contains evaluator-only key")
        if diagnose_this_action:
            diagnosis_seen = True
        oracle_rows.append({key: row[key] for key in ("observation_before", "action", "action_result", "observation_after")})
    if not diagnosis_seen or not oracle_world.state["success"]:
        raise AssertionError("Seed0 public Oracle must reveal diagnosis only at the typed diagnose result and complete the EVA")
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in oracle_rows), encoding="utf-8")

    reference = {"map_id": "MAP-25", "kind": "offline_hand_authored_tool_and_oxygen_replay",
                 "seed0_private_fixture": seed, "successful_routes": success_results,
                 "failure_routes": failure_results, "boundary_results": boundary_results,
                 "public_oracle_rows": len(oracle_rows), "runtime_verified": False}
    (ROOT / "planning" / "map25_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "MAP25_TYPED_EVA_FLOWS_AND_OXYGEN_BOUNDARIES_REPLAYED",
                      "runtime_verified": False, "successful_routes": success_results,
                      "failures": failure_results, "boundaries": boundary_results,
                      "oracle_rows": len(oracle_rows), "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
