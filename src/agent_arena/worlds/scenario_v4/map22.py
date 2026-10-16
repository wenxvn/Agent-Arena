"""V4 MAP-22, local signposts and Agent-owned route memory."""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4Map22Observation,
    V4MemoryFact,
    V4Status,
)

NODES: dict[str, dict[str, Any]] = {
    "A": {
        "sign": "CAMP_LANTERN_RING",
        "silhouette": "forked_lantern",
        "feature": "three_brass_prongs_and_ring_notch",
        "exits": {"NE": "B", "SE": "C"},
    },
    "B": {
        "sign": "B_RED_NICK",
        "silhouette": "three_pronged_forkpost",
        "feature": "red_diagonal_nick_at_northern_foot",
        "exits": {"SW": "A", "NE": "D", "E": "E"},
    },
    "C": {
        "sign": "C_WHITE_BIRCH_THREAD",
        "silhouette": "pale_trunk",
        "feature": "single_red_thread_on_white_birch",
        "exits": {"NW": "A", "E": "F"},
    },
    "D": {
        "sign": "D_TWIN_CUT_STONE",
        "silhouette": "narrow_stone",
        "feature": "two_vertical_cuts_facing_uphill",
        "exits": {"SW": "B", "E": "G"},
    },
    "E": {
        "sign": "E_ROOT_CROSSBAR",
        "silhouette": "three_pronged_forkpost",
        "feature": "two_pale_roots_under_eastern_rail",
        "exits": {"W": "B", "S": "F", "E": "H"},
    },
    "F": {
        "sign": "F_CRACKED_BELL",
        "silhouette": "hanging_bell",
        "feature": "bell_crack_open_to_north",
        "exits": {"W": "C", "N": "E", "NE": "I"},
    },
    "G": {
        "sign": "G_BLUE_CAIRN",
        "silhouette": "three_stone_cairn",
        "feature": "blue_thread_under_top_stone",
        "exits": {"W": "D", "E": "J"},
    },
    "H": {
        "sign": "H_TWIN_BAR_SADDLE",
        "silhouette": "three_pronged_forkpost",
        "feature": "paired_horizontal_cuts_below_saddle",
        "exits": {"W": "E", "S": "I", "E": "K"},
    },
    "I": {
        "sign": "I_MOSS_ARCH",
        "silhouette": "basalt_arch",
        "feature": "one_moss_spot_on_inner_left_pillar",
        "exits": {"SW": "F", "N": "H", "E": "L"},
    },
    "J": {
        "sign": "J_RED_RESIN_PINE",
        "silhouette": "bent_pine",
        "feature": "two_red_resin_drops_on_east_bend",
        "exits": {"W": "G", "S": "K"},
    },
    "K": {
        "sign": "K_MOSS_WEDGE",
        "silhouette": "three_pronged_forkpost",
        "feature": "moss_wedge_on_western_foot",
        "exits": {"W": "H", "N": "J", "S": "L"},
    },
    "L": {
        "sign": "RUIN_TRIPLE_ARCH",
        "silhouette": "dark_arch",
        "feature": "three_nested_black_arcs_over_stone_threshold",
        "exits": {"W": "I", "N": "K"},
    },
}
MAX_FACTS = 32


class Map22Environment(ScenarioV4Environment):
    map_id = "MAP-22"

    def __init__(
        self,
        *,
        memory_enabled: bool = True,
        step_limit: int = 100,
        nodes: dict[str, dict[str, Any]] | None = None,
        start_node: str = "A",
        target_node: str = "L",
        move_budget: int = 30,
        max_facts: int = MAX_FACTS,
        optimal_moves: int = 8,
        disabled_memory_result: str = "ACTION_NOT_AVAILABLE",
    ) -> None:
        # Optional parameters let the V6 fixture layer build structurally different
        # signpost forests from the same rule engine. The defaults reproduce the
        # reviewed V4 MAP-22 scene exactly.
        self.memory_enabled = memory_enabled
        self.step_limit = step_limit
        self.nodes = nodes if nodes is not None else NODES
        self.start_node = start_node
        self.target_node = target_node
        self.move_budget = move_budget
        self.max_facts = max_facts
        self.optimal_moves = optimal_moves
        self.disabled_memory_result = disabled_memory_result
        self.seed = 0
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(0)

    @property
    def tick(self) -> int:
        return self.movement_steps

    def _reset_state(self, seed: int) -> None:
        if seed not in {0, 1, 2}:
            raise ValueError("MAP-22 only accepts the three registered fixed-scene repeat labels.")
        self.node = self.start_node
        self.movement_steps = 0
        self.target_visited = False
        self.active_goal = self.nodes[self.target_node]["sign"]
        self.memory: list[V4MemoryFact] = []
        self.last_inspected_node: str | None = None
        self.last_traversed_edge: tuple[str, str, str] | None = None
        self.unique_nodes = {self.start_node}
        self.unique_edges: set[frozenset[str]] = set()
        self.node_visits: dict[str, int] = {self.start_node: 1}
        self.edge_traversals: dict[frozenset[str], int] = {}
        self.last_result = "INITIAL"

    def _observation(self) -> V4Map22Observation:
        detail = None
        if self.last_inspected_node == self.node:
            detail = {
                "sign_id": self.nodes[self.node]["sign"],
                "distinctive_feature": self.nodes[self.node]["feature"],
            }
        return V4Map22Observation(
            movement_steps=self.movement_steps,
            current_coarse_silhouette=self.nodes[self.node]["silhouette"],
            visible_exit_bearings=tuple(sorted(self.nodes[self.node]["exits"])),
            inspected_current_sign_detail=detail,
            active_goal_marker=self.active_goal,
            agent_authored_memory_journal=tuple(self.memory),
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _apply(self, action: ScenarioV4Action) -> str:
        if action.tool == "observe_signpost":
            self.last_inspected_node = self.node
            return self._finish("SIGNPOST_OBSERVED")
        if action.tool == "write_memory":
            if not self.memory_enabled:
                return self._finish(self.disabled_memory_result)
            assert action.facts is not None
            if len(self.memory) + len(action.facts) > self.max_facts:
                return self._finish("MEMORY_CAPACITY_EXCEEDED")
            for fact in action.facts:
                if not self._fact_is_grounded(fact):
                    return self._finish("MEMORY_FACT_NOT_OBSERVED")
            self.memory.extend(action.facts)
            return self._finish("MEMORY_WRITTEN")
        if action.tool == "move":
            assert action.bearing is not None
            destination = self.nodes[self.node]["exits"].get(action.bearing)
            if destination is None:
                return self._finish("INVALID_BEARING")
            origin = self.node
            self.node = destination
            self.movement_steps += 1
            self.last_traversed_edge = (origin, action.bearing, destination)
            self.unique_nodes.add(destination)
            self.node_visits[destination] = self.node_visits.get(destination, 0) + 1
            edge = frozenset((origin, destination))
            self.unique_edges.add(edge)
            self.edge_traversals[edge] = self.edge_traversals.get(edge, 0) + 1
            if destination == self.target_node:
                self.target_visited = True
            if (
                self.target_visited
                and destination == self.start_node
                and self.movement_steps <= self.move_budget
            ):
                self.status = V4Status.SUCCESS
                self.terminal_reason = "RETURNED_TO_CAMP_WITH_RUIN_RECORD"
                return self._finish(self.terminal_reason)
            if self.movement_steps >= self.move_budget:
                self.status = V4Status.FAILURE
                self.terminal_reason = "STEP_LIMIT_REACHED"
                return self._finish(self.terminal_reason)
            return self._finish("MOVE_SUCCEEDED")
        if action.tool == "check_goal":
            return self._finish(
                "GOAL_MARKER_CONFIRMED"
                if self.node == self.target_node
                else "GOAL_MARKER_NOT_HERE"
            )
        if action.tool == "return_to_camp":
            self.active_goal = self.nodes[self.start_node]["sign"]
            if (
                self.target_visited
                and self.node == self.start_node
                and self.movement_steps <= self.move_budget
            ):
                self.status = V4Status.SUCCESS
                self.terminal_reason = "RETURNED_TO_CAMP_WITH_RUIN_RECORD"
                return self._finish(self.terminal_reason)
            return self._finish("CAMP_SET_AS_GOAL")
        return self._finish("ACTION_NOT_AVAILABLE")

    def _fact_is_grounded(self, fact: V4MemoryFact) -> bool:
        if fact.fact_type == "node_page":
            node = self.node
            return (
                self.last_inspected_node == node
                and fact.sign_id == self.nodes[node]["sign"]
                and tuple(fact.exit_bearings or ()) == tuple(sorted(self.nodes[node]["exits"]))
            )
        if self.last_traversed_edge is None:
            return False
        origin, bearing, destination = self.last_traversed_edge
        reverse = next(
            key for key, value in self.nodes[destination]["exits"].items() if value == origin
        )
        return (
            fact.from_sign_id == self.nodes[origin]["sign"]
            and fact.departure_bearing == bearing
            and fact.to_sign_id == self.nodes[destination]["sign"]
            and fact.arrival_reverse_bearing == reverse
        )

    def _finish(self, result: str) -> str:
        self.last_result = result
        return result

    def _invalid_action(self) -> str:
        return self._finish("INVALID_ACTION_SCHEMA")

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "node": self.node,
            "movement_steps": self.movement_steps,
            "target_visited": self.target_visited,
            "active_goal": self.active_goal,
            "memory": [fact.model_dump() for fact in self.memory],
            "last_traversed_edge": self.last_traversed_edge,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "success": self.is_success,
            "movement_steps": self.movement_steps,
            "unique_nodes_seen": len(self.unique_nodes),
            "unique_edges_traversed": len(self.unique_edges),
            "repeated_node_visits": sum(self.node_visits.values()) - len(self.node_visits),
            "repeated_edge_traversals": sum(self.edge_traversals.values())
            - len(self.edge_traversals),
            "return_success": self.is_success,
            "shortest_route_gap": (
                self.movement_steps - self.optimal_moves if self.is_success else None
            ),
            "memory_facts_written": len(self.memory),
            "terminal_reason": self.terminal_reason,
        }
