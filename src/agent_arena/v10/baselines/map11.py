"""MAP-11 V10 基线：真值 Oracle、公开风暴感知搜索启发式与四类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map11 import ZONES, oracle_actions

Action = dict[str, Any]


class Map11StormAware:
    """公开启发式：风暴里不搜（等 1 tick），按顺序搜到信号就救。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        for item in observation["signals"]:
            if item["signal"]:
                return {"tool": "rescue", "area": item["area"]}
        if observation["in_storm"]:
            return {"tool": "wait", "ticks": 1}
        attempts = observation["search_attempts"]
        target = min(ZONES, key=lambda zone: (attempts.get(zone, 0), ZONES.index(zone)))
        return {"tool": "search", "area": target}


class Map11BlindRescue:
    """不搜索，逐个区域硬救（没有信号会被拒绝）。"""

    name = "blind_rescue"

    def reset(self) -> None:
        self.index = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.index >= len(ZONES):
            return {"tool": "wait", "ticks": 1}
        self.index += 1
        return {"tool": "rescue", "area": ZONES[self.index - 1]}


class Map11StormSearch:
    """无视风暴，一直在搜（漏检率高）。"""

    name = "storm_search"

    def reset(self) -> None:
        self.index = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        for item in observation["signals"]:
            if item["signal"]:
                return {"tool": "rescue", "area": item["area"]}
        target = ZONES[self.index % len(ZONES)]
        self.index += 1
        return {"tool": "search", "area": target}


class Map11SingleSearch:
    """只搜一次，没信号就放弃。"""

    name = "single_search_giveup"

    def reset(self) -> None:
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        for item in observation["signals"]:
            if item["signal"]:
                return {"tool": "rescue", "area": item["area"]}
        if self.done:
            return {"tool": "wait", "ticks": 1}
        if observation["in_storm"]:
            return {"tool": "wait", "ticks": 1}
        self.done = True
        return {"tool": "search", "area": ZONES[0]}


class Map11WasteWindow:
    """开局空转 6 tick 再搜（生命窗被浪费）。"""

    name = "waste_window"

    def reset(self) -> None:
        self.idle = 6
        self.inner = Map11StormAware()
        self.inner.reset()

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.idle > 0:
            self.idle -= 1
            return {"tool": "wait", "ticks": 1}
        return self.inner.act(observation, history)


HEURISTIC = Map11StormAware
ABLATIONS: dict[str, type[Any]] = {
    "blind_rescue": Map11BlindRescue,
    "storm_search": Map11StormSearch,
    "single_search_giveup": Map11SingleSearch,
    "waste_window": Map11WasteWindow,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map11BlindRescue",
    "Map11SingleSearch",
    "Map11StormAware",
    "Map11StormSearch",
    "Map11WasteWindow",
    "oracle_actions",
]
