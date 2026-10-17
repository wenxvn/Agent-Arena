"""Oracle and fixture cases for the six V4-backed V8 maps.

The oracle paths come from the independent V6 solvers, replayed through the V8
adapter. Fixture expectations are the hand-computed values already published in
``tests/test_v7_hand_traces.py`` for the reviewed V4 scenes; they are not
re-derived from a runtime run. Each map keeps at least two such cases: a
success/partial path and a mechanism-specific failure or boundary.
"""

from __future__ import annotations

from typing import Any

from agent_arena.v6.solvers import solve

_ORACLE_SCENES: dict[str, str] = {
    "MAP-08": "map08_l3_original",
    "MAP-16": "map16_l3_original",
    "MAP-18": "map18_l3_original",
    "MAP-22": "map22_l3_original",
    "MAP-26": "map26_l1_antenna_fault",
    "MAP-30": "map30_l3_original",
}

_FIRST_FIXTURES: dict[str, dict[str, Any]] = {
    "MAP-08": {
        "name": "x-first-success",
        "actions": [
            {"tool": "move", "edge_id": "X_A"},
            {"tool": "interact", "target_id": "X", "operation": "pressure_test_X"},
            {"tool": "move", "edge_id": "X_A"},
            {"tool": "move", "edge_id": "A_B"},
            {"tool": "interact", "target_id": "B", "operation": "repair_leak"},
        ],
        "expect": {
            "map08.diagnosis_accuracy": 1,
            "map08.wrong_repair": 0,
            "map08.tests_run": 1,
            "map08.candidate_reduction": 0.666667,
            "map08.information_gain_bits": 1.584963,
            "map08.peak_core_water": 4.0,
            "map08.legal_action_rate": 1.0,
        },
    },
    "MAP-16": {
        "name": "node-capacity-conflict",
        "actions": [
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
            {"tool": "set_route", "train_id": "b", "next_node": "Y"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "M"},
            {"tool": "set_route", "train_id": "b", "next_node": "M"},
            {"tool": "move_train"},
        ],
        "expect": {
            "map16.legal_reservation_rate": 1.0,
            "map16.node_capacity_conflicts": 1,
            "map16.committed_ticks": 1,
            "map16.makespan_gap": None,
        },
    },
    "MAP-18": {
        "name": "head-on-collision",
        "actions": [
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_R2": {"op": "release", "to": "R3"},
                    "T_R3": {"op": "release", "to": "R2"},
                },
            },
        ],
        "expect": {
            "map18.service_rate": 0.0,
            "map18.collision_violations": 1,
            "map18.first_reroute_delay": None,
        },
    },
    "MAP-22": {
        "name": "illegal-bearing-then-solve",
        "actions": [{"tool": "move", "bearing": "N"}],
        "extend_with_solver": True,
        "expect": {
            "map22.illegal_bearing_actions": 1,
            "map22.legal_action_rate": 0.888889,
        },
    },
    "MAP-26": {
        "name": "same-wrong-part-twice",
        "actions": [
            {"tool": "move", "to": "D"},
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "B"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "take_spare", "part_id": "power_regulator"},
            {"tool": "move", "to": "A"},
            {"tool": "replace", "part_id": "power_regulator"},
            {"tool": "replace", "part_id": "power_regulator"},
        ],
        "expect": {
            "map26.repair_success": 0,
            "map26.recovery_latency": None,
            "map26.repeat_error_rate": 0.5,
            "map26.spares_remaining": 0,
            "map26.diagnosis_accuracy": 0,
        },
    },
    "MAP-30": {
        "name": "two-unsupported-accusations",
        "actions": [
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
        ],
        "expect": {
            "map30.evidence_chain_coverage": 0.0,
            "map30.q4_recall_accuracy": 0,
            "map30.accusation_claim_precision": 0.0,
            "map30.unsupported_accusations": 2,
        },
    },
}

_SECOND_FIXTURES: dict[str, dict[str, Any]] = {
    "MAP-08": {
        "name": "y-first-boundary-7-0",
        "actions": [
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
        ],
        "expect": {
            "map08.diagnosis_accuracy": 1,
            "map08.tests_run": 2,
            "map08.peak_core_water": 7.0,
            "map08.information_gain_bits": 1.584963,
        },
    },
    "MAP-16": {
        "name": "l3-two-train-success",
        "actions": [
            {"tool": "inspect_network"},
            {"tool": "set_route", "train_id": "b", "next_node": "Y"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "X"},
            {"tool": "set_route", "train_id": "b", "next_node": "M"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "M"},
            {"tool": "occupy_siding", "train_id": "b", "next_node": "D"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "Y"},
            {"tool": "set_route", "train_id": "b", "next_node": "M"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "b", "next_node": "X"},
            {"tool": "move_train"},
            {"tool": "set_route", "train_id": "a", "next_node": "B"},
            {"tool": "set_route", "train_id": "b", "next_node": "A"},
            {"tool": "move_train"},
        ],
        "expect": {
            "map16.legal_reservation_rate": 1.0,
            "map16.committed_ticks": 6,
            "map16.makespan_gap": 0,
            "map16.node_capacity_conflicts": 0,
            "map16.head_on_conflicts": 0,
        },
    },
    "MAP-18": {
        "name": "observed-recovery",
        "actions": [
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
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {"T_X": {"op": "release", "to": "B3"}},
            },
            {
                "tool": "set_timetable",
                "tick": 3,
                "operations": {"T_X": {"op": "release", "to": "G2"}},
            },
            {"tool": "set_timetable", "tick": 4, "operations": {}},
            {
                "tool": "set_timetable",
                "tick": 5,
                "operations": {"T_R2": {"op": "release", "to": "R3"}},
            },
            {"tool": "set_timetable", "tick": 6, "operations": {}},
            {"tool": "set_timetable", "tick": 7, "operations": {}},
            {"tool": "set_timetable", "tick": 8, "operations": {}},
            {"tool": "set_timetable", "tick": 9, "operations": {}},
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
        ],
        "expect": {
            "map18.service_rate": 1.0,
            "map18.delay_person_ticks": 30,
            "map18.first_reroute_delay": 6,
            "map18.recovery_delay": 6,
            "map18.collision_violations": 0,
        },
    },
    "MAP-22": {
        "name": "exactly-30-moves",
        "actions": [
            {"tool": "move", "bearing": "NE"},
            {"tool": "move", "bearing": "NE"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "S"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "S"},
            {"tool": "move", "bearing": "NE"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "SW"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "N"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "NE"},
            {"tool": "move", "bearing": "SW"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "S"},
            {"tool": "move", "bearing": "NE"},
            {"tool": "move", "bearing": "E"},
            {"tool": "move", "bearing": "N"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "S"},
            {"tool": "move", "bearing": "SW"},
            {"tool": "move", "bearing": "W"},
            {"tool": "move", "bearing": "NW"},
        ],
        "expect": {
            "map22.return_success": 1,
            "map22.path_gap": 22,
            "map22.repeated_public_edge_rate": 0.3,
            "map22.legal_action_rate": 1.0,
        },
    },
    "MAP-26": {
        "name": "diagnose-then-repair",
        "actions": [
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
        ],
        "expect": {
            "map26.repair_success": 1,
            "map26.recovery_latency": None,
            "map26.repeat_error_rate": None,
            "map26.spares_remaining": 1,
            "map26.diagnosis_accuracy": 1,
            "map26.tests_run": 3,
        },
    },
    "MAP-30": {
        "name": "full-chain-success",
        "actions": [
            {"tool": "move", "to": "L"},
            {"tool": "move", "to": "A"},
            {"tool": "inspect", "evidence_id": "Q4_ARCHIVE_DOCKET"},
            {
                "tool": "interview",
                "npc_id": "ARCHIVE_CLERK",
                "topic_id": "Q4_CODEBOOK",
                "shown_evidence_ids": ["Q4_ARCHIVE_DOCKET"],
                "shown_casebook_entry_ids": [],
            },
            {
                "tool": "record",
                "entry_id": "Q4_CODEBOOK",
                "evidence_ids": ["Q4_CODE_INDEX"],
            },
            {"tool": "move", "to": "L"},
            {"tool": "move", "to": "H"},
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
                "entry_ids": [
                    "Q4_CODEBOOK",
                    "EVENT_1_HANDOFF",
                    "EVENT_2_WAX",
                    "EVENT_3_SIGNAL",
                ],
            },
            {"tool": "move", "to": "A"},
            {"tool": "move", "to": "L"},
            {"tool": "move", "to": "H"},
            {"tool": "move", "to": "J"},
            {
                "tool": "formal_accuse",
                "person_id": "MARA_VENN",
                "event_claims": [
                    {
                        "event_id": "EVENT_1_HANDOFF",
                        "time": "23:10",
                        "location": "B",
                        "duty_code": "M4",
                    },
                    {
                        "event_id": "EVENT_2_WAX",
                        "time": "23:22",
                        "location": "K",
                        "duty_code": "M4",
                    },
                    {
                        "event_id": "EVENT_3_SIGNAL",
                        "time": "23:40",
                        "location": "T",
                        "duty_code": "M4",
                    },
                ],
                "cited_entry_ids": [
                    "Q4_CODEBOOK",
                    "EVENT_1_HANDOFF",
                    "EVENT_2_WAX",
                    "EVENT_3_SIGNAL",
                ],
            },
        ],
        "expect": {
            "map30.evidence_chain_coverage": 1.0,
            "map30.investigation_progress": 1.0,
            "map30.q4_recall_accuracy": 1,
            "map30.accusation_claim_precision": 1.0,
            "map30.chain_reconciled": 1,
            "map30.unsupported_accusations": 0,
        },
    },
}


def _oracle_actions(map_id: str) -> list[dict[str, Any]]:
    result = solve(_ORACLE_SCENES[map_id], seed=0)
    return [dict(action) for action in result.actions]


def oracle_cases(map_id: str) -> tuple[dict[str, Any], ...]:
    return (
        {
            "trace_id": f"{map_id}-solver-success",
            "seed": 0,
            "actions": _oracle_actions(map_id),
            "expect_success": True,
        },
    )


def fixtures(map_id: str) -> tuple[dict[str, Any], ...]:
    cases: list[dict[str, Any]] = []
    for template in (_FIRST_FIXTURES[map_id], _SECOND_FIXTURES[map_id]):
        actions = [dict(action) for action in template["actions"]]
        if template.get("extend_with_solver"):
            actions.extend(_oracle_actions(map_id))
        cases.append(
            {
                "name": template["name"],
                "seed": 0,
                "actions": actions,
                "expect": dict(template["expect"]),
            }
        )
    return tuple(cases)


__all__ = ["fixtures", "oracle_cases"]
