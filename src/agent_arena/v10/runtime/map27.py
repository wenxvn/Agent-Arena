"""MAP-27 V10｜月球车多目标协调：电量/货舱/氧气的实例化（DCR-V10-30）。

V8 的 MAP-27 `_reset_state` 忽略 seed：电量容量 14、货舱 2、充电增益 4、余氧 18 恒定。
V10 把这四个**公开数值**按 seed 实例化（规则逻辑、动作契约、成功条件不变）：

| seed | label | 电量 | 货舱 | 充电增益 | 余氧 | 可达方案 |
|---:|---|---:|---:|---:|---:|---|
| 0 | base | 14 | 2 | 4 | 18 | relay-first / stabilize-first |
| 1 | tight_battery | 12 | 2 | 4 | 16 | 仅 stabilize-first |
| 2 | heavy_cargo | 16 | 3 | 4 | 18 | 两条都可 |
| 3 | fast_charge | 12 | 2 | 6 | 20 | 仅 stabilize-first |

每个实例都有已验证的 Oracle（`baselines/map27.py`），电量收紧后 relay-first 会
`VEHICLE_STRANDED`——这是**实例难度**的真实变化，不是规则变化。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.maps.map27 import Map27Environment


@dataclass(frozen=True)
class VehicleVariant:
    label: str
    battery_capacity: int
    cargo_capacity: int
    charge_gain: int
    oxygen: int


VARIANTS: dict[int, VehicleVariant] = {
    0: VehicleVariant("base", 14, 2, 4, 18),
    1: VehicleVariant("tight_battery", 12, 2, 4, 16),
    2: VehicleVariant("heavy_cargo", 16, 3, 4, 18),
    3: VehicleVariant("fast_charge", 12, 2, 6, 20),
}


class Map27V10Environment(V10Map, Map27Environment):
    map_id = "MAP-27"
    title = "月球车"
    world = "lunar"
    level = "困难"
    RULE_VERSION = "v10.map27.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map27.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map27.v10.mission_success",
            "primary",
            "higher",
            "在 B 提交时样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0",
            "1",
            censored_rule="截尾 → CENSORED；任一目标缺失 → VALID 0",
        ),
        MetricSpec(
            "map27.v10.joint_task_completion_rate",
            "secondary",
            "higher",
            "（中继在线 + 伤员撤离 + 样本封存）/ 3",
            "3",
            censored_rule="部分进度保持 VALID；未发生的终点事件为 CENSORED",
        ),
        MetricSpec(
            "map27.v10.completion_ticks",
            "diagnostic",
            "lower",
            "成功时的完成 tick",
            "成功局（1）",
            zero_denominator="未成功 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map27.v10.resource_conflicts",
            "guardrail",
            "lower",
            "电量/货舱冲突导致的拒绝次数",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map27.v10.cargo_errors",
            "guardrail",
            "lower",
            "货舱容量不足导致的装载失败次数",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map27.v10.blackout_ticks",
            "diagnostic",
            "lower",
            "中继离线期间的累计 tick",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map27.v10.charge_cells_used",
            "diagnostic",
            "none",
            "使用的充电桩次数",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        variant = VARIANTS[self.environment_seed]
        # 实例化公开数值（规则代码通过 self.X 读取）
        self.BATTERY_CAPACITY = variant.battery_capacity
        self.CARGO_CAPACITY = variant.cargo_capacity
        self.CHARGE_GAIN = variant.charge_gain
        Map27Environment._reset_state(self, seed)
        self.battery = variant.battery_capacity
        self.oxygen = variant.oxygen

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "label": variant.label,
            "battery_capacity": variant.battery_capacity,
            "cargo_capacity": variant.cargo_capacity,
            "charge_gain": variant.charge_gain,
            "oxygen": variant.oxygen,
        }

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "reference_critical_path": self.REFERENCE_CRITICAL_PATH,
            "vehicle": variant.label,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "B 是基地（提单与样本容器）、S 是中继站补给点与唯一充电桩、R 是中继塔、"
            "P 是采样点、E 是伤员位置；每条通道的耗时 = 电量消耗 = 氧气消耗。",
            "月球车有电量上限、货舱上限与余氧上限（数值见 Observation 的 "
            "battery_capacity / cargo_capacity / oxygen）；电量不足以进入下一段会抛锚。",
            "装载会占货舱槽位；货舱满时装载或充电会被拒绝并记一次冲突。",
            "在 S 可消耗充电桩充一次电（增益见实例）；充电桩数量见 Observation。",
            "中继塔需要 relay_repair_kit 才能修复；伤员需要 medical_kit 现场稳定后，"
            "在**中继在线**时才能远程撤离；样本容器需带到 P 采样封存。",
            "回到 B 提交才算完成：样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0。",
        )

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map27Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "battery_capacity": self.BATTERY_CAPACITY,
                "cargo_capacity": self.CARGO_CAPACITY,
                "charge_gain": self.CHARGE_GAIN,
                "oxygen_capacity": VARIANTS[self.environment_seed].oxygen,
                "blackout_ticks": self.blackout_ticks,
                "charge_cells_used": self.charge_cells_used,
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        completed = sum(
            (
                self.relay_state == "ONLINE",
                self.survivor_state == "RESCUED",
                self.sample_state == "SEALED",
            )
        )
        return {
            "map27.v10.mission_success": success,
            "map27.v10.joint_task_completion_rate": valid(round(completed / 3, 6)),
            "map27.v10.completion_ticks": (
                valid(self.tick_count) if self.is_success else not_applicable("未成功")
            ),
            "map27.v10.resource_conflicts": valid(self.resource_conflict_errors),
            "map27.v10.cargo_errors": valid(self.cargo_errors),
            "map27.v10.blackout_ticks": valid(self.blackout_ticks),
            "map27.v10.charge_cells_used": valid(self.charge_cells_used),
        }

    def mechanism_triggered(self) -> bool:
        """多目标协调机制：中继上线、伤员撤离、样本封存三者都达成。"""

        return (
            self.relay_state == "ONLINE"
            and self.survivor_state == "RESCUED"
            and self.sample_state == "SEALED"
        )


__all__ = ["Map27V10Environment", "VARIANTS", "VehicleVariant"]
