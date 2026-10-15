"""Replay MAP-21's authored evacuation choices and exact hidden-time utility table."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
HIDDEN_TICKS = [12, 16, 20]
PRIOR = [0.2, 0.5, 0.3]
EARLY_LIKELIHOOD = [0.8, 0.3, 0.1]
MEASUREMENT_POINTS = 2
SURVIVAL_POINTS = 100
SAMPLES = {
    "R_SURFACE_ASH": {"node": "R", "tier": "low", "ticks": 1, "plain": 5, "braced": 5},
    "W_LAYERED_CORE": {"node": "W", "tier": "medium", "ticks": 5, "plain": 12, "braced": 20},
    "S_DEEP_ISOTOPE": {"node": "S", "tier": "high", "ticks": 6, "plain": 40, "braced": 50},
}
EDGE_TICKS = {("O", "R"): 1, ("R", "W"): 2, ("W", "S"): 2, ("S", "E"): 2, ("O", "E"): 6}
EDGE_TICKS.update({(end, start): ticks for (start, end), ticks in list(EDGE_TICKS.items())})


def close(a: float, b: float, *, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def posterior_for(outcome: str) -> list[float]:
    likelihoods = EARLY_LIKELIHOOD if outcome == "EARLY_WARNING" else [1 - p for p in EARLY_LIKELIHOOD]
    marginal = sum(prior * likelihood for prior, likelihood in zip(PRIOR, likelihoods))
    return [prior * likelihood / marginal for prior, likelihood in zip(PRIOR, likelihoods)]


def measurement_marginals() -> dict[str, float]:
    return {
        "EARLY_WARNING": sum(p * likelihood for p, likelihood in zip(PRIOR, EARLY_LIKELIHOOD)),
        "LATE_WARNING": sum(p * (1 - likelihood) for p, likelihood in zip(PRIOR, EARLY_LIKELIHOOD)),
    }


def entropy(probabilities: list[float]) -> float:
    return -sum(value * math.log(value) for value in probabilities if value > 0)


def public_observation(state: dict[str, Any]) -> dict[str, Any]:
    node = state["node"]
    transit = state["transit"]
    location = f"IN_TRANSIT:{transit['from']}-{transit['to']}:{transit['progress']}/{transit['duration']}" if transit else node
    adjacent = [] if transit or node in ("E", "IN_TRANSIT") else [
        {"from": node, "to": end, "travel_ticks": duration}
        for (start, end), duration in EDGE_TICKS.items() if start == node
    ]
    local_tier = next((sample["tier"] for sample_id, sample in SAMPLES.items()
                       if sample["node"] == node and state["sample_id"] != sample_id), None)
    return {
        "elapsed_tick": state["elapsed"],
        "current_node_or_in_transit_edge": location,
        "available_adjacent_edges": adjacent,
        "measurement_available": not state["measurement_reserved"],
        "returned_measurement_if_any": state["measurement_outcome"],
        "posterior_over_eruption_ticks": list(state["posterior"]),
        "visible_local_sample_tier": local_tier,
        "reinforcement_kit_available": not state["reinforcement_reserved"],
        "carried_sample_tier": None if state["sample_id"] is None else SAMPLES[state["sample_id"]]["tier"],
        "terminal": state["terminal"],
        "terminal_reason": state["terminal_reason"],
        "terminal_score": state["score"],
    }


def simulate(operations: list[dict[str, Any]], eruption_tick: int, measurement_outcome: str | None = None,
             *, capture_trace: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state: dict[str, Any] = {
        "elapsed": 0, "node": "O", "transit": None, "measurement_reserved": False,
        "measurement_outcome": None, "posterior": list(PRIOR), "measurement_points": 0,
        "reinforcement_reserved": False, "reinforced": False, "reinforced_node": None, "sample_id": None,
        "research_points": 0, "terminal": False, "terminal_reason": None, "score": None,
        "failure_tick": None,
    }
    rows: list[dict[str, Any]] = []

    for operation in operations:
        if state["terminal"]:
            break
        action = operation["action"]
        duration = operation["duration_ticks"]
        if action == "move":
            start, end = operation["from"], operation["to"]
            if state["node"] != start or (start, end) not in EDGE_TICKS or EDGE_TICKS[(start, end)] != duration:
                raise AssertionError(f"Illegal or mistimed edge traversal {start}->{end}/{duration}")
        elif action == "measure":
            if state["node"] != "O" or state["measurement_reserved"] or duration != 2 or measurement_outcome not in ("EARLY_WARNING", "LATE_WARNING"):
                raise AssertionError("Measurement must be a single two-tick O action with one specified signal")
            state["measurement_reserved"] = True
        elif action == "reinforce_sample_case":
            if state["node"] != operation["at"] or operation["at"] not in ("W", "S") or state["reinforcement_reserved"] or state["sample_id"] is not None or duration != 1:
                raise AssertionError("Sample-case reinforcement is one tick, one use, and precedes collection at W/S")
            state["reinforcement_reserved"] = True
        elif action == "collect_and_carry_sample":
            sample_id = operation["sample_id"]
            if sample_id not in SAMPLES or state["node"] != SAMPLES[sample_id]["node"] or state["sample_id"] is not None or duration != SAMPLES[sample_id]["ticks"]:
                raise AssertionError(f"Wrong sample location, carry limit, or collection duration for {sample_id}")
            if operation["reinforced"] != state["reinforced"]:
                raise AssertionError(f"Sample reinforcement flag disagrees with preceding actions for {sample_id}")
        else:
            raise AssertionError(f"Unknown timed action: {action}")

        for progress in range(1, duration + 1):
            before = public_observation(state)
            state["elapsed"] += 1
            if action == "move":
                if progress == duration:
                    state["node"] = operation["to"]
                    state["transit"] = None
                else:
                    state["transit"] = {"from": operation["from"], "to": operation["to"],
                                         "progress": progress, "duration": duration}
            elif action == "measure" and progress == duration:
                state["measurement_outcome"] = measurement_outcome
                state["posterior"] = posterior_for(measurement_outcome)
                state["measurement_points"] = MEASUREMENT_POINTS
            elif action == "reinforce_sample_case" and progress == duration:
                state["reinforced"] = True
                state["reinforced_node"] = operation["at"]
            elif action == "collect_and_carry_sample" and progress == duration:
                state["sample_id"] = operation["sample_id"]
                sample = SAMPLES[state["sample_id"]]
                if state["reinforced"] and sample["node"] != state["reinforced_node"]:
                    raise AssertionError("A sample case can only protect the sample at the node where it was reinforced")
                state["research_points"] = sample["braced"] if state["reinforced"] else sample["plain"]

            # Reaching E is resolved before an eruption on the same tick.
            if state["node"] == "E":
                state["terminal"] = True
                state["terminal_reason"] = "EVACUATED_BEFORE_ERUPTION"
                state["score"] = SURVIVAL_POINTS + state["measurement_points"] + state["research_points"]
            elif state["elapsed"] == eruption_tick:
                state["terminal"] = True
                state["terminal_reason"] = "FATAL_ERUPTION"
                state["failure_tick"] = state["elapsed"]
                state["score"] = 0

            after = public_observation(state)
            if capture_trace:
                rows.append({"tick": state["elapsed"] - 1,
                             "action": {key: value for key, value in operation.items() if key != "duration_ticks"},
                             "action_progress": {"elapsed_in_action": progress, "duration_ticks": duration},
                             "observation_before": before, "observation_after": after})
            if state["terminal"]:
                break
        if state["terminal"]:
            break

    if not state["terminal"]:
        raise AssertionError("Hand-authored action sequence ended without entering E or reaching the hidden eruption")
    return state, rows


def audit_spec(spec: dict[str, Any]) -> None:
    if spec["status"] not in ("DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME") or spec["runtime_verified"] is not False:
        raise AssertionError("Design audit must preserve the pending-runtime boundary")
    hidden = spec["hidden_state"]
    if hidden["eruption_tick_values"] != HIDDEN_TICKS or hidden["prior_probabilities"] != PRIOR or not hidden["eruption_tick_private"] or not hidden["no_public_countdown"]:
        raise AssertionError("Hidden eruption domain or privacy contract differs from the manual audit")
    if not close(sum(hidden["prior_probabilities"]), 1.0):
        raise AssertionError("Hidden-time prior must sum to one")
    measurement = spec["measurement"]
    if measurement["duration_ticks"] != 2 or measurement["uses_per_run"] != 1:
        raise AssertionError("Measurement timing/usage differs from the fixed likelihood model")
    likelihood = [measurement["likelihood_by_true_eruption_tick"][str(tick)]["EARLY_WARNING"] for tick in HIDDEN_TICKS]
    if likelihood != EARLY_LIKELIHOOD:
        raise AssertionError("Measurement likelihoods differ from the manual Bayes table")
    if any(not close(measurement["likelihood_by_true_eruption_tick"][str(tick)]["EARLY_WARNING"] + measurement["likelihood_by_true_eruption_tick"][str(tick)]["LATE_WARNING"], 1.0) for tick in HIDDEN_TICKS):
        raise AssertionError("Each hidden-time sensor likelihood row must sum to one")
    for (start, end), duration in EDGE_TICKS.items():
        if duration <= 0:
            raise AssertionError(f"Nonpositive traversal edge {start}->{end}")
    expected_edges = {
        ("O", "R"): 1, ("R", "W"): 2, ("W", "S"): 2, ("S", "E"): 2, ("O", "E"): 6,
    }
    actual_edges: dict[tuple[str, str], int] = {}
    for edge in spec["topology"]["bidirectional_edges"].values():
        pair = (edge["from"], edge["to"])
        actual_edges[pair] = edge["travel_ticks"]
        actual_edges[(pair[1], pair[0])] = edge["travel_ticks"]
    symmetric_expected_edges = {**expected_edges, **{(end, start): ticks for (start, end), ticks in expected_edges.items()}}
    if actual_edges != symmetric_expected_edges:
        raise AssertionError("Hand-route travel graph differs from the authored topology")
    if {sample["id"] for sample in spec["samples"]["locations"]} != set(SAMPLES):
        raise AssertionError("Design spec and manual audit must enumerate the same one-of-each sample set")
    for sample in spec["samples"]["locations"]:
        hand_sample = SAMPLES[sample["id"]]
        if (sample["node"], sample["collection_ticks"], sample["unreinforced_points"], sample["reinforced_points"]) != (
            hand_sample["node"], hand_sample["ticks"], hand_sample["plain"], hand_sample["braced"]
        ):
            raise AssertionError(f"Sample table differs between map spec and manual replay: {sample['id']}")
    reinforcement = spec["samples"]["reinforcement"]
    if reinforcement["duration_ticks"] != 1 or reinforcement["uses_per_run"] != 1 or set(reinforcement["locations"]) != {"W", "S"}:
        raise AssertionError("Reinforcement action use, time, or sample sites differ from the hand-authored rules")
    if spec["scoring"]["safe_evacuation_points"] != SURVIVAL_POINTS or spec["scoring"]["measurement_data_points_if_carried_to_E"] != MEASUREMENT_POINTS:
        raise AssertionError("Public score contract differs from the decision ledger")


def main() -> None:
    spec = yaml.safe_load((ROOT / "map_spec.yaml").read_text(encoding="utf-8"))
    audit_spec(spec)
    trace_source = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    plans = trace_source["plans"]

    plan_results: dict[str, Any] = {}
    for plan_id in ("blind_fast_evacuation", "quick_surface_sample_then_leave", "unreinforced_medium_sample_exact_boundary", "reinforced_medium_sample_misses_eruption_edge", "reinforced_high_value_sample_risk"):
        plan = plans[plan_id]
        per_hidden = {}
        for eruption_tick in HIDDEN_TICKS:
            state, _ = simulate(plan["operations"], eruption_tick)
            declared = plan["terminal_by_hidden_tick"][str(eruption_tick)]
            if state["score"] != declared["score"]:
                raise AssertionError(f"{plan_id} / T={eruption_tick}: score {state['score']} != authored {declared['score']}")
            if state["terminal_reason"] == "EVACUATED_BEFORE_ERUPTION" and state["elapsed"] != declared["arrival_tick"]:
                raise AssertionError(f"{plan_id} / T={eruption_tick}: arrival tick mismatch")
            if state["terminal_reason"] == "FATAL_ERUPTION" and state["failure_tick"] != declared["failure_tick"]:
                raise AssertionError(f"{plan_id} / T={eruption_tick}: failure tick mismatch")
            per_hidden[str(eruption_tick)] = {"score": state["score"], "terminal_reason": state["terminal_reason"],
                                              "elapsed_or_failure_tick": state["elapsed"]}
        expected_score = sum(PRIOR[index] * per_hidden[str(tick)]["score"] for index, tick in enumerate(HIDDEN_TICKS))
        expected_survival = sum(PRIOR[index] for index, tick in enumerate(HIDDEN_TICKS)
                                if per_hidden[str(tick)]["terminal_reason"] == "EVACUATED_BEFORE_ERUPTION")
        expected_research = sum(PRIOR[index] * (
            (per_hidden[str(tick)]["score"] - SURVIVAL_POINTS) if per_hidden[str(tick)]["terminal_reason"] == "EVACUATED_BEFORE_ERUPTION" else 0
        ) for index, tick in enumerate(HIDDEN_TICKS))
        if not close(expected_score, plan["expected"]["expected_score"]) or not close(expected_survival, plan["expected"]["survival_probability"]) or not close(expected_research, plan["expected"]["expected_research_points"]):
            raise AssertionError(f"{plan_id}: hand expectation does not match exact hidden-time enumeration")
        plan_results[plan_id] = {"per_hidden_tick": per_hidden, "expected_score": expected_score,
                                 "survival_probability": expected_survival, "expected_research_points": expected_research}

    policy = plans["measure_then_branch_by_posterior"]
    early_posterior = posterior_for("EARLY_WARNING")
    late_posterior = posterior_for("LATE_WARNING")
    if any(not close(a, b) for a, b in zip(early_posterior, policy["measurement"]["early_posterior"])) or any(not close(a, b) for a, b in zip(late_posterior, policy["measurement"]["late_posterior"])):
        raise AssertionError("Authored posterior does not equal Bayes' rule")
    marginals = measurement_marginals()
    branch_results: dict[str, Any] = {}
    expected_score = survival_probability = research_expectation = 0.0
    per_hidden_expectation: dict[str, float] = {}
    for index, eruption_tick in enumerate(HIDDEN_TICKS):
        hidden_expected = 0.0
        for outcome, early_probability in (("EARLY_WARNING", EARLY_LIKELIHOOD[index]), ("LATE_WARNING", 1 - EARLY_LIKELIHOOD[index])):
            branch = policy["branches"][outcome]
            operations = [{"action": "measure", "duration_ticks": 2}, *branch["operations"]]
            state, _ = simulate(operations, eruption_tick, outcome)
            declared_score = branch["terminal_scores_by_hidden_tick"][str(eruption_tick)]
            if state["score"] != declared_score:
                raise AssertionError(f"Measured branch {outcome} / T={eruption_tick}: score mismatch")
            joint_probability = PRIOR[index] * early_probability
            expected_score += joint_probability * state["score"]
            hidden_expected += early_probability * state["score"]
            if state["terminal_reason"] == "EVACUATED_BEFORE_ERUPTION":
                survival_probability += joint_probability
                research_expectation += joint_probability * (state["score"] - SURVIVAL_POINTS)
            branch_results[f"T{eruption_tick}_{outcome}"] = {"joint_probability": joint_probability,
                                                              "score": state["score"],
                                                              "terminal_reason": state["terminal_reason"],
                                                              "failure_tick": state["failure_tick"]}
        per_hidden_expectation[str(eruption_tick)] = hidden_expected

    if not close(expected_score, policy["enumeration"]["expected_score"]) or not close(survival_probability, policy["enumeration"]["survival_probability"]) or not close(research_expectation, policy["enumeration"]["expected_research_points"]):
        raise AssertionError("Measurement-then-branch expected utility is not the exact joint sum")
    if not close(branch_results["T12_LATE_WARNING"]["joint_probability"], policy["enumeration"]["fatal_joint_probability"]):
        raise AssertionError("False-late fatal joint probability differs from the declared 4%")

    prior_entropy = entropy(PRIOR)
    expected_posterior_entropy = sum(marginals[outcome] * entropy(posterior_for(outcome)) for outcome in marginals)
    information_gain = prior_entropy - expected_posterior_entropy
    if any(len([p for p in posterior_for(signal) if p > 0]) != 3 for signal in marginals):
        raise AssertionError("A sensor result must not reveal an exact hidden eruption time")

    failures = yaml.safe_load((ROOT / "failure_traces" / "cases.yaml").read_text(encoding="utf-8"))
    failure_results: dict[str, Any] = {}
    for case in failures["cases"]:
        eruption_tick = case["hidden_eruption_tick_private_for_audit"]
        outcome = case.get("measurement_outcome_private_for_audit")
        operations: list[dict[str, Any]] = []
        for authored in case["operations"]:
            duration = authored["tick_range"][1] - authored["tick_range"][0]
            action = authored["action"]
            if action == "move":
                start, end = authored["edge"].split("_")
                operations.append({"action": action, "from": start, "to": end, "duration_ticks": duration})
            elif action == "measure":
                operations.append({"action": action, "duration_ticks": duration})
            elif action == "reinforce_sample_case":
                operations.append({"action": action, "at": authored["at"], "duration_ticks": duration})
            elif action == "collect_and_carry_sample":
                operations.append({"action": action, "sample_id": authored["sample"], "reinforced": authored["reinforced"], "duration_ticks": duration})
            else:
                raise AssertionError(f"Unknown failure-case operation {action}")
        state, _ = simulate(operations, eruption_tick, outcome)
        if state["terminal_reason"] != case["expected"]["terminal_reason"] or state["failure_tick"] != case["expected"]["failure_tick"]:
            raise AssertionError(f"{case['id']}: authored failure replay disagrees with its event trace")
        if outcome is not None:
            hidden_index = HIDDEN_TICKS.index(eruption_tick)
            actual_likelihood = EARLY_LIKELIHOOD[hidden_index] if outcome == "EARLY_WARNING" else 1 - EARLY_LIKELIHOOD[hidden_index]
            if not close(actual_likelihood, case["measurement_likelihood"]):
                raise AssertionError(f"{case['id']}: failure signal does not use the fixed sensor likelihood")
        location = (f"IN_TRANSIT_{state['transit']['from']}_{state['transit']['to']}" if state["transit"] else state["node"])
        if case["expected"]["location_at_failure"] != location:
            raise AssertionError(f"{case['id']}: failure location differs from its action-level cause")
        failure_results[case["id"]] = {"failure_tick": state["failure_tick"], "terminal_reason": state["terminal_reason"],
                                        "location": location}

    b02, _ = simulate(plans["reinforced_medium_sample_misses_eruption_edge"]["operations"], 12)
    if b02["terminal_reason"] != "FATAL_ERUPTION" or b02["failure_tick"] != 12:
        raise AssertionError("B02: one added reinforcement tick must miss the earliest eruption boundary")
    if plan_results["unreinforced_medium_sample_exact_boundary"]["per_hidden_tick"]["12"]["terminal_reason"] != "EVACUATED_BEFORE_ERUPTION":
        raise AssertionError("B01: entering E at the exact eruption tick must resolve first")

    # The evaluation table remains offline. Public Oracle is the seed-0 measured path only.
    private = yaml.safe_load((ROOT / "planning" / "private_seed_reference.yaml").read_text(encoding="utf-8"))
    draw = private["hidden_time_uniform_draw"]
    selected_hidden_tick = 12 if draw < 0.2 else (16 if draw < 0.7 else 20)
    if selected_hidden_tick != private["hidden_eruption_tick"]:
        raise AssertionError("Seed-0 hidden-time fixture does not follow the declared prior intervals")
    early_probability = EARLY_LIKELIHOOD[HIDDEN_TICKS.index(private["hidden_eruption_tick"])]
    expected_signal = "EARLY_WARNING" if private["measurement_uniform_draw"] < early_probability else "LATE_WARNING"
    if private["expected_measurement"] != expected_signal:
        raise AssertionError("Private seed fixture signal does not follow the fixed likelihood draw")
    chosen_branch = policy["branches"][expected_signal]
    oracle_operations = [{"action": "measure", "duration_ticks": 2}, *chosen_branch["operations"]]
    oracle_state, oracle_rows = simulate(oracle_operations, private["hidden_eruption_tick"], expected_signal, capture_trace=True)
    if oracle_state["terminal_reason"] != "EVACUATED_BEFORE_ERUPTION" or oracle_state["elapsed"] != 15 or oracle_state["score"] != 122:
        raise AssertionError("Seed-0 public demonstration path should safely return the full medium sample at tick 15")
    public_keys = set(spec["observation_fields"])
    for row in oracle_rows:
        for field in ("observation_before", "observation_after"):
            observation = row[field]
            if set(observation) != public_keys:
                raise AssertionError(f"Public Oracle observation keys differ from contract: {set(observation) ^ public_keys}")
            serialized = json.dumps(observation, ensure_ascii=False).lower()
            if any(secret in serialized for secret in ("hidden_eruption_tick", "measurement_uniform_draw", "scoring_reference", "unrevealed_measurement_outcomes")):
                raise AssertionError("A hidden timing/scoring field leaked into the public Oracle")

    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in oracle_rows), encoding="utf-8")
    reference = {
        "map_id": "MAP-21", "kind": "offline_exact_hidden_time_and_signal_enumeration",
        "enumerated_hidden_eruption_ticks": HIDDEN_TICKS, "prior": PRIOR,
        "measurement_outcome_marginals": marginals,
        "posterior_after_early": early_posterior, "posterior_after_late": late_posterior,
        "prior_entropy_nats": prior_entropy, "expected_posterior_entropy_nats": expected_posterior_entropy,
        "measurement_information_gain_nats": information_gain,
        "measurement_information_gain_nats_per_tick": information_gain / 2,
        "strategy_results": plan_results,
        "measure_then_branch": {"per_hidden_tick_expected_score": per_hidden_expectation,
                                "expected_score": expected_score, "survival_probability": survival_probability,
                                "expected_research_points": research_expectation, "joint_branches": branch_results},
        "failure_replays": failure_results, "same_tick_e_arrival_precedes_eruption": True,
        "integer_or_global_optimum_claimed": False,
        "seed0_public_signal": expected_signal, "seed0_public_oracle_rows": len(oracle_rows),
        "runtime_verified": False,
    }
    ref_path = ROOT / "planning" / "decision_reference.json"
    ref_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "HAND_AUTHORED_MAP21_DECISION_PATHS_AND_EXACT_EXPECTATIONS_REPLAYED",
                      "runtime_verified": False, "strategy_expected_scores": {key: value["expected_score"] for key, value in plan_results.items()},
                      "measured_policy_expected_score": expected_score, "measured_policy_survival_probability": survival_probability,
                      "measurement_information_gain_nats": round(information_gain, 8),
                      "failure_cases": failure_results, "boundary_B01_tick12": "EVACUATED_BEFORE_ERUPTION",
                      "boundary_B02_tick12": b02["terminal_reason"], "oracle_rows": len(oracle_rows),
                      "oracle_sha256": hashlib.sha256(oracle_path.read_bytes()).hexdigest().upper()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
