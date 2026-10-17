"""MAP-27｜月面联合行动：两格货舱、一次性电芯与两阶段救援的长程协调。

本图与同世界另两图的机制差异：MAP-25 是单人顺序合规（穿服/挂绳/诊断），没有
货舱、电池和远程救援；MAP-26 是隐藏故障的诊断-反馈-回滚循环。本图没有隐藏故障
（中继 OFFLINE 是公开状态），难度来自两格货舱里互斥工具的先后、14 电与 18 氧按
道路原子并行消耗、P–E 四 tick 远路与 S–E 一 tick 短路的选择，以及“现场稳定 ≠
完成救援”的两阶段救援（稳定 → 中继在线后才可远程撤离）。

动作契约（``SHAPES`` 精确声明）：
- ``load(item_id)``：样本容器只在 B，医疗包与维修盒只在 S；各占 1 格。
- ``drive(to)``：沿 ``EDGES`` 双向道路移动，tick/电池/氧气成本等于道路成本。
- ``charge()``：只在 S，2 tick，补 4 且硬封顶 14，消耗唯一电芯。
- ``repair_relay()``：只在 R，携带维修盒，2 tick，成功后永久在线并消耗维修盒。
- ``sample(item_id)``：只在 P，携带样本容器，1 tick，容器仍占 1 格。
- ``rescue(operation, item_id?)``：``field_stabilize`` 只在 E 且消耗医疗包；
  ``remote_evacuation`` 可在 R 或 E，要求中继在线且伤员已稳定。
- ``submit()``：只在 B，0 tick，按四个目标与正氧气一次性终局。

失败码沿用 ``worlds/v4/MAP-27/map_spec.yaml``：``ITEM_NOT_AVAILABLE_HERE``、
``CARGO_CAPACITY_EXCEEDED``、``EDGE_NOT_ADJACENT``、``BATTERY_INSUFFICIENT``、
``VEHICLE_STRANDED``、``CREW_OXYGEN_DEPLETED``、``CHARGER_EMPTY``、
``BATTERY_ALREADY_FULL``、``RELAY_TOOL_REQUIRED``、``RELAY_ALREADY_ONLINE``、
``SAMPLE_CONTAINER_REQUIRED``、``MEDICAL_KIT_REQUIRED``、``RELAY_OFFLINE``、
``CASUALTY_NOT_STABILIZED``、``OBJECTIVES_INCOMPLETE_AT_BASE``。本运行时按 V7 卡片
的未决项统一了载荷/能源冲突：货舱装满时的 ``load`` 与货舱无空位时的 ``charge`` 都
返回 ``RESOURCE_CONFLICT``（设计中的具体码 ``CARGO_CAPACITY_EXCEEDED`` 与
``CHARGE_SLOT_CONFLICT`` 保存在 ``judge_state()`` 的违规账里，两种冲突都不改动状态）。

指标口径（与 ``docs/v7/maps/MAP-27.md`` 一致）：
- ``map27.joint_task_completion_rate``：分子 = 中继在线 + 伤员 RESCUED + 样本 SEALED
  三项已完成数，分母固定 3；未提交按已完成项计。
- ``map27.critical_path_delay``：成功终局 tick 数 − 手写较快方案 B 的 20 tick；
  未成功 → ``None``（N/A）。
- ``map27.communication_blackout_ticks``：中继 OFFLINE 期间推进的 tick 数；修复动作
  自身的 2 tick 计入，修复完成当 tick 起不再计入。
- ``map27.resource_conflicts``：统一载荷/能源冲突 ``RESOURCE_CONFLICT`` 的次数
  （货舱溢出 + 充电无空货位；V7 卡片公式的两种来源）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map27Environment(MapEnvironment):
    map_id = "MAP-27"
    title = "月面联合行动"
    world = "lunar"
    level = "困难"
    EDGES = {
        "B_S": ("B", "S"),
        "S_R": ("S", "R"),
        "R_P": ("R", "P"),
        "P_E": ("P", "E"),
        "S_E": ("S", "E"),
    }
    #: 每段道路的 tick、电池与氧气成本相等。
    EDGE_COST = {"B_S": 1, "S_R": 2, "R_P": 2, "P_E": 4, "S_E": 1}
    SHAPES: dict[str, set[frozenset[str]]] = {
        "load": {frozenset({"tool", "item_id"})},
        "drive": {frozenset({"tool", "to"})},
        "charge": {frozenset({"tool"})},
        "repair_relay": {frozenset({"tool"})},
        "sample": {frozenset({"tool", "item_id"})},
        "rescue": {
            frozenset({"tool", "operation", "item_id"}),
            frozenset({"tool", "operation"}),
        },
        "submit": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "local_edges",
            "tick",
            "battery",
            "battery_capacity",
            "oxygen",
            "cargo",
            "cargo_capacity",
            "supplies_here",
            "charger_cells_remaining",
            "relay_state",
            "sample_state",
            "survivor_state",
            "crew_alive",
            "objectives",
            "goal",
        }
    )
    BATTERY_CAPACITY = 14
    CARGO_CAPACITY = 2
    CHARGE_GAIN = 4
    #: 手写较快方案 B 的参考关键路径；不是求解器最优证明。
    REFERENCE_CRITICAL_PATH = 20
    SAMPLE_CONTAINER = "sample_container"
    MEDICAL_KIT = "medical_kit"
    RELAY_KIT = "relay_repair_kit"

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "B"
        self.items = []
        self.battery = self.BATTERY_CAPACITY
        self.oxygen = 18
        self.stock = {self.SAMPLE_CONTAINER: 1, self.MEDICAL_KIT: 1, self.RELAY_KIT: 1}
        self.charge_cells = 1
        self.relay_state = "OFFLINE"
        self.sample_state = "UNSAMPLED"
        self.survivor_state = "UNSUPPORTED"
        self.crew_alive = True
        self.blackout_ticks = 0
        self.cargo_errors = 0
        self.resource_conflict_errors = 0
        self.charge_cells_used = 0
        self.objective_ticks: dict[str, int | None] = {
            "relay_online": None,
            "survivor_rescued": None,
            "sample_sealed": None,
            "sample_at_base": None,
        }
        self._pending_cost = 0

    # ------------------------------------------------------- objective ledger
    def _objectives(self) -> dict[str, bool]:
        return {
            "relay_online": self.relay_state == "ONLINE",
            "survivor_rescued": self.survivor_state == "RESCUED",
            "sample_sealed": self.sample_state == "SEALED",
            "sample_at_base": self.node == "B" and self.sample_state == "SEALED",
        }

    def _record_objectives(self) -> None:
        completed_at = self.tick_count + self._pending_cost
        for name, done in self._objectives().items():
            if done and self.objective_ticks[name] is None:
                self.objective_ticks[name] = completed_at

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        supplies: dict[str, int] = {}
        if self.node == "B":
            supplies[self.SAMPLE_CONTAINER] = self.stock[self.SAMPLE_CONTAINER]
        if self.node == "S":
            supplies[self.MEDICAL_KIT] = self.stock[self.MEDICAL_KIT]
            supplies[self.RELAY_KIT] = self.stock[self.RELAY_KIT]
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "local_edges": [
                {
                    "edge_id": edge_id,
                    "to": self.edge_destination(edge_id),
                    "ticks": self.EDGE_COST[edge_id],
                    "battery": self.EDGE_COST[edge_id],
                    "oxygen": self.EDGE_COST[edge_id],
                }
                for edge_id in self.visible_edges()
            ],
            "tick": self.tick_count,
            "battery": self.battery,
            "battery_capacity": self.BATTERY_CAPACITY,
            "oxygen": self.oxygen,
            "cargo": [{"item_id": item, "slots": 1} for item in self.items],
            "cargo_capacity": self.CARGO_CAPACITY,
            "supplies_here": supplies,
            "charger_cells_remaining": self.charge_cells if self.node == "S" else None,
            "relay_state": self.relay_state,
            "sample_state": self.sample_state,
            "survivor_state": self.survivor_state,
            "crew_alive": self.crew_alive,
            "objectives": self._objectives(),
            "goal": (
                "在 B 提交：样本已封存回基地、伤员经中继远程撤离、中继在线、"
                "全员存活且余氧大于 0。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_cost = 0
        offline_at_start = self.relay_state != "ONLINE"
        result = self._dispatch(action)
        if offline_at_start:
            self.blackout_ticks += self._pending_cost
        self._record_objectives()
        return result

    def _dispatch(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "load":
            return self._load(action)
        if tool == "drive":
            return self._drive(action)
        if tool == "charge":
            return self._charge()
        if tool == "repair_relay":
            return self._repair_relay()
        if tool == "sample":
            return self._sample(action)
        if tool == "rescue":
            return self._rescue(action)
        if tool == "submit":
            return self._submit()
        return "ACTION_NOT_ALLOWED"

    def _load(self, action: V8Action) -> str:
        item = action.item_id
        if item not in self.stock:
            return "ITEM_NOT_AVAILABLE_HERE"
        home = "B" if item == self.SAMPLE_CONTAINER else "S"
        if self.node != home or self.stock[item] <= 0:
            return "ITEM_NOT_AVAILABLE_HERE"
        if len(self.items) + 1 > self.CARGO_CAPACITY:
            self.cargo_errors += 1
            self._violate("CARGO_CAPACITY_EXCEEDED")
            return "RESOURCE_CONFLICT"
        self.stock[item] -= 1
        self.items.append(item)
        self._pending_cost = 1
        return f"LOAD_SUCCEEDED:{item}"

    def _drive(self, action: V8Action) -> str:
        edge_id = self._edge_id(action.to)
        if edge_id is None:
            return "EDGE_NOT_ADJACENT"
        cost = self.EDGE_COST[edge_id]
        if self.battery < cost:
            self._fail("VEHICLE_STRANDED")
            return "BATTERY_INSUFFICIENT"
        self._pending_cost = cost
        self.battery -= cost
        self.oxygen -= cost
        self.node = self.edge_destination(edge_id) or self.node
        if self.oxygen <= 0:
            self.crew_alive = False
            self._fail("CREW_OXYGEN_DEPLETED")
            return "CREW_OXYGEN_DEPLETED"
        if self.node != "B" and self._min_energy_to_base(self.node) > self.battery:
            self._fail("VEHICLE_STRANDED")
            return "VEHICLE_STRANDED"
        return "DRIVE_SUCCEEDED"

    def _charge(self) -> str:
        if self.node != "S":
            return "INVALID_LOCATION"
        if self.charge_cells <= 0:
            return "CHARGER_EMPTY"
        if self.battery >= self.BATTERY_CAPACITY:
            return "BATTERY_ALREADY_FULL"
        if len(self.items) >= self.CARGO_CAPACITY:
            self.resource_conflict_errors += 1
            self._violate("CHARGE_SLOT_CONFLICT")
            return "RESOURCE_CONFLICT"
        self.battery = min(self.BATTERY_CAPACITY, self.battery + self.CHARGE_GAIN)
        self.charge_cells -= 1
        self.charge_cells_used += 1
        self._pending_cost = 2
        return "CHARGED"

    def _repair_relay(self) -> str:
        if self.node != "R":
            return "INVALID_LOCATION"
        if self.relay_state == "ONLINE":
            return "RELAY_ALREADY_ONLINE"
        if self.RELAY_KIT not in self.items:
            return "RELAY_TOOL_REQUIRED"
        self.items.remove(self.RELAY_KIT)
        self.relay_state = "ONLINE"
        self._pending_cost = 2
        return "RELAY_REPAIRED"

    def _sample(self, action: V8Action) -> str:
        if self.node != "P":
            return "INVALID_LOCATION"
        if action.item_id != self.SAMPLE_CONTAINER:
            return "SAMPLE_CONTAINER_REQUIRED"
        if self.SAMPLE_CONTAINER not in self.items:
            return "SAMPLE_CONTAINER_REQUIRED"
        if self.sample_state == "SEALED":
            return "SAMPLE_ALREADY_SEALED"
        self.sample_state = "SEALED"
        self._pending_cost = 1
        return "SAMPLE_SEALED"

    def _rescue(self, action: V8Action) -> str:
        mode = action.operation
        if mode == "field_stabilize":
            if self.node != "E":
                return "INVALID_LOCATION"
            if self.MEDICAL_KIT not in self.items:
                return "MEDICAL_KIT_REQUIRED"
            if self.survivor_state != "UNSUPPORTED":
                return "CASUALTY_ALREADY_STABILIZED"
            self.items.remove(self.MEDICAL_KIT)
            self.survivor_state = "STABILIZED"
            self._pending_cost = 1
            return "CASUALTY_STABILIZED"
        if mode == "remote_evacuation":
            if self.node not in {"R", "E"}:
                return "INVALID_LOCATION"
            if self.relay_state != "ONLINE":
                return "RELAY_OFFLINE"
            if self.survivor_state == "RESCUED":
                return "REMOTE_EVACUATION_ALREADY_COMPLETE"
            if self.survivor_state != "STABILIZED":
                return "CASUALTY_NOT_STABILIZED"
            self.survivor_state = "RESCUED"
            self._pending_cost = 1
            return "REMOTE_EVACUATION_COMPLETE"
        return "ACTION_NOT_ALLOWED"

    def _submit(self) -> str:
        if self.node != "B":
            return "INVALID_LOCATION"
        if (
            self.sample_state == "SEALED"
            and self.survivor_state == "RESCUED"
            and self.relay_state == "ONLINE"
            and self.crew_alive
            and self.oxygen > 0
        ):
            self._succeed("ALL_OBJECTIVES_COMPLETE")
            return "ALL_OBJECTIVES_COMPLETE"
        self._fail("OBJECTIVES_INCOMPLETE_AT_BASE")
        return "OBJECTIVES_INCOMPLETE_AT_BASE"

    # ------------------------------------------------------------------ helpers
    def _edge_id(self, target: str | None) -> str | None:
        if target is None:
            return None
        for edge_id in self.visible_edges():
            if self.edge_destination(edge_id) == target:
                return edge_id
        return None

    def _min_energy_to_base(self, node: str) -> int:
        """Minimum battery needed to drive from ``node`` back to B."""

        best: dict[str, int] = {node: 0}
        frontier: list[tuple[int, str]] = [(0, node)]
        while frontier:
            frontier.sort(reverse=True)
            cost, here = frontier.pop()
            if cost != best[here]:
                continue
            if here == "B":
                return cost
            for edge_id, (a, b) in self.EDGES.items():
                if here not in (a, b):
                    continue
                there = b if a == here else a
                candidate = cost + self.EDGE_COST[edge_id]
                if candidate < best.get(there, 10**9):
                    best[there] = candidate
                    frontier.append((candidate, there))
        return 10**9

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._pending_cost

    def _invalid_action(self) -> str:
        if self.relay_state != "ONLINE":
            self.blackout_ticks += 1
        return "INVALID_ACTION_SCHEMA"

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "battery": self.battery,
            "oxygen": self.oxygen,
            "cargo": list(self.items),
            "stock": dict(self.stock),
            "charge_cells": self.charge_cells,
            "relay_state": self.relay_state,
            "sample_state": self.sample_state,
            "survivor_state": self.survivor_state,
            "crew_alive": self.crew_alive,
            "blackout_ticks": self.blackout_ticks,
            "cargo_errors": self.cargo_errors,
            "resource_conflict_errors": self.resource_conflict_errors,
            "charge_cells_used": self.charge_cells_used,
            "objectives": self._objectives(),
            "objective_ticks": dict(self.objective_ticks),
            "partial_completion": [
                name for name, done in self._objectives().items() if done
            ],
            "violations": dict(self.violations),
        }

    def metrics(self) -> dict[str, Any]:
        completed = sum(
            (
                self.relay_state == "ONLINE",
                self.survivor_state == "RESCUED",
                self.sample_state == "SEALED",
            )
        )
        delay: int | None = None
        if self.is_success:
            delay = max(0, self.tick_count - self.REFERENCE_CRITICAL_PATH)
        return {
            "map27.joint_task_completion_rate": {
                "numerator": completed,
                "denominator": 3,
            },
            "map27.critical_path_delay": delay,
            "map27.communication_blackout_ticks": self.blackout_ticks,
            "map27.resource_conflicts": self.cargo_errors + self.resource_conflict_errors,
        }


#: 方案 A：先修中继，再带医疗包走 P–E 远路（25 tick，余电 0、余氧 3）。
_RELAY_FIRST = [
    {"tool": "load", "item_id": "sample_container"},
    {"tool": "drive", "to": "S"},
    {"tool": "charge"},
    {"tool": "load", "item_id": "relay_repair_kit"},
    {"tool": "drive", "to": "R"},
    {"tool": "repair_relay"},
    {"tool": "drive", "to": "S"},
    {"tool": "load", "item_id": "medical_kit"},
    {"tool": "drive", "to": "R"},
    {"tool": "drive", "to": "P"},
    {"tool": "sample", "item_id": "sample_container"},
    {"tool": "drive", "to": "E"},
    {"tool": "rescue", "operation": "field_stabilize", "item_id": "medical_kit"},
    {"tool": "rescue", "operation": "remote_evacuation"},
    {"tool": "drive", "to": "S"},
    {"tool": "drive", "to": "B"},
    {"tool": "submit"},
]

#: 方案 B：先稳定伤员，再用短路回 S 取维修盒（20 tick，余电 2、余氧 6，不充电）。
_STABILIZE_FIRST = [
    {"tool": "load", "item_id": "sample_container"},
    {"tool": "drive", "to": "S"},
    {"tool": "load", "item_id": "medical_kit"},
    {"tool": "drive", "to": "E"},
    {"tool": "rescue", "operation": "field_stabilize", "item_id": "medical_kit"},
    {"tool": "drive", "to": "S"},
    {"tool": "load", "item_id": "relay_repair_kit"},
    {"tool": "drive", "to": "R"},
    {"tool": "repair_relay"},
    {"tool": "rescue", "operation": "remote_evacuation"},
    {"tool": "drive", "to": "P"},
    {"tool": "sample", "item_id": "sample_container"},
    {"tool": "drive", "to": "R"},
    {"tool": "drive", "to": "S"},
    {"tool": "drive", "to": "B"},
    {"tool": "submit"},
]

ORACLE_CASES = (
    {
        "trace_id": "relay_first_remote_road",
        "seed": 0,
        "actions": _RELAY_FIRST,
        "expect_success": True,
    },
    {
        "trace_id": "stabilize_first_short_road",
        "seed": 0,
        "actions": _STABILIZE_FIRST,
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "stabilize_first_full_success",
        "seed": 0,
        "actions": _STABILIZE_FIRST,
        # 手算：3/3 任务完成；20−20=0 延误；中继在 tick 11 上线，离线推进 11 tick。
        "expect": {
            "map27.joint_task_completion_rate": 1.0,
            "map27.critical_path_delay": 0,
            "map27.communication_blackout_ticks": 11,
            "map27.resource_conflicts": 0,
        },
    },
    {
        "name": "cargo_and_charger_slot_conflict",
        "seed": 0,
        "actions": [
            {"tool": "load", "item_id": "sample_container"},
            {"tool": "drive", "to": "S"},
            {"tool": "load", "item_id": "medical_kit"},
            {"tool": "load", "item_id": "relay_repair_kit"},
            {"tool": "charge"},
        ],
        # 手算：第三个 load 恰好在货舱满时被拒；随后 charge 没有空货位放电池 →
        # 两次都返回 RESOURCE_CONFLICT（具体子码进 judge_state 违规账），共 2 次；
        # 无任务完成。具体 tick：load 1 + drive 1 + load 1 = 3，两次失败均 0 tick。
        "expect": {
            "map27.joint_task_completion_rate": 0.0,
            "map27.critical_path_delay": None,
            "map27.communication_blackout_ticks": 3,
            "map27.resource_conflicts": 2,
        },
    },
    {
        "name": "remote_road_without_charge_is_stranded",
        "seed": 0,
        "actions": [
            {"tool": "load", "item_id": "sample_container"},
            {"tool": "drive", "to": "S"},
            {"tool": "load", "item_id": "relay_repair_kit"},
            {"tool": "drive", "to": "R"},
            {"tool": "repair_relay"},
            {"tool": "drive", "to": "S"},
            {"tool": "load", "item_id": "medical_kit"},
            {"tool": "drive", "to": "R"},
            {"tool": "drive", "to": "P"},
            {"tool": "sample", "item_id": "sample_container"},
            {"tool": "drive", "to": "E"},
        ],
        # 手算：14−1−2−2−2−2−4=1 电抵 E，而 E–S–B 最低需 2 → VEHICLE_STRANDED；
        # 中继在线、样本已封存 → 2/3；中继在 tick 9 上线，离线推进 7 tick。
        "expect": {
            "map27.joint_task_completion_rate": 0.666667,
            "map27.critical_path_delay": None,
            "map27.communication_blackout_ticks": 7,
            "map27.resource_conflicts": 0,
        },
    },
)


__all__ = ["FIXTURES", "Map27Environment", "ORACLE_CASES"]
