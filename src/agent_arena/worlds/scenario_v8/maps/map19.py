"""MAP-19｜温度临界点：三片独立热区、两 tick 冷却延迟与前馈负荷控制。

本图与同世界另两图的机制差异：MAP-20 是带 20% 损耗的互联管网、控制无延迟；
MAP-21 是隐藏喷发时刻下的风险决策。本图没有移动、没有随机事件、也没有跨区
热传导，主机制是“今天下达的冷却阀向量到 tick+2 才有效”这一条固定时间因果，
玩家必须提前两 tick 预判三区温度并用负荷档位交换产能。

指标口径（与 V7 卡片一致）：
- ``temperature_exceedance_area``：Σ_zone Σ_tick ``max(0, T - 8)``，只累计已结算
  tick；熔断 tick 的温度也记录并累计，之后不再增加。
- ``oscillation_count``：三区各自相邻非零 ``dT`` 的符号变化次数之和。
- ``critical_overheat_ticks``：已记录状态中 ``T > 10`` 的区·tick 数。
- ``coolant_exhausted``：``terminal_reason == COOLANT_EXHAUSTED`` 的 0/1。当前
  运行时不设冷却剂池，该原因码不可达，因此合法结果为 0。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action

ZONES = ("A", "B", "C")
INITIAL_TEMPERATURES = {"A": 6, "B": 5, "C": 4}
INITIAL_LOADS = {"A": 2, "B": 2, "C": 2}
SAFE_TEMPERATURE = 10
EXCEEDANCE_BASELINE = 8
COOLING_BUDGET = 4
HORIZON = 12
PRODUCTION_TARGET = 20


def _band(temperature: int) -> str:
    if temperature <= 4:
        return "COOL"
    if temperature <= 7:
        return "WARM"
    if temperature == 8:
        return "RISING"
    if temperature <= 10:
        return "NEAR_LIMIT"
    return "OVERHEAT"


class Map19Environment(MapEnvironment):
    map_id = "MAP-19"
    title = "温度临界点"
    world = "volcano"
    level = "简单"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "read_temperature": {frozenset({"tool", "station"})},
        "set_cooling": {frozenset({"tool", "set_cooling"})},
        "adjust_loads": {frozenset({"tool", "adjust_loads"})},
        "forecast_next": {frozenset({"tool", "forecast_next"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "ticks_remaining",
            "temperature_bands",
            "active_cooling",
            "current_load_levels",
            "pending_cooling_commands",
            "production_points",
            "production_target",
            "last_temperature_reading",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.temperatures = dict(INITIAL_TEMPERATURES)
        self.loads = dict(INITIAL_LOADS)
        self.active_cooling = {zone: 0 for zone in ZONES}
        self.pending: list[dict[str, Any]] = []
        self.production = 0
        self.forecasts: list[list[int]] = []
        self.forecast_errors: list[int] = []
        self.reading: dict[str, Any] | None = None
        self.read_tick = -1
        self.settled_states: list[dict[str, int]] = []
        self.deltas: dict[str, list[int]] = {zone: [] for zone in ZONES}
        self._cost = 0

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "ticks_remaining": max(0, HORIZON - self.tick_count),
            "temperature_bands": {
                zone: _band(self.temperatures[zone]) for zone in ZONES
            },
            "active_cooling": dict(self.active_cooling),
            "current_load_levels": dict(self.loads),
            "pending_cooling_commands": [
                {
                    "vector": dict(command["vector"]),
                    "effective_tick": command["effective_tick"],
                }
                for command in self.pending
            ],
            "production_points": self.production,
            "production_target": PRODUCTION_TARGET,
            "last_temperature_reading": self.reading,
            "goal": (
                "在 tick 0–11 内维持三区温度不超过 10，并累计至少 20 点产能；"
                "冷却阀命令在提交后 tick+2 才生效。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _mature(self) -> None:
        due = [
            command
            for command in self.pending
            if command["effective_tick"] <= self.tick_count
        ]
        for command in due:
            self.active_cooling = dict(command["vector"])
        self.pending = [
            command
            for command in self.pending
            if command["effective_tick"] > self.tick_count
        ]

    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        if action.tool == "wait":
            return self._wait()
        self._cost = 0
        if action.tool == "read_temperature":
            return self._read_temperature(action)
        if action.tool == "set_cooling":
            return self._set_cooling(action)
        if action.tool == "adjust_loads":
            return self._adjust_loads(action)
        if action.tool == "forecast_next":
            return self._forecast(action)
        return "ACTION_NOT_ALLOWED"

    def _read_temperature(self, action: V8Action) -> str:
        zone = action.station
        if zone not in ZONES:
            return "INVALID_ZONE"
        if self.read_tick == self.tick_count:
            return "READ_ALREADY_USED"
        self.read_tick = self.tick_count
        delta = self.deltas[zone][-1] if self.deltas[zone] else 0
        self.reading = {
            "tick": self.tick_count,
            "zone": zone,
            "temperature": self.temperatures[zone],
            "delta": delta,
        }
        return f"TEMPERATURE_READ:{zone}"

    def _set_cooling(self, action: V8Action) -> str:
        vector = action.set_cooling
        if vector is None or len(vector) != 3:
            return "INVALID_COOLING_VECTOR"
        if any(not isinstance(value, int) or value < 0 or value > 2 for value in vector):
            return "INVALID_COOLING_VECTOR"
        if sum(vector) > COOLING_BUDGET:
            return "VALVE_BUDGET_EXCEEDED"
        command = {
            "vector": dict(zip(ZONES, vector, strict=True)),
            "effective_tick": self.tick_count + 2,
        }
        self.pending.append(command)
        return f"COOLING_QUEUED_FOR_TICK:{command['effective_tick']}"

    def _adjust_loads(self, action: V8Action) -> str:
        loads = action.adjust_loads
        if loads is None or len(loads) != 3:
            return "INVALID_LOAD_LEVEL"
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2
            for value in loads
        ):
            return "INVALID_LOAD_LEVEL"
        self.loads = dict(zip(ZONES, loads, strict=True))
        return "LOADS_UPDATED"

    def _forecast(self, action: V8Action) -> str:
        forecast = action.forecast_next
        if forecast is None or len(forecast) != 3:
            return "INVALID_FORECAST"
        if any(not isinstance(value, int) or isinstance(value, bool) for value in forecast):
            return "INVALID_FORECAST"
        self.forecasts.append(list(forecast))
        return "FORECAST_RECORDED"

    def _wait(self) -> str:
        self._mature()
        load_total = sum(self.loads[zone] for zone in ZONES)
        next_temperatures = {
            zone: max(
                0,
                self.temperatures[zone]
                + self.loads[zone]
                - self.active_cooling[zone],
            )
            for zone in ZONES
        }
        forecast = self.forecasts.pop(0) if self.forecasts else None
        if forecast is not None:
            self.forecast_errors.extend(
                abs(forecast[index] - next_temperatures[zone])
                for index, zone in enumerate(ZONES)
            )
        for _index, zone in enumerate(ZONES):
            self.deltas[zone].append(next_temperatures[zone] - self.temperatures[zone])
        self.temperatures = next_temperatures
        self.settled_states.append(dict(next_temperatures))
        self.reading = None
        self.read_tick = -1
        if any(
            self.temperatures[zone] > SAFE_TEMPERATURE for zone in ZONES
        ):
            self._fail("THERMAL_RUNAWAY")
            return "THERMAL_RUNAWAY"
        self.production += load_total
        if self.tick_count + 1 >= HORIZON:
            if self.production >= PRODUCTION_TARGET:
                self._succeed("PRODUCTION_TARGET_MET")
                return "PRODUCTION_TARGET_MET"
            self._fail("PRODUCTION_BELOW_20")
            return "PRODUCTION_BELOW_20"
        return "TICK_SETTLED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        # Terminal transitions are decided inside ``_wait`` so the failing tick
        # is fully recorded before the clock advances.
        return None

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "temperatures": dict(self.temperatures),
            "loads": dict(self.loads),
            "active_cooling": dict(self.active_cooling),
            "pending": list(self.pending),
            "production": self.production,
            "settled_states": list(self.settled_states),
            "deltas": {zone: list(self.deltas[zone]) for zone in ZONES},
            "forecast_errors": list(self.forecast_errors),
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        exceedance = sum(
            max(0, temperature - EXCEEDANCE_BASELINE)
            for state in self.settled_states
            for temperature in state.values()
        )
        oscillations = 0
        for zone in ZONES:
            previous = 0
            for delta in self.deltas[zone]:
                if delta == 0:
                    continue
                if previous and (delta > 0) != (previous > 0):
                    oscillations += 1
                previous = delta
        overheat_ticks = sum(
            1
            for state in self.settled_states
            for temperature in state.values()
            if temperature > SAFE_TEMPERATURE
        )
        return {
            "map19.temperature_exceedance_area": exceedance,
            "map19.oscillation_count": oscillations,
            "map19.critical_overheat_ticks": overheat_ticks,
            "map19.coolant_exhausted": int(
                self.terminal_reason == "COOLANT_EXHAUSTED"
            ),
        }


def _forecast(temperatures: list[int]) -> dict[str, Any]:
    return {"tool": "forecast_next", "forecast_next": temperatures}


def _early_cooling_actions() -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {"tool": "read_temperature", "station": "A"},
        {"tool": "set_cooling", "set_cooling": [2, 1, 1]},
        {"tool": "adjust_loads", "adjust_loads": [2, 1, 1]},
        _forecast([8, 6, 5]),
        {"tool": "wait"},
    ]
    actions.append(_forecast([10, 7, 6]))
    actions.append({"tool": "wait"})
    for _ in range(10):
        actions.append(_forecast([10, 7, 6]))
        actions.append({"tool": "wait"})
    return actions


def _exact_twenty_actions() -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {"tool": "set_cooling", "set_cooling": [2, 1, 1]},
        {"tool": "adjust_loads", "adjust_loads": [2, 0, 0]},
    ]
    for tick in range(12):
        if tick == 10:
            actions.append({"tool": "adjust_loads", "adjust_loads": [0, 0, 0]})
        actions.append(_forecast([10 if tick >= 1 else 8, 5, 4]))
        actions.append({"tool": "wait"})
    return actions


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "early_cooling",
        "seed": 0,
        "actions": _early_cooling_actions(),
        "expect_success": True,
    },
    {
        "trace_id": "exact_production_boundary",
        "seed": 0,
        "actions": _exact_twenty_actions(),
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "early_cooling_area_and_production",
        "seed": 0,
        "actions": _early_cooling_actions(),
        "expect": {
            "map19.temperature_exceedance_area": 22,
            "map19.oscillation_count": 0,
            "map19.critical_overheat_ticks": 0,
            "map19.coolant_exhausted": 0,
        },
    },
    {
        "name": "production_exactly_twenty_succeeds",
        "seed": 0,
        "actions": _exact_twenty_actions(),
        "expect": {
            "map19.temperature_exceedance_area": 18,
            "map19.oscillation_count": 1,
            "map19.critical_overheat_ticks": 0,
            "map19.coolant_exhausted": 0,
        },
    },
    {
        "name": "valve_budget_rejected_atomically",
        "seed": 0,
        "actions": [
            {"tool": "set_cooling", "set_cooling": [2, 1, 2]},
        ],
        "expect": {
            "map19.temperature_exceedance_area": 0,
            "map19.oscillation_count": 0,
            "map19.critical_overheat_ticks": 0,
            "map19.coolant_exhausted": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map19Environment"]
