"""MAP-19 V10｜温度临界点：预测成为产能的必要条件（DCR-V10-10）。

与 V8 的差异：

- `forecast_next` 从“无效动作”变成**有约束力的申报**：每个 tick 结算时，只有在该 tick
  提交过预测、且预测与真实结算的最大误差 ≤ 公开容差，这一 tick 的负荷才计入产能；
  未申报或误差超容差的 tick 产能记 0，并分别记 `unpredicted_ticks` / `rejected_ticks`；
- 预测误差的反馈公开：Observation 给出 `last_forecast_error`、`forecast_tolerance`、
  `accepted_ticks`、`rejected_ticks`，`forecast_next` 不再是“石沉大海”；
- 冷却仍然是 tick+2 生效，因此要正确预测下一 tick 的温度，必须同时算上**尚未生效的
  冷却队列**——时滞第一次真正进入能力链；
- 4 个预登记实例：初始温度、初始负荷、冷却预算、容差、horizon 与产能目标都不同；
- 主指标 `production_credit` = 实得产能 / 目标；旧 `temperature_exceedance_area` 保留为
  护栏并按“已结算区·tick”给出分母。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    ratio,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

ZONES = ("A", "B", "C")
SAFE_TEMPERATURE = 10
EXCEEDANCE_BASELINE = 8


class Variant19:
    def __init__(
        self,
        label: str,
        temperatures: tuple[int, int, int],
        loads: tuple[int, int, int],
        cooling_budget: int,
        tolerance: int,
        horizon: int,
        target: int,
    ) -> None:
        self.label = label
        self.temperatures = dict(zip(ZONES, temperatures, strict=True))
        self.loads = dict(zip(ZONES, loads, strict=True))
        self.cooling_budget = cooling_budget
        self.tolerance = tolerance
        self.horizon = horizon
        self.target = target


VARIANTS: dict[int, Variant19] = {
    0: Variant19("baseline", (6, 5, 4), (2, 2, 2), 4, 1, 12, 49),
    1: Variant19("higher_start_tight_budget", (7, 6, 3), (2, 1, 2), 4, 1, 10, 41),
    2: Variant19("roomy_budget_lower_start", (5, 5, 5), (1, 2, 2), 5, 1, 12, 58),
    3: Variant19("wide_tolerance_short_horizon", (8, 4, 6), (2, 2, 1), 3, 2, 10, 31),
}


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


class Map19V10Environment(V10Map):
    map_id = "MAP-19"
    title = "温度临界点"
    world = "volcano"
    level = "简单"
    RULE_VERSION = "v10.map19.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
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
            "current_temperatures",
            "active_cooling",
            "current_load_levels",
            "pending_cooling_commands",
            "production_points",
            "production_target",
            "forecast_tolerance",
            "cooling_budget",
            "last_forecast_error",
            "accepted_ticks",
            "rejected_ticks",
            "last_temperature_reading",
            "goal",
        }
    )
    PRIMARY_METRIC = "map19.v10.production_credit"
    METRIC_SPECS = (
        MetricSpec(
            "map19.v10.production_credit",
            "primary",
            "higher",
            "实得产能 / 目标（只计申报准确 tick 的负荷）",
            "目标产能",
            censored_rule="截尾 → CENSORED；热失控 → VALID 0",
        ),
        MetricSpec(
            "map19.v10.mean_forecast_error",
            "secondary",
            "lower",
            "已结算 tick 的预测最大误差均值",
            "提交过预测的 tick",
            zero_denominator="从未提交预测 → NOT_APPLICABLE",
            unit="temperature",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map19.v10.rejected_ticks",
            "guardrail",
            "lower",
            "预测误差超容差或未申报的 tick 数",
            "已结算 tick",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map19.v10.temperature_exceedance_area",
            "guardrail",
            "lower",
            "Σ max(0, T − 8) / 已结算区·tick 数",
            "已结算区·tick 数",
            unit="temperature",
            valid_range=(0.0, 12.0),
        ),
        MetricSpec(
            "map19.v10.critical_overheat_ticks",
            "guardrail",
            "lower",
            "T > 10 的区·tick 数",
            "—",
            unit="count",
            valid_range=(0.0, 36.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.temperatures = dict(self.variant.temperatures)
        self.loads = dict(self.variant.loads)
        self.active_cooling = {zone: 0 for zone in ZONES}
        self.pending: list[dict[str, Any]] = []
        self.production = 0
        self.forecast: list[int] | None = None
        self.forecast_errors: list[int] = []
        self.accepted_ticks = 0
        self.rejected_ticks = 0
        self.unpredicted_ticks = 0
        self.reading: dict[str, Any] | None = None
        self.read_tick = -1
        self.settled: list[dict[str, int]] = []
        self.deltas: dict[str, list[int]] = {zone: [] for zone in ZONES}
        self.last_error: int | None = None
        self._cost = 0

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_temperatures": dict(self.variant.temperatures),
            "cooling_budget": self.variant.cooling_budget,
            "forecast_tolerance": self.variant.tolerance,
            "horizon": self.variant.horizon,
            "production_target": self.variant.target,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_loads": dict(self.variant.loads),
            "horizon": self.variant.horizon,
            "target": self.variant.target,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "三区 A/B/C；每 tick 结算一次温度：T_next = max(0, T + 负荷 − 已生效冷却)。",
            f"负荷每区 0–2；冷却向量每区 0–2 且总和不超过 {self.variant.cooling_budget}；"
            "同一生效 tick 上最后一条入队向量生效。",
            "set_cooling 在提交后 tick+2 才生效。",
            "**forecast_next 是申报**：必须提交下一 tick 的三区温度预测；预测最大误差 ≤ "
            f"{self.variant.tolerance} 时该 tick 的负荷才计入产能，否则该 tick 产能记 0。",
            f"在 {self.variant.horizon} tick 内累计 {self.variant.target} 点产能"
            "且温度不超 10 即成功。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "ticks_remaining": max(0, self.variant.horizon - self.tick_count),
            "temperature_bands": {zone: _band(self.temperatures[zone]) for zone in ZONES},
            "current_temperatures": dict(self.temperatures),
            "active_cooling": dict(self.active_cooling),
            "current_load_levels": dict(self.loads),
            "pending_cooling_commands": [
                {"vector": dict(command["vector"]), "effective_tick": command["effective_tick"]}
                for command in self.pending
            ],
            "production_points": self.production,
            "production_target": self.variant.target,
            "forecast_tolerance": self.variant.tolerance,
            "cooling_budget": self.variant.cooling_budget,
            "last_forecast_error": self.last_error,
            "accepted_ticks": self.accepted_ticks,
            "rejected_ticks": self.rejected_ticks,
            "last_temperature_reading": self.reading,
            "goal": (
                "在 horizon 内累计目标产能且三区不超 10；每个 tick 必须申报下一 tick 的温度，"
                "误差超过公开容差时该 tick 产能作废。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _mature(self) -> None:
        due = [item for item in self.pending if item["effective_tick"] <= self.tick_count]
        for item in due:
            self.active_cooling = dict(item["vector"])
        self.pending = [item for item in self.pending if item["effective_tick"] > self.tick_count]

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
        if sum(vector) > self.variant.cooling_budget:
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
        self.forecast = list(forecast)
        return "FORECAST_RECORDED"

    def _wait(self) -> str:
        self._mature()
        load_total = sum(self.loads[zone] for zone in ZONES)
        next_temperatures = {
            zone: max(0, self.temperatures[zone] + self.loads[zone] - self.active_cooling[zone])
            for zone in ZONES
        }
        if self.forecast is None:
            error = max(
                abs(next_temperatures[zone] - self.temperatures[zone]) + 99 for zone in ZONES
            )
            accepted = False
            self.unpredicted_ticks += 1
        else:
            error = max(
                abs(self.forecast[index] - next_temperatures[zone])
                for index, zone in enumerate(ZONES)
            )
            accepted = error <= self.variant.tolerance
        self.forecast = None
        self.last_error = None if not accepted and error > 90 else error
        self.forecast_errors.append(error)
        if accepted:
            self.accepted_ticks += 1
            self.production += load_total
        else:
            self.rejected_ticks += 1
        for zone in ZONES:
            self.deltas[zone].append(next_temperatures[zone] - self.temperatures[zone])
        self.temperatures = next_temperatures
        self.settled.append(dict(next_temperatures))
        self.reading = None
        self.read_tick = -1
        if any(self.temperatures[zone] > SAFE_TEMPERATURE for zone in ZONES):
            self._fail("THERMAL_RUNAWAY")
            return "THERMAL_RUNAWAY"
        if self.tick_count + 1 >= self.variant.horizon:
            if self.production >= self.variant.target:
                self._succeed("PRODUCTION_TARGET_MET")
                return "PRODUCTION_TARGET_MET"
            self._fail("PRODUCTION_BELOW_TARGET")
            return "PRODUCTION_BELOW_TARGET"
        return "TICK_SETTLED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "temperatures": dict(self.temperatures),
            "loads": dict(self.loads),
            "active_cooling": dict(self.active_cooling),
            "pending": list(self.pending),
            "production": self.production,
            "accepted_ticks": self.accepted_ticks,
            "rejected_ticks": self.rejected_ticks,
            "unpredicted_ticks": self.unpredicted_ticks,
            "forecast_errors": list(self.forecast_errors),
            "settled_states": list(self.settled),
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if self.is_terminal and not running:
            credit: MValue = valid(min(1.0, round(self.production / self.variant.target, 6)))
        else:
            credit = censored("截尾")
        real_errors = [item for item in self.forecast_errors if item <= 90]
        mean_error: MValue = (
            valid(round(sum(real_errors) / len(real_errors), 6))
            if real_errors
            else not_applicable("从未提交预测")
        )
        settled_zone_ticks = max(1, len(self.settled) * len(ZONES))
        area = sum(
            max(0, temperature - EXCEEDANCE_BASELINE)
            for state in self.settled
            for temperature in state.values()
        )
        overheat = sum(
            1
            for state in self.settled
            for temperature in state.values()
            if temperature > SAFE_TEMPERATURE
        )
        return {
            "map19.v10.production_credit": credit,
            "map19.v10.mean_forecast_error": mean_error,
            "map19.v10.rejected_ticks": valid(self.rejected_ticks + self.unpredicted_ticks),
            "map19.v10.temperature_exceedance_area": ratio(area, settled_zone_ticks),
            "map19.v10.critical_overheat_ticks": valid(overheat),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少有一个 tick 的产能是靠“申报准确”拿到的。"""

        return self.accepted_ticks > 0


def _vector_for(temperatures: dict[str, int], loads: dict[str, int], budget: int) -> list[int]:
    """把冷却预算优先分给“投影热量最高”的区。"""

    ordered = sorted(ZONES, key=lambda zone: -(temperatures[zone] + loads[zone]))
    vector = [0, 0, 0]
    remaining = budget
    for zone in ordered:
        index = ZONES.index(zone)
        want = min(2, remaining, max(0, temperatures[zone] + loads[zone] - 4))
        vector[index] = want
        remaining -= want
    for index in range(3):
        if remaining <= 0:
            break
        if vector[index] < 2:
            add = min(2 - vector[index], remaining)
            vector[index] += add
            remaining -= add
    return vector


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：按“下一 tick 已生效冷却”选最大安全负荷，并把冷却排到 t+2。"""

    environment = Map19V10Environment(seed=environment_seed)
    variant = VARIANTS[environment_seed]
    actions: list[dict[str, Any]] = []
    while not environment.is_terminal:
        tick = environment.tick_count
        # 下一 tick 的已生效冷却（含本 tick 到期的队列）
        active_next = dict(environment.active_cooling)
        for command in environment.pending:
            if command["effective_tick"] <= tick:
                active_next = dict(command["vector"])
        loads = {
            zone: max(
                0,
                min(2, SAFE_TEMPERATURE - environment.temperatures[zone] + active_next[zone]),
            )
            for zone in ZONES
        }
        loads = {zone: min(2, max(0, loads[zone])) for zone in ZONES}
        if loads != environment.loads:
            payload = {"tool": "adjust_loads", "adjust_loads": [loads[zone] for zone in ZONES]}
            actions.append(payload)
            environment.step(V8Action.model_validate(payload, strict=True))
            if environment.is_terminal:
                break
        # 冷却排到 t+2：按当前投影分配预算
        vector = _vector_for(environment.temperatures, loads, variant.cooling_budget)
        payload = {"tool": "set_cooling", "set_cooling": vector}
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))
        if environment.is_terminal:
            break
        # 预测：用“下一 tick 生效冷却 + 当前负荷”精确计算
        active_next = dict(environment.active_cooling)
        for command in environment.pending:
            if command["effective_tick"] <= environment.tick_count:
                active_next = dict(command["vector"])
        prediction = [
            max(0, environment.temperatures[zone] + environment.loads[zone] - active_next[zone])
            for zone in ZONES
        ]
        payload = {"tool": "forecast_next", "forecast_next": prediction}
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))
        if environment.is_terminal:
            break
        actions.append({"tool": "wait"})
        environment.step(V8Action.model_validate({"tool": "wait"}, strict=True))
    return actions


__all__ = [
    "Map19V10Environment",
    "SAFE_TEMPERATURE",
    "VARIANTS",
    "Variant19",
    "ZONES",
    "oracle_actions",
]
