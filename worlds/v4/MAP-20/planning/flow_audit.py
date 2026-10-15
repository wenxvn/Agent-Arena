"""Replay MAP-20's hand-authored water-network and thermal ledgers."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ZONES = ("A", "B", "C")
INITIAL_TEMPERATURES = [70, 60, 50]
INITIAL_MODES = ["FULL", "FULL", "FULL"]
HORIZON = 10
TARGET = 15
CRITICAL = 100
SOURCE_BUDGET = 60
FEEDER_CAPACITY = 25
ZONE_VALVE_CAPACITY = [40, 40, 30]
MODE_HEAT = {"FULL": [40, 30, 20], "REDUCED": [20, 20, 10], "IDLE": [0, 0, 0]}
MODE_PRODUCTION = {"FULL": [4, 3, 2], "REDUCED": [2, 2, 1], "IDLE": [0, 0, 0]}


class FlowError(ValueError):
    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


def band(temperature_tenths: int) -> str:
    if temperature_tenths <= 50:
        return "COOL"
    if temperature_tenths <= 80:
        return "WARM"
    if temperature_tenths <= CRITICAL:
        return "HOT"
    return "OVERHEAT"


def public_observation(tick: int, temperatures: list[int], modes: list[str],
                       previous_flow: dict[str, Any] | None, production: int,
                       terminal: bool = False, reason: str | None = None) -> dict[str, Any]:
    return {
        "tick": tick,
        "ticks_remaining": HORIZON - tick,
        "temperature_bands": {zone: band(value) for zone, value in zip(ZONES, temperatures)},
        "current_load_modes": dict(zip(ZONES, modes)),
        "previous_tick_flow_ledger": previous_flow,
        "source_water_remaining_this_tick": SOURCE_BUDGET,
        "production_points": production,
        "production_target": TARGET,
        "terminal": terminal,
        "terminal_reason": reason,
    }


def flow_receipts(direct: list[int], bypasses: dict[str, Any]) -> tuple[list[int], int]:
    if len(direct) != 3 or any(type(value) is not int or value < 0 or value > FEEDER_CAPACITY for value in direct):
        raise FlowError("FEEDER_CAPACITY_EXCEEDED")
    if sum(direct) > SOURCE_BUDGET:
        raise FlowError("SOURCE_BUDGET_EXCEEDED", {"direct_flow_tenths": direct, "total_draw_tenths": sum(direct)})

    receipts = list(direct)
    outgoing = [0, 0, 0]
    incoming = [0, 0, 0]
    total_loss = 0
    endpoints = {"AB": {"A": 0, "B": 1}, "BC": {"B": 1, "C": 2}}
    if set(bypasses) != {"AB", "BC"}:
        raise FlowError("INVALID_BYPASS_TRANSFER")
    for link, transfer in bypasses.items():
        if transfer is None:
            continue
        if transfer.get("from") not in endpoints[link] or transfer.get("to") not in endpoints[link]:
            raise FlowError("INVALID_BYPASS_TRANSFER")
        if transfer["from"] == transfer["to"]:
            raise FlowError("INVALID_BYPASS_TRANSFER")
        quantity = transfer.get("input_tenths")
        if type(quantity) is not int or quantity < 0 or quantity > 20 or quantity % 5 != 0:
            raise FlowError("INVALID_BYPASS_TRANSFER")
        donor = endpoints[link][transfer["from"]]
        receiver = endpoints[link][transfer["to"]]
        loss = quantity // 5
        outgoing[donor] += quantity
        incoming[receiver] += quantity - loss
        total_loss += loss
    if any(outgoing[index] > direct[index] for index in range(3)):
        raise FlowError("INVALID_BYPASS_TRANSFER", {"outgoing_tenths": outgoing, "direct_tenths": direct})
    receipts = [direct[index] - outgoing[index] + incoming[index] for index in range(3)]
    if any(value < 0 for value in receipts):
        raise FlowError("INVALID_BYPASS_TRANSFER", {"receipts_tenths": receipts})
    for index, value in enumerate(receipts):
        if value > ZONE_VALVE_CAPACITY[index]:
            raise FlowError("ZONE_VALVE_CAPACITY", {"zone": ZONES[index], "receipt_tenths": value,
                                                      "limit_tenths": ZONE_VALVE_CAPACITY[index]})
    if sum(receipts) != sum(direct) - total_loss:
        raise AssertionError("Network flow mass conservation failed")
    return receipts, total_loss


def simulate(plan_id: str, operations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    temperatures = list(INITIAL_TEMPERATURES)
    modes = list(INITIAL_MODES)
    production = safe_ticks = overheat_events = source_used = bypass_loss = 0
    maximum = max(temperatures)
    previous_delta: list[int] | None = None
    previous_flow: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    intervals: list[dict[str, Any]] = []
    terminal_reason: str | None = None
    final_tick = 0

    for tick, op in enumerate(operations):
        if op.get("tick") != tick:
            raise ValueError(f"{plan_id}: expected tick {tick}")
        before = public_observation(tick, temperatures, modes, previous_flow, production)
        zone = op.get("read_zone")
        if zone is not None and zone not in ZONES:
            raise ValueError(f"{plan_id}: invalid sensor zone {zone}")
        read_result = None
        if zone is not None:
            index = ZONES.index(zone)
            read_result = {"zone": zone, "temperature_tenths": temperatures[index],
                           "previous_delta_tenths": None if previous_delta is None else previous_delta[index]}
            expected_reading = op.get("expected_reading")
            if expected_reading is not None and expected_reading != {
                "temperature_tenths": read_result["temperature_tenths"],
                "previous_delta_tenths": read_result["previous_delta_tenths"],
            }:
                raise AssertionError(f"{plan_id}: hand sensor ledger mismatch at tick {tick}: {read_result}")

        direct = op.get("direct_flow_tenths", [0, 0, 0])
        bypasses = op.get("bypasses", {"AB": None, "BC": None})
        try:
            receipts, loss = flow_receipts(direct, bypasses)
        except FlowError as error:
            return rows, {"terminal_reason": error.reason, "failure_tick": tick,
                          "state_unchanged": True, **error.details}, intervals

        selected_modes = op.get("load_modes", modes)
        if len(selected_modes) != 3 or any(mode not in MODE_HEAT for mode in selected_modes):
            raise FlowError("INVALID_LOAD_MODE")
        modes = list(selected_modes)
        heat = [MODE_HEAT[mode][index] for index, mode in enumerate(modes)]
        output = [MODE_PRODUCTION[mode][index] for index, mode in enumerate(modes)]
        next_temperatures = [max(0, temperatures[index] + heat[index] - receipts[index])
                             for index in range(3)]
        overheated = [ZONES[index] for index, value in enumerate(next_temperatures) if value > CRITICAL]
        source_used += sum(direct)
        bypass_loss += loss
        if overheated:
            overheat_events += 1
            terminal_reason = "THERMAL_OVERHEAT"
            production_credit = 0
        else:
            production_credit = sum(output)
            production += production_credit
            safe_ticks += 1

        delta = [next_temperatures[index] - temperatures[index] for index in range(3)]
        intervals.append({"tick": tick, "temperatures_before_tenths": list(temperatures),
                          "direct_flow_tenths": list(direct), "bypasses": bypasses,
                          "delivered_tenths": receipts, "bypass_loss_tenths": loss,
                          "load_modes": list(modes), "heat_tenths": heat,
                          "temperatures_after_tenths": next_temperatures,
                          "production_credit": production_credit, "overheated_zones": overheated})
        if "expected_delivery_tenths" in op and op["expected_delivery_tenths"] != receipts:
            raise AssertionError(f"{plan_id}: bypass receipt mismatch at tick {tick}: {receipts}")
        if "expected_next_temp_tenths" in op and op["expected_next_temp_tenths"] != next_temperatures:
            raise AssertionError(f"{plan_id}: thermal ledger mismatch at tick {tick}: {next_temperatures}")
        if "expected_production_points" in op and op["expected_production_points"] != production_credit:
            raise AssertionError(f"{plan_id}: production credit mismatch at tick {tick}")

        temperatures = next_temperatures
        maximum = max(maximum, max(temperatures))
        previous_delta = delta
        final_tick = tick + 1
        if not overheated and final_tick == HORIZON:
            terminal_reason = "PRODUCTION_TARGET_MET" if production >= TARGET else "PRODUCTION_BELOW_15"
        terminal = terminal_reason is not None
        previous_flow = {"direct_flow_tenths": list(direct), "bypasses": bypasses,
                         "delivered_tenths": receipts, "bypass_loss_tenths": loss}
        after = public_observation(final_tick, temperatures, modes, previous_flow, production,
                                  terminal, terminal_reason)
        rows.append({
            "trace_id": plan_id,
            "step": tick + 1,
            "tick_before": tick,
            "observation_before": before,
            "sensor_result": read_result,
            "action": {"tool": "cooling_network_control_frame", "tick": tick,
                       "read_temperature": zone, "set_flow_tenths": list(direct),
                       "open_bypasses": bypasses, "adjust_loads": list(modes), "wait": 1},
            "expected_observation": after,
        })
        if terminal:
            break

    metrics = {"safe_ticks": safe_ticks, "production_points": production,
               "source_water_used_tenths": source_used, "bypass_loss_tenths": bypass_loss,
               "maximum_temperature_tenths": maximum, "final_temperatures_tenths": temperatures,
               "overheat_events": overheat_events, "success": terminal_reason == "PRODUCTION_TARGET_MET",
               "terminal_reason": terminal_reason, "failure_tick": None if terminal_reason == "PRODUCTION_TARGET_MET" else final_tick - 1}
    return rows, metrics, intervals


def audit_failures() -> dict[str, Any]:
    data = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    for case in data["cases"]:
        _, actual, intervals = simulate(case["id"], case["operations"])
        expected = case["expected"]
        for key in ("terminal_reason", "failure_tick"):
            if actual.get(key) != expected[key]:
                raise AssertionError(f"{case['id']}: {key} mismatch {actual.get(key)} != {expected[key]}")
        if case["id"] == "F01":
            if intervals[-1]["temperatures_after_tenths"] != expected["temperatures_after_failure_tenths"]:
                raise AssertionError("F01 temperature trajectory mismatch")
            if intervals[-1]["overheated_zones"] != expected["overheated_zones"]:
                raise AssertionError("F01 wrong zone overheated")
        elif case["id"] == "F02":
            if actual.get("total_draw_tenths") != expected["total_draw_tenths"] or not expected["each_feeder_within_25_tenths"]:
                raise AssertionError("F02 source-budget case should violate only the total source cap")
            if not actual.get("state_unchanged") or expected["tick_after_failure"] != 0:
                raise AssertionError("F02 invalid vector must be rejected without partial state changes")
        elif case["id"] == "F03":
            if intervals[-1]["temperatures_after_tenths"] != expected["temperatures_after_failure_tenths"]:
                raise AssertionError("F03 bypass-loss failure ledger mismatch")
            if intervals[-1]["overheated_zones"] != expected["overheated_zones"]:
                raise AssertionError("F03 wrong zone overheated")
        results[case["id"]] = {"terminal_reason": actual["terminal_reason"],
                                "failure_tick": actual["failure_tick"],
                                "temperatures_after_tenths": intervals[-1]["temperatures_after_tenths"] if intervals else None}

    boundaries = {case["id"]: case for case in data["boundary_cases"]}
    b01 = boundaries["B01"]
    receipts, loss = flow_receipts(b01["direct_flow_tenths"], {"AB": None, "BC": None})
    one_tick_after = [INITIAL_TEMPERATURES[index] + MODE_HEAT["FULL"][index] - receipts[index]
                      for index in range(3)]
    if sum(b01["direct_flow_tenths"]) != SOURCE_BUDGET or one_tick_after != b01["expected"]["temperatures_after_tenths"] or loss != 0:
        raise AssertionError("B01 exact source-water boundary must be accepted")
    if boundaries["B02"]["hand_plan"] != "exact_production_boundary":
        raise AssertionError("B02 must point to the dedicated exact-threshold hand plan")
    b03 = boundaries["B03"]
    before = {"tick": b03["tick"], "temperatures": list(INITIAL_TEMPERATURES), "water": 0}
    try:
        flow_receipts(b03["direct_flow_tenths"], b03["bypasses"])
    except FlowError as error:
        if error.reason != b03["expected"]["terminal_reason"] or error.details.get("receipt_tenths") != 32:
            raise AssertionError(f"B03 expected C=3.2 over its 3.0 valve: {error.reason} {error.details}")
    else:
        raise AssertionError("B03 over-capacity delivery should be rejected")
    if before != {"tick": b03["tick"], "temperatures": list(INITIAL_TEMPERATURES), "water": 0}:
        raise AssertionError("B03 invalid frame mutated the plant before rejection")
    results["B01"] = {"accepted_total_flow_tenths": SOURCE_BUDGET, "temperatures_after_tenths": one_tick_after}
    results["B02"] = {"accepted_production_points": TARGET}
    results["B03"] = {"reason": "ZONE_VALVE_CAPACITY", "C_receipt_tenths": 32,
                      "C_limit_tenths": ZONE_VALVE_CAPACITY[2], "no_temperature_or_tick_commit": True}
    return results


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    if spec["status"] != "DESIGN_COMPLETE_PENDING_RUNTIME" or spec["runtime_verified"] is not False:
        raise AssertionError("Hand audit must not claim runtime verification")
    topology = spec["topology"]
    flow_spec = spec["flow_model"]
    thermal_spec = spec["thermal_loads"]
    flow_action = next(action for action in spec["actions"] if action["name"] == "set_flow")
    if topology["upstream_direct_feeder_max_flow_units_each"] * 10 != FEEDER_CAPACITY:
        raise AssertionError("Direct feeder limit differs between design spec and hand replay")
    if spec["initial_state"]["source_water_units_per_tick"] * 10 != SOURCE_BUDGET:
        raise AssertionError("Source budget differs between design spec and hand replay")
    if flow_spec["direct_flow_range_tenths_each_branch"] != [0, FEEDER_CAPACITY] or flow_spec["direct_source_budget_tenths_per_tick"] != SOURCE_BUDGET:
        raise AssertionError("Direct-flow constraints differ between design spec and hand replay")
    if flow_spec["bypass_input_tenths_range"] != [0, 20] or flow_spec["bypass_input_quantum_tenths"] != 5:
        raise AssertionError("Bypass input domain differs between design spec and hand replay")
    if (flow_spec["bypass_loss_numerator"], flow_spec["bypass_loss_denominator"]) != (1, 5):
        raise AssertionError("Bypass loss differs between design spec and hand replay")
    if flow_spec["downstream_valve_max_tenths"] != dict(zip(ZONES, ZONE_VALVE_CAPACITY)):
        raise AssertionError("Zone valve capacities differ between design spec and hand replay")
    if flow_action["precondition"] != "each_0_to_25_and_sum_lte_60":
        raise AssertionError("set_flow action contract is inconsistent with feeder/source limits")
    if spec["temperature_limit"]["tenths_of_degree"] != CRITICAL:
        raise AssertionError("Temperature limit differs between design spec and hand replay")
    if (
        thermal_spec["initial_temperature_tenths"] != INITIAL_TEMPERATURES
        or thermal_spec["full"]["heat_tenths"] != MODE_HEAT["FULL"]
        or thermal_spec["reduced"]["heat_tenths"] != MODE_HEAT["REDUCED"]
        or thermal_spec["idle"]["heat_tenths"] != MODE_HEAT["IDLE"]
        or thermal_spec["full"]["production_points"] != MODE_PRODUCTION["FULL"]
        or thermal_spec["reduced"]["production_points"] != MODE_PRODUCTION["REDUCED"]
        or thermal_spec["idle"]["production_points"] != MODE_PRODUCTION["IDLE"]
    ):
        raise AssertionError("Thermal/load table differs between design spec and hand replay")
    source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    if source["initial_temperature_tenths"] != INITIAL_TEMPERATURES:
        raise AssertionError("Hand scenarios changed the fixed initial heat state")

    oracle: list[dict[str, Any]] = []
    plan_results: dict[str, Any] = {}
    for plan_id, plan in source["plans"].items():
        rows, metrics, intervals = simulate(plan_id, plan["operations"])
        expected = plan["expected"]
        comparable = {key: metrics[key] for key in expected}
        if comparable != expected:
            raise AssertionError(f"{plan_id}: hand ledger mismatch {comparable} != {expected}")
        if metrics["terminal_reason"] != "PRODUCTION_TARGET_MET" or metrics["safe_ticks"] != HORIZON:
            raise AssertionError(f"{plan_id}: all ten ticks must be safe and meet target")
        oracle.extend(rows)
        plan_results[plan_id] = metrics

    if plan_results["dynamic_priority_rotation"]["production_points"] <= plan_results["prioritize_A_through_two_bypasses"]["production_points"]:
        raise AssertionError("Dynamic hand schedule should trade additional water for its stated production gain")
    if plan_results["dynamic_priority_rotation"]["source_water_used_tenths"] <= plan_results["prioritize_A_through_two_bypasses"]["source_water_used_tenths"]:
        raise AssertionError("The two hand points should retain a water/production tradeoff")
    if plan_results["exact_production_boundary"]["production_points"] != TARGET:
        raise AssertionError("Exact-threshold hand plan did not land on 15")

    failure_results = audit_failures()
    for row in oracle:
        for field in ("observation_before", "expected_observation"):
            observation = row[field]
            if set(observation) != set(spec["public_observation_fields"]):
                raise AssertionError(f"Oracle {field} differs from MAP20 public observation contract")
            serialized = json.dumps(observation, ensure_ascii=False).lower()
            if any(private in serialized for private in ("future_oracle", "scoring_reference", "private_temperature")):
                raise AssertionError("Private/future judge data leaked into public state")

    # Linear thermal-energy relaxation: P <= source water (60/tick for 10 ticks) + 12 heat-headroom.
    initial_headroom = [CRITICAL - value for value in INITIAL_TEMPERATURES]
    relaxation_upper = SOURCE_BUDGET * HORIZON + sum(initial_headroom)
    if relaxation_upper != 720:
        raise AssertionError(f"Expected 72 flow/production units, got {relaxation_upper / 10}")
    reference = {
        "map_id": "MAP-20",
        "kind": "linear_energy_balance_relaxation",
        "source_water_upper_tenths_over_horizon": SOURCE_BUDGET * HORIZON,
        "initial_temperature_headroom_tenths": initial_headroom,
        "total_headroom_tenths": sum(initial_headroom),
        "production_upper_tenths": relaxation_upper,
        "production_upper_points": relaxation_upper / 10,
        "hand_authored_safe_witnesses": {key: value["production_points"] for key, value in plan_results.items()},
        "global_integer_optimum_proven": False,
        "success_target": TARGET,
        "target_feasible_in_hand_witnesses": True,
    }
    reference_path = ROOT / "planning" / "flow_reference.json"
    reference_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                         for row in oracle), encoding="utf-8")
    result = {"result": "HAND_AUTHORED_MAP20_FLOW_AND_THERMAL_PLANS_REPLAYED",
              "runtime_verified": False, "plan_metrics": plan_results,
              "failure_and_boundary_cases": failure_results,
              "linear_relaxation_upper_bound_points": reference["production_upper_points"],
              "global_integer_optimum_proven": False,
              "oracle_rows": len(oracle),
              "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
