"""MAP-10｜最后一桶燃料：同一 12 单位燃料池的运输位置与时间取舍。

本图与同世界另两图的机制差异：MAP-11 是带噪天气下的搜索与队员生命窗，MAP-12 是
30 天跨期库存与劳动槽排程；本图是单期（最长十余 tick）燃料分仓问题——基地油库只
能烧给暖气，随身燃料只能用于雪地车与发电机，两者不能互相挪用，且偶数 tick 的
供暖结算让“走多快”直接影响基地热量。这里没有 MAP-09 式的故障连锁。

指标口径（与 docs/v7/maps/MAP-10.md 一致）：
- ``fuel_consumed`` = 12 −（终局基地油库 + 随身燃料）；账本始终
  ``fuel_depot + carried_fuel + fuel_spent = 12``。
- ``key_task_fuel_efficiency`` = 完成的必需任务数（发电机启动 + 发报 = 0..2）/
  ``fuel_consumed``；燃料消耗为 0 时分母为 0，即 N/A。
- ``minimum_task_guarantee`` = 上述必需任务完成数（分母固定 2）。
- ``minimum_base_temperature`` = 逐 tick 结算后的最低基地温度（初值 5）。
- ``base_frozen`` = 1 当且仅当 ``terminal_reason == BASE_FROZEN``。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map10Environment(MapEnvironment):
    map_id = "MAP-10"
    title = "最后一桶燃料"
    world = "polar"
    level = "简单"
    EDGES = {
        "B_E": ("B", "E"),
        "E_T": ("E", "T"),
        "B_W": ("B", "W"),
        "W_T": ("W", "T"),
        "E_W_SNOWMOBILE": ("E", "W"),
    }
    EDGE_COST = {"B_E": 4, "E_T": 3, "B_W": 1, "W_T": 1, "E_W_SNOWMOBILE": 1}
    WALK_EDGES = frozenset({"B_E", "E_T", "B_W", "W_T"})
    SNOWMOBILE_EDGE = "E_W_SNOWMOBILE"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "walk": {frozenset({"tool", "edge_id"})},
        "drive_snowmobile": {
            frozenset({"tool", "edge_id"}),
            frozenset({"tool", "edge_id", "direction"}),
        },
        "load_fuel": {frozenset({"tool", "quantity"})},
        "set_heating": {frozenset({"tool", "choice"})},
        "activate_generator": {frozenset({"tool"})},
        "transmit": {frozenset({"tool"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "fuel_depot",
            "carried_fuel",
            "carry_capacity",
            "base_temperature",
            "heater_on",
            "generator_online",
            "transmission_complete",
            "goal",
        }
    )
    TOTAL_FUEL = 12
    CARRY_CAPACITY = 5
    HEATER_PERIOD = 2
    GENERATOR_FUEL_COST = 3
    SNOWMOBILE_FUEL_COST = 2

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "B"
        self.items = []
        self.fuel_depot = self.TOTAL_FUEL
        self.carried_fuel = 0
        self.base_temperature = 5
        self.heater_on = True
        self.generator_online = False
        self.transmission_complete = False

        self.minimum_base_temperature = self.base_temperature
        self.heater_fuel_spent = 0
        self.snowmobile_fuel_spent = 0
        self.generator_fuel_spent = 0
        self._destination: str | None = None
        self._pending_failure: str | None = None
        self._transmitting = False
        self._last_cost = 1

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "fuel_depot": self.fuel_depot,
            "carried_fuel": self.carried_fuel,
            "carry_capacity": self.CARRY_CAPACITY,
            "base_temperature": self.base_temperature,
            "heater_on": self.heater_on,
            "generator_online": self.generator_online,
            "transmission_complete": self.transmission_complete,
            "goal": "在基地不冻结的前提下，于 E 启动发电机并在 T 完成发报。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._destination = None
        self._pending_failure = None
        self._transmitting = False
        tool = action.tool
        if tool == "walk":
            return self._walk(action)
        if tool == "drive_snowmobile":
            return self._drive(action)
        if tool == "load_fuel":
            return self._load_fuel(action)
        if tool == "set_heating":
            return self._set_heating(action)
        if tool == "activate_generator":
            return self._activate_generator(action)
        if tool == "transmit":
            return self._transmit(action)
        if tool == "wait":
            return "WAITED" if action.ticks else "INVALID_ACTION_SCHEMA"
        return "ACTION_NOT_ALLOWED"

    def _walk(self, action: V8Action) -> str:
        if action.edge_id not in self.EDGES:
            return "INVALID_EDGE"
        if action.edge_id not in self.WALK_EDGES:
            return "INVALID_EDGE"
        destination = self.edge_destination(action.edge_id)
        if destination is None:
            return "EDGE_NOT_ADJACENT"
        self._destination = destination
        return f"WALKING:{destination}"

    def _drive(self, action: V8Action) -> str:
        if action.edge_id != self.SNOWMOBILE_EDGE:
            return "INVALID_EDGE"
        destination = self.edge_destination(action.edge_id)
        if destination is None:
            return "EDGE_NOT_ADJACENT"
        if action.direction is not None:
            # 设计轨迹自带方向标注；它只做一致性校验，不改变无向边定义。
            expected = "W_to_E" if self.node == "W" else "E_to_W"
            if action.direction != expected:
                return "INVALID_DIRECTION"
        if self.carried_fuel < self.SNOWMOBILE_FUEL_COST:
            self._pending_failure = "INSUFFICIENT_FUEL"
            return "SNOWMOBILE_FUEL_CHECK_FAILED"
        self.carried_fuel -= self.SNOWMOBILE_FUEL_COST
        self.snowmobile_fuel_spent += self.SNOWMOBILE_FUEL_COST
        self._destination = destination
        return f"DRIVING:{destination}"

    def _load_fuel(self, action: V8Action) -> str:
        if self.node != "B":
            return "INVALID_LOCATION"
        quantity = action.quantity
        if quantity is None or quantity <= 0:
            return "INVALID_QUANTITY"
        if self.carried_fuel + quantity > self.CARRY_CAPACITY:
            return "CARRY_CAPACITY_EXCEEDED"
        if quantity > self.fuel_depot:
            return "INSUFFICIENT_FUEL"
        self.fuel_depot -= quantity
        self.carried_fuel += quantity
        return f"FUEL_LOADED:{quantity}"

    def _set_heating(self, action: V8Action) -> str:
        if self.node != "B":
            return "INVALID_LOCATION"
        if action.choice not in {"on", "off"}:
            return "INVALID_CONTROL"
        requested = action.choice == "on"
        if self.heater_on == requested:
            return "HEATER_ALREADY_ON" if requested else "HEATER_ALREADY_OFF"
        self.heater_on = requested
        return "HEATING_ENABLED" if requested else "HEATING_DISABLED"

    def _activate_generator(self, action: V8Action) -> str:
        if self.node != "E":
            return "INVALID_LOCATION"
        if self.generator_online:
            return "GENERATOR_ALREADY_ONLINE"
        if self.carried_fuel < self.GENERATOR_FUEL_COST:
            self._pending_failure = "GENERATOR_FUEL_SHORTAGE"
            return "GENERATOR_FUEL_CHECK_FAILED"
        self.carried_fuel -= self.GENERATOR_FUEL_COST
        self.generator_fuel_spent += self.GENERATOR_FUEL_COST
        self.generator_online = True
        return "GENERATOR_ONLINE"

    def _transmit(self, action: V8Action) -> str:
        if self.node != "T":
            return "INVALID_LOCATION"
        if not self.generator_online:
            self._pending_failure = "GRID_OFFLINE"
            return "TRANSMIT_GRID_CHECK_FAILED"
        self._transmitting = True
        return "TRANSMITTING"

    def _action_cost(self, action: V8Action) -> int:
        if action.tool == "walk" and action.edge_id is not None:
            cost = self.EDGE_COST.get(action.edge_id, 1)
        elif action.tool == "drive_snowmobile":
            cost = 1
        elif action.tool == "wait":
            cost = action.ticks or 1
        else:
            cost = 1
        self._last_cost = cost
        return cost

    # ------------------------------------------------------------------ per tick
    def _settle_heating(self, tick_number: int) -> None:
        if tick_number % self.HEATER_PERIOD != 0:
            return
        if self.heater_on and self.fuel_depot >= 1:
            self.fuel_depot -= 1
            self.heater_fuel_spent += 1
        else:
            self.heater_on = False
            self.base_temperature -= 1
        self.minimum_base_temperature = min(
            self.minimum_base_temperature, self.base_temperature
        )

    def _after_tick(self) -> None:
        first_tick = self.tick_count - self._last_cost + 1
        for index in range(self._last_cost):
            last = index == self._last_cost - 1
            tick_number = first_tick + index
            if last and self._destination is not None:
                self.node = self._destination
                self._destination = None
            self._settle_heating(tick_number)
            if self.base_temperature <= 0:
                self._fail("BASE_FROZEN")
                return
        if self._pending_failure is not None:
            self._fail(self._pending_failure)
            return
        if self._transmitting and self.generator_online:
            self.transmission_complete = True
            self._succeed("TRANSMISSION_COMPLETE")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "fuel_depot": self.fuel_depot,
            "carried_fuel": self.carried_fuel,
            "base_temperature": self.base_temperature,
            "heater_on": self.heater_on,
            "generator_online": self.generator_online,
            "transmission_complete": self.transmission_complete,
            "minimum_base_temperature": self.minimum_base_temperature,
            "heater_fuel_spent": self.heater_fuel_spent,
            "snowmobile_fuel_spent": self.snowmobile_fuel_spent,
            "generator_fuel_spent": self.generator_fuel_spent,
            "fuel_spent": self.TOTAL_FUEL - self.fuel_depot - self.carried_fuel,
        }

    def _completed_tasks(self) -> int:
        return int(self.generator_online) + int(self.transmission_complete)

    def metrics(self) -> dict[str, Any]:
        consumed = self.TOTAL_FUEL - (self.fuel_depot + self.carried_fuel)
        return {
            "map10.base_frozen": int(self.terminal_reason == "BASE_FROZEN"),
            "map10.fuel_consumed": consumed,
            "map10.key_task_fuel_efficiency": {
                "numerator": self._completed_tasks(),
                "denominator": consumed,
            },
            "map10.minimum_base_temperature": self.minimum_base_temperature,
            "map10.minimum_task_guarantee": self._completed_tasks(),
        }


ORACLE_CASES = (
    {
        "trace_id": "walk_keep_fuel",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {"tool": "load_fuel", "quantity": 3},
            {"tool": "walk", "edge_id": "B_E"},
            {"tool": "activate_generator"},
            {"tool": "walk", "edge_id": "E_T"},
            {"tool": "transmit"},
        ],
    },
    {
        "trace_id": "snowmobile_shortcut",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {"tool": "load_fuel", "quantity": 5},
            {"tool": "walk", "edge_id": "B_W"},
            {"tool": "drive_snowmobile", "edge_id": "E_W_SNOWMOBILE"},
            {"tool": "activate_generator"},
            {"tool": "walk", "edge_id": "E_T"},
            {"tool": "transmit"},
        ],
    },
)


FIXTURES = (
    {
        "name": "walk_route_keeps_base_fuel",
        "seed": 0,
        "actions": [
            {"tool": "load_fuel", "quantity": 3},
            {"tool": "walk", "edge_id": "B_E"},
            {"tool": "activate_generator"},
            {"tool": "walk", "edge_id": "E_T"},
            {"tool": "transmit"},
        ],
        "expect": {
            # 发电机 3 + 偶数 tick 2/4/6/8/10 供暖 5 = 8；最低温度全程 5。
            "map10.fuel_consumed": 8,
            "map10.key_task_fuel_efficiency": 0.25,
            "map10.minimum_base_temperature": 5,
            "map10.minimum_task_guarantee": 2,
            "map10.base_frozen": 0,
        },
    },
    {
        "name": "shortcut_with_four_units_starves_generator",
        "seed": 0,
        "actions": [
            {"tool": "load_fuel", "quantity": 4},
            {"tool": "walk", "edge_id": "B_W"},
            {"tool": "drive_snowmobile", "edge_id": "E_W_SNOWMOBILE"},
            {"tool": "activate_generator"},
        ],
        "expect": {
            # 雪地车 2 + tick2/tick4 供暖 2 = 4；到 E 只剩 2，发电机 3 单位门槛失败。
            "map10.fuel_consumed": 4,
            "map10.key_task_fuel_efficiency": 0.0,
            "map10.minimum_task_guarantee": 0,
            "map10.base_frozen": 0,
        },
    },
    {
        "name": "over_capacity_load_is_refused_without_transfer",
        "seed": 0,
        "actions": [{"tool": "load_fuel", "quantity": 6}],
        "expect": {
            # 拒绝不产生搬运，账本保持 12；tick1 还没有供暖结算。
            "map10.fuel_consumed": 0,
            "map10.minimum_task_guarantee": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map10Environment"]
