"""Public-clue logic puzzles with bounded, non-revealing submissions."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction, SubmitAction
from agent_arena.arena.models import InspectAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]


class PyramidState(ScenarioState):
    unlocked: bool = False
    bridge_fixed: bool = False
    wrong_attempts: int = 0
    cooldown: int = 0
    clues_seen: set[str] = set()


class PyramidScenario(ScenarioEnvironment):
    _answers = {"easy": "EAST", "medium": "SUN-MOON-STAR", "hard": "SUN-SCARAB-REED-EYE"}

    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        rooms = {
            "entrance": "沙漠金字塔入口。目标是依据公开符文打开宝库并带回文物。",
            "east_mural": "东侧壁画室。壁画线索可检查。",
            "sun_chamber": "日轮机关室。错误答案只会得到统一反馈。",
            "north_tomb": "北碑墓室，石碑符号提供排列约束。",
            "west_tomb": "西碑墓室，石碑符号提供排列约束。",
            "south_tomb": "南碑墓室，石碑符号提供排列约束。",
            "bridge": "裂隙桥室。固定桥梁后才能安全通过。",
            "rune_hall": "四符文审判厅。每条符文约束都影响唯一解。",
            "treasury": "宝库。取得本关指定文物后返回入口完成探索。",
        }
        if difficulty == "easy":
            exits = {
                "entrance": ("east_mural",),
                "east_mural": ("entrance", "sun_chamber"),
                "sun_chamber": ("east_mural", "treasury"),
                "treasury": ("sun_chamber",),
            }
            objects = {
                "east_mural_clue": ("east_mural", "航路壁画：日轮应指向 EAST。"),
                "sun_dial": ("sun_chamber", "日轮锁接受由壁画推出的方向答案。"),
                "treasury_door": ("sun_chamber", "正确提交后可开启。"),
                "map_scroll": ("treasury", "记载金字塔安全结构的地图卷轴。"),
            }
            interactions = {"sun_dial": ("submit_answer",), "treasury_door": ("open",)}
            items = {"map_scroll": "treasury"}
        elif difficulty == "medium":
            exits = {
                "entrance": ("north_tomb", "west_tomb", "south_tomb", "sun_chamber"),
                "north_tomb": ("entrance",),
                "west_tomb": ("entrance",),
                "south_tomb": ("entrance",),
                "sun_chamber": ("entrance", "treasury"),
                "treasury": ("sun_chamber",),
            }
            objects = {
                "north_stone": ("north_tomb", "北碑：SUN 位于 STAR 之前。"),
                "west_stone": ("west_tomb", "西碑：MOON 不在第一位。"),
                "south_stone": ("south_tomb", "南碑：STAR 不在中间。三符号各用一次。"),
                "sequence_lock": ("sun_chamber", "提交三符号的完整顺序。"),
                "treasury_door": ("sun_chamber", "正确提交后可开启。"),
                "stone_tablet": ("treasury", "记录古代天象的石板。"),
            }
            interactions = {"sequence_lock": ("submit_answer",), "treasury_door": ("open",)}
            items = {"stone_tablet": "treasury"}
        else:
            exits = {
                "entrance": ("bridge",),
                "bridge": ("entrance", "rune_hall"),
                "rune_hall": ("bridge", "treasury"),
                "treasury": ("rune_hall",),
            }
            objects = {
                "bridge_mechanism": ("bridge", "先固定桥梁。"),
                "rune_sun": ("rune_hall", "符文一：SUN 在 SCARAB 之前。"),
                "rune_scarab": ("rune_hall", "符文二：SUN 与 SCARAB 必须相邻。"),
                "rune_reed": ("rune_hall", "符文三：SUN 位于 REED 之前。"),
                "rune_eye": ("rune_hall", "符文四：REED 位于 EYE 之前；四符号各用一次。"),
                "judgment_lock": ("rune_hall", "提交四符文完整顺序。"),
                "treasury_door": ("rune_hall", "符文正确后在此开启宝库门。"),
                "seal_relic": ("treasury", "古堡封印遗物。"),
            }
            interactions = {
                "bridge_mechanism": ("fix",),
                "judgment_lock": ("submit_answer",),
                "treasury_door": ("open",),
            }
            items = {"seal_relic": "treasury"}
        rooms = {room: description for room, description in rooms.items() if room in exits}
        definition = {
            "scenario_id": f"PY-{difficulty[0].upper()}",
            "source_design_id": f"PY-{difficulty[0].upper()}",
            "family": "pyramid",
            "difficulty": difficulty,
            "mechanic_version": "public-constraint-puzzle-v1",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "private_answer": self._answers[difficulty],
        }
        super().__init__(
            family="pyramid",
            difficulty=difficulty,
            scenario_id=f"PY-{difficulty[0].upper()}",
            public_goal="根据分散的公开线索解开机关，取得本关文物并返回入口。",
            world="pyramid-escape",
            world_version=f"pyramid-escape-world-v3-{difficulty}-zh",
            mechanic_version="public-constraint-puzzle-v1",
            start_room="entrance",
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _pyramid(self) -> PyramidState:
        return cast(PyramidState, self._require_state())

    def _initial_state(self, seed: int) -> PyramidState:
        return PyramidState(seed=seed, current_room=self.start_room)

    def _apply_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._pyramid()
        if isinstance(action, InspectAction):
            result = super()._apply_action(action)
            if result[0].status.value == "success" and action.target in self._puzzle_clues:
                state.clues_seen.add(action.target)
            return result
        return super()._apply_action(action)

    @property
    def _puzzle_clues(self) -> set[str]:
        return {
            "easy": {"east_mural_clue"},
            "medium": {"north_stone", "west_stone", "south_stone"},
            "hard": {"rune_sun", "rune_scarab", "rune_reed", "rune_eye"},
        }[self._difficulty]

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._pyramid()
        if isinstance(action, SubmitAction):
            if self._difficulty == "hard" and not state.bridge_fixed:
                return rejected("裂隙桥尚未固定，符文机关暂不可提交。", "bridge_unfixed")
            if not self._puzzle_clues.issubset(state.clues_seen):
                return rejected("尚未调查本关所有公开符文线索。", "puzzle_clues_missing")
            if state.cooldown:
                return rejected("机关正在冷却；等待后可以再次提交。", "puzzle_cooldown")
            normalized = "-".join(action.answer.upper().replace(" ", "").split("-"))
            if action.target not in {"sun_dial", "sequence_lock", "judgment_lock"}:
                return rejected("提交目标不是当前谜题锁。", "wrong_puzzle_target")
            if normalized == self._answers[self._difficulty]:
                state.unlocked = True
                return applied("机关已接受完整符号排列。", "puzzle_solved")
            state.wrong_attempts += 1
            if state.wrong_attempts % 3 == 0:
                state.cooldown = 3
            return rejected("组合未匹配。公开线索保持不变。", "puzzle_incorrect")
        if isinstance(action, InteractAction):
            if action.target == "bridge_mechanism" and action.choice == "fix":
                state.bridge_fixed = True
                return applied("裂隙桥已固定。", "bridge_fixed")
            if action.target == "treasury_door" and action.choice == "open":
                if not state.unlocked:
                    return rejected("符文锁尚未解开。", "lock_closed")
                state.facts["treasury_open"] = True
                return applied("宝库门已打开。", "treasury_opened")
        return rejected("该动作不适用于金字塔机关。", "pyramid_action_rejected")

    def _edge_is_open(self, source: str, destination: str) -> bool:
        state = self._pyramid()
        pair = {source, destination}
        if pair in ({"sun_chamber", "treasury"}, {"rune_hall", "treasury"}):
            return bool(state.facts.get("treasury_open", False))
        if pair == {"bridge", "rune_hall"}:
            return state.bridge_fixed
        return True

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._pyramid()
        return (
            PublicStatusFact(id="wrong_attempts", value=str(state.wrong_attempts)),
            PublicStatusFact(id="cooldown", value=str(state.cooldown)),
            PublicStatusFact(id="bridge_fixed", value=str(state.bridge_fixed).lower()),
            PublicStatusFact(id="lock_unlocked", value=str(state.unlocked).lower()),
            PublicStatusFact(id="clues_seen", value=",".join(sorted(state.clues_seen)) or "none"),
            PublicStatusFact(
                id="treasury_open",
                value=str(bool(state.facts.get("treasury_open", False))).lower(),
            ),
        )

    def _advance_tick(self) -> None:
        state = self._pyramid()
        if state.cooldown:
            state.cooldown -= 1

    def _update_terminal_status(self) -> None:
        state = self._pyramid()
        required = {
            "easy": "map_scroll",
            "medium": "stone_tablet",
            "hard": "seal_relic",
        }[self._difficulty]
        if state.current_room == "entrance" and required in state.inventory and state.unlocked:
            state.terminal_status = ScenarioStatus.SUCCESS
            state.score_components = {"wrong_attempts": state.wrong_attempts}


__all__ = ["PyramidScenario"]
