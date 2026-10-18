"""MAP-06 V10｜暴风眼：10-seed 分层天气 cohort 下的预报与加固决策（DCR-V10-03）。

与 V8 的差异：

- 10 个预登记环境 seed 组成分层 cohort（晴稳 / 短风暴 / 长风暴 / 预报噪声 / 边界期限），
  每个 seed 的天气真值、80% 准确率预报读数与公开截止时刻都写在 ``VARIANTS``；
  cohort 层面的长风暴先验 = 5/10、预报正确 = 8/10，与公开参数一致；
- 短风暴不再“无风险”：暴露区段与无护盾维修各 +1/tick（V8 短风暴恒 0 风险，
  使 seed 0 两步直达且核心机制不触发）；长风暴暴露 +1/tick、无护盾维修 +3/tick；
- 截止时刻随 seed 公开变化：部分实例中“先读预报再加固”已来不及，迫使 Agent 先判断
  信息是否还能改变决策；
- 被拒动作消耗 1 tick；预报重复读取返回同一读数并再付 2 tick；
- 主指标是公开的风险—时效效用 ``U = success × (1 − 0.5·risk/(budget+1) − 0.5·finish/deadline)``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

EDGES = {
    "M_Q": ("M", "Q"),
    "Q_P": ("Q", "P"),
    "M_G": ("M", "G"),
    "G_P": ("G", "P"),
}
EDGE_COST = {"M_Q": 1, "Q_P": 1, "M_G": 2, "G_P": 2}
EXPOSED_EDGES = frozenset({"Q_P", "G_P"})
RISK_BUDGET = 4
FORECAST_TICKS = 2
HARDEN_TICKS = 3
REPAIR_TICKS = 2
#: 每 tick 风险增量：(暴露区段, 无护盾维修)。
RISK_RATES = {"calm": (0, 0), "short": (1, 1), "long": (1, 3)}


@dataclass(frozen=True)
class WeatherVariant:
    weather: str  # calm / short / long（隐藏）
    forecast: str  # short / long（预报读数）
    deadline: int  # 公开
    cohort: str


VARIANTS: dict[int, WeatherVariant] = {
    0: WeatherVariant("calm", "short", 14, "clear_stable"),
    1: WeatherVariant("short", "short", 14, "short_storm"),
    2: WeatherVariant("long", "long", 14, "long_storm"),
    3: WeatherVariant("long", "long", 13, "long_storm"),
    4: WeatherVariant("short", "long", 14, "forecast_noise_false_alarm"),
    5: WeatherVariant("long", "short", 14, "forecast_noise_miss"),
    6: WeatherVariant("long", "long", 11, "boundary_deadline"),
    7: WeatherVariant("calm", "short", 8, "clear_tight"),
    8: WeatherVariant("short", "short", 11, "short_tight"),
    9: WeatherVariant("long", "long", 12, "boundary_exact"),
}

PLANS: dict[str, tuple[dict[str, Any], ...]] = {
    "direct": (
        {"tool": "move", "edge_id": "Q_P"},
        {"tool": "interact", "target_id": "P", "operation": "repair_lighthouse"},
    ),
    "reinforce": (
        {"tool": "move", "edge_id": "M_Q"},
        {"tool": "move", "edge_id": "M_G"},
        {"tool": "interact", "target_id": "G", "operation": "harden"},
        {"tool": "move", "edge_id": "G_P"},
        {"tool": "interact", "target_id": "P", "operation": "repair_lighthouse"},
    ),
}
FORECAST_ACTION = {"tool": "inspect", "target_id": "forecast"}


def plan_actions(plan: str, *, forecast: bool) -> list[dict[str, Any]]:
    prefix = [dict(FORECAST_ACTION)] if forecast else []
    return [*prefix, *(dict(item) for item in PLANS[plan])]


def utility(success: bool, risk: int, finish: int, deadline: int) -> float:
    if not success:
        return 0.0
    return round(1 - 0.5 * risk / (RISK_BUDGET + 1) - 0.5 * finish / deadline, 6)


class Map06V10Environment(V10Map):
    map_id = "MAP-06"
    title = "暴风眼"
    world = "lighthouse"
    level = "困难"
    RULE_VERSION = "v10.map06.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGES
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
            "edge_ticks",
            "exposed_edges",
            "tick",
            "risk",
            "risk_budget",
            "forecast_reading",
            "forecast_queries",
            "forecast_accuracy",
            "prior_long_storm",
            "storm_shield",
            "lamp_restored",
            "deadline_tick",
            "goal",
        }
    )
    PRIMARY_METRIC = "map06.v10.risk_time_utility"
    METRIC_SPECS = (
        MetricSpec(
            "map06.v10.risk_time_utility",
            "primary",
            "higher",
            "success × (1 − 0.5·risk/(budget+1) − 0.5·finish_tick/deadline)",
            "1",
            censored_rule="运行中截尾 → CENSORED；失败 → VALID 0",
        ),
        MetricSpec(
            "map06.v10.utility_regret",
            "primary",
            "lower",
            "该 seed 真值感知最优效用 − 实得效用",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map06.v10.shield_matches_truth",
            "secondary",
            "higher",
            "hardened == (weather == long)",
            "终局局（1）",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map06.v10.forecast_followed",
            "diagnostic",
            "none",
            "读过预报时：hardened == (reading == long)",
            "读过预报的终局局",
            zero_denominator="未读预报 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map06.v10.observation_cost_ticks",
            "guardrail",
            "lower",
            "forecast_queries × 2",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map06.v10.danger_exposure_ticks",
            "guardrail",
            "lower",
            "count(风险增加的 tick)",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map06.v10.final_risk",
            "guardrail",
            "lower",
            "累计风险",
            "—",
            unit="risk",
            valid_range=(0.0, 30.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.node = "Q"
        self.forecast_reading: str | None = None
        self.forecast_queries = 0
        self.risk = 0
        self.storm_shield = False
        self.hardened = False
        self.lamp_restored = False
        self.deadline_tick = self.variant.deadline
        self.danger_ticks = 0
        self.finish_tick: int | None = None
        self._last_cost = 1
        self._exposure_ticks = 0
        self._repair_ticks = 0
        self._repairing = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {"deadline_tick": self.deadline_tick, "cohort_size": len(VARIANTS)}

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "weather": self.variant.weather,
            "forecast": self.variant.forecast,
            "cohort": self.variant.cohort,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "起点 Q（预报站）。边耗时：M_Q=1、Q_P=1、M_G=2、G_P=2；Q_P 与 G_P 是暴露区段。",
            "inspect(target_id=forecast) 只能在 Q 使用，耗 2 tick，读数为 short 或 long；"
            "预报准确率 0.8，长风暴先验 0.5；重复读取返回同一读数并再耗 2 tick。",
            "interact(G, harden) 在 G 耗 3 tick 装上护盾；interact(P, repair_lighthouse) 在 P "
            "耗 2 tick，完成即成功。wait(ticks) 原地等待。被拒动作耗 1 tick。",
            "天气隐藏，三种之一：calm 无风险；short 暴露区段与无护盾维修各 +1/tick；"
            "long 暴露区段 +1/tick、无护盾维修 +3/tick、有护盾维修 0。",
            f"累计风险超过 {RISK_BUDGET} 立即失败；tick 达到 deadline_tick 仍未修好即失败。",
            "评分：成功时 U = 1 − 0.5·风险/5 − 0.5·完成 tick/deadline；失败 U = 0。"
            "越早修好、风险越低越好。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "edge_ticks": dict(EDGE_COST),
            "exposed_edges": sorted(EXPOSED_EDGES),
            "tick": self.tick_count,
            "risk": self.risk,
            "risk_budget": RISK_BUDGET,
            "forecast_reading": self.forecast_reading,
            "forecast_queries": self.forecast_queries,
            "forecast_accuracy": 0.8,
            "prior_long_storm": 0.5,
            "storm_shield": self.storm_shield,
            "lamp_restored": self.lamp_restored,
            "deadline_tick": self.deadline_tick,
            "goal": "在截止前修复灯塔；风暴类型未知，可付时间读预报、绕行加固或直接维修。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._exposure_ticks = 0
        self._repair_ticks = 0
        self._repairing = False
        self._last_cost = 1
        tool = action.tool
        if tool == "move":
            assert action.edge_id is not None
            destination = self.edge_destination(action.edge_id)
            if destination is None:
                return "EDGE_NOT_ADJACENT"
            self.node = destination
            self._last_cost = EDGE_COST[action.edge_id]
            if action.edge_id in EXPOSED_EDGES:
                self._exposure_ticks = self._last_cost
            return f"MOVED:{destination}"
        if tool == "inspect":
            if action.target_id != "forecast" or self.node != "Q":
                return "TARGET_NOT_VISIBLE"
            self._last_cost = FORECAST_TICKS
            self.forecast_queries += 1
            if self.forecast_reading is not None:
                return f"FORECAST_UNCHANGED:{self.forecast_reading}"
            self.forecast_reading = self.variant.forecast
            return f"FORECAST:{self.forecast_reading}"
        if tool == "wait":
            self._last_cost = int(action.ticks or 1)
            return "WAITED"
        if tool == "interact":
            if action.target_id == "P" and action.operation == "repair_lighthouse":
                if self.node != "P":
                    return "TARGET_NOT_VISIBLE"
                self._last_cost = REPAIR_TICKS
                self._repair_ticks = REPAIR_TICKS
                self._repairing = True
                return "REPAIR_STARTED"
            if action.target_id == "G" and action.operation == "harden":
                if self.node != "G":
                    return "TARGET_NOT_VISIBLE"
                if self.storm_shield:
                    return "SHIELD_ALREADY_READY"
                self._last_cost = HARDEN_TICKS
                self.storm_shield = True
                self.hardened = True
                return "STORM_SHIELD_READY"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._last_cost

    def _after_tick(self) -> None:
        exposure_rate, repair_rate = RISK_RATES[self.variant.weather]
        for _ in range(self._last_cost):
            added = 0
            if self._exposure_ticks > 0:
                self._exposure_ticks -= 1
                added = exposure_rate
            elif self._repair_ticks > 0:
                self._repair_ticks -= 1
                added = 0 if self.storm_shield else repair_rate
            if added:
                self.risk += added
                self.danger_ticks += 1
            if self.risk > RISK_BUDGET:
                self._fail("RESOURCE_EXHAUSTED")
                return
        if self._repairing and self._repair_ticks == 0 and self.tick_count <= self.deadline_tick:
            self.lamp_restored = True
            self.finish_tick = self.tick_count
            self._succeed("LAMP_RESTORED")
            return
        if self.tick_count >= self.deadline_tick:
            self._fail("REPAIR_DEADLINE_MISSED")

    def _invalid_action(self) -> str:
        self._exposure_ticks = 0
        self._repair_ticks = 0
        self._repairing = False
        self._last_cost = 1
        return "INVALID_ACTION_SCHEMA"

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "location": self.node,
            "tick": self.tick_count,
            "risk": self.risk,
            "hardened": self.hardened,
            "forecast_queries": self.forecast_queries,
            "lamp_restored": self.lamp_restored,
            "finish_tick": self.finish_tick,
            "danger_ticks": self.danger_ticks,
            "truth_seal": self.truth_seal(),
        }

    def achieved_utility(self) -> float:
        return utility(self.is_success, self.risk, self.finish_tick or 0, self.deadline_tick)

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal or self.status.value == "step_limit_reached"
        if running:
            score: MValue = censored("截尾")
            regret: MValue = censored("截尾")
            shield: MValue = censored("截尾")
        else:
            achieved = self.achieved_utility()
            score = valid(achieved)
            regret = valid(round(oracle_utility(self.environment_seed) - achieved, 6))
            shield = valid(int(self.hardened == (self.variant.weather == "long")))
        if self.forecast_reading is None:
            followed = not_applicable("未读预报")
        elif running:
            followed = censored("截尾")
        else:
            followed = valid(int(self.hardened == (self.forecast_reading == "long")))
        return {
            "map06.v10.risk_time_utility": score,
            "map06.v10.utility_regret": regret,
            "map06.v10.shield_matches_truth": shield,
            "map06.v10.forecast_followed": followed,
            "map06.v10.observation_cost_ticks": valid(self.forecast_queries * FORECAST_TICKS),
            "map06.v10.danger_exposure_ticks": valid(self.danger_ticks),
            "map06.v10.final_risk": valid(self.risk),
        }

    def mechanism_triggered(self) -> bool:
        """本实例存在风暴风险（short/long），即直达与加固的取舍真实有代价。"""

        return self.variant.weather != "calm" or self.deadline_tick < 10


def simulate(seed: int, actions: list[dict[str, Any]]) -> Map06V10Environment:
    environment = Map06V10Environment(seed=seed)
    for payload in actions:
        if environment.is_terminal:
            break
        environment.step(V8Action.model_validate(payload, strict=True))
    return environment


def oracle_plan(seed: int) -> tuple[str, bool]:
    """真值感知：在四个规范计划中选效用最高者（知道天气就不必读预报）。"""

    best: tuple[float, str, bool] = (-1.0, "direct", False)
    for plan in PLANS:
        for forecast in (False, True):
            environment = simulate(seed, plan_actions(plan, forecast=forecast))
            value = environment.achieved_utility()
            if value > best[0]:
                best = (value, plan, forecast)
    return best[1], best[2]


def oracle_utility(seed: int) -> float:
    plan, forecast = oracle_plan(seed)
    return simulate(seed, plan_actions(plan, forecast=forecast)).achieved_utility()


__all__ = [
    "Map06V10Environment",
    "PLANS",
    "VARIANTS",
    "oracle_plan",
    "oracle_utility",
    "plan_actions",
    "simulate",
    "utility",
]
