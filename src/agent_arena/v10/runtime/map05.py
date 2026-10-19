"""MAP-05 V10｜三束信号：共享供电下的三窗口排程（DCR-V10-27，原生 seed 化）。

V8 的 MAP-05 是一个固定实例（`_reset_state` 忽略 seed）：窗口恒为 R[15,18]/B[22,25]/W[29,35]、
通道耗时恒为 1/2/3。V10 把它参数化为 4 个预登记实例，**规则逻辑、动作契约与成功条件不变**，
只改变公开的窗口时刻与通道耗时：

| seed | R 窗口 | B 窗口 | W 窗口 | 通道耗时 C-R/C-B/C-W |
|---:|---|---|---|---|
| 0 | 15–18 | 22–25 | 29–35 | 1 / 2 / 3 |
| 1 | 9–12 | 16–20 | 24–30 | 1 / 2 / 3 |
| 2 | 18–21 | 24–27 | 30–34 | 2 / 1 / 3 |
| 3 | 12–16 | 20–24 | 26–32 | 1 / 3 / 2 |

每个实例都用同一份公开排程可行（Oracle 4/4，见 `baselines/map05.py`）。供电仍然一次只能
指向一个塔，切换只能在 C 进行——这是本图“单路共享供电”的核心机制。
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
from agent_arena.worlds.scenario_v8.maps.map05 import Map05Environment
from agent_arena.worlds.scenario_v8.models import V8Action

STATIONS = ("R", "B", "W")


@dataclass(frozen=True)
class WindowVariant:
    label: str
    windows: dict[str, tuple[int, int]]
    edge_cost: dict[str, int]
    reference_completion_tick: int


#: 4 个预登记实例：窗口时刻、通道耗时与参考完成 tick 都不同。
VARIANTS: dict[int, WindowVariant] = {
    0: WindowVariant(
        "base",
        {"R": (15, 18), "B": (22, 25), "W": (29, 35)},
        {"C_R": 1, "C_B": 2, "C_W": 3},
        31,
    ),
    1: WindowVariant(
        "early_windows",
        {"R": (9, 12), "B": (16, 20), "W": (24, 30)},
        {"C_R": 1, "C_B": 2, "C_W": 3},
        25,
    ),
    2: WindowVariant(
        "late_windows_swapped_cost",
        {"R": (18, 21), "B": (24, 27), "W": (30, 34)},
        {"C_R": 2, "C_B": 1, "C_W": 3},
        33,
    ),
    3: WindowVariant(
        "wide_middle_short_outbound",
        {"R": (12, 16), "B": (20, 24), "W": (26, 32)},
        {"C_R": 1, "C_B": 3, "C_W": 2},
        30,
    ),
}


class Map05V10Environment(V10Map, Map05Environment):
    map_id = "MAP-05"
    title = "三束信号"
    world = "lighthouse"
    level = "中等"
    RULE_VERSION = "v10.map05.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map05.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map05.v10.mission_success",
            "primary",
            "higher",
            "三束信号都在各自窗口内发出",
            "1",
            censored_rule="截尾 → CENSORED；窗口错过 → VALID 0",
        ),
        MetricSpec(
            "map05.v10.window_slack_ticks",
            "secondary",
            "higher",
            "min(窗口结束 tick − 该塔实际发送 tick)",
            "已发送信号的塔（1–3）",
            zero_denominator="未发出任何信号 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(-40.0, 40.0),
        ),
        MetricSpec(
            "map05.v10.effective_signals",
            "secondary",
            "higher",
            "窗口内发出的信号数 / 3",
            "3",
        ),
        MetricSpec(
            "map05.v10.power_switches",
            "diagnostic",
            "none",
            "switch_power 次数（共享供电的调度成本）",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map05.v10.missed_windows",
            "guardrail",
            "lower",
            "窗口结束仍未发出的塔数",
            "—",
            unit="count",
            valid_range=(0.0, 3.0),
        ),
        MetricSpec(
            "map05.v10.idle_ticks",
            "diagnostic",
            "lower",
            "已校准但仍等待窗口的 tick 数",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        variant = VARIANTS[self.environment_seed]
        # 实例化公开参数（规则代码通过 self.WINDOWS / self.EDGE_COST 读取）
        self.WINDOWS = dict(variant.windows)
        self.EDGE_COST = dict(variant.edge_cost)
        self.power_switches = 0
        self.transmit_tick: dict[str, int | None] = {station: None for station in STATIONS}
        Map05Environment._reset_state(self, seed)

    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "label": variant.label,
            "windows": {name: list(window) for name, window in variant.windows.items()},
            "edge_cost": dict(variant.edge_cost),
        }

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {"reference_completion_tick": variant.reference_completion_tick}

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        payload = Map05Environment._public(self)
        windows = "、".join(
            f"{name}[{window[0]},{window[1]}]"
            for name, window in sorted(self.WINDOWS.items())
        )
        payload["goal"] = f"在 {windows} 三个窗口内各发出一束信号。"
        return payload

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        if action.tool == "switch_power":
            target = action.station
            if self.node == "C" and target in self.WINDOWS and target != self.power_target:
                self.power_switches += 1
        result = Map05Environment._apply(self, action)
        if result == "SIGNAL_SENT" and self._pending_signal is not None:
            # 信号在下一 tick 结算；先记下结算后的 tick，供指标使用
            self.transmit_tick[self._pending_signal] = self.tick_count + 1
        return result

    def _after_tick(self) -> None:
        Map05Environment._after_tick(self)
        for station, transmitted in self.transmitted.items():
            if transmitted and self.transmit_tick[station] is None:
                self.transmit_tick[station] = self.tick_count

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(Map05Environment.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "power_switches": self.power_switches,
                "transmit_tick": dict(self.transmit_tick),
                "windows": {name: list(window) for name, window in self.WINDOWS.items()},
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(1 if self.is_success else 0)
        sent = [station for station, done in self.transmitted.items() if done]
        ticks = [self.transmit_tick[station] for station in sent]
        if not sent:
            slack: MValue = censored("截尾") if running else not_applicable("未发出任何信号")
        elif any(tick is None for tick in ticks):
            slack = censored("截尾")
        else:
            slack = valid(
                min(
                    self.WINDOWS[station][1] - int(self.transmit_tick[station] or 0)
                    for station in sent
                )
            )
        return {
            "map05.v10.mission_success": success,
            "map05.v10.window_slack_ticks": slack,
            "map05.v10.effective_signals": (
                censored("截尾") if running else valid(round(len(sent) / 3, 6))
            ),
            "map05.v10.power_switches": valid(self.power_switches),
            "map05.v10.missed_windows": valid(self.missed_windows),
            "map05.v10.idle_ticks": valid(self.idle_ticks),
        }

    def mechanism_triggered(self) -> bool:
        """共享供电机制：至少切换 1 次电，且至少 1 束信号落在窗口内。"""

        return self.power_switches >= 1 and any(self.transmitted.values())


__all__ = ["Map05V10Environment", "VARIANTS", "WindowVariant"]
