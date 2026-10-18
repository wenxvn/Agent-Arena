"""MAP-21 V10 基线：真值 Oracle、risk_aware 启发式、always_evac、always_collect。

- ``oracle``：知道喷发时刻，选能按时撤离、科研分最高的计划；
- ``public_heuristic``（risk_aware）：先测量，按公开后验选计划——只选"抵 E 时刻前喷发
  概率 ≤ 5%"的计划中科研分最高者；
- ``always_evac``：立即直达 E（安全但科研 0）；
- ``always_collect``：不测量，直接走最高分的深层加固样品路线（不考虑风险）；
- ``measure_then_evac``：测量后直达（只拿 5 分测量记录）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map21 import (
    ERUPTION_TICKS,
    PLANS,
    VARIANTS,
    plan_actions,
    plan_arrival,
    plan_science,
)

Action = dict[str, Any]
RISK_TOLERANCE = 0.05


def oracle_actions(environment_seed: int) -> list[Action]:
    eruption = VARIANTS[environment_seed][0]
    best = max(
        (
            (
                plan_science(plan, measure=measure),
                -plan_arrival(plan, measure=measure),
                plan,
                measure,
            )
            for plan in PLANS
            for measure in (False, True)
            if plan_arrival(plan, measure=measure) <= eruption
        ),
    )
    return plan_actions(best[2], measure=best[3])


def risk_of(posterior: dict[str, float], arrival: int) -> float:
    return sum(weight for tick, weight in posterior.items() if int(tick) < arrival)


class _Queue:
    name = "queue"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.started = False

    def first(self, observation: dict[str, Any]) -> list[Action]:
        raise NotImplementedError

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if not self.started:
            self.queue = self.first(observation)
            self.started = True
        if not self.queue:
            self.queue = self.after_measure(observation)
        return self.queue.pop(0) if self.queue else {"tool": "wait", "ticks": 1}

    def after_measure(self, observation: dict[str, Any]) -> list[Action]:
        del observation
        return []


class Map21RiskAware(_Queue):
    name = "public_heuristic"

    def first(self, observation: dict[str, Any]) -> list[Action]:
        del observation
        return [{"tool": "measure"}]

    def after_measure(self, observation: dict[str, Any]) -> list[Action]:
        if self.started and getattr(self, "planned", False):
            return []
        self.planned = True
        posterior = observation["posterior_over_eruption_ticks"]
        elapsed = int(observation["elapsed_tick"])
        options = []
        for plan in PLANS:
            arrival = elapsed + plan_arrival(plan, measure=False)
            if risk_of(posterior, arrival) <= RISK_TOLERANCE:
                options.append((plan_science(plan, measure=False), -arrival, plan))
        plan = max(options)[2] if options else "direct"
        return [dict(item) for item in PLANS[plan]]

    def reset(self) -> None:
        super().reset()
        self.planned = False


class Map21AlwaysEvac(_Queue):
    name = "always_evac"

    def first(self, observation: dict[str, Any]) -> list[Action]:
        del observation
        return plan_actions("direct", measure=False)


class Map21AlwaysCollect(_Queue):
    name = "always_collect"

    def first(self, observation: dict[str, Any]) -> list[Action]:
        del observation
        return plan_actions("deep_reinforced", measure=False)


class Map21MeasureThenEvac(_Queue):
    name = "measure_then_evac"

    def first(self, observation: dict[str, Any]) -> list[Action]:
        del observation
        return plan_actions("direct", measure=True)


HEURISTIC = Map21RiskAware
ABLATIONS: dict[str, type[_Queue]] = {
    "always_evac": Map21AlwaysEvac,
    "always_collect": Map21AlwaysCollect,
    "measure_then_evac": Map21MeasureThenEvac,
}

__all__ = ["ABLATIONS", "ERUPTION_TICKS", "HEURISTIC", "oracle_actions", "risk_of"]
