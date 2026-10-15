"""Replay MAP-17's two hand-authored timetables and compare public Pareto metrics."""
from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HORIZON = 12
ENERGY_BUDGET = 18
SEATS = 3
STATION_CAPACITY = 2
DEMAND = {"A_to_C": ("A", "C", 2), "B_to_E": ("B", "E", 2),
          "C_to_F": ("C", "F", 2), "D_to_B": ("D", "B", 2),
          "F_to_A": ("F", "A", 2)}
ADJACENCY = {
    "A": {"B", "D"}, "B": {"A", "C", "E"}, "C": {"B", "D"},
    "D": {"C", "A"}, "E": {"B", "F"}, "F": {"E"},
}
OD_BY_KEY = {key: (origin, destination) for key, (origin, destination, _) in DEMAND.items()}


def public_observation(tick: int, positions: dict[str, str], queues: dict[str, int],
                       onboard: dict[str, dict[str, int]], delivered: dict[str, int],
                       wait: int, energy: int, terminal: bool,
                       reason: str | None) -> dict:
    return {
        "tick": tick,
        "ticks_remaining": HORIZON - tick,
        "topology": {"ring_nodes": ["A", "B", "C", "D"],
                     "ring_segments": ["AB", "BC", "CD", "DA"],
                     "branch_nodes": ["B", "E", "F"],
                     "branch_segments": ["BE", "EF"],
                     "shared_bidirectional_segment": "BC",
                     "segment_capacity_per_tick": 1,
                     "station_train_berth_capacity": STATION_CAPACITY},
        "demand_matrix": {key: quantity for key, (_, _, quantity) in DEMAND.items()},
        "train_seat_capacity": {train: SEATS for train in positions},
        "train_positions": dict(positions),
        "station_train_counts": {station: sum(p == station for p in positions.values())
                                 for station in sorted(ADJACENCY)},
        "waiting_demand": dict(queues),
        "onboard_passengers": {train: dict(load) for train, load in onboard.items()},
        "delivered_by_od": dict(delivered),
        "passenger_wait_person_ticks": wait,
        "energy_consumed": energy,
        "energy_remaining": ENERGY_BUDGET - energy,
        "terminal": terminal,
        "terminal_reason": reason,
    }


def replay(plan_id: str, plan: dict) -> tuple[list[dict], dict]:
    positions = {name: train["start"] for name, train in plan["trains"].items()}
    queues = {key: quantity for key, (_, _, quantity) in DEMAND.items()}
    onboard = {name: {} for name in positions}
    delivered = {key: 0 for key in DEMAND}
    branch_selected: set[str] = set()
    wait = energy = 0
    last_delivery_tick = 0
    trace_rows: list[dict] = []

    for tick_row in plan["operations"]:
        tick = tick_row["tick"]
        if tick != len(trace_rows):
            raise ValueError(f"{plan_id}: expected sequential tick row, got {tick}")
        operations = {train: row for train, row in tick_row.items() if train != "tick"}
        release_edges: dict[frozenset[str], str] = {}
        next_positions = dict(positions)
        release_count = 0

        for train, operation in operations.items():
            if train not in positions:
                raise ValueError(f"{plan_id}: unknown train {train}")
            op = operation["op"]
            current = positions[train]
            if op == "release":
                destination = operation["to"]
                if destination not in ADJACENCY[current]:
                    raise ValueError(f"{plan_id}: illegal segment {current}-{destination} at tick {tick}")
                if current == "B" and destination == "E" and train not in branch_selected:
                    raise ValueError(f"{plan_id}: train {train} entered branch BE without switching at B")
                if current == "B" and destination in {"A", "C"} and train in branch_selected:
                    raise ValueError(f"{plan_id}: train {train} selected branch but released onto the ring")
                segment = frozenset((current, destination))
                if segment in release_edges:
                    raise ValueError(f"{plan_id}: shared segment used twice at tick {tick}")
                release_edges[segment] = train
                next_positions[train] = destination
                release_count += 1
            elif op == "switch_line":
                if current != "B" or operation.get("line") not in {"ring", "branch"}:
                    raise ValueError(f"{plan_id}: illegal line switch by {train} at {current}")
                if operation["line"] == "branch":
                    branch_selected.add(train)
                else:
                    branch_selected.discard(train)
            elif op not in {"stop", "delay"}:
                raise ValueError(f"{plan_id}: unsupported operation {op}")

        if energy + release_count > ENERGY_BUDGET:
            raise ValueError(f"{plan_id}: energy budget exceeded at tick {tick}")
        station_counts = {station: sum(p == station for p in next_positions.values())
                          for station in ADJACENCY}
        if any(count > STATION_CAPACITY for count in station_counts.values()):
            raise ValueError(f"{plan_id}: station platform capacity exceeded at tick {tick}: {station_counts}")

        # The whole tick has passed safety/resource preflight; waiting accrues before boarding.
        wait += sum(queues.values())
        energy += release_count
        delivered_this_tick = 0
        positions = next_positions
        for train, operation in operations.items():
            if operation["op"] == "release" and operation.get("to") in {"A", "C", "E"}:
                branch_selected.discard(train)

        for train, operation in operations.items():
            if operation["op"] != "release":
                continue
            arrival = positions[train]
            for od_key, quantity in list(onboard[train].items()):
                _, destination = OD_BY_KEY[od_key]
                if destination == arrival:
                    delivered[od_key] += quantity
                    delivered_this_tick += quantity
                    del onboard[train][od_key]

        for train, operation in operations.items():
            if operation["op"] not in {"stop", "switch_line"}:
                continue
            origin_here = positions[train]
            manifest = operation.get("board", {})
            current_load = sum(onboard[train].values())
            requested = sum(manifest.values())
            if current_load + requested > SEATS:
                raise ValueError(f"{plan_id}: train {train} exceeds seat capacity at tick {tick}")
            for od_key, quantity in manifest.items():
                if od_key not in DEMAND:
                    raise ValueError(f"{plan_id}: unknown OD {od_key}")
                origin, destination = OD_BY_KEY[od_key]
                if origin != origin_here or quantity > queues[od_key] or destination == origin_here:
                    raise ValueError(f"{plan_id}: invalid boarding manifest at tick {tick}: {train} {od_key} {quantity}")
                queues[od_key] -= quantity
                onboard[train][od_key] = onboard[train].get(od_key, 0) + quantity

        if delivered_this_tick:
            last_delivery_tick = tick + 1
        tick_after = tick + 1
        terminal = tick_after == HORIZON
        service_rate = sum(delivered.values()) / sum(quantity for _, _, quantity in DEMAND.values())
        reason = "DEMAND_THRESHOLD_MET" if terminal and service_rate >= 0.8 else (
            "DEADLINE_SERVICE_BELOW_80" if terminal else None)
        action = {"tool": "set_timetable", "tick": tick, "operations": operations}
        trace_rows.append({
            "trace_id": plan_id,
            "step": tick + 1,
            "tick_before": tick,
            "action": action,
            "expected_observation": public_observation(tick_after, positions, queues, onboard,
                                                       delivered, wait, energy, terminal, reason),
        })

    metrics = {
        "delivered": sum(delivered.values()),
        "service_rate": sum(delivered.values()) / sum(quantity for _, _, quantity in DEMAND.values()),
        "passenger_wait_person_ticks": wait,
        "energy": energy,
        "last_delivery_tick": last_delivery_tick,
        "transfers": 0,
        "success": sum(delivered.values()) >= 8 and energy <= ENERGY_BUDGET,
    }
    if metrics != plan["expected"]:
        raise AssertionError(f"{plan_id}: hand metric ledger mismatch: {metrics} != {plan['expected']}")
    return trace_rows, metrics


def normalized_vector(metrics: dict) -> tuple[float, float, float, float]:
    return (1.0 - metrics["service_rate"],
            metrics["passenger_wait_person_ticks"] / (10 * HORIZON),
            metrics["energy"] / ENERGY_BUDGET,
            metrics["last_delivery_tick"] / HORIZON)


def main() -> None:
    source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    if source["demand"] != {key: value[2] for key, value in DEMAND.items()}:
        raise ValueError("Hand-written demand differs from MAP-17 audit constants")
    all_rows: list[dict] = []
    results = {}
    for name, plan in source["plans"].items():
        rows, metrics = replay(name, {**plan, "trains": source["trains"]})
        all_rows.extend(rows)
        results[name] = metrics

    first, second = results["time_priority"], results["energy_priority"]
    time_dominates_energy = (first["service_rate"] >= second["service_rate"]
                             and first["passenger_wait_person_ticks"] <= second["passenger_wait_person_ticks"]
                             and first["energy"] <= second["energy"]
                             and first["last_delivery_tick"] <= second["last_delivery_tick"])
    energy_dominates_time = (second["service_rate"] >= first["service_rate"]
                             and second["passenger_wait_person_ticks"] <= first["passenger_wait_person_ticks"]
                             and second["energy"] <= first["energy"]
                             and second["last_delivery_tick"] <= first["last_delivery_tick"])
    if time_dominates_energy or energy_dominates_time:
        raise AssertionError("The hand-authored reference points are not mutually non-dominated")

    anchors = [normalized_vector(first), normalized_vector(second)]
    distances = {}
    for name, metrics in results.items():
        vector = normalized_vector(metrics)
        distances[name] = min(math.sqrt(sum((left - right) ** 2 for left, right in zip(vector, anchor)))
                              for anchor in anchors)
    reference = {
        "map_id": "MAP-17", "runtime_verified": False,
        "objectives": ["maximize_service_rate", "minimize_wait", "minimize_energy", "minimize_last_delivery_tick"],
        "hand_authored_reference_points": results,
        "normalized_euclidean_distance_to_reference_set": distances,
        "normalization_ranges": {"service_loss": [0, 1], "wait": [0, 120], "energy": [0, 18], "last_delivery_tick": [0, 12]},
        "points_mutually_non_dominated": True,
        "global_optimal_front_proven": False,
    }
    (ROOT / "planning" / "pareto_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "oracle_trace.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in all_rows), encoding="utf-8")
    print(json.dumps({"result": "HAND_TIMETABLES_REPLAYED_AND_PARETO_ANCHORS_CHECKED",
                      "reference": reference, "oracle_rows": len(all_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
