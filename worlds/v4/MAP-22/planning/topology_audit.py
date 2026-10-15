"""Replay MAP-22's fixed signpost graph, memory tour, and step-boundary routes."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SIGNS = {
    "A": ("CAMP_LANTERN_RING", "forked_lantern", "three_brass_prongs_and_ring_notch"),
    "B": ("B_RED_NICK", "three_pronged_forkpost", "red_diagonal_nick_at_northern_foot"),
    "C": ("C_WHITE_BIRCH_THREAD", "pale_trunk", "single_red_thread_on_white_birch"),
    "D": ("D_TWIN_CUT_STONE", "narrow_stone", "two_vertical_cuts_facing_uphill"),
    "E": ("E_ROOT_CROSSBAR", "three_pronged_forkpost", "two_pale_roots_under_eastern_rail"),
    "F": ("F_CRACKED_BELL", "hanging_bell", "bell_crack_open_to_north"),
    "G": ("G_BLUE_CAIRN", "three_stone_cairn", "blue_thread_under_top_stone"),
    "H": ("H_TWIN_BAR_SADDLE", "three_pronged_forkpost", "paired_horizontal_cuts_below_saddle"),
    "I": ("I_MOSS_ARCH", "basalt_arch", "one_moss_spot_on_inner_left_pillar"),
    "J": ("J_RED_RESIN_PINE", "bent_pine", "two_red_resin_drops_on_east_bend"),
    "K": ("K_MOSS_WEDGE", "three_pronged_forkpost", "moss_wedge_on_western_foot"),
    "L": ("RUIN_TRIPLE_ARCH", "dark_arch", "three_nested_black_arcs_over_stone_threshold"),
}
BEARINGS = {
    "A": {"NE": "B", "SE": "C"},
    "B": {"SW": "A", "NE": "D", "E": "E"},
    "C": {"NW": "A", "E": "F"},
    "D": {"SW": "B", "E": "G"},
    "E": {"W": "B", "S": "F", "E": "H"},
    "F": {"W": "C", "N": "E", "NE": "I"},
    "G": {"W": "D", "E": "J"},
    "H": {"W": "E", "S": "I", "E": "K"},
    "I": {"SW": "F", "N": "H", "E": "L"},
    "J": {"W": "G", "S": "K"},
    "K": {"W": "H", "N": "J", "S": "L"},
    "L": {"W": "I", "N": "K"},
}
PRIORITY = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
REVERSE = {"N": "S", "NE": "SW", "E": "W", "SE": "NW", "S": "N", "SW": "NE", "W": "E", "NW": "SE"}
EDGES = {tuple(sorted((node, target))) for node, exits in BEARINGS.items() for target in exits.values()}
EULER_MEMORY_ROUTE = ["A", "B", "D", "G", "J", "K", "H", "E", "B", "E", "F", "I", "L", "K", "H", "I", "F", "C", "A"]
DFS_BOUNDARY_ROUTE = ["A", "B", "D", "G", "J", "K", "L", "I", "H", "K", "H", "E", "F", "I", "F", "C", "A", "C", "F", "E", "B", "E", "H", "I", "L", "K", "J", "G", "D", "B", "A"]


def edge(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def route_metrics(route: list[str]) -> dict[str, Any]:
    traversals = [edge(a, b) for a, b in zip(route, route[1:])]
    if any(b not in BEARINGS[a].values() for a, b in zip(route, route[1:])):
        raise AssertionError(f"Hand route has a non-edge: {route}")
    edge_counts = Counter(traversals)
    node_counts = Counter(route)
    return {
        "movement_steps": len(route) - 1,
        "final_node": route[-1],
        "target_first_visited_at_step": route.index("L") if "L" in route else None,
        "unique_nodes_seen": len(set(route)),
        "unique_edges_traversed": len(edge_counts),
        "repeated_node_visits": sum(count - 1 for count in node_counts.values()),
        "repeated_edge_traversals": len(traversals) - len(edge_counts),
        "edge_counts": edge_counts,
    }


def shortest_paths(start: str, goal: str) -> tuple[int, int, list[str]]:
    queue = deque([start])
    distance = {start: 0}
    ways = {start: 1}
    parent: dict[str, str] = {}
    while queue:
        node = queue.popleft()
        for target in BEARINGS[node].values():
            if target not in distance:
                distance[target] = distance[node] + 1
                ways[target] = ways[node]
                parent[target] = node
                queue.append(target)
            elif distance[target] == distance[node] + 1:
                ways[target] += ways[node]
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    return distance[goal], ways[goal], list(reversed(path))


def public_observation(node: str, movement_steps: int, inspected: bool, active_goal: str,
                       journal: list[dict[str, Any]], terminal: bool = False,
                       reason: str | None = None) -> dict[str, Any]:
    return {
        "movement_steps": movement_steps,
        "current_coarse_silhouette": SIGNS[node][1],
        "visible_exit_bearings": list(BEARINGS[node]),
        "inspected_current_sign_detail": {"sign_id": SIGNS[node][0], "distinctive_feature": SIGNS[node][2]} if inspected else None,
        "active_goal_marker": active_goal,
        "agent_authored_memory_journal": journal,
        "terminal": terminal,
        "terminal_reason": reason,
    }


def audit_routes(source: dict[str, Any]) -> dict[str, Any]:
    strategies = source["strategies"]
    greedy = strategies["no_memory_local_priority"]["node_route_first_30_moves"]
    expected_greedy = ["A"]
    for _ in range(30):
        node = expected_greedy[-1]
        bearing = next(direction for direction in PRIORITY if direction in BEARINGS[node])
        expected_greedy.append(BEARINGS[node][bearing])
    greedy_metrics = route_metrics(greedy)
    if greedy != expected_greedy or greedy_metrics["movement_steps"] != 30 or "L" in greedy or greedy[-1] != "J":
        raise AssertionError("No-memory fixed-bearing baseline must reproduce its J-K cycle and miss L")
    for key, value in strategies["no_memory_local_priority"]["expected"].items():
        metric_key = {"final_node": "final_node", "unique_nodes_seen": "unique_nodes_seen",
                      "unique_edges_traversed": "unique_edges_traversed", "repeated_node_visits": "repeated_node_visits",
                      "repeated_edge_traversals": "repeated_edge_traversals"}.get(key)
        if metric_key and greedy_metrics[metric_key] != value:
            raise AssertionError(f"No-memory baseline metric mismatch for {key}")

    tour = strategies["external_graph_memory_euler_tour"]
    route = tour["node_route"]
    metrics = route_metrics(route)
    direction_path = [next(direction for direction, target in BEARINGS[a].items() if target == b) for a, b in zip(route, route[1:])]
    if direction_path != tour["directions"]:
        raise AssertionError("Hand-authored memory tour direction table disagrees with signposts")
    if metrics["movement_steps"] != 18 or metrics["final_node"] != "A" or metrics["target_first_visited_at_step"] != 12 or set(route) != set(BEARINGS) or set(metrics["edge_counts"]) != EDGES:
        raise AssertionError("18-step external memory route must visit L and traverse every node/edge before returning")
    repeated = sorted("-".join(e) for e, count in metrics["edge_counts"].items() if count > 1)
    if repeated != sorted(tour["repeated_edges"]) or len(repeated) != 3 or metrics["repeated_node_visits"] != 7:
        raise AssertionError("Memory-tour repeated-edge/node audit differs from the hand ledger")
    if tour["memory_facts_written"] != {"node_pages": 12, "edge_pages": 15, "total": 27}:
        raise AssertionError("Full graph memory should require 27 visited-evidence facts")

    complete = strategies["complete_map_upper_bound"]["node_route"]
    distance, ways, shortest = shortest_paths("A", "L")
    if distance != 4 or ways != 1 or shortest != ["A", "C", "F", "I", "L"] or complete != shortest + shortest[-2::-1]:
        raise AssertionError("Complete-map upper-bound route must be the unique hand-checked 8-step round trip")
    disjoint_a = ["A", "C", "F", "I", "L"]
    disjoint_b = ["A", "B", "E", "H", "K", "L"]
    if set(disjoint_a[1:-1]) & set(disjoint_b[1:-1]) or any(edge(a, b) not in EDGES for path in (disjoint_a, disjoint_b) for a, b in zip(path, path[1:])):
        raise AssertionError("Two claimed A-L internally disjoint routes must be physically valid")

    dfs = strategies["depth_first_exact_30_boundary"]["node_route"]
    dfs_metrics = route_metrics(dfs)
    if dfs != DFS_BOUNDARY_ROUTE or dfs_metrics["movement_steps"] != 30 or dfs[-1] != "A" or dfs.index("L") != 6:
        raise AssertionError("DFS boundary witness must meet the exact 30-step endpoint")
    if set(dfs_metrics["edge_counts"]) != EDGES or any(count != 2 for count in dfs_metrics["edge_counts"].values()):
        raise AssertionError("The 30-step DFS route must traverse every unique edge exactly out-and-back")

    cases = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    if cases["boundary_cases"][0]["hand_plan"] != "depth_first_exact_30_boundary" or cases["boundary_cases"][1]["failure_case"] != "F03":
        raise AssertionError("Boundary cases must reference the authored exact-cap and one-step-late routes")
    case_f1 = cases["cases"][0]
    f1 = route_metrics(case_f1["node_route"])
    if case_f1["node_route"] != greedy or f1["movement_steps"] != 30 or f1["final_node"] != "J" or "L" in case_f1["node_route"]:
        raise AssertionError("F01 local loop must match the fixed no-memory baseline")
    f2 = route_metrics(cases["cases"][1]["node_route"])
    if f2["movement_steps"] != 30 or f2["final_node"] != "H" or "L" not in cases["cases"][1]["node_route"] or f2["final_node"] == "A":
        raise AssertionError("F02 must have visited L yet end away from camp at the cap")
    f3_case = cases["cases"][2]
    f3_route = f3_case["node_route_planned_including_unaccepted_last_step"]
    f3 = route_metrics(f3_route[:31])
    if len(f3_route) - 1 != 31 or f3["movement_steps"] != 30 or f3["final_node"] != "C" or f3["target_first_visited_at_step"] != 27 or f3_route[-1] != "A":
        raise AssertionError("F03 must need the unaccepted 31st move from C to A")
    if BEARINGS["I"].get("N") != "H" or BEARINGS["I"].get("SW") != "F":
        raise AssertionError("F02 wrong-turn explanation must match the I sign's two distinct exits")
    if list(BEARINGS["K"]) != cases["boundary_cases"][2]["expected_visible_bearings"]:
        raise AssertionError("B03 local-bearings boundary must be exact")

    return {
        "fixed_graph": {"nodes": len(BEARINGS), "edges": len(EDGES), "cycle_rank": len(EDGES) - len(BEARINGS) + 1},
        "path_redundancy": {"unique_shortest_A_to_L": shortest, "distance": distance,
                            "shortest_path_count": ways, "internally_vertex_disjoint_paths": 2,
                            "alternate_path": disjoint_b, "alternate_length": len(disjoint_b) - 1},
        "no_memory_local_priority": {"steps": f1["movement_steps"], "final": f1["final_node"],
                                     "nodes": f1["unique_nodes_seen"], "unique_edges": f1["unique_edges_traversed"],
                                     "repeated_edges": f1["repeated_edge_traversals"], "success": False},
        "external_graph_memory": {"steps": metrics["movement_steps"], "target_first_step": metrics["target_first_visited_at_step"],
                                  "unique_nodes": metrics["unique_nodes_seen"], "unique_edges": metrics["unique_edges_traversed"],
                                  "repeat_node_visits": metrics["repeated_node_visits"], "repeated_edges": repeated,
                                  "memory_facts": 27, "success": True},
        "complete_map_upper_bound": {"steps": distance * 2, "route_is_unique_shortest": True},
        "depth_first_boundary": {"steps": dfs_metrics["movement_steps"], "target_first_step": dfs_metrics["target_first_visited_at_step"],
                                 "unique_nodes": dfs_metrics["unique_nodes_seen"], "unique_edges": dfs_metrics["unique_edges_traversed"], "success": True},
        "failures": {"F01": {"steps": 30, "end": f1["final_node"], "target_visited": False},
                     "F02": {"steps": 30, "end": f2["final_node"], "target_visited": True},
                     "F03": {"accepted_steps": 30, "end": f3["final_node"], "planned_return_step": 31}},
    }


def audit_public_spec(spec: dict[str, Any]) -> None:
    if spec["status"] not in ("DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME") or spec["runtime_verified"] is not False:
        raise AssertionError("Map design audit must retain pending-runtime status")
    topology = spec["topology"]["nodes"]
    if set(topology) != set(BEARINGS):
        raise AssertionError("Topology must contain exactly the manually fixed A-L node set")
    seen_ids: set[str] = set()
    for node, spec_node in topology.items():
        sign_id, silhouette, feature = SIGNS[node]
        if spec_node["sign_id"] != sign_id or spec_node["coarse_silhouette"] != silhouette or spec_node["distinctive_feature"] != feature or spec_node["exits"] != BEARINGS[node]:
            raise AssertionError(f"Sign, visible bearing, or graph mismatch at node {node}")
        if sign_id in seen_ids:
            raise AssertionError("Every manually placed signpost must have a unique inspected mark")
        seen_ids.add(sign_id)
    for node, exits in BEARINGS.items():
        for bearing, neighbor in exits.items():
            if BEARINGS[neighbor].get(REVERSE[bearing]) != node:
                raise AssertionError(f"Signpost route {node}:{bearing}->{neighbor} has no reciprocal return direction")
    if len(EDGES) != 15 or spec["topology"]["undirected_edge_count"] != len(EDGES) or spec["topology"]["graph_cycle_rank"] != 4:
        raise AssertionError("Fixed graph edge count or cycle-rank discrepancy")
    if spec["movement_step_limit"] != 30 or spec["topology"]["shortest_A_to_L_path"] != ["A", "C", "F", "I", "L"]:
        raise AssertionError("Movement cap or precomputed target path differs from the graph")
    if spec["memory"]["maximum_facts"] != 32 or spec["memory"]["evidence_gate"] != "may_write_only_current_inspection_or_edge_traversed_on_most_recent_move":
        raise AssertionError("External memory must stay evidence-gated and fit the full observed graph")
    if spec["signpost_observation"]["never_shows_neighbor_sign_ids"] is not True or spec["memory"]["complete_adjacency_request_supported"] is not False:
        raise AssertionError("Local observation must not leak the complete adjacency list")
    forbidden_observation_words = ("canonical_node_id", "complete_adjacency", "neighbor_sign_ids", "unvisited_node")
    if any(any(word in field for word in forbidden_observation_words) for field in spec["observation_fields"]):
        raise AssertionError("Observation schema contains a forbidden global-map or unvisited-node field")
    if spec["evaluation_tracks"][0]["fixed_bearing_priority"] != PRIORITY:
        raise AssertionError("No-memory baseline must use the explicitly listed fixed local bearing priority")


def render_oracle(spec: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    route = EULER_MEMORY_ROUTE
    node_cards: set[str] = set()
    edge_cards: set[tuple[str, str]] = set()
    journal: list[dict[str, Any]] = []
    current = "A"
    step = 0
    goal_visited = False
    active_goal = "RUIN_TRIPLE_ARCH"
    inspected = False
    terminal = False
    terminal_reason: str | None = None
    rows: list[dict[str, Any]] = []

    # Initial node card is deliberately written from the first local inspection.
    pre_actions: list[dict[str, Any]] = [{"action": "observe_signpost", "result": SIGNS[current][0:3]}]
    journal.append({"fact_type": "node_page", "sign_id": SIGNS[current][0], "exit_bearings": list(BEARINGS[current])})
    node_cards.add(current)
    pre_actions.append({"action": "write_memory", "fact": journal[-1]})
    inspected = True

    for source, destination in zip(route, route[1:]):
        if current != source:
            raise AssertionError("Euler Oracle route state drift")
        before = public_observation(current, step, inspected, active_goal, journal, terminal, terminal_reason)
        direction = next(bearing for bearing, neighbor in BEARINGS[current].items() if neighbor == destination)
        step += 1
        current = destination
        inspected = False
        actions_after: list[dict[str, Any]] = [{"action": "observe_signpost", "result": SIGNS[current][0:3]}]
        if current not in node_cards:
            fact = {"fact_type": "node_page", "sign_id": SIGNS[current][0], "exit_bearings": list(BEARINGS[current])}
            journal.append(fact)
            node_cards.add(current)
            actions_after.append({"action": "write_memory", "fact": fact})
        traversed = edge(source, destination)
        if traversed not in edge_cards:
            origin_direction = direction
            reverse_direction = REVERSE[direction]
            fact = {"fact_type": "traversed_edge_page", "from_sign_id": SIGNS[source][0],
                    "departure_bearing": origin_direction, "to_sign_id": SIGNS[destination][0],
                    "arrival_reverse_bearing": reverse_direction}
            journal.append(fact)
            edge_cards.add(traversed)
            actions_after.append({"action": "write_memory", "fact": fact})
        inspected = True
        if current == "L":
            goal_visited = True
            actions_after.append({"action": "check_goal", "result": True})
            active_goal = "CAMP_LANTERN_RING"
            actions_after.append({"action": "return_to_camp", "moved": False})
        if current == "A" and goal_visited and step <= 30:
            terminal = True
            terminal_reason = "RETURNED_TO_CAMP_WITH_RUIN_RECORD"
        after = public_observation(current, step, inspected, active_goal, journal, terminal, terminal_reason)
        rows.append({"movement_step": step, "observation_before": before,
                     "auxiliary_actions_before_move": pre_actions if step == 1 else [],
                     "actions": [{"action": "move", "bearing": direction}],
                     "auxiliary_actions_after_arrival": actions_after,
                     "observation_after": after})
        if terminal:
            break

    if not terminal or len(rows) != 18 or len(node_cards) != 12 or len(edge_cards) != 15 or len(journal) != 27:
        raise AssertionError("Public external-memory Oracle must gradually learn all evidence and return at step 18")
    fields = set(spec["observation_fields"])
    forbidden = ("canonical_node_id", "complete_adjacency_table", "unvisited_node_features", "auto_return_route")
    for row in rows:
        for key in ("observation_before", "observation_after"):
            obs = row[key]
            if set(obs) != fields:
                raise AssertionError(f"Oracle observation schema mismatch: {set(obs) ^ fields}")
            serialized = json.dumps(obs, ensure_ascii=False).lower()
            if any(value in serialized for value in forbidden):
                raise AssertionError("Oracle includes forbidden private navigation data")
    return rows


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    audit_public_spec(spec)
    source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    metrics = audit_routes(source)
    rows = render_oracle(spec, metrics)
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    reference = {"map_id": "MAP-22", "kind": "offline_topology_and_memory_policy_comparison",
                 "fixed_graph_internal_reference_only": {"nodes": list(BEARINGS), "edges": sorted("-".join(e) for e in EDGES),
                                                          "bearings": BEARINGS},
                 **metrics,
                 "oracle_memory_facts_by_return": {"node_pages": 12, "edge_pages": 15, "total": 27},
                 "public_oracle_rows": len(rows), "runtime_verified": False,
                 "no_memory_result_is_a_fixed_reactive_baseline_not_a_universal_lower_bound": True}
    (ROOT / "planning" / "graph_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "HAND_AUTHORED_MAP22_TOPOLOGY_MEMORY_AND_RETURN_PATHS_REPLAYED",
                      "runtime_verified": False, "graph": metrics["fixed_graph"],
                      "no_memory": metrics["no_memory_local_priority"],
                      "external_graph_memory": metrics["external_graph_memory"],
                      "complete_map_upper_bound": metrics["complete_map_upper_bound"],
                      "depth_first_boundary": metrics["depth_first_boundary"],
                      "failures": metrics["failures"], "oracle_rows": len(rows),
                      "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
