"""Flood control, pressure balance and pump allocation rules."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]


class AbyssState(ScenarioState):
    water: int = 4
    west_pressure: int = 5
    east_pressure: int = 2
    pump_uses: int = 3
    leak_open: bool = True
    greenhouse_gate_open: bool = True
    core_safe: bool = True
    control_water: int = 2
    greenhouse_water: int = 6
    machine_water: int = 3
    greenhouse_lost: bool = False


class AbyssScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        interactions: dict[str, tuple[str, ...]]
        rooms = {
            "control": "深海站控制室。仪表公开显示舱水、压强和泵能。",
            "valve": "漏水阀室；先关阀可阻止水位继续上升。",
            "pump": "泵室；有限泵能可抽水或调整舱间压强。",
            "lift": "上浮平台。只有满足本关水位或压差条件才能启动。",
            "west": "西侧取样舱。样本必须带回上浮平台。",
            "east": "东侧压力舱。泵可提升其压力。",
            "greenhouse": "温室舱；硬关允许牺牲这里保护核心舱。",
            "machine": "设备核心舱。保持低水位是撤离的关键。",
        }
        if difficulty == "easy":
            exits = {
                "control": ("valve",),
                "valve": ("control", "pump"),
                "pump": ("valve", "lift"),
                "lift": ("pump",),
            }
            objects = {
                "leak_valve": ("valve", "关闭后会停止每回合 +1 的漏水。"),
                "drain_pump": ("pump", "每次启动消耗一次泵能并抽水 3 单位。"),
                "surface_lift": ("lift", "舱水不高于 2 时可上浮。"),
            }
            interactions = {
                "leak_valve": ("close",),
                "drain_pump": ("pump",),
                "surface_lift": ("surface",),
            }
            items: dict[str, str] = {}
            start = "control"
        elif difficulty == "medium":
            exits = {
                "control": ("west", "east", "pump", "lift"),
                "west": ("control",),
                "east": ("control",),
                "pump": ("control",),
                "lift": ("control",),
            }
            objects = {
                "west_gauge": ("west", "西舱压力初始为 5。"),
                "east_gauge": ("east", "东舱压力初始为 2；泵每次增加 1。"),
                "equalizer": ("control", "两侧压差不超过 1 且携带样本时可开放。"),
                "east_pump": ("pump", "每次泵送使东舱压强增加 1。"),
                "sample": ("west", "完成任务必须携带此样本上浮。"),
                "surface_lift": ("lift", "均压通道打开后可撤离。"),
            }
            interactions = {
                "equalizer": ("open",),
                "east_pump": ("raise_pressure",),
                "surface_lift": ("surface",),
            }
            items = {"sample_canister": "west"}
            start = "control"
        else:
            exits = {
                "control": ("greenhouse", "pump", "machine", "lift"),
                "greenhouse": ("control",),
                "pump": ("control",),
                "machine": ("control",),
                "lift": ("control",),
            }
            objects = {
                "overflow_gate": ("greenhouse", "关闭后温室不再向核心区溢流。"),
                "pump_console": (
                    "pump",
                    "仅有 3 次泵能；每次从一个舱室抽排 3 单位。核心舱达到 10 即失守。",
                ),
                "data_disk": ("machine", "研究数据盘，完整撤离的必需任务物品。"),
                "surface_lift": ("lift", "核心舱水位低于 3 且携带数据盘时可上浮。"),
            }
            interactions = {
                "overflow_gate": ("close",),
                "pump_console": ("pump_greenhouse", "pump_control", "pump_machine"),
                "surface_lift": ("surface",),
            }
            items = {"data_disk": "machine"}
            start = "control"
        rooms = {room: description for room, description in rooms.items() if room in exits}
        initial = (
            {"water": 4, "pump_uses": 3}
            if difficulty == "easy"
            else {"west_pressure": 5, "east_pressure": 2, "pump_uses": 3}
            if difficulty == "medium"
            else {
                "control_water": 2,
                "greenhouse_water": 6,
                "machine_water": 3,
                "pump_uses": 3,
            }
        )
        definition = {
            "scenario_id": f"AB-{difficulty[0].upper()}",
            "source_design_id": f"AB-{difficulty[0].upper()}",
            "family": "abyss",
            "difficulty": difficulty,
            "mechanic_version": "flood-pressure-allocation-v1",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "initial": initial,
        }
        super().__init__(
            family="abyss",
            difficulty=difficulty,
            scenario_id=f"AB-{difficulty[0].upper()}",
            public_goal="控制进水或压差，完成本关目标并安全上浮。",
            world="abyss-escape",
            world_version=f"abyss-escape-world-v3-{difficulty}-zh",
            mechanic_version="flood-pressure-allocation-v1",
            start_room=start,
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _abyss(self) -> AbyssState:
        return cast(AbyssState, self._require_state())

    def _initial_state(self, seed: int) -> AbyssState:
        return AbyssState(seed=seed, current_room=self.start_room)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于深海站设备。", "abyss_action_rejected")
        state = self._abyss()
        if action.target == "leak_valve" and action.choice == "close":
            state.leak_open = False
            return applied("漏水阀已关闭。", "leak_stopped")
        if action.target == "drain_pump" and action.choice == "pump":
            if state.pump_uses <= 0:
                return rejected("泵能已耗尽。", "pump_empty")
            state.pump_uses -= 1
            state.water = max(0, state.water - 3)
            return applied("泵已抽排 3 单位海水。", "water_pumped")
        if action.target == "equalizer" and action.choice == "open":
            if abs(state.west_pressure - state.east_pressure) > 1:
                return rejected("两侧压差超过安全阈值 1。", "pressure_delta_high")
            if "sample_canister" not in state.inventory:
                return rejected("尚未取得西舱样本，不能开始撤离程序。", "sample_missing")
            state.facts["equalizer_open"] = True
            return applied("均压通道已打开。", "equalizer_opened")
        if action.target == "east_pump" and action.choice == "raise_pressure":
            if state.east_pressure >= 5:
                return rejected("东舱压强已达到公开上限 5。", "overpressure")
            state.east_pressure += 1
            return applied("东舱压强增加 1。", "east_pressure_raised")
        if action.target == "pump_console" and action.choice.startswith("pump_"):
            if state.pump_uses <= 0:
                return rejected("仅有的三次泵能已经耗尽。", "pump_empty")
            state.pump_uses -= 1
            target = action.choice.removeprefix("pump_")
            if target == "greenhouse":
                state.greenhouse_water = max(0, state.greenhouse_water - 3)
            elif target == "machine":
                state.machine_water = max(0, state.machine_water - 3)
            elif target == "control":
                state.control_water = max(0, state.control_water - 3)
            return applied(f"泵能已分配给 {target} 舱。", "pump_allocated")
        if action.target == "overflow_gate" and action.choice == "close":
            state.greenhouse_gate_open = False
            return applied("温室溢流门已关闭，水流被限制在温室侧。", "greenhouse_isolated")
        if action.target == "surface_lift" and action.choice == "surface":
            if self._difficulty == "easy" and state.water > 2:
                return rejected("当前舱水高于 2，升降平台不能启动。", "water_too_high")
            if self._difficulty == "medium" and not state.facts.get("equalizer_open", False):
                return rejected("均压通道尚未开放。", "equalizer_closed")
            if self._difficulty == "hard":
                if state.machine_water >= 3:
                    return rejected("核心舱水位必须低于 3 才能上浮。", "core_water_high")
                if "data_disk" not in state.inventory:
                    state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
                    state.failure_reason = "人员已撤离，但研究数据盘留在核心舱。"
                    return applied("人员已上浮；研究数据未带回。", "surface_partial")
                state.terminal_status = ScenarioStatus.SUCCESS
            else:
                state.terminal_status = ScenarioStatus.SUCCESS
            return applied("潜水员已安全上浮。", "surfaced")
        return rejected("该设备当前不接受此操作。", "abyss_action_rejected")

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._abyss()
        facts = [
            PublicStatusFact(id="pump_uses", value=str(state.pump_uses)),
            PublicStatusFact(id="leak_open", value=str(state.leak_open).lower()),
        ]
        if self._difficulty == "easy":
            facts.append(PublicStatusFact(id="water", value=str(state.water)))
        elif self._difficulty == "medium":
            facts.extend(
                (
                    PublicStatusFact(id="west_pressure", value=str(state.west_pressure)),
                    PublicStatusFact(id="east_pressure", value=str(state.east_pressure)),
                    PublicStatusFact(
                        id="pressure_delta",
                        value=str(abs(state.west_pressure - state.east_pressure)),
                    ),
                )
            )
        else:
            facts.extend(
                (
                    PublicStatusFact(
                        id="greenhouse_gate_open", value=str(state.greenhouse_gate_open).lower()
                    ),
                    PublicStatusFact(id="control_water", value=str(state.control_water)),
                    PublicStatusFact(id="greenhouse_water", value=str(state.greenhouse_water)),
                    PublicStatusFact(id="machine_water", value=str(state.machine_water)),
                    PublicStatusFact(
                        id="greenhouse_lost", value=str(state.greenhouse_lost).lower()
                    ),
                )
            )
        if self._difficulty == "medium":
            facts.append(
                PublicStatusFact(
                    id="equalizer_open",
                    value=str(bool(state.facts.get("equalizer_open", False))).lower(),
                )
            )
        return tuple(facts)

    def _advance_tick(self) -> None:
        state = self._abyss()
        if self._difficulty == "easy" and state.leak_open:
            state.water += 1
            if state.water >= 10:
                state.terminal_status = ScenarioStatus.FAILURE
                state.failure_reason = "漏水使舱水达到危险上限 10。"
        elif self._difficulty == "hard":
            if state.greenhouse_gate_open:
                state.greenhouse_water += 1
                if state.tick % 2 == 0:
                    state.control_water += 1
            if state.tick % 3 == 0:
                state.machine_water += 1
            if state.greenhouse_water >= 10:
                state.greenhouse_lost = True
            if state.control_water >= 10 or state.machine_water >= 10:
                state.terminal_status = ScenarioStatus.FAILURE
                state.failure_reason = "主控舱或设备核心舱水位达到危险上限 10。"


__all__ = ["AbyssScenario"]
