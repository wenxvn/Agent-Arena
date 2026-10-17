"""Six replayable hand-calibration traces for each runtime-backed V7 map.

Each case below is a real, deterministic step sequence through the frozen V4
environment: success, failure, boundary, missing-data or censored branches.
The judge artefact is built from ``environment.judge_state()`` exactly as the
offline V6 runner does, so private truth never enters the public trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from agent_arena.v6.catalog import build_environment, get_scene
from agent_arena.v6.solvers import solve
from agent_arena.v7.metrics import registry
from agent_arena.v7.metrics.schema import MetricStatus, parse_trace_rows
from agent_arena.worlds.scenario_v4 import ScenarioV4Action
from agent_arena.worlds.scenario_v4.map22 import NODES
from agent_arena.worlds.scenario_v4.models import V4Status


@dataclass(frozen=True)
class HandCase:
    name: str
    instance_id: str
    condition: str
    actions: tuple[dict[str, Any], ...]
    expected: dict[str, tuple[MetricStatus, float | int | None]]
    seed: int = 0
    step_limit: int = 100
    terminal_status: V4Status | None = None
    terminal_reason: str | None = None


def _terminal_status(environment: Any) -> V4Status:
    return environment.status


def _replay(case: HandCase) -> tuple[Any, dict[str, Any]]:
    scene = get_scene(case.instance_id)
    environment = build_environment(
        scene, case.condition, seed=case.seed, step_limit=case.step_limit
    )
    rows: list[dict[str, Any]] = [
        {
            "event": "trace_header",
            "map_id": scene.map_id,
            "instance_id": case.instance_id,
            "condition_id": case.condition,
            "seed": case.seed,
            "scenario_hash": environment.source_hash,
            "provider": "offline",
            "model": "hand-calibration",
        }
    ]
    observation = environment.observe().model_dump(mode="json")
    for index, payload in enumerate(case.actions):
        step = environment.step(ScenarioV4Action.model_validate(payload, strict=True))
        after = step.observation.model_dump(mode="json")
        rows.append(
            {
                "event": "decision",
                "decision_index": index,
                "action": payload,
                "result": step.result,
                "observation_before": observation,
                "observation_after": after,
                "invalid_output_reason": None,
            }
        )
        observation = after
    judge_status = (
        "success"
        if environment.is_success
        else "censored"
        if environment.status is V4Status.CENSORED
        else "failure"
        if environment.is_terminal
        else "running"
    )
    record = parse_trace_rows(
        rows,
        judge={
            "status": judge_status,
            "judge_state": environment.judge_state(),
        },
        source=f"hand:{case.name}",
    )
    return environment, registry.compute_metrics(record)


def _moves(sequence: str) -> tuple[dict[str, Any], ...]:
    actions: list[dict[str, Any]] = []
    for origin, destination in zip(sequence, sequence[1:], strict=False):
        bearing = next(key for key, value in NODES[origin]["exits"].items() if value == destination)
        actions.append({"tool": "move", "bearing": bearing})
    return tuple(actions)


def _solver(instance_id: str) -> tuple[dict[str, Any], ...]:
    return tuple(dict(action) for action in solve(instance_id).actions)


_V = MetricStatus.VALID
_NA = MetricStatus.NOT_APPLICABLE
_CEN = MetricStatus.CENSORED

_EMPTY = {"tool": "set_timetable", "tick": 0, "operations": {}}
_TICK_1 = {"tool": "set_timetable", "tick": 1, "operations": {}}
_TICK_2 = {"tool": "set_timetable", "tick": 2, "operations": {}}
_TICK_3 = {"tool": "set_timetable", "tick": 3, "operations": {}}
_TICK_4 = {"tool": "set_timetable", "tick": 4, "operations": {}}
_TICK_5 = {"tool": "set_timetable", "tick": 5, "operations": {}}
_TICK_6 = {"tool": "set_timetable", "tick": 6, "operations": {}}
_TICK_7 = {"tool": "set_timetable", "tick": 7, "operations": {}}
_TICK_8 = {"tool": "set_timetable", "tick": 8, "operations": {}}
_TICK_9 = {"tool": "set_timetable", "tick": 9, "operations": {}}
_TICK_10 = {"tool": "set_timetable", "tick": 10, "operations": {}}
_TICK_11 = {"tool": "set_timetable", "tick": 11, "operations": {}}

_MAP18_DEADLINE = (
    _EMPTY,
    _TICK_1,
    _TICK_2,
    _TICK_3,
    _TICK_4,
    _TICK_5,
    _TICK_6,
    _TICK_7,
    _TICK_8,
    _TICK_9,
    _TICK_10,
    _TICK_11,
)

_MAP18_RECOVERY = (
    {
        "tool": "set_timetable",
        "tick": 0,
        "operations": {
            "T_B": {"op": "release", "to": "B2"},
            "T_G": {"op": "release", "to": "G2"},
            "T_R1": {"op": "release", "to": "R2"},
            "T_R2": {"op": "temporary_stop"},
            "T_X": {"op": "release", "to": "B2"},
        },
    },
    {
        "tool": "set_timetable",
        "tick": 1,
        "operations": {
            "T_B": {"op": "release", "to": "B3"},
            "T_G": {"op": "release", "to": "G3"},
            "T_X": {"op": "temporary_stop"},
        },
    },
    {"tool": "set_timetable", "tick": 2, "operations": {"T_X": {"op": "release", "to": "B3"}}},
    {"tool": "set_timetable", "tick": 3, "operations": {"T_X": {"op": "release", "to": "G2"}}},
    _TICK_4,
    {
        "tool": "set_timetable",
        "tick": 5,
        "operations": {"T_R2": {"op": "release", "to": "R3"}},
    },
    _TICK_6,
    _TICK_7,
    _TICK_8,
    _TICK_9,
    {
        "tool": "set_timetable",
        "tick": 10,
        "operations": {"T_R2": {"op": "release", "to": "R3"}},
    },
    {
        "tool": "set_timetable",
        "tick": 11,
        "operations": {"T_R3": {"op": "release", "to": "R2"}},
    },
)

_MAP30_F02 = (
    {"tool": "move", "to": "B"},
    {"tool": "inspect", "evidence_id": "B_KEY_STUB_2310"},
    {
        "tool": "interview",
        "npc_id": "BANQUET_CLERK",
        "topic_id": "EVENT_1_HANDOFF",
        "shown_evidence_ids": ["B_KEY_STUB_2310"],
        "shown_casebook_entry_ids": [],
    },
    {
        "tool": "record",
        "entry_id": "EVENT_1_HANDOFF",
        "evidence_ids": ["B_KEY_STUB_2310", "B_WITNESS_HANDOFF"],
    },
    {"tool": "move", "to": "K"},
    {"tool": "inspect", "evidence_id": "K_WAX_PLATE_2322"},
    {
        "tool": "interview",
        "npc_id": "KITCHEN_COOK",
        "topic_id": "EVENT_2_WAX",
        "shown_evidence_ids": [],
        "shown_casebook_entry_ids": ["EVENT_1_HANDOFF"],
    },
    {
        "tool": "record",
        "entry_id": "EVENT_2_WAX",
        "evidence_ids": ["K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"],
    },
    {"tool": "move", "to": "T"},
    {"tool": "inspect", "evidence_id": "T_CHAIN_REGISTER_2340"},
    {
        "tool": "interview",
        "npc_id": "TOWER_WATCH",
        "topic_id": "EVENT_3_SIGNAL",
        "shown_evidence_ids": [],
        "shown_casebook_entry_ids": ["EVENT_2_WAX"],
    },
    {
        "tool": "record",
        "entry_id": "EVENT_3_SIGNAL",
        "evidence_ids": ["T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"],
    },
    {
        "tool": "compare_records",
        "entry_ids": ["EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"],
    },
    {"tool": "move", "to": "K"},
    {"tool": "move", "to": "B"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "J"},
    {
        "tool": "formal_accuse",
        "person_id": "MARA_VENN",
        "event_claims": [],
        "cited_entry_ids": ["EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"],
    },
    {
        "tool": "formal_accuse",
        "person_id": "MARA_VENN",
        "event_claims": [],
        "cited_entry_ids": ["EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"],
    },
)

_MAP30_SWAPPED = (
    *_solver("map30_l3_original")[:-1],
    {
        "tool": "formal_accuse",
        "person_id": "MARA_VENN",
        "event_claims": [
            {"event_id": "EVENT_1_HANDOFF", "time": "23:10", "location": "B", "duty_code": "M4"},
            {"event_id": "EVENT_2_WAX", "time": "23:40", "location": "K", "duty_code": "M4"},
            {"event_id": "EVENT_3_SIGNAL", "time": "23:22", "location": "T", "duty_code": "M4"},
        ],
        "cited_entry_ids": [
            "Q4_CODEBOOK",
            "EVENT_1_HANDOFF",
            "EVENT_2_WAX",
            "EVENT_3_SIGNAL",
        ],
    },
)
_MAP30_SWAPPED = (*_MAP30_SWAPPED, _MAP30_SWAPPED[-1])

_MAP22_30 = "ABDGJKHEBEFIL" + "IFCFEBDBEFIL" + "KHIFCA"
_MAP22_LOOP = "ABDGJK" + "JK" * 12 + "J"

CASES = (
    # MAP-08: success, exact 7.0 boundary, wrong repair, flooding, censor, no repair.
    HandCase(
        "map08-x-first-success",
        "map08_l3_original",
        "hypothesis_table",
        (
            {"tool": "move", "edge_id": "X_A"},
            {"tool": "interact", "target_id": "X", "operation": "pressure_test_X"},
            {"tool": "move", "edge_id": "X_A"},
            {"tool": "move", "edge_id": "A_B"},
            {"tool": "interact", "target_id": "B", "operation": "repair_leak"},
        ),
        {
            "map08.diagnosis_accuracy": (_V, 1),
            "map08.wrong_repair": (_V, 0),
            "map08.tests_run": (_V, 1),
            "map08.candidate_reduction": (_V, 0.666667),
            "map08.information_gain_bits": (_V, 1.584963),
            "map08.peak_core_water": (_V, 4.0),
            "map08.legal_action_rate": (_V, 1.0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="LEAK_SEALED",
    ),
    HandCase(
        "map08-y-first-boundary-7-0",
        "map08_l3_original",
        "hypothesis_table",
        (
            {"tool": "move", "edge_id": "F_A"},
            {"tool": "move", "edge_id": "Y_F"},
            {"tool": "interact", "target_id": "Y", "operation": "pressure_test_Y"},
            {"tool": "move", "edge_id": "Y_D"},
            {"tool": "move", "edge_id": "C_D"},
            {"tool": "move", "edge_id": "X_C"},
            {"tool": "interact", "target_id": "X", "operation": "pressure_test_X"},
            {"tool": "move", "edge_id": "X_C"},
            {"tool": "move", "edge_id": "B_C"},
            {"tool": "interact", "target_id": "B", "operation": "repair_leak"},
        ),
        {
            "map08.diagnosis_accuracy": (_V, 1),
            "map08.tests_run": (_V, 2),
            "map08.peak_core_water": (_V, 7.0),
            "map08.information_gain_bits": (_V, 1.584963),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="LEAK_SEALED",
    ),
    HandCase(
        "map08-wrong-repair",
        "map08_l3_original",
        "hypothesis_table",
        (
            {"tool": "move", "edge_id": "A_B"},
            {"tool": "interact", "target_id": "B", "operation": "repair_leak"},
        ),
        {
            "map08.diagnosis_accuracy": (_V, 0),
            "map08.wrong_repair": (_V, 1),
            "map08.peak_core_water": (_V, 3.5),
            "map08.tests_run": (_V, 0),
        },
        seed=8,
        terminal_status=V4Status.FAILURE,
        terminal_reason="SEALANT_MISUSED",
    ),
    HandCase(
        "map08-water-limit",
        "map08_l3_original",
        "hypothesis_table",
        tuple({"tool": "wait", "turns": 1} for _ in range(13)),
        {
            "map08.diagnosis_accuracy": (_NA, None),
            "map08.wrong_repair": (_NA, None),
            "map08.peak_core_water": (_V, 7.5),
            "map08.tests_run": (_V, 0),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="CORE_WATER_LIMIT_EXCEEDED",
    ),
    HandCase(
        "map08-censored",
        "map08_l3_original",
        "hypothesis_table",
        ({"tool": "move", "edge_id": "X_A"},),
        {
            "map08.diagnosis_accuracy": (_CEN, None),
            "map08.peak_core_water": (_CEN, 1.5),
            "map08.legal_action_rate": (_V, 1.0),
        },
        step_limit=1,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
    HandCase(
        "map08-test-without-repair",
        "map08_l3_original",
        "hypothesis_table",
        (
            {"tool": "move", "edge_id": "X_A"},
            {"tool": "interact", "target_id": "X", "operation": "pressure_test_X"},
        ),
        {
            "map08.diagnosis_accuracy": (_NA, None),
            "map08.tests_run": (_V, 1),
            "map08.candidate_reduction": (_V, 0.666667),
            "map08.peak_core_water": (_V, 2.5),
        },
    ),
    # MAP-16: L1/L3 success, node/head-on failures, censor, no reservation.
    HandCase(
        "map16-l1-success",
        "map16_l1_single_train",
        "constraint_table",
        (
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "M"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "B"},
            {"tool": "move_train"},
        ),
        {
            "map16.legal_reservation_rate": (_V, 1.0),
            "map16.committed_ticks": (_V, 3),
            "map16.makespan_gap": (_V, 0),
            "map16.deadlock": (_V, 0),
            "map16.legal_action_rate": (_V, 1.0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="GATE_OPENED",
    ),
    HandCase(
        "map16-l3-success",
        "map16_l3_original",
        "constraint_table",
        _solver("map16_l3_original"),
        {
            "map16.legal_reservation_rate": (_V, 1.0),
            "map16.committed_ticks": (_V, 6),
            "map16.makespan_gap": (_V, 0),
            "map16.node_capacity_conflicts": (_V, 0),
            "map16.head_on_conflicts": (_V, 0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="GATE_OPENED",
    ),
    HandCase(
        "map16-node-capacity",
        "map16_l3_original",
        "constraint_table",
        (
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
            {"tool": "set_route", "train_id": "b", "next_node": "Y"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "M"},
            {"tool": "set_route", "train_id": "b", "next_node": "M"},
            {"tool": "move_train"},
        ),
        {
            "map16.legal_reservation_rate": (_V, 1.0),
            "map16.node_capacity_conflicts": (_V, 1),
            "map16.committed_ticks": (_V, 1),
            "map16.makespan_gap": (_NA, None),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="NODE_CAPACITY_CONFLICT",
    ),
    HandCase(
        "map16-head-on",
        "map16_l3_original",
        "constraint_table",
        (
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "b", "next_node": "Y"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "b", "next_node": "M"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "M"},
            {"tool": "set_route", "train_id": "b", "next_node": "X"},
            {"tool": "move_train"},
        ),
        {
            "map16.legal_reservation_rate": (_V, 0.8),
            "map16.head_on_conflicts": (_V, 1),
            "map16.committed_ticks": (_V, 3),
            "map16.makespan_gap": (_NA, None),
            "map16.legal_action_rate": (_V, 0.9),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="HEAD_ON_SWAP",
    ),
    HandCase(
        "map16-censored",
        "map16_l1_single_train",
        "constraint_table",
        (
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
        ),
        {
            "map16.legal_reservation_rate": (_V, 1.0),
            "map16.committed_ticks": (_V, 0),
            "map16.makespan_gap": (_CEN, None),
        },
        step_limit=2,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
    HandCase(
        "map16-no-reservation",
        "map16_l1_single_train",
        "constraint_table",
        ({"tool": "inspect_network"},),
        {
            "map16.legal_reservation_rate": (_NA, None),
            "map16.committed_ticks": (_V, 0),
            "map16.makespan_gap": (_NA, None),
            "map16.deadlock": (_V, 0),
        },
    ),
    # MAP-18: no-fault, observed recovery, two hard failures, censor, deadline.
    HandCase(
        "map18-l1-no-fault",
        "map18_l1_no_fault",
        "alert_on",
        _solver("map18_l1_no_fault"),
        {
            "map18.service_rate": (_V, 1.0),
            "map18.delay_person_ticks": (_V, 0),
            "map18.first_reroute_delay": (_NA, None),
            "map18.recovery_delay": (_NA, None),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="SERVICE_COMPLETE",
    ),
    HandCase(
        "map18-observed-recovery",
        "map18_l3_original",
        "alert_on",
        _MAP18_RECOVERY,
        {
            "map18.service_rate": (_V, 1.0),
            "map18.delay_person_ticks": (_V, 30),
            "map18.first_reroute_delay": (_V, 6),
            "map18.recovery_delay": (_V, 6),
            "map18.collision_violations": (_V, 0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="SERVICE_COMPLETE",
    ),
    HandCase(
        "map18-head-on",
        "map18_l3_original",
        "alert_on",
        (
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_R2": {"op": "release", "to": "R3"},
                    "T_R3": {"op": "release", "to": "R2"},
                },
            },
        ),
        {
            "map18.service_rate": (_V, 0.0),
            "map18.collision_violations": (_V, 1),
            "map18.first_reroute_delay": (_NA, None),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="HEAD_ON_COLLISION",
    ),
    HandCase(
        "map18-station-capacity",
        "map18_l3_original",
        "alert_on",
        (
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_R2": {"op": "temporary_stop"},
                    "T_R1": {"op": "release", "to": "R2"},
                    "T_R3": {"op": "release", "to": "R2"},
                },
            },
        ),
        {
            "map18.service_rate": (_V, 0.0),
            "map18.station_capacity_violations": (_V, 1),
            "map18.collision_violations": (_V, 0),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="STATION_CAPACITY_EXCEEDED",
    ),
    HandCase(
        "map18-censored",
        "map18_l3_original",
        "alert_on",
        (_EMPTY,),
        {
            "map18.service_rate": (_CEN, 0.0),
            "map18.delay_person_ticks": (_CEN, 0),
            "map18.first_reroute_delay": (_NA, None),
        },
        step_limit=1,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
    HandCase(
        "map18-deadline",
        "map18_l3_original",
        "alert_on",
        _MAP18_DEADLINE,
        {
            "map18.service_rate": (_V, 0.0),
            "map18.delay_person_ticks": (_V, 0),
            "map18.recovery_delay": (_CEN, None),
            "map18.first_reroute_delay": (_NA, None),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="DEADLINE_SERVICE_BELOW_70",
    ),
    # MAP-22: shortest, exact 30-move boundary, budget failure, bad bearing, bad memory, censor.
    HandCase(
        "map22-l1-shortest",
        "map22_l1_short_return",
        "history5_graph_memory",
        _solver("map22_l1_short_return"),
        {
            "map22.return_success": (_V, 1),
            "map22.path_gap": (_V, 0),
            "map22.repeated_public_edge_rate": (_V, 0.0),
            "map22.legal_action_rate": (_V, 1.0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="RETURNED_TO_CAMP_WITH_RUIN_RECORD",
    ),
    HandCase(
        "map22-exactly-30-moves",
        "map22_l3_original",
        "history5_graph_memory",
        _moves(_MAP22_30),
        {
            "map22.return_success": (_V, 1),
            "map22.path_gap": (_V, 22),
            "map22.repeated_public_edge_rate": (_V, 0.3),
            "map22.legal_action_rate": (_V, 1.0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="RETURNED_TO_CAMP_WITH_RUIN_RECORD",
    ),
    HandCase(
        "map22-budget-failure",
        "map22_l3_original",
        "history5_graph_memory",
        _moves(_MAP22_LOOP),
        {
            "map22.return_success": (_V, 0),
            "map22.path_gap": (_NA, None),
            "map22.repeated_public_edge_rate": (_V, 0.8),
            "map22.legal_action_rate": (_V, 1.0),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="STEP_LIMIT_REACHED",
    ),
    HandCase(
        "map22-illegal-bearing",
        "map22_l1_short_return",
        "history5_graph_memory",
        ({"tool": "move", "bearing": "N"}, *_solver("map22_l1_short_return")),
        {
            "map22.return_success": (_V, 1),
            "map22.path_gap": (_V, 0),
            "map22.illegal_bearing_actions": (_V, 1),
            "map22.legal_action_rate": (_V, 0.8),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="RETURNED_TO_CAMP_WITH_RUIN_RECORD",
    ),
    HandCase(
        "map22-memory-grounding",
        "map22_l1_short_return",
        "history5_graph_memory",
        (
            {
                "tool": "write_memory",
                "facts": [
                    {
                        "fact_type": "node_page",
                        "sign_id": "WRONG",
                        "exit_bearings": ["NE", "SE"],
                    }
                ],
            },
            *_solver("map22_l1_short_return"),
        ),
        {
            "map22.return_success": (_V, 1),
            "map22.memory_grounding_violations": (_V, 1),
            "map22.memory_facts_written": (_V, 0),
            "map22.legal_action_rate": (_V, 0.8),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="RETURNED_TO_CAMP_WITH_RUIN_RECORD",
    ),
    HandCase(
        "map22-censored",
        "map22_l1_short_return",
        "history5_graph_memory",
        ({"tool": "move", "bearing": "NE"},),
        {
            "map22.return_success": (_CEN, 0),
            "map22.path_gap": (_CEN, None),
            "map22.repeated_public_edge_rate": (_NA, None),
        },
        step_limit=1,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
    # MAP-26: diagnose-then-repair, recover-from-wrong, three failure modes, censor.
    HandCase(
        "map26-diagnose-then-repair",
        "map26_l1_antenna_fault",
        "free_diagnosis",
        (
            {"tool": "move", "to": "D"},
            {"tool": "read_log", "log_id": "COMM_LOSS_LAST_TRANSMIT"},
            {"tool": "test", "test_id": "bus_load"},
            {"tool": "test", "test_id": "antenna_loopback"},
            {"tool": "test", "test_id": "software_checksum"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "antenna_coupler"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "antenna_coupler"},
            {"tool": "restart"},
        ),
        {
            "map26.repair_success": (_V, 1),
            "map26.recovery_latency": (_NA, None),
            "map26.repeat_error_rate": (_NA, None),
            "map26.spares_remaining": (_V, 1),
            "map26.diagnosis_accuracy": (_V, 1),
            "map26.tests_run": (_V, 3),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="ALL_OBJECTIVES_COMPLETE",
    ),
    HandCase(
        "map26-recovery-from-wrong",
        "map26_recovery_antenna",
        "recovery_full",
        (
            {"tool": "move", "to": "D"},
            {"tool": "read_log", "log_id": "COMM_LOSS_LAST_TRANSMIT"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "power_regulator"},
            {"tool": "rollback"},
            {"tool": "move", "to": "D"},
            {"tool": "test", "test_id": "antenna_loopback"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "antenna_coupler"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "antenna_coupler"},
            {"tool": "restart"},
        ),
        {
            "map26.repair_success": (_V, 1),
            "map26.recovery_latency": (_V, 1),
            "map26.repeat_error_rate": (_V, 0.0),
            "map26.spares_remaining": (_V, 1),
            "map26.tests_run": (_V, 1),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="ALL_OBJECTIVES_COMPLETE",
    ),
    HandCase(
        "map26-two-different-wrong",
        "map26_l1_antenna_fault",
        "free_diagnosis",
        (
            {"tool": "move", "to": "D"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "take_spare", "part_id": "software_image"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "power_regulator"},
            {"tool": "replace", "part_id": "software_image"},
        ),
        {
            "map26.repair_success": (_V, 0),
            "map26.recovery_latency": (_V, 1),
            "map26.repeat_error_rate": (_V, 0.0),
            "map26.spares_remaining": (_V, 0),
            "map26.diagnosis_accuracy": (_V, 0),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="SPARES_EXHAUSTED",
    ),
    HandCase(
        "map26-same-wrong-twice",
        "map26_l1_antenna_fault",
        "free_diagnosis",
        (
            {"tool": "move", "to": "D"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "power_regulator"},
            {"tool": "replace", "part_id": "power_regulator"},
        ),
        {
            "map26.repair_success": (_V, 0),
            "map26.recovery_latency": (_CEN, None),
            "map26.repeat_error_rate": (_V, 0.5),
            "map26.spares_remaining": (_V, 0),
            "map26.diagnosis_accuracy": (_V, 0),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="SPARES_EXHAUSTED",
    ),
    HandCase(
        "map26-ignored-counterevidence",
        "map26_l1_antenna_fault",
        "free_diagnosis",
        (
            {"tool": "move", "to": "D"},
            {"tool": "test", "test_id": "bus_load"},
            {"tool": "test", "test_id": "software_checksum"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "take_spare", "part_id": "software_image"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "power_regulator"},
            {"tool": "replace", "part_id": "software_image"},
        ),
        {
            "map26.repair_success": (_V, 0),
            "map26.repeat_error_rate": (_V, 0.0),
            "map26.spares_remaining": (_V, 0),
            "map26.diagnosis_accuracy": (_V, 0),
            "map26.tests_run": (_V, 2),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="SPARES_EXHAUSTED",
    ),
    HandCase(
        "map26-censored",
        "map26_l1_antenna_fault",
        "free_diagnosis",
        ({"tool": "move", "to": "D"},),
        {
            "map26.repair_success": (_CEN, 0),
            "map26.recovery_latency": (_NA, None),
            "map26.repeat_error_rate": (_NA, None),
            "map26.spares_remaining": (_V, 2),
            "map26.diagnosis_accuracy": (_CEN, None),
        },
        step_limit=1,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
    # MAP-30: full and recall success, three failure modes, censor.
    HandCase(
        "map30-full-chain",
        "map30_l3_original",
        "history5_casebook",
        _solver("map30_l3_original"),
        {
            "map30.evidence_chain_coverage": (_V, 1.0),
            "map30.investigation_progress": (_V, 1.0),
            "map30.q4_recall_accuracy": (_V, 1),
            "map30.accusation_claim_precision": (_V, 1.0),
            "map30.chain_reconciled": (_V, 1),
            "map30.unsupported_accusations": (_V, 0),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN",
    ),
    HandCase(
        "map30-recall-condition",
        "map30_recall_original",
        "history5_casebook",
        _solver("map30_recall_original"),
        {
            "map30.evidence_chain_coverage": (_V, 1.0),
            "map30.q4_recall_accuracy": (_V, 1),
            "map30.accusation_claim_precision": (_V, 1.0),
            "map30.chain_reconciled": (_V, 1),
        },
        terminal_status=V4Status.SUCCESS,
        terminal_reason="ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN",
    ),
    HandCase(
        "map30-two-guesses",
        "map30_l3_original",
        "history5_casebook",
        (
            {"tool": "move", "to": "L"},
            {"tool": "move", "to": "H"},
            {"tool": "move", "to": "J"},
            {
                "tool": "formal_accuse",
                "person_id": "ORIN_VALE",
                "event_claims": [],
                "cited_entry_ids": [],
            },
            {
                "tool": "formal_accuse",
                "person_id": "PELL_GRAN",
                "event_claims": [],
                "cited_entry_ids": [],
            },
        ),
        {
            "map30.evidence_chain_coverage": (_V, 0.0),
            "map30.q4_recall_accuracy": (_V, 0),
            "map30.accusation_claim_precision": (_V, 0.0),
            "map30.unsupported_accusations": (_V, 2),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="ACCUSATION_LIMIT_EXCEEDED",
    ),
    HandCase(
        "map30-missing-q4",
        "map30_l3_original",
        "history5_casebook",
        _MAP30_F02,
        {
            "map30.evidence_chain_coverage": (_V, 0.75),
            "map30.investigation_progress": (_V, 0.75),
            "map30.q4_recall_accuracy": (_V, 0),
            "map30.unsupported_accusations": (_V, 2),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="ACCUSATION_LIMIT_EXCEEDED",
    ),
    HandCase(
        "map30-swapped-times",
        "map30_l3_original",
        "history5_casebook",
        _MAP30_SWAPPED,
        {
            "map30.evidence_chain_coverage": (_V, 1.0),
            "map30.q4_recall_accuracy": (_V, 1),
            "map30.accusation_claim_precision": (_V, 0.0),
            "map30.chain_reconciled": (_V, 1),
            "map30.unsupported_accusations": (_V, 2),
        },
        terminal_status=V4Status.FAILURE,
        terminal_reason="ACCUSATION_LIMIT_EXCEEDED",
    ),
    HandCase(
        "map30-censored",
        "map30_l3_original",
        "history5_casebook",
        ({"tool": "move", "to": "L"},),
        {
            "map30.evidence_chain_coverage": (_V, 0.0),
            "map30.investigation_progress": (_V, 0.0),
            "map30.q4_recall_accuracy": (_CEN, None),
            "map30.accusation_claim_precision": (_CEN, None),
        },
        step_limit=1,
        terminal_status=V4Status.CENSORED,
        terminal_reason="ACTION_LIMIT_REACHED",
    ),
)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_hand_calibration_trace(case: HandCase) -> None:
    environment, values = _replay(case)
    if case.terminal_status is not None:
        assert environment.status is case.terminal_status
    if case.terminal_reason is not None:
        assert environment.terminal_reason == case.terminal_reason
    for metric_id, (expected_status, expected_value) in case.expected.items():
        value = values[metric_id]
        assert value.status is expected_status, (case.name, metric_id, value)
        if expected_value is None:
            assert value.value is None, (case.name, metric_id, value)
        else:
            assert value.value == pytest.approx(expected_value), (case.name, metric_id, value)


def test_each_runtime_map_has_six_hand_cases() -> None:
    counts = {map_id: 0 for map_id in ("MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30")}
    for case in CASES:
        counts[get_scene(case.instance_id).map_id] += 1
    assert counts == {
        "MAP-08": 6,
        "MAP-16": 6,
        "MAP-18": 6,
        "MAP-22": 6,
        "MAP-26": 6,
        "MAP-30": 6,
    }
