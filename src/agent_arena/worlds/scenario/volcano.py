"""Heat, coolant flow and eruption-threshold rules for three volcano missions."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction
from agent_arena.arena.models import PickupAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]
FLOW_COOLING = {"off": 0, "low": 1, "high": 3}


class VolcanoState(ScenarioState):
    heat: int = 4
    heat_a: int = 7
    heat_b: int = 5
    coolant: int = 0
    critical: int = 16
    critical_a: int = 14
    critical_b: int = 14
    base_heat: int = 1
    flow_a: str = "off"
    flow_b: str = "off"
    pump_on: bool = False
    valve_open: bool = False
    pump_confirmed: bool = False
    vent_open: bool = False
    shield_deployed: bool = False
    sample_collected: bool = False


class VolcanoScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        if difficulty == "easy":
            rooms = {
                "control": "控制室。热量、升温速率、冷却净效应和临界值公开显示。",
                "cooling_room": "冷却室。水泵必须在冷却阀打开时才产生流量。",
                "exit_platform": "撤离平台。热量不高于 5 且水泵曾有效运行才可离站。",
                "viewing_deck": "观测平台。可查看火山活动，不改变冷却系统。",
            }
            exits = {
                "control": ("cooling_room", "viewing_deck"),
                "cooling_room": ("control", "exit_platform"),
                "exit_platform": ("cooling_room",),
                "viewing_deck": ("control",),
            }
            objects = {
                "heat_monitor": ("control", "显示当前热量、+1/tick、冷却效果和 critical=16。"),
                "coolant_valve": ("cooling_room", "开启后允许主泵产生冷却流量。"),
                "main_pump": ("cooling_room", "阀门关闭时空转；有效冷却每 tick 消耗 1 coolant。"),
                "cable_car": ("exit_platform", "热量≤5 且泵曾有效运行时可撤离。"),
            }
            interactions = {
                "coolant_valve": ("open", "close"),
                "main_pump": ("on", "off"),
                "cable_car": ("depart",),
            }
            items: dict[str, str] = {}
            start = "control"
            initial = {"heat": 4, "coolant": 5, "critical": 16, "base_heat": 1}
            mechanic_version = "thermal-threshold-easy-v2"
        elif difficulty == "medium":
            rooms = {
                "control": (
                    "控制室。两温区读数、critical=14、18 单位冷却库存，"
                    "总流量上限 3 均公开。"
                ),
                "junction": (
                    "回路分配节点。pump_switch 可一次切换两阀，"
                    "避免切换动作造成未预期升温。"
                ),
                "loop_a_room": "A 回路。阀门可选 off、low、high。",
                "loop_b_room": "B 回路。阀门可选 off、low、high。",
                "service_lift": "服务升降台。两温区均≤6 且泵运行时可完成安全认证。",
            }
            exits = {
                "control": ("junction",),
                "junction": ("control", "loop_a_room", "loop_b_room", "service_lift"),
                "loop_a_room": ("junction",),
                "loop_b_room": ("junction",),
                "service_lift": ("junction",),
            }
            objects = {
                "dual_monitor": ("control", "显示 A/B 当前热量和分别升温 +1/tick。"),
                "pump_switch": (
                    "junction",
                    "可设 A high，或将 A/B 同时切为 low；总流量不得超过 3。",
                ),
                "valve_a": ("loop_a_room", "off=0、low=1、high=3 冷却；每 tick 消耗对应流量。"),
                "valve_b": ("loop_b_room", "off=0、low=1、high=3 冷却；每 tick 消耗对应流量。"),
                "evac": ("service_lift", "两温区均≤6 且至少一条回路有流量时离开。"),
            }
            interactions = {
                "pump_switch": ("run_a_high", "balance_low", "off"),
                "valve_a": ("off", "low", "high"),
                "valve_b": ("off", "low", "high"),
                "evac": ("depart",),
            }
            items = {}
            start = "junction"
            initial = {"heat_a": 7, "heat_b": 5, "coolant": 18, "critical": 14}
            mechanic_version = "thermal-flow-medium-v2"
        else:
            rooms = {
                "command": "指挥室。seismic_clock 显示热量、+2/tick、critical=20 和安全余量。",
                "cooling_hub": "冷却枢纽。水泵开启时每 tick 消耗 1 coolant 并净降热量 2。",
                "lava_probe": "熔岩探针点。必须部署 probe_shield 后才能取 core_sample。",
                "aux_tank": "备用冷却剂储罐。可检查剩余资源。",
                "vent_room": "排气室。打开 vent_flap 后基础升温从 +2 降为 +1。",
                "cable_station": "撤离索道。需要已收集样本且热量≤10。",
            }
            exits = {
                "command": ("cooling_hub", "cable_station"),
                "cooling_hub": ("command", "lava_probe", "aux_tank", "vent_room"),
                "lava_probe": ("cooling_hub",),
                "aux_tank": ("cooling_hub",),
                "vent_room": ("cooling_hub",),
                "cable_station": ("command",),
            }
            objects = {
                "seismic_clock": ("command", "显示 heat=6、critical=20、base_heat=+2/tick。"),
                "pump_control": (
                    "cooling_hub",
                    "on/off；每个有效冷却 tick 消耗 1 coolant，热量 -4 再加基础升温。",
                ),
                "probe_shield": ("lava_probe", "采样前必须部署护罩；操作消耗 1 tick。"),
                "core_sample": ("lava_probe", "关键温压样本；须带到 cable_station 撤离。"),
                "coolant_canister": ("aux_tank", "冷却剂总量 8；不能超过初始库存。"),
                "vent_flap": ("vent_room", "打开后永久降低基础升温 +2→+1。"),
                "cable_car": ("cable_station", "heat≤10 且持有 core_sample 才能撤离。"),
            }
            interactions = {
                "pump_control": ("on", "off"),
                "probe_shield": ("deploy",),
                "vent_flap": ("open",),
                "cable_car": ("evacuate",),
            }
            items = {"core_sample": "lava_probe"}
            start = "command"
            initial = {"heat": 6, "coolant": 8, "critical": 20, "base_heat": 2}
            mechanic_version = "thermal-sampling-hard-v2"
        rooms = {room: description for room, description in rooms.items() if room in exits}
        definition = {
            "scenario_id": f"VO-{difficulty[0].upper()}",
            "source_design_id": f"VO-{difficulty[0].upper()}",
            "family": "volcano",
            "difficulty": difficulty,
            "mechanic_version": mechanic_version,
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "initial": initial,
            "flow_cooling": FLOW_COOLING if difficulty == "medium" else None,
        }
        super().__init__(
            family="volcano",
            difficulty=difficulty,
            scenario_id=f"VO-{difficulty[0].upper()}",
            public_goal="依据公开热量与冷却读数完成喷口稳定或安全撤离。",
            world="volcano-escape",
            world_version=f"volcano-escape-world-v3-{difficulty}-zh",
            mechanic_version=mechanic_version,
            start_room=start,
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _volcano(self) -> VolcanoState:
        return cast(VolcanoState, self._require_state())

    def _initial_state(self, seed: int) -> VolcanoState:
        if self._difficulty == "easy":
            return VolcanoState(
                seed=seed,
                current_room=self.start_room,
                heat=4,
                coolant=5,
                critical=16,
                base_heat=1,
            )
        if self._difficulty == "medium":
            return VolcanoState(
                seed=seed,
                current_room=self.start_room,
                heat_a=7,
                heat_b=5,
                coolant=18,
                critical_a=14,
                critical_b=14,
                base_heat=1,
            )
        return VolcanoState(
            seed=seed,
            current_room=self.start_room,
            heat=6,
            coolant=8,
            critical=20,
            base_heat=2,
        )

    def _apply_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._volcano()
        if isinstance(action, PickupAction) and action.item == "core_sample":
            if self._difficulty != "hard" or not state.shield_deployed:
                return rejected("采样前必须在 lava_probe 部署护罩。", "probe_shield_required")
            result = super()._apply_action(action)
            if result[0].status.value == "success":
                state.sample_collected = True
            return result
        return super()._apply_action(action)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于火山控制系统。", "volcano_action_rejected")
        state = self._volcano()
        if self._difficulty == "easy":
            if action.target == "coolant_valve" and action.choice in {"open", "close"}:
                state.valve_open = action.choice == "open"
                return applied(
                    f"冷却阀已{('打开' if state.valve_open else '关闭')}。", "valve_updated"
                )
            if action.target == "main_pump" and action.choice in {"on", "off"}:
                state.pump_on = action.choice == "on"
                return applied(f"主泵已{('启动' if state.pump_on else '停止')}。", "pump_updated")
            if action.target == "cable_car" and action.choice == "depart":
                if state.heat > 5 or not state.pump_confirmed:
                    return rejected("需热量≤5 且确认主泵曾有效冷却。", "evacuation_precondition")
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "heat_at_departure": state.heat,
                    "coolant_remaining": state.coolant,
                }
                return applied("观测站已乘救援缆车安全撤离。", "volcano_evacuated")
        elif self._difficulty == "medium":
            if action.target == "pump_switch" and action.choice == "run_a_high":
                state.flow_a, state.flow_b = "high", "off"
                return applied("A 回路设为 high，泵开始按公开流量冷却。", "flow_a_high")
            if action.target == "pump_switch" and action.choice == "balance_low":
                state.flow_a, state.flow_b = "low", "low"
                return applied("A/B 回路同时设为 low，总流量 2/3。", "flows_balanced")
            if action.target == "pump_switch" and action.choice == "off":
                state.flow_a = state.flow_b = "off"
                return applied("两条冷却回路均已关闭。", "flows_off")
            if action.target in {"valve_a", "valve_b"} and action.choice in FLOW_COOLING:
                next_a = action.choice if action.target == "valve_a" else state.flow_a
                next_b = action.choice if action.target == "valve_b" else state.flow_b
                total_flow = FLOW_COOLING[next_a] + FLOW_COOLING[next_b]
                if total_flow > 3:
                    return rejected(
                        "A/B 总流量超过公开容量 3，阀门设置未改变。", "flow_capacity_exceeded"
                    )
                state.flow_a, state.flow_b = next_a, next_b
                return applied(f"阀门已更新；总流量 {total_flow}/3。", "valve_flow_updated")
            if action.target == "evac" and action.choice == "depart":
                if (
                    max(state.heat_a, state.heat_b) > 6
                    or state.flow_a == "off"
                    and state.flow_b == "off"
                ):
                    return rejected("两温区均需≤6，并保持至少一条回路运行。", "balance_not_reached")
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "heat_a": state.heat_a,
                    "heat_b": state.heat_b,
                    "coolant_remaining": state.coolant,
                }
                return applied("双回路热平衡认证通过。", "dual_loop_stable")
        else:
            if action.target == "pump_control" and action.choice in {"on", "off"}:
                if action.choice == "on" and state.coolant <= 0:
                    return rejected("冷却剂耗尽，不能重新启动水泵。", "coolant_empty")
                state.pump_on = action.choice == "on"
                return applied(f"冷却泵已{('开启' if state.pump_on else '关闭')}。", "pump_updated")
            if action.target == "probe_shield" and action.choice == "deploy":
                state.shield_deployed = True
                return applied("探针护罩已部署。", "probe_shield_deployed")
            if action.target == "vent_flap" and action.choice == "open":
                state.vent_open = True
                state.base_heat = 1
                return applied("排气阀已打开，基础升温降为 +1/tick。", "vent_opened")
            if action.target == "cable_car" and action.choice == "evacuate":
                if not state.sample_collected or state.heat > 10:
                    return rejected(
                        "需持有 core_sample 且热量≤10 才能使用撤离索道。", "evacuation_precondition"
                    )
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "heat_at_departure": state.heat,
                    "coolant_remaining": state.coolant,
                    "sample_collected": True,
                    "vent_open": state.vent_open,
                }
                return applied("温压样本已带回，观测站安全撤离。", "volcano_evacuated")
        return rejected("该火山设备当前不接受此操作。", "volcano_action_rejected")

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._volcano()
        if self._difficulty == "easy":
            cooling = -2 if state.pump_on and state.valve_open and state.coolant > 0 else 1
            return (
                PublicStatusFact(id="heat", value=str(state.heat)),
                PublicStatusFact(id="heat_rate", value=f"{cooling:+d}/tick"),
                PublicStatusFact(id="critical_heat", value=str(state.critical)),
                PublicStatusFact(id="coolant", value=str(state.coolant)),
                PublicStatusFact(id="valve_open", value=str(state.valve_open).lower()),
                PublicStatusFact(id="pump_on", value=str(state.pump_on).lower()),
                PublicStatusFact(id="pump_confirmed", value=str(state.pump_confirmed).lower()),
            )
        if self._difficulty == "medium":
            return (
                PublicStatusFact(id="heat_a", value=str(state.heat_a)),
                PublicStatusFact(id="heat_b", value=str(state.heat_b)),
                PublicStatusFact(id="critical_a", value=str(state.critical_a)),
                PublicStatusFact(id="critical_b", value=str(state.critical_b)),
                PublicStatusFact(id="flow_a", value=state.flow_a),
                PublicStatusFact(id="flow_b", value=state.flow_b),
                PublicStatusFact(
                    id="flow_total",
                    value=str(FLOW_COOLING[state.flow_a] + FLOW_COOLING[state.flow_b]),
                ),
                PublicStatusFact(id="coolant", value=str(state.coolant)),
            )
        heat_rate = (
            state.base_heat - 4
            if state.pump_on and state.coolant > 0
            else state.base_heat
        )
        return (
            PublicStatusFact(id="heat", value=str(state.heat)),
            PublicStatusFact(id="heat_rate", value=f"{heat_rate:+d}/tick"),
            PublicStatusFact(id="critical_heat", value=str(state.critical)),
            PublicStatusFact(id="coolant", value=str(state.coolant)),
            PublicStatusFact(id="pump_on", value=str(state.pump_on).lower()),
            PublicStatusFact(id="vent_open", value=str(state.vent_open).lower()),
            PublicStatusFact(id="shield_deployed", value=str(state.shield_deployed).lower()),
            PublicStatusFact(id="sample_collected", value=str(state.sample_collected).lower()),
        )

    def _advance_tick(self) -> None:
        state = self._volcano()
        if self._difficulty == "easy":
            if state.pump_on and state.valve_open and state.coolant > 0:
                state.heat = max(0, state.heat + state.base_heat - 3)
                state.coolant -= 1
                state.pump_confirmed = True
            else:
                state.heat += state.base_heat
            if state.heat >= state.critical:
                state.terminal_status = ScenarioStatus.FAILURE
                state.failure_reason = "热量达到公开临界值 16。"
            return
        if self._difficulty == "medium":
            flow_a, flow_b = FLOW_COOLING[state.flow_a], FLOW_COOLING[state.flow_b]
            total_flow = flow_a + flow_b
            if total_flow and state.coolant >= total_flow:
                state.heat_a += 1 - flow_a
                state.heat_b += 1 - flow_b
                state.coolant -= total_flow
            else:
                state.heat_a += 1
                state.heat_b += 1
            if state.heat_a >= state.critical_a or state.heat_b >= state.critical_b:
                state.terminal_status = ScenarioStatus.FAILURE
                state.failure_reason = "A 或 B 温区达到公开临界值 14。"
            return
        if state.pump_on and state.coolant > 0:
            state.heat = max(0, state.heat + state.base_heat - 4)
            state.coolant -= 1
        else:
            state.heat += state.base_heat
        if state.heat >= state.critical:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "热量达到公开临界值 20。"


__all__ = ["VolcanoScenario"]
