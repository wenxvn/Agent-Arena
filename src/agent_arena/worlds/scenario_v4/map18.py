"""V4 MAP-18, simultaneous recovery dispatch with a paired warning."""

from __future__ import annotations

from collections import Counter
from typing import Any, TypedDict

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4Map18Observation,
    V4Status,
)

HORIZON = 12
FAULT_EDGE = frozenset(("R2", "R3"))
ADJACENCY = {
    "R1": ("R2",),
    "R2": ("R1", "R3", "B2"),
    "R3": ("R2",),
    "B1": ("B2",),
    "B2": ("B1", "B3", "R2"),
    "B3": ("B2", "G2"),
    "G1": ("G2",),
    "G2": ("G1", "G3", "B3"),
    "G3": ("G2",),
}
INITIAL_POSITIONS = {
    "T_R1": "R1",
    "T_R2": "R2",
    "T_R3": "R3",
    "T_B": "B1",
    "T_G": "G1",
    "T_X": "R2",
}
TRAIN_TASKS = {
    "T_R1": "TASK_R1_R2",
    "T_R2": "TASK_R2_R3",
    "T_R3": "TASK_R3_R2",
    "T_B": "TASK_B1_B3",
    "T_G": "TASK_G1_G3",
    "T_X": "TASK_R2_G2",
}


class TaskSpec(TypedDict):
    origin: str
    destination: str
    passengers: int
    planned_arrival_tick: int


TASKS: dict[str, TaskSpec] = {
    "TASK_R1_R2": {"origin": "R1", "destination": "R2", "passengers": 3, "planned_arrival_tick": 6},
    "TASK_R2_R3": {"origin": "R2", "destination": "R3", "passengers": 3, "planned_arrival_tick": 6},
    "TASK_R3_R2": {"origin": "R3", "destination": "R2", "passengers": 3, "planned_arrival_tick": 7},
    "TASK_B1_B3": {"origin": "B1", "destination": "B3", "passengers": 3, "planned_arrival_tick": 2},
    "TASK_G1_G3": {"origin": "G1", "destination": "G3", "passengers": 3, "planned_arrival_tick": 2},
    "TASK_R2_G2": {"origin": "R2", "destination": "G2", "passengers": 3, "planned_arrival_tick": 7},
}
DISPATCH_WINDOWS: dict[str, dict[str, int | tuple[int, ...]]] = {
    "TASK_R1_R2": {"release_tick": 5, "arrival_tick": 6},
    "TASK_R2_R3": {"release_tick": 5, "arrival_tick": 6},
    "TASK_R3_R2": {"release_tick": 6, "arrival_tick": 7},
    "TASK_B1_B3": {"release_ticks": (0, 1), "arrival_tick": 2},
    "TASK_G1_G3": {"release_ticks": (0, 1), "arrival_tick": 2},
    "TASK_R2_G2": {"detour_release_tick": 4, "arrival_tick": 7},
}
TOPOLOGY = {
    "red_nodes": ("R1", "R2", "R3"),
    "blue_nodes": ("B1", "B2", "B3"),
    "green_nodes": ("G1", "G2", "G3"),
    "interchange_segments": ("R2_B2", "B3_G2"),
    "segment_capacity_per_tick": 1,
    "station_train_berth_capacity": 2,
}


class Map18Environment(ScenarioV4Environment):
    map_id = "MAP-18"

    def __init__(
        self,
        *,
        alert_enabled: bool = True,
        step_limit: int = 100,
        fault_edge: frozenset[str] | None = None,
        fault_window: tuple[int, int] = (5, 10),
        fault_enabled: bool = True,
        alert_tick: int = 4,
        horizon: int = HORIZON,
        success_threshold: int = 13,
    ) -> None:
        # Optional parameters let the V6 fixture layer build independent fault
        # scenarios from the same dispatch engine. Defaults reproduce the reviewed
        # V4 MAP-18 scene exactly.
        self.alert_enabled = alert_enabled
        self.step_limit = min(step_limit, horizon)
        self.fault_edge = fault_edge if fault_edge is not None else FAULT_EDGE
        self.fault_window = fault_window
        self.fault_enabled = fault_enabled
        self.alert_tick = alert_tick
        self.horizon = horizon
        self.success_threshold = success_threshold
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
            raise ValueError("MAP-18 only accepts the three registered fixed-scene repeat labels.")
        self.positions = dict(INITIAL_POSITIONS)
        self.headings = {
            "T_R1": "R2",
            "T_R2": "R3",
            "T_R3": "R2",
            "T_B": "B2",
            "T_G": "G2",
            "T_X": "B2",
        }
        self.task_status = {task: "pending" for task in TASKS}
        self.current_train_locks: dict[str, dict[str, Any]] = {}
        self.current_tick = 0
        self.delivered = 0
        self.canceled = 0
        self.delay_person_ticks = 0
        self.last_delivery_tick = 0
        self.fault_resolution: dict[str, int] = {}
        self.failure_counts: dict[str, int] = {}
        self.last_result = "INITIAL"

    def _observation(self) -> V4Map18Observation:
        closed: tuple[str, ...] = ()
        if self.fault_enabled and self.fault_window[0] <= self.current_tick < self.fault_window[1]:
            closed = ("_".join(sorted(self.fault_edge)),)
        alert = None
        if self.current_tick == self.alert_tick and self.alert_enabled:
            alert = {
                "id": "NETWORK_DISRUPTION_WATCH",
                "message": (
                    "A mainline section may close next tick; "
                    "the segment and duration are unspecified."
                ),
            }
        states = self.task_status
        return V4Map18Observation(
            tick=self.current_tick,
            ticks_remaining=self.horizon - self.current_tick,
            topology=TOPOLOGY,
            train_positions=dict(self.positions),
            station_berths=dict(sorted(Counter(self.positions.values()).items())),
            task_passenger_counts={task: int(TASKS[task]["passengers"]) for task in sorted(TASKS)},
            delivered_tasks=tuple(
                sorted(task for task, state in states.items() if state == "delivered")
            ),
            canceled_tasks=tuple(
                sorted(task for task, state in states.items() if state == "canceled")
            ),
            delivered_passengers=self.delivered,
            canceled_passengers=self.canceled,
            closed_segments=closed,
            current_train_locks={
                train: int(lock["remaining"])
                for train, lock in sorted(self.current_train_locks.items())
            },
            published_dispatch_windows=DISPATCH_WINDOWS,
            alert_message_if_any=alert,
            recovery_status=(
                "not_started"
                if self.current_tick < self.fault_window[0]
                else "section_closed"
                if self.current_tick < self.fault_window[1]
                else "reopened"
            ),
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _apply(self, action: ScenarioV4Action) -> str:
        if action.tool != "set_timetable":
            self.last_result = "ACTION_NOT_AVAILABLE"
            return self.last_result
        if action.tick != self.current_tick:
            self.last_result = "TICK_MISMATCH"
            return self.last_result
        assert action.operations is not None
        operations = action.operations
        if any(train not in self.positions for train in operations):
            self.last_result = "UNKNOWN_TRAIN"
            return self.last_result
        if any(train in self.current_train_locks for train in operations):
            self.last_result = "TRAIN_LOCKED"
            return self.last_result

        accepted_moves: dict[str, tuple[str, str]] = {}
        closed_results: dict[str, str] = {}
        cancel_now: list[str] = []
        start_turnbacks: dict[str, str] = {}
        for train, op_data in operations.items():
            task_id = TRAIN_TASKS[train]
            task_state = self.task_status[task_id]
            current = self.positions[train]
            op = op_data.op
            if op in {"release", "detour"}:
                destination = op_data.to
                if destination not in ADJACENCY[current]:
                    return self._record_failure("INVALID_LINK")
                if task_state == "pending":
                    pass
                elif task_state == "canceled" and train == "T_R2":
                    if op != "release" or destination != self.headings[train]:
                        return self._record_failure("CANCELED_TRAIN_ROUTE_INVALID")
                else:
                    return self._record_failure("COMPLETED_TRAIN_MOVED")
                if (
                    self.fault_enabled
                    and frozenset((current, destination)) == self.fault_edge
                    and self.fault_window[0] <= self.current_tick < self.fault_window[1]
                ):
                    closed_results[train] = "TRACK_CLOSED"
                    continue
                accepted_moves[train] = (current, destination)
            elif op == "cancel_service":
                cancel_id = op_data.task_id
                if (
                    cancel_id != task_id
                    or task_state != "pending"
                    or current != TASKS[task_id]["origin"]
                ):
                    return self._record_failure("INVALID_CANCELLATION")
                cancel_now.append(task_id)
            elif op == "turnback":
                if task_state != "canceled" or train != "T_R2" or op_data.duration_ticks != 2:
                    return self._record_failure("INVALID_TURNBACK")
                reverse = op_data.reverse_toward
                if reverse not in ADJACENCY[current] or self.headings[train] == reverse:
                    return self._record_failure("INVALID_TURNBACK")
                start_turnbacks[train] = reverse
            elif op == "temporary_stop":
                continue

        edge_owners: dict[frozenset[str], str] = {}
        for train, (origin, destination) in accepted_moves.items():
            edge = frozenset((origin, destination))
            if edge in edge_owners:
                other = edge_owners[edge]
                reason = (
                    "HEAD_ON_COLLISION"
                    if self.positions[other] == destination
                    else "SEGMENT_CAPACITY"
                )
                return self._terminal_failure(reason)
            edge_owners[edge] = train
        next_positions = dict(self.positions)
        for train, (_, destination) in accepted_moves.items():
            next_positions[train] = destination
        if max(Counter(next_positions.values()).values(), default=0) > 2:
            return self._terminal_failure("STATION_CAPACITY_EXCEEDED")

        # Commit the whole timetable only after link and capacity checks pass.
        self.positions = next_positions
        for task_id in cancel_now:
            self.task_status[task_id] = "canceled"
            self.canceled += int(TASKS[task_id]["passengers"])
            if task_id in {"TASK_R2_R3", "TASK_R3_R2"}:
                self.fault_resolution[task_id] = self.current_tick
        for train, reverse in start_turnbacks.items():
            self.current_train_locks[train] = {"remaining": 2, "reverse_toward": reverse}
        for train in accepted_moves:
            task_id = TRAIN_TASKS[train]
            task = TASKS[task_id]
            if self.positions[train] == task["destination"]:
                self.task_status[task_id] = "delivered"
                passengers = int(task["passengers"])
                self.delivered += passengers
                arrival = self.current_tick + 1
                self.last_delivery_tick = max(self.last_delivery_tick, arrival)
                self.delay_person_ticks += passengers * max(
                    arrival - task["planned_arrival_tick"], 0
                )
                if task_id in {"TASK_R2_R3", "TASK_R3_R2"}:
                    self.fault_resolution[task_id] = arrival
        for train, lock in list(self.current_train_locks.items()):
            lock["remaining"] -= 1
            if lock["remaining"] == 0:
                self.headings[train] = str(lock["reverse_toward"])
                del self.current_train_locks[train]
        self.current_tick += 1
        if self.current_tick >= self.horizon:
            if self.delivered >= self.success_threshold:
                self.status = V4Status.SUCCESS
                self.terminal_reason = "SERVICE_COMPLETE"
            else:
                self.status = V4Status.FAILURE
                self.terminal_reason = "DEADLINE_SERVICE_BELOW_70"
        result = "TICK_COMMITTED"
        if closed_results:
            result = ";".join(f"{train}:{value}" for train, value in sorted(closed_results.items()))
        self.last_result = result
        return result

    def _record_failure(self, reason: str) -> str:
        self.failure_counts[reason] = self.failure_counts.get(reason, 0) + 1
        self.last_result = reason
        return reason

    def _invalid_action(self) -> str:
        return self._record_failure("INVALID_ACTION_SCHEMA")

    def _terminal_failure(self, reason: str) -> str:
        self.failure_counts[reason] = self.failure_counts.get(reason, 0) + 1
        self.status = V4Status.FAILURE
        self.terminal_reason = reason
        self.last_result = reason
        return reason

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "tick": self.current_tick,
            "positions": dict(sorted(self.positions.items())),
            "headings": dict(sorted(self.headings.items())),
            "task_status": dict(sorted(self.task_status.items())),
            "locks": self.current_train_locks,
            "delivered": self.delivered,
            "canceled": self.canceled,
            "delay_person_ticks": self.delay_person_ticks,
            "alert_enabled": self.alert_enabled,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
        }

    def metrics(self) -> dict[str, Any]:
        resolved = [
            tick
            for task, tick in self.fault_resolution.items()
            if task in {"TASK_R2_R3", "TASK_R3_R2"}
        ]
        recovery_duration = max(resolved) - self.fault_window[0] if resolved else None
        return {
            "success": self.is_success,
            "delivered_passengers": self.delivered,
            "total_demand": sum(int(task["passengers"]) for task in TASKS.values()),
            "service_rate": self.delivered / 18,
            "canceled_passengers": self.canceled,
            "total_delay_person_ticks": self.delay_person_ticks,
            "last_delivery_tick": self.last_delivery_tick,
            "recovery_duration_ticks": recovery_duration,
            "failure_counts": dict(self.failure_counts),
            "terminal_reason": self.terminal_reason,
        }
