"""MAP-17 V10｜瓶颈下的四车多目标排程：服务阈值与时限的实例化（DCR-V10-34）。

V8 的 MAP-17 把 `SERVICE_THRESHOLD=8` 与 `HORIZON=12` 写成模块常量，`_reset_state` 忽略 seed。
V10 只把这两个**公开验收参数**按 seed 实例化（规则逻辑、动作契约、需求表与拓扑不变）：

| seed | label | 服务阈值 | 时限 |
|---:|---|---:|---:|
| 0 | base | 8 | 12 |
| 1 | stricter_9 | 9 | 12 |
| 2 | perfect_10 | 10 | 12 |
| 3 | extended_14 | 8 | 14 |

同一份 12-tick 时刻表在四个实例上都能送满 10/10，因此四个实例都可解；
差异在**成功门槛**与**时限余量**（阈值 10 要求零损失，时限 14 放宽后允许更慢的排程）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.maps.map17 import Map17Environment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status


@dataclass(frozen=True)
class ScheduleVariant:
    label: str
    threshold: int
    horizon: int


VARIANTS: dict[int, ScheduleVariant] = {
    0: ScheduleVariant("base", 8, 12),
    1: ScheduleVariant("stricter_9", 9, 12),
    2: ScheduleVariant("perfect_10", 10, 12),
    3: ScheduleVariant("extended_14", 8, 14),
}


class Map17V10Environment(V10Map, Map17Environment):
    map_id = "MAP-17"
    title = "四车排程"
    world = "subway"
    level = "中等"
    RULE_VERSION = "v10.map17.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map17.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map17.v10.mission_success",
            "primary",
            "higher",
            "在时限内送达人数达到该实例的服务阈值",
            "1",
            censored_rule="截尾 → CENSORED；到时限未达标 → VALID 0",
        ),
        MetricSpec(
            "map17.v10.service_rate",
            "secondary",
            "higher",
            "已送达人次 / 10",
            "10",
        ),
        MetricSpec(
            "map17.v10.threshold_margin",
            "secondary",
            "higher",
            "送达人次 − 本实例服务阈值（正数表示超过门槛）",
            "1",
            censored_rule="截尾 → CENSORED",
            unit="passengers",
            valid_range=(-10.0, 10.0),
        ),
        MetricSpec(
            "map17.v10.wait_person_ticks",
            "guardrail",
            "lower",
            "累计候车人·tick",
            "—",
            unit="person_ticks",
            valid_range=(0.0, 500.0),
        ),
        MetricSpec(
            "map17.v10.refused_frames",
            "guardrail",
            "lower",
            "被环境整帧拒绝的时刻表数（容量/冲突/时刻不符）",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map17.v10.energy_used",
            "diagnostic",
            "lower",
            "已消耗的线路能量",
            "—",
            unit="energy",
            valid_range=(0.0, 500.0),
        ),
        MetricSpec(
            "map17.v10.completion_ticks",
            "diagnostic",
            "lower",
            "成功时的完成 tick",
            "成功局（1）",
            zero_denominator="未成功 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        Map17Environment._reset_state(self, seed)
        variant = VARIANTS[self.environment_seed]
        self.service_threshold = variant.threshold
        self.horizon = variant.horizon
        self.refused_frames = 0
        self.switch_ops = 0

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"label": variant.label, "threshold": variant.threshold, "horizon": variant.horizon}

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"schedule": variant.label, "threshold": variant.threshold}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "环线 A—B—C—D 与支线 B—E—F 共用 B 站咽喉；每段每 tick 只能过 1 列车。",
            "每 tick 提交一整行时刻表：set_timetable(tick, operations)。"
            "operations 以列车 id 为键，每项含 op"
            "（stop/release/detour/switch_line/delay）与目标/上车人数。",
            "上车（board）必须对应列车的 task 路线与需求表 demand_matrix；"
            "站台/区段容量或同段冲突会让整帧被拒（tick 不前进）。",
            "需求表共 10 人；到时限时送达人数达到本实例的服务阈值即成功。",
            "公开验收参数（服务阈值与时限）见 goal 与 ticks_remaining。",
        )

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        result = Map17Environment._apply(self, action)
        if action.tool != "set_timetable":
            return result
        if self._rejected:
            # 被整帧拒绝的时刻表不推进 tick
            self.refused_frames += 1
        elif any(
            operation.get("op") == "switch_line"
            for operation in (action.operations or {}).values()
        ):
            self.switch_ops += 1
        return result

    def _public(self) -> dict[str, Any]:
        payload = Map17Environment._public(self)
        payload["ticks_remaining"] = max(0, self.horizon - self.tick_count)
        total = self.delivered_total + sum(self.waiting.values())
        payload["goal"] = (
            f"在 {self.horizon} tick 内运送至少 {self.service_threshold}/{total} "
            "名乘客，并自行权衡服务率、等待与能耗。"
        )
        return payload

    def _after_tick(self) -> None:
        if self.status is not V8Status.RUNNING:
            return
        if self._rejected or self.tick_count < self.horizon:
            return
        if self.delivered_total >= self.service_threshold:
            self._succeed("DEMAND_THRESHOLD_MET")
        else:
            self._fail("DEADLINE_SERVICE_BELOW_THRESHOLD")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map17Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "service_threshold": self.service_threshold,
                "horizon": self.horizon,
                "refused_frames": self.refused_frames,
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        delivered = self.delivered_total
        return {
            "map17.v10.mission_success": success,
            "map17.v10.service_rate": valid(round(delivered / 10, 6)),
            "map17.v10.threshold_margin": (
                censored("截尾") if running else valid(delivered - self.service_threshold)
            ),
            "map17.v10.wait_person_ticks": valid(self.wait_person_ticks),
            "map17.v10.refused_frames": valid(self.refused_frames),
            "map17.v10.energy_used": valid(self.energy_used),
            "map17.v10.completion_ticks": (
                valid(self.tick_count) if self.is_success else not_applicable("未成功")
            ),
        }

    def mechanism_triggered(self) -> bool:
        """瓶颈共用机制：至少有一次被接受的换线排程，且送达人数达到阈值。"""

        return self.switch_ops >= 1 and self.delivered_total >= self.service_threshold


__all__ = ["Map17V10Environment", "ScheduleVariant", "VARIANTS"]
