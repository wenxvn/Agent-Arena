"""MAP-25 V10｜第一次出舱：起始位置与氧气预算的实例化（DCR-V10-33）。

V8 的 MAP-25 `_reset_state` 忽略 seed：起始恒在 H、氧气恒 12。V10 把这两个**实例参数**
按 seed 实例化（规则逻辑、动作契约、成功条件不变）：

| seed | label | 起始位置 | 氧气 |
|---:|---|---|---:|
| 0 | base | H | 12 |
| 1 | suited_start | T（装备间） | 12 |
| 2 | lean_oxygen | H | 10 |
| 3 | suited_lean | T | 10 |

起始在装备间会省掉一次移动；氧气收紧到 10 时，出舱后的每个动作都更贵。
四个实例都有已验证的 Oracle（`baselines/map25.py`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.maps.map25 import REQUIRED_STEPS, Map25Environment


@dataclass(frozen=True)
class EvaVariant:
    label: str
    start: str
    oxygen: int


VARIANTS: dict[int, EvaVariant] = {
    0: EvaVariant("base", "H", 12),
    1: EvaVariant("suited_start", "T", 12),
    2: EvaVariant("lean_oxygen", "H", 10),
    3: EvaVariant("suited_lean", "T", 10),
}


class Map25V10Environment(V10Map, Map25Environment):
    map_id = "MAP-25"
    title = "第一次出舱"
    world = "lunar"
    level = "简单"
    RULE_VERSION = "v10.map25.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map25.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map25.v10.mission_success",
            "primary",
            "higher",
            "按依赖顺序完成准备、出舱、诊断与维修并安全返舱",
            "1",
            censored_rule="截尾 → CENSORED；装备/顺序/氧气终局 → VALID 0",
        ),
        MetricSpec(
            "map25.v10.required_check_coverage",
            "secondary",
            "higher",
            "已完成的必需步骤 / 7",
            "7",
        ),
        MetricSpec(
            "map25.v10.dependency_order_correctness",
            "secondary",
            "higher",
            "前置满足的必需步骤 / 已尝试必需步骤",
            "已尝试的必需步骤",
            zero_denominator="未尝试任何必需步骤 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map25.v10.unsafe_eva_attempts",
            "guardrail",
            "lower",
            "未穿服或未挂绳的出舱尝试次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map25.v10.oxygen_shortfall",
            "guardrail",
            "lower",
            "因氧气耗尽终局（1 表示失败）",
            "1",
        ),
        MetricSpec(
            "map25.v10.completion_ticks",
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
        Map25Environment._reset_state(self, seed)
        variant = VARIANTS[self.environment_seed]
        self.node = variant.start
        self.oxygen = variant.oxygen

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"label": variant.label, "start": variant.start, "oxygen": variant.oxygen}

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"eva": variant.label, "oxygen": variant.oxygen}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "H（居住舱）—T（装备间）—A（气闸）为舱内通路；A 之外是阵列 S。",
            "在 T 穿 EVA 服、取诊断单元与扳手并检查装备；在 A 挂安全绳；"
            "排压后才能出舱（未穿服/未挂绳/未排压都会失败）。",
            "在 S 先检查阵列、再用诊断单元诊断，维修必须带齐诊断单元与扳手并给出诊断码。",
            "维修后依次返回 A、增压、经 T 回 H；回到 H 且维修完成才算成功。",
            "氧气只在舱外消耗（出舱、检查、诊断、维修、返舱各计费），"
            "本实例的起始位置与氧气预算见 Observation。",
        )

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map25Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "start": VARIANTS[self.environment_seed].start,
                "oxygen_capacity": VARIANTS[self.environment_seed].oxygen,
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        done = len(self.required_done)
        attempts = self.required_attempted
        order: MValue = (
            valid(round(self.required_correct / attempts, 6))
            if attempts
            else not_applicable("未尝试必需步骤")
        )
        return {
            "map25.v10.mission_success": success,
            "map25.v10.required_check_coverage": valid(
                round(done / len(REQUIRED_STEPS), 6)
            ),
            "map25.v10.dependency_order_correctness": order,
            "map25.v10.unsafe_eva_attempts": valid(
                self.counters.get("UNSUITED_EVA", 0)
                + self.counters.get("UNSAFE_UNTETHERED_EVA", 0)
            ),
            "map25.v10.oxygen_shortfall": valid(
                int(self.terminal_reason == "OXYGEN_DEPLETED")
            ),
            "map25.v10.completion_ticks": (
                valid(self.tick_count) if self.is_success else not_applicable("未成功")
            ),
        }

    def mechanism_triggered(self) -> bool:
        """依赖顺序机制：诊断与维修都发生，且维修带齐两件工具。"""

        return self.diagnosed and self.repaired


__all__ = ["EvaVariant", "Map25V10Environment", "VARIANTS"]
