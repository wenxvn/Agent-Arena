"""MAP-06 V10 基线：真值 Oracle、forecast_aware 启发式与 always_direct / always_reinforce。

公开启发式只读 Observation 的 ``deadline_tick``、``forecast_reading``、``storm_shield``、
``location`` 与公开边耗时：

- 若“读预报 + 加固 + 维修”（12 tick）能在截止前完成，则先读预报；读数 long → 加固，
  short → 直修（后验长风暴概率 0.2）；
- 否则不读预报：截止 ≥ 10 时加固（先验 0.5 下直修的期望失败率过高），否则直修。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map06 import PLANS, oracle_plan, plan_actions

Action = dict[str, Any]
FORECAST_THEN_REINFORCE_TICKS = 12
REINFORCE_TICKS = 10


def oracle_actions(environment_seed: int) -> list[Action]:
    plan, forecast = oracle_plan(environment_seed)
    return plan_actions(plan, forecast=forecast)


class _PlanPolicy:
    name = "plan"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.decided = False

    def choose(self, observation: dict[str, Any]) -> tuple[str, bool]:
        raise NotImplementedError

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.decided:
            plan, forecast = self.choose(observation)
            if forecast:
                self.queue = [{"tool": "inspect", "target_id": "forecast"}]
                self.pending_after_forecast = True
            else:
                self.queue = [dict(item) for item in PLANS[plan]]
                self.pending_after_forecast = False
            self.decided = True
        if not self.queue and getattr(self, "pending_after_forecast", False):
            self.pending_after_forecast = False
            plan = "reinforce" if observation.get("forecast_reading") == "long" else "direct"
            self.queue = [dict(item) for item in PLANS[plan]]
        return self.queue.pop(0) if self.queue else {"tool": "wait", "ticks": 1}


class Map06ForecastAware(_PlanPolicy):
    name = "public_heuristic"

    def choose(self, observation: dict[str, Any]) -> tuple[str, bool]:
        deadline = int(observation["deadline_tick"])
        if deadline >= FORECAST_THEN_REINFORCE_TICKS:
            return "direct", True
        return ("reinforce" if deadline >= REINFORCE_TICKS else "direct"), False


class Map06AlwaysDirect(_PlanPolicy):
    name = "always_direct"

    def choose(self, observation: dict[str, Any]) -> tuple[str, bool]:
        del observation
        return "direct", False


class Map06AlwaysReinforce(_PlanPolicy):
    name = "always_reinforce"

    def choose(self, observation: dict[str, Any]) -> tuple[str, bool]:
        del observation
        return "reinforce", False


class Map06ForecastTrusting(_PlanPolicy):
    """总是先读预报再按读数行动，不考虑截止时刻（检验“信息有价值但有成本”）。"""

    name = "forecast_always"

    def choose(self, observation: dict[str, Any]) -> tuple[str, bool]:
        del observation
        return "direct", True


HEURISTIC = Map06ForecastAware
ABLATIONS: dict[str, type[_PlanPolicy]] = {
    "always_direct": Map06AlwaysDirect,
    "always_reinforce": Map06AlwaysReinforce,
    "forecast_always": Map06ForecastTrusting,
}

__all__ = ["ABLATIONS", "HEURISTIC", "oracle_actions"]
