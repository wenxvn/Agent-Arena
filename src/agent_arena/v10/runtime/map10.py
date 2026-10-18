"""MAP-10 V10｜燃料运输：装载量与油耗耦合使“装多少”成为决策（DCR-V10-20）。

V9 的证据：接口修复后 0/2→2/2，需要验证“装载与燃料分配确实必需”。V10 的修复：

- **油耗随载重上升**：`move` 的燃料消耗 = `burn_base + ceil(cargo / 2)`，
  于是“装得越多越省一趟”与“装得越多越费油”形成真实取舍；
- **容量与库存双约束**：单次装载 ≤ `capacity`，且 ≤ 站点库存；
- **必须精确算账**：到达时必须 `cargo ≥ required` 且燃料不能为负，否则
  `OUT_OF_FUEL`（货也丢光）；
- 4 个预登记实例：初始燃料、容量、库存、必需量与油耗基数都不同。

指标：`mission_success`（主）+ `delivered_ratio` / `fuel_left` / `load_retries`。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    ratio,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

EDGES = {"A_D": ("A", "D")}
DEPOT = "D"


class Variant10:
    def __init__(
        self,
        label: str,
        fuel: int,
        capacity: int,
        stock: int,
        required: int,
        burn_base: int,
    ) -> None:
        self.label = label
        self.fuel = fuel
        self.capacity = capacity
        self.stock = stock
        self.required = required
        self.burn_base = burn_base

    def burn(self, cargo: int) -> int:
        return self.burn_base + (cargo + 1) // 2

    def best_load(self) -> int | None:
        """能到达且满足必需量的最小装载量。"""

        for cargo in range(self.required, min(self.capacity, self.stock) + 1):
            if self.burn(cargo) <= self.fuel:
                return cargo
        return None


VARIANTS: dict[int, Variant10] = {
    0: Variant10("balanced", 6, 10, 12, 6, 2),
    1: Variant10("tight_fuel", 5, 8, 10, 5, 2),
    2: Variant10("heavy_burn", 8, 12, 14, 8, 3),
    3: Variant10("low_capacity", 7, 6, 12, 4, 2),
}


class Map10V10Environment(V10Map):
    map_id = "MAP-10"
    title = "燃料运输"
    world = "polar"
    level = "简单"
    RULE_VERSION = "v10.map10.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGES
    SHAPES: dict[str, set[frozenset[str]]] = {
        "load": {frozenset({"tool", "quantity"})},
        "move": {frozenset({"tool", "to"})},
        "unload": {frozenset({"tool", "quantity"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "fuel",
            "cargo",
            "capacity",
            "station_stock",
            "burn_base",
            "required_delivery",
            "delivered",
            "load_retries",
            "burn_formula",
            "goal",
        }
    )
    PRIMARY_METRIC = "map10.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map10.v10.mission_success",
            "primary",
            "higher",
            "抵达补给站且 cargo ≥ 必需量",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map10.v10.delivered_ratio",
            "secondary",
            "higher",
            "交付量 / 必需量（截断到 1）",
            "必需量",
        ),
        MetricSpec(
            "map10.v10.fuel_left",
            "secondary",
            "higher",
            "抵达后剩余燃料",
            "抵达过的局（1）",
            zero_denominator="未抵达 → NOT_APPLICABLE",
            unit="fuel",
            valid_range=(0.0, 40.0),
        ),
        MetricSpec(
            "map10.v10.load_retries",
            "diagnostic",
            "lower",
            "重复装载次数（多付一次决策）",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.position = "A"
        self.fuel = self.variant.fuel
        self.cargo = 0
        self.stock = self.variant.stock
        self.delivered = 0
        self.arrived = False
        self.load_retries = 0
        self.loaded_once = False
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_fuel": self.variant.fuel,
            "capacity": self.variant.capacity,
            "station_stock": self.variant.stock,
            "required_delivery": self.variant.required,
            "burn_base": self.variant.burn_base,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "best_load": self.variant.best_load(),
            "required": self.variant.required,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            f"A 到补给站 {DEPOT} 一次移动；油耗 = burn_base + ceil(cargo / 2)，"
            "burn_base 与容量、库存公开。",
            "load(quantity)：装载量 ≤ capacity 且 ≤ 站点库存；可以分多次装。",
            "move：燃料不足即 OUT_OF_FUEL，货物一并损失。",
            "抵达时必须 cargo ≥ required_delivery 才算成功；unload 只是把货卸到站点。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.position,
            "fuel": self.fuel,
            "cargo": self.cargo,
            "capacity": self.variant.capacity,
            "station_stock": self.stock,
            "burn_base": self.variant.burn_base,
            "required_delivery": self.variant.required,
            "delivered": self.delivered,
            "load_retries": self.load_retries,
            "burn_formula": "burn_base + ceil(cargo / 2)",
            "goal": "算出能到站且够用的装载量，别装太满把油烧光。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "load":
            return self._load(action)
        if tool == "move":
            return self._move(action)
        if tool == "unload":
            return self._unload(action)
        if tool == "wait":
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _load(self, action: V8Action) -> str:
        if self.position != "A":
            return "NOT_AT_STATION"
        quantity = action.quantity
        if quantity is None or quantity <= 0:
            return "INVALID_QUANTITY"
        if quantity > self.variant.capacity - self.cargo:
            return "CAPACITY_EXCEEDED"
        if quantity > self.stock:
            return "STOCK_EXHAUSTED"
        if self.loaded_once:
            self.load_retries += 1
        self.cargo += int(quantity)
        self.stock -= int(quantity)
        self.loaded_once = True
        return f"LOADED:{self.cargo}"

    def _move(self, action: V8Action) -> str:
        if action.to != DEPOT:
            return "UNKNOWN_DESTINATION"
        if self.position == DEPOT:
            return "ALREADY_AT_DEPOT"
        burn = self.variant.burn(self.cargo)
        if self.fuel < burn:
            self.fuel = 0
            self.cargo = 0
            self._fail("OUT_OF_FUEL")
            return "OUT_OF_FUEL"
        self.fuel -= burn
        self.position = DEPOT
        self.arrived = True
        if self.cargo >= self.variant.required:
            self._succeed("DELIVERED_IN_FULL")
            return "DELIVERED_IN_FULL"
        self._fail("DELIVERY_SHORT")
        return "DELIVERY_SHORT"

    def _unload(self, action: V8Action) -> str:
        if self.position != DEPOT:
            return "NOT_AT_DEPOT"
        quantity = action.quantity or 0
        if quantity <= 0 or quantity > self.cargo:
            return "INVALID_QUANTITY"
        self.cargo -= int(quantity)
        self.delivered += int(quantity)
        return f"UNLOADED:{self.delivered}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "position": self.position,
            "fuel": self.fuel,
            "cargo": self.cargo,
            "delivered": self.delivered,
            "arrived": self.arrived,
            "load_retries": self.load_retries,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
        delivered_ratio = ratio(min(self.cargo, self.variant.required), self.variant.required)
        fuel_left: MValue = (
            valid(self.fuel) if self.arrived else not_applicable("未抵达")
        )
        return {
            "map10.v10.mission_success": success,
            "map10.v10.delivered_ratio": delivered_ratio,
            "map10.v10.fuel_left": fuel_left,
            "map10.v10.load_retries": valid(self.load_retries),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：装载量参与了成败（装载过且抵达）。"""

        return self.loaded_once and self.arrived


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：装到能到达且够用的最小量，然后直达。"""

    variant = VARIANTS[environment_seed]
    best = variant.best_load()
    if best is None:  # pragma: no cover - 预登记实例都可解
        raise RuntimeError("infeasible instance")
    return [
        {"tool": "load", "quantity": best},
        {"tool": "move", "to": DEPOT},
    ]


__all__ = [
    "DEPOT",
    "Map10V10Environment",
    "VARIANTS",
    "Variant10",
    "oracle_actions",
]
