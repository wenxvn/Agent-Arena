"""V4 MAP-16, atomic single-track reservations and deadlock control."""

from __future__ import annotations

from collections import Counter, deque
from itertools import product
from typing import Any

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4Map16Observation,
    V4Status,
)

NODES = ("A", "X", "M", "Y", "B", "D")
ADJACENCY = {
    "A": ("X",),
    "X": ("A", "M"),
    "M": ("X", "Y", "D"),
    "Y": ("M", "B"),
    "B": ("Y",),
    "D": ("M",),
}
DIRECTIONS = {
    "a": {"A": ("X",), "X": ("M",), "M": ("Y", "D"), "D": ("M",), "Y": ("B",), "B": ()},
    "b": {"B": ("Y",), "Y": ("M",), "M": ("X", "D"), "D": ("M",), "X": ("A",), "A": ()},
}
DEFAULT_SEGMENT_CAPACITIES = {"AX": 1, "XM": 1, "MY": 1, "YB": 1, "MD": 1}


def _section(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


class Map16Environment(ScenarioV4Environment):
    map_id = "MAP-16"

    def __init__(
        self,
        *,
        step_limit: int = 100,
        adjacency: dict[str, tuple[str, ...]] | None = None,
        directions: dict[str, dict[str, tuple[str, ...]]] | None = None,
        start_positions: dict[str, str] | None = None,
        goals: dict[str, str] | None = None,
        segment_capacities: dict[str, int] | None = None,
        node_capacities: dict[str, int] | None = None,
        sidings: frozenset[str] = frozenset({"D"}),
    ) -> None:
        # Optional parameters let the V6 fixture layer build structurally different
        # single-track layouts (one or more trains). Defaults reproduce the reviewed
        # V4 MAP-16 scene exactly.
        self.step_limit = step_limit
        self.adjacency = adjacency if adjacency is not None else ADJACENCY
        self.directions = directions if directions is not None else DIRECTIONS
        self.start_positions = (
            start_positions if start_positions is not None else {"a": "A", "b": "B"}
        )
        self.goals = goals if goals is not None else {"a": "B", "b": "A"}
        self.segment_capacities = (
            segment_capacities
            if segment_capacities is not None
            else dict(DEFAULT_SEGMENT_CAPACITIES)
        )
        self.node_capacities = (
            node_capacities
            if node_capacities is not None
            else {node: 1 for node in NODES}
        )
        self.sidings = sidings
        self.trains = tuple(self.start_positions)
        self.seed = 0
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(0)

    @property
    def tick(self) -> int:
        return self.current_tick

    def _reset_state(self, seed: int) -> None:
        if seed not in {0, 1, 2}:
            raise ValueError("MAP-16 only accepts the three registered fixed-scene repeat labels.")
        self.positions = dict(self.start_positions)
        self.current_tick = 0
        self.pending: dict[str, str] = {}
        self.last_action_result = "INITIAL"
        self.conflicts = {
            key: 0
            for key in (
                "SECTION_RESERVATION_CONFLICT",
                "HEAD_ON_SWAP",
                "NODE_CAPACITY_CONFLICT",
                "SIDING_CAPACITY_CONFLICT",
                "DEADLOCK",
            )
        }
        self.route_action_count = 0
        self.deadlock_count = 0

    def _observation(self) -> V4Map16Observation:
        return V4Map16Observation(
            tick=self.current_tick,
            topology={node: self.adjacency[node] for node in self.adjacency},
            train_route_directions={train: self.directions[train] for train in self.trains},
            train_positions=dict(self.positions),
            train_goals=dict(self.goals),
            segment_capacities=dict(self.segment_capacities),
            node_capacities=dict(self.node_capacities),
            occupied_nodes=tuple(sorted(self.positions.values())),
            pending_route_reservations=dict(self.pending),
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _route(self, action: ScenarioV4Action) -> str:
        if action.train_id not in self.trains or action.next_node is None:
            return self._reject("INVALID_ROUTE")
        train = action.train_id
        destination = action.next_node
        current = self.positions[train]
        if train in self.pending:
            return self._reject("INVALID_ROUTE")
        if destination not in self.directions[train][current]:
            return self._reject("INVALID_ROUTE")
        section = _section(current, destination)
        for other_train, other_destination in self.pending.items():
            other_current = self.positions[other_train]
            if _section(other_current, other_destination) == section:
                reason = (
                    "HEAD_ON_SWAP"
                    if current == other_destination and destination == other_current
                    else "SECTION_RESERVATION_CONFLICT"
                )
                self.conflicts[reason] += 1
                self.status = V4Status.FAILURE
                self.terminal_reason = reason
                return self._finish(reason)
        self.pending[train] = destination
        self.route_action_count += 1
        return self._finish("ROUTE_RESERVED")

    def _apply(self, action: ScenarioV4Action) -> str:
        if action.tool == "inspect_network":
            return self._finish("NETWORK_INSPECTED")
        if action.tool in {"set_route", "occupy_siding"}:
            if action.tool == "occupy_siding":
                if (
                    action.train_id not in self.trains
                    or action.next_node not in self.sidings
                    or action.next_node
                    not in self.directions[action.train_id][self.positions[action.train_id]]
                ):
                    return self._reject("INVALID_ROUTE")
            return self._route(action)
        if action.tool == "release_section":
            release_train = action.train_id
            if release_train not in self.pending:
                return self._reject("INVALID_ROUTE")
            current = self.positions[release_train]
            if action.section_id not in {
                f"{current}{self.pending[release_train]}",
                f"{self.pending[release_train]}{current}",
                "_".join(sorted((current, self.pending[release_train]))),
            }:
                return self._reject("INVALID_ROUTE")
            del self.pending[release_train]
            return self._finish("ROUTE_RELEASED")
        if action.tool == "move_train":
            if not self.pending:
                return self._reject("NO_PENDING_ROUTE")
            following = dict(self.positions)
            used: dict[frozenset[str], str] = {}
            for moving_train, destination in self.pending.items():
                current = self.positions[moving_train]
                section = _section(current, destination)
                if section in used:
                    other = used[section]
                    reason = (
                        "HEAD_ON_SWAP"
                        if current == self.positions[other]
                        and destination == self.positions[other]
                        else "SECTION_RESERVATION_CONFLICT"
                    )
                    return self._terminal_conflict(reason)
                used[section] = moving_train
                following[moving_train] = destination
            collisions = [
                node for node, count in Counter(following.values()).items() if count > 1
            ]
            if collisions:
                return self._terminal_conflict(
                    "SIDING_CAPACITY_CONFLICT"
                    if any(node in self.sidings for node in collisions)
                    else "NODE_CAPACITY_CONFLICT"
                )
            self.positions = following
            self.pending.clear()
            self.current_tick += 1
            if all(self.positions[train] == self.goals[train] for train in self.trains):
                self.status = V4Status.SUCCESS
                self.terminal_reason = "GATE_OPENED"
                return self._finish("GATE_OPENED")
            if not self._has_safe_completion(tuple(self.positions[train] for train in self.trains)):
                self.conflicts["DEADLOCK"] += 1
                self.deadlock_count += 1
                self.status = V4Status.FAILURE
                self.terminal_reason = "DEADLOCK"
                return self._finish("DEADLOCK")
            return self._finish("MOVES_COMMITTED")
        return self._reject("ACTION_NOT_AVAILABLE")

    def _terminal_conflict(self, reason: str) -> str:
        self.conflicts[reason] += 1
        self.status = V4Status.FAILURE
        self.terminal_reason = reason
        return self._finish(reason)

    def _reject(self, reason: str) -> str:
        self.last_action_result = reason
        return reason

    def _invalid_action(self) -> str:
        return self._reject("INVALID_ACTION_SCHEMA")

    def _finish(self, result: str) -> str:
        self.last_action_result = result
        return result

    def _successors(self, state: tuple[str, ...]) -> set[tuple[str, ...]]:
        options = [
            sorted({state[index], *self.directions[train][state[index]]})
            for index, train in enumerate(self.trains)
        ]
        results: set[tuple[str, ...]] = set()
        for combination in product(*options):
            if len(set(combination)) != len(combination):
                continue
            blocked = False
            for left in range(len(combination)):
                for right in range(left + 1, len(combination)):
                    if combination[left] != state[left] and combination[right] != state[right]:
                        if _section(state[left], combination[left]) == _section(
                            state[right], combination[right]
                        ):
                            blocked = True
            if not blocked:
                results.add(combination)
        return results

    def _has_safe_completion(self, start: tuple[str, ...]) -> bool:
        goal = tuple(self.goals[train] for train in self.trains)
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                return True
            for following in self._successors(current):
                if following not in seen:
                    seen.add(following)
                    queue.append(following)
        return False

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "tick": self.current_tick,
            "positions": dict(self.positions),
            "pending": dict(self.pending),
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "conflicts": dict(self.conflicts),
        }

    def metrics(self) -> dict[str, Any]:
        shortest, _ = self._shortest_schedule()
        return {
            "success": self.is_success,
            "makespan_ticks": self.current_tick,
            "optimality_gap": self.current_tick - shortest if self.is_success else None,
            "deadlock_count": self.deadlock_count,
            **{
                f"{key.lower()}_count": value
                for key, value in self.conflicts.items()
                if key != "DEADLOCK"
            },
            "route_action_count": self.route_action_count,
            "terminal_reason": self.terminal_reason,
        }

    def _shortest_schedule(self) -> tuple[int, int]:
        start = tuple(self.start_positions[train] for train in self.trains)
        goal = tuple(self.goals[train] for train in self.trains)
        distances = {start: 0}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for following in self._successors(current):
                if following not in distances:
                    distances[following] = distances[current] + 1
                    queue.append(following)
        return distances.get(goal, -1), len(distances)
