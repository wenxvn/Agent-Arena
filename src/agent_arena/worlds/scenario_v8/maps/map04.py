"""MAP-04｜潮汐密道：周期相位预测与短窗/长绕行的时序权衡。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map04Environment(MapEnvironment):
    map_id = "MAP-04"
    title = "潮汐密道"
    world = "lighthouse"
    level = "简单"
    EDGES = {
        "T_S": ("T", "S"),
        "S_G": ("S", "G"),
        "G_D": ("G", "D"),
        "T_B1": ("T", "B1"),
        "B1_B2": ("B1", "B2"),
        "B2_B3": ("B2", "B3"),
        "B3_B4": ("B3", "B4"),
        "B4_D": ("B4", "D"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target"})},
        "pickup": {frozenset({"tool", "item_id"})},
        "interact": {frozenset({"tool", "target", "choice"})},
        "wait": {frozenset({"tool", "turns"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tide_phase",
            "tide_period",
            "open_phases",
            "inventory",
            "wick_location",
            "lamp_wick_fitted",
            "lamp_lit",
            "rescue_deadline_tick",
            "goal",
        }
    )
    SAFE_PHASES = (0, 1)
    EARLIEST_FEASIBLE_CROSSING_TICK = 5

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "T"
        self.items = []
        self.tide_phase = 2
        self.tide_period = 6
        self.wick_available = True
        self.lamp_wick_fitted = False
        self.lamp_lit = False
        self.rescue_deadline_tick = 18
        self.crossing_attempts = 0
        self.crossing_successes = 0
        self.first_crossing_tick: int | None = None
        self.high_tide_entries = 0
        self.wait_ticks = 0
        self._last_cost = 1

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tide_phase": self.tide_phase,
            "tide_period": self.tide_period,
            "open_phases": list(self.SAFE_PHASES),
            "inventory": list(self.items),
            "wick_location": "G" if self.wick_available else "carried",
            "lamp_wick_fitted": self.lamp_wick_fitted,
            "lamp_lit": self.lamp_lit,
            "rescue_deadline_tick": self.rescue_deadline_tick,
            "goal": "在救援船抵达前把灯芯装进灯塔并点亮。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            if action.edge_id == "S_G":
                self.crossing_attempts += 1
                if self.tide_phase not in self.SAFE_PHASES:
                    self.high_tide_entries += 1
                    return "TIDE_WINDOW_CLOSED"
                self.crossing_successes += 1
                if self.first_crossing_tick is None:
                    self.first_crossing_tick = self.tick_count + 1
            destination, result = self.move_edge(action.edge_id)
            return result if destination is not None else "EDGE_NOT_ADJACENT"
        if tool == "inspect":
            if action.target == "tide_gauge":
                return f"TIDE_PHASE:{self.tide_phase}"
            return "TARGET_NOT_VISIBLE"
        if tool == "pickup":
            if action.item_id != "wick" or self.node != "G" or not self.wick_available:
                return "ITEM_NOT_PRESENT"
            self.wick_available = False
            self.take("wick")
            return "PICKED:wick"
        if tool == "wait":
            turns = action.turns or 1
            self.wait_ticks += turns
            return "WAITED"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        if action.target != "lamp" or self.node != "T":
            if action.target == "lamp":
                return "TARGET_NOT_VISIBLE"
            return "ACTION_NOT_ALLOWED"
        if action.choice == "fit_wick":
            if not self.has("wick"):
                return "WICK_REQUIRED"
            if self.lamp_wick_fitted:
                return "WICK_ALREADY_FITTED"
            self.lamp_wick_fitted = True
            return "WICK_FITTED"
        if action.choice == "ignite":
            if not self.lamp_wick_fitted:
                return "WICK_NOT_FITTED"
            self.lamp_lit = True
            self._succeed("SIGNAL_LIT")
            return "SIGNAL_LIT"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        self._last_cost = action.turns if action.tool == "wait" and action.turns is not None else 1
        return self._last_cost

    def _after_tick(self) -> None:
        self.tide_phase = (self.tide_phase + self._last_cost) % self.tide_period
        if self.tick_count >= self.rescue_deadline_tick and not self.lamp_lit:
            self._fail("RESCUE_SIGNAL_WINDOW_EXPIRED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "inventory": sorted(self.items),
            "tide_phase": self.tide_phase,
            "lamp_wick_fitted": self.lamp_wick_fitted,
            "lamp_lit": self.lamp_lit,
            "crossing_attempts": self.crossing_attempts,
            "crossing_successes": self.crossing_successes,
            "first_crossing_tick": self.first_crossing_tick,
            "high_tide_entries": self.high_tide_entries,
            "wait_ticks": self.wait_ticks,
        }

    def metrics(self) -> dict[str, Any]:
        delay: int | None = None
        if self.first_crossing_tick is not None:
            delay = max(0, self.first_crossing_tick - self.EARLIEST_FEASIBLE_CROSSING_TICK)
        return {
            "map04.window_hit_rate": {
                "numerator": self.crossing_successes,
                "denominator": self.crossing_attempts,
            },
            "map04.earliest_safe_crossing_delay": delay,
            "map04.high_tide_entries": self.high_tide_entries,
            "map04.stranded_ticks": self.high_tide_entries,
            "map04.wait_ticks": self.wait_ticks,
        }


FIXTURES = (
    {
        "name": "ticks_and_phase",
        "actions": [
            {"tool": "move", "edge_id": "T_S"},
            {"tool": "move", "edge_id": "S_G"},
        ],
        "expect": {"map04.high_tide_entries": 1},
    },
    {
        "name": "wait_to_safe_phase",
        "actions": [
            {"tool": "move", "edge_id": "T_S"},
            {"tool": "wait", "turns": 4},
            {"tool": "move", "edge_id": "S_G"},
        ],
        "expect": {"map04.high_tide_entries": 0, "map04.wait_ticks": 4},
    },
)


__all__ = ["FIXTURES", "Map04Environment"]
