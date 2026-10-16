"""V6 instance scenes: data-only definitions injected into the V4 rule engines.

Every scene here is original V6 data. None of it modifies the reviewed V4 map
files; the V4 environments were parameterized with backward-compatible defaults
(see `docs/v6/design-change-requests.md`, DCR-002). All instances are marked
`pending_human_review`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.worlds.scenario_v4.map30 import Map30Case, WitnessRule
from agent_arena.worlds.scenario_v4.models import V4EventClaim

REVIEW_STATUS = "pending_human_review"
RULE_VERSION = "v6.0"


def _forest(spec: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Expand a compact {node: {exits}} spec into a full MAP-22 node table."""
    nodes: dict[str, dict[str, Any]] = {}
    for node, payload in spec.items():
        nodes[node] = {
            "sign": f"{node}_SIGN",
            "silhouette": f"{node}_silhouette",
            "feature": f"{node}_feature",
            "exits": dict(payload["exits"]),
        }
    return nodes


# --------------------------------------------------------------------------- #
# MAP-16 scenes
# --------------------------------------------------------------------------- #
MAP16_DIREctions_DEFAULT = {
    "a": {"A": ("X",), "X": ("M",), "M": ("Y", "D"), "D": ("M",), "Y": ("B",), "B": ()},
    "b": {"B": ("Y",), "Y": ("M",), "M": ("X", "D"), "D": ("M",), "X": ("A",), "A": ()},
}


@dataclass(frozen=True)
class Map16Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    adjacency: dict[str, tuple[str, ...]]
    directions: dict[str, dict[str, tuple[str, ...]]]
    start_positions: dict[str, str]
    goals: dict[str, str]
    sidings: frozenset[str]
    note: str
    map_id: str = "MAP-16"

    def env_kwargs(self) -> dict[str, Any]:
        return {
            "adjacency": self.adjacency,
            "directions": self.directions,
            "start_positions": self.start_positions,
            "goals": self.goals,
            "sidings": self.sidings,
        }


def _line_with_sidings(
    nodes: tuple[str, ...], *siding: str
) -> dict[str, tuple[str, ...]]:
    """Build a bidirectional line graph with optional extra siding nodes."""
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for left, right in zip(nodes, nodes[1:], strict=False):
        adjacency[left].add(right)
        adjacency[right].add(left)
    for index, sid in enumerate(siding):
        # Spread sidings across the line, starting at the first interior node.
        anchor = nodes[min(index + 1, len(nodes) - 1)]
        adjacency.setdefault(sid, set()).add(anchor)
        adjacency[anchor].add(sid)
    return {node: tuple(sorted(neighbors)) for node, neighbors in adjacency.items()}


def _directions_from_adjacency(
    adjacency: dict[str, tuple[str, ...]],
    trains: dict[str, tuple[str, str]],
    sidings: frozenset[str] = frozenset(),
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Direction table where each train advances toward its goal, plus sidings."""

    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for train, (origin, goal) in trains.items():
        # Breadth-first ordering of nodes by hop distance toward the goal.
        distance: dict[str, int] = {goal: 0}
        queue = [goal]
        while queue:
            node = queue.pop(0)
            for neighbor in adjacency.get(node, ()):
                if neighbor not in distance:
                    distance[neighbor] = distance[node] + 1
                    queue.append(neighbor)
        table: dict[str, tuple[str, ...]] = {}
        for node, neighbors in adjacency.items():
            advancing = {
                neighbor
                for neighbor in neighbors
                if distance.get(neighbor, 10**6) < distance.get(node, 10**6)
            }
            sidings_here = {neighbor for neighbor in neighbors if neighbor in sidings}
            allowed = advancing | sidings_here
            table[node] = tuple(sorted(allowed)) if allowed else tuple(sorted(neighbors))
        table[origin] = table[origin] or tuple(sorted(adjacency[origin]))
        result[train] = table
    return result


def _build_map16_scenes() -> dict[str, Map16Scene]:
    scenes: dict[str, Map16Scene] = {}
    # L3: the reviewed V4 scene, unchanged.
    scenes["map16_l3_original"] = Map16Scene(
        instance_id="map16_l3_original",
        level="L3",
        capability="synchronized_capacity_scheduling",
        paired_conditions=("react", "constraint_table"),
        adjacency={
            "A": ("X",),
            "X": ("A", "M"),
            "M": ("X", "Y", "D"),
            "Y": ("M", "B"),
            "B": ("Y",),
            "D": ("M",),
        },
        directions=MAP16_DIREctions_DEFAULT,
        start_positions={"a": "A", "b": "B"},
        goals={"a": "B", "b": "A"},
        sidings=frozenset({"D"}),
        note="Reviewed V4 topology; synchronous two-train meet at siding D.",
    )
    # L1: a single train, one reservation at a time, capacity legality only.
    scenes["map16_l1_single_train"] = Map16Scene(
        instance_id="map16_l1_single_train",
        level="L1",
        capability="single_reservation_capacity_legality",
        paired_conditions=("react", "constraint_table"),
        adjacency={
            "A": ("X",),
            "X": ("A", "M"),
            "M": ("X", "B"),
            "B": ("M",),
        },
        directions={"a": {"A": ("X",), "X": ("M",), "M": ("B",), "B": ()}},
        start_positions={"a": "A"},
        goals={"a": "B"},
        sidings=frozenset({"M"}),
        note="Single train: tests only per-step reservation and capacity legality.",
    )
    # L2: two trains, one siding, but a simpler line than the full V4 topology.
    adjacency_a = _line_with_sidings(("P", "Q", "R"), "S")
    directions_a = _directions_from_adjacency(
        adjacency_a, {"a": ("P", "R"), "b": ("R", "P")}, frozenset({"S"})
    )
    scenes["map16_l2_siding_variant_a"] = Map16Scene(
        instance_id="map16_l2_siding_variant_a",
        level="L2",
        capability="two_train_siding_avoidance",
        paired_conditions=("react", "constraint_table"),
        adjacency=adjacency_a,
        directions=directions_a,
        start_positions={"a": "P", "b": "R"},
        goals={"a": "R", "b": "P"},
        sidings=frozenset({"S"}),
        note="Line P-Q-R with a single siding S: one forced avoidance, less sync load.",
    )
    # L2 variant b: longer line with two sidings.
    adjacency_b = _line_with_sidings(("P", "Q", "R", "T"), "S1", "S2")
    directions_b = _directions_from_adjacency(
        adjacency_b, {"a": ("P", "T"), "b": ("T", "P")}, frozenset({"S1", "S2"})
    )
    scenes["map16_l2_siding_variant_b"] = Map16Scene(
        instance_id="map16_l2_siding_variant_b",
        level="L2",
        capability="two_train_siding_avoidance",
        paired_conditions=("react", "constraint_table"),
        adjacency=adjacency_b,
        directions=directions_b,
        start_positions={"a": "P", "b": "T"},
        goals={"a": "T", "b": "P"},
        sidings=frozenset({"S1", "S2"}),
        note="Longer line with two sidings: repeated avoidance with a different geometry.",
    )
    return scenes


# --------------------------------------------------------------------------- #
# MAP-22 scenes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Map22Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    nodes: dict[str, dict[str, Any]]
    start: str
    target: str
    move_budget: int
    note: str
    map_id: str = "MAP-22"

    def env_kwargs(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "start_node": self.start,
            "target_node": self.target,
            "move_budget": self.move_budget,
            "optimal_moves": _round_trip_length(self.nodes, self.start, self.target),
        }


def _round_trip_length(
    nodes: dict[str, dict[str, Any]], start: str, target: str
) -> int:
    """Shortest walk that visits the target and returns to the start."""
    from collections import deque

    queue: deque[tuple[str, bool]] = deque([(start, False)])
    distance: dict[tuple[str, bool], int] = {(start, False): 0}
    goal = (start, True)
    while queue:
        node, visited = queue.popleft()
        if (node, visited) == goal:
            return distance[(node, visited)]
        for bearing in sorted(nodes[node]["exits"]):
            neighbor = nodes[node]["exits"][bearing]
            state = (neighbor, visited or neighbor == target)
            if state not in distance:
                distance[state] = distance[(node, visited)] + 1
                queue.append(state)
    return 0

def _build_map22_scenes() -> dict[str, Map22Scene]:
    scenes: dict[str, Map22Scene] = {}
    scenes["map22_l1_short_return"] = Map22Scene(
        instance_id="map22_l1_short_return",
        level="L1",
        capability="short_known_return",
        paired_conditions=("history5", "history5_graph_memory"),
        nodes=_forest(
            {
                "A": {"exits": {"E": "B"}},
                "B": {"exits": {"W": "A", "E": "C"}},
                "C": {"exits": {"W": "B"}},
            }
        ),
        start="A",
        target="C",
        move_budget=10,
        note="Three-node line: after two observed nodes the return is trivial.",
    )
    scenes["map22_l2_branch_loop"] = Map22Scene(
        instance_id="map22_l2_branch_loop",
        level="L2",
        capability="partial_graph_backtracking",
        paired_conditions=("history5", "history5_graph_memory"),
        nodes=_forest(
            {
                "A": {"exits": {"N": "B", "E": "C"}},
                "B": {"exits": {"S": "A", "E": "D", "W": "E"}},
                "C": {"exits": {"W": "A", "N": "D"}},
                "D": {"exits": {"W": "B", "S": "C"}},
                "E": {"exits": {"E": "B"}},
            }
        ),
        start="A",
        target="D",
        move_budget=12,
        note="Four-cycle plus a dead-end branch E: dead ends force backtracking.",
    )
    scenes["map22_l2_dead_end_spur"] = Map22Scene(
        instance_id="map22_l2_dead_end_spur",
        level="L2",
        capability="partial_graph_backtracking",
        paired_conditions=("history5", "history5_graph_memory"),
        nodes=_forest(
            {
                "A": {"exits": {"E": "B"}},
                "B": {"exits": {"W": "A", "NE": "C", "SW": "S"}},
                "C": {"exits": {"SW": "B", "S": "D"}},
                "D": {"exits": {"N": "C", "E": "T"}},
                "S": {"exits": {"NE": "B"}},
                "T": {"exits": {"W": "D"}},
            }
        ),
        start="A",
        target="T",
        move_budget=14,
        note="Two dead-end spurs (S, T) beside the route: repeated-point recognition.",
    )
    scenes["map22_l3_original"] = Map22Scene(
        instance_id="map22_l3_original",
        level="L3",
        capability="spatial_return_memory",
        paired_conditions=("history5", "history5_graph_memory"),
        nodes=_forest(
            {
                "A": {"exits": {"NE": "B", "SE": "C"}},
                "B": {"exits": {"SW": "A", "NE": "D", "E": "E"}},
                "C": {"exits": {"NW": "A", "E": "F"}},
                "D": {"exits": {"SW": "B", "E": "G"}},
                "E": {"exits": {"W": "B", "S": "F", "E": "H"}},
                "F": {"exits": {"W": "C", "N": "E", "NE": "I"}},
                "G": {"exits": {"W": "D", "E": "J"}},
                "H": {"exits": {"W": "E", "S": "I", "E": "K"}},
                "I": {"exits": {"SW": "F", "N": "H", "E": "L"}},
                "J": {"exits": {"W": "G", "S": "K"}},
                "K": {"exits": {"W": "H", "N": "J", "S": "L"}},
                "L": {"exits": {"W": "I", "N": "K"}},
            }
        ),
        start="A",
        target="L",
        move_budget=30,
        note="Reviewed V4 12-node forest, unchanged geometry.",
    )
    return scenes


# --------------------------------------------------------------------------- #
# MAP-08 scenes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Map08Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    edges: dict[str, tuple[str, str]]
    signatures: dict[str, dict[str, str]]
    leak_by_seed: dict[int, str]
    note: str
    water_limit: float = 7.0
    sealant_count: int = 1
    test_ticks: int = 2
    wrong_repair_ticks: int = 4
    map_id: str = "MAP-08"

    def env_kwargs(self) -> dict[str, Any]:
        return {
            "edges": self.edges,
            "signatures": self.signatures,
            "leak_by_seed": self.leak_by_seed,
            "water_limit": self.water_limit,
            "sealant_count": self.sealant_count,
            "test_ticks": self.test_ticks,
            "wrong_repair_ticks": self.wrong_repair_ticks,
        }


_V4_EDGES = {
    "A_B": ("A", "B"),
    "B_C": ("B", "C"),
    "C_D": ("C", "D"),
    "D_E": ("D", "E"),
    "E_F": ("E", "F"),
    "F_A": ("F", "A"),
    "X_A": ("X", "A"),
    "X_C": ("X", "C"),
    "Y_D": ("Y", "D"),
    "Y_F": ("Y", "F"),
}


def _build_map08_scenes() -> dict[str, Map08Scene]:
    scenes: dict[str, Map08Scene] = {}
    scenes["map08_l1_two_candidate"] = Map08Scene(
        instance_id="map08_l1_two_candidate",
        level="L1",
        capability="single_test_diagnosis",
        paired_conditions=("no_hypothesis_table", "hypothesis_table"),
        edges=_V4_EDGES,
        signatures={"B": {"X": "pulse_amber", "Y": "pulse_slate"},
                    "D": {"X": "pulse_slate", "Y": "pulse_cobalt"}},
        leak_by_seed={0: "B", 1: "D"},
        note="Two candidates: one test already distinguishes them.",
    )
    scenes["map08_l2_alt_coverage"] = Map08Scene(
        instance_id="map08_l2_alt_coverage",
        level="L2",
        capability="multi_step_information_gain",
        paired_conditions=("no_hypothesis_table", "hypothesis_table"),
        edges=_V4_EDGES,
        signatures={
            "B": {"X": "pulse_amber", "Y": "pulse_amber"},
            "D": {"X": "pulse_slate", "Y": "pulse_amber"},
            "F": {"X": "pulse_slate", "Y": "pulse_slate"},
        },
        leak_by_seed={0: "B", 1: "D", 2: "F"},
        note="Three candidates with altered sensor coverage; X alone is unambiguous here.",
    )
    scenes["map08_l2_alt_candidates"] = Map08Scene(
        instance_id="map08_l2_alt_candidates",
        level="L2",
        capability="multi_step_information_gain",
        paired_conditions=("no_hypothesis_table", "hypothesis_table"),
        edges={
            "A_X": ("A", "X"),
            "A_Y": ("A", "Y"),
            "X_B": ("X", "B"),
            "X_C": ("X", "C"),
            "Y_C": ("Y", "C"),
            "Y_D": ("Y", "D"),
        },
        signatures={
            "B": {"X": "pulse_amber", "Y": "pulse_slate"},
            "C": {"X": "pulse_amber", "Y": "pulse_cobalt"},
            "D": {"X": "pulse_slate", "Y": "pulse_cobalt"},
        },
        leak_by_seed={0: "B", 1: "C", 2: "D"},
        note="Compact hub topology with a non-V4 candidate C sharing two stations.",
    )
    scenes["map08_l3_original"] = Map08Scene(
        instance_id="map08_l3_original",
        level="L3",
        capability="active_leak_diagnosis",
        paired_conditions=("no_hypothesis_table", "hypothesis_table"),
        edges=_V4_EDGES,
        signatures={
            "B": {"X": "pulse_amber", "Y": "pulse_slate"},
            "D": {"X": "pulse_slate", "Y": "pulse_cobalt"},
            "F": {"X": "pulse_slate", "Y": "pulse_slate"},
        },
        leak_by_seed={**{seed: "B" for seed in range(0, 4)},
                      **{seed: "D" for seed in range(4, 8)},
                      **{seed: "F" for seed in range(8, 12)}},
        note="Reviewed V4 diagnosis scene, unchanged.",
    )
    return scenes


# --------------------------------------------------------------------------- #
# MAP-26 scenes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Map26Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    fault_part: str
    spares: int
    note: str
    feedback_mode: str = "full"
    map_id: str = "MAP-26"

    def env_kwargs(self) -> dict[str, Any]:
        return {
            "fault_part": self.fault_part,
            "spares": self.spares,
        }


def _build_map26_scenes() -> dict[str, Map26Scene]:
    recovery_conditions = ("recovery_full", "recovery_structured", "recovery_hidden")
    return {
        "map26_l1_antenna_fault": Map26Scene(
            instance_id="map26_l1_antenna_fault",
            level="L1",
            capability="single_fault_diagnosis",
            paired_conditions=("free_diagnosis",),
            fault_part="antenna_coupler",
            spares=2,
            note="Antenna fault with ample spares; a single correct replacement suffices.",
        ),
        "map26_l2_power_fault": Map26Scene(
            instance_id="map26_l2_power_fault",
            level="L2",
            capability="diagnosis_with_feedback_correction",
            paired_conditions=("free_diagnosis",),
            fault_part="power_regulator",
            spares=2,
            note="Power fault; an early wrong replacement forces a correction.",
        ),
        "map26_l3_software_fault": Map26Scene(
            instance_id="map26_l3_software_fault",
            level="L3",
            capability="diagnosis_under_tight_spares",
            paired_conditions=("free_diagnosis",),
            fault_part="software_image",
            spares=2,
            note="Software fault with the full three-test diagnosis.",
        ),
        "map26_l2_spare_rich": Map26Scene(
            instance_id="map26_l2_spare_rich",
            level="L2",
            capability="diagnosis_with_feedback_correction",
            paired_conditions=("free_diagnosis",),
            fault_part="power_regulator",
            spares=3,
            note="Power fault with a larger spare budget than the reviewed V4 scene.",
        ),
        "map26_recovery_antenna": Map26Scene(
            instance_id="map26_recovery_antenna",
            level="L3",
            capability="feedback_correction",
            paired_conditions=recovery_conditions,
            fault_part="antenna_coupler",
            spares=2,
            note="Registered wrong-replacement prefix; three information-equal feedback modes.",
        ),
    }


# --------------------------------------------------------------------------- #
# MAP-18 scenes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Map18Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    fault_edge: frozenset[str]
    fault_window: tuple[int, int]
    fault_enabled: bool
    alert_tick: int
    horizon: int
    success_threshold: int
    note: str
    map_id: str = "MAP-18"

    def env_kwargs(self) -> dict[str, Any]:
        return {
            "fault_edge": self.fault_edge,
            "fault_window": self.fault_window,
            "fault_enabled": self.fault_enabled,
            "alert_tick": self.alert_tick,
            "horizon": self.horizon,
            "success_threshold": self.success_threshold,
        }


def _build_map18_scenes() -> dict[str, Map18Scene]:
    return {
        "map18_l1_no_fault": Map18Scene(
            instance_id="map18_l1_no_fault",
            level="L1",
            capability="static_dispatch",
            paired_conditions=("alert_off", "alert_on"),
            fault_edge=frozenset(("R2", "R3")),
            fault_window=(5, 10),
            fault_enabled=False,
            alert_tick=4,
            horizon=12,
            success_threshold=13,
            note="No fault: static dispatch only.",
        ),
        "map18_l2_short_closure": Map18Scene(
            instance_id="map18_l2_short_closure",
            level="L2",
            capability="known_fault_local_reroute",
            paired_conditions=("alert_off", "alert_on"),
            fault_edge=frozenset(("R2", "R3")),
            fault_window=(5, 8),
            fault_enabled=True,
            alert_tick=4,
            horizon=12,
            success_threshold=13,
            note="Shorter R2-R3 closure: recovery fits inside the horizon.",
        ),
        "map18_l3_original": Map18Scene(
            instance_id="map18_l3_original",
            level="L3",
            capability="online_uncertain_fault_replanning",
            paired_conditions=("alert_off", "alert_on"),
            fault_edge=frozenset(("R2", "R3")),
            fault_window=(5, 10),
            fault_enabled=True,
            alert_tick=4,
            horizon=12,
            success_threshold=13,
            note="Reviewed V4 fault window, unchanged.",
        ),
        "map18_l3_long_closure": Map18Scene(
            instance_id="map18_l3_long_closure",
            level="L3",
            capability="online_uncertain_fault_replanning",
            paired_conditions=("alert_off", "alert_on"),
            fault_edge=frozenset(("R2", "R3")),
            fault_window=(5, 12),
            fault_enabled=True,
            alert_tick=4,
            horizon=12,
            success_threshold=13,
            note="Longer closure: one opposite-direction service must be canceled.",
        ),
    }


# --------------------------------------------------------------------------- #
# MAP-30 scenes
# --------------------------------------------------------------------------- #
def _two_event_case() -> Map30Case:
    nodes = frozenset({"H", "M", "P", "Q", "J"})
    edges = frozenset(
        {frozenset(("H", "M")), frozenset(("M", "P")), frozenset(("P", "Q")),
         frozenset(("H", "J")), frozenset(("Q", "J"))}
    )
    evidence = {
        "R7_DOCKET": {
            "location": "M",
            "source_class": "sealed_envelope",
            "fact": {"document_id": "R7", "requires_clerk_interview": True},
            "text": "档案柜里的R7封套要求值班员当面核验。",
        },
        "R7_CODE_INDEX": {
            "location": "M",
            "source_class": "signed_duty_archive",
            "fact": {"document_id": "R7", "M2": "IVO_KEST"},
            "text": "R7暗码索引写明：M-2对应机修员伊沃·凯斯特。",
        },
        "P_TALLY_0100": {
            "location": "P",
            "source_class": "physical_receipt",
            "fact": {"time": "01:00", "location": "P", "object": "span_bolt", "signed_code": "M2"},
            "text": "泵房领料回执记载：01:00，拉杆螺栓由M-2签收。",
        },
        "P_WITNESS_TALLY": {
            "location": "P",
            "source_class": "witness_confirmation",
            "fact": {"time": "01:00", "location": "P", "object": "span_bolt", "signed_code": "M2"},
            "text": "值夜工核对回执后确认，01:00是M-2本人取走拉杆螺栓。",
        },
        "Q_GATE_0140": {
            "location": "Q",
            "source_class": "mechanical_register",
            "fact": {
                "time": "01:40",
                "location": "Q",
                "mechanism": "gate_counter",
                "duty_code": "M2",
            },
            "text": "闸门计数器在01:40推进一格，操作牌刻着M-2。",
        },
        "Q_WITNESS_GATE": {
            "location": "Q",
            "source_class": "witness_confirmation",
            "fact": {"time": "01:40", "location": "Q", "route": "P_Q_duct", "duty_code": "M2"},
            "text": "巡渠人看到泵房领料记录后，才想起M-2于01:40从P-Q暗渠进入。",
        },
    }
    node_evidence = {"M": {"R7_DOCKET"}, "P": {"P_TALLY_0100"}, "Q": {"Q_GATE_0140"}}
    entry_allowed = {
        "R7_CODEBOOK": {"R7_CODE_INDEX"},
        "EVENT_1_TALLY": {"P_TALLY_0100", "P_WITNESS_TALLY"},
        "EVENT_2_GATE": {"Q_GATE_0140", "Q_WITNESS_GATE"},
    }
    claims = (
        V4EventClaim(event_id="EVENT_1_TALLY", time="01:00", location="P", duty_code="M2"),
        V4EventClaim(event_id="EVENT_2_GATE", time="01:40", location="Q", duty_code="M2"),
    )
    witness_rules: dict[str, tuple[WitnessRule, ...]] = {
        "REPAIR_CLERK": (
            WitnessRule(
                "R7_CONFIRMED",
                ("R7_CODE_INDEX",),
                "R7暗码索引写明：M-2对应机修员伊沃·凯斯特。",
                requires_shown_evidence="R7_DOCKET",
                condition_key="R7_with_docket",
            ),
            WitnessRule("R7_UNLOCATED", (), "没有封套编号，我无法确认你要查哪份值勤表。",
                        condition_key="R7_without_docket"),
        ),
        "PUMP_WATCH": (
            WitnessRule(
                "P_WITNESS_TALLY",
                ("P_WITNESS_TALLY",),
                "核对回执后，我确认01:00是M-2本人取走拉杆螺栓。",
                requires_shown_evidence="P_TALLY_0100",
                condition_key="TALLY_with_stub",
            ),
            WitnessRule("P_GENERIC_TALLY", (), "我记得有人领过料，但没有回执就想不起时刻。",
                        condition_key="TALLY_without_stub"),
        ),
        "CANAL_WATCH": (
            WitnessRule(
                "Q_WITNESS_GATE",
                ("Q_WITNESS_GATE",),
                "看到泵房领料记录后，我想起M-2于01:40从P-Q暗渠进入。",
                requires_casebook_entry="EVENT_1_TALLY",
                condition_key="GATE_with_event_1",
            ),
            WitnessRule("Q_GENERIC_GATE", (), "夜里闸门开过；我记不清是哪一次。",
                        condition_key="GATE_without_event_1"),
        ),
    }
    return Map30Case(
        nodes=nodes,
        edges=edges,
        node_evidence=node_evidence,
        node_npcs={"M": "REPAIR_CLERK", "P": "PUMP_WATCH", "Q": "CANAL_WATCH"},
        entry_allowed=entry_allowed,
        entry_order=("R7_CODEBOOK", "EVENT_1_TALLY", "EVENT_2_GATE"),
        claims=claims,
        evidence=evidence,
        witness_rules=witness_rules,
        culprit="IVO_KEST",
        code_entry="R7_CODEBOOK",
        code_index_evidence="R7_CODE_INDEX",
        deadline=30,
        casebook_capacity=3,
    )


def _three_event_alt_case() -> Map30Case:
    nodes = frozenset({"H", "R", "W", "X", "Z", "J"})
    edges = frozenset(
        {frozenset(("H", "R")), frozenset(("R", "W")), frozenset(("W", "X")),
         frozenset(("X", "Z")), frozenset(("Z", "H")), frozenset(("H", "J"))}
    )
    evidence = {
        "S9_SEAL": {
            "location": "R",
            "source_class": "sealed_cache",
            "fact": {"document_id": "S9", "requires_vault_interview": True},
            "text": "金库内的S9封漆匣要求库管当面核验。",
        },
        "S9_CODE_INDEX": {
            "location": "R",
            "source_class": "signed_duty_archive",
            "fact": {"document_id": "S9", "M7": "NELL_ORAV"},
            "text": "S9暗码索引写明：M-7对应库管内尔·奥拉夫。",
        },
        "W_SLIP_2205": {
            "location": "W",
            "source_class": "physical_receipt",
            "fact": {"time": "22:05", "location": "W", "signed_code": "M7"},
            "text": "装卸台运单记载：22:05由M-7签收。",
        },
        "W_WITNESS_SLIP": {
            "location": "W",
            "source_class": "witness_confirmation",
            "fact": {"time": "22:05", "location": "W", "signed_code": "M7"},
            "text": "装卸组长核对运单后确认22:05是M-7本人签字。",
        },
        "X_LEDGER_2230": {
            "location": "X",
            "source_class": "physical_trace",
            "fact": {"time": "22:30", "location": "X", "duty_code": "M7"},
            "text": "账房的炭笔账页停在22:30，页脚压着M-7印。",
        },
        "X_WITNESS_LEDGER": {
            "location": "X",
            "source_class": "witness_confirmation",
            "fact": {"time": "22:30", "location": "X", "duty_code": "M7"},
            "text": "账房先生看到装卸运单后，想起M-7在22:30翻过账本。",
        },
        "Z_BELL_2300": {
            "location": "Z",
            "source_class": "mechanical_register",
            "fact": {
                "time": "23:00",
                "location": "Z",
                "mechanism": "vault_bell",
                "duty_code": "M7",
            },
            "text": "金库铃绳计数器在23:00推进，铜牌刻着M-7。",
        },
        "Z_WITNESS_BELL": {
            "location": "Z",
            "source_class": "witness_confirmation",
            "fact": {"time": "23:00", "location": "Z", "route": "W_Z_shaft", "duty_code": "M7"},
            "text": "看库人看到账房账页后，才想起M-7于23:00从W-Z竖井进入拉动铃绳。",
        },
    }
    node_evidence = {
        "R": {"S9_SEAL"},
        "W": {"W_SLIP_2205"},
        "X": {"X_LEDGER_2230"},
        "Z": {"Z_BELL_2300"},
    }
    entry_allowed = {
        "S9_CODEBOOK": {"S9_CODE_INDEX"},
        "EVENT_1_SLIP": {"W_SLIP_2205", "W_WITNESS_SLIP"},
        "EVENT_2_LEDGER": {"X_LEDGER_2230", "X_WITNESS_LEDGER"},
        "EVENT_3_BELL": {"Z_BELL_2300", "Z_WITNESS_BELL"},
    }
    claims = (
        V4EventClaim(event_id="EVENT_1_SLIP", time="22:05", location="W", duty_code="M7"),
        V4EventClaim(event_id="EVENT_2_LEDGER", time="22:30", location="X", duty_code="M7"),
        V4EventClaim(event_id="EVENT_3_BELL", time="23:00", location="Z", duty_code="M7"),
    )
    witness_rules: dict[str, tuple[WitnessRule, ...]] = {
        "VAULT_KEEPER": (
            WitnessRule("S9_CONFIRMED", ("S9_CODE_INDEX",),
                        "S9暗码索引写明：M-7对应库管内尔·奥拉夫。",
                        requires_shown_evidence="S9_SEAL", condition_key="S9_with_seal"),
            WitnessRule("S9_UNLOCATED", (), "没有封漆匣，我无法确认你要查哪份值勤表。",
                        condition_key="S9_without_seal"),
        ),
        "DOCK_LEAD": (
            WitnessRule("W_WITNESS_SLIP", ("W_WITNESS_SLIP",),
                        "核对运单后，我确认22:05是M-7本人签字。",
                        requires_shown_evidence="W_SLIP_2205", condition_key="SLIP_with_stub"),
            WitnessRule("W_GENERIC_SLIP", (), "有人签过运单，但没有原件我想不起时刻。",
                        condition_key="SLIP_without_stub"),
        ),
        "LEDGER_CLERK": (
            WitnessRule("X_WITNESS_LEDGER", ("X_WITNESS_LEDGER",),
                        "看到装卸运单后，我想起M-7在22:30翻过账本。",
                        requires_casebook_entry="EVENT_1_SLIP",
                        condition_key="LEDGER_with_event_1"),
            WitnessRule("X_GENERIC_LEDGER", (), "账本被人翻过，我记不清时间。",
                        condition_key="LEDGER_without_event_1"),
        ),
        "VAULT_WATCH": (
            WitnessRule("Z_WITNESS_BELL", ("Z_WITNESS_BELL",),
                        "看到账房账页后，我想起M-7于23:00从W-Z竖井进入拉动铃绳。",
                        requires_casebook_entry="EVENT_2_LEDGER",
                        condition_key="BELL_with_event_2"),
            WitnessRule("Z_GENERIC_BELL", (), "夜里铃绳动过，我记不清是哪一次。",
                        condition_key="BELL_without_event_2"),
        ),
    }
    return Map30Case(
        nodes=nodes,
        edges=edges,
        node_evidence=node_evidence,
        node_npcs={"R": "VAULT_KEEPER", "W": "DOCK_LEAD", "X": "LEDGER_CLERK", "Z": "VAULT_WATCH"},
        entry_allowed=entry_allowed,
        entry_order=("S9_CODEBOOK", "EVENT_1_SLIP", "EVENT_2_LEDGER", "EVENT_3_BELL"),
        claims=claims,
        evidence=evidence,
        witness_rules=witness_rules,
        culprit="NELL_ORAV",
        code_entry="S9_CODEBOOK",
        code_index_evidence="S9_CODE_INDEX",
        deadline=36,
        casebook_capacity=4,
    )


@dataclass(frozen=True)
class Map30Scene:
    instance_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]
    case: Map30Case | None
    note: str
    map_id: str = "MAP-30"

    def env_kwargs(self) -> dict[str, Any]:
        return {"case": self.case} if self.case is not None else {}


def _build_map30_scenes() -> dict[str, Map30Scene]:
    return {
        "map30_l1_two_event_case": Map30Scene(
            instance_id="map30_l1_two_event_case",
            level="L1",
            capability="short_evidence_chain",
            paired_conditions=("history_full", "history5", "history5_casebook"),
            case=_two_event_case(),
            note="Two-event case on a five-node map with a three-entry casebook.",
        ),
        "map30_l2_three_event_alt": Map30Scene(
            instance_id="map30_l2_three_event_alt",
            level="L2",
            capability="long_gap_evidence_memory",
            paired_conditions=("history_full", "history5", "history5_casebook"),
            case=_three_event_alt_case(),
            note="Three-event case with two evidence nodes and a different culprit.",
        ),
        "map30_l3_original": Map30Scene(
            instance_id="map30_l3_original",
            level="L3",
            capability="long_gap_evidence_memory",
            paired_conditions=("history_full", "history5", "history5_casebook"),
            case=None,
            note="Reviewed V4 case, unchanged.",
        ),
    }


def all_scenes() -> dict[str, Any]:
    scenes: dict[str, Any] = {}
    scenes.update(_build_map16_scenes())
    scenes.update(_build_map22_scenes())
    scenes.update(_build_map08_scenes())
    scenes.update(_build_map26_scenes())
    scenes.update(_build_map18_scenes())
    scenes.update(_build_map30_scenes())
    return scenes
