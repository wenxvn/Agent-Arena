"""MAP-19 V10 基线：真值 Oracle、公开预测启发式与四类消融。

公开启发式只读 `current_temperatures`、`active_cooling`、`pending_cooling_commands`、
`current_load_levels`、`cooling_budget`、`forecast_tolerance` 与公开规则：每个 tick 依次
下发“负荷 → 冷却（排到 tick+2）→ 申报下一 tick 温度 → 等待”。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map19 import (
    SAFE_TEMPERATURE,
    ZONES,
    oracle_actions,
)

Action = dict[str, Any]


def _cooling_budget(observation: dict[str, Any]) -> int:
    return int(observation.get("cooling_budget", 4))


def _active_for_settlement(observation: dict[str, Any]) -> dict[str, int]:
    """结算时会生效的冷却：`effective_tick <= 当前 tick` 的最后一条队列向量。"""

    active = dict(observation["active_cooling"])
    for command in observation["pending_cooling_commands"]:
        if command["effective_tick"] <= observation["tick"]:
            active = dict(command["vector"])
    return active


def _safe_loads(observation: dict[str, Any]) -> dict[str, int]:
    active = _active_for_settlement(observation)
    temperatures = observation["current_temperatures"]
    return {
        zone: max(0, min(2, SAFE_TEMPERATURE - temperatures[zone] + active[zone]))
        for zone in ZONES
    }


def _cooling_vector(observation: dict[str, Any], loads: dict[str, int], budget: int) -> list[int]:
    temperatures = observation["current_temperatures"]
    ordered = sorted(ZONES, key=lambda zone: -(temperatures[zone] + loads[zone]))
    vector = [0, 0, 0]
    remaining = budget
    for zone in ordered:
        want = min(2, remaining, max(0, temperatures[zone] + loads[zone] - 4))
        vector[ZONES.index(zone)] = want
        remaining -= want
    for index in range(3):
        if remaining <= 0:
            break
        add = min(2 - vector[index], remaining)
        vector[index] += add
        remaining -= add
    return vector


def _tick_plan(
    observation: dict[str, Any], *, forecast: str, ignore_pending: bool = False
) -> list[Action]:
    loads = _safe_loads(observation)
    current = observation["current_load_levels"]
    plan: list[Action] = []
    if any(loads[zone] != current[zone] for zone in ZONES):
        plan.append({"tool": "adjust_loads", "adjust_loads": [loads[zone] for zone in ZONES]})
    plan.append(
        {
            "tool": "set_cooling",
            "set_cooling": _cooling_vector(
                observation, loads, _cooling_budget(observation)
            ),
        }
    )
    if forecast == "exact":
        active = (
            dict(observation["active_cooling"])
            if ignore_pending
            else _active_for_settlement(observation)
        )
        prediction = [
            max(0, observation["current_temperatures"][zone] + loads[zone] - active[zone])
            for zone in ZONES
        ]
        plan.append({"tool": "forecast_next", "forecast_next": prediction})
    plan.append({"tool": "wait"})
    return plan


class _Ticker:
    name = "policy"
    forecast = "exact"
    ignore_pending = False

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.queue:
            self.queue = _tick_plan(
                observation, forecast=self.forecast, ignore_pending=self.ignore_pending
            )
        return self.queue.pop(0)


class Map19Predictive(_Ticker):
    """公开启发式：精确预测 + 延迟感知的冷却排程。"""

    name = "public_heuristic"


class Map19NoForecast(_Ticker):
    """从不申报预测（产能全部作废）。"""

    name = "no_forecast"
    forecast = "never"


class Map19NaiveForecast(_Ticker):
    """忽略尚未生效的冷却队列（时滞无感）。"""

    name = "naive_forecast"
    ignore_pending = True


class Map19FixedVector(_Ticker):
    """V9 的旁路：固定 [2,1,1] 冷却 + [2,2,2] 负荷，不做延迟感知。"""

    name = "fixed_vector_no_lag"

    def reset(self) -> None:
        self.queue = []
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        if not self.done:
            self.done = True
            self.queue = [
                {"tool": "set_cooling", "set_cooling": [2, 1, 1]},
                {"tool": "adjust_loads", "adjust_loads": [2, 2, 2]},
            ]
            return self.queue.pop(0)
        active = dict(observation["active_cooling"])
        loads = dict(observation["current_load_levels"])
        prediction = [
            max(0, observation["current_temperatures"][zone] + loads[zone] - active[zone])
            for zone in ZONES
        ]
        self.queue = [{"tool": "wait"}]
        return {"tool": "forecast_next", "forecast_next": prediction}


class Map19MaxLoads(_Ticker):
    """不做热控，永远满载且不冷却。"""

    name = "max_loads_no_cooling"

    def reset(self) -> None:
        self.queue = []
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        if not self.done:
            self.done = True
            self.queue = [{"tool": "adjust_loads", "adjust_loads": [2, 2, 2]}]
            return self.queue.pop(0)
        active = dict(observation["active_cooling"])
        loads = dict(observation["current_load_levels"])
        prediction = [
            max(0, observation["current_temperatures"][zone] + loads[zone] - active[zone])
            for zone in ZONES
        ]
        self.queue = [{"tool": "wait"}]
        return {"tool": "forecast_next", "forecast_next": prediction}


HEURISTIC = Map19Predictive
ABLATIONS: dict[str, type[Any]] = {
    "no_forecast": Map19NoForecast,
    "naive_forecast": Map19NaiveForecast,
    "fixed_vector_no_lag": Map19FixedVector,
    "max_loads_no_cooling": Map19MaxLoads,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map19FixedVector",
    "Map19MaxLoads",
    "Map19NaiveForecast",
    "Map19NoForecast",
    "Map19Predictive",
    "oracle_actions",
]
