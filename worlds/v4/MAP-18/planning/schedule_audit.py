"""Replay MAP-18's hand-authored disruption schedules and emit public-state Oracle rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
HORIZON = 12
FAULT_START = 5
FAULT_REOPEN = 10
FAULT_EDGE = frozenset(("R2", "R3"))
STATION_CAPACITY = 2
ADJACENCY = {
    "R1": {"R2"}, "R2": {"R1", "R3", "B2"}, "R3": {"R2"},
    "B1": {"B2"}, "B2": {"B1", "B3", "R2"}, "B3": {"B2", "G2"},
    "G1": {"G2"}, "G2": {"G1", "G3", "B3"}, "G3": {"G2"},
}
HAND_PATHS = {
    "TASK_R1_R2": [("release", "R2")],
    "TASK_R2_R3": [("release", "R3")],
    "TASK_R3_R2": [("release", "R2")],
    "TASK_B1_B3": [("release", "B2"), ("release", "B3")],
    "TASK_G1_G3": [("release", "G2"), ("release", "G3")],
    "TASK_R2_G2": [("detour", "B2"), ("release", "B3"), ("release", "G2")],
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def public_observation(tick: int, positions: dict[str, str], states: dict[str, str],
                       delivered: int, canceled: int, locks: dict[str, dict[str, Any]],
                       alert_enabled: bool, terminal: bool = False,
                       terminal_reason: str | None = None) -> dict[str, Any]:
    closed = ["R2_R3"] if FAULT_START <= tick < FAULT_REOPEN else []
    alert = None
    if tick == 4 and alert_enabled:
        alert = {
            "id": "NETWORK_DISRUPTION_WATCH",
            "message": "A mainline section may close next tick; the segment and duration are unspecified.",
        }
    return {
        "tick": tick,
        "ticks_remaining": HORIZON - tick,
        "topology": {
            "red_nodes": ["R1", "R2", "R3"],
            "blue_nodes": ["B1", "B2", "B3"],
            "green_nodes": ["G1", "G2", "G3"],
            "interchange_segments": ["R2_B2", "B3_G2"],
            "segment_capacity_per_tick": 1,
            "station_train_berth_capacity": STATION_CAPACITY,
        },
        "train_positions": dict(positions),
        "station_berths": dict(sorted(Counter(positions.values()).items())),
        "task_passenger_counts": {task_id: 3 for task_id in sorted(states)},
        "delivered_tasks": sorted(task_id for task_id, state in states.items() if state == "delivered"),
        "canceled_tasks": sorted(task_id for task_id, state in states.items() if state == "canceled"),
        "delivered_passengers": delivered,
        "canceled_passengers": canceled,
        "closed_segments": closed,
        "current_train_locks": {train: lock["remaining"] for train, lock in sorted(locks.items())},
        "published_dispatch_windows": {
            "TASK_R1_R2": {"release_tick": 5, "arrival_tick": 6},
            "TASK_R2_R3": {"release_tick": 5, "arrival_tick": 6},
            "TASK_R3_R2": {"release_tick": 6, "arrival_tick": 7},
            "TASK_B1_B3": {"release_ticks": [0, 1], "arrival_tick": 2},
            "TASK_G1_G3": {"release_ticks": [0, 1], "arrival_tick": 2},
            "TASK_R2_G2": {"detour_release_tick": 4, "arrival_tick": 7},
        },
        "alert_message_if_any": alert,
        "recovery_status": "not_started" if tick < FAULT_START else (
            "section_closed" if tick < FAULT_REOPEN else "reopened"),
        "terminal": terminal,
        "terminal_reason": terminal_reason,
    }


def replay(plan_id: str, plan: dict[str, Any], source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    positions = dict(source["initial_trains"])
    tasks = source["tasks"]
    states = {task_id: "pending" for task_id in tasks}
    progress = {task_id: 0 for task_id in tasks}
    task_for_train = {task["train"]: task_id for task_id, task in tasks.items()}
    headings = {"T_R1": "R2", "T_R2": "R3", "T_R3": "R2", "T_B": "B2", "T_G": "G2", "T_X": "B2"}
    locks: dict[str, dict[str, Any]] = {}
    delivered = canceled = delay = last_delivery = 0
    fault_resolution: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    initial_counts = Counter(positions.values())
    if any(count > STATION_CAPACITY for count in initial_counts.values()):
        raise ValueError(f"{plan_id}: invalid initial berth occupancy {initial_counts}")

    for tick, tick_row in enumerate(plan["operations"]):
        if tick_row.get("tick") != tick:
            raise ValueError(f"{plan_id}: expected tick {tick}, got {tick_row.get('tick')}")
        before = public_observation(tick, positions, states, delivered, canceled, locks,
                                    plan["alert_mode"] == "enabled")
        operations = {train: op for train, op in tick_row.items() if train != "tick"}
        accepted_moves: dict[str, tuple[str, str]] = {}
        closed_results: dict[str, str] = {}
        cancel_now: list[str] = []
        start_turnbacks: dict[str, str] = {}

        for train, op_data in operations.items():
            if train not in positions:
                raise ValueError(f"{plan_id}: unknown train {train}")
            if train in locks:
                raise ValueError(f"{plan_id}: locked train {train} received an action at tick {tick}")
            op = op_data["op"]
            task_id = task_for_train[train]
            task_state = states[task_id]
            current = positions[train]

            if op in {"release", "detour"}:
                destination = op_data["to"]
                if destination not in ADJACENCY[current]:
                    raise ValueError(f"{plan_id}: illegal link {current}-{destination} at tick {tick}")
                if task_state == "pending":
                    route_index = progress[task_id]
                    if route_index >= len(HAND_PATHS[task_id]) or (op, destination) != HAND_PATHS[task_id][route_index]:
                        raise ValueError(f"{plan_id}: route deviates from hand-authored task path at tick {tick}: {train} {op} {destination}")
                elif task_state == "canceled" and train == "T_R2":
                    if op != "release" or destination != headings[train]:
                        raise ValueError(f"{plan_id}: empty T_R2 may only reposition toward {headings[train]}")
                else:
                    raise ValueError(f"{plan_id}: completed train {train} moved at tick {tick}")
                if frozenset((current, destination)) == FAULT_EDGE and FAULT_START <= tick < FAULT_REOPEN:
                    closed_results[train] = "TRACK_CLOSED"
                    continue
                accepted_moves[train] = (current, destination)
            elif op == "cancel_service":
                cancel_id = op_data["task_id"]
                if cancel_id != task_id or task_state != "pending" or current != tasks[cancel_id]["from"]:
                    raise ValueError(f"{plan_id}: invalid cancellation {cancel_id} by {train} at tick {tick}")
                cancel_now.append(cancel_id)
            elif op == "turnback":
                if task_state != "canceled" or train != "T_R2" or op_data.get("duration_ticks") != 2:
                    raise ValueError(f"{plan_id}: turnback requires canceled T_R2 and exactly two ticks")
                reverse_toward = op_data["reverse_toward"]
                if reverse_toward not in ADJACENCY[current] or headings[train] == reverse_toward:
                    raise ValueError(f"{plan_id}: invalid reversal from {current} toward {reverse_toward}")
                start_turnbacks[train] = reverse_toward
            elif op == "temporary_stop":
                continue
            else:
                raise ValueError(f"{plan_id}: unsupported action {op}")

        edge_owners: dict[frozenset[str], tuple[str, str, str]] = {}
        for train, (origin, destination) in accepted_moves.items():
            edge = frozenset((origin, destination))
            if edge in edge_owners:
                other, other_origin, other_destination = edge_owners[edge]
                reason = "HEAD_ON_COLLISION" if (origin, destination) == (other_destination, other_origin) else "SEGMENT_CAPACITY"
                raise ValueError(f"{plan_id}: {reason} at tick {tick}: {train} and {other}")
            edge_owners[edge] = (train, origin, destination)

        next_positions = dict(positions)
        for train, (_, destination) in accepted_moves.items():
            next_positions[train] = destination
        berth_counts = Counter(next_positions.values())
        if any(count > STATION_CAPACITY for count in berth_counts.values()):
            raise ValueError(f"{plan_id}: post-tick station capacity exceeded at {tick}: {berth_counts}")

        # Conflicts and berth counts have passed; commit the complete tick atomically.
        positions = next_positions
        for task_id in cancel_now:
            states[task_id] = "canceled"
            canceled += tasks[task_id]["passengers"]
            if task_id in {"TASK_R2_R3", "TASK_R3_R2"}:
                fault_resolution[task_id] = tick
        for train, reverse_toward in start_turnbacks.items():
            locks[train] = {"remaining": 2, "reverse_toward": reverse_toward}

        for train in accepted_moves:
            task_id = task_for_train[train]
            task = tasks[task_id]
            progress[task_id] += 1
            if positions[train] == task["to"]:
                states[task_id] = "delivered"
                passengers = task["passengers"]
                delivered += passengers
                arrival_tick = tick + 1
                last_delivery = max(last_delivery, arrival_tick)
                delay += passengers * max(arrival_tick - task["planned_arrival_tick"], 0)
                if task_id in {"TASK_R2_R3", "TASK_R3_R2"}:
                    fault_resolution[task_id] = arrival_tick

        for train, lock in list(locks.items()):
            lock["remaining"] -= 1
            if lock["remaining"] == 0:
                headings[train] = lock["reverse_toward"]
                del locks[train]

        tick_after = tick + 1
        terminal = tick_after == HORIZON
        success_at_deadline = delivered >= 13
        terminal_reason = ("SERVICE_COMPLETE" if success_at_deadline else "DEADLINE_SERVICE_BELOW_70") if terminal else None
        after = public_observation(tick_after, positions, states, delivered, canceled, locks,
                                   plan["alert_mode"] == "enabled", terminal, terminal_reason)
        rows.append({
            "trace_id": plan_id,
            "step": tick + 1,
            "tick_before": tick,
            "observation_before": before,
            "action": {"tool": "set_timetable", "tick": tick, "operations": operations},
            "expected_observation": after,
        })

    if len(plan["operations"]) != HORIZON:
        raise ValueError(f"{plan_id}: expected {HORIZON} ticks, got {len(plan['operations'])}")
    if set(fault_resolution) != {"TASK_R2_R3", "TASK_R3_R2"}:
        raise ValueError(f"{plan_id}: both fault-affected tasks must be resolved: {fault_resolution}")
    recovery = max(fault_resolution.values()) - FAULT_START
    metrics = {
        "delivered": delivered,
        "service_rate": delivered / 18,
        "canceled_passengers": canceled,
        "total_passenger_delay_ticks": delay,
        "recovery_duration_ticks": recovery,
        "last_delivery_tick": last_delivery,
        "success": delivered >= 13,
    }
    if metrics != plan["expected"]:
        raise AssertionError(f"{plan_id}: hand metric ledger mismatch: {metrics} != {plan['expected']}")
    return rows, metrics


def replay_failure_case(case: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    positions = dict(source["initial_trains"])
    tasks = source["tasks"]
    states = {task_id: "pending" for task_id in tasks}
    progress = {task_id: 0 for task_id in tasks}
    task_for_train = {task["train"]: task_id for task_id, task in tasks.items()}
    rows = {row["tick"]: row for row in case["operations"]}
    blocked: list[dict[str, Any]] = []
    delivered = canceled = 0

    for tick in range(HORIZON):
        row = rows.get(tick, {"tick": tick})
        operations = {train: op for train, op in row.items() if train != "tick"}
        start_positions = dict(positions)
        moves: dict[str, tuple[str, str]] = {}
        cancel_now: list[str] = []
        for train, op_data in operations.items():
            task_id = task_for_train[train]
            op = op_data["op"]
            if op in {"release", "detour"}:
                origin, destination = positions[train], op_data["to"]
                if destination not in ADJACENCY[origin]:
                    raise ValueError(f"{case['id']}: illegal link {origin}-{destination} at tick {tick}")
                if states[task_id] != "pending" or (op, destination) != HAND_PATHS[task_id][progress[task_id]]:
                    raise ValueError(f"{case['id']}: illegal hand route at tick {tick} for {train}")
                if frozenset((origin, destination)) == FAULT_EDGE and FAULT_START <= tick < FAULT_REOPEN:
                    blocked.append({"tick": tick, "train": train, "reason": "TRACK_CLOSED"})
                else:
                    moves[train] = (origin, destination)
            elif op == "cancel_service":
                cancel_id = op_data["task_id"]
                if cancel_id != task_id or states[task_id] != "pending" or positions[train] != tasks[task_id]["from"]:
                    raise ValueError(f"{case['id']}: invalid cancellation at tick {tick}")
                cancel_now.append(task_id)
            else:
                raise ValueError(f"{case['id']}: unsupported failure-case action {op}")

        edge_owner: dict[frozenset[str], tuple[str, str, str]] = {}
        conflict = False
        for train, (origin, destination) in moves.items():
            edge = frozenset((origin, destination))
            if edge in edge_owner:
                conflict = True
                break
            edge_owner[edge] = (train, origin, destination)
        if conflict:
            return {"terminal_reason": "HEAD_ON_COLLISION", "failure_tick": tick,
                    "final_tick": tick, "no_partial_movement": positions == start_positions,
                    "delivered": delivered, "canceled": canceled, "blocked_attempts": blocked}

        next_positions = dict(positions)
        for train, (_, destination) in moves.items():
            next_positions[train] = destination
        if any(count > STATION_CAPACITY for count in Counter(next_positions.values()).values()):
            return {"terminal_reason": "STATION_CAPACITY_OVERFLOW", "failure_tick": tick,
                    "final_tick": tick, "no_partial_movement": positions == start_positions,
                    "delivered": delivered, "canceled": canceled, "blocked_attempts": blocked}
        positions = next_positions
        for task_id in cancel_now:
            states[task_id] = "canceled"
            canceled += tasks[task_id]["passengers"]
        for train in moves:
            task_id = task_for_train[train]
            progress[task_id] += 1
            if positions[train] == tasks[task_id]["to"]:
                states[task_id] = "delivered"
                delivered += tasks[task_id]["passengers"]

        if tick + 1 == HORIZON:
            reason = "SERVICE_COMPLETE" if delivered >= 13 else "DEADLINE_SERVICE_BELOW_70"
            return {"terminal_reason": reason, "failure_tick": HORIZON - 1,
                    "final_tick": HORIZON, "no_partial_movement": True,
                    "delivered": delivered, "canceled": canceled, "blocked_attempts": blocked}
    raise AssertionError(f"{case['id']}: no terminal result")


def audit_failure_cases(source: dict[str, Any]) -> dict[str, Any]:
    cases = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    cases_by_id = {case["id"]: case for case in cases["cases"]}
    results: dict[str, Any] = {}
    for case_id, case in cases_by_id.items():
        actual = replay_failure_case(case, source)
        expected = case["expected"]
        for key in ("terminal_reason", "failure_tick"):
            if actual[key] != expected[key]:
                raise AssertionError(f"{case_id}: {key} mismatch: {actual[key]} != {expected[key]}")
        if case_id in {"F01", "F02"} and not actual["no_partial_movement"]:
            raise AssertionError(f"{case_id}: failure tick committed a partial movement")
        if case_id == "F01" and actual["blocked_attempts"]:
            raise AssertionError("F01 collision must occur before the fault and any blocked action")
        if case_id == "F02":
            counts = Counter((entry["tick"], entry["train"]) for entry in actual["blocked_attempts"])
            if len(actual["blocked_attempts"]) != 10 or any(
                counts[(tick, train)] != 1 for tick in range(5, 10) for train in ("T_R2", "T_R3")
            ):
                raise AssertionError("F02 must yield ten per-train TRACK_CLOSED outcomes over ticks 5–9")
            if actual["blocked_attempts"] != expected["blocked_attempts"]:
                expected_flat = [{"tick": item["tick"], "train": train, "reason": item["reason"]}
                                 for item in expected["blocked_attempts"] for train in item["trains"]]
                if actual["blocked_attempts"] != expected_flat:
                    raise AssertionError("F02 blocked release ledger differs from its hand-authored case")
        if case_id == "F03":
            for key, actual_key in (("delivered_by_deadline", "delivered"),
                                    ("canceled_passengers", "canceled")):
                if actual[actual_key] != expected[key]:
                    raise AssertionError(f"F03 {key} mismatch: {actual[actual_key]} != {expected[key]}")
            if actual["delivered"] / expected["denominator"] != expected["service_rate"]:
                raise AssertionError("F03 service fraction mismatch")
        results[case_id] = {"terminal_reason": actual["terminal_reason"],
                            "failure_tick": actual["failure_tick"], "delivered": actual["delivered"],
                            "canceled": actual["canceled"], "blocked_attempt_count": len(actual["blocked_attempts"])}

    boundaries = {case["id"]: case for case in cases["boundary_cases"]}
    if boundaries["B01"]["closed_tick"] != 9 or boundaries["B02"]["reopened_tick"] != 10:
        raise AssertionError("Boundary cases must straddle the 9/10 repair edge")
    if boundaries["B01"]["expected"] != {"reason": "TRACK_CLOSED", "position": "R2", "tick_after": 10}:
        raise AssertionError("B01 must hold the train at R2 on the final closed tick")
    if boundaries["B02"]["expected"] != {"reason": None, "position_after": "R3", "arrival_tick": 11}:
        raise AssertionError("B02 must permit passage on the first reopened tick")
    if boundaries["B03"]["alert_tick"] != 4 or boundaries["B03"]["expected"]["alert_contains_fault_id"] is not False:
        raise AssertionError("B03 must keep the advance warning generic")
    return {"failure_replays": results, "boundaries": ["B01", "B02", "B03"]}


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    if spec["status"] != "DESIGN_COMPLETE_PENDING_RUNTIME" or spec["runtime_verified"] is not False:
        raise AssertionError("Design audit must not promote runtime status")
    if "private_fault_id_until_tick_5" not in spec["private_state"] and "fault_id_until_tick_5" not in spec["private_state"]:
        raise AssertionError("Private fault identity is not declared private")
    if "fault_id" in spec["alert"]["content"].lower() or "R2-R3" in spec["alert"]["content"]:
        raise AssertionError("Generic warning leaks the hidden section")
    if spec["incident"]["closed_ticks_inclusive"] != [5, 9] or spec["incident"]["reopened_before_operations_at_tick"] != 10:
        raise AssertionError("Incident window must be exactly ticks 5 through 9")

    source = read_json(ROOT / "planning" / "hand_traces.json")
    if sum(task["passengers"] for task in source["tasks"].values()) != 18:
        raise AssertionError("Task ledger must retain all 18 passengers")
    plans = source["plans"]
    oracle_rows: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    preobservations: dict[str, dict[int, dict[str, Any]]] = {}
    operations: dict[str, dict[int, dict[str, Any]]] = {}
    for plan_id, plan in plans.items():
        rows, result = replay(plan_id, plan, source)
        oracle_rows.extend(rows)
        metrics[plan_id] = result
        preobservations[plan_id] = {row["tick_before"]: row["observation_before"] for row in rows}
        operations[plan_id] = {row["tick_before"]: row["action"]["operations"] for row in rows}

    public_fields = set(spec["public_observation_fields"])
    for row in oracle_rows:
        for key in ("observation_before", "expected_observation"):
            observation = row[key]
            if set(observation) != public_fields:
                raise AssertionError(f"Oracle {key} differs from the declared public observation contract")
            serialized = json.dumps(observation, ensure_ascii=False).lower()
            if any(private in serialized for private in ("fault_id", "expected_oracle_routes", "scoring_reference")):
                raise AssertionError(f"Private judge data leaked into {key}")
            if observation["tick"] < FAULT_START and observation["closed_segments"]:
                raise AssertionError("The exact fault section became observable before the incident")
            alert = observation["alert_message_if_any"]
            if alert and any(secret in alert["message"].lower() for secret in ("r2-r3", "r2_r3", "5 ticks", "five ticks")):
                raise AssertionError("Generic alert leaks fault location or duration")

    alert_name, no_alert_name = "alert_proactive_detour", "no_alert_reactive_detour"
    for tick in range(4):
        if preobservations[alert_name][tick] != preobservations[no_alert_name][tick]:
            raise AssertionError(f"Paired pre-event observations differ at tick {tick}")
        if operations[alert_name][tick] != operations[no_alert_name][tick]:
            raise AssertionError(f"Paired pre-event actions differ at tick {tick}")
    alert_obs, no_alert_obs = preobservations[alert_name][4], preobservations[no_alert_name][4]
    if alert_obs["alert_message_if_any"] is None or no_alert_obs["alert_message_if_any"] is not None:
        raise AssertionError("Tick 4 must be the only information treatment")
    alert_without_message = {key: value for key, value in alert_obs.items() if key != "alert_message_if_any"}
    no_alert_without_message = {key: value for key, value in no_alert_obs.items() if key != "alert_message_if_any"}
    if alert_without_message != no_alert_without_message:
        raise AssertionError("Alert observation contains a delta beyond the generic message")
    if metrics[no_alert_name]["total_passenger_delay_ticks"] - metrics[alert_name]["total_passenger_delay_ticks"] != 3:
        raise AssertionError("Hand-paired alert effect must equal one tick for three passengers")

    failure_summary = audit_failure_cases(source)
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                         for row in oracle_rows), encoding="utf-8")
    payload = oracle_path.read_bytes()
    result = {
        "result": "HAND_AUTHORED_MAP18_SCHEDULES_REPLAYED",
        "runtime_verified": False,
        "plan_metrics": metrics,
        "paired_alert_observations_equal_before_tick_4": True,
        "paired_alert_pre_tick_4_actions_equal": True,
        "paired_alert_delay_reduction_person_ticks": 3,
        "failure_cases": failure_summary,
        "oracle_rows": len(oracle_rows),
        "oracle_sha256": hashlib.sha256(payload).hexdigest().upper(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
