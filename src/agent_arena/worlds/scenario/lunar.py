"""EVA oxygen, sunlight charging and return-reserve rules."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction
from agent_arena.arena.models import PickupAction, UseAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]
SUN = ("DAY", "DAY", "DAY", "SHADOW", "SHADOW", "SHADOW")
OUTDOOR = {"solar_pad", "solar_array", "antenna", "relay_point", "crater_rim", "mast"}


class LunarState(ScenarioState):
    oxygen: int = 10
    reserve_oxygen: int = 0
    battery: int = 0
    eva_prepared: bool = False
    eva_active: bool = False
    panel_repaired: bool = False
    comms_repaired: bool = False
    mast_repaired: bool = False
    crew_oxygen: int = 5
    crew_escorting: bool = False
    crew_rescued: bool = False
    rescue_checked_in: bool = False
    solar_charges: int = 0


class LunarScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        interactions: dict[str, tuple[str, ...]]
        if difficulty == "easy":
            rooms = {
                "habitat": "月球基地居住舱。可检查宇航服氧气余量。",
                "airlock": "气闸。穿好宇航服后循环出舱；返航时循环入舱。",
                "solar_pad": "太阳能板平台。舱外每个行动 tick 消耗 1 单位氧气。",
                "storage": "补给储藏间。修理包在公开货架上。",
            }
            exits = {
                "habitat": ("airlock", "storage"),
                "airlock": ("habitat", "solar_pad"),
                "solar_pad": ("airlock",),
                "storage": ("habitat",),
            }
            objects = {
                "suit_rack": ("airlock", "检查并穿戴宇航服后才能循环气闸。"),
                "broken_panel": ("solar_pad", "太阳能板损坏；需要 patch_kit 修复。"),
                "return_check": ("habitat", "面板修复且人员返回 habitat 后完成。"),
            }
            interactions = {"suit_rack": ("prepare", "cycle_out", "cycle_in")}
            items = {"patch_kit": "storage"}
            initial_oxygen, reserve, initial_battery = 10, 0, 0
        elif difficulty == "medium":
            rooms = {
                "habitat": "基地居住舱。屏幕公開六 tick 日照周期和剩余氧气储备。",
                "power_room": "电力室。battery_module 在此待装载。",
                "airlock": "气闸。出舱前检查氧气和返航余量。",
                "solar_array": "太阳能阵列。仅 DAY 相位可为电池充 1 单位。",
                "antenna": "舱外通信塔。通信模块需要电量至少 3。",
            }
            exits = {
                "habitat": ("power_room",),
                "power_room": ("habitat", "airlock"),
                "airlock": ("power_room", "solar_array", "antenna"),
                "solar_array": ("airlock",),
                "antenna": ("airlock",),
            }
            objects = {
                "airlock": ("airlock", "出舱前检查装备与氧气余量。"),
                "o2_station": ("habitat", "最多补充 6 单位氧气，受公开 reserve_oxygen 限制。"),
                "battery_module": ("power_room", "备用通信电池模块。"),
                "solar_charger": ("solar_array", "持有模块且当前为 DAY 时可充 1 单位。"),
                "comms_socket": ("antenna", "电池能量达到 3 后可安装模块并校准。"),
                "return_check": ("habitat", "通信塔模块更换并返回基地后完成。"),
            }
            interactions = {
                "o2_station": ("refill",),
                "solar_charger": ("charge",),
                "comms_socket": ("install",),
                "airlock": ("prepare", "cycle_out", "cycle_in"),
            }
            items = {"battery_module": "power_room"}
            initial_oxygen, reserve, initial_battery = 12, 6, 0
        else:
            rooms = {
                "habitat": "基地居住舱。每次 EVA 前核对本人氧气和队员余氧。",
                "supply": "补给区。唯一 charged_cell 和有限 reserve_oxygen 存放在此。",
                "airlock": "气闸。宇航员和被护送队员共用室外路线，但氧气分别计量。",
                "relay_point": "远侧中继点。队员 B 在安全应急棚内等待，不会随全球 tick 耗氧。",
                "crater_rim": "陨坑边缘。可选长线捷径，增加双方室外行动成本。",
                "mast": "信号桅杆。装入 charged_cell 后恢复定位信号。",
            }
            exits = {
                "habitat": ("supply",),
                "supply": ("habitat", "airlock"),
                "airlock": ("supply", "relay_point", "mast"),
                "relay_point": ("airlock", "crater_rim"),
                "crater_rim": ("relay_point", "mast"),
                "mast": ("airlock", "crater_rim"),
            }
            objects = {
                "o2_station": ("supply", "补充本人氧气最多 6 单位，消耗相同 reserve。"),
                "airlock": ("airlock", "先检查宇航服，再循环出舱或入舱。"),
                "cell_rack": ("supply", "恢复信号桅杆所需的唯一 charged_cell。"),
                "signal_mast": ("mast", "必须用 charged_cell 修复，之后才能安全导航救援。"),
                "astronaut_b": ("relay_point", "困在远侧中继点的队员；本人氧气单独计量。"),
                "rescue_check": ("habitat", "桅杆在线、队员回到 habitat 且双方余氧大于零后完成。"),
            }
            interactions = {
                "o2_station": ("refill",),
                "signal_mast": ("repair",),
                "astronaut_b": ("escort",),
                "airlock": ("prepare", "cycle_out", "cycle_in"),
            }
            items = {"charged_cell": "supply"}
            initial_oxygen, reserve, initial_battery = 12, 10, 1
        definition = {
            "scenario_id": f"LU-{difficulty[0].upper()}",
            "source_design_id": f"LU-{difficulty[0].upper()}",
            "family": "lunar",
            "difficulty": difficulty,
            "mechanic_version": "eva-oxygen-solar-budget-v2",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "sun_cycle": SUN,
            "outdoor_rooms": sorted(OUTDOOR),
            "initial": {
                "oxygen": initial_oxygen,
                "reserve_oxygen": reserve,
                "battery": initial_battery,
                "crew_oxygen": 5,
            },
        }
        super().__init__(
            family="lunar",
            difficulty=difficulty,
            scenario_id=f"LU-{difficulty[0].upper()}",
            public_goal=(
                "修复太阳能板并安全返回 habitat。"
                if difficulty == "easy"
                else "管理日照、电池和返航氧气，完成通信或双人救援并返回基地。"
            ),
            world="lunar-escape",
            world_version=f"lunar-escape-world-v3-{difficulty}-zh",
            mechanic_version="eva-oxygen-solar-budget-v2",
            start_room="habitat",
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _lunar(self) -> LunarState:
        return cast(LunarState, self._require_state())

    def _initial_state(self, seed: int) -> LunarState:
        oxygen = 10 if self._difficulty == "easy" else 12
        reserve = 0 if self._difficulty == "easy" else 6 if self._difficulty == "medium" else 10
        battery = 0 if self._difficulty != "hard" else 1
        return LunarState(
            seed=seed,
            current_room=self.start_room,
            oxygen=oxygen,
            reserve_oxygen=reserve,
            battery=battery,
        )

    def _apply_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if isinstance(action, PickupAction) and action.item == "charged_cell":
            if self._difficulty != "hard":
                return rejected("本关没有可用的 charged_cell。", "cell_unavailable")
        return super()._apply_action(action)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._lunar()
        if isinstance(action, InteractAction):
            if action.target in {"airlock", "suit_rack"} and action.choice == "prepare":
                if state.current_room != "airlock" or state.oxygen <= 2:
                    return rejected(
                        "需在气闸检查装备，且本人氧气必须大于返航最低值。", "eva_reserve_low"
                    )
                state.eva_prepared = True
                return applied("宇航服检查完成。", "eva_prepared")
            if action.target in {"airlock", "suit_rack"} and action.choice == "cycle_out":
                if state.current_room != "airlock" or not state.eva_prepared:
                    return rejected("需在气闸穿戴宇航服后才能循环出舱。", "suit_required")
                state.eva_active = True
                return applied("气闸已循环，舱外路线开放。", "airlock_opened")
            if action.target in {"airlock", "suit_rack"} and action.choice == "cycle_in":
                if state.current_room != "airlock" or not state.eva_active:
                    return rejected("人员需先通过气闸返回，才能循环入舱。", "airlock_not_active")
                state.eva_active = False
                return applied("气闸已循环入舱，氧气损耗暂停。", "airlock_closed")
            if action.target == "o2_station" and action.choice == "refill":
                if self._difficulty == "easy" or state.current_room not in {"habitat", "supply"}:
                    return rejected("补氧站只在基地或补给区开放。", "refill_station_unavailable")
                amount = min(6, state.reserve_oxygen, 12 - state.oxygen)
                if amount <= 0:
                    return rejected("预备氧气不足，不能继续补充。", "reserve_empty")
                state.reserve_oxygen -= amount
                state.oxygen += amount
                return applied(f"补充了 {amount} 单位氧气。", "oxygen_refilled")
            if action.target == "solar_charger" and action.choice == "charge":
                if self._difficulty != "medium" or state.current_room != "solar_array":
                    return rejected("太阳能充电设备当前不可用。", "charger_unavailable")
                if "battery_module" not in state.inventory:
                    return rejected("需先从 power_room 取回 battery_module。", "module_missing")
                if self._sun() != "DAY":
                    return rejected("当前处于阴影相位，太阳能阵列不能充电。", "no_sunlight")
                state.battery += 1
                state.solar_charges += 1
                return applied("电池模块充入 1 单位。", "battery_charged")
            if action.target == "comms_socket" and action.choice == "install":
                if (
                    self._difficulty != "medium"
                    or state.current_room != "antenna"
                    or "battery_module" not in state.inventory
                    or state.battery < 3
                ):
                    return rejected("通信模块需要在塔位安装且电量至少为 3。", "comms_precondition")
                state.comms_repaired = True
                return applied("通信模块已安装，信号校准完成。", "comms_restored")
            if action.target == "signal_mast" and action.choice == "repair":
                if (
                    self._difficulty != "hard"
                    or state.current_room != "mast"
                    or "charged_cell" not in state.inventory
                ):
                    return rejected(
                        "需在桅杆处使用已取得的 charged_cell。", "mast_repair_precondition"
                    )
                state.inventory.remove("charged_cell")
                state.mast_repaired = True
                return applied("信号桅杆恢复，可用于远端导航。", "mast_repaired")
            if action.target == "astronaut_b" and action.choice == "escort":
                if self._difficulty != "hard" or state.current_room != "relay_point":
                    return rejected(
                        "队员只能在 relay_point 现场接应，不能远程护送。", "crew_not_present"
                    )
                if not state.mast_repaired:
                    return rejected("信号桅杆尚未修复，不能安全定位返航路线。", "mast_offline")
                state.crew_escorting = True
                state.crew_rescued = True
                return applied("队员已加入护送；双方氧气分别计量。", "crew_escorted")
        if isinstance(action, UseAction):
            if (
                self._difficulty == "easy"
                and action.item == "patch_kit"
                and action.target == "broken_panel"
            ):
                if state.current_room != "solar_pad" or "patch_kit" not in state.inventory:
                    return rejected(
                        "需在太阳能板旁持有 patch_kit 才能维修。", "panel_repair_precondition"
                    )
                state.panel_repaired = True
                return applied("太阳能板修复完成。", "panel_repaired")
        return rejected("该动作不适用于月面 EVA 设备。", "lunar_action_rejected")

    def _sun(self) -> str:
        return SUN[self._require_state().tick % len(SUN)]

    def _edge_is_open(self, source: str, destination: str) -> bool:
        if "airlock" not in {source, destination}:
            return True
        other = destination if source == "airlock" else source
        if other in OUTDOOR:
            return self._lunar().eva_active
        return True

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._lunar()
        return (
            PublicStatusFact(id="sun_phase", value=self._sun()),
            PublicStatusFact(id="eva_oxygen", value=str(state.oxygen)),
            PublicStatusFact(id="reserve_oxygen", value=str(state.reserve_oxygen)),
            PublicStatusFact(id="battery", value=str(state.battery)),
            PublicStatusFact(id="solar_charges", value=str(state.solar_charges)),
            PublicStatusFact(id="eva_prepared", value=str(state.eva_prepared).lower()),
            PublicStatusFact(id="eva_active", value=str(state.eva_active).lower()),
            PublicStatusFact(id="panel_repaired", value=str(state.panel_repaired).lower()),
            PublicStatusFact(id="comms_repaired", value=str(state.comms_repaired).lower()),
            PublicStatusFact(id="mast_repaired", value=str(state.mast_repaired).lower()),
            PublicStatusFact(id="crew_oxygen", value=str(state.crew_oxygen)),
            PublicStatusFact(id="crew_escorting", value=str(state.crew_escorting).lower()),
            PublicStatusFact(id="crew_rescued", value=str(state.crew_rescued).lower()),
            PublicStatusFact(id="rescue_checked_in", value=str(state.rescue_checked_in).lower()),
        )

    def _advance_tick(self) -> None:
        state = self._lunar()
        if state.current_room in OUTDOOR:
            state.oxygen -= 1
            if state.crew_escorting:
                state.crew_oxygen -= 1
        if state.oxygen <= 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "EVA 氧气耗尽。"
        elif state.crew_escorting and state.crew_oxygen <= 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "被护送队员的独立氧气耗尽。"

    def _update_terminal_status(self) -> None:
        state = self._lunar()
        if state.terminal_status is not ScenarioStatus.RUNNING or state.current_room != "habitat":
            return
        if self._difficulty == "easy" and state.panel_repaired:
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {"oxygen_remaining": state.oxygen}
        elif self._difficulty == "medium" and state.comms_repaired:
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {
                "oxygen_remaining": state.oxygen,
                "reserve_oxygen_remaining": state.reserve_oxygen,
                "battery_remaining": state.battery,
            }
        elif self._difficulty == "hard" and state.mast_repaired and state.crew_rescued:
            state.rescue_checked_in = True
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {
                "oxygen_remaining": state.oxygen,
                "crew_oxygen_remaining": state.crew_oxygen,
                "reserve_oxygen_remaining": state.reserve_oxygen,
            }


__all__ = ["LunarScenario"]
