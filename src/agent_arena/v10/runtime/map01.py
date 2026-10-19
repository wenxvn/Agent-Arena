"""MAP-01 V10｜破损的曙光号：氧气余量/断供容错/供电参数的实例化（DCR-V10-31）。

V8 的 MAP-01 `_reset_state` 忽略 seed：氧气储备恒 18、断供容错恒 3 tick、
公开配电容量恒 6/3/2/2。V10 把这些**实例参数**按 seed 实例化（规则逻辑、动作契约、
成功条件不变）：

| seed | label | 氧气储备 | 断供容错 | 容量/固定/供氧/维修臂 |
|---:|---|---:|---:|---|
| 0 | base | 18 | 3 | 6 / 3 / 2 / 2 |
| 1 | lean_reserve | 10 | 3 | 6 / 3 / 2 / 2 |
| 2 | tolerant_outage | 18 | 4 | 5 / 2 / 3 / 3 |
| 3 | tight_reserve | 12 | 3 | 7 / 4 / 2 / 2 |

四个实例都允许同一条 15 动作方案（Oracle 4/4）；差异在**容错余量**与公开配电参数，
所以“浪费 tick 的策略”会在不同实例上以不同方式失败。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.maps.map01 import Map01Environment
from agent_arena.worlds.scenario_v8.models import V8Action


@dataclass(frozen=True)
class LifeSupportVariant:
    label: str
    oxygen_reserve: int
    off_limit: int
    capacity: int
    fixed_load: int
    support_load: int
    arm_load: int


VARIANTS: dict[int, LifeSupportVariant] = {
    0: LifeSupportVariant("base", 18, 3, 6, 3, 2, 2),
    1: LifeSupportVariant("lean_reserve", 10, 3, 6, 3, 2, 2),
    2: LifeSupportVariant("tolerant_outage", 18, 4, 5, 2, 3, 3),
    3: LifeSupportVariant("tight_reserve", 12, 3, 7, 4, 2, 2),
}


class Map01V10Environment(V10Map, Map01Environment):
    map_id = "MAP-01"
    title = "破损的曙光号"
    world = "spaceship"
    level = "简单"
    RULE_VERSION = "v10.map01.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map01.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map01.v10.mission_success",
            "primary",
            "higher",
            "修复船壳、恢复供氧与主电源、完成气闸检查并在舰桥确认",
            "1",
            censored_rule="截尾 → CENSORED；氧气/断供终局 → VALID 0",
        ),
        MetricSpec(
            "map01.v10.dependency_satisfaction_rate",
            "secondary",
            "higher",
            "已满足的依赖前置数 / 6（供氧→取件→断电→修壳→母线→气闸→确认）",
            "6",
        ),
        MetricSpec(
            "map01.v10.longest_oxygen_outage_ticks",
            "guardrail",
            "lower",
            "最长断供连续 tick",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map01.v10.oxygen_guardrail_violations",
            "guardrail",
            "lower",
            "因氧气耗尽/断供超限导致的终局（1 表示失败）",
            "1",
        ),
        MetricSpec(
            "map01.v10.dependency_violations",
            "guardrail",
            "lower",
            "违反依赖顺序的动作次数",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map01.v10.completion_ticks",
            "diagnostic",
            "lower",
            "成功时的完成 tick",
            "成功局（1）",
            zero_denominator="未成功 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        variant = VARIANTS[self.environment_seed]
        Map01Environment._reset_state(self, seed)
        self.oxygen_reserve = variant.oxygen_reserve
        self.oxygen_off_limit = variant.off_limit
        self.capacity = variant.capacity
        self.fixed_load = variant.fixed_load
        self.support_load = variant.support_load
        self.arm_load = variant.arm_load

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "label": variant.label,
            "oxygen_reserve": variant.oxygen_reserve,
            "off_limit": variant.off_limit,
            "loads": {
                "capacity": variant.capacity,
                "fixed": variant.fixed_load,
                "support": variant.support_load,
                "arm": variant.arm_load,
            },
        }

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"life_support": variant.label, "off_limit": variant.off_limit}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "舰内拓扑：B（舰桥）—H（中枢）—W（船壳/配电）、H—P（反应堆）、H—A（气闸）；"
            "W—P 服务通道只在船壳修补后才能通行。",
            "供氧继电器可在 B/H 启动供氧；启动后若把配电切到维修臂，供氧会中断，"
            "断供期间氧气储备每 tick 递减，超过容错上限立即失败。",
            "修补船壳的顺序：先取 patch_kit（需供氧稳定）→ 在 W 把配电切到维修臂 → "
            "patch 船壳 → 切回供氧。",
            "母线重置必须在船壳修补后；气闸压力测试要求供氧与母线同时在线；"
            "最后回 B 在舰桥确认。",
            "公开配电参数（容量/固定负载/供氧/维修臂）见 inspect(power_diagram)；"
            "本实例的氧气储备与断供容错以 Observation 的 oxygen_reserve 与规则为准。",
        )

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        if action.tool == "inspect" and action.target == "power_diagram" and self.node == "H":
            return (
                f"DIAGRAM:capacity={self.capacity},fixed={self.fixed_load},"
                f"support={self.support_load},arm={self.arm_load}"
            )
        return Map01Environment._apply(self, action)

    def _after_tick(self) -> None:
        if self.oxygen_output:
            self.oxygen_off_ticks = 0
            self.current_outage = 0
            return
        self.oxygen_reserve -= 1
        self.oxygen_off_ticks += 1
        self.current_outage += 1
        self.max_outage = max(self.max_outage, self.current_outage)
        if self.oxygen_reserve <= 0:
            self._fail("OXYGEN_RESERVE_EXHAUSTED")
        elif self.oxygen_off_ticks > self.oxygen_off_limit:
            self._fail("OXYGEN_SUPPLY_INTERRUPTION_LIMIT")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map01Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "oxygen_off_limit": self.oxygen_off_limit,
                "capacity": self.capacity,
                "fixed_load": self.fixed_load,
                "support_load": self.support_load,
                "arm_load": self.arm_load,
                "max_outage": self.max_outage,
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        completed = sum(1 for done in self.dependencies.values() if done)
        return {
            "map01.v10.mission_success": success,
            "map01.v10.dependency_satisfaction_rate": valid(
                round(completed / len(self.REQUIRED_DEPENDENCIES), 6)
            ),
            "map01.v10.longest_oxygen_outage_ticks": valid(self.max_outage),
            "map01.v10.oxygen_guardrail_violations": valid(
                int(
                    self.terminal_reason
                    in {"OXYGEN_RESERVE_EXHAUSTED", "OXYGEN_SUPPLY_INTERRUPTION_LIMIT"}
                )
            ),
            "map01.v10.dependency_violations": valid(self.violations.get("dependency", 0)),
            "map01.v10.completion_ticks": (
                valid(self.tick_count) if self.is_success else not_applicable("未成功")
            ),
        }

    def mechanism_triggered(self) -> bool:
        """互斥供电链：取件→断电切臂→修壳→母线，四步都真实发生。"""

        keys = (
            "oxygen_on_to_patch_pickup",
            "patch_hold_to_route_arm",
            "arm_on_to_hull_patch",
            "hull_intact_to_bus_reset",
        )
        return all(self.dependencies.get(key) for key in keys)


__all__ = ["LifeSupportVariant", "Map01V10Environment", "VARIANTS"]
