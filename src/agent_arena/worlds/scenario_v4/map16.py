"""V4 MAP-16, atomic single-track reservations and deadlock control."""

from __future__ import annotations

from collections import deque
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


def _section(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


class Map16Environment(ScenarioV4Environment):
    map_id = "MAP-16"

    def __init__(self, *, step_limit: int = 100) -> None:
        self.step_limit = step_limit
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
        self.positions = {"a": "A", "b": "B"}
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
            topology={node: ADJACENCY[node] for node in NODES},
            train_route_directions={train: DIRECTIONS[train] for train in ("a", "b")},
            train_positions=dict(self.positions),
            train_goals={"a": "B", "b": "A"},
            segment_capacities={"AX": 1, "XM": 1, "MY": 1, "YB": 1, "MD": 1},
            node_capacities={node: 1 for node in NODES},
            occupied_nodes=tuple(sorted(self.positions.values())),
            pending_route_reservations=dict(self.pending),
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _route(self, action: ScenarioV4Action) -> str:
        if action.train_id not in {"a", "b"} or action.next_node is None:
            return self._reject("INVALID_ROUTE")
        train = action.train_id
        destination = action.next_node
        current = self.positions[train]
        if train in self.pending:
            return self._reject("INVALID_ROUTE")
        if destination not in DIRECTIONS[train][current]:
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
                    action.next_node != "D"
                    or action.train_id not in {"a", "b"}
                    or self.positions[action.train_id] != "M"
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
                    reason = (
                        "HEAD_ON_SWAP"
                        if current == self.positions[used[section]]
                        and destination == self.positions[used[section]]
                        else "SECTION_RESERVATION_CONFLICT"
                    )
                    return self._terminal_conflict(reason)
                used[section] = moving_train
                following[moving_train] = destination
            if following["a"] == following["b"]:
                return self._terminal_conflict(
                    "SIDING_CAPACITY_CONFLICT"
                    if "D" in following.values()
                    else "NODE_CAPACITY_CONFLICT"
                )
            self.positions = following
            self.pending.clear()
            self.current_tick += 1
            if self.positions == {"a": "B", "b": "A"}:
                self.status = V4Status.SUCCESS
                self.terminal_reason = "GATE_OPENED"
                return self._finish("GATE_OPENED")
            if not self._has_safe_completion((self.positions["a"], self.positions["b"])):
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

    @staticmethod
    def _successors(state: tuple[str, str]) -> set[tuple[str, str]]:
        a, b = state
        a_options = {a, *DIRECTIONS["a"][a]}
        b_options = {b, *DIRECTIONS["b"][b]}
        return {
            (next_a, next_b)
            for next_a in a_options
            for next_b in b_options
            if next_a != next_b
            and not (next_a != a and next_b != b and _section(a, next_a) == _section(b, next_b))
        }

    @classmethod
    def _has_safe_completion(cls, start: tuple[str, str]) -> bool:
        goal = ("B", "A")
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                return True
            for following in cls._successors(current):
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

    @classmethod
    def _shortest_schedule(cls) -> tuple[int, int]:
        start = ("A", "B")
        goal = ("B", "A")
        distances = {start: 0}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for following in cls._successors(current):
                if following not in distances:
                    distances[following] = distances[current] + 1
                    queue.append(following)
        return distances.get(goal, -1), len(distances)
