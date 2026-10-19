"""MAP-20 V10｜冷却网络：动态热点让有损旁路成为必要（DCR-V10-11）。

与 V8 的差异（对应 V9 审计的两条根因）：

- **产能不再等于“交付水 × 0.1”**：V8 的 `PRODUCTION[zone][mode] = HEAT[zone][mode]/10`
  使每单位水的产能恒定，20% 损耗的旁路被直供严格支配。V10 把两者解耦：区产量系数
  独立为 A/B/C = 4/3/2，只有**交付水覆盖该区当 tick 热量**才拿满，
  否则按 `产量 × 交付/热量` 部分计分——缺水第一次有代价，超供仍然浪费；
- **动态热点**：热量表按 tick 轮换（公开），热点区每 tick 需要 26–30 十分之一度，
  超过单支管上限 25，**必须从邻区经有损旁路调入**；静态分配无法覆盖；
- 流量守恒、区阀、旁路档位与交付系数与 V8 一致（公开可推理）；
- 4 个预登记实例：热点轮换序列、热点热量与邻区热量都不同。

指标：主指标为产能兑现率，另加 `bypass_used_ticks`（旁路是否真的改变了交付向量）、
`zones_covered_ticks`、`flow_conservation_violations` 与 `thermal_exceedance`。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, ratio, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

ZONES = ("A", "B", "C")
ZONE_VALVE_MAX = {"A": 40, "B": 40, "C": 35}
DIRECT_MAX = 25
SOURCE_MAX = 60
BYPASS_QUANTUM = 5
BYPASS_MAX = 20
SAFE_TEMPERATURE = 100
LINK_ENDPOINTS = {"AB": ("A", "B"), "BC": ("B", "C")}
PRODUCTION_BASE = {"A": 4, "B": 3, "C": 2}
HEAT_REDUCED_FACTOR = 0.5
HORIZON = 10


class Variant20:
    def __init__(
        self,
        label: str,
        hot_sequence: tuple[str, ...],
        hot_heat: int,
        idle_heat: int,
        initial_temperatures: tuple[int, int, int],
    ) -> None:
        self.label = label
        self.hot_sequence = hot_sequence
        self.hot_heat = hot_heat
        self.idle_heat = idle_heat
        self.initial_temperatures = dict(zip(ZONES, initial_temperatures, strict=True))

    @property
    def schedule(self) -> dict[str, list[int]]:
        return {
            zone: [
                self.hot_heat if self.hot_sequence[tick] == zone else self.idle_heat
                for tick in range(HORIZON)
            ]
            for zone in ZONES
        }


VARIANTS: dict[int, Variant20] = {
    0: Variant20(
        "rotate_ab_first",
        ("A", "A", "B", "B", "B", "C", "C", "A", "A", "B"),
        28,
        10,
        (70, 60, 50),
    ),
    1: Variant20(
        "rotate_bc_first",
        ("B", "B", "C", "C", "A", "A", "B", "B", "C", "A"),
        30,
        8,
        (60, 74, 52),
    ),
    2: Variant20(
        "fast_rotation",
        ("C", "A", "B", "C", "A", "B", "C", "A", "B", "C"),
        26,
        12,
        (64, 58, 56),
    ),
    3: Variant20(
        "wide_swing",
        ("A", "C", "C", "B", "B", "A", "A", "C", "C", "B"),
        30,
        10,
        (72, 56, 60),
    ),
}


def _band(tenths: int) -> str:
    if tenths <= 50:
        return "COOL"
    if tenths <= 80:
        return "WARM"
    if tenths <= 100:
        return "HOT"
    return "OVERHEAT"


class Map20V10Environment(V10Map):
    map_id = "MAP-20"
    title = "冷却网络"
    world = "volcano"
    level = "中等"
    RULE_VERSION = "v10.map20.2"
    SEED_SPACE = tuple(sorted(VARIANTS))
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
            "current_temperatures_tenths",
            "heat_schedule",
            "production_base",
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
    PRIMARY_METRIC = "map20.v10.production_credit"
    METRIC_SPECS = (
        MetricSpec(
            "map20.v10.production_credit",
            "primary",
            "higher",
            "实得产能 / 目标（覆盖热量的区拿满，缺水的区按比例）",
            "目标产能",
            censored_rule="截尾 → CENSORED；热越界 → VALID 0（按已结算 tick 计）",
        ),
        MetricSpec(
            "map20.v10.zones_covered_ticks",
            "secondary",
            "higher",
            "交付水覆盖本 tick 热量的 区·tick 数",
            "已结算区·tick 数",
        ),
        MetricSpec(
            "map20.v10.bypass_used_ticks",
            "diagnostic",
            "higher",
            "旁路实际改变交付向量并帮助覆盖热点的 tick 数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map20.v10.flow_conservation_violations",
            "guardrail",
            "lower",
            "非法控制帧次数",
            "—",
            unit="count",
            valid_range=(0.0, 40.0),
        ),
        MetricSpec(
            "map20.v10.thermal_exceedance_tenths",
            "guardrail",
            "lower",
            "Σ max(0, T − 100) / 已结算区·tick 数",
            "已结算区·tick 数",
            unit="temperature_tenths",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.schedule = self.variant.schedule
        self.temperatures = dict(self.variant.initial_temperatures)
        self.loads = {"A": "FULL", "B": "FULL", "C": "FULL"}
        self.direct = {"A": 20, "B": 20, "C": 20}
        self.bypass: dict[str, dict[str, Any]] = {}
        self.production = 0
        self.reading: dict[str, Any] | None = None
        self.read_tick = -1
        self.ledger: dict[str, Any] = {}
        self.settled: list[dict[str, int]] = []
        self.covered_ticks = 0
        self.bypass_used_ticks = 0
        self._cost = 0

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "hot_sequence": list(self.variant.hot_sequence),
            "hot_heat": self.variant.hot_heat,
            "idle_heat": self.variant.idle_heat,
            "heat_schedule": self.schedule,
            "production_base": dict(PRODUCTION_BASE),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "initial_temperatures": dict(self.variant.initial_temperatures),
            "horizon": HORIZON,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "三区 A/B/C，每 tick 结算一次：T_next = max(0, T + 本 tick 热量 − 交付水)。",
            f"水源每 tick {SOURCE_MAX}；单支管直供上限 {DIRECT_MAX}；区阀上限 "
            f"A/B/C = {ZONE_VALVE_MAX['A']}/{ZONE_VALVE_MAX['B']}/{ZONE_VALVE_MAX['C']}；"
            "交付超过区阀 → 整帧拒绝。",
            f"set_flow(tenths)：`set_flow_tenths` 是长度为 3 的整数数组，顺序固定为区 A、B、C；"
            f"每项 0–{DIRECT_MAX}，三项之和不超过水源 {SOURCE_MAX}，超限整帧拒绝。",
            f"adjust_loads(loads)：`adjust_loads` 是长度为 3 的字符串数组（顺序 A、B、C），"
            '取值只能是 "FULL"、"REDUCED"、"IDLE"；三档的热量分别为 本 tick 热量、'
            f"本 tick 热量 ×{HEAT_REDUCED_FACTOR}、0。",
            f"open_bypass(bypasses)：`open_bypasses` 是以链路名为键的对象，链路只能是 "
            '"AB" 或 "BC"；值为 {"from": 端点, "to": 另一端点, "input_tenths": 取水档位}，'
            f"端点取自该链路两端；`input_tenths` 必须是 {BYPASS_QUANTUM} 的整数倍且不超过 "
            f"{BYPASS_MAX}（可选 {BYPASS_QUANTUM}/{2 * BYPASS_QUANTUM}/"
            f"{3 * BYPASS_QUANTUM}/{BYPASS_MAX}）。",
            f"旁路按 {BYPASS_QUANTUM} 一档、单链路上限 {BYPASS_MAX}，下游只收到 4/5。",
            "**本 tick 三区热量公开**（heat_schedule）；热点区热量会超过单支管上限，"
            "必须从邻区经有损旁路调水。",
            "区产量系数 A/B/C = 4/3/2：交付覆盖该区热量才拿满，否则按 交付/热量 折减。",
            f"在 {HORIZON} tick 内累计目标产能且三区不超过 10.0 即成功。",
            "时间只在 wait 时推进：set_flow / open_bypass / adjust_loads 只修改本 tick 的设置，"
            "不推进 tick；每个 tick 必须调用一次 wait 才提交并结算（否则 tick 不变、产能为 0）。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "ticks_remaining": max(0, HORIZON - self.tick_count),
            "temperature_bands": {zone: _band(self.temperatures[zone]) for zone in ZONES},
            "current_temperatures_tenths": dict(self.temperatures),
            "heat_schedule": {zone: list(values) for zone, values in self.schedule.items()},
            "production_base": dict(PRODUCTION_BASE),
            "current_load_modes": dict(self.loads),
            "direct_flow_tenths": dict(self.direct),
            "bypass_settings": {
                link: dict(setting) for link, setting in sorted(self.bypass.items())
            },
            "previous_tick_flow_ledger": dict(self.ledger),
            "source_water_remaining_this_tick": SOURCE_MAX - sum(self.direct.values()),
            "production_points": self.production,
            "production_target": self.target(),
            "last_temperature_reading": self.reading,
            "flow_rules": {
                "unit": "tenths",
                "source_max_per_tick": SOURCE_MAX,
                "direct_max_per_branch": DIRECT_MAX,
                "bypass_quantum": BYPASS_QUANTUM,
                "bypass_max_per_link": BYPASS_MAX,
                "bypass_delivered_fraction": 0.8,
                "zone_valve_max": dict(ZONE_VALVE_MAX),
                "temperature_limit": SAFE_TEMPERATURE,
            },
            "goal": (
                "在 10 tick 内保持三区温度不超过 10.0 并累计目标产能；"
                "热点区需要从邻区经有损旁路调水。"
            ),
        }

    def target(self) -> int:
        return TARGETS[self.environment_seed]

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
            not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in flow
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
            if link not in LINK_ENDPOINTS:
                return self._reject("INVALID_BYPASS_TRANSFER")
            if setting is None:
                continue
            if not isinstance(setting, dict):
                return self._reject("INVALID_BYPASS_TRANSFER")
            endpoints = LINK_ENDPOINTS[link]
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
            parsed[link] = {"from": source, "to": target, "input_tenths": amount}
        self.bypass = parsed
        return "BYPASS_SET" if parsed else "BYPASS_CLOSED"

    def _adjust_loads(self, action: V8Action) -> str:
        loads = action.adjust_loads
        if loads is None or len(loads) != 3:
            return "INVALID_LOAD_LEVEL"
        if any(mode not in ("FULL", "REDUCED", "IDLE") for mode in loads):
            return "INVALID_LOAD_LEVEL"
        self.loads = dict(zip(ZONES, loads, strict=True))
        return "LOADS_UPDATED"

    def heat(self, zone: str) -> int:
        """本 tick 该区热量：负荷档按公开规则折减。"""

        base = self.schedule[zone][min(self.tick_count, HORIZON - 1)]
        if self.loads[zone] == "FULL":
            return base
        if self.loads[zone] == "REDUCED":
            return int(base * HEAT_REDUCED_FACTOR)
        return 0

    def production_potential(self, zone: str) -> int:
        if self.loads[zone] == "FULL":
            return PRODUCTION_BASE[zone]
        if self.loads[zone] == "REDUCED":
            return max(1, PRODUCTION_BASE[zone] // 2)
        return 0

    def _delivered(self) -> dict[str, int] | None:
        delivered = dict(self.direct)
        for _link, setting in self.bypass.items():
            amount = setting["input_tenths"]
            delivered[setting["from"]] -= amount
            delivered[setting["to"]] += amount * 4 // 5
        if any(value < 0 for value in delivered.values()):
            return None
        if any(delivered[zone] > ZONE_VALVE_MAX[zone] for zone in ZONES):
            return None
        return delivered

    def _wait(self) -> str:
        delivered = self._delivered()
        if delivered is None:
            return self._reject("ZONE_VALVE_CAPACITY")
        heats = {zone: self.heat(zone) for zone in ZONES}
        self.ledger = {
            "tick": self.tick_count,
            "direct_tenths": dict(self.direct),
            "bypass": {link: dict(setting) for link, setting in sorted(self.bypass.items())},
            "delivered_tenths": dict(delivered),
            "bypass_loss_tenths": sum(
                setting["input_tenths"] // 5 for setting in self.bypass.values()
            ),
            "heat_tenths": dict(heats),
        }
        next_temperatures = {
            zone: max(0, self.temperatures[zone] + heats[zone] - delivered[zone]) for zone in ZONES
        }
        self.temperatures = next_temperatures
        self.settled.append(dict(next_temperatures))
        self.reading = None
        self.read_tick = -1
        covered = 0
        gained = 0
        for zone in ZONES:
            if heats[zone] == 0:
                covered += 1
                continue
            if delivered[zone] >= heats[zone]:
                covered += 1
                gained += self.production_potential(zone)
            else:
                gained += self.production_potential(zone) * delivered[zone] // heats[zone]
        self.covered_ticks += covered
        has_bypass = bool(self.bypass)
        if has_bypass:
            direct_only = {zone: self.direct[zone] - heats[zone] for zone in ZONES}
            if covered > sum(1 for zone in ZONES if direct_only[zone] >= 0):
                self.bypass_used_ticks += 1
        self.production += gained
        if any(self.temperatures[zone] > SAFE_TEMPERATURE for zone in ZONES):
            self._fail("THERMAL_OVERHEAT")
            return "THERMAL_OVERHEAT"
        if self.tick_count + 1 >= HORIZON:
            if self.production >= self.target():
                self._succeed("PRODUCTION_TARGET_MET")
                return "PRODUCTION_TARGET_MET"
            self._fail("PRODUCTION_BELOW_TARGET")
            return "PRODUCTION_BELOW_TARGET"
        return "TICK_SETTLED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "temperatures_tenths": dict(self.temperatures),
            "loads": dict(self.loads),
            "direct_tenths": dict(self.direct),
            "bypass": {link: dict(setting) for link, setting in sorted(self.bypass.items())},
            "settled_states_tenths": list(self.settled),
            "production": self.production,
            "target": self.target(),
            "covered_ticks": self.covered_ticks,
            "bypass_used_ticks": self.bypass_used_ticks,
            "ledger": dict(self.ledger),
            "violations": dict(sorted(self.violations.items())),
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            credit: MValue = censored("截尾")
        else:
            credit = valid(min(1.0, round(self.production / self.target(), 6)))
        settled_zone_ticks = max(1, len(self.settled) * len(ZONES))
        exceedance = sum(
            max(0, temperature - SAFE_TEMPERATURE)
            for state in self.settled
            for temperature in state.values()
        )
        return {
            "map20.v10.production_credit": credit,
            "map20.v10.zones_covered_ticks": ratio(self.covered_ticks, settled_zone_ticks),
            "map20.v10.bypass_used_ticks": valid(self.bypass_used_ticks),
            "map20.v10.flow_conservation_violations": valid(sum(self.violations.values())),
            "map20.v10.thermal_exceedance_tenths": ratio(exceedance, settled_zone_ticks),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少一个 tick 的覆盖是靠有损旁路调水达成的。"""

        return self.bypass_used_ticks > 0


HORIZON_TICKS = HORIZON


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：热点区拉满直供 + 有损旁路补差，供体区先取够自家水量再外送。"""

    variant = VARIANTS[environment_seed]
    actions: list[dict[str, Any]] = []
    for tick in range(HORIZON):
        hot = variant.hot_sequence[tick]
        heats = {zone: variant.schedule[zone][tick] for zone in ZONES}
        donor = "B" if hot in ("A", "C") else "A"
        third = next(zone for zone in ZONES if zone not in (hot, donor))
        direct = {zone: heats[zone] for zone in ZONES}
        direct[hot] = DIRECT_MAX
        need = heats[hot] - DIRECT_MAX
        import_units = 0
        while import_units * 4 // 5 < need:
            import_units += BYPASS_QUANTUM
        direct[donor] = min(DIRECT_MAX, heats[donor] + import_units)
        bypass: dict[str, dict[str, Any]] = {}
        if import_units:
            link = "AB" if hot in ("A", "B") and donor in ("A", "B") else "BC"
            bypass[link] = {"from": donor, "to": hot, "input_tenths": import_units}
        actions.append({"tool": "set_flow", "set_flow_tenths": [direct[zone] for zone in ZONES]})
        actions.append({"tool": "open_bypass", "open_bypasses": bypass})
        actions.append({"tool": "adjust_loads", "adjust_loads": ["FULL", "FULL", "FULL"]})
        actions.append({"tool": "wait"})
        del third
    return actions


TARGETS: dict[int, int] = {0: 85, 1: 85, 2: 85, 3: 85}


__all__ = [
    "DIRECT_MAX",
    "HORIZON",
    "Map20V10Environment",
    "SOURCE_MAX",
    "TARGETS",
    "VARIANTS",
    "Variant20",
    "oracle_actions",
]
