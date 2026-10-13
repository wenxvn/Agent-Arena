"""Tide, fog, lens direction and staged beacon rules."""

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
TIDES = ("HIGH", "RISING", "LOW", "FALLING")


class LighthouseState(ScenarioState):
    direction: str = "NORTH"
    color: str = "white"
    lamp_on: bool = False
    sequence: list[str] = []
    rescue_confirmed: bool = False
    expired: bool = False


class LighthouseScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        rooms = {
            "keeper_house": "灯塔守望室。航海日志公开说明本关航道与救援窗口。",
            "tower_base": "灯塔基座。信号廊可以查看航道图。",
            "lamp_room": "灯室。潮相和雾相会随公开 tick 按固定周期变化。",
            "signal_gallery": "信号廊。航道标记给出镜头朝向线索。",
            "east_pier": "东湾码头。救援船确认后可登船。",
            "west_dock": "西侧码头。第二阶段握手成功后可以登船。",
            "north_beacon": "北侧信标站，完成三段信号后等待救援。",
        }
        if difficulty == "easy":
            exits = {
                "keeper_house": ("tower_base",),
                "tower_base": ("keeper_house", "lamp_room", "east_pier"),
                "lamp_room": ("tower_base",),
                "east_pier": ("tower_base",),
            }
            objects = {
                "shipping_log": ("keeper_house", "救援船将在低潮通过东侧航道。"),
                "lens": ("lamp_room", "镜头可调整为 NORTH、EAST 或 WEST。东湾航向为 EAST。"),
                "beacon_switch": ("lamp_room", "点灯并在低潮发送有效信号。"),
                "signal_flag": ("east_pier", "救援确认后登船。"),
            }
            interactions = {
                "lens": ("north", "east", "west"),
                "beacon_switch": ("on", "off", "send_signal"),
                "signal_flag": ("board_rescue",),
            }
        elif difficulty == "medium":
            exits = {
                "keeper_house": ("tower_base",),
                "tower_base": ("keeper_house", "lamp_room", "signal_gallery", "west_dock"),
                "lamp_room": ("tower_base",),
                "signal_gallery": ("tower_base",),
                "west_dock": ("tower_base",),
            }
            objects = {
                "port_manual": ("keeper_house", "港务手册：白灯确认必须先于红灯靠港。"),
                "route_chart": (
                    "signal_gallery",
                    "船从西侧防波堤入港；镜头朝向 WEST。红灯须在高潮发出。",
                ),
                "tide_gauge": ("lamp_room", "潮相按 HIGH、RISING、LOW、FALLING 循环。"),
                "lens": ("lamp_room", "镜头方向控制信号航向。"),
                "lamp": ("lamp_room", "先白灯确认，再红灯引导。"),
                "rescue_boat": ("west_dock", "握手完成后登船。"),
            }
            interactions = {
                "lens": ("west", "east", "north"),
                "lamp": ("white", "red", "emit"),
                "rescue_boat": ("board",),
            }
        else:
            exits = {
                "keeper_house": ("tower_base",),
                "tower_base": ("keeper_house", "lamp_room", "signal_gallery", "north_beacon"),
                "lamp_room": ("tower_base",),
                "signal_gallery": ("tower_base",),
                "north_beacon": ("tower_base",),
            }
            objects = {
                "beacon_schedule": (
                    "keeper_house",
                    "信号顺序为短、长、短；末段只在高潮且无雾时有效。",
                ),
                "coast_chart": ("signal_gallery", "镜头应指向 NORTH；潮相和雾况都公开循环。"),
                "tide_gauge": ("lamp_room", "四相潮历：HIGH、RISING、LOW、FALLING。"),
                "fog_sensor": ("lamp_room", "雾况按 CLEAR、CLEAR、FOG 循环。"),
                "lens": ("lamp_room", "调整信标方向。"),
                "signal_console": ("lamp_room", "发送 SHORT、LONG、SHORT 三段信号。"),
                "rescue_beacon": ("north_beacon", "末段信号确认后启动救援。"),
            }
            interactions = {
                "lens": ("north", "east", "west"),
                "signal_console": ("short", "long", "emit"),
                "rescue_beacon": ("board",),
            }
        rooms = {room: description for room, description in rooms.items() if room in exits}
        definition = {
            "scenario_id": f"LH-{difficulty[0].upper()}",
            "source_design_id": f"LH-{difficulty[0].upper()}",
            "family": "lighthouse",
            "difficulty": difficulty,
            "mechanic_version": "tide-fog-beacon-v1",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": {},
            "cycle": {"tide": TIDES, "fog": ("CLEAR", "CLEAR", "FOG")},
        }
        super().__init__(
            family="lighthouse",
            difficulty=difficulty,
            scenario_id=f"LH-{difficulty[0].upper()}",
            public_goal="依据公开航道与潮雾周期发出有效信标，并在正确码头完成救援。",
            world="lighthouse-escape",
            world_version=f"lighthouse-escape-world-v3-{difficulty}-zh",
            mechanic_version="tide-fog-beacon-v1",
            start_room="keeper_house",
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items={},
            definition=definition,
            seed=seed,
        )

    def _lighthouse(self) -> LighthouseState:
        return cast(LighthouseState, self._require_state())

    def _initial_state(self, seed: int) -> LighthouseState:
        return LighthouseState(seed=seed, current_room=self.start_room)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于信标设备。", "beacon_action_rejected")
        state = self._lighthouse()
        if action.target == "lens" and action.choice.upper() in {"NORTH", "EAST", "WEST"}:
            state.direction = action.choice.upper()
            return applied(f"镜头已转向 {state.direction}。", "lens_set")
        if self._difficulty == "easy":
            if action.target == "beacon_switch" and action.choice == "on":
                state.lamp_on = True
                return applied("归航灯已点亮。", "beacon_lit")
            if action.target == "beacon_switch" and action.choice == "send_signal":
                if state.direction != "EAST" or not state.lamp_on or self._tide() != "LOW":
                    return rejected(
                        "信号未被东湾航道接收；请查看镜头、灯光和当前潮相。",
                        "signal_not_acknowledged",
                    )
                state.rescue_confirmed = True
                return applied("东湾救援船已确认归航信号。", "rescue_confirmed")
            if action.target == "signal_flag" and action.choice == "board_rescue":
                return self._board(state)
        elif self._difficulty == "medium":
            if action.target == "lamp" and action.choice in {"white", "red"}:
                state.color = action.choice
                return applied(f"信标颜色已设为 {state.color.upper()}。", "lamp_color_set")
            if action.target == "lamp" and action.choice == "emit":
                if state.direction != "WEST":
                    return rejected("信号方向与西侧航道图不符。", "wrong_bearing")
                if not state.sequence and state.color == "white":
                    state.sequence.append("white")
                    return applied("白灯确认已登记；第二阶段仍需符合潮相。", "white_acknowledged")
                if state.sequence == ["white"] and state.color == "red" and self._tide() == "HIGH":
                    state.sequence.append("red")
                    state.rescue_confirmed = True
                    return applied("红灯引导已获西侧救援队确认。", "red_acknowledged")
                return rejected("当前灯色、顺序或潮相不符合握手阶段。", "signal_not_acknowledged")
            if action.target == "rescue_boat" and action.choice == "board":
                return self._board(state)
        else:
            if action.target == "signal_console" and action.choice in {"short", "long"}:
                expected = ("short", "long", "short")
                if (
                    len(state.sequence) >= len(expected)
                    or action.choice != expected[len(state.sequence)]
                ):
                    return rejected(
                        "此段信号与公开序列不符，已确认部分仍保留。", "sequence_rejected"
                    )
                state.sequence.append(action.choice)
                return applied(f"信号阶段 {len(state.sequence)} 已确认。", "signal_stage_confirmed")
            if action.target == "signal_console" and action.choice == "emit":
                if state.direction != "NORTH":
                    return rejected("信标方向与海岸图不一致。", "wrong_bearing")
                if len(state.sequence) < 2:
                    return rejected("前两段信号尚未确认。", "signal_stage_missing")
                if self._tide() != "HIGH" or self._fog() != "CLEAR":
                    return rejected(
                        "末段信号未被接收；潮雾窗口当前不安全。", "rescue_window_closed"
                    )
                state.sequence.append("short")
                state.rescue_confirmed = True
                return applied("三段信标已获北侧救援船确认。", "rescue_confirmed")
            if action.target == "rescue_beacon" and action.choice == "board":
                return self._board(state)
        return rejected("该设备当前不接受此操作。", "beacon_action_rejected")

    def _board(self, state: LighthouseState) -> ScenarioActionResult:
        correct_room = {"easy": "east_pier", "medium": "west_dock", "hard": "north_beacon"}[
            self._difficulty
        ]
        if state.current_room != correct_room or not state.rescue_confirmed:
            return rejected("当前地点或救援确认状态不满足登船条件。", "boarding_rejected")
        state.terminal_status = ScenarioStatus.SUCCESS
        state.score_components = {
            "signals_confirmed": len(state.sequence) + int(state.rescue_confirmed)
        }
        return applied("已在正确码头登船，救援完成。", "rescue_boarded")

    def _tide(self) -> str:
        return TIDES[self._require_state().tick % len(TIDES)]

    def _fog(self) -> str:
        return ("CLEAR", "CLEAR", "FOG")[self._require_state().tick % 3]

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._lighthouse()
        return (
            PublicStatusFact(id="tide", value=self._tide()),
            PublicStatusFact(id="fog", value=self._fog()),
            PublicStatusFact(id="lens_direction", value=state.direction),
            PublicStatusFact(id="lamp_on", value=str(state.lamp_on).lower()),
            PublicStatusFact(id="lamp_color", value=state.color.upper()),
            PublicStatusFact(id="confirmed_stages", value=str(len(state.sequence))),
            PublicStatusFact(id="rescue_confirmed", value=str(state.rescue_confirmed).lower()),
        )


__all__ = ["LighthouseScenario"]
