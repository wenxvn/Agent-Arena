"""MAP-11｜失联的小队：带噪天气下的短线风险与长线安全路线选择。

本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池、发电机缺油/
基地冻结），MAP-12 是 30 天跨期库存与劳动槽排程（无空间搜索、无风暴抽签）；
本图是短时（≤25 tick）空间搜救，核心变量是四次相关风暴抽签、队员生命窗、
侦察后验与负重返程每段 +1 tick。三图的失败码与资源账本互不重叠。

指标口径（与 docs/v7/maps/MAP-11.md 一致）：

- ``map11.rescue_count``：成功带回 B 的队员数，0/1；未终局或救援后失败均为 0。
- ``map11.resource_cost_per_rescue``：已耗补给 / 获救人数；分母 0 → N/A。
- ``map11.rescuer_hypothermia``：``BODY_HEAT_DEPLETED`` 终局计数，0/1。
- ``map11.abandoned_reachable_targets``：终局时队员未获救且生命仍 >0 的人数，0/1。
- ``map11.first_clue_delay``：首次 ``scout`` 结果落地 tick；未侦察 → None。

隐藏真值（气象态、逐段风暴掩码）只进 ``judge_state()``；公开面只有已走过的
天气、噪声信号与递推后验。
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map11Environment(MapEnvironment):
    map_id = "MAP-11"
    title = "失联的小队"
    world = "polar"
    level = "中等"
    EDGES = {
        "B_P_SHORT": ("B", "P"),
        "P_S_SHORT": ("P", "S"),
        "B_D_LONG": ("B", "D"),
        "D_Q_LONG": ("D", "Q"),
        "Q_S_LONG": ("Q", "S"),
    }
    SHORT_EDGES = frozenset({"B_P_SHORT", "P_S_SHORT"})
    EDGE_COST = {
        "B_P_SHORT": 1,
        "P_S_SHORT": 1,
        "B_D_LONG": 3,
        "D_Q_LONG": 3,
        "Q_S_LONG": 3,
    }
    #: 每次穿越的补给费用；负重只加 tick，不加补给。
    EDGE_SUPPLY = {
        "B_P_SHORT": 2,
        "P_S_SHORT": 2,
        "B_D_LONG": 1,
        "D_Q_LONG": 1,
        "Q_S_LONG": 1,
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {
            frozenset({"tool", "edge_id"}),
            frozenset({"tool", "edge_id", "loaded_return"}),
            frozenset({"tool", "edge_id", "loaded_return", "direction"}),
        },
        "scout": {frozenset({"tool"})},
        "resupply": {frozenset({"tool", "quantity"})},
        "rest": {frozenset({"tool"})},
        "rescue": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "supply_depot_B",
            "carried_supply",
            "carried_supply_capacity",
            "agent_heat",
            "teammate_heat",
            "teammate_life_remaining",
            "teammate_rescued",
            "current_storm",
            "posterior_unstable_probability_belief",
            "forecast_storm_probability_per_short_crossing",
            "last_scout_signal",
            "loaded_return_required",
            "short_crossings_resolved",
            "goal",
        }
    )
    #: 手工审计 fixture 的 0–9 号 seed（worlds/v4/MAP-11/weather_seed_fixture.yaml）。
    AUDIT_SEEDS = {
        0: ("quiet", "falling", "0000"),
        1: ("quiet", "falling", "1000"),
        2: ("quiet", "rising", "0000"),
        3: ("quiet", "falling", "0000"),
        4: ("quiet", "falling", "0100"),
        5: ("unstable", "rising", "1100"),
        6: ("unstable", "rising", "1010"),
        7: ("unstable", "rising", "1110"),
        8: ("unstable", "falling", "1001"),
        9: ("unstable", "rising", "0111"),
    }
    CARRY_CAPACITY = 8
    INITIAL_DEPOT = 8
    INITIAL_HEAT = 10
    INITIAL_TEAMMATE_LIFE = 15

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ state
    def _weather(self, seed: int) -> tuple[str, str, str]:
        audit = self.AUDIT_SEEDS.get(seed)
        if audit is not None:
            return audit
        digest = sha256(f"MAP-11|{seed}".encode()).digest()
        regime = "unstable" if digest[0] & 1 else "quiet"
        p_storm = 0.6 if regime == "unstable" else 0.1
        p_rising = 0.8 if regime == "unstable" else 0.2
        signal = "rising" if (digest[1] % 100) / 100 < p_rising else "falling"
        mask = "".join(
            "1" if (digest[2 + index] % 100) / 100 < p_storm else "0"
            for index in range(4)
        )
        return regime, signal, mask

    def _reset_state(self, seed: int) -> None:
        self.node = "B"
        self.items = []
        self.depot = self.INITIAL_DEPOT
        self.carried = 0
        self.agent_heat = self.INITIAL_HEAT
        self.teammate_heat = self.INITIAL_HEAT
        self.teammate_life = self.INITIAL_TEAMMATE_LIFE
        self.teammate_rescued = False
        self.current_storm = "clear"
        self.posterior = 0.5
        self.hidden_regime, self.hidden_signal, self.hidden_storm_mask = self._weather(seed)
        self.scout_signal: str | None = None
        self.scout_tick: int | None = None
        self.short_crossings = 0
        self.storm_hits = 0
        self.supply_spent = 0
        self.rests = 0
        self.rescue_tick: int | None = None
        self.min_agent_heat = self.INITIAL_HEAT
        self.min_teammate_heat = self.INITIAL_HEAT
        self._pending_edge: str | None = None
        self._pending_destination: str | None = None
        self._pending_cost = 0
        self._pending_rescue = False
        self._settled_tick = 0

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "supply_depot_B": self.depot,
            "carried_supply": self.carried,
            "carried_supply_capacity": self.CARRY_CAPACITY,
            "agent_heat": self.agent_heat,
            "teammate_heat": self.teammate_heat,
            "teammate_life_remaining": self.teammate_life,
            "teammate_rescued": self.teammate_rescued,
            "current_storm": self.current_storm,
            "posterior_unstable_probability_belief": round(self.posterior, 6),
            "forecast_storm_probability_per_short_crossing": round(
                0.1 + 0.5 * self.posterior, 6
            ),
            "last_scout_signal": self.scout_signal,
            "loaded_return_required": self.teammate_rescued,
            "short_crossings_resolved": self.short_crossings,
            "goal": "抵达 S 救回队员，并在两人体温都 >0 的前提下返回 B。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_edge = None
        self._pending_destination = None
        self._pending_cost = 0
        self._pending_rescue = False
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "scout":
            if self.node != "B":
                return "INVALID_LOCATION"
            self.scout_signal = self.hidden_signal
            self.posterior = 0.8 if self.hidden_signal == "rising" else 0.2
            self._pending_cost = 2
            if self.scout_tick is None:
                self.scout_tick = self.tick_count + 2
            return f"SCOUT:{self.hidden_signal}"
        if tool == "resupply":
            return self._resupply(action)
        if tool == "rest":
            return self._rest()
        if tool == "rescue":
            return self._rescue()
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        edge_id = action.edge_id
        if edge_id is None:
            return "INVALID_ACTION_SCHEMA"
        edge = self.EDGES.get(edge_id)
        if edge is None:
            return "INVALID_EDGE"
        if self.node not in edge:
            return "EDGE_NOT_ADJACENT"
        destination = edge[1] if edge[0] == self.node else edge[0]
        required = self.EDGE_SUPPLY[edge_id]
        if self.carried < required:
            self._fail("SUPPLY_SHORTAGE")
            return "SUPPLY_SHORTAGE"
        if action.loaded_return is not None and action.loaded_return != self.teammate_rescued:
            return "LOADED_RETURN_MISMATCH"
        if action.direction is not None:
            if action.direction != f"{self.node}_to_{destination}":
                return "INVALID_DIRECTION"
        self.carried -= required
        self.supply_spent += required
        cost = self.EDGE_COST[edge_id] + (1 if self.teammate_rescued else 0)
        self._pending_edge = edge_id
        self._pending_destination = destination
        self._pending_cost = cost
        return f"MOVING:{self.node}_to_{destination}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._pending_cost or 1

    def _resupply(self, action: V8Action) -> str:
        if self.node != "B":
            return "INVALID_LOCATION"
        quantity = action.quantity
        if quantity is None or quantity <= 0:
            return "INVALID_QUANTITY"
        if quantity > self.depot:
            return "DEPOT_INSUFFICIENT"
        if self.carried + quantity > self.CARRY_CAPACITY:
            return "CARRY_CAPACITY_EXCEEDED"
        self.depot -= quantity
        self.carried += quantity
        return f"RESUPPLIED:{quantity}"

    def _rest(self) -> str:
        if self.node not in {"B", "D", "Q"}:
            return "INVALID_LOCATION"
        if self.carried < 1:
            self._fail("SUPPLY_SHORTAGE")
            return "SUPPLY_SHORTAGE"
        self.carried -= 1
        self.supply_spent += 1
        self.rests += 1
        self.agent_heat = min(self.INITIAL_HEAT, self.agent_heat + 2)
        if self.teammate_rescued:
            self.teammate_heat = min(self.INITIAL_HEAT, self.teammate_heat + 2)
        return "RESTED"

    def _rescue(self) -> str:
        if self.node != "S":
            return "INVALID_LOCATION"
        if self.teammate_rescued:
            return "ALREADY_RESCUED"
        if self.teammate_life <= 0:
            self._fail("TEAM_LIFE_EXPIRED")
            return "TEAM_LIFE_EXPIRED"
        self._pending_rescue = True
        return "RESCUE_PENDING"

    # ------------------------------------------------------------------ ticks
    def _after_tick(self) -> None:
        elapsed = self.tick_count - self._settled_tick
        if elapsed <= 0:
            return
        self._settled_tick = self.tick_count
        if not self.teammate_rescued:
            self.teammate_life = max(0, self.teammate_life - elapsed)
            if self.teammate_life <= 0:
                self._pending_edge = None
                self._pending_destination = None
                self._pending_rescue = False
                self._fail("TEAM_LIFE_EXPIRED")
                return
        if self._pending_edge is not None and self._pending_destination is not None:
            edge_id = self._pending_edge
            destination = self._pending_destination
            self._pending_edge = None
            self._pending_destination = None
            self._resolve_arrival(edge_id, destination)
            if self.is_terminal:
                return
        if self._pending_rescue:
            self._pending_rescue = False
            self.teammate_rescued = True
            self.rescue_tick = self.tick_count
        if (
            self.node == "B"
            and self.teammate_rescued
            and self.agent_heat > 0
            and self.teammate_heat > 0
        ):
            self._succeed("FULL_SAFE_RETURN")

    def _resolve_arrival(self, edge_id: str, destination: str) -> None:
        self.node = destination
        if edge_id in self.SHORT_EDGES:
            bit = "0"
            if self.short_crossings < len(self.hidden_storm_mask):
                bit = self.hidden_storm_mask[self.short_crossings]
            self.short_crossings += 1
            storm = bit == "1"
            self.current_storm = "storm" if storm else "clear"
            unstable = self.posterior
            if storm:
                numerator = 0.6 * unstable
                self.posterior = numerator / (numerator + 0.1 * (1 - unstable))
                self.storm_hits += 1
            else:
                numerator = 0.4 * unstable
                self.posterior = numerator / (numerator + 0.9 * (1 - unstable))
            # B-P 出发时队员仍在 S；其余短路段双方都在暴露位置。
            exposed_teammate = self.teammate_rescued or destination == "S"
            self._cold(1 + (5 if storm else 0), exposed_teammate)
        else:
            self._cold(1, self.teammate_rescued)

    def _cold(self, amount: int, include_teammate: bool) -> None:
        self.agent_heat -= amount
        self.min_agent_heat = min(self.min_agent_heat, self.agent_heat)
        if include_teammate:
            self.teammate_heat -= amount
            self.min_teammate_heat = min(self.min_teammate_heat, self.teammate_heat)
        if self.agent_heat <= 0 or (include_teammate and self.teammate_heat <= 0):
            self._fail("BODY_HEAT_DEPLETED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "tick": self.tick_count,
            "hidden_regime": self.hidden_regime,
            "hidden_scout_signal": self.hidden_signal,
            "hidden_storm_mask": self.hidden_storm_mask,
            "posterior_unstable": round(self.posterior, 9),
            "scout_signal": self.scout_signal,
            "scout_tick": self.scout_tick,
            "short_crossings": self.short_crossings,
            "storm_hits": self.storm_hits,
            "depot": self.depot,
            "carried": self.carried,
            "supply_spent": self.supply_spent,
            "agent_heat": self.agent_heat,
            "teammate_heat": self.teammate_heat,
            "teammate_life": self.teammate_life,
            "teammate_rescued": self.teammate_rescued,
            "rescue_tick": self.rescue_tick,
            "min_agent_heat": self.min_agent_heat,
            "min_teammate_heat": self.min_teammate_heat,
            "rests": self.rests,
        }

    def metrics(self) -> dict[str, Any]:
        returns_home = int(self.is_success)
        abandoned = int(
            self.is_terminal and not self.teammate_rescued and self.teammate_life > 0
        )
        return {
            "map11.rescue_count": returns_home,
            "map11.resource_cost_per_rescue": {
                "numerator": self.supply_spent,
                "denominator": returns_home,
            },
            "map11.rescuer_hypothermia": int(
                self.terminal_reason == "BODY_HEAT_DEPLETED"
            ),
            "map11.abandoned_reachable_targets": abandoned,
            "map11.first_clue_delay": self.scout_tick,
        }


def _move(edge_id: str, *, loaded: bool, direction: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool": "move",
        "edge_id": edge_id,
        "loaded_return": loaded,
    }
    if direction is not None:
        payload["direction"] = direction
    return payload


#: 三条手写计划来自 worlds/v4/MAP-11/oracle_trace.jsonl，动作已是逐步动作。
_QUICK_SHORT_ACTIONS: list[dict[str, Any]] = [
    {"tool": "resupply", "quantity": 8},
    _move("B_P_SHORT", loaded=False),
    _move("P_S_SHORT", loaded=False),
    {"tool": "rescue"},
    _move("P_S_SHORT", loaded=True, direction="S_to_P"),
    _move("B_P_SHORT", loaded=True, direction="P_to_B"),
]

_LONG_ACTIONS: list[dict[str, Any]] = [
    {"tool": "resupply", "quantity": 6},
    {"tool": "scout"},
    _move("B_D_LONG", loaded=False),
    _move("D_Q_LONG", loaded=False),
    _move("Q_S_LONG", loaded=False),
    {"tool": "rescue"},
    _move("Q_S_LONG", loaded=True, direction="S_to_Q"),
    _move("D_Q_LONG", loaded=True, direction="Q_to_D"),
    _move("B_D_LONG", loaded=True, direction="D_to_B"),
]

_SEVEN_SUPPLY_ACTIONS: list[dict[str, Any]] = [
    {"tool": "resupply", "quantity": 7},
    _move("B_P_SHORT", loaded=False),
    _move("P_S_SHORT", loaded=False),
    {"tool": "rescue"},
    _move("P_S_SHORT", loaded=True, direction="S_to_P"),
    _move("B_P_SHORT", loaded=True, direction="P_to_B"),
]

#: 侦察后的 falling 分支（seed 0），用于验证首次线索延迟。
_SCOUTED_SHORT_ACTIONS: list[dict[str, Any]] = [
    {"tool": "scout"},
    {"tool": "resupply", "quantity": 8},
    _move("B_P_SHORT", loaded=False),
    _move("P_S_SHORT", loaded=False),
    {"tool": "rescue"},
    _move("P_S_SHORT", loaded=True, direction="S_to_P"),
    _move("B_P_SHORT", loaded=True, direction="P_to_B"),
]

ORACLE_CASES = (
    {
        "trace_id": "quick_short_seed0",
        "seed": 0,
        "actions": list(_QUICK_SHORT_ACTIONS),
        "expect_success": True,
    },
    {
        "trace_id": "scout_then_short_seed0",
        "seed": 0,
        "actions": list(_SCOUTED_SHORT_ACTIONS),
        "expect_success": True,
    },
    {
        "trace_id": "scout_then_long_seed7",
        "seed": 7,
        "actions": list(_LONG_ACTIONS),
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "quick_short_success_eight_supplies",
        "seed": 0,
        "actions": list(_QUICK_SHORT_ACTIONS),
        "expect": {
            "map11.rescue_count": 1,
            "map11.resource_cost_per_rescue": 8.0,
            "map11.first_clue_delay": None,
        },
    },
    {
        "name": "seven_supplies_cannot_close_short_loop",
        "seed": 0,
        "actions": list(_SEVEN_SUPPLY_ACTIONS),
        "expect": {
            "map11.rescue_count": 0,
            "map11.rescuer_hypothermia": 0,
        },
    },
    {
        "name": "false_negative_scout_two_storms",
        "seed": 8,
        "actions": list(_SCOUTED_SHORT_ACTIONS),
        "expect": {
            "map11.rescuer_hypothermia": 1,
            "map11.rescue_count": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map11Environment"]
