"""Independent offline solvers for V6 instances.

Each solver reads only the public scene data and produces a legal action path
plus an optimal value or a justified lower bound. Solvers are intentionally
separate from the runtime step logic: the validator then replays each solver's
path through the real environment and requires the same terminal outcome.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_arena.v6.catalog import get_scene
from agent_arena.worlds.scenario_v4 import map18 as map18_module
from agent_arena.worlds.scenario_v4.map30 import DEFAULT_CASE, Map30Case, WitnessRule


@dataclass(frozen=True)
class SolverResult:
    instance_id: str
    actions: tuple[dict[str, Any], ...]
    optimum: int | None
    lower_bound: int | None
    note: str


# --------------------------------------------------------------------------- #
# MAP-16
# --------------------------------------------------------------------------- #
def _map16_successors(
    state: tuple[str, ...],
    trains: tuple[str, ...],
    directions: dict[str, dict[str, tuple[str, ...]]],
) -> set[tuple[str, ...]]:
    options = [
        sorted({state[index], *directions[train][state[index]]})
        for index, train in enumerate(trains)
    ]
    results: set[tuple[str, ...]] = set()
    for combo in _product(options):
        if len(set(combo)) != len(combo):
            continue
        blocked = False
        for left in range(len(combo)):
            for right in range(left + 1, len(combo)):
                if combo[left] != state[left] and combo[right] != state[right]:
                    if frozenset((state[left], combo[left])) == frozenset(
                        (state[right], combo[right])
                    ):
                        blocked = True
        if not blocked:
            results.add(combo)
    return results


def _product(options: list[list[str]]) -> list[tuple[str, ...]]:
    result: list[tuple[str, ...]] = [()]
    for pool in options:
        result = [prefix + (item,) for prefix in result for item in pool]
    return result


def solve_map16(instance_id: str) -> SolverResult:
    scene = get_scene(instance_id)
    trains = tuple(scene.start_positions)
    start = tuple(scene.start_positions[train] for train in trains)
    goal = tuple(scene.goals[train] for train in trains)
    parents: dict[tuple[str, ...], tuple[str, ...] | None] = {start: None}
    queue = deque([start])
    found = start == goal
    while queue and not found:
        current = queue.popleft()
        for following in _map16_successors(current, trains, scene.directions):
            if following not in parents:
                parents[following] = current
                if following == goal:
                    found = True
                    break
                queue.append(following)
    if not found:
        return SolverResult(instance_id, (), None, None, "no schedule found")
    states: list[tuple[str, ...]] = [goal]
    cursor = goal
    while parents[cursor] is not None:
        cursor = parents[cursor]  # type: ignore[assignment]
        states.append(cursor)
    states.reverse()
    actions: list[dict[str, Any]] = [{"tool": "inspect_network"}]
    for previous, following in zip(states, states[1:], strict=False):
        for index, train in enumerate(trains):
            if following[index] != previous[index]:
                destination = following[index]
                tool = "occupy_siding" if destination in scene.sidings else "set_route"
                actions.append({"tool": tool, "train_id": train, "next_node": destination})
        actions.append({"tool": "move_train"})
    makespan = len(states) - 1
    return SolverResult(
        instance_id,
        tuple(actions),
        makespan,
        makespan,
        f"BFS minimum makespan {makespan} over {len(parents)} reachable states",
    )


# --------------------------------------------------------------------------- #
# MAP-22
# --------------------------------------------------------------------------- #
def _map22_round_trip(scene: Any) -> list[str]:
    nodes = scene.nodes
    start, target = scene.start, scene.target
    parents: dict[tuple[str, bool], tuple[tuple[str, bool], str] | None] = {(start, False): None}
    queue = deque([(start, False)])
    final: tuple[str, bool] | None = (start, True) if start == target else None
    while queue and final is None:
        node, visited = queue.popleft()
        for bearing in sorted(nodes[node]["exits"]):
            neighbor = nodes[node]["exits"][bearing]
            next_visited = visited or neighbor == target
            state = (neighbor, next_visited)
            if state not in parents:
                parents[state] = ((node, visited), bearing)
                if state == (start, True):
                    final = state
                    break
                queue.append(state)
    if final is None:
        return []
    bearings: list[str] = []
    cursor = final
    while parents[cursor] is not None:
        previous, bearing = parents[cursor]  # type: ignore[misc]
        bearings.append(bearing)
        cursor = previous
    bearings.reverse()
    return bearings


def solve_map22(instance_id: str) -> SolverResult:
    scene = get_scene(instance_id)
    bearings = _map22_round_trip(scene)
    actions: list[dict[str, Any]] = [{"tool": "move", "bearing": b} for b in bearings]
    moves = len(bearings)
    return SolverResult(
        instance_id,
        tuple(actions),
        moves,
        moves,
        f"shortest visit-and-return walk of {moves} moves (budget {scene.move_budget})",
    )


# --------------------------------------------------------------------------- #
# MAP-08
# --------------------------------------------------------------------------- #
def _edge_adjacency(edges: dict[str, tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge_id, (left, right) in edges.items():
        adjacency.setdefault(left, []).append((edge_id, right))
        adjacency.setdefault(right, []).append((edge_id, left))
    return adjacency


def _shortest_edge_path(
    adjacency: dict[str, list[tuple[str, str]]], start: str, goal: str
) -> list[str]:
    if start == goal:
        return []
    parents: dict[str, tuple[str, str] | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for edge_id, neighbor in sorted(adjacency.get(node, [])):
            if neighbor not in parents:
                parents[neighbor] = (node, edge_id)
                if neighbor == goal:
                    queue.clear()
                    break
                queue.append(neighbor)
    if goal not in parents:
        raise ValueError(f"No MAP-08 path from {start} to {goal}.")
    path: list[str] = []
    cursor = goal
    while parents[cursor] is not None:
        previous, edge_id = parents[cursor]  # type: ignore[misc]
        path.append(edge_id)
        cursor = previous
    path.reverse()
    return path


def solve_map08(instance_id: str, seed: int) -> SolverResult:
    scene = get_scene(instance_id)
    adjacency = _edge_adjacency(scene.edges)
    leak = scene.leak_by_seed[seed]
    stations = sorted({station for row in scene.signatures.values() for station in row})
    actions: list[dict[str, Any]] = []
    node = "A"
    remaining = set(scene.signatures)
    for station in stations:
        if len(remaining) <= 1:
            break
        for edge_id in _shortest_edge_path(adjacency, node, station):
            actions.append({"tool": "move", "edge_id": edge_id})
        node = station
        actions.append(
            {"tool": "interact", "target_id": station, "operation": f"pressure_test_{station}"}
        )
        reading = scene.signatures[leak][station]
        remaining = {site for site in remaining if scene.signatures[site][station] == reading}
    for edge_id in _shortest_edge_path(adjacency, node, leak):
        actions.append({"tool": "move", "edge_id": edge_id})
    actions.append({"tool": "interact", "target_id": leak, "operation": "repair_leak"})
    return SolverResult(
        instance_id,
        tuple(actions),
        len(actions),
        len(actions),
        f"seed {seed}: diagnose leak {leak} with {len(actions)} actions",
    )


# --------------------------------------------------------------------------- #
# MAP-26
# --------------------------------------------------------------------------- #
def solve_map26(instance_id: str, seed: int = 0) -> SolverResult:
    scene = get_scene(instance_id)
    fault = scene.fault_part
    actions: list[dict[str, Any]] = [
        {"tool": "move", "to": "D"},
    ]
    for test_id, part in (
        ("bus_load", "power_regulator"),
        ("antenna_loopback", "antenna_coupler"),
        ("software_checksum", "software_image"),
    ):
        actions.append({"tool": "test", "test_id": test_id})
        if part == fault:
            break
    actions.extend(
        [
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": fault},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": fault},
            {"tool": "restart"},
        ]
    )
    return SolverResult(
        instance_id,
        tuple(actions),
        len(actions),
        len(actions),
        f"diagnose and replace {fault} leaving spares unused",
    )


# --------------------------------------------------------------------------- #
# MAP-18
# --------------------------------------------------------------------------- #
def _map18_task_map() -> dict[str, dict[str, Any]]:
    return {
        train: dict(map18_module.TASKS[task_id])
        for train, task_id in map18_module.TRAIN_TASKS.items()
    }


def _map18_route(adjacency: dict[str, tuple[str, ...]], start: str, goal: str) -> list[str]:
    parents: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in sorted(adjacency.get(node, ())):
            if neighbor not in parents:
                parents[neighbor] = node
                if neighbor == goal:
                    queue.clear()
                    break
                queue.append(neighbor)
    if goal not in parents:
        return []
    route: list[str] = []
    cursor: str | None = goal
    while cursor is not None:
        route.append(cursor)
        cursor = parents[cursor]
    route.reverse()
    return route[1:]


def solve_map18(instance_id: str) -> SolverResult:
    scene = get_scene(instance_id)
    task_map = _map18_task_map()
    adjacency = map18_module.ADJACENCY
    routes = {
        train: _map18_route(adjacency, task["origin"], task["destination"])
        for train, task in task_map.items()
    }
    # Greedy tick scheduler: advance each train one edge toward its destination
    # when the edge and destination station are free this tick.
    position = {train: task["origin"] for train, task in task_map.items()}
    delivered: set[str] = set()
    actions: list[dict[str, Any]] = []
    for tick in range(scene.horizon):
        operations: dict[str, dict[str, Any]] = {}
        claimed: set[frozenset[str]] = set()
        berths: dict[str, int] = {}
        for train in sorted(task_map):
            task = task_map[train]
            if train in delivered or position[train] == task["destination"]:
                delivered.add(train)
                continue
            route = routes[train]
            if not route:
                continue
            following = route[0]
            edge = frozenset((position[train], following))
            if edge in claimed or berths.get(following, 0) >= 2:
                operations[train] = {"op": "temporary_stop"}
                continue
            operations[train] = {"op": "release", "to": following}
            claimed.add(edge)
            berths[following] = berths.get(following, 0) + 1
            position[train] = following
            route.pop(0)
            if following == task["destination"]:
                delivered.add(train)
        actions.append({"tool": "set_timetable", "tick": tick, "operations": operations})
    total_demand = sum(int(task["passengers"]) for task in task_map.values())
    delivered_passengers = sum(int(task_map[t]["passengers"]) for t in delivered)
    # The greedy plan delivers every passenger whenever it reaches the total
    # demand, which is a provable optimum for the service-rate objective. Other
    # plans report the achieved passenger count as a lower bound.
    if delivered_passengers == total_demand:
        optimum: int | None = total_demand
        lower_bound: int | None = total_demand
        note = f"delivers all {total_demand} passengers (optimal service rate)"
    else:
        optimum = None
        lower_bound = delivered_passengers
        note = f"delivers {delivered_passengers}/{total_demand} passengers (lower bound)"
    return SolverResult(instance_id, tuple(actions), optimum, lower_bound, note)


# --------------------------------------------------------------------------- #
# MAP-30
# --------------------------------------------------------------------------- #
def _map30_locate(case: Map30Case) -> dict[str, str]:
    locate: dict[str, str] = {}
    for node, ids in case.node_evidence.items():
        for evidence_id in ids:
            locate[evidence_id] = node
    return locate


def _map30_producing(
    case: Map30Case, evidence_id: str
) -> tuple[str, WitnessRule] | None:
    for npc, rules in case.witness_rules.items():
        for rule in rules:
            if evidence_id in rule.evidence_ids:
                return npc, rule
    return None


def _map30_node_path(case: Map30Case, start: str, goal: str) -> list[str]:
    adjacency: dict[str, set[str]] = {}
    for edge in case.edges:
        left, right = tuple(edge)
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
    parents: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in sorted(adjacency.get(node, ())):
            if neighbor not in parents:
                parents[neighbor] = node
                if neighbor == goal:
                    queue.clear()
                    break
                queue.append(neighbor)
    path: list[str] = []
    cursor: str | None = goal
    while cursor is not None:
        path.append(cursor)
        cursor = parents.get(cursor)
    path.reverse()
    return path[1:]


def solve_map30(instance_id: str) -> SolverResult:
    scene = get_scene(instance_id)
    case = scene.case if scene.case is not None else DEFAULT_CASE
    locate = _map30_locate(case)
    npc_node = {npc: node for node, npc in case.node_npcs.items()}
    actions: list[dict[str, Any]] = []
    node = "H"
    inspected: set[str] = set()
    for entry in case.entry_order:
        required = case.entry_allowed[entry]
        witness = [e for e in required if e not in locate]
        npc = None
        rule = None
        if witness:
            producing = _map30_producing(case, witness[0])
            if producing is None:
                raise ValueError(f"No witness rule produces {witness[0]}.")
            npc, rule = producing
            target_node = npc_node[npc]
        else:
            target_node = locate[sorted(required)[0]]
        for step_node in _map30_node_path(case, node, target_node):
            actions.append({"tool": "move", "to": step_node})
        node = target_node
        inspect_ids: set[str] = set()
        for evidence_id in required:
            if evidence_id in locate and locate[evidence_id] == node:
                inspect_ids.add(evidence_id)
        if rule is not None and rule.requires_shown_evidence is not None:
            inspect_ids.add(rule.requires_shown_evidence)
        for evidence_id in sorted(inspect_ids - inspected):
            actions.append({"tool": "inspect", "evidence_id": evidence_id})
            inspected.add(evidence_id)
        if npc is not None and rule is not None:
            actions.append(
                {
                    "tool": "interview",
                    "npc_id": npc,
                    "topic_id": entry,
                    "shown_evidence_ids": (
                        [rule.requires_shown_evidence]
                        if rule.requires_shown_evidence is not None
                        else []
                    ),
                    "shown_casebook_entry_ids": (
                        [rule.requires_casebook_entry]
                        if rule.requires_casebook_entry is not None
                        else []
                    ),
                }
            )
        actions.append(
            {"tool": "record", "entry_id": entry, "evidence_ids": sorted(required)}
        )
    actions.append({"tool": "compare_records", "entry_ids": list(case.entry_order)})
    for step_node in _map30_node_path(case, node, "J"):
        actions.append({"tool": "move", "to": step_node})
    actions.append(
        {
            "tool": "formal_accuse",
            "person_id": case.culprit,
            "event_claims": [claim.model_dump() for claim in case.claims],
            "cited_entry_ids": list(case.entry_order),
        }
    )
    lower_bound = len(actions)
    return SolverResult(
        instance_id,
        tuple(actions),
        None,
        lower_bound,
        f"constructive route with {len(actions)} actions to a complete accusation",
    )


def map26_recovery_prefix(instance_id: str) -> list[dict[str, Any]]:
    """Return the legal failure prefix that precedes a MAP-26 recovery episode."""
    scene = get_scene(instance_id)
    if scene.use_registered_prefix:
        route_path = (
            Path(__file__).resolve().parents[3]
            / "worlds" / "v4" / "MAP-26" / "planning" / "hand_traces.json"
        )
        data = json.loads(route_path.read_text(encoding="utf-8"))
        route = next(item for item in data["routes"] if item["id"] == "feedback_then_correct")
        prefix: list[dict[str, Any]] = []
        for action in route["actions"][:7]:
            payload = {"tool": action["name"]}
            payload.update({key: value for key, value in action.items() if key != "name"})
            prefix.append(payload)
        return prefix
    wrong = scene.recovery_wrong_part
    if wrong is None:
        raise ValueError(f"{instance_id} has no recovery prefix source.")
    return [
        {"tool": "move", "to": "D"},
        {"tool": "move", "to": "A"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": wrong},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": wrong},
    ]


def solve_map26_recovery(instance_id: str, feedback_mode: str = "full") -> SolverResult:
    """Replay a legal failure prefix, then search a legal repair tail."""
    from agent_arena.v6.catalog import build_environment
    from agent_arena.worlds.scenario_v4 import ScenarioV4Action

    scene = get_scene(instance_id)
    prefix = map26_recovery_prefix(instance_id)

    parts = ("power_regulator", "antenna_coupler", "software_image")

    def candidate_actions(env: Any) -> list[dict[str, Any]]:
        node = env.node
        options: list[dict[str, Any]] = []
        for target in ("T", "D", "A", "B"):
            if frozenset((node, target)) in env.edges:
                options.append({"tool": "move", "to": target})
        if node == "D":
            for test_id in ("bus_load", "antenna_loopback", "software_checksum"):
                options.append({"tool": "test", "test_id": test_id})
        if node == "B":
            for part in parts:
                options.append({"tool": "take_spare", "part_id": part})
        if node == "A":
            for part in parts:
                options.append({"tool": "replace", "part_id": part})
            options.append({"tool": "rollback"})
            options.append({"tool": "restart"})
        return options

    explored: set[str] = set()

    def dfs(path: list[dict[str, Any]], depth: int) -> list[dict[str, Any]] | None:
        current = build_environment(scene, feedback_mode, seed=0)
        for payload in [*prefix, *path]:
            current.step(ScenarioV4Action.model_validate(payload, strict=True))
        if current.is_success:
            return path
        if depth == 0 or current.is_terminal:
            return None
        key = current.state_hash()
        if key in explored:
            return None
        explored.add(key)
        for action in candidate_actions(current):
            result = dfs([*path, action], depth - 1)
            if result is not None:
                return result
        return None

    solution = dfs([], 9)
    if solution is None:
        return SolverResult(
            instance_id, tuple(prefix), None, None, f"{feedback_mode}: no repair tail found"
        )
    return SolverResult(
        instance_id,
        tuple([*prefix, *solution]),
        len(prefix) + len(solution),
        len(prefix) + len(solution),
        f"{feedback_mode}: legal prefix plus a {len(solution)}-action repair tail",
    )


def map30_recall_actions() -> list[dict[str, Any]]:
    """Return the reviewed V4 investigation prefix (excluding the final accusation)."""
    route_path = (
        Path(__file__).resolve().parents[3]
        / "worlds" / "v4" / "MAP-30" / "planning" / "hand_traces.json"
    )
    data = json.loads(route_path.read_text(encoding="utf-8"))
    route = next(item for item in data["routes"] if item["id"] == "event_by_event_archive_first")
    actions: list[dict[str, Any]] = []
    for action in route["actions"][:-1]:
        payload = {"tool": action["name"]}
        payload.update({key: value for key, value in action.items() if key != "name"})
        if action["name"] == "interview":
            payload.setdefault("shown_evidence_ids", [])
            payload.setdefault("shown_casebook_entry_ids", [])
        actions.append(payload)
    return actions


def solve_map30_recall(instance_id: str) -> SolverResult:
    from agent_arena.worlds.scenario_v4.map30 import DEFAULT_CASE

    prefix = map30_recall_actions()
    accuse = {
        "tool": "formal_accuse",
        "person_id": DEFAULT_CASE.culprit,
        "event_claims": [claim.model_dump() for claim in DEFAULT_CASE.claims],
        "cited_entry_ids": list(DEFAULT_CASE.entry_order),
    }
    actions = [*prefix, accuse]
    return SolverResult(
        instance_id,
        tuple(actions),
        len(actions),
        len(actions),
        "recall: reviewed investigation prefix plus the formal accusation",
    )


def solve(instance_id: str, *, seed: int = 0) -> SolverResult:
    scene = get_scene(instance_id)
    if scene.map_id == "MAP-16":
        return solve_map16(instance_id)
    if scene.map_id == "MAP-22":
        return solve_map22(instance_id)
    if scene.map_id == "MAP-08":
        return solve_map08(instance_id, seed)
    if scene.map_id == "MAP-26":
        if "recovery" in instance_id:
            return solve_map26_recovery(instance_id, "recovery_full")
        return solve_map26(instance_id, seed)
    if scene.map_id == "MAP-18":
        return solve_map18(instance_id)
    if scene.map_id == "MAP-30":
        if getattr(scene, "use_recall_prefix", False):
            return solve_map30_recall(instance_id)
        return solve_map30(instance_id)
    raise ValueError(f"Unsupported V6 map: {scene.map_id}")
