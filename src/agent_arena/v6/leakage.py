"""Leakage counter-example checks for V6 instances.

Every check is a counter-example test: it fails if private truth, Oracle routes,
unlocked evidence, or future events can reach a prompt or an Agent-visible
Observation. Checks operate on the real environments and the V6 prompts.
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v6.catalog import build_environment, get_scene
from agent_arena.v6.prompts import v6_system_prompt
from agent_arena.v6.solvers import solve

# Public Observation fields per map (the allowlist). Any extra key is a leak.
_PUBLIC_FIELDS = {
    "MAP-08": {
        "map_id", "terminal", "terminal_reason", "location", "visible_edges", "current_tick",
        "current_core_water", "baseline_sensor_reading", "published_candidate_set",
        "published_prior", "known_test_semantics", "sealant_count", "test_results",
        "last_action_result",
    },
    "MAP-16": {
        "map_id", "terminal", "terminal_reason", "tick", "topology", "train_route_directions",
        "train_positions", "train_goals", "segment_capacities", "node_capacities",
        "occupied_nodes", "pending_route_reservations",
    },
    "MAP-18": {
        "map_id", "terminal", "terminal_reason", "tick", "ticks_remaining", "topology",
        "train_positions", "station_berths", "task_passenger_counts", "delivered_tasks",
        "canceled_tasks", "delivered_passengers", "canceled_passengers", "closed_segments",
        "current_train_locks", "published_dispatch_windows", "alert_message_if_any",
        "recovery_status",
    },
    "MAP-22": {
        "map_id", "terminal", "terminal_reason", "movement_steps", "current_coarse_silhouette",
        "visible_exit_bearings", "inspected_current_sign_detail", "active_goal_marker",
        "agent_authored_memory_journal",
    },
    "MAP-26": {
        "map_id", "terminal", "terminal_reason", "current_tick", "current_node", "alert",
        "log_readings", "test_readings", "spare_units_at_B", "carried_spare_units",
        "installed_candidates", "last_action_result", "communication_restored",
        "last_action_error_code",
    },
    "MAP-30": {
        "map_id", "terminal", "terminal_reason", "current_tick", "current_node",
        "local_neighbors", "public_alert", "visible_local_evidence", "recent_action_window",
        "casebook", "current_hypothesis", "unsupported_formal_accusations", "last_action_result",
    },
}


def _observation_leak_keys(instance_id: str, condition_id: str, seed: int = 0) -> list[str]:
    scene = get_scene(instance_id)
    environment = build_environment(scene, condition_id, seed=seed)
    dump = environment.observe().model_dump(mode="json")
    allowed = _PUBLIC_FIELDS[scene.map_id]
    return sorted(set(dump) - allowed)


def _oracle_action_strings(instance_id: str) -> list[str]:
    result = solve(instance_id)
    strings: list[str] = []
    for action in result.actions:
        strings.append(json.dumps(action, ensure_ascii=False, sort_keys=True))
    return strings


def _prompt_leaks_oracle(instance_id: str, condition_id: str) -> list[str]:
    scene = get_scene(instance_id)
    prompt = v6_system_prompt(scene.map_id, condition_id)
    return [text for text in _oracle_action_strings(instance_id) if text and text in prompt]


def _map22_memory_contract_findings() -> list[str]:
    from agent_arena.v6.prompts import v6_action_contract

    findings: list[str] = []
    for condition in ("history5", "history5_graph_memory"):
        prompt = v6_system_prompt("MAP-22", condition)
        contract = v6_action_contract("MAP-22", condition)
        if condition == "history5" and "write_memory{" in contract:
            findings.append("MAP-22 history5 action contract advertises write_memory")
        if "return_to_camp" in contract and "不会自动移动" not in prompt:
            findings.append(f"MAP-22 {condition} prompt does not clarify return_to_camp")
    return findings


def _map22_disabled_memory_result_findings() -> list[str]:
    scene = get_scene("map22_l3_original")
    environment = build_environment(scene, "history5", seed=0)
    from agent_arena.worlds.scenario_v4 import ScenarioV4Action

    result = environment.step(
        ScenarioV4Action.model_validate(
            {
                "tool": "write_memory",
                "facts": [{"fact_type": "node_page", "sign_id": "X", "exit_bearings": ["N"]}],
            },
            strict=True,
        )
    )
    if result.result != "MEMORY_DISABLED":
        return ["MAP-22 history5 write_memory did not return MEMORY_DISABLED"]
    return []


def _map30_initial_hidden_evidence_findings(instance_id: str) -> list[str]:
    findings: list[str] = []
    scene = get_scene(instance_id)
    case = scene.case
    environment = build_environment(scene, "history5_casebook", seed=0)
    dump = environment.observe().model_dump(mode="json")
    if dump["casebook"]:
        findings.append("MAP-30 initial casebook is not empty")
    visible = set(dump["visible_local_evidence"])
    if case is not None:
        known = {evidence_id for ids in case.node_evidence.values() for evidence_id in ids}
        if not visible.issubset(known):
            findings.append("MAP-30 visible evidence is not a subset of local evidence")
        culprit = case.culprit
        if culprit in json.dumps(dump, ensure_ascii=False):
            findings.append("MAP-30 initial observation leaks the culprit id")
    return findings


def _no_seed_truth_in_prompt_findings() -> list[str]:
    findings: list[str] = []
    # MAP-08: the prompt must not encode the seed-to-leak mapping.
    prompt = v6_system_prompt("MAP-08", "hypothesis_table")
    for token in ("seed", "0:", "4:", "8:"):
        if token in prompt:
            findings.append(f"MAP-08 prompt contains likely seed mapping token {token!r}")
    return findings


def audit_all() -> dict[str, Any]:
    findings: dict[str, list[str]] = {}
    for instance_id, scene in sorted(get_scene_map().items()):
        issues: list[str] = []
        for condition in scene.paired_conditions:
            issues.extend(
                f"{condition}: unexpected observation key {key}"
                for key in _observation_leak_keys(instance_id, condition)
            )
            issues.extend(
                f"{condition}: prompt leaks oracle action {text}"
                for text in _prompt_leaks_oracle(instance_id, condition)
            )
        if scene.map_id == "MAP-30":
            issues.extend(_map30_initial_hidden_evidence_findings(instance_id))
        if issues:
            findings[instance_id] = issues
    findings["MAP-22"] = (
        _map22_memory_contract_findings() + _map22_disabled_memory_result_findings()
    )
    findings["seed_truth"] = _no_seed_truth_in_prompt_findings()
    return {key: value for key, value in findings.items() if value}


def get_scene_map() -> dict[str, Any]:
    from agent_arena.v6.scenes import all_scenes

    return all_scenes()
