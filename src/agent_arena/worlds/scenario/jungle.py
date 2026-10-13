"""Local landmark navigation with a turning gate and storm-driven river."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import Field

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction, SubmitAction
from agent_arena.arena.models import InspectAction, PickupAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]


class JungleState(ScenarioState):
    landmarks_seen: set[str] = Field(default_factory=set)
    gate_direction: str = "NORTH"
    shortcut_unlocked: bool = False
    marker_progress: int = 0
    altar_unlocked: bool = False
    return_gate_open: bool = False


class JungleScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        interactions: dict[str, tuple[str, ...]]
        if difficulty == "easy":
            rooms = {
                "camp": "丛林营地。侦察笔记记载三种树标各自指向的岔路。",
                "fork": "岔路口。红树、蓝树、白树三个本地出口标记清晰可见。",
                "red_tree": "红树路标。红色刻痕标记继续通往古碑的石阶。",
                "blue_tree": "蓝树路标。溪流声从此路传来，尽头有可返回的水边观测点。",
                "white_tree": "白树路标。白色树皮标记通往观测点，可沿原路回岔路。",
                "ruin": "古碑遗址。取回石碑记录，再回营地提交考察报告。",
                "creek": "溪边观测点。地面湿滑但退回蓝树岔路仍然安全。",
                "lookout": "林间观测点。可辨认营地烟柱，原路可返回。",
            }
            exits = {
                "camp": ("fork",),
                "fork": ("camp", "red_tree", "blue_tree", "white_tree"),
                "red_tree": ("fork", "ruin"),
                "blue_tree": ("fork", "creek"),
                "white_tree": ("fork", "lookout"),
                "ruin": ("red_tree",),
                "creek": ("blue_tree",),
                "lookout": ("white_tree",),
            }
            objects = {
                "scout_note": ("camp", "红色标记指向石碑，蓝色标记指向溪流，白色标记通往观测点。"),
                "red_marker": ("red_tree", "红色标记与石阶方向一致，沿路可达古碑。"),
                "blue_marker": ("blue_tree", "蓝色标记对应溪流观测点。"),
                "white_marker": ("white_tree", "白色标记对应林间观测点。"),
                "ancient_tablet": ("ruin", "古碑记录可带回营地。"),
                "field_report": ("camp", "携回 ruin_notes 后提交本次考察记录。"),
            }
            interactions = {"field_report": ("submit",)}
            items = {"ruin_notes": "ruin"}
            start = "camp"
            mechanic = "landmark-navigation-easy-v2"
        elif difficulty == "medium":
            rooms = {
                "camp": "丛林营地。任务笔记说明目标遗迹在东侧，但藤门目前可能封住路线。",
                "fork": "岔路口。石碑路标指示遗迹位于 east_path 之后。",
                "turntable": "转盘石碑。转动会即时改变藤门连通的路径边。",
                "north_path": "北侧藤径。只有藤门朝 NORTH 时才能进入遗迹方向。",
                "east_path": "东侧藤径。只有藤门朝 EAST 时才能进入遗迹方向。",
                "hidden_ruin": "隐蔽遗迹。带回石板后，可从安全捷径返回营地。",
            }
            exits = {
                "camp": ("fork",),
                "fork": ("camp", "turntable", "north_path", "east_path"),
                "turntable": ("fork",),
                "north_path": ("fork", "hidden_ruin"),
                "east_path": ("fork", "hidden_ruin"),
                "hidden_ruin": ("north_path", "east_path", "camp"),
            }
            objects = {
                "camp_note": ("camp", "目的地在东侧遗迹。"),
                "rune_marker": ("fork", "石碑刻痕：目标遗迹在 east_path 之后。"),
                "turntable": ("turntable", "设为 NORTH/EAST 会改变当前可通行的遗迹连边。"),
                "stone_tablet": ("hidden_ruin", "带回营地的遗迹石板。"),
                "return_shortcut": ("hidden_ruin", "取到石板后可解锁的返营捷径。"),
            }
            interactions = {
                "turntable": ("set_north", "set_east"),
                "return_shortcut": ("open_return",),
            }
            items = {"stone_tablet": "hidden_ruin"}
            start = "camp"
            mechanic = "turning-vine-gate-medium-v2"
        else:
            rooms = {
                "camp": "丛林营地。天气日志公开六 tick 水位周期。",
                "fork": "岔路口。山脊全年可通；河道仅低水位可渡。",
                "river_bank": "河岸。水位改变时仍可退回 fork，不会被留在关闭的连边上。",
                "high_ridge": "高山脊。全年稳定可走；藤叶与石片给出祭台序列线索。",
                "stone_circle": "石阵。按三处地标线索触碰正确顺序才会开放祭台。",
                "altar": "祭台。取回 relic_seed 并解开返程封印。",
                "return_pass": "返程古道。只有祭台封印打开后才能通往营地。",
            }
            exits = {
                "camp": ("fork",),
                "fork": ("camp", "river_bank", "high_ridge"),
                "river_bank": ("fork", "stone_circle"),
                "high_ridge": ("fork", "stone_circle"),
                "stone_circle": ("river_bank", "high_ridge", "altar"),
                "altar": ("stone_circle", "return_pass"),
                "return_pass": ("altar", "camp"),
            }
            objects = {
                "weather_log": ("camp", "storm_phase=tick%6；0–2 低水，3–5 涨水。"),
                "path_sign": ("fork", "高山脊全年可走；河道只在低水位连通石阵。"),
                "oak_mark": ("fork", "第一块路标记录 OAK。"),
                "fern_mark": ("river_bank", "第二块路标记录 FERN。"),
                "vine_mark": ("high_ridge", "第三块路标记录 VINE。"),
                "three_stones": ("stone_circle", "按三处公开标记的顺序触碰石阵。"),
                "return_seal": ("altar", "打开封印后经 return_pass 返回营地。"),
            }
            interactions = {
                "three_stones": ("oak", "fern", "vine"),
                "return_seal": ("unfasten",),
            }
            items = {"relic_seed": "altar"}
            start = "camp"
            mechanic = "storm-river-navigation-hard-v2"
        rooms = {room: description for room, description in rooms.items() if room in exits}
        definition = {
            "scenario_id": f"JU-{difficulty[0].upper()}",
            "source_design_id": f"JU-{difficulty[0].upper()}",
            "family": "jungle",
            "difficulty": difficulty,
            "mechanic_version": mechanic,
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "dynamic_edges": (
                "river_low_water"
                if difficulty == "hard"
                else "vine_orientation"
                if difficulty == "medium"
                else None
            ),
        }
        super().__init__(
            family="jungle",
            difficulty=difficulty,
            scenario_id=f"JU-{difficulty[0].upper()}",
            public_goal=(
                "依靠本地树标找到古碑，带回记录並在营地提交。"
                if difficulty == "easy"
                else "根据地标与动态边调整路线，带回目标并返回营地。"
            ),
            world="jungle-escape",
            world_version=f"jungle-escape-world-v3-{difficulty}-zh",
            mechanic_version=mechanic,
            start_room=start,
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _jungle(self) -> JungleState:
        return cast(JungleState, self._require_state())

    def _initial_state(self, seed: int) -> JungleState:
        return JungleState(seed=seed, current_room=self.start_room)

    def _apply_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._jungle()
        if isinstance(action, InspectAction):
            result = super()._apply_action(action)
            if result[0].status.value == "success":
                state.landmarks_seen.add(action.target)
            return result
        if isinstance(action, PickupAction):
            if action.item == "relic_seed" and not state.altar_unlocked:
                return rejected("石阵序列未完成，祭台尚不可达。", "altar_locked")
        if isinstance(action, SubmitAction) and self._difficulty == "easy":
            if action.target != "field_report" or action.answer.strip().lower() != "ruin_notes":
                return rejected("提交内容或目标不正确；需要带回 ruin_notes。", "report_invalid")
            if state.current_room != "camp" or "ruin_notes" not in state.inventory:
                return rejected("需带着 ruin_notes 返回营地后才能提交。", "notes_missing")
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {
                "landmarks_seen": len(state.landmarks_seen),
                "notes_returned": True,
            }
            return applied("古碑记录已在营地归档。", "field_report_submitted")
        return super()._apply_action(action)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于丛林地标。", "jungle_action_rejected")
        state = self._jungle()
        if self._difficulty == "medium" and action.target == "turntable":
            if action.choice not in {"set_north", "set_east"}:
                return rejected("转盘只接受 NORTH 或 EAST 方位。", "orientation_invalid")
            state.gate_direction = "NORTH" if action.choice == "set_north" else "EAST"
            return applied(f"藤门方向已转为 {state.gate_direction}。", "orientation_changed")
        if (
            self._difficulty == "medium"
            and action.target == "return_shortcut"
            and action.choice == "open_return"
        ):
            if "stone_tablet" not in state.inventory:
                return rejected("未取到石板，返营捷径尚未开放。", "shortcut_precondition")
            state.shortcut_unlocked = True
            return applied("遗迹返营捷径已打开。", "shortcut_opened")
        if self._difficulty == "hard" and action.target == "three_stones":
            required_marks = {"oak_mark", "fern_mark", "vine_mark"}
            if not required_marks.issubset(state.landmarks_seen):
                return rejected("三处地标尚未全部调查，石阵线索不完整。", "landmarks_missing")
            sequence = ("oak", "fern", "vine")
            if state.marker_progress >= len(sequence):
                return rejected("石阵序列已完成，无需重复触碰。", "sequence_complete")
            expected = sequence[state.marker_progress]
            if action.choice != expected:
                state.marker_progress = 0
                return rejected(
                    "石阵次序不匹配，进度已清零，可按已发现地标重试。", "marker_sequence_reset"
                )
            state.marker_progress += 1
            if state.marker_progress == len(sequence):
                state.altar_unlocked = True
                return applied("三块路标顺序吻合，祭台通道已开放。", "altar_unlocked")
            return applied("石阵接受了当前路标。", "marker_recorded")
        if (
            self._difficulty == "hard"
            and action.target == "return_seal"
            and action.choice == "unfasten"
        ):
            if not state.altar_unlocked or "relic_seed" not in state.inventory:
                return rejected("需先开放祭台并取得 relic_seed。", "return_seal_precondition")
            state.return_gate_open = True
            return applied("返程封印已解开。", "return_gate_opened")
        return rejected("该地标当前不接受此操作。", "jungle_action_rejected")

    def _edge_is_open(self, source: str, destination: str) -> bool:
        state = self._jungle()
        pair = {source, destination}
        if self._difficulty == "medium":
            if pair == {"north_path", "hidden_ruin"}:
                return source == "hidden_ruin" or state.gate_direction == "NORTH"
            if pair == {"east_path", "hidden_ruin"}:
                return source == "hidden_ruin" or state.gate_direction == "EAST"
            if pair == {"hidden_ruin", "camp"}:
                return state.shortcut_unlocked
        if self._difficulty == "hard":
            if pair == {"river_bank", "stone_circle"}:
                return self._weather_phase() == "LOW"
            if pair == {"stone_circle", "altar"}:
                return state.altar_unlocked
            if pair == {"altar", "return_pass"} or pair == {"return_pass", "camp"}:
                return state.return_gate_open
        return True

    def _weather_phase(self) -> str:
        return "LOW" if self._require_state().tick % 6 < 3 else "HIGH"

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._jungle()
        facts = [
            PublicStatusFact(
                id="landmarks_seen", value=",".join(sorted(state.landmarks_seen)) or "none"
            ),
            PublicStatusFact(id="gate_direction", value=state.gate_direction),
            PublicStatusFact(id="shortcut_unlocked", value=str(state.shortcut_unlocked).lower()),
            PublicStatusFact(id="marker_progress", value=str(state.marker_progress)),
            PublicStatusFact(id="altar_unlocked", value=str(state.altar_unlocked).lower()),
            PublicStatusFact(id="return_gate_open", value=str(state.return_gate_open).lower()),
        ]
        if self._difficulty == "hard":
            facts.append(PublicStatusFact(id="weather_phase", value=self._weather_phase()))
        return tuple(facts)

    def _update_terminal_status(self) -> None:
        state = self._jungle()
        if (
            self._difficulty == "medium"
            and state.current_room == "camp"
            and "stone_tablet" in state.inventory
        ):
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {
                "landmarks_seen": len(state.landmarks_seen),
                "tablet_returned": True,
            }
        elif (
            self._difficulty == "hard"
            and state.current_room == "camp"
            and state.return_gate_open
            and "relic_seed" in state.inventory
        ):
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {
                "landmarks_seen": len(state.landmarks_seen),
                "relic_returned": True,
                "return_gate_open": True,
            }


__all__ = ["JungleScenario"]
