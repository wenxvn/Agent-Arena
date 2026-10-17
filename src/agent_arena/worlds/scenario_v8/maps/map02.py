"""MAP-02｜双重警报：动作序号触发的泄漏事件与在线目标重排。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map02Environment(MapEnvironment):
    map_id = "MAP-02"
    title = "双重警报"
    world = "spaceship"
    level = "中等"
    EDGES = {
        "L1_L2": ("L1", "L2"),
        "C_L1": ("C", "L1"),
        "C_R1": ("C", "R1"),
        "R1_R2": ("R1", "R2"),
        "C_X": ("C", "X"),
        "X_L2": ("X", "L2"),
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
            "navigation_alarm",
            "nav_core_secured",
            "nav_core_location",
            "crew_location",
            "crew_escorted",
            "crew_in_escape_pod",
            "center_gate",
            "leak_active",
            "leak_location",
            "crew_pressure_ticks",
            "spread_contained",
            "repair_pack_available",
            "deadline_tick",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "C"
        self.items = []
        self.nav_core_secured = False
        self.crew_escorted = False
        self.crew_in_escape_pod = False
        self.center_gate = "open"
        self.leak_active = False
        self.leak_announced_tick: int | None = None
        self.spread_ticks = 2
        self.crew_pressure_ticks = 8
        self.repair_pack_available = True
        self.action_index = 0
        self.stale_actions_after_leak = 0
        self.first_meaningful_after_leak: int | None = None
        self.leak_trigger_index = 4
        self.global_deadline = 20

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "navigation_alarm": True,
            "nav_core_secured": self.nav_core_secured,
            "nav_core_location": "R1",
            "crew_location": (
                "escape_pod"
                if self.crew_in_escape_pod
                else "escorted"
                if self.crew_escorted
                else "L2"
            ),
            "crew_escorted": self.crew_escorted,
            "crew_in_escape_pod": self.crew_in_escape_pod,
            "center_gate": self.center_gate,
            "leak_active": self.leak_active,
            "leak_location": "L1" if self.leak_active else None,
            "crew_pressure_ticks": (
                self.crew_pressure_ticks
                if self.leak_active and not self.crew_in_escape_pod
                else None
            ),
            "spread_contained": self.center_gate == "closed",
            "repair_pack_available": self.repair_pack_available,
            "deadline_tick": self.global_deadline,
            "goal": "封存导航核，并把左区船员送入右区救生舱。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        if self.leak_active and self.first_meaningful_after_leak is None:
            if action.tool not in {"wait", "inspect"}:
                self.first_meaningful_after_leak = self.tick_count + 1
        if self.leak_active and not self.crew_in_escape_pod:
            destination = (
                self.edge_destination(action.edge_id) if action.edge_id is not None else None
            )
            if destination == "R1" or (
                action.tool == "interact" and action.target in {"nav_core", "core_cradle"}
            ):
                self.stale_actions_after_leak += 1
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            if action.edge_id == "C_L1" and self.center_gate == "closed":
                return "GATE_SEALED"
            destination, result = self.move_edge(action.edge_id)
            if destination is None:
                return "EDGE_NOT_ADJACENT"
            if destination == "R2" and self.crew_escorted and not self.crew_in_escape_pod:
                self.crew_in_escape_pod = True
                return "CREW_IN_ESCAPE_POD"
            return result
        if tool == "inspect":
            if action.target == "alarm_panel" and self.node == "C":
                if self.leak_active:
                    return "ALARM:navigation_fault;leak_active=true"
                return "ALARM:navigation_fault"
            if action.target == "core_cradle" and self.node == "R1":
                return "NAV_CORE_AT:R1"
            return "TARGET_NOT_VISIBLE"
        if tool == "pickup":
            if action.item_id != "crew" or self.node != "L2":
                return "ITEM_NOT_PRESENT"
            if self.crew_in_escape_pod:
                return "CREW_ALREADY_SAFE"
            if self.crew_escorted:
                return "CREW_ALREADY_ESCORTED"
            self.crew_escorted = True
            return "CREW_ESCORTED"
        if tool == "wait":
            return "WAITED"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        target, choice = action.target, action.choice
        if target == "nav_core" and choice == "brace_in_case":
            if self.node != "R1":
                return "TARGET_NOT_VISIBLE"
            if self.nav_core_secured:
                return "NAV_CORE_ALREADY_SECURED"
            if not self.repair_pack_available and not self.has("repair_pack"):
                return "REPAIR_PACK_REQUIRED"
            self.repair_pack_available = False
            self.drop("repair_pack")
            self.nav_core_secured = True
            return "NAV_CORE_SECURED"
        if target == "center_gate" and choice == "isolate_L1":
            if self.node != "C":
                return "TARGET_NOT_VISIBLE"
            if self.center_gate == "closed":
                return "GATE_ALREADY_SEALED"
            self.center_gate = "closed"
            return "GATE_SEALED"
        if target == "crew" and choice == "escort":
            if self.node != "L2":
                return "TARGET_NOT_VISIBLE"
            if self.crew_in_escape_pod or self.crew_escorted:
                return "CREW_ALREADY_ESCORTED"
            self.crew_escorted = True
            return "CREW_ESCORTED"
        return "ACTION_NOT_ALLOWED"

    def _after_tick(self) -> None:
        self.action_index += 1
        if not self.leak_active and self.action_index >= self.leak_trigger_index:
            self.leak_active = True
            self.leak_announced_tick = self.tick_count
            return
        if self.nav_core_secured and self.crew_in_escape_pod:
            self._succeed("DUAL_OBJECTIVE_COMPLETE")
            return
        if not self.leak_active:
            return
        if self.center_gate != "closed":
            self.spread_ticks -= 1
            if self.spread_ticks <= 0:
                self.spread_ticks = 0
                if not self.nav_core_secured:
                    self._fail("NAV_CORE_FLOODED")
                    return
        if not self.crew_in_escape_pod:
            self.crew_pressure_ticks -= 1
            if self.crew_pressure_ticks <= 0:
                self._fail("CREW_PRESSURE_LOST")
                return
        if self.tick_count >= self.global_deadline:
            self._fail("GLOBAL_DEADLINE")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "nav_core_secured": self.nav_core_secured,
            "crew_escorted": self.crew_escorted,
            "crew_in_escape_pod": self.crew_in_escape_pod,
            "center_gate": self.center_gate,
            "leak_active": self.leak_active,
            "spread_ticks": self.spread_ticks,
            "crew_pressure_ticks": self.crew_pressure_ticks,
            "action_index": self.action_index,
            "stale_actions_after_leak": self.stale_actions_after_leak,
        }

    def metrics(self) -> dict[str, Any]:
        rescue = 1.0 if self.crew_in_escape_pod else 0.0
        nav = 1.0 if self.nav_core_secured else 0.0
        latency: int | None = None
        if self.leak_announced_tick is not None and self.first_meaningful_after_leak is not None:
            latency = self.first_meaningful_after_leak - self.leak_announced_tick
        return {
            "map02.dual_objective_completion": {
                "numerator": rescue + nav,
                "denominator": 2,
            },
            "map02.event_response_latency": latency,
            "map02.stale_plan_actions_after_leak": self.stale_actions_after_leak,
            "map02.crew_decompression": int(self.terminal_reason == "CREW_PRESSURE_LOST"),
            "map02.completion_ticks": self.tick_count if self.is_success else None,
        }


FIXTURES = (
    {
        "name": "nav_core_then_pod_success",
        "actions": [
            {"tool": "move", "edge_id": "C_L1"},
            {"tool": "move", "edge_id": "L1_L2"},
            {"tool": "pickup", "item_id": "crew"},
            {"tool": "move", "edge_id": "L1_L2"},
            {"tool": "move", "edge_id": "C_L1"},
            {"tool": "interact", "target": "center_gate", "choice": "isolate_L1"},
            {"tool": "move", "edge_id": "C_R1"},
            {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"},
            {"tool": "move", "edge_id": "R1_R2"},
        ],
        "expect": {
            # Leak announces at tick 4; first non-wait/inspect reply lands tick 5.
            "map02.dual_objective_completion": 1.0,
            "map02.event_response_latency": 1,
            # Two post-leak commands still target the now-stale R1 errand.
            "map02.stale_plan_actions_after_leak": 2,
            "map02.crew_decompression": 0,
            "map02.completion_ticks": 9,
        },
    },
    {
        "name": "secure_core_but_lose_crew",
        "actions": [
            {"tool": "move", "edge_id": "C_L1"},
            {"tool": "move", "edge_id": "L1_L2"},
            {"tool": "move", "edge_id": "L1_L2"},
            {"tool": "move", "edge_id": "C_L1"},
            {"tool": "interact", "target": "center_gate", "choice": "isolate_L1"},
            {"tool": "move", "edge_id": "C_R1"},
            {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
        ],
        "expect": {
            # Crew pressure 8 starts draining at tick 5 and hits 0 at tick 12.
            "map02.crew_decompression": 1,
            "map02.dual_objective_completion": 0.5,
            "map02.stale_plan_actions_after_leak": 2,
            "map02.event_response_latency": 1,
            "map02.completion_ticks": None,
        },
    },
)


__all__ = ["FIXTURES", "Map02Environment"]
