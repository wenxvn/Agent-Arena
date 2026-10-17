"""MAP-03｜最后的百步：五阶段里程碑与一次性远期代码召回。"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map03Environment(MapEnvironment):
    map_id = "MAP-03"
    title = "最后的百步"
    world = "spaceship"
    level = "困难"
    EDGES = {
        "D1_D2": ("D1", "D2"),
        "D2_D3": ("D2", "D3"),
        "D3_XD": ("D3", "XD"),
        "XD_XU": ("XD", "XU"),
        "XU_U3": ("XU", "U3"),
        "U3_U2": ("U3", "U2"),
        "U2_U1": ("U2", "U1"),
        "D3_V": ("D3", "V"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target"})},
        "interact": {frozenset({"tool", "target", "choice"})},
        "submit": {frozenset({"tool", "target", "answer"})},
        "wait": {frozenset({"tool", "turns"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "aux_power",
            "cryo_power",
            "communications_power",
            "sample_cold",
            "antenna",
            "telemetry",
            "route_calibrated",
            "route_tag_read",
            "route_tag_value",
            "sample_thermal_ticks",
            "eva_supply",
            "eva_active",
            "milestones",
            "milestones_completed",
            "return_window_end_tick",
            "goal",
        }
    )
    MILESTONES = ("P1", "P2", "P3", "P4", "P5")

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "U2"
        self.items = []
        self.aux_power = False
        self.cryo_power = False
        self.communications_power = False
        self.sample_cold = False
        self.antenna = "damaged"
        self.telemetry = "not_sent"
        self.route_calibrated = False
        self.route_tag_read = False
        self.just_read_tag = False
        self.thermal_ticks: int | None = None
        self.eva_supply = 3
        self.milestones: dict[str, bool] = {name: False for name in self.MILESTONES}
        self.return_window_end_tick = 36
        self.submissions = 0
        self.tag_read_tick: int | None = None

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "aux_power": self.aux_power,
            "cryo_power": self.cryo_power,
            "communications_power": self.communications_power,
            "sample_cold": self.sample_cold,
            "antenna": self.antenna,
            "telemetry": self.telemetry,
            "route_calibrated": self.route_calibrated,
            "route_tag_read": self.route_tag_read,
            "route_tag_value": "K7" if self.just_read_tag else None,
            "sample_thermal_ticks": self.thermal_ticks,
            "eva_supply": self.eva_supply,
            "eva_active": self.node == "V",
            "milestones": dict(self.milestones),
            "milestones_completed": sum(1 for done in self.milestones.values() if done),
            "return_window_end_tick": self.return_window_end_tick,
            "goal": "完成供电、样本保全、天线修复、遥测与 K7 航线校准。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self.just_read_tag = False
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            destination, result = self.move_edge(action.edge_id)
            if destination is None:
                return "EDGE_NOT_ADJACENT"
            if destination == "V" or self.node == "V":
                self.eva_supply -= 1
                if self.eva_supply < 0:
                    self.eva_supply = 0
                if self.eva_supply == 0 and self.node == "V":
                    self._fail("EVA_OXYGEN_EXHAUSTED")
                    return "EVA_OXYGEN_EXHAUSTED"
                if self.node == "V":
                    return "EVA_UNIT_SPENT"
            return result
        if tool == "inspect":
            if action.target == "telemetry_panel" and self.node == "U3":
                return "TELEMETRY_REQUIRES_REPAIRED_ANTENNA"
            return "TARGET_NOT_VISIBLE"
        if tool == "wait":
            return "WAITED"
        if tool == "submit":
            return self._submit(action)
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        target, choice = action.target, action.choice
        if target == "aux_panel" and choice == "restore_power":
            if self.node != "D1":
                return "TARGET_NOT_VISIBLE"
            if self.aux_power:
                return "POWER_ALREADY_ON"
            self.aux_power = True
            self.cryo_power = True
            self.communications_power = True
            self.milestones["P1"] = True
            return "AUX_POWER_ON"
        if target == "sample_manifest" and choice == "read_tag":
            if self.node != "U1":
                return "TARGET_NOT_VISIBLE"
            if not self.aux_power:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.route_tag_read:
                return "TAG_ALREADY_READ"
            self.route_tag_read = True
            self.just_read_tag = True
            self.thermal_ticks = 4
            self.tag_read_tick = self.tick_count + 1
            return "TAG:K7"
        if target == "cryo_case" and choice == "stabilize_sample":
            if self.node != "U1":
                return "TARGET_NOT_VISIBLE"
            if not self.aux_power or not self.route_tag_read:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.sample_cold:
                return "SAMPLE_ALREADY_STABLE"
            if self.thermal_ticks is None or self.thermal_ticks <= 0:
                self._fail("SAMPLE_COLD_WINDOW_EXPIRED")
                return "SAMPLE_COLD_WINDOW_EXPIRED"
            self.sample_cold = True
            self.thermal_ticks = None
            self.milestones["P2"] = True
            return "SAMPLE_STABILIZED"
        if target == "antenna" and choice == "repair":
            if self.node != "V":
                return "TARGET_NOT_VISIBLE"
            if not (self.milestones["P1"] and self.milestones["P2"]):
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.antenna == "repaired":
                return "ANTENNA_ALREADY_REPAIRED"
            if self.eva_supply <= 0:
                self._fail("EVA_OXYGEN_EXHAUSTED")
                return "EVA_OXYGEN_EXHAUSTED"
            self.antenna = "repaired"
            self.eva_supply -= 1
            self.milestones["P3"] = True
            if self.eva_supply == 0 and self.node == "V":
                self._fail("EVA_OXYGEN_EXHAUSTED")
            return "ANTENNA_REPAIRED"
        if target == "telemetry" and choice == "transmit":
            if self.node != "U3":
                return "TARGET_NOT_VISIBLE"
            if not self.milestones["P3"]:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.telemetry == "sent":
                return "TELEMETRY_ALREADY_SENT"
            self.telemetry = "sent"
            self.milestones["P4"] = True
            return "TELEMETRY_SENT"
        return "ACTION_NOT_ALLOWED"

    def _submit(self, action: V8Action) -> str:
        if action.target != "route_console" or self.node != "U2":
            return "TARGET_NOT_VISIBLE"
        if self.submissions >= 1:
            return "SUBMISSION_ALREADY_USED"
        if not all(self.milestones[name] for name in ("P1", "P2", "P3", "P4")):
            self._violate("phase_order")
            return "PHASE_OUT_OF_ORDER"
        self.submissions += 1
        if action.answer != "K7":
            self._fail("ROUTE_KEY_REJECTED")
            return "ROUTE_KEY_REJECTED"
        self.route_calibrated = True
        self.milestones["P5"] = True
        self._succeed("ROUTE_CALIBRATED")
        return "ROUTE_CALIBRATED"

    def _after_tick(self) -> None:
        if self.thermal_ticks is not None and not self.sample_cold:
            if self.tag_read_tick is not None and self.tick_count > self.tag_read_tick:
                self.thermal_ticks -= 1
                if self.thermal_ticks <= 0:
                    self.thermal_ticks = 0
                    self._fail("SAMPLE_COLD_WINDOW_EXPIRED")
                    return
        if self.is_terminal:
            return
        if self.tick_count >= self.return_window_end_tick and not self.route_calibrated:
            self._fail("RETURN_WINDOW_EXPIRED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "aux_power": self.aux_power,
            "sample_cold": self.sample_cold,
            "antenna": self.antenna,
            "telemetry": self.telemetry,
            "route_calibrated": self.route_calibrated,
            "route_tag_read": self.route_tag_read,
            "eva_supply": self.eva_supply,
            "milestones": dict(self.milestones),
            "thermal_ticks": self.thermal_ticks,
            "submissions": self.submissions,
            "violations": dict(self.violations),
        }

    def metrics(self) -> dict[str, Any]:
        completed = sum(1 for done in self.milestones.values() if done)
        recall = 1.0 if self.route_calibrated else 0.0
        return {
            "map03.phase_completion_coverage": {
                "numerator": completed,
                "denominator": len(self.MILESTONES),
            },
            "map03.long_delay_recall_accuracy": {"numerator": recall, "denominator": 1},
            "map03.phase_order_violations": self.violations.get("phase_order", 0),
            "map03.lost_sample": int(self.terminal_reason == "SAMPLE_COLD_WINDOW_EXPIRED"),
            "map03.completion_ticks": self.tick_count if self.is_success else None,
        }


FIXTURES = (
    {
        "name": "early_route_submission_is_refused",
        "actions": [
            {"tool": "submit", "target": "route_console", "answer": "K7"},
        ],
        "expect": {
            "map03.phase_completion_coverage": 0.0,
            "map03.long_delay_recall_accuracy": 0.0,
            "map03.phase_order_violations": 1,
            "map03.lost_sample": 0,
            "map03.completion_ticks": None,
        },
    },
    {
        "name": "cold_window_expires_after_tag_read",
        "actions": [
            {"tool": "move", "edge_id": "U2_U1"},
            {"tool": "move", "edge_id": "U2_U1"},
            {"tool": "move", "edge_id": "U3_U2"},
            {"tool": "move", "edge_id": "XU_U3"},
            {"tool": "move", "edge_id": "XD_XU"},
            {"tool": "move", "edge_id": "D3_XD"},
            {"tool": "move", "edge_id": "D2_D3"},
            {"tool": "move", "edge_id": "D1_D2"},
            {"tool": "interact", "target": "aux_panel", "choice": "restore_power"},
            {"tool": "move", "edge_id": "D1_D2"},
            {"tool": "move", "edge_id": "D2_D3"},
            {"tool": "move", "edge_id": "D3_XD"},
            {"tool": "move", "edge_id": "XD_XU"},
            {"tool": "move", "edge_id": "XU_U3"},
            {"tool": "move", "edge_id": "U3_U2"},
            {"tool": "move", "edge_id": "U2_U1"},
            {"tool": "interact", "target": "sample_manifest", "choice": "read_tag"},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
            {"tool": "wait", "turns": 1},
        ],
        "expect": {
            # Only P1 completes; the 4-tick cold window drains after tick 18.
            "map03.phase_completion_coverage": 0.2,
            "map03.long_delay_recall_accuracy": 0.0,
            "map03.phase_order_violations": 0,
            "map03.lost_sample": 1,
            "map03.completion_ticks": None,
        },
    },
)


__all__ = ["FIXTURES", "Map03Environment"]
