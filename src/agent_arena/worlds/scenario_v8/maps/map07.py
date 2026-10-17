"""MAP-07｜逆流阀门：同一 tick 内按 v1→v2→v3→v4→泵 级联的可变水位水路。

本图与同世界另两图的机制差异：MAP-08 用主动测试缩小隐藏漏点的假设集合，
MAP-09 是漏水/电量/供氧/通信的跨系统资源耦合；本图没有行走图，Agent 始终在
控制台 P 远程操作，因果难度来自“一个 tick 内可变水位按固定次序级联”以及
单向回流 v4（C→A）——给 C 降压会把水送回 A，而不是排掉。

指标口径（与 docs/v7/maps/MAP-07.md 一致）：
- ``excess_water_integral``：对每个已完成流水 tick 累加
  ``Σ_{c∈{A,B,C}} max(0, level_c - 2)``；tick 0 不计，流水后立即读数。
- ``correct_direction_rate``：分子是“使总超额水量下降”的成功阀门操作数，
  或总超额水量已为 0 时仍保持 0 的操作；分母是所有成功改变阀门状态、并触发
  随后流水 tick 的操作。平局（>0 且不变）算方向错误。
- ``overpressure_ticks``：A/B/C 任一 ``>8`` 的流水 tick 数。
- ``illegal_valve_combo``：控制台拒绝的“一条命令同时操作多个阀门”的次数
  （``arguments`` 出现 ``valve_id``/``open`` 之外的阀门字段）。真实的水路错误
  组合（例如只开 v1/v4）是合法命令，按设计照常结算并由溢流失败暴露。
- ``interventions``：成功改变状态的阀门开/关与泵启/停次数。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map07Environment(MapEnvironment):
    map_id = "MAP-07"
    title = "逆流阀门"
    world = "abyss"
    level = "简单"
    EDGES: dict[str, tuple[str, str]] = {}
    SHAPES: dict[str, set[frozenset[str]]] = {
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
            "water_levels",
            "valves",
            "pump_active",
            "pump_power_draw",
            "pump_energy",
            "low_water_streak",
            "pipe_diagram",
            "goal",
        }
    )
    HYDRAULIC_NODES = ("A", "B", "C", "D")
    OVERFLOW_LIMIT = 8
    LOW_WATER_TARGET = 2
    PUMP_DRAIN_CAP = 2
    PUMP_POWER_PER_TICK = 2
    PIPE_DIAGRAM = {
        "v1": {"from": "A", "to": "B", "capacity": 2},
        "v2": {"from": "B", "to": "C", "capacity": 2},
        "v3": {"from": "C", "to": "D", "capacity": 2},
        "v4": {"from": "C", "to": "A", "capacity": 1, "one_way": True},
    }
    VALVES = ("v1", "v2", "v3", "v4")

    def __init__(self, *, seed: int = 0, step_limit: int = 120) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "P"
        self.items = []
        self.water: dict[str, int] = {"A": 6, "B": 2, "C": 4, "D": 0}
        self.valves: dict[str, bool] = {name: False for name in self.VALVES}
        self.pump_active = False
        self.pump_energy = 0
        self.low_water_streak = 0
        self.excess_integral = 0
        self.overpressure_ticks = 0
        self.correct_valve_ops = 0
        self.decidable_valve_ops = 0
        self.illegal_combos = 0
        self.interventions = 0
        self.prediction_errors: list[int] = []
        self._pending_valve_before: int | None = None
        self._pending_prediction: dict[str, int] | None = None

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "water_levels": dict(self.water),
            "valves": dict(self.valves),
            "pump_active": self.pump_active,
            "pump_power_draw": self.PUMP_POWER_PER_TICK if self.pump_active else 0,
            "pump_energy": self.pump_energy,
            "low_water_streak": self.low_water_streak,
            "pipe_diagram": {
                name: dict(spec) for name, spec in self.PIPE_DIAGRAM.items()
            },
            "goal": "让 A/B/C 连续两个流水 tick 都不超过 2，且任一流水 tick 都不超过 8。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_valve_before = None
        self._pending_prediction = None
        tool = action.tool
        if tool == "inspect":
            return self._inspect(action)
        if tool == "wait":
            if action.ticks != 1:
                return "INVALID_WAIT_DURATION"
            return "WAITED"
        if tool == "interact":
            return self._control(action)
        return "ACTION_NOT_ALLOWED"

    def _inspect(self, action: V8Action) -> str:
        if action.target_id == "water_levels":
            levels = ",".join(f"{name}={self.water[name]}" for name in self.HYDRAULIC_NODES)
            return f"WATER_LEVELS:{levels}"
        if action.target_id == "pipe_diagram":
            return "PIPE_DIAGRAM:v1=A>B2;v2=B>C2;v3=C>D2;v4=C>A1"
        return "TARGET_NOT_VISIBLE"

    def _control(self, action: V8Action) -> str:
        if action.target_id != "control_panel":
            return "TARGET_NOT_VISIBLE"
        operation = action.operation
        arguments: dict[str, Any] = action.arguments or {}
        if operation == "set_valve":
            return self._set_valve(arguments)
        if operation in {"start_pump", "stop_pump"}:
            if arguments:
                return "INVALID_CONTROL"
            return self._set_pump(operation)
        if operation == "predict_next_levels":
            return self._predict(arguments)
        return "ACTION_NOT_ALLOWED"

    def _set_valve(self, arguments: dict[str, Any]) -> str:
        extra = set(arguments) - {"valve_id", "open"}
        if extra:
            # 控制台一次只接受一个阀门；任何额外阀门字段都是组合指令。
            self.illegal_combos += 1
            self._violate("illegal_valve_combination")
            return "INVALID_VALVE_COMBINATION"
        if set(arguments) != {"valve_id", "open"}:
            return "INVALID_CONTROL"
        valve_id = arguments["valve_id"]
        requested = arguments["open"]
        if not isinstance(valve_id, str) or not isinstance(requested, bool):
            return "INVALID_CONTROL"
        if valve_id not in self.valves:
            return "INVALID_VALVE"
        if self.valves[valve_id] == requested:
            return "VALVE_ALREADY_OPEN" if requested else "VALVE_ALREADY_CLOSED"
        self._pending_valve_before = self._excess()
        self.valves[valve_id] = requested
        self.interventions += 1
        return f"VALVE_OPEN:{valve_id}" if requested else f"VALVE_CLOSE:{valve_id}"

    def _set_pump(self, operation: str) -> str:
        starting = operation == "start_pump"
        if starting and self.pump_active:
            return "PUMP_ALREADY_RUNNING"
        if not starting and not self.pump_active:
            return "PUMP_NOT_RUNNING"
        self.pump_active = starting
        self.interventions += 1
        return "PUMP_STARTED" if starting else "PUMP_STOPPED"

    def _predict(self, arguments: dict[str, Any]) -> str:
        if set(arguments) != set(self.HYDRAULIC_NODES):
            return "INVALID_CONTROL"
        if any(not isinstance(arguments[name], int) for name in self.HYDRAULIC_NODES):
            return "INVALID_CONTROL"
        self._pending_prediction = {name: arguments[name] for name in self.HYDRAULIC_NODES}
        return "PREDICTION_RECORDED"

    # ------------------------------------------------------------------ per tick
    def _excess(self) -> int:
        return sum(
            max(0, self.water[name] - self.LOW_WATER_TARGET)
            for name in ("A", "B", "C")
        )

    def _transfer(self, source: str, destination: str, capacity: int) -> None:
        moved = min(capacity, self.water[source])
        self.water[source] -= moved
        self.water[destination] += moved

    def _flow_tick(self) -> None:
        if self.valves["v1"]:
            self._transfer("A", "B", 2)
        if self.valves["v2"]:
            self._transfer("B", "C", 2)
        if self.valves["v3"]:
            self._transfer("C", "D", 2)
        if self.valves["v4"]:
            self._transfer("C", "A", 1)
        if self.pump_active:
            self.water["D"] -= min(self.PUMP_DRAIN_CAP, self.water["D"])
            self.pump_energy += self.PUMP_POWER_PER_TICK

        excess = self._excess()
        self.excess_integral += excess
        if self._pending_valve_before is not None:
            self.decidable_valve_ops += 1
            if excess < self._pending_valve_before or (
                self._pending_valve_before == 0 and excess == 0
            ):
                self.correct_valve_ops += 1
            self._pending_valve_before = None
        if self._pending_prediction is not None:
            error = sum(
                abs(self._pending_prediction[name] - self.water[name])
                for name in self.HYDRAULIC_NODES
            )
            self.prediction_errors.append(error)
            self._pending_prediction = None

        overflowing = [
            name
            for name in ("A", "B", "C")
            if self.water[name] > self.OVERFLOW_LIMIT
        ]
        if overflowing:
            self.overpressure_ticks += 1
            self._fail(f"COMPARTMENT_OVERFLOW_{overflowing[0]}")
            return

        if all(self.water[name] <= self.LOW_WATER_TARGET for name in ("A", "B", "C")):
            self.low_water_streak += 1
        else:
            self.low_water_streak = 0
        if self.low_water_streak >= 2:
            self._succeed("LOW_WATER_STABLE")

    def _after_tick(self) -> None:
        self._flow_tick()

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "water": dict(self.water),
            "valves": dict(self.valves),
            "pump_active": self.pump_active,
            "pump_energy": self.pump_energy,
            "low_water_streak": self.low_water_streak,
            "excess_integral": self.excess_integral,
            "overpressure_ticks": self.overpressure_ticks,
            "correct_valve_ops": self.correct_valve_ops,
            "decidable_valve_ops": self.decidable_valve_ops,
            "illegal_combos": self.illegal_combos,
            "interventions": self.interventions,
            "prediction_errors": list(self.prediction_errors),
            "violations": dict(self.violations),
        }

    def metrics(self) -> dict[str, Any]:
        return {
            "map07.correct_direction_rate": {
                "numerator": self.correct_valve_ops,
                "denominator": self.decidable_valve_ops,
            },
            "map07.excess_water_integral": self.excess_integral,
            "map07.illegal_valve_combo": self.illegal_combos,
            "map07.interventions": self.interventions,
            "map07.overpressure_ticks": self.overpressure_ticks,
        }


ORACLE_CASES = (
    {
        "trace_id": "downstream_first",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "start_pump",
                "arguments": {},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v3", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v2", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v1", "open": True},
            },
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
        ],
    },
    {
        "trace_id": "upstream_staged",
        "seed": 0,
        "expect_success": True,
        "actions": [
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v1", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v2", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v3", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "start_pump",
                "arguments": {},
            },
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
        ],
    },
)


FIXTURES = (
    {
        "name": "downstream_first_success",
        "seed": 0,
        "actions": [
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "start_pump",
                "arguments": {},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v3", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v2", "open": True},
            },
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v1", "open": True},
            },
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
        ],
        "expect": {
            # 6+4+4+2+0+0 的超额水量积分；三次阀门操作中两次降低总超额（v3 与 v1）。
            "map07.excess_water_integral": 16,
            "map07.correct_direction_rate": 0.666667,
            "map07.interventions": 4,
            "map07.overpressure_ticks": 0,
        },
    },
    {
        "name": "bypass_v4_backflow_overflows_A",
        "seed": 0,
        "actions": [
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v4", "open": True},
            },
            {"tool": "wait", "ticks": 1},
            {"tool": "wait", "ticks": 1},
        ],
        "expect": {
            # tick1/2/3 超额 = 6/6/7；tick3 的 A=9 越过溢流线。
            "map07.excess_water_integral": 19,
            "map07.overpressure_ticks": 1,
            "map07.correct_direction_rate": 0.0,
        },
    },
    {
        "name": "combined_valve_command_is_refused",
        "seed": 0,
        "actions": [
            {
                "tool": "interact",
                "target_id": "control_panel",
                "operation": "set_valve",
                "arguments": {"valve_id": "v1", "open": True, "also_open": "v4"},
            },
        ],
        "expect": {
            # 命令被拒，但流水 tick 照常发生；四个阀门仍全闭，水位不变。
            "map07.illegal_valve_combo": 1,
            "map07.excess_water_integral": 6,
            "map07.interventions": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map07Environment"]
