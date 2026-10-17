"""MAP-06｜暴风眼：80% 条件预报、风险预算与加固决策。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map06Environment(MapEnvironment):
    map_id = "MAP-06"
    title = "暴风眼"
    world = "lighthouse"
    level = "困难"
    EDGES = {
        "M_Q": ("M", "Q"),
        "Q_P": ("Q", "P"),
        "M_G": ("M", "G"),
        "G_P": ("G", "P"),
    }
    EDGE_COST = {"M_Q": 1, "Q_P": 1, "M_G": 2, "G_P": 2}
    EXPOSED_EDGES = frozenset({"Q_P", "G_P"})
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target_id"})},
        "interact": {frozenset({"tool", "target_id", "operation"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "risk",
            "risk_budget",
            "weather_observable",
            "forecast_reading",
            "forecast_queries",
            "forecast_accuracy",
            "prior_short",
            "prior_long",
            "storm_shield",
            "lamp_restored",
            "deadline_tick",
            "goal",
        }
    )
    #: Ten registered seeds with the documented 80% conditional accuracy.
    WEATHER = {
        0: "short",
        1: "short",
        2: "short",
        3: "short",
        4: "short",
        5: "long",
        6: "long",
        7: "long",
        8: "long",
        9: "long",
    }
    FORECAST = {
        0: "short",
        1: "short",
        2: "short",
        3: "short",
        4: "long",
        5: "long",
        6: "long",
        7: "long",
        8: "long",
        9: "short",
    }

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        self.node = "Q"
        self.items = []
        self.seed_id = seed % 10
        self.weather = self.WEATHER[self.seed_id]
        self.forecast_reading: str | None = None
        self.forecast_queries = 0
        self.risk = 0
        self.risk_budget = 4
        self.storm_shield = False
        self.lamp_restored = False
        self.deadline_tick = 14
        self.high_risk_ticks = 0
        self._last_cost = 1
        self._exposure_ticks = 0
        self._repair_ticks = 0
        self._repairing = False

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "risk": self.risk,
            "risk_budget": self.risk_budget,
            "weather_observable": False,
            "forecast_reading": self.forecast_reading,
            "forecast_queries": self.forecast_queries,
            "forecast_accuracy": 0.8,
            "prior_short": 0.5,
            "prior_long": 0.5,
            "storm_shield": self.storm_shield,
            "lamp_restored": self.lamp_restored,
            "deadline_tick": self.deadline_tick,
            "goal": "在 tick 14 前修好灯塔设备，累计风险不得超过 4。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._exposure_ticks = 0
        self._repair_ticks = 0
        self._repairing = False
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            cost = self.EDGE_COST.get(action.edge_id, 1)
            destination, result = self.move_edge(action.edge_id)
            if destination is None:
                return "EDGE_NOT_ADJACENT"
            if action.edge_id in self.EXPOSED_EDGES:
                self._exposure_ticks = cost
            return result
        if tool == "inspect":
            if action.target_id == "forecast" and self.node == "Q":
                self.forecast_queries += 1
                self.forecast_reading = self.FORECAST[self.seed_id]
                return f"FORECAST:{self.forecast_reading}"
            return "TARGET_NOT_VISIBLE"
        if tool == "wait":
            return "WAITED"
        if tool == "interact":
            if action.target_id == "P" and action.operation == "repair_lighthouse":
                if self.node != "P":
                    return "TARGET_NOT_VISIBLE"
                if self.lamp_restored:
                    return "LAMP_ALREADY_RESTORED"
                self._repair_ticks = 2
                self._repairing = True
                return "REPAIR_STARTED"
            if action.target_id == "G" and action.operation == "harden":
                if self.node != "G":
                    return "TARGET_NOT_VISIBLE"
                self.storm_shield = True
                return "STORM_SHIELD_READY"
            return "ACTION_NOT_ALLOWED"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        if action.tool == "move" and action.edge_id in self.EDGE_COST:
            cost = self.EDGE_COST[action.edge_id]
        elif action.tool == "inspect":
            cost = 2
        elif action.tool == "interact" and action.operation == "harden":
            cost = 3
        elif action.tool == "interact" and action.operation == "repair_lighthouse":
            cost = 2
        else:
            cost = action.ticks or 1
        self._last_cost = cost
        return cost

    def _after_tick(self) -> None:
        for _ in range(self._last_cost):
            if self.weather == "long":
                if self._exposure_ticks > 0:
                    self._exposure_ticks -= 1
                    self.risk += 1
                    self.high_risk_ticks += 1
                elif self._repair_ticks > 0:
                    self._repair_ticks -= 1
                    if not self.storm_shield:
                        self.risk += 3
                        self.high_risk_ticks += 1
            elif self._repair_ticks > 0:
                self._repair_ticks -= 1
            elif self._exposure_ticks > 0:
                self._exposure_ticks -= 1
            if self.risk > self.risk_budget:
                self._fail("RESOURCE_EXHAUSTED")
                return
        if self._repairing and self._repair_ticks == 0:
            self.lamp_restored = True
            self.storm_shield = False
            self._succeed("LAMP_RESTORED")
            return
        if self.tick_count >= self.deadline_tick and not self.lamp_restored:
            self._fail("REPAIR_DEADLINE_MISSED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "weather": self.weather,
            "forecast_reading": self.forecast_reading,
            "forecast_queries": self.forecast_queries,
            "risk": self.risk,
            "storm_shield": self.storm_shield,
            "lamp_restored": self.lamp_restored,
            "high_risk_ticks": self.high_risk_ticks,
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "map06.task_success_rate": {
                "numerator": 1 if self.lamp_restored else 0,
                "denominator": 1,
            },
            "map06.high_risk_exposure_ticks": self.high_risk_ticks,
            "map06.observation_cost": self.forecast_queries * 2,
            "map06.resource_exhausted": int(self.terminal_reason == "RESOURCE_EXHAUSTED"),
            "map06.value_of_information": None,
        }


FIXTURES = (
    {
        "name": "short_storm_direct_repair",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "Q_P"},
            {"tool": "interact", "target_id": "P", "operation": "repair_lighthouse"},
        ],
        "expect": {"map06.high_risk_exposure_ticks": 0, "map06.task_success_rate": 1.0},
    },
    {
        "name": "long_storm_repair_without_shield",
        "seed": 5,
        "actions": [
            {"tool": "move", "edge_id": "Q_P"},
            {"tool": "interact", "target_id": "P", "operation": "repair_lighthouse"},
        ],
        "expect": {"map06.high_risk_exposure_ticks": 3, "map06.resource_exhausted": 1},
    },
)


__all__ = ["FIXTURES", "Map06Environment"]
