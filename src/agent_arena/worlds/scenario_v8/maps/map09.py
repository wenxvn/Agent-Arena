"""MAP-09｜深海连锁故障：漏水、电量、供氧与通信四条链的跨系统耦合。

本图与同世界另两图的机制差异：MAP-07 只有单一水路内部的顺序转移，水位直接可见、
动作只改变水量；MAP-08 用主动测试缩小隐藏漏点假设集。本图没有隐藏故障位置，难点
是同一 tick 内的资源循环——E-P 漏水会把泵房水推进动力舱并短路，抽水消耗刚好够
发报的电量，断电只影响供氧线路而不回充电池，供氧稳定计数又决定能否发报。

指标口径（与 docs/v7/maps/MAP-09.md 一致）：
- ``stable_time_ratio`` = 满足 ``water_E<=4 且 oxygen_reserve>0`` 的已结算 tick 数 /
  全部已结算 tick；未行动（0 tick）时分母为 0，即 N/A。
- ``fault_propagation_scale`` = 首个故障后进入不安全/不可达状态的子系统数
  （E 短路、氧耗尽、P 被弃置）。完全没有故障事件时返回 None（N/A）。
- ``hard_threshold_breaches`` = 1[water_E>4] + 1[oxygen_reserve<=0] +
  1[INSUFFICIENT_TRANSMIT_POWER]；每个 episode 每项最多计一次。
- ``repair_dependency_violations`` = 前置条件不足而被拒的修复/开机/补氧/发报尝试数。
- ``repair_actions`` = 成功执行的封舱、抽水、修线、开氧、补氧动作数。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map09Environment(MapEnvironment):
    map_id = "MAP-09"
    title = "深海连锁故障"
    world = "abyss"
    level = "困难"
    EDGES = {
        "E_P": ("E", "P"),
        "P_O": ("P", "O"),
        "O_C": ("O", "C"),
        "C_E": ("C", "E"),
        "E_C_EMERGENCY": ("E", "C"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target_id"})},
        "interact": {
            frozenset({"tool", "target_id", "operation"}),
            frozenset({"tool", "target_id", "operation", "arguments"}),
        },
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "battery",
            "water_P",
            "water_E",
            "bulkhead_state",
            "p_sacrificed",
            "generator_online",
            "oxygen_reserve",
            "oxygen_support_on",
            "oxygen_stable_ticks",
            "packet_complete",
            "goal",
        }
    )
    SHORT_CIRCUIT_LIMIT = 4
    PUMP_WATER_PER_STROKE = 2
    PUMP_BATTERY_COST = 1
    PACKET_BATTERY_COST = 3
    PACKET_TRANSMIT_TICKS = 2
    PACKET_STABLE_REQUIRED = 2
    OXYGEN_FULL = 12

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "E"
        self.items = []
        self.battery = 5
        self.water_P = 5
        self.water_E = 3
        self.bulkhead_closed = False
        self.p_sacrificed = False
        self.generator_online = False
        self.oxygen_reserve = self.OXYGEN_FULL
        self.oxygen_support_on = False
        self.oxygen_stable_ticks = 0
        self.packet_complete = False

        self.repair_actions = 0
        self.safe_ticks = 0
        self.valid_ticks = 0
        self.short_circuit = False
        self.oxygen_depleted = False
        self.transmit_power_failed = False
        self._sending = False
        self._pending_failure: str | None = None
        self._last_cost = 1

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "battery": self.battery,
            "water_P": self.water_P,
            "water_E": self.water_E,
            "bulkhead_state": "closed" if self.bulkhead_closed else "open",
            "p_sacrificed": self.p_sacrificed,
            "generator_online": self.generator_online,
            "oxygen_reserve": self.oxygen_reserve,
            "oxygen_support_on": self.oxygen_support_on,
            "oxygen_stable_ticks": self.oxygen_stable_ticks,
            "packet_complete": self.packet_complete,
            "goal": "封住漏水、恢复发电主线与供氧，并在 C 发出完整两 tick 求救包。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._sending = False
        self._pending_failure = None
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "inspect":
            return self._inspect(action)
        if tool == "wait":
            return "WAITED" if action.ticks else "INVALID_ACTION_SCHEMA"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        if action.edge_id is None:
            return "INVALID_ACTION_SCHEMA"
        if self.p_sacrificed and self._edge_touches_p(action.edge_id):
            return "P_UNREACHABLE"
        destination, result = self.move_edge(action.edge_id)
        return result if destination is not None else "EDGE_NOT_ADJACENT"

    def _edge_touches_p(self, edge_id: str) -> bool:
        edge = self.EDGES.get(edge_id)
        return edge is not None and "P" in edge

    def _inspect(self, action: V8Action) -> str:
        if action.target_id == "water_gauges":
            return f"WATER:P={self.water_P},E={self.water_E}"
        if action.target_id == "power_panel":
            return f"POWER:battery={self.battery},generator={self.generator_online}"
        if action.target_id == "oxygen_panel":
            return (
                f"OXYGEN:reserve={self.oxygen_reserve},support={self.oxygen_support_on},"
                f"stable={self.oxygen_stable_ticks}"
            )
        return "TARGET_NOT_VISIBLE"

    def _interact(self, action: V8Action) -> str:
        operation = action.operation
        if operation == "isolate_compartment":
            return self._isolate(action)
        if operation == "pump_once":
            return self._pump(action)
        if operation == "restore_power_line":
            return self._restore_power(action)
        if operation == "restart_oxygen":
            return self._restart_oxygen(action)
        if operation == "replenish_oxygen":
            return self._replenish_oxygen(action)
        if operation == "send_distress_packet":
            return self._send_packet(action)
        return "INVALID_OPERATION"

    def _isolate(self, action: V8Action) -> str:
        if action.target_id != "bulkhead_E_P" or self.node != "E":
            return "INVALID_LOCATION"
        mode = (action.arguments or {}).get("mode")
        if mode not in {"preserve", "sacrifice"}:
            return "INVALID_OPERATION"
        if self.bulkhead_closed:
            return "BULKHEAD_ALREADY_CLOSED"
        self.bulkhead_closed = True
        if mode == "sacrifice":
            self.p_sacrificed = True
        self.repair_actions += 1
        return "BULKHEAD_CLOSED_PRESERVE" if mode == "preserve" else "BULKHEAD_CLOSED_SACRIFICE"

    def _pump(self, action: V8Action) -> str:
        if action.target_id != "pump" or self.node != "P":
            return "INVALID_LOCATION"
        if self.p_sacrificed:
            return "P_UNREACHABLE"
        if self.battery < self.PUMP_BATTERY_COST:
            return "INSUFFICIENT_PUMP_POWER"
        self.battery -= self.PUMP_BATTERY_COST
        self.water_P = max(0, self.water_P - self.PUMP_WATER_PER_STROKE)
        self.repair_actions += 1
        return f"PUMPED:P={self.water_P}"

    def _restore_power(self, action: V8Action) -> str:
        if action.target_id != "power_line" or self.node != "E":
            return "INVALID_LOCATION"
        if self.generator_online:
            return "GENERATOR_ALREADY_ONLINE"
        if self.water_E > self.SHORT_CIRCUIT_LIMIT:
            self._violate("repair_dependency")
            return "REPAIR_DEPENDENCY_VIOLATION"
        self.generator_online = True
        self.repair_actions += 1
        return "POWER_LINE_RESTORED"

    def _restart_oxygen(self, action: V8Action) -> str:
        if action.target_id != "oxygen_system" or self.node != "O":
            return "INVALID_LOCATION"
        if not self.generator_online:
            self._violate("repair_dependency")
            return "REPAIR_DEPENDENCY_VIOLATION"
        if self.oxygen_support_on:
            return "OXYGEN_ALREADY_ON"
        self.oxygen_support_on = True
        self.repair_actions += 1
        return "OXYGEN_RESTARTED"

    def _replenish_oxygen(self, action: V8Action) -> str:
        if action.target_id != "oxygen_system" or self.node != "O":
            return "INVALID_LOCATION"
        if not self.oxygen_support_on:
            self._violate("repair_dependency")
            return "REPAIR_DEPENDENCY_VIOLATION"
        self.oxygen_reserve = self.OXYGEN_FULL
        self.repair_actions += 1
        return "OXYGEN_REPLENISHED"

    def _send_packet(self, action: V8Action) -> str:
        if action.target_id != "radio" or self.node != "C":
            return "INVALID_LOCATION"
        if not self.generator_online:
            self._violate("repair_dependency")
            return "REPAIR_DEPENDENCY_VIOLATION"
        if self.oxygen_stable_ticks < self.PACKET_STABLE_REQUIRED:
            self._violate("repair_dependency")
            return "OXYGEN_NOT_STABLE"
        if self.battery < self.PACKET_BATTERY_COST:
            # 门槛校验耗 1 tick，之后以电量不足终止，且不扣剩余电量。
            self._pending_failure = "INSUFFICIENT_TRANSMIT_POWER"
            return "TRANSMIT_POWER_CHECK_FAILED"
        self.battery -= self.PACKET_BATTERY_COST
        self._sending = True
        return "TRANSMITTING_DISTRESS_PACKET"

    def _action_cost(self, action: V8Action) -> int:
        if self._sending:
            cost = self.PACKET_TRANSMIT_TICKS
        elif action.tool == "wait":
            cost = action.ticks or 1
        else:
            cost = 1
        self._last_cost = cost
        return cost

    # ------------------------------------------------------------------ per tick
    def _after_tick(self) -> None:
        for index in range(self._last_cost):
            last = index == self._last_cost - 1
            if not self.bulkhead_closed and self.water_P > 0:
                self.water_P -= 1
                self.water_E += 1
            if self.oxygen_support_on:
                self.oxygen_stable_ticks += 1
            else:
                self.oxygen_reserve -= 1

            self.valid_ticks += 1
            if self.water_E <= self.SHORT_CIRCUIT_LIMIT and self.oxygen_reserve > 0:
                self.safe_ticks += 1
            if self.water_E > self.SHORT_CIRCUIT_LIMIT:
                self.short_circuit = True
                self._fail("SHORT_CIRCUIT")
                return
            if self.oxygen_reserve <= 0:
                self.oxygen_depleted = True
                self._fail("OXYGEN_DEPLETED")
                return
            if last and self._pending_failure is not None:
                reason = self._pending_failure
                if reason == "INSUFFICIENT_TRANSMIT_POWER":
                    self.transmit_power_failed = True
                self._fail(reason)
                return
            if last and self._sending:
                if (
                    self.oxygen_support_on
                    and self.oxygen_stable_ticks >= self.PACKET_STABLE_REQUIRED
                ):
                    self.packet_complete = True
                    self._succeed("DISTRESS_PACKET_SENT")
                else:
                    self._violate("packet_interrupted")
                return

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "battery": self.battery,
            "water_P": self.water_P,
            "water_E": self.water_E,
            "bulkhead_closed": self.bulkhead_closed,
            "p_sacrificed": self.p_sacrificed,
            "generator_online": self.generator_online,
            "oxygen_reserve": self.oxygen_reserve,
            "oxygen_support_on": self.oxygen_support_on,
            "oxygen_stable_ticks": self.oxygen_stable_ticks,
            "packet_complete": self.packet_complete,
            "repair_actions": self.repair_actions,
            "safe_ticks": self.safe_ticks,
            "valid_ticks": self.valid_ticks,
            "short_circuit": self.short_circuit,
            "oxygen_depleted": self.oxygen_depleted,
            "transmit_power_failed": self.transmit_power_failed,
            "violations": dict(self.violations),
        }

    def _fault_propagation_scale(self) -> int | None:
        subsystems = [self.short_circuit, self.oxygen_depleted, self.p_sacrificed]
        any_fault = any(subsystems) or self.transmit_power_failed
        if not any_fault:
            return None
        return sum(1 for flag in subsystems if flag)

    def metrics(self) -> dict[str, Any]:
        return {
            "map09.fault_propagation_scale": self._fault_propagation_scale(),
            "map09.hard_threshold_breaches": (
                int(self.short_circuit)
                + int(self.oxygen_depleted)
                + int(self.transmit_power_failed)
            ),
            "map09.repair_actions": self.repair_actions,
            "map09.repair_dependency_violations": self.violations.get(
                "repair_dependency", 0
            ),
            "map09.stable_time_ratio": {
                "numerator": self.safe_ticks,
                "denominator": self.valid_ticks,
            },
        }


ORACLE_CASES = (
    {
        "trace_id": "preserve_and_pump",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {
                "tool": "interact",
                "target_id": "bulkhead_E_P",
                "operation": "isolate_compartment",
                "arguments": {"mode": "preserve"},
            },
            {"tool": "move", "edge_id": "E_P"},
            {"tool": "interact", "target_id": "pump", "operation": "pump_once"},
            {"tool": "interact", "target_id": "pump", "operation": "pump_once"},
            {"tool": "move", "edge_id": "E_P"},
            {"tool": "interact", "target_id": "power_line", "operation": "restore_power_line"},
            {"tool": "move", "edge_id": "E_C_EMERGENCY"},
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "oxygen_system", "operation": "restart_oxygen"},
            {
                "tool": "interact",
                "target_id": "oxygen_system",
                "operation": "replenish_oxygen",
            },
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "radio", "operation": "send_distress_packet"},
        ],
    },
    {
        "trace_id": "sacrifice_P",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {
                "tool": "interact",
                "target_id": "bulkhead_E_P",
                "operation": "isolate_compartment",
                "arguments": {"mode": "sacrifice"},
            },
            {"tool": "interact", "target_id": "power_line", "operation": "restore_power_line"},
            {"tool": "move", "edge_id": "E_C_EMERGENCY"},
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "oxygen_system", "operation": "restart_oxygen"},
            {
                "tool": "interact",
                "target_id": "oxygen_system",
                "operation": "replenish_oxygen",
            },
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "radio", "operation": "send_distress_packet"},
        ],
    },
)


FIXTURES = (
    {
        "name": "sacrifice_route_sends_packet",
        "seed": 0,
        "actions": [
            {
                "tool": "interact",
                "target_id": "bulkhead_E_P",
                "operation": "isolate_compartment",
                "arguments": {"mode": "sacrifice"},
            },
            {"tool": "interact", "target_id": "power_line", "operation": "restore_power_line"},
            {"tool": "move", "edge_id": "E_C_EMERGENCY"},
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "oxygen_system", "operation": "restart_oxygen"},
            {
                "tool": "interact",
                "target_id": "oxygen_system",
                "operation": "replenish_oxygen",
            },
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "radio", "operation": "send_distress_packet"},
        ],
        "expect": {
            # 9 个已结算 tick 全部满足 water_E<=4 且 oxygen>0。
            "map09.stable_time_ratio": 1.0,
            "map09.hard_threshold_breaches": 0,
            "map09.fault_propagation_scale": 1,
            "map09.repair_actions": 4,
        },
    },
    {
        "name": "open_bulkhead_wait_shorts_power_bay",
        "seed": 0,
        "actions": [
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
        ],
        "expect": {
            # tick1 E=4 安全；tick2 E=5 短路，故 1/2 安全。
            "map09.stable_time_ratio": 0.5,
            "map09.hard_threshold_breaches": 1,
            "map09.fault_propagation_scale": 1,
            "map09.repair_actions": 0,
        },
    },
    {
        "name": "oxygen_restart_without_generator_is_refused",
        "seed": 0,
        "actions": [
            {
                "tool": "interact",
                "target_id": "bulkhead_E_P",
                "operation": "isolate_compartment",
                "arguments": {"mode": "preserve"},
            },
            {"tool": "move", "edge_id": "E_C_EMERGENCY"},
            {"tool": "move", "edge_id": "O_C"},
            {"tool": "interact", "target_id": "oxygen_system", "operation": "restart_oxygen"},
        ],
        "expect": {
            # 只有封舱成功；开氧被拒后供氧仍关，4 个 tick 都在安全域内。
            "map09.repair_dependency_violations": 1,
            "map09.repair_actions": 1,
            "map09.stable_time_ratio": 1.0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map09Environment"]
