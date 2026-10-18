"""MAP-12 V10 基线：真值 Oracle、公开缺口优先排班与四类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map12 import oracle_actions

Action = dict[str, Any]


class Map12Planner:
    """公开启发式：先补即将见底的食物/站体，其余槽位做研究。"""

    name = "public_heuristic"

    def reset(self) -> None:
        return None

    def _plan(self, observation: dict[str, Any]) -> list[str]:
        slots = int(observation["slots_per_day"])
        food = int(observation["food"])
        integrity = int(observation["integrity"])
        consumption = int(observation["daily_consumption"])
        decay = int(observation["daily_decay"])
        plan: list[str] = []
        while slots > 0 and food - consumption + 2 * plan.count("forage") <= 2:
            plan.append("forage")
            slots -= 1
        while slots > 0 and integrity - decay + 2 * plan.count("repair") <= 2:
            plan.append("repair")
            slots -= 1
        plan.extend(["research"] * slots)
        return plan

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        return {"tool": "assign", "plan": self._plan(observation)}


class Map12AllResearch(Map12Planner):
    """全部槽位做研究。"""

    name = "all_research"

    def _plan(self, observation: dict[str, Any]) -> list[str]:
        return ["research"] * int(observation["slots_per_day"])


class Map12AllForage(Map12Planner):
    """全部槽位采集。"""

    name = "all_forage"

    def _plan(self, observation: dict[str, Any]) -> list[str]:
        return ["forage"] * int(observation["slots_per_day"])


class Map12NoResearch(Map12Planner):
    """只维持生存，不做研究。"""

    name = "no_research"

    def _plan(self, observation: dict[str, Any]) -> list[str]:
        slots = int(observation["slots_per_day"])
        plan: list[str] = []
        while slots > 0 and (
            int(observation["food"]) - int(observation["daily_consumption"])
            + 2 * plan.count("forage")
            <= 2
        ):
            plan.append("forage")
            slots -= 1
        while slots > 0 and (
            int(observation["integrity"]) - int(observation["daily_decay"])
            + 2 * plan.count("repair")
            <= 2
        ):
            plan.append("repair")
            slots -= 1
        return plan


class Map12WasteSlots(Map12Planner):
    """每天只用 1 个槽位。"""

    name = "waste_slots"

    def _plan(self, observation: dict[str, Any]) -> list[str]:
        plan = super()._plan(observation)
        return plan[:1]


HEURISTIC = Map12Planner
ABLATIONS: dict[str, type[Any]] = {
    "all_research": Map12AllResearch,
    "all_forage": Map12AllForage,
    "no_research": Map12NoResearch,
    "waste_slots": Map12WasteSlots,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map12AllForage",
    "Map12AllResearch",
    "Map12NoResearch",
    "Map12Planner",
    "Map12WasteSlots",
    "oracle_actions",
]
