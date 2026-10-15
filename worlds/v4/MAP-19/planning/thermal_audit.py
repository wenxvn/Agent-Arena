"""Replay MAP-19's hand-written thermal plans, sensor reads, forecasts, and failures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ZONE_NAMES = ("A", "B", "C")
INITIAL_TEMPERATURES = [6, 5, 4]
INITIAL_LOADS = [2, 2, 2]
INITIAL_COOLING = [0, 0, 0]
HORIZON = 12
TARGET = 20
COOLING_DELAY = 2
CRITICAL = 10
COOLING_ZONE_MAX = 2
COOLING_BUDGET = 4


def band(temperature: int) -> str:
    if temperature <= 4:
        return "COOL"
    if temperature <= 7:
        return "WARM"
    if temperature == 8:
        return "RISING"
    if temperature <= CRITICAL:
        return "NEAR_LIMIT"
    return "OVERHEAT"


def public_observation(tick: int, temperatures: list[int], active: list[int], loads: list[int],
                       pending: list[dict[str, Any]], production: int,
                       terminal: bool = False, reason: str | None = None) -> dict[str, Any]:
    return {
        "tick": tick,
        "ticks_remaining": HORIZON - tick,
        "temperature_bands": {zone: band(value) for zone, value in zip(ZONE_NAMES, temperatures)},
        "active_cooling": dict(zip(ZONE_NAMES, active)),
        "current_load_levels": dict(zip(ZONE_NAMES, loads)),
        "pending_cooling_commands": [
            {"effective_tick": row["effective_tick"], "vector": list(row["vector"])}
            for row in sorted(pending, key=lambda item: item["effective_tick"])
        ],
        "production_points": production,
        "production_target": TARGET,
        "terminal": terminal,
        "terminal_reason": reason,
    }


def validate_vector(name: str, values: list[int], low: int, high: int) -> None:
    if len(values) != 3 or any(type(value) is not int or value < low or value > high for value in values):
        raise ValueError(f"invalid {name} vector: {values}")


def enqueue_cooling(pending: list[dict[str, Any]], tick: int, vector: list[int]) -> list[dict[str, Any]]:
    validate_vector("cooling", vector, 0, COOLING_ZONE_MAX)
    if sum(vector) > COOLING_BUDGET:
        raise ValueError("VALVE_BUDGET_EXCEEDED")
    return [*pending, {"effective_tick": tick + COOLING_DELAY, "vector": list(vector)}]


def simulate(plan_id: str, operations: list[dict[str, Any]], *, expect_success: bool) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    temperatures = list(INITIAL_TEMPERATURES)
    active = list(INITIAL_COOLING)
    loads = list(INITIAL_LOADS)
    pending: list[dict[str, Any]] = []
    previous_delta: list[int] | None = None
    production = safe_ticks = overheat_events = 0
    maximum = max(temperatures)
    forecast_absolute_errors: list[int] = []
    row_results: list[dict[str, Any]] = []
    interval_states: list[dict[str, Any]] = []
    terminal_reason: str | None = None
    final_tick = 0

    def mature(tick: int) -> None:
        nonlocal active, pending
        due = [command for command in pending if command["effective_tick"] == tick]
        if len(due) > 1:
            raise ValueError(f"{plan_id}: more than one full-vector actuator command matures at tick {tick}")
        if due:
            active = list(due[0]["vector"])
            pending = [command for command in pending if command["effective_tick"] != tick]

    for tick, source_row in enumerate(operations):
        if source_row.get("tick") != tick or source_row.get("wait", 1) != 1:
            raise ValueError(f"{plan_id}: expected one sequential wait at tick {tick}")
        mature(tick)
        before = public_observation(tick, temperatures, active, loads, pending, production)
        read_zone = source_row.get("read_zone")
        if read_zone not in ZONE_NAMES:
            raise ValueError(f"{plan_id}: exactly one valid zone read is required at tick {tick}")
        read_index = ZONE_NAMES.index(read_zone)
        read_result = {"zone": read_zone, "temperature": temperatures[read_index],
                       "previous_delta": None if previous_delta is None else previous_delta[read_index]}
        if "expected_reading" in source_row and source_row["expected_reading"] != {
            "temperature": read_result["temperature"], "previous_delta": read_result["previous_delta"]
        }:
            raise AssertionError(f"{plan_id}: sensor ledger mismatch at tick {tick}: {read_result}")

        if "set_cooling" in source_row:
            vector = source_row["set_cooling"]
            try:
                pending = enqueue_cooling(pending, tick, vector)
            except ValueError as error:
                raise ValueError(f"{plan_id}: {error} at tick {tick}: {vector}") from error
        if "set_loads" in source_row:
            validate_vector(f"{plan_id} loads", source_row["set_loads"], 0, 2)
            loads = list(source_row["set_loads"])

        forecast = source_row["forecast_next"]
        validate_vector(f"{plan_id} forecast", forecast, 0, 99)
        next_temperatures = [max(0, temperature + load - cooling)
                             for temperature, load, cooling in zip(temperatures, loads, active)]
        forecast_absolute_errors.extend(abs(expected - actual)
                                        for expected, actual in zip(forecast, next_temperatures))
        overheated = [zone for zone, value in zip(ZONE_NAMES, next_temperatures) if value > CRITICAL]
        if overheated:
            overheat_events += 1
            terminal_reason = "THERMAL_RUNAWAY"
        else:
            production += sum(loads)
            safe_ticks += 1

        delta = [new - old for new, old in zip(next_temperatures, temperatures)]
        interval_states.append({"tick": tick, "temperatures_before": list(temperatures),
                               "active_cooling": list(active), "loads": list(loads),
                               "temperatures_after": list(next_temperatures),
                               "pending_cooling_commands": [dict(row) for row in pending],
                               "production_credited": 0 if overheated else sum(loads),
                               "overheated_zones": overheated})
        temperatures = next_temperatures
        maximum = max(maximum, max(temperatures))
        previous_delta = delta
        final_tick = tick + 1
        if not overheated and final_tick == HORIZON:
            terminal_reason = "PRODUCTION_TARGET_MET" if production >= TARGET else "PRODUCTION_BELOW_20"
        terminal = terminal_reason is not None

        # A command due next tick does not mature if this interval terminates the map.
        if not terminal:
            mature(final_tick)
        after = public_observation(final_tick, temperatures, active, loads, pending, production,
                                  terminal, terminal_reason)
        action = {
            "tool": "thermal_control_frame",
            "tick": tick,
            "read_temperature": read_zone,
            "set_cooling": source_row.get("set_cooling"),
            "adjust_loads": source_row.get("set_loads"),
            "forecast_next": list(forecast),
            "wait": 1,
        }
        row_results.append({"trace_id": plan_id, "step": tick + 1, "tick_before": tick,
                            "observation_before": before, "sensor_result": read_result,
                            "action": action, "expected_observation": after})
        if terminal:
            break

    expected_reason = "PRODUCTION_TARGET_MET" if expect_success else "THERMAL_RUNAWAY"
    if terminal_reason != expected_reason:
        raise AssertionError(f"{plan_id}: expected terminal {expected_reason}, got {terminal_reason}")
    if expect_success and final_tick != HORIZON:
        raise AssertionError(f"{plan_id}: successful plan stopped at tick {final_tick}")
    mae = sum(forecast_absolute_errors) / len(forecast_absolute_errors)
    metrics = {
        "safe_ticks": safe_ticks,
        "production_points": production,
        "overheat_events": overheat_events,
        "maximum_temperature": maximum,
        "final_temperatures": temperatures,
        "mean_absolute_prediction_error": mae,
        "success": terminal_reason == "PRODUCTION_TARGET_MET",
        "terminal_reason": terminal_reason,
        "failure_tick": None if expect_success else final_tick - 1,
        "forecast_values_checked": len(forecast_absolute_errors),
    }
    return row_results, metrics, interval_states


def audit_failure_cases(source: dict[str, Any]) -> dict[str, Any]:
    cases = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    for case in cases["cases"]:
        _, metrics, intervals = simulate(case["id"], case["operations"], expect_success=False)
        expected = case["expected"]
        failed = intervals[-1]
        checks = {
            "terminal_reason": metrics["terminal_reason"],
            "failure_tick": metrics["failure_tick"],
            "resulting_temperatures": failed["temperatures_after"],
        }
        if checks["terminal_reason"] != expected["terminal_reason"] or checks["failure_tick"] != expected["failure_tick"]:
            raise AssertionError(f"{case['id']}: failure terminal mismatch {checks}")
        if checks["resulting_temperatures"] != expected["resulting_temperatures"]:
            raise AssertionError(f"{case['id']}: temperature ledger mismatch {checks['resulting_temperatures']}")
        if failed["overheated_zones"] != expected["overheated_zones"]:
            raise AssertionError(f"{case['id']}: wrong zone overheated: {failed['overheated_zones']}")
        if case["id"] == "F01":
            issue_tick = next(row["tick"] for row in case["operations"] if "set_cooling" in row)
            pending_due = issue_tick + COOLING_DELAY
            if pending_due != expected["pending_vector_effective_tick"] or pending_due <= metrics["failure_tick"]:
                raise AssertionError("F01 cooling command should still be pending at thermal failure")
            if failed["pending_cooling_commands"] != [{"effective_tick": pending_due,
                                                        "vector": case["operations"][issue_tick]["set_cooling"]}]:
                raise AssertionError("F01 future valve command incorrectly matured after terminal failure")
        elif case["id"] == "F02":
            if failed["active_cooling"] != case["operations"][0]["set_cooling"]:
                raise AssertionError("F02 must fail despite the under-sized valve vector becoming active")
        elif case["id"] == "F03":
            if sum(case["operations"][0]["set_cooling"]) > COOLING_BUDGET:
                raise AssertionError("F03 cooling vector should be legal")
        results[case["id"]] = checks

    boundary = {row["id"]: row for row in cases["boundary_cases"]}
    if boundary["B01"]["resulting_temperature_A"] != CRITICAL or boundary["B01"]["expected"] != "safe":
        raise AssertionError("B01 must establish equality at ten as safe")
    if boundary["B02"]["resulting_production_at_tick_12"] != TARGET or boundary["B02"]["expected"] != "success":
        raise AssertionError("B02 must establish production equality as success")
    if boundary["B03"]["cooling_vector"] != [2, 1, 2] or sum(boundary["B03"]["cooling_vector"]) <= COOLING_BUDGET:
        raise AssertionError("B03 must exceed the cooling budget by exactly one unit")
    if boundary["B03"]["expected"] != {"reason": "VALVE_BUDGET_EXCEEDED", "no_pending_command": True,
                                          "no_tick_advance": True}:
        raise AssertionError("B03 must reject its full valve vector atomically")

    # An invalid vector is rejected before any actuator, temperature, or clock mutation.
    before = {"temperatures": list(INITIAL_TEMPERATURES), "active": list(INITIAL_COOLING),
              "pending": [], "tick": 0}
    after = {"temperatures": list(before["temperatures"]), "active": list(before["active"]),
             "pending": list(before["pending"]), "tick": before["tick"]}
    try:
        after["pending"] = enqueue_cooling(after["pending"], 0, boundary["B03"]["cooling_vector"])
        after["tick"] += 1
    except ValueError as error:
        if str(error) != "VALVE_BUDGET_EXCEEDED":
            raise
    results["B03"] = {"reason": "VALVE_BUDGET_EXCEEDED", "state_unchanged": after == before}
    if not results["B03"]["state_unchanged"]:
        raise AssertionError("B03 over-budget validation mutated actuator or time state")
    return {"cases": results, "boundaries": ["B01", "B02", "B03"]}


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    if spec["status"] != "DESIGN_COMPLETE_PENDING_RUNTIME" or spec["runtime_verified"] is not False:
        raise AssertionError("Design replay must not claim runtime verification")
    source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    if source["initial_temperatures_private_until_read"] != INITIAL_TEMPERATURES:
        raise AssertionError("Hand traces changed the fixed seed-0 initial thermal state")

    oracle_rows: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    interval_states: dict[str, list[dict[str, Any]]] = {}
    for plan_id, plan in source["plans"].items():
        rows, result, states = simulate(plan_id, plan["operations"], expect_success=True)
        expected = plan["expected"]
        comparable = {key: result[key] for key in expected}
        if comparable != expected:
            raise AssertionError(f"{plan_id}: manual metric ledger mismatch: {comparable} != {expected}")
        if result["mean_absolute_prediction_error"] != 0.0:
            raise AssertionError(f"{plan_id}: hand-written forecast is not exact")
        oracle_rows.extend(rows)
        metrics[plan_id] = result
        interval_states[plan_id] = states

    # Check the two mechanism edges against actual row-by-row state, not only declared expected values.
    hot = interval_states["pre_cool_hot_zone"]
    if hot[1]["temperatures_after"][0] != 10 or hot[1]["overheated_zones"]:
        raise AssertionError("A=10 at tick 1 must remain safe")
    if hot[2]["active_cooling"] != [2, 1, 1] or hot[2]["temperatures_after"][0] != 10:
        raise AssertionError("Tick-0 valve vector must first affect the tick-2 thermal transition")
    if metrics["exact_production_boundary"]["production_points"] != TARGET:
        raise AssertionError("The exact production boundary must be achieved")

    failure_summary = audit_failure_cases(source)
    public_fields = set(spec["public_observation_fields"])
    for row in oracle_rows:
        for field in ("observation_before", "expected_observation"):
            observation = row[field]
            if set(observation) != public_fields:
                raise AssertionError(f"Oracle {field} does not match the public observation schema")
            if any("exact_temperature" in key.lower() or "future_temperature" in key.lower()
                   for key in observation):
                raise AssertionError("Exact or future temperatures were placed in the normal Observation")
            if any(value == ["oracle"] for value in observation.values() if isinstance(value, list)):
                raise AssertionError("Oracle content leaked into public state")

    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                         for row in oracle_rows), encoding="utf-8")
    output = {
        "result": "HAND_AUTHORED_MAP19_THERMAL_PLANS_REPLAYED",
        "runtime_verified": False,
        "plan_metrics": metrics,
        "failure_cases": failure_summary,
        "oracle_rows": len(oracle_rows),
        "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
