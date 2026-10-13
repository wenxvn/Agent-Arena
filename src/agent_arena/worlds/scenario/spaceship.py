"""Pressure, compartment isolation and finite EVA oxygen rules."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction, UseAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]


class ShipState(ScenarioState):
    integrity: int
    oxygen: int
    lab_open: bool = True
    cargo_open: bool = True
    pod_pressurized: bool = False
    collected: set[str] = set()
    sealed: set[str] = set()
    repaired: bool = False


class SpaceshipScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        rooms = {
            "bridge": "驾驶桥。公开警报显示研究舱失压，必须隔离泄漏并安全撤离。",
            "hub": "中央枢纽。压力表公开显示船体完整度、漏点和隔舱状态。",
            "junction": "舱段交汇处。研究舱隔离门位于这里。",
            "suit_room": "装备间。宇航服可让你进入压力为零的舱室。",
            "lab": "研究舱处于失压状态，舱内每回合消耗宇航服氧气。",
            "cargo": "货舱处于失压状态，内有修复胶。",
            "repair_bay": "维修舱，可修补已隔离的船体破口。",
            "engineering": "工程舱压力稳定，调压器可为逃生舱供压。",
            "escape_pod": "逃生舱。供压且满足任务条件后可撤离。",
        }
        if difficulty == "easy":
            exits = {
                "bridge": ("junction",),
                "junction": ("bridge", "engineering", "lab"),
                "lab": ("junction",),
                "engineering": ("junction", "escape_pod"),
                "escape_pod": ("engineering",),
            }
            start = "bridge"
            objects = {
                "bulkhead_lab": ("junction", "关闭后将隔离研究舱；门关闭时无法进入研究舱。"),
                "pressure_regulator": ("engineering", "仅在研究舱已隔离时可给逃生舱供压。"),
                "launch_control": ("escape_pod", "满足安全条件后可以撤离。"),
            }
            interactions = {
                "bulkhead_lab": ("close",),
                "pressure_regulator": ("pressurize_pod",),
                "launch_control": ("evacuate",),
            }
            items: dict[str, str] = {}
            integrity, oxygen = 12, 0
        elif difficulty == "medium":
            exits = {
                "bridge": ("hub",),
                "hub": ("bridge", "suit_room", "lab", "repair_bay"),
                "suit_room": ("hub",),
                "lab": ("hub",),
                "repair_bay": ("hub", "escape_pod"),
                "escape_pod": ("repair_bay",),
            }
            start = "bridge"
            objects = {
                "lab_door": ("hub", "不可逆隔舱门；关闭后无法回到研究舱。"),
                "hull_display": ("hub", "完整度每回合下降 1，直到研究舱隔离。"),
                "suit_case": ("suit_room", "宇航服可用于低压区；氧气初始为 8。"),
                "pod_regulator": ("repair_bay", "研究舱隔离后为逃生舱供压。"),
                "launch_control": ("escape_pod", "带回样本并完成供压后撤离。"),
                "sample_canister": ("lab", "事故样本，任务要求携带撤离。"),
            }
            interactions = {
                "lab_door": ("close",),
                "pod_regulator": ("pressurize",),
                "launch_control": ("evacuate",),
            }
            items = {"suit": "suit_room", "sample_canister": "lab"}
            integrity, oxygen = 22, 8
        else:
            exits = {
                "bridge": ("hub",),
                "hub": ("bridge", "suit_room", "lab", "cargo", "repair_bay"),
                "suit_room": ("hub", "service_duct"),
                "service_duct": ("suit_room", "cargo"),
                "lab": ("hub",),
                "cargo": ("hub", "service_duct"),
                "repair_bay": ("hub", "escape_pod"),
                "escape_pod": ("repair_bay",),
            }
            start = "bridge"
            objects = {
                "damage_panel": ("hub", "兩處低壓漏點同時工作，完整度每回合下降 2。"),
                "door_lab": ("hub", "研究艙隔離門不可重開。"),
                "door_cargo": ("hub", "貨艙隔離門不可重開。"),
                "evac_manual": ("suit_room", "维修风道只能穿宇航服进入；低压区每回合消耗氧气。"),
                "pod_regulator": ("repair_bay", "两个隔舱关闭且船体完整时可调压。"),
                "hull_patch": ("repair_bay", "使用货舱取回的修复胶堵住剩余船体破口。"),
                "launch_control": ("escape_pod", "携带黑匣子并完成调压后可完整撤离。"),
                "blackbox": ("lab", "事故黑匣子，任务证据。"),
                "sealant": ("cargo", "船体修复胶，可堵住剩余漏点。"),
            }
            interactions = {
                "door_lab": ("close",),
                "door_cargo": ("close",),
                "pod_regulator": ("pressurize",),
                "launch_control": ("evacuate",),
            }
            items = {"suit": "suit_room", "blackbox": "lab", "sealant": "cargo"}
            integrity, oxygen = 40, 12
        rooms = {room: description for room, description in rooms.items() if room in exits}
        definition = {
            "scenario_id": f"SP-{difficulty[0].upper()}",
            "source_design_id": f"SP-{difficulty[0].upper()}",
            "family": "spaceship",
            "difficulty": difficulty,
            "mechanic_version": "pressure-isolation-v1",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "initial": {"integrity": integrity, "oxygen": oxygen},
        }
        super().__init__(
            family="spaceship",
            difficulty=difficulty,
            scenario_id=f"SP-{difficulty[0].upper()}",
            public_goal="隔离失压舱段、完成本关任务并安全撤离。",
            world="spaceship-escape",
            world_version=f"spaceship-escape-world-v3-{difficulty}-zh",
            mechanic_version="pressure-isolation-v1",
            start_room=start,
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _ship(self) -> ShipState:
        return cast(ShipState, self._require_state())

    def _initial_state(self, seed: int) -> ShipState:
        del seed
        integrity = 12 if self._difficulty == "easy" else 22 if self._difficulty == "medium" else 40
        oxygen = 0 if self._difficulty == "easy" else 8 if self._difficulty == "medium" else 12
        return ShipState(
            seed=self._seed, current_room=self.start_room, integrity=integrity, oxygen=oxygen
        )

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if isinstance(action, UseAction):
            state = self._ship()
            if (
                self._difficulty != "hard"
                or action.target != "hull_patch"
                or action.item != "sealant"
                or "sealant" not in state.inventory
                or state.current_room != "repair_bay"
            ):
                return rejected("当前没有可用的对应修复资源或操作点。", "hull_patch_rejected")
            state.repaired = True
            return applied("剩余船体破口已用修复胶封堵。", "hull_patched")
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于飞船设备。", "ship_action_rejected")
        state = self._ship()
        if action.target in {"bulkhead_lab", "lab_door", "door_lab"} and action.choice == "close":
            if state.current_room not in {"junction", "hub"}:
                return rejected("必须在隔舱控制点操作。", "bulkhead_rejected")
            if action.target == "bulkhead_lab":
                state.lab_open = False
            else:
                if self._difficulty == "medium" and "sample_canister" not in state.inventory:
                    state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
                    state.failure_reason = "隔离门已不可逆关闭，事故样本未回收。"
                    return applied("研究舱已隔离，但样本留在舱内。", "lab_abandoned")
                state.lab_open = False
                state.sealed.add("lab")
            return applied("研究舱隔离门已关闭。", "lab_isolated")
        if action.target == "door_cargo" and action.choice == "close":
            if state.current_room != "hub":
                return rejected("必须在中央枢纽操作隔舱门。", "bulkhead_rejected")
            if "sealant" not in state.inventory:
                state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
                state.failure_reason = "货舱已不可逆隔离，修复胶未回收。"
                return applied("货舱已隔离，修复胶留在舱内。", "cargo_abandoned")
            state.cargo_open = False
            state.sealed.add("cargo")
            return applied("货舱隔离门已关闭。", "cargo_isolated")
        if action.target in {"pressure_regulator", "pod_regulator"} and action.choice in {
            "pressurize_pod",
            "pressurize",
        }:
            if self._difficulty == "easy":
                isolated = not state.lab_open
            elif self._difficulty == "medium":
                isolated = not state.lab_open
            else:
                isolated = not state.lab_open and not state.cargo_open
            if not isolated or state.integrity <= 0:
                return rejected("失压舱段尚未全部隔离，当前不能安全调压。", "pressure_unstable")
            if self._difficulty == "hard" and not state.repaired:
                return rejected("船体破口尚未修补，当前不能安全调压。", "hull_unrepaired")
            state.pod_pressurized = True
            return applied("逃生舱供压完成。", "pod_pressurized")
        if action.target == "launch_control" and action.choice == "evacuate":
            if not state.pod_pressurized:
                return rejected("逃生舱尚未供压。", "pod_unpressurized")
            required = (
                None
                if self._difficulty == "easy"
                else "sample_canister"
                if self._difficulty == "medium"
                else "blackbox"
            )
            if self._difficulty == "hard" and not state.repaired:
                state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
                state.failure_reason = "已撤离，但未携带修复胶完成船体修复。"
                return applied("人员已撤离；船体修复目标未完成。", "evacuated_partial")
            if required is None or required in state.inventory:
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {"integrity": state.integrity, "oxygen": state.oxygen}
                return applied("任务物证与人员均已安全撤离。", "evacuated")
            state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
            state.failure_reason = "人员已撤离，但任务物证没有随行。"
            return applied("人员已撤离；任务物证未回收。", "evacuated_partial")
        return rejected("该设备当前不接受此操作。", "ship_action_rejected")

    def _edge_is_open(self, source: str, destination: str) -> bool:
        state = self._ship()
        pair = {source, destination}
        if ("lab" in pair or "cargo" in pair) and "suit" not in state.inventory:
            return False
        if self._difficulty == "easy" and pair == {"junction", "lab"}:
            return state.lab_open
        if pair == {"hub", "lab"}:
            return state.lab_open
        if pair == {"hub", "cargo"}:
            return state.cargo_open
        if pair == {"service_duct", "cargo"}:
            return self._difficulty == "hard" and "suit" in state.inventory
        return True

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._ship()
        leaks = int(state.lab_open) + (int(state.cargo_open) if self._difficulty == "hard" else 0)
        return (
            PublicStatusFact(id="ship_integrity", value=str(state.integrity)),
            PublicStatusFact(id="leak_rate", value=str(leaks)),
            PublicStatusFact(id="suit_oxygen", value=str(state.oxygen)),
            PublicStatusFact(id="lab_bulkhead", value="open" if state.lab_open else "closed"),
            PublicStatusFact(id="pod_pressurized", value=str(state.pod_pressurized).lower()),
            PublicStatusFact(id="hull_repaired", value=str(state.repaired).lower()),
            PublicStatusFact(id="cargo_bulkhead", value="open" if state.cargo_open else "closed"),
        )

    def _advance_tick(self) -> None:
        state = self._ship()
        if state.current_room in {"lab", "cargo", "service_duct"} and self._difficulty != "easy":
            state.oxygen -= 1
        if state.lab_open:
            state.integrity -= 1
        if self._difficulty == "hard" and state.cargo_open:
            state.integrity -= 1
        if state.integrity <= 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "船体完整度降至零。"
        elif state.oxygen < 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "宇航服氧气耗尽。"


__all__ = ["SpaceshipScenario"]
