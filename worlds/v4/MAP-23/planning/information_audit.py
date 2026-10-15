"""Replay MAP-23's manually authored clue partitions, supply routes, and variants."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "X_TRUE": {"truth": "X", "signals": {"N": "STONE_SPLIT", "R": "WATER_UPSTREAM_SINK", "H": "RIDGE_NORTH_WHITE_MARK"}},
    "Y_TRUE": {"truth": "Y", "signals": {"N": "STONE_SPLIT", "R": "WATER_TWIN_RIPPLES", "H": "RIDGE_CENTER_AMBER_MARK"}},
    "Z_TRUE": {"truth": "Z", "signals": {"N": "STONE_THREE_RINGS", "R": "WATER_TWIN_RIPPLES", "H": "RIDGE_LOW_BLACK_MARK"}},
}
GRAPH = {
    "A": {"N": 1, "R": 2, "H": 2},
    "N": {"A": 1, "X": 1, "Y": 2},
    "R": {"A": 2, "Y": 1, "Z": 2},
    "H": {"A": 2},
    "X": {"N": 1}, "Y": {"N": 2, "R": 1}, "Z": {"R": 2},
}
SCOUT_COST = 2
ENTRY_COST = {"X": 3, "Y": 2, "Z": 3}
STARTING_SUPPLY = 14
SCOUT_NODES = {"N", "R", "H"}
ENTRANCES = {"X", "Y", "Z"}


def support_for(site: str, signal: str, decoder: dict[str, Any]) -> set[str]:
    try:
        return set(decoder[site][signal])
    except KeyError as error:
        raise AssertionError(f"No public signal decoder for {site}:{signal}") from error


def public_observation(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_node": state["node"],
        "locally_visible_neighbors_and_supply_costs": dict(GRAPH[state["node"]]),
        "supply_remaining": state["supply"],
        "resupply_cache_available": state["cache_available"],
        "available_scout_stations": [site for site in SCOUT_NODES if site == state["node"] and site not in state["clues"]],
        "clues_received": dict(state["clues"]),
        "entrances_already_searched_false": sorted(state["false_entrances"]),
        "agent_marked_candidate": state["mark"],
        "terminal": state["terminal"],
        "terminal_reason": state["reason"],
    }


def contains_private_key(value: Any) -> bool:
    private_names = {"variant_id", "true_entrance", "private_truth", "unscouted_signals", "clue_profile_for_unscouted_sites"}
    if isinstance(value, dict):
        return any(str(key).lower() in private_names or contains_private_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_private_key(child) for child in value)
    return False


def simulate(actions: list[dict[str, Any]], variant_id: str, decoder: dict[str, Any], *, capture: bool = False) -> dict[str, Any]:
    variant = VARIANTS[variant_id]
    state: dict[str, Any] = {"node": "A", "supply": STARTING_SUPPLY, "cache_available": True,
                             "clues": {}, "false_entrances": set(), "investigated": set(), "mark": None,
                             "terminal": False, "reason": None, "success": False, "true_entrance_found": False,
                             "move_count": 0, "unique_nodes": {"A"}, "records": [], "research_signal_info": []}

    def end_for_empty_supply(true_found: bool) -> None:
        if state["supply"] == 0:
            state["terminal"] = True
            state["success"] = False
            state["reason"] = "SUPPLY_MUST_REMAIN_POSITIVE" if true_found else "SUPPLY_DEPLETED"

    for action in actions:
        if state["terminal"]:
            break
        before = public_observation(state)
        kind = action["action"]
        result: dict[str, Any] = {}
        if kind == "move":
            target = action["to"]
            cost = action["supply_cost"]
            if target not in GRAPH[state["node"]] or GRAPH[state["node"]][target] != cost or state["supply"] < cost:
                raise AssertionError(f"Unaffordable or invalid route {state['node']}->{target} at {state['supply']} supply")
            state["supply"] -= cost
            state["node"] = target
            state["move_count"] += 1
            state["unique_nodes"].add(target)
            result = {"arrived_at": target, "supply_spent": cost}
            end_for_empty_supply(true_found=False)
        elif kind == "scout":
            site = action["location"]
            cost = action["supply_cost"]
            if site != state["node"] or site not in SCOUT_NODES or site in state["clues"] or cost != SCOUT_COST or state["supply"] < cost:
                raise AssertionError(f"Invalid, repeated, or unaffordable scout at {site}")
            signal = variant["signals"][site]
            if action.get("expected_signal") is not None and action["expected_signal"] != signal:
                raise AssertionError(f"{variant_id} {site} signal mismatch")
            candidates = support_for(site, signal, decoder)
            if variant["truth"] not in candidates or len(candidates) == 0:
                raise AssertionError(f"Scout signal {site}:{signal} excluded the hidden truth")
            state["supply"] -= cost
            state["clues"][site] = signal
            result = {"signal": signal, "compatible_entrances": sorted(candidates), "supply_spent": cost}
            end_for_empty_supply(true_found=False)
        elif kind == "mark":
            if action["entrance"] not in ENTRANCES:
                raise AssertionError("A candidate marker must be X, Y, or Z")
            state["mark"] = action["entrance"]
            result = {"marked_candidate": state["mark"]}
        elif kind == "resupply":
            if state["node"] != "A" or not state["cache_available"] or state["supply"] >= STARTING_SUPPLY:
                raise AssertionError("Resupply is one use at A and refills only an undersupplied pack")
            previous = state["supply"]
            state["supply"] = STARTING_SUPPLY
            state["cache_available"] = False
            result = {"supply_before": previous, "supply_after": STARTING_SUPPLY, "cache_available": False}
        elif kind == "investigate":
            entrance = action["entrance"]
            cost = action["supply_cost"]
            if entrance not in ENTRANCES or state["node"] != entrance or entrance in state["investigated"] or cost != ENTRY_COST[entrance] or state["supply"] < cost:
                raise AssertionError(f"Invalid, repeated, or unaffordable investigation at {entrance}")
            state["supply"] -= cost
            state["investigated"].add(entrance)
            true_found = entrance == variant["truth"]
            result = {"entrance_result": "TRUE" if true_found else "FALSE", "supply_spent": cost}
            if true_found:
                state["true_entrance_found"] = True
                if state["supply"] > 0:
                    state["terminal"] = True
                    state["success"] = True
                    state["reason"] = "TRUE_ENTRANCE_FOUND"
                else:
                    end_for_empty_supply(true_found=True)
            else:
                state["false_entrances"].add(entrance)
                end_for_empty_supply(true_found=False)
        else:
            raise AssertionError(f"Unknown MAP23 action {kind}")

        after = public_observation(state)
        state["records"].append({"observation_before": before, "action": action, "action_result": result,
                                 "observation_after": after})
        if state["terminal"]:
            break

    if capture:
        state["trace"] = state["records"]
    return state


def check_policy_prefixes(paths: dict[str, list[dict[str, Any]]], decoder: dict[str, Any]) -> None:
    runs = {variant_id: simulate(actions, variant_id, decoder) for variant_id, actions in paths.items()}
    variants = list(paths)
    for left_index, left in enumerate(variants):
        for right in variants[left_index + 1:]:
            left_run, right_run = runs[left], runs[right]
            shared = min(len(left_run["records"]), len(right_run["records"]))
            for index in range(shared):
                left_record = left_run["records"][index]
                right_record = right_run["records"][index]
                if left_record["observation_before"] == right_record["observation_before"] and left_record["action"] != right_record["action"]:
                    raise AssertionError(f"Policy {left}/{right} branches on hidden truth before observing evidence at action {index}")
                # Public outcomes may diverge here; later actions can then follow that received evidence.
                if left_record["observation_after"] != right_record["observation_after"]:
                    break


def policy_summary(policy: dict[str, Any], decoder: dict[str, Any]) -> dict[str, Any]:
    paths = policy["variant_paths"]
    check_policy_prefixes(paths, decoder)
    per_variant = {}
    for variant_id, actions in paths.items():
        state = simulate(actions, variant_id, decoder)
        if state["success"] is not True or state["reason"] != "TRUE_ENTRANCE_FOUND":
            raise AssertionError(f"{variant_id} route did not find its true entrance with positive supply")
        if policy["expected"]["success_by_variant"].get(variant_id) is not True:
            raise AssertionError(f"{variant_id} success differs from the authored policy outcome table")
        expected = policy["expected"]["remaining_supply_by_variant"][variant_id]
        if state["supply"] != expected:
            raise AssertionError(f"{variant_id} route remaining supply {state['supply']} != authored {expected}")
        per_variant[variant_id] = {"remaining_supply": state["supply"], "probes": len(state["investigated"]),
                                   "move_count": state["move_count"], "unique_nodes": len(state["unique_nodes"]),
                                   "terminal_reason": state["reason"]}
    mean_supply = sum(value["remaining_supply"] for value in per_variant.values()) / len(per_variant)
    mean_probes = sum(value["probes"] for value in per_variant.values()) / len(per_variant)
    if not math.isclose(mean_supply, policy["expected"]["mean_remaining_supply"], abs_tol=1e-9) or not math.isclose(mean_probes, policy["expected"]["mean_entrance_probes"], abs_tol=1e-9):
        raise AssertionError("Equal-prior policy mean does not match hand-authored route ledger")
    return {"per_variant": per_variant, "mean_remaining_supply": mean_supply,
            "mean_entrance_probes": mean_probes, "success_probability": 1.0}


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    if spec["status"] not in ("DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME") or spec["runtime_verified"] is not False:
        raise AssertionError("Static information audit must retain pending-runtime status")
    decoder = spec["scouting"]["clue_decoder_visible_to_agent"]
    edges_from_spec = {}
    for edge in spec["topology"]["undirected_edges"]:
        pair = frozenset((edge["a"], edge["b"]))
        edges_from_spec[pair] = edge["supply_cost"]
    edges_from_audit = {frozenset((node, neighbor)): cost for node, neighbors in GRAPH.items() for neighbor, cost in neighbors.items()}
    if edges_from_spec != edges_from_audit:
        raise AssertionError("Hand-authored movement graph/costs disagree with map_spec")
    if spec["resources"]["initial"] != STARTING_SUPPLY or spec["resources"]["maximum"] != STARTING_SUPPLY:
        raise AssertionError("Starting/maximum supply must both be 14")
    if spec["entrances"]["direct_investigation_supply_cost"] != ENTRY_COST:
        raise AssertionError("Entrance exploration costs differ from the manual routes")

    private = yaml.safe_load((ROOT / "planning" / "private_variant_reference.yaml").read_text(encoding="utf-8"))
    if sum(row["prior_weight"] for row in private["variant_population"]) != 3 or {row["id"] for row in private["variant_population"]} != set(VARIANTS):
        raise AssertionError("Hidden variant prior must include three equal-weight scenarios")
    signal_changes: list[int] = []
    for row in private["variant_population"]:
        expected = VARIANTS[row["id"]]
        if row["true_entrance"] != expected["truth"] or row["signals"] != expected["signals"]:
            raise AssertionError(f"Private clue profile drift for {row['id']}")
        for site, signal in row["signals"].items():
            if support_for(site, signal, decoder) != set(decoder[site][signal]) or expected["truth"] not in support_for(site, signal, decoder):
                raise AssertionError(f"{row['id']} {site} signal excludes its true entrance")
    variant_rows = private["variant_population"]
    for left, right in zip(variant_rows, variant_rows[1:] + variant_rows[:1]):
        changed = sum(left["signals"][site] != right["signals"][site] for site in ("N", "R", "H"))
        if changed < 2 or left["true_entrance"] == right["true_entrance"]:
            raise AssertionError("A variant must change the true entry and synchronously rewrite at least two clue sites")
        signal_changes.append(changed)

    prior_entropy = math.log2(3)
    information: dict[str, Any] = {}
    for site in ("N", "R", "H"):
        signal_counts: dict[str, int] = {}
        for variant in VARIANTS.values():
            signal = variant["signals"][site]
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        outcome_entropy = -sum((count / 3) * math.log2(count / 3) for count in signal_counts.values())
        travel_cost = min(cost for cost in GRAPH["A"].values()) if site == "N" else GRAPH["A"][site]
        if site == "N":
            travel_cost = GRAPH["A"]["N"]
        total_info_cost = travel_cost + SCOUT_COST
        information[site] = {"signal_counts": signal_counts, "information_gain_bits": outcome_entropy,
                             "travel_plus_scout_supply": total_info_cost,
                             "bits_per_supply_including_travel": outcome_entropy / total_info_cost}
    if not math.isclose(information["N"]["information_gain_bits"], 0.9182958340544896, abs_tol=1e-12) or not math.isclose(information["R"]["information_gain_bits"], 0.9182958340544896, abs_tol=1e-12) or not math.isclose(information["H"]["information_gain_bits"], prior_entropy, abs_tol=1e-12):
        raise AssertionError("Local survey information gain differs from exact equal-prior partitions")
    direct_probe_ig = prior_entropy - (2 / 3) * math.log2(2)
    direct_probe_efficiency = direct_probe_ig / (GRAPH["A"]["N"] + GRAPH["N"]["X"] + ENTRY_COST["X"])

    plans = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))["policies"]
    results = {name: policy_summary(policy, decoder) for name, policy in plans.items()}

    failures = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    failure_results: dict[str, Any] = {}
    for case in failures["cases"]:
        state = {"node": "A", "supply": STARTING_SUPPLY, "cache_available": True}
        clues: dict[str, str] = {}
        false_entries: set[str] = set()
        marker: str | None = None
        terminal_reason = None
        for action in case["actions"]:
            if terminal_reason is not None:
                raise AssertionError(f"{case['id']}: route continues after terminal state {terminal_reason}")
            kind = action["action"]
            if kind == "move":
                if (state["node"] != action["from"] or GRAPH[state["node"]].get(action["to"]) != action["cost"]
                        or state["supply"] != action["supply_before"] or action["cost"] <= 0
                        or state["supply"] < action["cost"]):
                    raise AssertionError(f"{case['id']}: failure movement ledger mismatch")
                state["node"] = action["to"]
                state["supply"] -= action["cost"]
                if state["supply"] != action["supply_after"]:
                    raise AssertionError(f"{case['id']}: failure movement supply mismatch")
                if state["supply"] == 0:
                    terminal_reason = "SUPPLY_DEPLETED"
            elif kind == "scout":
                variant = VARIANTS[case["hidden_variant_private_for_audit"]]
                signal = variant["signals"][action["at"]]
                site = action["at"]
                if (site not in SCOUT_NODES or state["node"] != site or site in clues
                        or signal != action["signal"] or set(action["supports"]) != set(decoder[site].get(signal, []))
                        or signal not in decoder[site] or VARIANTS[case["hidden_variant_private_for_audit"]]["truth"] not in decoder[site][signal]
                        or state["supply"] != action["supply_before"] or action["cost"] != SCOUT_COST
                        or state["supply"] < action["cost"]):
                    raise AssertionError(f"{case['id']}: failure scout result mismatch")
                state["supply"] -= action["cost"]
                if state["supply"] != action["supply_after"]:
                    raise AssertionError(f"{case['id']}: failure scout supply mismatch")
                clues[site] = signal
                if state["supply"] == 0:
                    terminal_reason = "SUPPLY_DEPLETED"
            elif kind == "mark":
                if action["entrance"] not in ENTRANCES:
                    raise AssertionError(f"{case['id']}: invalid candidate marker")
                marker = action["entrance"]
            elif kind == "investigate":
                truth = VARIANTS[case["hidden_variant_private_for_audit"]]["truth"]
                entrance = action["entrance"]
                if (entrance not in ENTRANCES or state["node"] != entrance or entrance in false_entries
                        or state["supply"] != action["supply_before"] or action["cost"] != ENTRY_COST[entrance]
                        or state["supply"] < action["cost"]):
                    raise AssertionError(f"{case['id']}: failure investigation precondition mismatch")
                if (action["entrance"] == truth) != action["is_true_private"]:
                    raise AssertionError(f"{case['id']}: declared private truth/falsity mismatch")
                state["supply"] -= action["cost"]
                if state["supply"] != action["supply_after"]:
                    raise AssertionError(f"{case['id']}: investigation supply mismatch")
                if action["is_true_private"]:
                    terminal_reason = "TRUE_ENTRANCE_FOUND" if state["supply"] > 0 else "SUPPLY_MUST_REMAIN_POSITIVE"
                else:
                    false_entries.add(action["entrance"])
                    if state["supply"] == 0:
                        terminal_reason = "SUPPLY_DEPLETED"
            elif kind == "resupply":
                if (state["node"] != "A" or not state["cache_available"] or state["supply"] >= STARTING_SUPPLY
                        or state["supply"] != action["supply_before"] or action["refill_to"] != STARTING_SUPPLY
                        or action["cache_after"] != "unavailable"):
                    raise AssertionError(f"{case['id']}: resupply precondition mismatch")
                state["supply"] = action["refill_to"]
                state["cache_available"] = False
            else:
                raise AssertionError(f"{case['id']}: unknown failure action {kind}")
        expected = case["expected"]
        if case["id"] == "F02":
            if (state["node"] != "Z" or state["supply"] != 1 or GRAPH["Z"]["R"] <= state["supply"]
                    or clues["H"] != "RIDGE_NORTH_WHITE_MARK" or marker != "Z" or "Z" not in false_entries):
                raise AssertionError("F02 stranded state/clue does not match its concrete route")
            terminal_reason = "SUPPLY_STRANDED"
        if (terminal_reason != expected["terminal_reason"]
                or state["supply"] != expected.get("supply_after", expected.get("supply_remaining"))
                or state["node"] != expected.get("final_node", state["node"]) or expected.get("success") is not False):
            raise AssertionError(f"{case['id']}: failure terminal/inventory mismatch {terminal_reason} / {state['supply']}")
        if case["id"] == "F01" and ("X" in false_entries or "X" == state["node"] or expected.get("true_X_not_reached") is not True):
            raise AssertionError("F01 must exhaust at the false Y entrance without reaching true X")
        if case["id"] == "F03" and (state["cache_available"] or expected.get("cache_unavailable") is not True
                                      or expected.get("true_Z_not_reached") is not True):
            raise AssertionError("F03 must end without the used cache and without reaching true Z")
        failure_results[case["id"]] = {"terminal_reason": terminal_reason, "supply_remaining": state["supply"], "location": state["node"]}

    boundary_rows = {row["id"]: row for row in failures["boundary_cases"]}
    b01 = boundary_rows["B01"]["initial"]
    b02 = boundary_rows["B02"]["initial"]
    if b01["node"] != "Z" or b01["supply"] - ENTRY_COST["Z"] != 1 or b02["node"] != "Z" or b02["supply"] - ENTRY_COST["Z"] != 0:
        raise AssertionError("B01/B02 must straddle the strict-positive supply boundary")
    if boundary_rows["B01"]["expected"]["terminal_reason"] != "TRUE_ENTRANCE_FOUND" or boundary_rows["B02"]["expected"]["terminal_reason"] != "SUPPLY_MUST_REMAIN_POSITIVE":
        raise AssertionError("B01/B02 terminal codes disagree with the success predicate")

    private_seed = yaml.safe_load((ROOT / "planning" / "private_seed_reference.yaml").read_text(encoding="utf-8"))
    if private_seed["seed"] != 0 or private_seed["variant_id"] != "Z_TRUE" or private_seed["true_entrance"] != "Z":
        raise AssertionError("Seed0 private fixture must point to the Z variant")
    oracle_policy = plans["river_water_partition"]["variant_paths"]["Z_TRUE"]
    oracle_state = simulate(oracle_policy, "Z_TRUE", decoder, capture=True)
    if oracle_state["success"] is not True or oracle_state["supply"] != 1 or oracle_state["clues"].get("R") != private_seed["expected_river_signal"]:
        raise AssertionError("Canonical river-clue Oracle path must find Z with exactly one supply left")
    oracle_rows = []
    for record in oracle_state["records"]:
        for key in ("observation_before", "observation_after"):
            observation = record[key]
            if set(observation) != set(spec["public_observation_fields"]):
                raise AssertionError("Oracle public observation fields differ from map_spec")
            if contains_private_key(observation):
                raise AssertionError("Oracle leaks hidden variant/truth or unscouted information")
        oracle_rows.append(record)
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in oracle_rows), encoding="utf-8")

    reference = {"map_id": "MAP-23", "kind": "offline_exact_variant_and_supply_enumeration",
                 "variants_private_for_audit": VARIANTS, "equal_prior_weights": {key: 1 for key in VARIANTS},
                 "scout_information": information, "prior_entropy_bits": prior_entropy,
                 "direct_first_X_probe_information_gain_bits": direct_probe_ig,
                 "direct_first_X_probe_efficiency_bits_per_supply": direct_probe_efficiency,
                 "strategy_results": results, "failures": failure_results,
                 "variant_signal_changes_on_rotation": signal_changes,
                 "seed0_public_signal": private_seed["expected_river_signal"],
                 "seed0_public_oracle_actions": len(oracle_rows), "runtime_verified": False}
    (ROOT / "planning" / "information_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "HAND_AUTHORED_MAP23_INFORMATION_AND_SUPPLY_ROUTES_REPLAYED",
                      "runtime_verified": False, "information": information,
                      "direct_probe_efficiency_bits_per_supply": direct_probe_efficiency,
                      "strategy_means": {key: {"remaining_supply": value["mean_remaining_supply"],
                                                "entrance_probes": value["mean_entrance_probes"],
                                                "success_probability": value["success_probability"]}
                                         for key, value in results.items()},
                      "failures": failure_results, "oracle_rows": len(oracle_rows),
                      "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
