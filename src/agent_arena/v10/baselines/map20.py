"""MAP-20 V10 基线：真值 Oracle、公开热量表启发式与四类消融。

公开启发式只读 `heat_schedule` / `production_base` / `flow_rules` / `current_temperatures_tenths`
与公开规则：热点区拉满直供，再按 4/5 交付率从相邻的供体区经旁路补差。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map20 import (
    BYPASS_QUANTUM,
    DIRECT_MAX,
    HORIZON,
    ZONES,
    oracle_actions,
)

Action = dict[str, Any]


def _hot_zone(observation: dict[str, Any]) -> str:
    tick = int(observation["tick"])
    schedule = observation["heat_schedule"]
    return max(ZONES, key=lambda zone: schedule[zone][min(tick, HORIZON - 1)])


def _import_units(heats: dict[str, int], hot: str) -> int:
    units = 0
    while units * 4 // 5 < heats[hot] - DIRECT_MAX:
        units += BYPASS_QUANTUM
    return units


class Map20PublicPlan:
    """公开热量表下的确定性分配：热点拉满 + 旁路补差。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        tick = int(observation["tick"])
        schedule = observation["heat_schedule"]
        heats = {zone: schedule[zone][min(tick, HORIZON - 1)] for zone in ZONES}
        hot = _hot_zone(observation)
        donor = "B" if hot in ("A", "C") else "A"
        units = _import_units(heats, hot)
        direct = {zone: heats[zone] for zone in ZONES}
        direct[hot] = DIRECT_MAX
        direct[donor] = min(DIRECT_MAX, heats[donor] + units)
        bypass: dict[str, dict[str, Any]] = {}
        if units:
            link = "AB" if {hot, donor} == {"A", "B"} else "BC"
            bypass[link] = {"from": donor, "to": hot, "input_tenths": units}
        self.queue = [{"tool": "open_bypass", "open_bypasses": bypass}, {"tool": "wait"}]
        return {"tool": "set_flow", "set_flow_tenths": [direct[zone] for zone in ZONES]}


class Map20StaticAllocation:
    """固定 [20,20,20] 直供、不开旁路（V9 的静态旁路）。"""

    name = "static_allocation"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        if not self.done:
            self.done = True
            self.queue = [{"tool": "wait"}]
            return {"tool": "set_flow", "set_flow_tenths": [20, 20, 20]}
        return {"tool": "wait"}


class Map20NoBypass:
    """每 tick 按热量给直供，但从不使用旁路。"""

    name = "no_bypass"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        tick = int(observation["tick"])
        schedule = observation["heat_schedule"]
        heats = {zone: schedule[zone][min(tick, HORIZON - 1)] for zone in ZONES}
        direct = {zone: min(DIRECT_MAX, heats[zone]) for zone in ZONES}
        self.queue = [{"tool": "open_bypass", "open_bypasses": {}}, {"tool": "wait"}]
        return {"tool": "set_flow", "set_flow_tenths": [direct[zone] for zone in ZONES]}


class Map20BypassOveruse:
    """每 tick 都从供体区搬满 20 单位（赔本搬水）。"""

    name = "bypass_overuse"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        tick = int(observation["tick"])
        schedule = observation["heat_schedule"]
        heats = {zone: schedule[zone][min(tick, HORIZON - 1)] for zone in ZONES}
        hot = _hot_zone(observation)
        donor = "B" if hot in ("A", "C") else "A"
        direct = {zone: heats[zone] for zone in ZONES}
        direct[hot] = DIRECT_MAX
        direct[donor] = DIRECT_MAX
        link = "AB" if {hot, donor} == {"A", "B"} else "BC"
        self.queue = [{"tool": "wait"}]
        return {
            "tool": "open_bypass",
            "open_bypasses": {link: {"from": donor, "to": hot, "input_tenths": 20}},
        }


class Map20ZeroFlow:
    """完全不管冷却，只等 tick 推进。"""

    name = "zero_flow"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        if not self.done:
            self.done = True
            self.queue = [{"tool": "wait"}]
            return {"tool": "set_flow", "set_flow_tenths": [0, 0, 0]}
        return {"tool": "wait"}


HEURISTIC = Map20PublicPlan
ABLATIONS: dict[str, type[Any]] = {
    "static_allocation": Map20StaticAllocation,
    "no_bypass": Map20NoBypass,
    "bypass_overuse": Map20BypassOveruse,
    "zero_flow": Map20ZeroFlow,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map20BypassOveruse",
    "Map20NoBypass",
    "Map20PublicPlan",
    "Map20StaticAllocation",
    "Map20ZeroFlow",
    "oracle_actions",
]
