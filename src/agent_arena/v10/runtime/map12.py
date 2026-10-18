"""MAP-12 V10｜极夜三十天：跨期库存与研究积分的劳动分配（DCR-V10-22）。

V9 的证据：`v9_fixed` 臂没有有效 MiMo 结果，且离线也未验证“跨期库存 + 研究积分”
是否真的需要平衡。V10 的修复：

- **每日若干劳动槽**：`forage`（食物 +2）、`repair`（站体 +2）、`research`（研究 +1）；
- **每日结算**：食物 -consumption、站体 -decay；任一归零即失败（`STARVED` / `STATION_LOST`）；
- **必须留出研究槽**：研究目标 = 可用槽位减去维持生存所需槽位的余量，因此
  “只顾生存”与“只顾研究”都会失败；
- 4 个预登记实例：初始食物/站体、消耗/衰减、槽位数与研究目标都不同。

指标：`mission_success`（主）+ `research_points` / `min_food` / `min_integrity` / `idle_slots`。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, ratio, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

TASKS = ("forage", "repair", "research")
DAYS = 30


class Variant12:
    def __init__(
        self,
        label: str,
        food: int,
        integrity: int,
        consumption: int,
        decay: int,
        slots: int,
        target: int,
    ) -> None:
        self.label = label
        self.food = food
        self.integrity = integrity
        self.consumption = consumption
        self.decay = decay
        self.slots = slots
        self.target = target


VARIANTS: dict[int, Variant12] = {
    0: Variant12("balanced", 12, 12, 2, 2, 3, 34),
    1: Variant12("lean_stock", 8, 10, 2, 2, 3, 32),
    2: Variant12("fast_burn", 14, 14, 3, 3, 4, 36),
    3: Variant12("wide_margin", 20, 18, 2, 2, 4, 68),
}


class Map12V10Environment(V10Map):
    map_id = "MAP-12"
    title = "极夜三十天"
    world = "polar"
    level = "困难"
    RULE_VERSION = "v10.map12.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "assign": {frozenset({"tool", "plan"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "day",
            "days_remaining",
            "food",
            "integrity",
            "research_points",
            "research_target",
            "slots_per_day",
            "daily_consumption",
            "daily_decay",
            "tasks",
            "idle_slots",
            "goal",
        }
    )
    PRIMARY_METRIC = "map12.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map12.v10.mission_success",
            "primary",
            "higher",
            "存活 30 天且研究积分达到目标",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map12.v10.research_points",
            "secondary",
            "higher",
            "累计研究积分",
            "—",
            unit="points",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map12.v10.research_completion",
            "secondary",
            "higher",
            "研究积分 / 目标（可 >1：超额研究计入）",
            "目标积分",
            valid_range=(0.0, 3.0),
        ),
        MetricSpec(
            "map12.v10.min_food",
            "guardrail",
            "higher",
            "过程中最低食物库存",
            "—",
            unit="stock",
            valid_range=(0.0, 100.0),
        ),
        MetricSpec(
            "map12.v10.idle_slots",
            "diagnostic",
            "lower",
            "未分配任何任务的槽位总数",
            "—",
            unit="count",
            valid_range=(0.0, 100.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 200) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.day = 0
        self.food = self.variant.food
        self.integrity = self.variant.integrity
        self.research = 0
        self.idle_slots = 0
        self.min_food = self.variant.food
        self.min_integrity = self.variant.integrity
        self.plans: list[dict[str, int]] = []

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "days": DAYS,
            "slots_per_day": self.variant.slots,
            "daily_consumption": self.variant.consumption,
            "daily_decay": self.variant.decay,
            "research_target": self.variant.target,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_food": self.variant.food,
            "initial_integrity": self.variant.integrity,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            f"共 {DAYS} 天，每天 {self.variant.slots} 个劳动槽；assign(plan=[...]) 一次排完当天。",
            "forage：食物 +2；repair：站体 +2；research：研究 +1。",
            f"每日结算：食物 -{self.variant.consumption}、站体 -{self.variant.decay}。",
            f"研究积分达到 {self.variant.target} 且存活到第 {DAYS} 天才算成功。",
            "食物归零 → STARVED；站体归零 → STATION_LOST。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "days_remaining": max(0, DAYS - self.day),
            "food": self.food,
            "integrity": self.integrity,
            "research_points": self.research,
            "research_target": self.variant.target,
            "slots_per_day": self.variant.slots,
            "daily_consumption": self.variant.consumption,
            "daily_decay": self.variant.decay,
            "tasks": list(TASKS),
            "idle_slots": self.idle_slots,
            "goal": "在极夜里活下去，并把研究积分做够。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        if action.tool == "wait":
            return self._settle([])
        if action.tool != "assign":
            return "ACTION_NOT_ALLOWED"
        plan = action.plan or []
        if len(plan) > self.variant.slots:
            return "TOO_MANY_SLOTS"
        if any(str(item) not in TASKS for item in plan):
            return "UNKNOWN_TASK"
        return self._settle([str(item) for item in plan])

    def _settle(self, plan: list[str]) -> str:
        counts = {task: plan.count(task) for task in TASKS}
        self.idle_slots += max(0, self.variant.slots - len(plan))
        self.food += counts["forage"] * 2
        self.integrity += counts["repair"] * 2
        self.research += counts["research"]
        self.food -= self.variant.consumption
        self.integrity -= self.variant.decay
        self.plans.append(counts)
        self.day += 1
        self.min_food = min(self.min_food, self.food)
        self.min_integrity = min(self.min_integrity, self.integrity)
        if self.food <= 0:
            self._fail("STARVED")
            return "STARVED"
        if self.integrity <= 0:
            self._fail("STATION_LOST")
            return "STATION_LOST"
        if self.day >= DAYS:
            if self.research >= self.variant.target:
                self._succeed("RESEARCH_COMPLETED")
                return "RESEARCH_COMPLETED"
            self._fail("RESEARCH_SHORT")
            return "RESEARCH_SHORT"
        return "DAY_SETTLED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return 1

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "day": self.day,
            "food": self.food,
            "integrity": self.integrity,
            "research": self.research,
            "min_food": self.min_food,
            "min_integrity": self.min_integrity,
            "idle_slots": self.idle_slots,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        success: MValue = censored("截尾") if running else valid(int(self.is_success))
        return {
            "map12.v10.mission_success": success,
            "map12.v10.research_points": valid(self.research),
            "map12.v10.research_completion": ratio(self.research, self.variant.target),
            "map12.v10.min_food": valid(self.min_food),
            "map12.v10.idle_slots": valid(self.idle_slots),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：既做过维持生存的劳动，也做过研究。"""

        return (
            any(plan["forage"] or plan["repair"] for plan in self.plans)
            and any(plan["research"] for plan in self.plans)
        )


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：按“缺口优先”逐日排班（食物/站体一旦将见底就补，其余做研究）。"""

    variant = VARIANTS[environment_seed]
    food = variant.food
    integrity = variant.integrity
    research = 0
    actions: list[dict[str, Any]] = []
    for _day in range(DAYS):
        slots = variant.slots
        plan: list[str] = []
        while slots > 0 and food - variant.consumption + 2 * plan.count("forage") <= 2:
            plan.append("forage")
            slots -= 1
        while slots > 0 and integrity - variant.decay + 2 * plan.count("repair") <= 2:
            plan.append("repair")
            slots -= 1
        plan.extend(["research"] * slots)
        actions.append({"tool": "assign", "plan": plan})
        food += plan.count("forage") * 2 - variant.consumption
        integrity += plan.count("repair") * 2 - variant.decay
        research += plan.count("research")
    return actions


__all__ = [
    "DAYS",
    "Map12V10Environment",
    "TASKS",
    "VARIANTS",
    "Variant12",
    "oracle_actions",
]
