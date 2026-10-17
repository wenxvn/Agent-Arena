"""MAP-05｜三束信号：单路共享供电下的跨塔校准与窗口排程。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map05Environment(MapEnvironment):
    map_id = "MAP-05"
    title = "三束信号"
    world = "lighthouse"
    level = "中等"
    EDGES = {"C_R": ("C", "R"), "C_B": ("C", "B"), "C_W": ("C", "W")}
    EDGE_COST = {"C_R": 1, "C_B": 2, "C_W": 3}
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target_id"})},
        "switch_power": {frozenset({"tool", "station"})},
        "interact": {frozenset({"tool", "target_id", "operation"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "power_target",
            "calibration",
            "transmitted",
            "windows",
            "schedule_chart_inspected",
            "goal",
        }
    )
    WINDOWS = {"R": (15, 18), "B": (22, 25), "W": (29, 35)}
    #: DCR-V8-002: the paper schedule is feasible; this is the checked earliest
    #: completion of the near-first plan (see docs/v8/dcr-resolution.md).
    FEASIBLE_TASK_COUNT = 3

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "C"
        self.items = []
        self.power_target: str | None = None
        self.calibration = {"R": 0, "B": 0, "W": 0}
        self.transmitted = {"R": False, "B": False, "W": False}
        self.chart_inspected = False
        self.idle_ticks = 0
        self.missed_windows = 0
        self._last_cost = 1
        self._pending_signal: str | None = None

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "power_target": self.power_target,
            "calibration": dict(self.calibration),
            "transmitted": dict(self.transmitted),
            "windows": {name: list(window) for name, window in self.WINDOWS.items()},
            "schedule_chart_inspected": self.chart_inspected,
            "goal": "在 R[15,18]、B[22,25]、W[29,35] 三个窗口内各发出一束信号。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_signal = None
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            destination, result = self.move_edge(action.edge_id)
            return result if destination is not None else "EDGE_NOT_ADJACENT"
        if tool == "inspect":
            if action.target_id == "schedule_chart" and self.node == "C":
                self.chart_inspected = True
                return "SCHEDULE:INSPECTED"
            return "TARGET_NOT_VISIBLE"
        if tool == "switch_power":
            if self.node != "C":
                return "TARGET_NOT_VISIBLE"
            if action.station not in self.WINDOWS:
                return "UNKNOWN_STATION"
            self.power_target = action.station
            return f"POWER:{action.station}"
        if tool == "wait":
            if action.ticks is None:
                return "INVALID_ACTION_SCHEMA"
            if self.power_target is not None and self.calibration[self.power_target] == 2:
                self.idle_ticks += action.ticks
            return "WAITED"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        station = action.target_id
        operation = action.operation
        if station not in self.WINDOWS or self.node != station:
            return "TARGET_NOT_VISIBLE"
        if self.power_target != station:
            return "STATION_UNPOWERED"
        if operation == "calibrate_align":
            if self.calibration[station] >= 1:
                return "ALIGN_ALREADY_DONE"
            self.calibration[station] = 1
            return f"ALIGNED:{station}"
        if operation == "calibrate_phase_lock":
            if self.calibration[station] == 0:
                return "ALIGN_REQUIRED"
            if self.calibration[station] >= 2:
                return "CALIBRATION_ALREADY_COMPLETE"
            self.calibration[station] = 2
            return f"CALIBRATED:{station}"
        if operation == "send_signal":
            if self.calibration[station] < 2:
                return "CALIBRATION_REQUIRED"
            if self.transmitted[station]:
                return "SIGNAL_ALREADY_SENT"
            self._pending_signal = station
            return "SIGNAL_SENT"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        if action.tool == "move" and action.edge_id in self.EDGE_COST:
            self._last_cost = self.EDGE_COST[action.edge_id]
        elif action.tool == "wait":
            self._last_cost = action.ticks or 1
        else:
            self._last_cost = 1
        return self._last_cost

    def _after_tick(self) -> None:
        if self._pending_signal is not None:
            station = self._pending_signal
            start, end = self.WINDOWS[station]
            if start <= self.tick_count <= end:
                self.transmitted[station] = True
                self._pending_signal = None
            else:
                self._pending_signal = None
        for station, (_start, end) in self.WINDOWS.items():
            if not self.transmitted[station] and self.tick_count > end:
                self.missed_windows += 1
                self._fail("SIGNAL_WINDOW_MISSED")
                return
        if all(self.transmitted.values()):
            self._succeed("THREE_SIGNALS_SENT")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "power_target": self.power_target,
            "calibration": dict(self.calibration),
            "transmitted": dict(self.transmitted),
            "idle_ticks": self.idle_ticks,
            "missed_windows": self.missed_windows,
        }

    def metrics(self) -> dict[str, Any]:
        sent = sum(1 for value in self.transmitted.values() if value)
        return {
            "map05.effective_signals": {"numerator": sent, "denominator": 3},
            "map05.window_utilization": {
                "numerator": sent,
                "denominator": self.FEASIBLE_TASK_COUNT,
            },
            "map05.idle_ticks": self.idle_ticks,
            "map05.missed_windows": self.missed_windows,
            "map05.power_overcommit": 0,
        }


FIXTURES = (
    {
        "name": "travel_cost_and_switch",
        "actions": [
            {"tool": "switch_power", "station": "B"},
            {"tool": "move", "edge_id": "C_B"},
        ],
        "expect": {"map05.idle_ticks": 0},
    },
    {
        "name": "unpowered_calibration_is_refused",
        "actions": [
            {"tool": "move", "edge_id": "C_R"},
            {"tool": "interact", "target_id": "R", "operation": "calibrate_align"},
        ],
        "expect": {"map05.effective_signals": 0},
    },
)


__all__ = ["FIXTURES", "Map05Environment"]
