"""MAP-01｜破损的曙光号：生命支持、互斥供电与船壳修补的依赖规划。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map01Environment(MapEnvironment):
    map_id = "MAP-01"
    title = "破损的曙光号"
    world = "spaceship"
    level = "简单"
    EDGES = {
        "B_H": ("B", "H"),
        "H_O": ("H", "O"),
        "H_P": ("H", "P"),
        "H_W": ("H", "W"),
        "H_A": ("H", "A"),
        "W_P_SERVICE": ("W", "P"),
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
            "oxygen_reserve",
            "oxygen_output",
            "routed_branch",
            "repair_arm",
            "hull_intact",
            "main_bus",
            "airlock_sealed",
            "pressure_test",
            "inventory",
            "service_edge_open",
            "goal",
        }
    )
    REQUIRED_DEPENDENCIES = (
        "oxygen_on_to_patch_pickup",
        "patch_hold_to_route_arm",
        "arm_on_to_hull_patch",
        "hull_intact_to_bus_reset",
        "bus_on_to_pressure_test",
        "pressure_pass_to_bridge_confirm",
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "B"
        self.items = []
        self.oxygen_reserve = 18
        self.oxygen_output = False
        self.oxygen_off_ticks = 0
        self.current_outage = 0
        self.max_outage = 0
        self.battery_load_limit = 6
        self.fixed_load = 3
        self.routed_branch = "none"
        self.hull_intact = False
        self.main_bus = False
        self.airlock_sealed = True
        self.pressure_test = "not_done"
        self.patch_available = True
        self.confirmed = False
        self.dependencies: dict[str, bool] = {
            name: False for name in self.REQUIRED_DEPENDENCIES
        }

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "oxygen_reserve": self.oxygen_reserve,
            "oxygen_output": self.oxygen_output,
            "routed_branch": self.routed_branch,
            "repair_arm": self.routed_branch == "arm",
            "hull_intact": self.hull_intact,
            "main_bus": self.main_bus,
            "airlock_sealed": self.airlock_sealed,
            "pressure_test": self.pressure_test,
            "inventory": list(self.items),
            "service_edge_open": self.hull_intact,
            "goal": "修复船壳、恢复供氧与主电源、完成气闸检查并在舰桥确认。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            if action.edge_id == "W_P_SERVICE" and not self.hull_intact:
                return "EDGE_LOCKED_HULL_OPEN"
            destination, result = self.move_edge(action.edge_id)
            return result if destination is not None else "EDGE_NOT_ADJACENT"
        if tool == "inspect":
            if action.target == "power_diagram" and self.node == "H":
                return "DIAGRAM:capacity=6,fixed=3,support=2,arm=2"
            if action.target == "scrubber_status" and self.node == "O":
                return "SUPPORT_STABLE" if self.oxygen_output else "SUPPORT_OFF"
            if action.target == "airlock_gauge" and self.node == "A":
                return f"AIRLOCK:{'SEALED' if self.airlock_sealed else 'OPEN'}"
            return "TARGET_NOT_VISIBLE"
        if tool == "pickup":
            if action.item_id != "patch_kit" or self.node != "W" or not self.patch_available:
                return "ITEM_NOT_PRESENT"
            if not self.oxygen_output:
                self._violate("dependency")
                return "OXYGEN_NOT_STABLE"
            self.patch_available = False
            self.take("patch_kit")
            self.dependencies["oxygen_on_to_patch_pickup"] = True
            return "PICKED:patch_kit"
        if tool == "wait":
            return "WAITED"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        target, choice = action.target, action.choice
        if target == "oxygen_relay" and choice == "start_support":
            if self.node not in {"B", "H"}:
                return "TARGET_NOT_VISIBLE"
            if self.oxygen_output:
                return "SUPPORT_ALREADY_ON"
            if self.routed_branch == "arm":
                return "POWER_CAPACITY_CONFLICT"
            self.oxygen_output = True
            self.routed_branch = "support"
            return "OXYGEN_ON"
        if target == "local_breaker" and choice == "route_arm":
            if self.node != "W":
                return "TARGET_NOT_VISIBLE"
            if not self.oxygen_output:
                return "SUPPORT_NOT_STABLE"
            if self.routed_branch == "arm":
                return "ARM_ALREADY_ROUTED"
            if not self.has("patch_kit"):
                self._violate("dependency")
                return "PATCH_REQUIRED"
            self.oxygen_output = False
            self.routed_branch = "arm"
            self.dependencies["patch_hold_to_route_arm"] = True
            return "REPAIR_ARM_ON"
        if target == "hull_panel" and choice == "apply_patch":
            if self.node != "W":
                return "TARGET_NOT_VISIBLE"
            if not self.has("patch_kit"):
                self._violate("dependency")
                return "PATCH_REQUIRED"
            if self.routed_branch != "arm":
                self._violate("dependency")
                return "ARM_UNPOWERED"
            if self.hull_intact:
                return "HULL_ALREADY_INTACT"
            self.hull_intact = True
            self.drop("patch_kit")
            self.dependencies["arm_on_to_hull_patch"] = True
            return "HULL_PATCHED"
        if target == "local_breaker" and choice == "route_support":
            if self.node != "W":
                return "TARGET_NOT_VISIBLE"
            if not self.hull_intact:
                return "REPAIR_INCOMPLETE"
            if self.oxygen_output:
                return "SUPPORT_ALREADY_ON"
            self.oxygen_output = True
            self.routed_branch = "support"
            return "SUPPORT_RESTORED"
        if target == "main_reactor" and choice == "reset_bus":
            if self.node != "P":
                return "TARGET_NOT_VISIBLE"
            if not self.hull_intact:
                self._violate("dependency")
                self._fail("BUS_RESET_WITH_HULL_OPEN")
                return "BUS_RESET_WITH_HULL_OPEN"
            if self.main_bus:
                return "BUS_ALREADY_ON"
            self.main_bus = True
            self.dependencies["hull_intact_to_bus_reset"] = True
            return "BUS_ON"
        if target == "airlock_console" and choice == "pressure_test":
            if self.node != "A":
                return "TARGET_NOT_VISIBLE"
            if not (self.oxygen_output and self.main_bus):
                return "AIRLOCK_UNSAFE"
            self.pressure_test = "pass"
            self.dependencies["bus_on_to_pressure_test"] = True
            return "PRESSURE_PASS"
        if target == "bridge_console" and choice == "confirm_repair":
            if self.node != "B":
                return "TARGET_NOT_VISIBLE"
            if not (self.hull_intact and self.main_bus and self.pressure_test == "pass"):
                return "REPAIR_INCOMPLETE"
            self.confirmed = True
            self.dependencies["pressure_pass_to_bridge_confirm"] = True
            self._succeed("REPAIR_CONFIRMED")
            return "REPAIR_CONFIRMED"
        return "ACTION_NOT_ALLOWED"

    def _after_tick(self) -> None:
        if self.oxygen_output:
            self.oxygen_off_ticks = 0
            self.current_outage = 0
            return
        self.oxygen_reserve -= 1
        self.oxygen_off_ticks += 1
        self.current_outage += 1
        self.max_outage = max(self.max_outage, self.current_outage)
        if self.oxygen_reserve <= 0:
            self._fail("OXYGEN_RESERVE_EXHAUSTED")
        elif self.oxygen_off_ticks > 3:
            self._fail("OXYGEN_SUPPLY_INTERRUPTION_LIMIT")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "inventory": sorted(self.items),
            "oxygen_reserve": self.oxygen_reserve,
            "oxygen_output": self.oxygen_output,
            "oxygen_off_ticks": self.oxygen_off_ticks,
            "dependencies": dict(self.dependencies),
            "hull_intact": self.hull_intact,
            "main_bus": self.main_bus,
            "pressure_test": self.pressure_test,
            "confirmed": self.confirmed,
            "violations": dict(self.violations),
        }

    def metrics(self) -> dict[str, Any]:
        completed = sum(1 for value in self.dependencies.values() if value)
        return {
            "map01.dependency_satisfaction_rate": {
                "numerator": completed,
                "denominator": len(self.REQUIRED_DEPENDENCIES),
            },
            "map01.longest_oxygen_outage_ticks": self.max_outage,
            "map01.oxygen_guardrail_violations": int(
                self.terminal_reason
                in {"OXYGEN_RESERVE_EXHAUSTED", "OXYGEN_SUPPLY_INTERRUPTION_LIMIT"}
            ),
            "map01.dependency_violations": self.violations.get("dependency", 0),
            "map01.completion_ticks": self.tick_count if self.is_success else None,
        }


#: Hand-computed offline fixtures. The oracle trace in
#: ``worlds/v4/MAP-01/oracle_trace.jsonl`` stays the success reference.
FIXTURES = (
    {
        "name": "pickup_denied_without_oxygen",
        "actions": [
            {"tool": "move", "edge_id": "B_H"},
            {"tool": "move", "edge_id": "H_W"},
            {"tool": "pickup", "item_id": "patch_kit"},
        ],
        "expect": {
            # 3 ticks without support: 18 -> 15 reserve, outage 3.
            "map01.dependency_satisfaction_rate": 0.0,
            "map01.longest_oxygen_outage_ticks": 3,
            "map01.dependency_violations": 1,
            "map01.oxygen_guardrail_violations": 0,
            "map01.completion_ticks": None,
        },
    },
    {
        "name": "four_tick_support_interruption_fails",
        "actions": [{"tool": "wait", "turns": 1} for _ in range(4)],
        "expect": {
            # 4 > 3 tolerated off-ticks; reserve 18 - 4 = 14.
            "map01.longest_oxygen_outage_ticks": 4,
            "map01.oxygen_guardrail_violations": 1,
            "map01.dependency_satisfaction_rate": 0.0,
            "map01.completion_ticks": None,
        },
    },
)


__all__ = ["FIXTURES", "Map01Environment"]
