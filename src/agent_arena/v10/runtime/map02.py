"""MAP-02 V10｜事件触发的双目标重排（DCR-V10-29，原生 seed 化）。

V8 的 MAP-02 `_reset_state` 忽略 seed：泄漏恒在第 4 个动作后出现、扩散窗口 2 tick、
乘员压力 8 tick、全局 deadline 20 tick。V10 把这些**实例参数**按 seed 实例化
（规则逻辑、动作契约、成功条件不变）：

| seed | label | 泄漏触发动作序 | 扩散窗口 | 乘员压力 | deadline |
|---:|---|---:|---:|---:|---:|
| 0 | base | 4 | 2 | 8 | 20 |
| 1 | early_leak_long_spread | 3 | 3 | 7 | 20 |
| 2 | tight_deadline | 4 | 2 | 6 | 16 |
| 3 | late_leak_generous | 6 | 2 | 10 | 24 |

四个实例都允许同一条 9 动作的双目标方案（Oracle 4/4，见 `baselines/map02.py`）。
`global_deadline` 与 `leak_trigger_index` 只通过事件时序与最终时限改变难度。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.maps.map02 import Map02Environment


@dataclass(frozen=True)
class EventVariant:
    label: str
    leak_trigger_index: int
    spread_ticks: int
    crew_pressure_ticks: int
    global_deadline: int


VARIANTS: dict[int, EventVariant] = {
    0: EventVariant("base", 4, 2, 8, 20),
    1: EventVariant("early_leak_long_spread", 3, 3, 7, 20),
    2: EventVariant("tight_deadline", 4, 2, 6, 16),
    3: EventVariant("late_leak_generous", 6, 2, 10, 24),
}


class Map02V10Environment(V10Map, Map02Environment):
    map_id = "MAP-02"
    title = "双重警报"
    world = "spaceship"
    level = "中等"
    RULE_VERSION = "v10.map02.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map02.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map02.v10.mission_success",
            "primary",
            "higher",
            "泄漏后同时保住导航核心并把乘员送入逃生舱",
            "1",
            censored_rule="截尾 → CENSORED；泄漏扩散/压力归零 → VALID 0",
        ),
        MetricSpec(
            "map02.v10.event_response_latency",
            "secondary",
            "lower",
            "泄漏公告后第一个有效动作的延迟 tick",
            "发生泄漏的局（1）",
            zero_denominator="未泄漏 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map02.v10.dual_objective_completion",
            "secondary",
            "higher",
            "（导航核心已固定 + 乘员已在逃生舱）/ 2",
            "2",
        ),
        MetricSpec(
            "map02.v10.stale_plan_actions_after_leak",
            "guardrail",
            "lower",
            "泄漏后仍按旧计划前往受威胁区域的动作数",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map02.v10.crew_decompression",
            "guardrail",
            "lower",
            "乘员压力是否归零终局（1 表示失败）",
            "1",
        ),
        MetricSpec(
            "map02.v10.completion_ticks",
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
        Map02Environment._reset_state(self, seed)
        variant = VARIANTS[self.environment_seed]
        self.leak_trigger_index = variant.leak_trigger_index
        self.spread_ticks = variant.spread_ticks
        self.crew_pressure_ticks = variant.crew_pressure_ticks
        self.global_deadline = variant.global_deadline

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "label": variant.label,
            "leak_trigger_index": variant.leak_trigger_index,
            "spread_ticks": variant.spread_ticks,
            "crew_pressure_ticks": variant.crew_pressure_ticks,
            "global_deadline": variant.global_deadline,
        }

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"event_order_seed": self.environment_seed, "deadline": variant.global_deadline}

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        payload = Map02Environment._public(self)
        payload["goal"] = (
            "导航核心故障与舱段泄漏会按事件顺序出现；泄漏后同时保住导航核心、"
            "把乘员送进逃生舱，并在时限内完成。"
        )
        return payload

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map02Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "leak_trigger_index": self.leak_trigger_index,
                "global_deadline": self.global_deadline,
                "first_meaningful_after_leak": self.first_meaningful_after_leak,
                "leak_announced_tick": self.leak_announced_tick,
                "crew_decompression": int(self.terminal_reason == "CREW_PRESSURE_LOST"),
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        if self.leak_announced_tick is None or self.first_meaningful_after_leak is None:
            latency: MValue = censored("截尾") if running else not_applicable("未发生有效响应")
        else:
            latency = valid(
                max(0, self.first_meaningful_after_leak - self.leak_announced_tick)
            )
        objectives = int(self.nav_core_secured) + int(self.crew_in_escape_pod)
        completion: MValue = (
            valid(self.tick_count)
            if self.is_success
            else (not_applicable("未成功"))
        )
        return {
            "map02.v10.mission_success": success,
            "map02.v10.event_response_latency": latency,
            "map02.v10.dual_objective_completion": valid(round(objectives / 2, 6)),
            "map02.v10.stale_plan_actions_after_leak": valid(self.stale_actions_after_leak),
            "map02.v10.crew_decompression": valid(
                int(self.terminal_reason == "CREW_PRESSURE_LOST")
            ),
            "map02.v10.completion_ticks": completion,
        }

    def mechanism_triggered(self) -> bool:
        """事件重排机制：泄漏已出现且 Agent 在泄漏后做出过有效动作。"""

        return self.leak_active and self.first_meaningful_after_leak is not None


__all__ = ["EventVariant", "Map02V10Environment", "VARIANTS"]
