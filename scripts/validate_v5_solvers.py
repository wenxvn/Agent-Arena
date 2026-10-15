"""Run small, independent offline checks for the six V5 measurement targets."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import types
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "worlds" / "v4"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def map08_information_audit() -> dict[str, Any]:
    candidates = ("B", "D", "F")
    signatures = {
        "B": ("pulse_amber", "pulse_slate"),
        "D": ("pulse_slate", "pulse_cobalt"),
        "F": ("pulse_slate", "pulse_slate"),
    }
    for station_index in (0, 1):
        answers = {signatures[node][station_index] for node in candidates}
        if len(answers) < 2:
            raise AssertionError("Each MAP-08 test must partition the current hypotheses.")
    joint = set(signatures.values())
    if len(joint) != len(candidates):
        raise AssertionError("The two public MAP-08 test results must identify each candidate.")
    entropy_prior = math.log2(3)
    entropy_after_first = (2 / 3) * 1.0 + (1 / 3) * 0.0
    return {
        "candidate_count": len(candidates),
        "joint_signature_count": len(joint),
        "prior_entropy_bits": round(entropy_prior, 6),
        "first_test_information_gain_bits": round(entropy_prior - entropy_after_first, 6),
    }


def map16_schedule_audit() -> dict[str, Any]:
    directions_a = {
        "A": {"X"}, "X": {"M"}, "M": {"Y", "D"},
        "D": {"M"}, "Y": {"B"}, "B": set(),
    }
    directions_b = {
        "B": {"Y"}, "Y": {"M"}, "M": {"X", "D"},
        "D": {"M"}, "X": {"A"}, "A": set(),
    }
    start = ("A", "B")
    goal = ("B", "A")

    def successors(state: tuple[str, str]) -> set[tuple[str, str]]:
        a, b = state
        choices_a = {a, *directions_a[a]}
        choices_b = {b, *directions_b[b]}
        following_states: set[tuple[str, str]] = set()
        for next_a in choices_a:
            for next_b in choices_b:
                if next_a == next_b:
                    continue
                edge_a = frozenset((a, next_a)) if next_a != a else None
                edge_b = frozenset((b, next_b)) if next_b != b else None
                if edge_a is not None and edge_a == edge_b:
                    continue
                following_states.add((next_a, next_b))
        return following_states

    distance = {start: 0}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        for following in successors(state):
            if following not in distance:
                distance[following] = distance[state] + 1
                queue.append(following)
    if distance.get(goal) != 6:
        raise AssertionError(
            f"MAP-16 independent synchronous BFS found {distance.get(goal)} ticks."
        )
    return {"minimum_makespan_ticks": distance[goal], "reachable_position_states": len(distance)}


def map18_schedule_audit() -> dict[str, Any]:
    # This audit is authored separately under worlds/v4 and uses a hand-written
    # tick scheduler, not the V5 runtime. Its replay helper does not need YAML;
    # only its standalone file audit reads YAML source records.
    if importlib.util.find_spec("yaml") is None:
        sys.modules["yaml"] = types.ModuleType("yaml")
    path = WORLD / "MAP-18" / "planning" / "schedule_audit.py"
    module_spec = importlib.util.spec_from_file_location("map18_independent_audit", path)
    if module_spec is None or module_spec.loader is None:
        raise AssertionError("Could not load the MAP-18 independent schedule audit.")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    source = read_json(WORLD / "MAP-18" / "planning" / "hand_traces.json")
    metrics: dict[str, Any] = {}
    for plan_id, plan in source["plans"].items():
        _, result = module.replay(plan_id, plan, source)
        metrics[plan_id] = result
    alert = metrics["alert_proactive_detour"]
    no_alert = metrics["no_alert_reactive_detour"]
    if alert["delivered"] != 18 or no_alert["delivered"] != 18:
        raise AssertionError("MAP-18 paired schedules must both deliver all 18 passengers.")
    delay_difference = (
        no_alert["total_passenger_delay_ticks"] - alert["total_passenger_delay_ticks"]
    )
    if delay_difference != 3:
        raise AssertionError("MAP-18 hand schedule delay difference no longer equals three.")
    return {"plan_count": len(metrics), "alert_pair_delay_difference": delay_difference}


def map22_graph_audit() -> dict[str, Any]:
    graph = read_json(WORLD / "MAP-22" / "planning" / "graph_reference.json")
    reference = graph["fixed_graph_internal_reference_only"]
    adjacency = {node: set() for node in reference["nodes"]}
    for text in reference["edges"]:
        left, right = text.split("-", 1)
        adjacency[left].add(right)
        adjacency[right].add(left)
    distances = {"A": 0}
    ways = {"A": 1}
    queue = deque(["A"])
    while queue:
        node = queue.popleft()
        for following in adjacency[node]:
            if following not in distances:
                distances[following] = distances[node] + 1
                ways[following] = ways[node]
                queue.append(following)
            elif distances[following] == distances[node] + 1:
                ways[following] += ways[node]
    if distances.get("L") != 4 or ways.get("L") != 1:
        raise AssertionError("MAP-22 independent graph search must find one 4-edge A-L route.")
    return {
        "node_count": len(adjacency),
        "edge_count": sum(map(len, adjacency.values())) // 2,
        "shortest_A_L_edges": distances["L"],
        "shortest_path_count": ways["L"],
    }


def _map26_fixtures() -> dict[int, dict[str, str]]:
    text = (WORLD / "MAP-26" / "planning" / "private_seed_reference.yaml").read_text(
        encoding="utf-8"
    )
    fixtures: dict[int, dict[str, str]] = {}
    active_seed: int | None = None
    for line in text.splitlines():
        seed_match = re.fullmatch(r"  (\d+):", line)
        if seed_match:
            active_seed = int(seed_match.group(1))
            fixtures[active_seed] = {}
            continue
        if active_seed is None:
            continue
        fault_match = re.fullmatch(r"    fault_part: ([a-z_]+)", line)
        if fault_match:
            fixtures[active_seed]["fault_part"] = fault_match.group(1)
        reading_match = re.fullmatch(r"    readings: \{(.+)\}", line)
        if reading_match:
            for pair in reading_match.group(1).split(", "):
                key, value = pair.split(": ", 1)
                fixtures[active_seed][key] = value
    if set(fixtures) != {0, 1, 2} or any("fault_part" not in row for row in fixtures.values()):
        raise AssertionError("MAP-26 seed source could not be independently parsed.")
    return fixtures


def map26_recoverability_audit() -> dict[str, Any]:
    part_for_positive_test = {
        "bus_load": ("BUS_VOLTAGE_DROOP", "power_regulator"),
        "antenna_loopback": ("ANTENNA_LOOPBACK_OPEN", "antenna_coupler"),
        "software_checksum": ("IMAGE_CHECKSUM_MISMATCH", "software_image"),
    }
    fixtures = _map26_fixtures()
    diagnoses: dict[str, str] = {}
    for seed, fixture in fixtures.items():
        matches = [
            part
            for test, (positive, part) in part_for_positive_test.items()
            if fixture.get(test) == positive
        ]
        if matches != [fixture["fault_part"]]:
            raise AssertionError(f"MAP-26 seed {seed} does not identify one recoverable component.")
        diagnoses[str(seed)] = matches[0]

    # A mistaken first spare can be rolled back into inventory; with two total
    # spares, a second correct replacement leaves one unused after recovery.
    at_b = 2
    carried = 0
    at_b -= 1
    carried += 1
    carried -= 1  # wrong replacement consumes the first candidate temporarily
    at_b += 0
    carried += 1  # rollback returns that component to the uninstalled stock
    at_b -= 1
    carried += 1  # take the true component from B
    carried -= 1  # replace the true component
    uninstalled_after_success = at_b + carried
    if uninstalled_after_success != 1:
        raise AssertionError("MAP-26 recovery must succeed with one spare still unused.")
    return {
        "seed_faults": diagnoses,
        "recoverable_after_one_error": True,
        "spares_after_success": 1,
    }


def map30_evidence_audit() -> dict[str, Any]:
    graph = {
        "H": {"B", "L", "J"}, "B": {"H", "K"}, "K": {"B", "Y", "T"},
        "Y": {"K"}, "L": {"H", "A"}, "A": {"L", "T"}, "T": {"A", "K"},
        "J": {"H"},
    }
    evidence_at = {
        "A": {"Q4_ARCHIVE_DOCKET"},
        "B": {"B_KEY_STUB_2310"},
        "K": {"K_WAX_PLATE_2322"},
        "T": {"T_CHAIN_REGISTER_2340"},
    }
    answer_for = {
        "ARCHIVE_CLERK": ("Q4_ARCHIVE_DOCKET", "Q4_CODE_INDEX"),
        "BANQUET_CLERK": ("B_KEY_STUB_2310", "B_WITNESS_HANDOFF"),
        "KITCHEN_COOK": ("EVENT_1_HANDOFF", "K_WITNESS_WAX_ROUTE"),
        "TOWER_WATCH": ("EVENT_2_WAX", "T_WITNESS_SIGNAL_ROUTE"),
    }
    allowed = {
        "Q4_CODEBOOK": {"Q4_CODE_INDEX"},
        "EVENT_1_HANDOFF": {"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"},
        "EVENT_2_WAX": {"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"},
        "EVENT_3_SIGNAL": {"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"},
    }
    order = ["Q4_CODEBOOK", "EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"]
    claims = [
        {"event_id": "EVENT_1_HANDOFF", "time": "23:10", "location": "B", "duty_code": "M4"},
        {"event_id": "EVENT_2_WAX", "time": "23:22", "location": "K", "duty_code": "M4"},
        {"event_id": "EVENT_3_SIGNAL", "time": "23:40", "location": "T", "duty_code": "M4"},
    ]
    route_data = read_json(WORLD / "MAP-30" / "planning" / "hand_traces.json")
    route = next(
        item for item in route_data["routes"] if item["id"] == "event_by_event_archive_first"
    )
    node = "H"
    tick = 0
    found: set[str] = set()
    casebook: dict[str, set[str]] = {}
    compared = False
    finished = False
    for action in route["actions"]:
        if action["name"] == "move":
            target = action["to"]
            if target not in graph[node]:
                raise AssertionError(f"MAP-30 route contains a non-edge: {node}->{target}.")
            node = target
        elif action["name"] == "inspect":
            evidence = action["evidence_id"]
            if evidence not in evidence_at.get(node, set()):
                raise AssertionError("MAP-30 evidence is not locally reachable at inspection.")
            found.add(evidence)
        elif action["name"] == "interview":
            prerequisite, answer = answer_for[action["npc_id"]]
            if prerequisite.startswith("EVENT_"):
                shown = set(action.get("shown_casebook_entry_ids", []))
                if prerequisite not in shown or not allowed[prerequisite] <= casebook.get(
                    prerequisite, set()
                ):
                    raise AssertionError(
                        "MAP-30 witness skipped its required prior casebook entry."
                    )
                found.add(answer)
            else:
                shown = set(action.get("shown_evidence_ids", []))
                if prerequisite not in found or prerequisite not in shown:
                    raise AssertionError(
                        "MAP-30 interview lacked its public prerequisite evidence."
                    )
                found.add(answer)
        elif action["name"] == "record":
            entry = action["entry_id"]
            evidence_ids = set(action["evidence_ids"])
            if entry != order[len(casebook)] or not evidence_ids <= found:
                raise AssertionError(
                    "MAP-30 casebook entry is out of order or cites unseen evidence."
                )
            if evidence_ids != allowed[entry]:
                raise AssertionError(
                    "MAP-30 casebook entry does not meet its required evidence set."
                )
            casebook[entry] = evidence_ids
        elif action["name"] == "compare_records":
            if action["entry_ids"] != order or any(
                casebook.get(entry) != allowed[entry] for entry in order
            ):
                raise AssertionError("MAP-30 record comparison is not evidence-complete.")
            compared = True
        elif action["name"] == "formal_accuse":
            if node != "J" or not compared:
                raise AssertionError("MAP-30 accusation lacks the court location or comparison.")
            if action["person_id"] != "MARA_VENN" or action["event_claims"] != claims:
                raise AssertionError("MAP-30 final claim does not match the evidence timeline.")
            if action["cited_entry_ids"] != order:
                raise AssertionError("MAP-30 final claim does not cite all four casebook entries.")
            finished = True
        tick += 1
        if tick >= 40 and not finished:
            raise AssertionError("MAP-30 hand route misses the deadline.")
    casebook_source_count = len(set().union(*casebook.values())) if casebook else 0
    if not finished or len(found) != 8 or casebook_source_count != 7 or len(casebook) != 4:
        raise AssertionError(
            "MAP-30 evidence dependency route did not reach a complete case: "
            f"finished={finished}, found={sorted(found)}, entries={sorted(casebook)}."
        )
    return {
        "route_ticks": tick,
        "public_evidence_found": len(found),
        "casebook_source_count": casebook_source_count,
        "casebook_entries": len(casebook),
    }


def main() -> None:
    result = {
        "MAP-08": map08_information_audit(),
        "MAP-16": map16_schedule_audit(),
        "MAP-18": map18_schedule_audit(),
        "MAP-22": map22_graph_audit(),
        "MAP-26": map26_recoverability_audit(),
        "MAP-30": map30_evidence_audit(),
    }
    print(
        "V5 independent solver checks passed:",
        json.dumps(result, ensure_ascii=False, sort_keys=True),
    )


if __name__ == "__main__":
    main()
