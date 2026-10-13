"""Weather, body heat and rescue logistics rules for polar scenarios."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import Field

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
WEATHER = ("CLEAR", "CLEAR", "STORM", "STORM")
HARD_WEATHER = ("CLEAR", "CLEAR", "CLEAR", "STORM", "STORM", "STORM")


class PolarState(ScenarioState):
    body_heat: int = 10
    fuel: int = 2
    rescued: set[str] = Field(default_factory=set)
    rope_fixed: bool = False
    escorted_crew: str | None = None
    crew_heat: dict[str, int] = Field(default_factory=dict)
    sample_delivered: bool = False


class PolarScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        self._weather = HARD_WEATHER if difficulty == "hard" else WEATHER

        if difficulty == "easy":
            rooms = {
                "station": "极地前哨站。天气广播公开四回合周期：晴、晴、暴雪、暴雪。",
                "observatory": "气象观测点。可选地点，往返会消耗回合。",
                "snow_pass": "雪岭通道。室外行动按当前天气消耗体热。",
                "shelter": "应急棚屋。连接通讯天线即可呼叫救援。",
            }
            exits = {
                "station": ("snow_pass", "observatory"),
                "observatory": ("station",),
                "snow_pass": ("station", "shelter"),
                "shelter": ("snow_pass",),
            }
            objects = {
                "weather_radio": (
                    "station",
                    "天气周期为晴、晴、暴雪、暴雪；每个有效行动推进一相。",
                ),
                "heater": ("station", "室内消耗 1 燃料恢复 4 点体热。"),
                "radio_antenna": ("shelter", "连接天线后可以发出救援信号。"),
            }
            interactions = {
                "heater": ("warm",),
                "radio_antenna": ("activate",),
            }
            items: dict[str, str] = {}
            outdoor_rooms = {"snow_pass"}
            fuel = 2
        elif difficulty == "medium":
            rooms = {
                "station": "科考站。带回冰芯后须在样本接收器登记。",
                "supply_hut": "补给棚。室内供暖会消耗与雪地车共用的燃料。",
                "ice_field": "冰原。步行路线上的室外区域。",
                "drill_site": "钻探站。冰芯在此等待回收。",
                "vehicle_pad": "雪地车停靠点。雪地车只在此处启动。",
                "return_route": "步行返程通道。与钻探站和科考站相连。",
            }
            exits = {
                "station": ("supply_hut",),
                "supply_hut": ("station", "ice_field", "vehicle_pad"),
                "ice_field": ("supply_hut", "drill_site"),
                "drill_site": ("ice_field", "return_route"),
                "return_route": ("drill_site", "station"),
                "vehicle_pad": ("supply_hut",),
            }
            objects = {
                "supply_log": ("supply_hut", "雪地车往返各消耗 1 燃料；也可徒步，但须管理体热。"),
                "heater": ("supply_hut", "室内消耗 1 燃料恢复 4 点体热。"),
                "snowmobile": ("vehicle_pad", "消耗 1 燃料直接从停靠点抵达钻探站。"),
                "snowmobile_return": ("drill_site", "消耗 1 燃料直接返回雪地车停靠点。"),
                "sample_receiver": ("station", "必须携带冰芯回到科考站并在此登记。"),
            }
            interactions = {
                "heater": ("warm",),
                "snowmobile": ("ride_to_drill",),
                "snowmobile_return": ("ride_to_pad",),
                "sample_receiver": ("deliver",),
            }
            items = {"ice_core": "drill_site"}
            outdoor_rooms = {"ice_field", "drill_site", "return_route"}
            fuel = 2
        else:
            rooms = {
                "base": "极地主站。指挥板公开队员位置、天气和至少保留 1 单位返程燃料的要求。",
                "heated_hut": "保暖小屋。可以取暖；取得绳索套件后可固定通往山脊的冰桥。",
                "drill_camp": "钻探营地。研究员 A 等待分次护送。",
                "ridge": "山脊。室外区域；固定冰桥后可由保暖小屋抵达。",
                "weather_post": "气象哨位。研究员 B 等待分次护送。",
            }
            exits = {
                "base": ("heated_hut", "ridge"),
                "heated_hut": ("base", "drill_camp", "ridge"),
                "drill_camp": ("heated_hut",),
                "ridge": ("base", "weather_post", "heated_hut"),
                "weather_post": ("ridge",),
            }
            objects = {
                "control_board": (
                    "base",
                    "研究员 A 在钻探营地、研究员 B 在气象哨位；天气晴三回合、暴雪三回合循环。",
                ),
                "fuel_depot": ("base", "救援完成时必须至少保留 1 单位燃料。"),
                "heater": ("heated_hut", "室内消耗 1 单位燃料，玩家和同行者各恢复 4 点体热。"),
                "rope_kit": ("heated_hut", "取得后可在小屋固定冰桥，开放小屋与山脊间的捷径。"),
                "researcher_a": (
                    "drill_camp",
                    "研究员 A；一次只能护送一名队员。抵达主站后才算获救。",
                ),
                "researcher_b": (
                    "weather_post",
                    "研究员 B；一次只能护送一名队员。抵达主站后才算获救。",
                ),
                "rescue_roster": ("base", "两名研究员回到主站且燃料至少剩 1，才算完整撤离。"),
            }
            interactions = {
                "heater": ("rest",),
                "rope_kit": ("fix",),
                "researcher_a": ("escort",),
                "researcher_b": ("escort",),
            }
            items = {"rope_kit": "heated_hut"}
            outdoor_rooms = {"drill_camp", "ridge", "weather_post"}
            fuel = 4

        self._outdoor_rooms = outdoor_rooms
        definition = {
            "scenario_id": f"PO-{difficulty[0].upper()}",
            "source_design_id": f"PO-{difficulty[0].upper()}",
            "family": "polar",
            "difficulty": difficulty,
            "mechanic_version": "weather-heat-logistics-v2",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "weather": self._weather,
            "outdoor_rooms": sorted(outdoor_rooms),
            "initial": {"body_heat": 10, "fuel": fuel},
        }
        super().__init__(
            family="polar",
            difficulty=difficulty,
            scenario_id=f"PO-{difficulty[0].upper()}",
            public_goal={
                "easy": "依据公开天气管理体热，启动棚屋天线请求救援。",
                "medium": "管理体热和共用燃料，将冰芯带回科考站登记。",
                "hard": "分次护送两名队员回主站，并至少保留 1 单位燃料。",
            }[difficulty],
            world="polar-escape",
            world_version=f"polar-escape-world-v3-{difficulty}-zh",
            mechanic_version="weather-heat-logistics-v2",
            start_room={"easy": "station", "medium": "station", "hard": "base"}[difficulty],
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _polar(self) -> PolarState:
        return cast(PolarState, self._require_state())

    def _initial_state(self, seed: int) -> PolarState:
        return PolarState(
            seed=seed,
            current_room=self.start_room,
            body_heat=10,
            fuel={"easy": 2, "medium": 2, "hard": 4}[self._difficulty],
        )

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于极地设备。", "polar_action_rejected")
        state = self._polar()

        if action.target == "heater" and action.choice in {"warm", "rest"}:
            if state.current_room in self._outdoor_rooms:
                return rejected("只能在室内使用取暖器。", "heater_outdoors")
            if state.fuel <= 0:
                return rejected("取暖燃料已用尽。", "heater_fuel_empty")
            state.fuel -= 1
            state.body_heat = min(10, state.body_heat + 4)
            if state.escorted_crew is not None:
                crew_heat = state.crew_heat[state.escorted_crew]
                state.crew_heat[state.escorted_crew] = min(10, crew_heat + 4)
            return applied("消耗 1 单位燃料，室内取暖恢复体热。", "body_heat_restored")

        if action.target == "radio_antenna" and action.choice == "activate":
            if self._difficulty != "easy" or state.current_room != "shelter":
                return rejected("必须抵达应急棚屋才能启动天线。", "antenna_unavailable")
            state.terminal_status = ScenarioStatus.SUCCESS
            return applied("应急天线已发出救援信号。", "rescue_signaled")

        if action.target == "snowmobile" and action.choice == "ride_to_drill":
            if self._difficulty != "medium" or state.current_room != "vehicle_pad":
                return rejected("雪地车只能从指定停靠点出发。", "vehicle_not_docked")
            if state.fuel <= 0:
                return rejected("雪地车燃料不足。", "vehicle_fuel_empty")
            state.fuel -= 1
            state.current_room = "drill_site"
            return applied("雪地车消耗 1 单位燃料抵达钻探站，未经过冰原。", "vehicle_arrived")

        if action.target == "snowmobile_return" and action.choice == "ride_to_pad":
            if self._difficulty != "medium" or state.current_room != "drill_site":
                return rejected("返程雪地车只能从钻探站出发。", "vehicle_not_docked")
            if state.fuel <= 0:
                return rejected("雪地车燃料不足；可沿公开步行路线返回。", "vehicle_fuel_empty")
            state.fuel -= 1
            state.current_room = "vehicle_pad"
            return applied("雪地车消耗 1 单位燃料抵达停靠点，未经过冰原。", "vehicle_arrived")

        if action.target == "sample_receiver" and action.choice == "deliver":
            if self._difficulty != "medium" or state.current_room != "station":
                return rejected("必须回到科考站才能登记冰芯。", "sample_receiver_unavailable")
            if "ice_core" not in state.inventory:
                return rejected("尚未携带冰芯样本。", "sample_missing")
            state.sample_delivered = True
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {"fuel_remaining": state.fuel, "body_heat": state.body_heat}
            return applied("冰芯已登记，样本任务完成。", "sample_delivered")

        if action.target == "rope_kit" and action.choice == "fix":
            if self._difficulty != "hard" or state.current_room != "heated_hut":
                return rejected("只能在保暖小屋固定绳桥。", "bridge_unavailable")
            if "rope_kit" not in state.inventory:
                return rejected("没有绳索套件，无法固定冰桥。", "rope_missing")
            state.rope_fixed = True
            return applied("冰桥已固定，保暖小屋与山脊间的捷径开放。", "bridge_fixed")

        if action.target in {"researcher_a", "researcher_b"} and action.choice == "escort":
            if self._difficulty != "hard":
                return rejected("当前场景没有可护送的队员。", "crew_unavailable")
            crew = "a" if action.target == "researcher_a" else "b"
            expected_room = {"a": "drill_camp", "b": "weather_post"}[crew]
            if state.current_room != expected_room:
                return rejected("目标队员不在当前位置。", "crew_not_present")
            if crew in state.rescued:
                return rejected("该队员已经获救。", "crew_already_rescued")
            if state.escorted_crew is not None:
                return rejected("一次只能护送一名队员。", "escort_capacity_full")
            state.escorted_crew = crew
            state.crew_heat[crew] = 6
            return applied("队员已加入单人护送队伍，体热从 6 点开始计量。", "crew_escorted")

        return rejected("该设备当前不接受此操作。", "polar_action_rejected")

    def _edge_is_open(self, source: str, destination: str) -> bool:
        if self._difficulty == "hard" and {source, destination} == {"heated_hut", "ridge"}:
            return self._polar().rope_fixed
        return True

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._polar()
        clue_ids = {
            "easy": ("weather_radio", "radio_antenna"),
            "medium": ("supply_log", "sample_receiver"),
            "hard": ("control_board", "fuel_depot", "rope_kit"),
        }[self._difficulty]
        facts = [
            PublicStatusFact(id="weather", value=self._weather[state.tick % len(self._weather)]),
            PublicStatusFact(id="body_heat", value=str(state.body_heat)),
            PublicStatusFact(id="fuel", value=str(state.fuel)),
            PublicStatusFact(id="rescued_crew", value=",".join(sorted(state.rescued)) or "none"),
            PublicStatusFact(
                id="escorted_crew", value=state.escorted_crew if state.escorted_crew else "none"
            ),
            PublicStatusFact(id="rope_fixed", value=str(state.rope_fixed).lower()),
            PublicStatusFact(id="sample_delivered", value=str(state.sample_delivered).lower()),
        ]
        facts.extend(
            PublicStatusFact(
                id=f"{clue}_read", value=str(clue in state.revealed_objects).lower()
            )
            for clue in clue_ids
        )
        facts.extend(
            PublicStatusFact(id=f"crew_{crew}_heat", value=str(heat))
            for crew, heat in sorted(state.crew_heat.items())
        )
        return tuple(facts)

    def _advance_tick(self) -> None:
        state = self._polar()
        # The effect uses the weather phase shown in the observation before this action.
        weather = self._weather[(state.tick - 1) % len(self._weather)]
        if state.current_room in self._outdoor_rooms:
            heat_loss = 2 if weather == "STORM" else 1
            state.body_heat -= heat_loss
            if state.escorted_crew is not None:
                state.crew_heat[state.escorted_crew] -= heat_loss

        if state.escorted_crew is not None and state.current_room == "base":
            state.rescued.add(state.escorted_crew)
            state.crew_heat.pop(state.escorted_crew, None)
            state.escorted_crew = None

        if state.body_heat <= 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "户外体热降至零。"
        elif state.escorted_crew is not None and state.crew_heat[state.escorted_crew] <= 0:
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = f"同行队员 {state.escorted_crew} 体热降至零。"

        if self._difficulty == "hard" and state.current_room == "base" and len(state.rescued) == 2:
            if state.fuel >= 1:
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "fuel_remaining": state.fuel,
                    "body_heat": state.body_heat,
                }
            else:
                state.terminal_status = ScenarioStatus.PARTIAL_SUCCESS
                state.failure_reason = "两名队员获救，但返程燃料低于 1。"


__all__ = ["PolarScenario"]
