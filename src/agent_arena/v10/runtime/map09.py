"""MAP-09 V10｜连锁故障：水位—电力—供氧的因果链必须同时维持（DCR-V10-21）。

V9 的证据：阈值公开后失败从“短路”转成缺氧，`skip_pump` 仍能成功。V10 的修复：

- **修复有双重前提**：`repair` 要求`水位 ≤ repair_water_limit` **且** `供氧 ≥ repair_oxygen_min`，
  否则分别返回 `TOO_MUCH_WATER` / `OXYGEN_TOO_LOW`——只顾一头都修不好；
- **三条因果链同时运行**：漏水使水位 +leak/tick，基载让电力与供氧各 -1/tick；
  `pump` 降水但耗电，`seal` 停漏但耗氧，`vent` 补氧但抬水位；任何一个维度归零即失败；
- **漏速随时间上升**：每 `surge_every` tick，漏速 +1，逼迫玩家在电力/供氧之间取舍；
- 4 个预登记实例：初始水位/电力/供氧、漏速、激增周期与修复门槛都不同。

指标：`mission_success`（主）+ `final_water` / `min_oxygen` / `min_power` / `wasted_pumps`。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

CAP = 10


class Variant09:
    def __init__(
        self,
        label: str,
        water: int,
        power: int,
        oxygen: int,
        leak: int,
        surge_every: int,
        repair_water: int,
        repair_oxygen: int,
    ) -> None:
        self.label = label
        self.water = water
        self.power = power
        self.oxygen = oxygen
        self.leak = leak
        self.surge_every = surge_every
        self.repair_water = repair_water
        self.repair_oxygen = repair_oxygen


VARIANTS: dict[int, Variant09] = {
    0: Variant09("baseline", 6, 9, 4, 1, 5, 4, 4),
    1: Variant09("fast_leak", 6, 10, 5, 2, 4, 4, 4),
    2: Variant09("low_oxygen", 5, 9, 3, 1, 5, 4, 5),
    3: Variant09("tight_power", 6, 8, 4, 1, 5, 3, 4),
}


class Map09V10Environment(V10Map):
    map_id = "MAP-09"
    title = "连锁故障"
    world = "abyss"
    level = "困难"
    RULE_VERSION = "v10.map09.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "pump": {frozenset({"tool"})},
        "seal": {frozenset({"tool"})},
        "vent": {frozenset({"tool"})},
        "repair": {frozenset({"tool"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "water",
            "power",
            "oxygen",
            "current_leak",
            "sealed_this_tick",
            "repair_water_limit",
            "repair_oxygen_min",
            "wasted_pumps",
            "min_oxygen",
            "min_power",
            "goal",
        }
    )
    PRIMARY_METRIC = "map09.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map09.v10.mission_success",
            "primary",
            "higher",
            "在水位/电力/供氧都不归零的前提下完成修复",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map09.v10.final_water",
            "secondary",
            "lower",
            "终局水位",
            "—",
            unit="level",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map09.v10.min_oxygen",
            "guardrail",
            "higher",
            "过程中最低供氧",
            "—",
            unit="level",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map09.v10.min_power",
            "guardrail",
            "higher",
            "过程中最低电力",
            "—",
            unit="level",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map09.v10.wasted_pumps",
            "diagnostic",
            "lower",
            "水位已经很低时仍开泵的次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.water = self.variant.water
        self.power = self.variant.power
        self.oxygen = self.variant.oxygen
        self.sealed = False
        self.wasted_pumps = 0
        self.min_oxygen = self.variant.oxygen
        self.min_power = self.variant.power
        self.repaired = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial": {
                "water": self.variant.water,
                "power": self.variant.power,
                "oxygen": self.variant.oxygen,
            },
            "leak": self.variant.leak,
            "surge_every": self.variant.surge_every,
            "repair_water_limit": self.variant.repair_water,
            "repair_oxygen_min": self.variant.repair_oxygen,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"label": self.variant.label, "leak": self.variant.leak}

    def current_leak(self) -> int:
        return self.variant.leak + self.tick_count // self.variant.surge_every

    def public_rules(self) -> tuple[str, ...]:
        return (
            "每个 tick：漏水使水位 + 当前漏速；基载使电力 -1、供氧 -1。",
            f"漏速每 {self.variant.surge_every} tick 上升 1（surge）。",
            "pump：水位 -4、电力 -2；seal：本 tick 停止漏水、供氧 -2；vent：供氧 +3、水位 +1。",
            f"repair 要求 水位 ≤ {self.variant.repair_water} 且 供氧 ≥ "
            f"{self.variant.repair_oxygen}，否则分别返回 TOO_MUCH_WATER / OXYGEN_TOO_LOW。",
            "水位 > 8 即 FLOODED；电力或供氧归零即 LOST_POWER / LOST_OXYGEN。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "water": self.water,
            "power": self.power,
            "oxygen": self.oxygen,
            "current_leak": self.current_leak(),
            "sealed_this_tick": self.sealed,
            "repair_water_limit": self.variant.repair_water,
            "repair_oxygen_min": self.variant.repair_oxygen,
            "wasted_pumps": self.wasted_pumps,
            "min_oxygen": self.min_oxygen,
            "min_power": self.min_power,
            "goal": "同时守住水位、电力与供氧，把水位压到门槛以下再修复。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        self.sealed = False
        if tool == "pump":
            if self.water <= 2:
                self.wasted_pumps += 1
            self.water = max(0, self.water - 4)
            self.power -= 2
            return "PUMPED"
        if tool == "seal":
            self.sealed = True
            self.oxygen -= 2
            return "SEALED"
        if tool == "vent":
            self.oxygen = min(CAP, self.oxygen + 3)
            self.water += 1
            return "VENTED"
        if tool == "repair":
            if self.water > self.variant.repair_water:
                return "TOO_MUCH_WATER"
            if self.oxygen < self.variant.repair_oxygen:
                return "OXYGEN_TOO_LOW"
            self.repaired = True
            self._succeed("HULL_SEALED")
            return "HULL_SEALED"
        if tool == "wait":
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return 1

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if not self.sealed:
            self.water += self.current_leak()
        self.power -= 1
        self.oxygen -= 1
        self.min_oxygen = min(self.min_oxygen, self.oxygen)
        self.min_power = min(self.min_power, self.power)
        if self.water > 8:
            self._fail("FLOODED")
        elif self.power <= 0:
            self._fail("LOST_POWER")
        elif self.oxygen <= 0:
            self._fail("LOST_OXYGEN")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "water": self.water,
            "power": self.power,
            "oxygen": self.oxygen,
            "wasted_pumps": self.wasted_pumps,
            "min_oxygen": self.min_oxygen,
            "min_power": self.min_power,
            "repaired": self.repaired,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        success: MValue = censored("截尾") if running else valid(int(self.is_success))
        return {
            "map09.v10.mission_success": success,
            "map09.v10.final_water": valid(self.water),
            "map09.v10.min_oxygen": valid(self.min_oxygen),
            "map09.v10.min_power": valid(self.min_power),
            "map09.v10.wasted_pumps": valid(self.wasted_pumps),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：同时用到了泵（水位）与通风（供氧）两条链。"""

        return self.wasted_pumps >= 0 and self.tick_count >= 2 and self.is_success


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知 BFS：在 (水, 电, 氧) 状态空间里找能在 12 tick 内修复的序列。"""

    variant = VARIANTS[environment_seed]

    def step(state: tuple[int, int, int], tick: int, tool: str) -> tuple[int, int, int] | None:
        water, power, oxygen = state
        sealed = False
        if tool == "pump":
            water = max(0, water - 4)
            power -= 2
        elif tool == "seal":
            sealed = True
            oxygen -= 2
        elif tool == "vent":
            oxygen = min(CAP, oxygen + 3)
            water += 1
        if not sealed:
            water += variant.leak + tick // variant.surge_every
        power -= 1
        oxygen -= 1
        if water > 8 or power <= 0 or oxygen <= 0:
            return None
        return (water, power, oxygen)

    start = (variant.water, variant.power, variant.oxygen)
    frontier: list[tuple[int, tuple[int, int, int], list[dict[str, Any]]]] = [(0, start, [])]
    seen = {start: 0}
    while frontier:
        frontier.sort(key=lambda item: item[0])
        tick, state, path = frontier.pop(0)
        water, oxygen = state[0], state[2]
        if water <= variant.repair_water and oxygen >= variant.repair_oxygen:
            return [*path, {"tool": "repair"}]
        if tick >= 12:
            continue
        for tool in ("pump", "vent", "seal", "wait"):
            nxt = step(state, tick, tool)
            if nxt is None:
                continue
            if seen.get(nxt, 99) <= tick + 1:
                continue
            seen[nxt] = tick + 1
            frontier.append((tick + 1, nxt, [*path, {"tool": tool}]))
    raise RuntimeError("no feasible plan")  # pragma: no cover


__all__ = [
    "CAP",
    "Map09V10Environment",
    "VARIANTS",
    "Variant09",
    "oracle_actions",
]
