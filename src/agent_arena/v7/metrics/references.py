"""Frozen offline scoring references for the six runtime-backed V4 maps.

These constants are *judge-side* data. They never enter an Agent prompt, a
public Observation, a tool response, or a public report. They are duplicated
here (rather than imported from mutable runtime modules) so that a V7 metric
value can be audited against one frozen file and so that a later runtime change
cannot silently redefine a historical score.

Provenance:

- ``MAP16_OPTIMAL_MAKESPAN``: V6 ``docs/v6/measurement-matrix.md`` and
  ``solve_map16`` (combinatorial BFS).
- ``MAP22_OPTIMAL_MOVES``: V6 solver ``solve_map22`` (BFS over
  ``(node, target_visited)``).
- ``MAP26_FAULT_PART`` / spares: V6 ``scenes.py`` instance definitions.
- ``MAP30_CASES``: V6 case definitions (entry order, required evidence, culprit,
  claim count), including the L1/L2 alternative cases.
- ``MAP18_TASK_*``: V4 ``map18.py`` public dispatch table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MAP16_OPTIMAL_MAKESPAN: Final[dict[str, int]] = {
    "map16_l1_single_train": 3,
    "map16_l2_siding_variant_a": 4,
    "map16_l2_siding_variant_b": 5,
    "map16_l3_original": 6,
}

MAP22_OPTIMAL_MOVES: Final[dict[str, int]] = {
    "map22_l1_short_return": 4,
    "map22_l2_branch_loop": 4,
    "map22_l2_dead_end_spur": 8,
    "map22_l3_original": 8,
}

MAP26_FAULT_PART: Final[dict[str, str]] = {
    "map26_l1_antenna_fault": "antenna_coupler",
    "map26_l2_power_fault": "power_regulator",
    "map26_l2_spare_rich": "power_regulator",
    "map26_l3_software_fault": "software_image",
    "map26_recovery_antenna": "antenna_coupler",
    "map26_recovery_power": "power_regulator",
    "map26_recovery_software": "software_image",
}

MAP26_INITIAL_SPARES: Final[dict[str, int]] = {
    "map26_l1_antenna_fault": 2,
    "map26_l2_power_fault": 2,
    "map26_l2_spare_rich": 3,
    "map26_l3_software_fault": 2,
    "map26_recovery_antenna": 2,
    "map26_recovery_power": 2,
    "map26_recovery_software": 2,
}


@dataclass(frozen=True)
class Map30CaseReference:
    entry_order: tuple[str, ...]
    entry_required: dict[str, frozenset[str]]
    culprit: str
    claim_count: int
    code_entry: str
    claims: tuple[tuple[str, str, str, str], ...]


MAP30_CASES: Final[dict[str, Map30CaseReference]] = {
    "map30_l1_two_event_case": Map30CaseReference(
        entry_order=("R7_CODEBOOK", "EVENT_1_TALLY", "EVENT_2_GATE"),
        entry_required={
            "R7_CODEBOOK": frozenset({"R7_CODE_INDEX"}),
            "EVENT_1_TALLY": frozenset({"P_TALLY_0100", "P_WITNESS_TALLY"}),
            "EVENT_2_GATE": frozenset({"Q_GATE_0140", "Q_WITNESS_GATE"}),
        },
        culprit="IVO_KEST",
        claim_count=2,
        code_entry="R7_CODEBOOK",
        claims=(
            ("EVENT_1_TALLY", "01:00", "P", "M2"),
            ("EVENT_2_GATE", "01:40", "Q", "M2"),
        ),
    ),
    "map30_l2_three_event_alt": Map30CaseReference(
        entry_order=("S9_CODEBOOK", "EVENT_1_SLIP", "EVENT_2_LEDGER", "EVENT_3_BELL"),
        entry_required={
            "S9_CODEBOOK": frozenset({"S9_CODE_INDEX"}),
            "EVENT_1_SLIP": frozenset({"W_SLIP_2205", "W_WITNESS_SLIP"}),
            "EVENT_2_LEDGER": frozenset({"X_LEDGER_2230", "X_WITNESS_LEDGER"}),
            "EVENT_3_BELL": frozenset({"Z_BELL_2300", "Z_WITNESS_BELL"}),
        },
        culprit="NELL_ORAV",
        claim_count=3,
        code_entry="S9_CODEBOOK",
        claims=(
            ("EVENT_1_SLIP", "22:05", "W", "M7"),
            ("EVENT_2_LEDGER", "22:30", "X", "M7"),
            ("EVENT_3_BELL", "23:00", "Z", "M7"),
        ),
    ),
    "map30_l3_original": Map30CaseReference(
        entry_order=(
            "Q4_CODEBOOK",
            "EVENT_1_HANDOFF",
            "EVENT_2_WAX",
            "EVENT_3_SIGNAL",
        ),
        entry_required={
            "Q4_CODEBOOK": frozenset({"Q4_CODE_INDEX"}),
            "EVENT_1_HANDOFF": frozenset({"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"}),
            "EVENT_2_WAX": frozenset({"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"}),
            "EVENT_3_SIGNAL": frozenset({"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"}),
        },
        culprit="MARA_VENN",
        claim_count=3,
        code_entry="Q4_CODEBOOK",
        claims=(
            ("EVENT_1_HANDOFF", "23:10", "B", "M4"),
            ("EVENT_2_WAX", "23:22", "K", "M4"),
            ("EVENT_3_SIGNAL", "23:40", "T", "M4"),
        ),
    ),
}
MAP30_CASES["map30_recall_original"] = MAP30_CASES["map30_l3_original"]

MAP18_TOTAL_DEMAND: Final[int] = 18
MAP18_PASSENGERS: Final[dict[str, int]] = {
    "TASK_R1_R2": 3,
    "TASK_R2_R3": 3,
    "TASK_R3_R2": 3,
    "TASK_B1_B3": 3,
    "TASK_G1_G3": 3,
    "TASK_R2_G2": 3,
}
MAP18_PLANNED_ARRIVAL: Final[dict[str, int]] = {
    "TASK_R1_R2": 6,
    "TASK_R2_R3": 6,
    "TASK_R3_R2": 7,
    "TASK_B1_B3": 2,
    "TASK_G1_G3": 2,
    "TASK_R2_G2": 7,
}
MAP18_RED_TASKS: Final[tuple[str, ...]] = ("TASK_R2_R3", "TASK_R3_R2")
MAP18_FAULT_WINDOW: Final[dict[str, tuple[int, int] | None]] = {
    "map18_l1_no_fault": None,
    "map18_l2_short_closure": (5, 8),
    "map18_l2_alt_segment_r2b2": (2, 7),
    "map18_l3_original": (5, 10),
    "map18_l3_long_closure": (5, 12),
    "map18_l3_alt_segment_b3g2": (4, 9),
}


__all__ = [
    "MAP18_FAULT_WINDOW",
    "MAP18_PASSENGERS",
    "MAP18_PLANNED_ARRIVAL",
    "MAP18_RED_TASKS",
    "MAP18_TOTAL_DEMAND",
    "MAP22_OPTIMAL_MOVES",
    "MAP26_FAULT_PART",
    "MAP26_INITIAL_SPARES",
    "MAP30_CASES",
    "MAP16_OPTIMAL_MAKESPAN",
    "Map30CaseReference",
]
