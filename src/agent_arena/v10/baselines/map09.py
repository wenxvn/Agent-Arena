"""MAP-09 V10 基线：真值 Oracle、公开三链启发式与四类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map09 import oracle_actions

Action = dict[str, Any]


class Map09TripleChain:
    """公开启发式：先补齐氧，再把水位压到门槛下，最后修复。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        water = int(observation["water"])
        oxygen = int(observation["oxygen"])
        limit = int(observation["repair_water_limit"])
        ox_min = int(observation["repair_oxygen_min"])
        if water <= limit and oxygen >= ox_min:
            return {"tool": "repair"}
        if oxygen < ox_min:
            return {"tool": "vent"}
        if water > limit:
            return {"tool": "pump"}
        if oxygen < ox_min + 2:
            return {"tool": "vent"}
        return {"tool": "wait"}


class Map09SkipPump(Map09TripleChain):
    """只通风、不开泵。"""

    name = "skip_pump"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        water = int(observation["water"])
        oxygen = int(observation["oxygen"])
        limit = int(observation["repair_water_limit"])
        ox_min = int(observation["repair_oxygen_min"])
        if water <= limit and oxygen >= ox_min:
            return {"tool": "repair"}
        return {"tool": "vent"}


class Map09SkipVent(Map09TripleChain):
    """只开泵、不通风。"""

    name = "skip_vent"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        water = int(observation["water"])
        oxygen = int(observation["oxygen"])
        limit = int(observation["repair_water_limit"])
        ox_min = int(observation["repair_oxygen_min"])
        if water <= limit and oxygen >= ox_min:
            return {"tool": "repair"}
        return {"tool": "pump"}


class Map09SealOnly(Map09TripleChain):
    """只封舱（停漏但耗氧），从不开泵。"""

    name = "seal_only"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        water = int(observation["water"])
        oxygen = int(observation["oxygen"])
        limit = int(observation["repair_water_limit"])
        ox_min = int(observation["repair_oxygen_min"])
        if water <= limit and oxygen >= ox_min:
            return {"tool": "repair"}
        return {"tool": "seal"}


HEURISTIC = Map09TripleChain
ABLATIONS: dict[str, type[Any]] = {
    "skip_pump": Map09SkipPump,
    "skip_vent": Map09SkipVent,
    "seal_only": Map09SealOnly,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map09SealOnly",
    "Map09SkipPump",
    "Map09SkipVent",
    "Map09TripleChain",
    "oracle_actions",
]
