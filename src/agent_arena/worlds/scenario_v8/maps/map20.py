"""MAP-20｜冷却网络：带 20% 损耗的跨区旁路与四重流量约束。

本图与同世界另两图的机制差异：MAP-19 是三片互不传导的独立回路、共享总阀量
且命令延迟两 tick；MAP-21 是隐藏喷发时刻下的风险决策。本图没有时滞与随机事件，
主机制是“水源 60 刻度 + 单支管 25 刻度 + 区间旁路必损 20% + 区阀 4/4/3”，
玩家必须同时决定直供、旁路方向/流量和负荷档，用邻区余量给热点续命。

实现约定（对应 `docs/v8/dcr-resolution.md` 的 V8-DCR-020/021/022）：
- 温度、流量全部用十分之一单位整数；过热线严格 `> 100`。
- 一次非法控制帧（源超预算、支管越界、旁路非法、区阀越界）整帧拒绝、计一次
  `flow_conservation_violations`，但不推进时钟、不结束 episode；这样 Agent 可以
  在下一帧改正。只有热越界与终局产能不足是终止失败。
- 直供与旁路设定是“保持型设定”，在 Agent 改写前逐 tick 复用；水量本身不储存。
- ``max_node_exceedance`` 与 ``safe_node_ticks`` 使用裁判侧精确温度（V7-DCR-010），
  单位均为十分之一度。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action

ZONES = ("A", "B", "C")
ZONE_VALVE_MAX = {"A": 40, "B": 40, "C": 30}
DIRECT_MAX = 25
SOURCE_MAX = 60
BYPASS_QUANTUM = 5
BYPASS_MAX = 20
INITIAL_TEMPERATURES = {"A": 70, "B": 60, "C": 50}
HEAT = {
    "FULL": {"A": 40, "B": 30, "C": 20},
    "REDUCED": {"A": 20, "B": 20, "C": 10},
    "IDLE": {"A": 0, "B": 0, "C": 0},
}
PRODUCTION = {
    "FULL": {"A": 4, "B": 3, "C": 2},
    "REDUCED": {"A": 2, "B": 2, "C": 1},
    "IDLE": {"A": 0, "B": 0, "C": 0},
}
HORIZON = 10
PRODUCTION_TARGET = 15


def _band(tenths: int) -> str:
    if tenths <= 50:
        return "COOL"
    if tenths <= 80:
        return "WARM"
    if tenths <= 100:
        return "HOT"
    return "OVERHEAT"


class Map20Environment(MapEnvironment):
    map_id = "MAP-20"
    title = "冷却网络"
    world = "volcano"
    level = "中等"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "read_temperature": {frozenset({"tool", "station"})},
        "set_flow": {frozenset({"tool", "set_flow_tenths"})},
        "open_bypass": {frozenset({"tool", "open_bypasses"})},
        "adjust_loads": {frozenset({"tool", "adjust_loads"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "ticks_remaining",
            "temperature_bands",
            "current_load_modes",
            "direct_flow_tenths",
            "bypass_settings",
            "previous_tick_flow_ledger",
            "source_water_remaining_this_tick",
            "production_points",
            "production_target",
            "last_temperature_reading",
            "flow_rules",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.temperatures = dict(INITIAL_TEMPERATURES)
        self.loads = {"A": "FULL", "B": "FULL", "C": "FULL"}
        self.direct = {"A": 20, "B": 20, "C": 20}
        self.bypass: dict[str, dict[str, Any]] = {}
        self.production = 0
        self.reading: dict[str, Any] | None = None
        self.read_tick = -1
        self.ledger: dict[str, Any] = {}
        self.settled_states: list[dict[str, int]] = []
        self._cost = 0

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "ticks_remaining": max(0, HORIZON - self.tick_count),
            "temperature_bands": {
                zone: _band(self.temperatures[zone]) for zone in ZONES
            },
            "current_load_modes": dict(self.loads),
            "direct_flow_tenths": dict(self.direct),
            "bypass_settings": {
                link: dict(setting) for link, setting in sorted(self.bypass.items())
            },
            "previous_tick_flow_ledger": dict(self.ledger),
            "source_water_remaining_this_tick": SOURCE_MAX - sum(self.direct.values()),
            "production_points": self.production,
            "production_target": PRODUCTION_TARGET,
            "last_temperature_reading": self.reading,
            "flow_rules": {
                "unit": "tenths",
                "source_max_per_tick": SOURCE_MAX,
                "direct_max_per_branch": DIRECT_MAX,
                "bypass_quantum": BYPASS_QUANTUM,
                "bypass_max_per_link": BYPASS_MAX,
                "bypass_delivered_fraction": 0.8,
                "zone_valve_max": dict(ZONE_VALVE_MAX),
                "temperature_limit": 100,
            },
            "goal": (
                "在 tick 0–9 内保持三区温度不超过 10.0 并累计至少 15 点产能；"
                "旁路输入每 0.5 单位一档，下游只收到 4/5。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        if action.tool == "wait":
            return self._wait()
        self._cost = 0
        if action.tool == "read_temperature":
            return self._read_temperature(action)
        if action.tool == "set_flow":
            return self._set_flow(action)
        if action.tool == "open_bypass":
            return self._open_bypass(action)
        if action.tool == "adjust_loads":
            return self._adjust_loads(action)
        return "ACTION_NOT_ALLOWED"

    def _reject(self, code: str) -> str:
        self._violate(code)
        return code

    def _read_temperature(self, action: V8Action) -> str:
        zone = action.station
        if zone not in ZONES:
            return "INVALID_ZONE"
        if self.read_tick == self.tick_count:
            return "READ_ALREADY_USED"
        self.read_tick = self.tick_count
        self.reading = {
            "tick": self.tick_count,
            "zone": zone,
            "temperature_tenths": self.temperatures[zone],
        }
        return f"TEMPERATURE_READ:{zone}"

    def _set_flow(self, action: V8Action) -> str:
        flow = action.set_flow_tenths
        if flow is None or len(flow) != 3:
            return self._reject("FLOW_CONSERVATION_VIOLATION")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in flow
        ):
            return self._reject("FLOW_CONSERVATION_VIOLATION")
        if any(value > DIRECT_MAX for value in flow):
            return self._reject("FEEDER_CAPACITY_EXCEEDED")
        if sum(flow) > SOURCE_MAX:
            return self._reject("SOURCE_BUDGET_EXCEEDED")
        self.direct = dict(zip(ZONES, flow, strict=True))
        return "FLOW_SET"

    def _open_bypass(self, action: V8Action) -> str:
        settings = action.open_bypasses
        if settings is None or not isinstance(settings, dict):
            return self._reject("INVALID_BYPASS_TRANSFER")
        parsed: dict[str, dict[str, Any]] = {}
        for link, setting in settings.items():
            if link not in ("AB", "BC"):
                return self._reject("INVALID_BYPASS_TRANSFER")
            if setting is None:
                continue
            if not isinstance(setting, dict):
                return self._reject("INVALID_BYPASS_TRANSFER")
            endpoints = ("A", "B") if link == "AB" else ("B", "C")
            source = setting.get("from")
            target = setting.get("to")
            amount = setting.get("input_tenths")
            if source not in endpoints or target not in endpoints or source == target:
                return self._reject("INVALID_BYPASS_TRANSFER")
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount <= 0
                or amount > BYPASS_MAX
                or amount % BYPASS_QUANTUM
            ):
                return self._reject("INVALID_BYPASS_TRANSFER")
            parsed[link] = {
                "from": source,
                "to": target,
                "input_tenths": amount,
            }
        self.bypass = parsed
        return "BYPASS_SET" if parsed else "BYPASS_CLOSED"

    def _adjust_loads(self, action: V8Action) -> str:
        loads = action.adjust_loads
        if loads is None or len(loads) != 3:
            return "INVALID_LOAD_LEVEL"
        if any(mode not in HEAT for mode in loads):
            return "INVALID_LOAD_LEVEL"
        self.loads = dict(zip(ZONES, loads, strict=True))
        return "LOADS_UPDATED"

    def _delivered(self) -> dict[str, int] | None:
        delivered = dict(self.direct)
        for _link, setting in self.bypass.items():
            amount = setting["input_tenths"]
            delivered[setting["from"]] -= amount
            delivered[setting["to"]] += amount * 4 // 5
        if any(value < 0 for value in delivered.values()):
            return None
        if any(
            delivered[zone] > ZONE_VALVE_MAX[zone] for zone in ZONES
        ):
            return None
        return delivered

    def _wait(self) -> str:
        delivered = self._delivered()
        if delivered is None:
            return self._reject("ZONE_VALVE_CAPACITY")
        self.ledger = {
            "tick": self.tick_count,
            "direct_tenths": dict(self.direct),
            "bypass": {
                link: dict(setting) for link, setting in sorted(self.bypass.items())
            },
            "delivered_tenths": dict(delivered),
            "bypass_loss_tenths": sum(
                setting["input_tenths"] // 5
                for setting in self.bypass.values()
            ),
        }
        next_temperatures = {
            zone: max(
                0,
                self.temperatures[zone]
                + HEAT[self.loads[zone]][zone]
                - delivered[zone],
            )
            for zone in ZONES
        }
        self.temperatures = next_temperatures
        self.settled_states.append(dict(next_temperatures))
        self.reading = None
        self.read_tick = -1
        if any(self.temperatures[zone] > 100 for zone in ZONES):
            self._fail("THERMAL_OVERHEAT")
            return "THERMAL_OVERHEAT"
        self.production += sum(PRODUCTION[self.loads[zone]][zone] for zone in ZONES)
        if self.tick_count + 1 >= HORIZON:
            if self.production >= PRODUCTION_TARGET:
                self._succeed("PRODUCTION_TARGET_MET")
                return "PRODUCTION_TARGET_MET"
            self._fail("PRODUCTION_BELOW_15")
            return "PRODUCTION_BELOW_15"
        return "TICK_SETTLED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        return None

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "temperatures_tenths": dict(self.temperatures),
            "loads": dict(self.loads),
            "direct_tenths": dict(self.direct),
            "bypass": {
                link: dict(setting) for link, setting in sorted(self.bypass.items())
            },
            "settled_states_tenths": list(self.settled_states),
            "production": self.production,
            "ledger": dict(self.ledger),
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        exceedance = max(
            (
                max(0, temperature - 100)
                for state in self.settled_states
                for temperature in state.values()
            ),
            default=0,
        )
        safe_node_ticks = sum(
            1
            for state in self.settled_states
            for temperature in state.values()
            if temperature <= 100
        )
        return {
            "map20.max_node_exceedance": exceedance,
            "map20.safe_node_ticks": safe_node_ticks,
            "map20.flow_conservation_violations": sum(self.violations.values()),
            "map20.key_node_runaway": int(
                any(
                    temperature > 100
                    for state in self.settled_states
                    for temperature in state.values()
                )
            ),
        }


def _wait() -> dict[str, Any]:
    return {"tool": "wait"}


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "a_priority",
        "seed": 0,
        "actions": [
            {"tool": "set_flow", "set_flow_tenths": [20, 20, 20]},
            {
                "tool": "open_bypass",
                "open_bypasses": {
                    "AB": {"from": "B", "to": "A", "input_tenths": 10}
                },
            },
            {"tool": "adjust_loads", "adjust_loads": ["FULL", "REDUCED", "REDUCED"]},
            _wait(),
            _wait(),
            {"tool": "set_flow", "set_flow_tenths": [20, 20, 10]},
            {"tool": "open_bypass", "open_bypasses": {}},
            {"tool": "adjust_loads", "adjust_loads": ["REDUCED", "REDUCED", "REDUCED"]},
            _wait(),
            _wait(),
            _wait(),
            _wait(),
            _wait(),
            _wait(),
            _wait(),
            _wait(),
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "a_priority_safe_network",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map20.max_node_exceedance": 0,
            "map20.safe_node_ticks": 30,
            "map20.flow_conservation_violations": 0,
            "map20.key_node_runaway": 0,
        },
    },
    {
        "name": "full_load_without_bypass_overheats_a",
        "seed": 0,
        "actions": [_wait(), _wait()],
        "expect": {
            "map20.max_node_exceedance": 10,
            "map20.safe_node_ticks": 5,
            "map20.flow_conservation_violations": 0,
            "map20.key_node_runaway": 1,
        },
    },
    {
        "name": "zone_valve_rejected_atomically",
        "seed": 0,
        "actions": [
            {"tool": "set_flow", "set_flow_tenths": [20, 20, 20]},
            {
                "tool": "open_bypass",
                "open_bypasses": {
                    "BC": {"from": "B", "to": "C", "input_tenths": 15}
                },
            },
            _wait(),
        ],
        "expect": {
            "map20.max_node_exceedance": 0,
            "map20.safe_node_ticks": 0,
            "map20.flow_conservation_violations": 1,
            "map20.key_node_runaway": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map20Environment"]
