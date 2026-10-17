"""MAP-12｜极夜三十天：30 天库存、维修与连续研究串的跨期排程。

本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池的一次性分配），
MAP-11 是短时空间搜救与带噪风暴抽签；本图没有空间移动、风暴或救援对象，核心是
每日两个劳动槽在供暖、温室连续供能、零件两段转运、四次控制器磨损与四轮三日
研究串之间的争用，加上燃料/口粮库存安全垫。

动作契约：每天恰好两个劳动槽，每个动作（含被拒绝的动作）消耗 1 tick / 1 槽；
``wait`` 是空转槽。当日第二个动作之后的 ``_after_tick`` 执行一次日结算，因此
论文 ``oracle_trace.jsonl`` 的“每日 0–2 条行动”可直接展平为逐步动作，日号 =
``(tick_count + 1) // 2``。

指标口径（与 docs/v7/maps/MAP-12.md 一致）：

- ``map12.survival_days``：日结算时供暖与口粮均正常的天数 / 30；提前失败照实计。
- ``map12.minimum_safety_margin``：``min_t(fuel_E_t−1, food_H_t−1)``，t 取每日
  结算快照；尚无快照 → None（UNAVAILABLE）。
- ``map12.heating_outage_days``：当日供暖关闭或无燃料即记 1 天。
- ``map12.plan_breach_days``：出现被拒绝的劳动动作，或磨损日结束时控制器仍离线
  的天数（每类同日只记 1 天）。
- ``map12.fuel_consumed``：``40 − fuel_E``（当前账本，含供暖与温室燃料）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map12Environment(MapEnvironment):
    map_id = "MAP-12"
    title = "极夜三十天"
    world = "polar"
    level = "困难"
    EDGES = {
        "H_E": ("H", "E"),
        "E_G": ("E", "G"),
        "G_S": ("G", "S"),
        "S_L": ("S", "L"),
        "H_S": ("H", "S"),
        "G_L": ("G", "L"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "set_heating": {frozenset({"tool", "choice"})},
        "start_greenhouse_power": {frozenset({"tool"})},
        "plant_batch": {frozenset({"tool"})},
        "research": {frozenset({"tool"})},
        "repair_controller": {frozenset({"tool"})},
        "transfer": {
            frozenset({"tool", "commodity", "edge_id", "from_node", "to_node", "quantity"})
        },
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "day",
            "node_inventories",
            "fuel_E",
            "heater_on",
            "controller_online",
            "greenhouse_powered",
            "greenhouse_powered_streak",
            "greenhouse_crop_planted",
            "research_streak",
            "research_points",
            "consecutive_heat_shortage_days",
            "consecutive_food_shortage_days",
            "labor_slots_remaining",
            "labor_actions_used",
            "maintenance_today",
            "goal",
        }
    )
    HORIZON_DAYS = 30
    MAINTENANCE_DAYS = (7, 14, 21, 28)
    SLOTS_PER_DAY = 2
    INITIAL_FUEL = 40
    GREENHOUSE_DAYS = 3
    HARVEST_FOOD = 5
    RESEARCH_CYCLE_DAYS = 3
    RESEARCH_POINTS = 12
    PART_LIMIT = 2
    FOOD_LIMIT = 5
    REPAIR_PARTS = 2

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ state
    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "E"
        self.items = []
        self.day = 1
        self.fuel_E = self.INITIAL_FUEL
        self.food = {"H": 30, "E": 0, "G": 0, "S": 0, "L": 0}
        self.parts = {"S": 8, "G": 0, "E": 0, "H": 0, "L": 0}
        self.heater_on = True
        self.controller_online = True
        self.greenhouse_powered = False
        self.crop_planted = False
        self.greenhouse_streak = 0
        self.research_streak = 0
        self.research_points = 0
        self.heat_streak = 0
        self.food_streak = 0
        self.heat_outage_days = 0
        self.breach_days = 0
        self.repairs = 0
        self.heat_fuel_spent = 0
        self.greenhouse_fuel_spent = 0
        self.harvested_food = 0
        self.food_consumed = 0
        self.snapshots: list[dict[str, Any]] = []
        self._research_today = False
        self._day_breach = False
        self.terminal_day: int | None = None

    # ------------------------------------------------------------------ public
    def _slots_used(self) -> int:
        return self.tick_count - (self.day - 1) * self.SLOTS_PER_DAY

    def _public(self) -> dict[str, Any]:
        used = max(0, min(self.SLOTS_PER_DAY, self._slots_used()))
        return {
            "day": self.day,
            "node_inventories": {
                "food": dict(self.food),
                "parts": dict(self.parts),
            },
            "fuel_E": self.fuel_E,
            "heater_on": self.heater_on,
            "controller_online": self.controller_online,
            "greenhouse_powered": self.greenhouse_powered,
            "greenhouse_powered_streak": self.greenhouse_streak,
            "greenhouse_crop_planted": self.crop_planted,
            "research_streak": self.research_streak,
            "research_points": self.research_points,
            "consecutive_heat_shortage_days": self.heat_streak,
            "consecutive_food_shortage_days": self.food_streak,
            "labor_slots_remaining": max(0, self.SLOTS_PER_DAY - used),
            "labor_actions_used": used,
            "maintenance_today": self.day in self.MAINTENANCE_DAYS,
            "goal": "活过 30 天并累计 12 研究积分；供暖/口粮欠供不得连续两天。",
        }

    # ------------------------------------------------------------------ rules
    def _refuse(self, code: str) -> str:
        self._day_breach = True
        return code

    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "set_heating":
            if action.choice not in {"on", "off"}:
                return self._refuse("INVALID_ACTION_SCHEMA")
            self.heater_on = action.choice == "on"
            return f"HEATING:{action.choice}"
        if tool == "start_greenhouse_power":
            if not self.controller_online:
                return self._refuse("CONTROLLER_OFFLINE")
            if self.greenhouse_powered:
                return self._refuse("GREENHOUSE_ALREADY_POWERED")
            self.greenhouse_powered = True
            return "GREENHOUSE_POWERED"
        if tool == "plant_batch":
            if not self.controller_online:
                return self._refuse("CONTROLLER_OFFLINE")
            if self.crop_planted:
                return self._refuse("BATCH_ALREADY_PLANTED")
            self.crop_planted = True
            return "BATCH_PLANTED"
        if tool == "research":
            if not self.controller_online:
                return self._refuse("CONTROLLER_OFFLINE")
            if self._research_today:
                return self._refuse("RESEARCH_ALREADY_LOGGED_TODAY")
            self._research_today = True
            return "RESEARCH_LOGGED"
        if tool == "repair_controller":
            if self.parts["E"] < self.REPAIR_PARTS:
                return self._refuse("PARTS_SHORTAGE")
            if self.controller_online:
                return self._refuse("CONTROLLER_ALREADY_ONLINE")
            self.parts["E"] -= self.REPAIR_PARTS
            self.controller_online = True
            self.repairs += 1
            return "CONTROLLER_REPAIRED"
        if tool == "transfer":
            return self._transfer(action)
        if tool == "wait":
            return "IDLE_SLOT"
        return self._refuse("ACTION_NOT_ALLOWED")

    def _transfer(self, action: V8Action) -> str:
        commodity = action.commodity
        if commodity not in {"food", "parts"}:
            return self._refuse("INVALID_TRANSFER")
        edge = self.EDGES.get(action.edge_id or "")
        if edge is None:
            return self._refuse("INVALID_EDGE")
        source, destination = action.from_node, action.to_node
        if source is None or destination is None:
            return self._refuse("INVALID_TRANSFER")
        if frozenset({source, destination}) != frozenset(edge):
            return self._refuse("INVALID_TRANSFER")
        quantity = action.quantity
        limit = self.PART_LIMIT if commodity == "parts" else self.FOOD_LIMIT
        if quantity is None or quantity < 1 or quantity > limit:
            return self._refuse("INVALID_TRANSFER")
        stock = self.food if commodity == "food" else self.parts
        if stock[source] < quantity:
            return self._refuse("STOCK_SHORTAGE")
        stock[source] -= quantity
        stock[destination] += quantity
        return f"TRANSFERRED:{commodity}:{source}->{destination}:{quantity}"

    # ------------------------------------------------------------------ ticks
    def _after_tick(self) -> None:
        if self.is_terminal:
            return
        if self._slots_used() < self.SLOTS_PER_DAY:
            return
        self._settle_day()

    def _settle_day(self) -> None:
        # 1) 独立供暖炉
        if self.heater_on and self.fuel_E >= 1:
            self.fuel_E -= 1
            self.heat_fuel_spent += 1
            self.heat_streak = 0
        else:
            self.heat_streak += 1
            self.heat_outage_days += 1
        # 2) 温室供能与连续 powered day
        if self.greenhouse_powered and self.controller_online and self.crop_planted:
            if self.fuel_E >= 1:
                self.fuel_E -= 1
                self.greenhouse_fuel_spent += 1
                self.greenhouse_streak += 1
                if self.greenhouse_streak >= self.GREENHOUSE_DAYS:
                    self.food["G"] += self.HARVEST_FOOD
                    self.harvested_food += self.HARVEST_FOOD
                    self.greenhouse_powered = False
                    self.crop_planted = False
                    self.greenhouse_streak = 0
            else:
                self.greenhouse_streak = 0
        else:
            self.greenhouse_streak = 0
        # 3) 居住舱日配给（在当日转运之后）
        if self.food["H"] >= 1:
            self.food["H"] -= 1
            self.food_consumed += 1
            self.food_streak = 0
        else:
            self.food_streak += 1
        # 4) 连续三日研究串
        if self._research_today and self.controller_online:
            self.research_streak += 1
            if self.research_streak >= self.RESEARCH_CYCLE_DAYS:
                self.research_points += 3
                self.research_streak = 0
        else:
            self.research_streak = 0
        # 5) 计划违约：被拒绝动作或磨损日未修复
        if self.day in self.MAINTENANCE_DAYS and not self.controller_online:
            self._day_breach = True
        if self._day_breach:
            self.breach_days += 1
        # 6) 日结算快照（指标用）
        self.snapshots.append(
            {
                "day": self.day,
                "fuel_E": self.fuel_E,
                "food_H": self.food["H"],
                "heat_ok": self.heat_streak == 0,
                "food_ok": self.food_streak == 0,
            }
        )
        # 7) 终局判定
        if self.heat_streak >= 2:
            self.terminal_day = self.day
            self._fail("HEAT_SHORTAGE_STREAK")
            return
        if self.food_streak >= 2:
            self.terminal_day = self.day
            self._fail("FOOD_SHORTAGE_STREAK")
            return
        if self.day >= self.HORIZON_DAYS:
            self.terminal_day = self.day
            if self.research_points >= self.RESEARCH_POINTS:
                self._succeed("SURVIVED_AND_RESEARCHED")
            else:
                self._fail("RESEARCH_TARGET_MISSED")
            return
        # 8) 推进到下一天并应用磨损
        self.day += 1
        self._research_today = False
        self._day_breach = False
        if self.day in self.MAINTENANCE_DAYS:
            self.controller_online = False
            self.greenhouse_powered = False
            self.greenhouse_streak = 0

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "tick": self.tick_count,
            "fuel_E": self.fuel_E,
            "food": dict(self.food),
            "parts": dict(self.parts),
            "heater_on": self.heater_on,
            "controller_online": self.controller_online,
            "greenhouse_powered": self.greenhouse_powered,
            "crop_planted": self.crop_planted,
            "greenhouse_streak": self.greenhouse_streak,
            "research_streak": self.research_streak,
            "research_points": self.research_points,
            "heat_streak": self.heat_streak,
            "food_streak": self.food_streak,
            "heat_outage_days": self.heat_outage_days,
            "breach_days": self.breach_days,
            "repairs": self.repairs,
            "heat_fuel_spent": self.heat_fuel_spent,
            "greenhouse_fuel_spent": self.greenhouse_fuel_spent,
            "harvested_food": self.harvested_food,
            "food_consumed": self.food_consumed,
            "snapshots": [dict(row) for row in self.snapshots],
        }

    def metrics(self) -> dict[str, Any]:
        if self.snapshots:
            margin = min(
                min(row["fuel_E"] - 1, row["food_H"] - 1) for row in self.snapshots
            )
        else:
            margin = None
        survival = sum(
            1 for row in self.snapshots if row["heat_ok"] and row["food_ok"]
        )
        return {
            "map12.survival_days": {
                "numerator": survival,
                "denominator": self.HORIZON_DAYS,
            },
            "map12.minimum_safety_margin": margin,
            "map12.heating_outage_days": self.heat_outage_days,
            "map12.plan_breach_days": self.breach_days,
            "map12.fuel_consumed": self.INITIAL_FUEL - self.fuel_E,
        }


def _parts(edge_id: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "tool": "transfer",
        "commodity": "parts",
        "edge_id": edge_id,
        "from_node": source,
        "to_node": destination,
        "quantity": 2,
    }


def _food(edge_id: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "tool": "transfer",
        "commodity": "food",
        "edge_id": edge_id,
        "from_node": source,
        "to_node": destination,
        "quantity": 5,
    }


_RESEARCH = {"tool": "research"}
_REPAIR = {"tool": "repair_controller"}

#: 论文方案 A（research_priority）：每日 0–2 条行动，按日展平后日结算落在第二个动作。
ORACLE_DAYS_RESEARCH_PRIORITY: tuple[tuple[dict[str, Any], ...], ...] = (
    ({"tool": "start_greenhouse_power"}, {"tool": "plant_batch"}),
    (_RESEARCH, _parts("G_S", "S", "G")),
    (_RESEARCH, _parts("E_G", "G", "E")),
    (_RESEARCH, _parts("G_S", "S", "G")),
    (_RESEARCH, _parts("E_G", "G", "E")),
    (_RESEARCH, _food("E_G", "G", "E")),
    (_REPAIR, _RESEARCH),
    (_RESEARCH, _food("H_E", "E", "H")),
    (_RESEARCH,),
    (_RESEARCH,),
    (_RESEARCH, _parts("G_S", "S", "G")),
    (_RESEARCH, _parts("E_G", "G", "E")),
    (_RESEARCH,),
    (_REPAIR,),
    (),
    (),
    (),
    (),
    (),
    (),
    (_REPAIR,),
    (),
    (),
    (),
    (_parts("G_S", "S", "G"),),
    (_parts("E_G", "G", "E"),),
    (),
    (_REPAIR,),
    (),
    (),
)

#: 论文方案 B（safety_buffer）：多收一批粮、把研究改排到 day10–21。
ORACLE_DAYS_SAFETY_BUFFER: tuple[tuple[dict[str, Any], ...], ...] = (
    ({"tool": "start_greenhouse_power"}, {"tool": "plant_batch"}),
    (_parts("G_S", "S", "G"),),
    (_parts("E_G", "G", "E"),),
    ({"tool": "start_greenhouse_power"}, {"tool": "plant_batch"}),
    (_food("E_G", "G", "E"),),
    (_food("H_E", "E", "H"),),
    (_REPAIR, _food("E_G", "G", "E")),
    (_parts("G_S", "S", "G"), _food("H_E", "E", "H")),
    (_parts("E_G", "G", "E"),),
    (_RESEARCH,),
    (_RESEARCH,),
    (_RESEARCH,),
    (_RESEARCH,),
    (_REPAIR, _RESEARCH),
    (_RESEARCH, _parts("G_S", "S", "G")),
    (_RESEARCH, _parts("E_G", "G", "E")),
    (_RESEARCH,),
    (_RESEARCH,),
    (_RESEARCH,),
    (_RESEARCH,),
    (_REPAIR, _RESEARCH),
    (_parts("G_S", "S", "G"),),
    (_parts("E_G", "G", "E"),),
    (),
    (),
    (),
    (),
    (_REPAIR,),
    (),
    (),
)


def _flatten_days(days: tuple[tuple[dict[str, Any], ...], ...]) -> list[dict[str, Any]]:
    """把每日 0–2 条行动展平；空槽以 ``wait`` 补齐，日结算仍在第二个动作之后。"""

    actions: list[dict[str, Any]] = []
    for day in days:
        row = list(day)
        while len(row) < Map12Environment.SLOTS_PER_DAY:
            row.append({"tool": "wait"})
        actions.extend(row)
    return actions


ORACLE_CASES = (
    {
        "trace_id": "research_priority",
        "seed": 0,
        "actions": _flatten_days(ORACLE_DAYS_RESEARCH_PRIORITY),
        "expect_success": True,
    },
    {
        "trace_id": "safety_buffer",
        "seed": 0,
        "actions": _flatten_days(ORACLE_DAYS_SAFETY_BUFFER),
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "research_priority_plan_a",
        "seed": 0,
        "actions": _flatten_days(ORACLE_DAYS_RESEARCH_PRIORITY),
        "expect": {
            "map12.fuel_consumed": 33,
            "map12.minimum_safety_margin": 4,
            "map12.survival_days": 1.0,
            "map12.heating_outage_days": 0,
            "map12.plan_breach_days": 0,
        },
    },
    {
        "name": "heating_off_two_days_with_full_fuel",
        "seed": 0,
        "actions": [
            {"tool": "set_heating", "choice": "off"},
            {"tool": "wait"},
            {"tool": "set_heating", "choice": "off"},
            {"tool": "wait"},
        ],
        "expect": {
            "map12.heating_outage_days": 2,
            "map12.fuel_consumed": 0,
            "map12.minimum_safety_margin": 27,
            "map12.survival_days": 0.0,
        },
    },
    {
        "name": "rejected_repair_is_a_plan_breach",
        "seed": 0,
        "actions": [
            {"tool": "repair_controller"},
            {"tool": "wait"},
            {"tool": "wait"},
            {"tool": "wait"},
        ],
        "expect": {
            "map12.plan_breach_days": 1,
            "map12.fuel_consumed": 2,
            "map12.heating_outage_days": 0,
        },
    },
    {
        "name": "thirty_days_passive_research_target_missed",
        "seed": 0,
        "actions": [{"tool": "wait"} for _ in range(60)],
        "expect": {
            "map12.fuel_consumed": 30,
            "map12.minimum_safety_margin": -1,
            "map12.survival_days": 1.0,
        },
    },
)


__all__ = [
    "FIXTURES",
    "ORACLE_CASES",
    "ORACLE_DAYS_RESEARCH_PRIORITY",
    "ORACLE_DAYS_SAFETY_BUFFER",
    "Map12Environment",
]
