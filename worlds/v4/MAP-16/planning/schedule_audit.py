"""Check hand-authored MAP-16 schedules and enumerate the finite route state space."""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = ("A", "B")  # tuple order is train a, train b
GOAL = ("B", "A")
NEIGHBORS = {
    "A": {"X"}, "X": {"M"}, "M": {"D", "Y"},
    "D": {"M"}, "Y": {"B"}, "B": set(),
}
NEIGHBORS_B = {
    "B": {"Y"}, "Y": {"M"}, "M": {"D", "X"},
    "D": {"M"}, "X": {"A"}, "A": set(),
}


def edge(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


def successors(state: tuple[str, str]) -> list[tuple[str, str]]:
    positions = (state[0], state[1])
    options = [({positions[0]} | NEIGHBORS[positions[0]]),
               ({positions[1]} | NEIGHBORS_B[positions[1]])]
    if positions[0] == "B":
        options[0] = {"B"}
    if positions[1] == "A":
        options[1] = {"A"}
    states = []
    for a_next in options[0]:
        for b_next in options[1]:
            if a_next == b_next:
                continue  # final node capacity
            used = []
            if a_next != positions[0]:
                used.append(edge(positions[0], a_next))
            if b_next != positions[1]:
                used.append(edge(positions[1], b_next))
            if len(used) != len(set(used)):
                continue  # section capacity, including head-on swaps
            states.append((a_next, b_next))
    return states


def shortest_schedule() -> tuple[int | None, int]:
    distance = {START: 0}
    queue = deque([START])
    while queue:
        state = queue.popleft()
        for following in successors(state):
            if following not in distance:
                distance[following] = distance[state] + 1
                queue.append(following)
    return distance.get(GOAL), len(distance)


def enumerate_reachable_states() -> set[tuple[str, str]]:
    states = {START}
    queue = deque([START])
    while queue:
        for following in successors(queue.popleft()):
            if following not in states:
                states.add(following)
                queue.append(following)
    return states


def has_safe_completion(state: tuple[str, str]) -> bool:
    seen = {state}
    queue = deque([state])
    while queue:
        current = queue.popleft()
        if current == GOAL:
            return True
        for following in successors(current):
            if following not in seen:
                seen.add(following)
                queue.append(following)
    return False


def action_observation(positions: tuple[str, str], tick: int,
                       pending: dict[str, str], terminal: bool = False,
                       reason: str | None = None) -> dict:
    return {
        "tick": tick,
        "train_positions": {"a": positions[0], "b": positions[1]},
        "train_goals": {"a": "B", "b": "A"},
        "occupied_nodes": sorted(positions),
        "pending_route_reservations": dict(pending),
        "terminal": terminal,
        "terminal_reason": reason,
    }


def replay(plan_name: str, plan: list[dict]) -> list[dict]:
    positions, tick = START, 0
    pending: dict[str, str] = {}
    rows: list[dict] = []
    for tick_plan in plan:
        if tick_plan["tick_before"] != tick or tuple(tick_plan["positions_before"][t]
                                                       for t in ("a", "b")) != positions:
            raise ValueError(f"{plan_name}: tick or pre-state mismatch")
        for train, destination in tick_plan["route_intents"].items():
            current = positions[0 if train == "a" else 1]
            available = NEIGHBORS[current] if train == "a" else NEIGHBORS_B[current]
            if destination not in available or train in pending:
                raise ValueError(f"{plan_name}: illegal or duplicate route reservation")
            tool = "occupy_siding" if (current, destination) == ("M", "D") else "set_route"
            action = {"tool": tool, "train_id": train, "next_node": destination}
            pending[train] = destination
            rows.append({"trace_id": plan_name, "step": len(rows) + 1, "action": action,
                         "expected_observation": action_observation(positions, tick, pending)})

        following = [tick_plan["positions_after"][train] for train in ("a", "b")]
        used_edges = []
        for index, train in enumerate(("a", "b")):
            destination = pending.get(train, positions[index])
            if destination != positions[index]:
                used_edges.append(edge(positions[index], destination))
        if len(used_edges) != len(set(used_edges)) or following[0] == following[1]:
            raise ValueError(f"{plan_name}: section or node capacity conflict")
        if following != [pending.get(train, positions[index])
                         for index, train in enumerate(("a", "b"))]:
            raise ValueError(f"{plan_name}: authored post-state differs from route intents")
        positions = (following[0], following[1])
        pending.clear()
        tick += 1
        terminal = positions == GOAL
        if not terminal and not has_safe_completion(positions):
            raise ValueError(f"{plan_name}: hand schedule enters a deadlock")
        action = {"tool": "move_train"}
        observation = action_observation(positions, tick, pending, terminal,
                                         "GATE_OPENED" if terminal else None)
        rows.append({"trace_id": plan_name, "step": len(rows) + 1, "action": action,
                     "expected_observation": observation})
    if positions != GOAL:
        raise ValueError(f"{plan_name}: both trains did not reach opposite endpoints")
    return rows


def main() -> None:
    source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    best, reachable_states = shortest_schedule()
    if best != 6:
        raise AssertionError(f"Expected six-tick optimum from the authored topology, got {best}")
    deadlocks = sorted(state for state in enumerate_reachable_states()
                       if state != GOAL and not has_safe_completion(state))
    if deadlocks != [("A", "X"), ("Y", "B")]:
        raise AssertionError(f"Unexpected finite-map deadlock states: {deadlocks}")
    all_rows = []
    summary = {}
    for name, plan in source["plans"].items():
        rows = replay(name, plan)
        if len(plan) != best:
            raise AssertionError(f"{name}: expected optimal {best}-tick schedule")
        all_rows.extend(rows)
        summary[name] = {"ticks": len(plan), "primitive_actions": len(rows),
                         "final_positions": plan[-1]["positions_after"],
                         "optimality_gap": 0.0}
    (ROOT / "oracle_trace.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                for row in all_rows), encoding="utf-8")
    result = {
        "map_id": "MAP-16", "runtime_verified": False,
        "topology": "A-X-M-Y-B with siding M-D",
        "reachable_collision_free_position_states": reachable_states,
        "unrecoverable_deadlock_states": [{"a": state[0], "b": state[1]} for state in deadlocks],
        "shortest_conflict_free_makespan_ticks": best,
        "lower_bound": "the siding train's six required segment traversals",
        "manual_plans": summary,
        "both_train_orders_are_distinct_and_optimal": len(summary) == 2,
    }
    (ROOT / "planning" / "route_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "HAND_SCHEDULES_SAFE_AND_BFS_OPTIMAL",
                      "audit": result,
                      "oracle_rows": len(all_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
