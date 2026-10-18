"""MAP-07 V10 基线：真值 Oracle、公开方向探测启发式与四类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map07 import oracle_actions

Action = dict[str, Any]
ORDER = ("clockwise", "counter")


class Map07Probe:
    """公开启发式：读面板 → 试一个方向，没开就换另一个 → 等到达标。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.tried: list[str] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        if not observation["panel_read"]:
            return {"tool": "inspect", "target_id": "control_panel"}
        if not observation["valve_state"] == "open":
            for direction in ORDER:
                if direction not in self.tried:
                    self.tried.append(direction)
                    return {"tool": "turn_valve", "choice": direction}
        return {"tool": "wait", "ticks": 1}


class Map07FixedClockwise(Map07Probe):
    """固定脚本：永远转顺时针。"""

    name = "fixed_clockwise"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not observation["panel_read"]:
            return {"tool": "inspect", "target_id": "control_panel"}
        if observation["valve_state"] != "open":
            return {"tool": "turn_valve", "choice": "clockwise"}
        return {"tool": "wait", "ticks": 1}


class Map07NeverOpen(Map07Probe):
    """只读水位，从不开阀。"""

    name = "never_open"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        return {"tool": "read_gauge"}


class Map07LateOpen(Map07Probe):
    """先空转 6 tick 才开阀。"""

    name = "late_open"

    def reset(self) -> None:
        super().reset()
        self.idle = 6

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.idle > 0:
            self.idle -= 1
            return {"tool": "wait", "ticks": 1}
        return super().act(observation, history)


class Map07TurnBoth(Map07Probe):
    """两个方向都转一遍（合法但多一次拧紧）。"""

    name = "turn_both"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not observation["panel_read"]:
            return {"tool": "inspect", "target_id": "control_panel"}
        if observation["valve_state"] != "open":
            return {"tool": "turn_valve", "choice": ORDER[len(self.tried) % 2]}
        if len(self.tried) < 2:
            direction = ORDER[len(self.tried)]
            self.tried.append(direction)
            return {"tool": "turn_valve", "choice": direction}
        return {"tool": "wait", "ticks": 1}


HEURISTIC = Map07Probe
ABLATIONS: dict[str, type[Any]] = {
    "fixed_clockwise": Map07FixedClockwise,
    "never_open": Map07NeverOpen,
    "late_open": Map07LateOpen,
    "turn_both": Map07TurnBoth,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map07FixedClockwise",
    "Map07LateOpen",
    "Map07NeverOpen",
    "Map07Probe",
    "Map07TurnBoth",
    "oracle_actions",
]
