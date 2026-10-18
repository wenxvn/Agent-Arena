"""MAP-07 V10｜阀门方向：方向识别 + 水位预测决定成败（DCR-V10-19）。

V9 的证据：公开控制面板后 0/1→1/1，需要检验“是不是只是固定脚本”。V10 的修复：

- **方向随 seed 变化**：阀门开向 ∈ {顺时针, 逆时针}，由 seed 决定且**不公开**；
  面板只公开“转对方向会开阀、转错方向会把阀拧得更紧（进水更快）”这一因果；
- **拧错有代价**：转错方向会让阀口再紧一档（进水速率 +1），并耗 1 tick；
- **水位预测进入成败**：进水在第 3 tick 起按公开的 `inflow_schedule` 上升，
  排水只在阀开时生效；必须在生效时刻前把水位压到安全线下，否则 `FLOODED`；
- 4 个预登记实例：开向、初始水位、进水表、安全线、截止都不同。

指标：`mission_success`（主）+ `final_level` / `wrong_direction_turns` / `time_margin`。
固定脚本（永远转顺时针）在两种开向下只可能命中一半实例，这是本图要保留的区分度。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, not_applicable, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

SAFE_LEVEL = 8
DEADLINE = 10


class Variant07:
    def __init__(
        self,
        label: str,
        open_direction: str,
        initial_level: int,
        inflow: tuple[int, ...],
        drain: int,
    ) -> None:
        self.label = label
        self.open_direction = open_direction
        self.initial_level = initial_level
        self.inflow = inflow
        self.drain = drain


VARIANTS: dict[int, Variant07] = {
    0: Variant07("clockwise_open", "clockwise", 3, (0, 0, 2, 2, 2, 2, 2, 2, 2, 2), 4),
    1: Variant07("counter_open", "counter", 4, (0, 0, 2, 2, 2, 2, 2, 2, 2, 2), 4),
    2: Variant07("clockwise_high_start", "clockwise", 6, (1, 2, 3, 3, 3, 3, 3, 3, 3, 3), 5),
    3: Variant07("counter_slow_inflow", "counter", 3, (0, 0, 2, 2, 2, 2, 2, 2, 2, 2), 5),
}


class Map07V10Environment(V10Map):
    map_id = "MAP-07"
    title = "阀门方向"
    world = "abyss"
    level = "简单"
    RULE_VERSION = "v10.map07.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "inspect": {frozenset({"tool", "target_id"})},
        "read_gauge": {frozenset({"tool"})},
        "turn_valve": {frozenset({"tool", "choice"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "deadline_tick",
            "safe_level",
            "current_level",
            "level_reading",
            "panel_read",
            "valve_state",
            "inflow_schedule",
            "inflow_tightened",
            "wrong_direction_turns",
            "goal",
        }
    )
    PRIMARY_METRIC = "map07.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map07.v10.mission_success",
            "primary",
            "higher",
            "阀已开且截止时水位 ≤ 安全线",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map07.v10.final_level",
            "secondary",
            "lower",
            "截止时的水位",
            "—",
            unit="level",
            valid_range=(0.0, 40.0),
        ),
        MetricSpec(
            "map07.v10.wrong_direction_turns",
            "guardrail",
            "lower",
            "转错方向的次数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map07.v10.time_margin",
            "secondary",
            "higher",
            "开阀后剩余 tick（截止 − 开阀 tick）",
            "开过阀的局（1）",
            zero_denominator="从未开阀 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(-20.0, 20.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.water = self.variant.initial_level
        self.valve_open = False
        self.panel_read = False
        self.reading: int | None = None
        self.tightened = 0
        self.wrong_turns = 0
        self.open_tick: int | None = None
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_level": self.variant.initial_level,
            "inflow_schedule": list(self.variant.inflow),
            "safe_level": SAFE_LEVEL,
            "deadline_tick": DEADLINE,
            "directions": ["clockwise", "counter"],
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"open_direction": self.variant.open_direction, "label": self.variant.label}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "turn_valve(clockwise|counter)：转对方向开阀（此后每 tick 排水），"
            "转错方向会把阀再拧紧一档（进水速率 +1）并耗 1 tick。",
            "inspect(control_panel) 耗 1 tick，公开阀门方向与进水/排水的因果，但不告诉你当前开向。",
            "read_gauge 耗 1 tick，返回精确水位。",
            f"进水从 tick 3 起按 inflow_schedule 上升；水位超过 {SAFE_LEVEL} 即 FLOODED。",
            f"tick {DEADLINE} 结算：阀已开且水位 ≤ {SAFE_LEVEL} 即成功。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "deadline_tick": DEADLINE,
            "safe_level": SAFE_LEVEL,
            "current_level": self.water,
            "level_reading": self.reading,
            "panel_read": self.panel_read,
            "valve_state": "open" if self.valve_open else "closed",
            "inflow_schedule": list(self.variant.inflow),
            "inflow_tightened": self.tightened,
            "wrong_direction_turns": self.wrong_turns,
            "goal": "判断阀门开向、及时开阀排水，在截止前把水位压到安全线下。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        self._cost = 1
        if tool == "inspect":
            if action.target_id != "control_panel":
                return "TARGET_NOT_VISIBLE"
            self.panel_read = True
            return "PANEL_READ"
        if tool == "read_gauge":
            self.reading = self.water
            return f"LEVEL:{self.water}"
        if tool == "turn_valve":
            return self._turn(action)
        if tool == "wait":
            self._cost = int(action.ticks or 1)
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _turn(self, action: V8Action) -> str:
        direction = action.choice
        if direction not in ("clockwise", "counter"):
            return "UNKNOWN_DIRECTION"
        if direction == self.variant.open_direction:
            if not self.valve_open:
                self.valve_open = True
                self.open_tick = self.tick_count + 1
            return "VALVE_OPENED"
        self.wrong_turns += 1
        if not self.valve_open:
            self.tightened += 1
        return "VALVE_TIGHTENED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        index = min(self.tick_count, len(self.variant.inflow) - 1)
        inflow = self.variant.inflow[index] + self.tightened
        drain = self.variant.drain if self.valve_open else 0
        self.water = max(0, self.water + inflow - drain)
        if self.water > SAFE_LEVEL:
            self._fail("FLOODED")
            return
        if self.tick_count >= DEADLINE:
            if self.valve_open and self.water <= SAFE_LEVEL:
                self._succeed("DRAINED_IN_TIME")
            else:
                self._fail("WATER_TOO_HIGH")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "level": self.water,
            "valve_open": self.valve_open,
            "panel_read": self.panel_read,
            "tightened": self.tightened,
            "wrong_turns": self.wrong_turns,
            "open_tick": self.open_tick,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
        margin: MValue = (
            valid(DEADLINE - self.open_tick)
            if self.open_tick is not None
            else not_applicable("从未开阀")
        )
        return {
            "map07.v10.mission_success": success,
            "map07.v10.final_level": valid(self.water),
            "map07.v10.wrong_direction_turns": valid(self.wrong_turns),
            "map07.v10.time_margin": margin,
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：真的依据方向信息开过阀。"""

        return self.valve_open


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：读面板 → 按正确方向开阀 → 等到截止。"""

    variant = VARIANTS[environment_seed]
    actions: list[dict[str, Any]] = [
        {"tool": "inspect", "target_id": "control_panel"},
        {"tool": "turn_valve", "choice": variant.open_direction},
    ]
    actions.extend({"tool": "wait", "ticks": 1} for _ in range(DEADLINE))
    return actions


__all__ = [
    "DEADLINE",
    "Map07V10Environment",
    "SAFE_LEVEL",
    "VARIANTS",
    "Variant07",
    "oracle_actions",
]
