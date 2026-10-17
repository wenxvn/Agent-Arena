"""MAP-25｜第一次出舱：严格依赖顺序的 EVA 维修与氧气预算。

本图与同世界另两图的机制差异：MAP-26 有诊断反馈与备件预算、核心是错误后修正；
MAP-27 是多主体协同。本图是单 Agent 单线程流程，故障固定且单一，核心是“别在
准备阶段漏步”：穿服、挂绳、排压、检查、诊断、维修、返舱之间的前置关系不可交换。

指标口径（与 V7 卡片一致）：
- ``required_check_coverage`` = 已完成必需步骤 / 7（4 件装备 + T 清单 + S 检查 +
  诊断）。
- ``dependency_order_correctness`` = 前置满足的必需步骤 / 已尝试必需步骤；0 步为
  N/A。
- ``unsafe_eva_attempts`` = ``UNSUITED_EVA`` + ``UNSAFE_UNTETHERED_EVA`` 次数。
- ``oxygen_shortfall`` = 1 当且仅当终局为 ``OXYGEN_DEPLETED``。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

REQUIRED_STEPS = (
    "eva_suit",
    "diagnostic_unit",
    "wrench",
    "safety_tether",
    "equipment_inspected",
    "array_inspected",
    "diagnosed",
)
TOOL_IDS = ("eva_suit", "diagnostic_unit", "wrench", "safety_tether")
REPAIR_TOOLS = ("diagnostic_unit", "wrench")
DIAGNOSIS = "FUSE_BANK_B_OPEN"


class Map25Environment(MapEnvironment):
    map_id = "MAP-25"
    title = "第一次出舱"
    world = "lunar"
    level = "简单"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "inspect": {frozenset({"tool", "target"})},
        "equip": {
            frozenset({"tool", "item_id"}),
            frozenset({"tool", "item_id", "target"}),
        },
        "depressurize": {frozenset({"tool"})},
        "eva_exit": {frozenset({"tool"})},
        "diagnose": {frozenset({"tool", "device_id"})},
        "repair": {
            frozenset({"tool", "target_id", "tool_ids", "diagnosis_code"}),
            frozenset({"tool", "target_id", "tool_ids"}),
        },
        "return_to_A": {frozenset({"tool"})},
        "pressurize": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "location",
            "oxygen_remaining",
            "airlock_pressure",
            "inner_hatch_locked",
            "suit_worn",
            "tether_attached",
            "carried_tools",
            "visible_equipment_here",
            "array_surface_symptom",
            "diagnosis_code_if_obtained",
            "array_repaired",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "H"
        self.oxygen = 12
        self.pressure = "PRESSURIZED"
        self.outer_hatch = "CLOSED"
        self.suit = False
        self.tools: set[str] = set()
        self.tether = False
        self.equipment_inspected = False
        self.array_inspected = False
        self.diagnosed = False
        self.repaired = False
        self.last_error = ""
        self.required_done: set[str] = set()
        self.required_attempted = 0
        self.required_correct = 0
        self._cost = 1
        self._oxygen_cost = 0
        self._arrived_home = False

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        equipment = (
            [
                item
                for item in ("eva_suit", "diagnostic_unit", "wrench")
                if item not in self.tools
            ]
            if self.node == "T"
            else []
        )
        return {
            "tick": self.tick_count,
            "location": self.node,
            "oxygen_remaining": self.oxygen,
            "airlock_pressure": self.pressure,
            "inner_hatch_locked": self.pressure == "VACUUM",
            "suit_worn": self.suit,
            "tether_attached": self.tether,
            "carried_tools": sorted(self.tools),
            "visible_equipment_here": equipment,
            "array_surface_symptom": (
                "ARRAY_OUTPUT_ZERO" if self.array_inspected else None
            ),
            "diagnosis_code_if_obtained": DIAGNOSIS if self.diagnosed else None,
            "array_repaired": self.repaired,
            "goal": (
                "穿上 EVA 服、在 A 挂安全绳并排压，出舱检查并诊断阵列，用精确工具"
                "组合维修后返回 H；氧气只在舱外消耗。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        self._oxygen_cost = 0
        self._arrived_home = False
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "inspect":
            return self._inspect(action)
        if tool == "equip":
            return self._equip(action)
        if tool == "depressurize":
            return self._depressurize()
        if tool == "eva_exit":
            return self._eva_exit()
        if tool == "diagnose":
            return self._diagnose(action)
        if tool == "repair":
            return self._repair(action)
        if tool == "return_to_A":
            return self._return_to_a()
        if tool == "pressurize":
            return self._pressurize()
        self._cost = 0
        return "ACTION_NOT_ALLOWED"

    def _record_required(self, key: str, *, correct: bool, done: bool) -> None:
        self.required_attempted += 1
        if correct:
            self.required_correct += 1
        if done:
            self.required_done.add(key)

    def _reject_zero(self, code: str) -> str:
        self._cost = 0
        self._oxygen_cost = 0
        return code

    def _move(self, action: V8Action) -> str:
        target = action.to
        allowed = {
            frozenset({"H", "T"}),
            frozenset({"T", "A"}),
        }
        edge = frozenset({self.node, target}) if target else frozenset()
        if edge not in allowed:
            return self._reject_zero("NOT_ADJACENT")
        if self.node == "A" and self.pressure == "VACUUM":
            return self._reject_zero("AIRLOCK_NOT_PRESSURIZED")
        self.node = str(target)
        self._arrived_home = target == "H"
        return f"MOVED:{target}"

    def _inspect(self, action: V8Action) -> str:
        target = action.target
        if target == "equipment":
            correct = self.node == "T"
            self._record_required("equipment_inspected", correct=correct, done=correct)
            if not correct:
                return self._reject_zero("EQUIPMENT_NOT_AVAILABLE_HERE")
            self.equipment_inspected = True
            return "EQUIPMENT_INSPECTED"
        if target == "array":
            correct = self.node == "S" and self.oxygen >= 1
            self._record_required("array_inspected", correct=correct, done=correct)
            if self.node != "S":
                return self._reject_zero("INSPECTION_REQUIRED")
            if self.oxygen < 1:
                self._fail("OXYGEN_DEPLETED")
                return "OXYGEN_DEPLETED"
            self._cost = 1
            self._oxygen_cost = 1
            self.array_inspected = True
            return "ARRAY_OUTPUT_ZERO"
        return self._reject_zero("INVALID_INSPECT_TARGET")

    def _equip(self, action: V8Action) -> str:
        item = action.item_id
        if item not in TOOL_IDS:
            return self._reject_zero("INVALID_TOOL_ID")
        key = item
        if item == "safety_tether":
            correct = self.node == "A"
            self._record_required(key, correct=correct, done=correct)
            if not correct:
                return self._reject_zero("EQUIPMENT_NOT_AVAILABLE_HERE")
            if self.tether:
                return "TETHER_ATTACHED"
            self.tether = True
            return "TETHER_ATTACHED"
        correct = self.node == "T"
        self._record_required(key, correct=correct, done=correct)
        if not correct:
            return self._reject_zero("EQUIPMENT_NOT_AVAILABLE_HERE")
        if item == "eva_suit":
            self.suit = True
            return "SUIT_EQUIPPED"
        self.tools.add(item)
        return f"TOOL_EQUIPPED:{item}"

    def _depressurize(self) -> str:
        if self.node != "A":
            return self._reject_zero("AIRLOCK_PRECONDITION_FAILED")
        if not self.suit or self.outer_hatch != "CLOSED":
            return self._reject_zero("AIRLOCK_PRECONDITION_FAILED")
        self.pressure = "VACUUM"
        return "AIRLOCK_DEPRESSURIZED"

    def _eva_exit(self) -> str:
        if self.node != "A":
            return self._reject_zero("AIRLOCK_PRECONDITION_FAILED")
        if not self.suit:
            self._count("UNSUITED_EVA")
            self._fail("UNSUITED_EVA")
            self._cost = 0
            return "UNSUITED_EVA"
        if not self.tether:
            self._count("UNSAFE_UNTETHERED_EVA")
            self._fail("UNSAFE_UNTETHERED_EVA")
            self._cost = 0
            return "UNSAFE_UNTETHERED_EVA"
        if self.pressure != "VACUUM":
            return self._reject_zero("AIRLOCK_NOT_DEPRESSURIZED")
        self.node = "S"
        self._oxygen_cost = 1
        return "EVA_STARTED"

    def _diagnose(self, action: V8Action) -> str:
        correct = (
            self.node == "S"
            and self.array_inspected
            and "diagnostic_unit" in self.tools
            and self.oxygen >= 1
        )
        self._record_required("diagnosed", correct=correct, done=correct)
        if action.device_id != "diagnostic_unit":
            return self._reject_zero("INVALID_TOOL_ID")
        if self.node != "S":
            return self._reject_zero("DIAGNOSIS_REQUIRED")
        if not self.array_inspected:
            return self._reject_zero("INSPECTION_REQUIRED")
        if "diagnostic_unit" not in self.tools:
            return self._reject_zero("MISSING_REQUIRED_TOOL:diagnostic_unit")
        if self.oxygen < 1:
            self._fail("OXYGEN_DEPLETED")
            return "OXYGEN_DEPLETED"
        self._oxygen_cost = 1
        self.diagnosed = True
        return "DIAGNOSIS_COMPLETE"

    def _repair(self, action: V8Action) -> str:
        if action.target_id != "array_fuse_B":
            return self._reject_zero("INVALID_TARGET_ID")
        if action.tool_ids is None or not action.tool_ids:
            return self._reject_zero("INVALID_TOOL_ID")
        if any(item not in REPAIR_TOOLS for item in action.tool_ids):
            return self._reject_zero("INVALID_TOOL_ID")
        if len(set(action.tool_ids)) != len(action.tool_ids):
            return self._reject_zero("INVALID_TOOL_ID")
        if action.diagnosis_code not in (None, DIAGNOSIS):
            return self._reject_zero("INVALID_DIAGNOSIS_CODE")
        if self.node != "S":
            return self._reject_zero("ARRAY_NOT_REACHABLE")
        if self.oxygen < 3:
            return self._reject_zero("OXYGEN_RESERVE_REQUIRED_FOR_RETURN")
        self._cost = 2
        self._oxygen_cost = 2
        if not self.diagnosed:
            return "DIAGNOSIS_REQUIRED"
        if action.diagnosis_code != DIAGNOSIS:
            return "DIAGNOSIS_REQUIRED"
        missing = [item for item in REPAIR_TOOLS if item not in action.tool_ids]
        if missing:
            return f"MISSING_REQUIRED_TOOL:{missing[0]}"
        self.repaired = True
        return "ARRAY_REPAIRED"

    def _return_to_a(self) -> str:
        if self.node != "S":
            return self._reject_zero("RETURN_PRECONDITION_FAILED")
        if not self.suit or not self.tether:
            return self._reject_zero("RETURN_PRECONDITION_FAILED")
        if self.oxygen < 1:
            self._fail("OXYGEN_DEPLETED")
            return "OXYGEN_DEPLETED"
        self._oxygen_cost = 1
        self.node = "A"
        self.outer_hatch = "CLOSED"
        return "RETURNED_TO_A"

    def _pressurize(self) -> str:
        if self.node != "A" or self.pressure != "VACUUM":
            return self._reject_zero("PRESSURIZATION_PRECONDITION_FAILED")
        self.pressure = "PRESSURIZED"
        return "AIRLOCK_PRESSURIZED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        self.oxygen = max(0, self.oxygen - self._oxygen_cost)
        if self.status is not V8Status.RUNNING:
            return
        if self.node == "S" and self.oxygen == 0:
            self._fail("OXYGEN_DEPLETED")
            return
        if self.node == "H" and self._arrived_home:
            self._arrived_home = False
            if self.repaired:
                self._succeed("ALL_OBJECTIVES_COMPLETE")
            else:
                self._fail("OBJECTIVE_INCOMPLETE_AT_H")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "location": self.node,
            "oxygen": self.oxygen,
            "pressure": self.pressure,
            "suit": self.suit,
            "tools": sorted(self.tools),
            "tether": self.tether,
            "equipment_inspected": self.equipment_inspected,
            "array_inspected": self.array_inspected,
            "diagnosed": self.diagnosed,
            "repaired": self.repaired,
            "required_done": sorted(self.required_done),
            "required_attempted": self.required_attempted,
            "required_correct": self.required_correct,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "map25.required_check_coverage": {
                "numerator": len(self.required_done),
                "denominator": len(REQUIRED_STEPS),
            },
            "map25.dependency_order_correctness": (
                None
                if self.required_attempted == 0
                else {
                    "numerator": self.required_correct,
                    "denominator": self.required_attempted,
                }
            ),
            "map25.unsafe_eva_attempts": self.counters.get("UNSUITED_EVA", 0)
            + self.counters.get("UNSAFE_UNTETHERED_EVA", 0),
            "map25.oxygen_shortfall": int(self.terminal_reason == "OXYGEN_DEPLETED"),
        }


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "inspect_then_equip",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "T"},
            {"tool": "inspect", "target": "equipment"},
            {"tool": "equip", "item_id": "diagnostic_unit"},
            {"tool": "equip", "item_id": "wrench"},
            {"tool": "equip", "item_id": "eva_suit"},
            {"tool": "move", "to": "A"},
            {"tool": "equip", "item_id": "safety_tether"},
            {"tool": "depressurize"},
            {"tool": "eva_exit"},
            {"tool": "inspect", "target": "array"},
            {"tool": "diagnose", "device_id": "diagnostic_unit"},
            {
                "tool": "repair",
                "target_id": "array_fuse_B",
                "tool_ids": ["diagnostic_unit", "wrench"],
                "diagnosis_code": DIAGNOSIS,
            },
            {"tool": "return_to_A"},
            {"tool": "pressurize"},
            {"tool": "move", "to": "T"},
            {"tool": "move", "to": "H"},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "suit_first",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "T"},
            {"tool": "equip", "item_id": "eva_suit"},
            {"tool": "equip", "item_id": "wrench"},
            {"tool": "equip", "item_id": "diagnostic_unit"},
            {"tool": "inspect", "target": "equipment"},
            {"tool": "move", "to": "A"},
            {"tool": "equip", "item_id": "safety_tether"},
            {"tool": "depressurize"},
            {"tool": "eva_exit"},
            {"tool": "inspect", "target": "array"},
            {"tool": "diagnose", "device_id": "diagnostic_unit"},
            {
                "tool": "repair",
                "target_id": "array_fuse_B",
                "tool_ids": ["diagnostic_unit", "wrench"],
                "diagnosis_code": DIAGNOSIS,
            },
            {"tool": "return_to_A"},
            {"tool": "pressurize"},
            {"tool": "move", "to": "T"},
            {"tool": "move", "to": "H"},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "standard_sequence",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map25.required_check_coverage": 1.0,
            "map25.dependency_order_correctness": 1.0,
            "map25.unsafe_eva_attempts": 0,
            "map25.oxygen_shortfall": 0,
        },
    },
    {
        "name": "unsuited_eva_is_terminal",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "T"},
            {"tool": "move", "to": "A"},
            {"tool": "eva_exit"},
        ],
        "expect": {
            "map25.required_check_coverage": 0.0,
            "map25.dependency_order_correctness": None,
            "map25.unsafe_eva_attempts": 1,
            "map25.oxygen_shortfall": 0,
        },
    },
    {
        "name": "untethered_eva_keeps_partial_coverage",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "T"},
            {"tool": "equip", "item_id": "eva_suit"},
            {"tool": "equip", "item_id": "diagnostic_unit"},
            {"tool": "equip", "item_id": "wrench"},
            {"tool": "move", "to": "A"},
            {"tool": "depressurize"},
            {"tool": "eva_exit"},
        ],
        "expect": {
            "map25.required_check_coverage": 0.428571,
            "map25.dependency_order_correctness": 1.0,
            "map25.unsafe_eva_attempts": 1,
            "map25.oxygen_shortfall": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map25Environment"]
