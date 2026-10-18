"""MAP-10 V10 基线：真值 Oracle、公开算账启发式与三类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map10 import DEPOT, oracle_actions

Action = dict[str, Any]


def _burn(burn_base: int, cargo: int) -> int:
    return burn_base + (cargo + 1) // 2


class Map10Planner:
    """公开启发式：算出能到站且够用的最小装载量。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.loaded = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.loaded:
            self.loaded = True
            required = int(observation["required_delivery"])
            upper = min(int(observation["capacity"]), int(observation["station_stock"]))
            fuel = int(observation["fuel"])
            burn_base = int(observation["burn_base"])
            cargo = next(
                (value for value in range(required, upper + 1) if _burn(burn_base, value) <= fuel),
                required,
            )
            return {"tool": "load", "quantity": cargo}
        return {"tool": "move", "to": DEPOT}


class Map10MaxLoad(Map10Planner):
    """装到容量上限（最省趟数，但可能烧光油）。"""

    name = "max_load"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.loaded:
            self.loaded = True
            quantity = min(int(observation["capacity"]), int(observation["station_stock"]))
            return {"tool": "load", "quantity": quantity}
        return {"tool": "move", "to": DEPOT}


class Map10Underload(Map10Planner):
    """少装一档（省油但不够用）。"""

    name = "underload"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.loaded:
            self.loaded = True
            required = int(observation["required_delivery"])
            return {"tool": "load", "quantity": max(1, required - 1)}
        return {"tool": "move", "to": DEPOT}


class Map10NoMove(Map10Planner):
    """装了货但从不出发。"""

    name = "no_move"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.loaded:
            self.loaded = True
            return {"tool": "load", "quantity": int(observation["required_delivery"])}
        return {"tool": "wait"}


HEURISTIC = Map10Planner
ABLATIONS: dict[str, type[Any]] = {
    "max_load": Map10MaxLoad,
    "underload": Map10Underload,
    "no_move": Map10NoMove,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map10MaxLoad",
    "Map10NoMove",
    "Map10Planner",
    "Map10Underload",
    "oracle_actions",
]
