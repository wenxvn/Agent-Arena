"""Evidence-gated dialogue and deduction scenarios from the V3 outline."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import Field

from agent_arena.arena import (
    InteractAction,
    PublicStatusFact,
    ScenarioAction,
    SubmitAction,
    ToolStatus,
    UseAction,
)
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


class CastleState(ScenarioState):
    evidence: set[str] = Field(default_factory=set)
    key_revealed: bool = False
    library_unlocked: bool = False
    verdict_accepted: bool = False
    secret_study_open: bool = False
    case_closed: bool = False


class CastleScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        if difficulty == "easy":
            rooms = {
                "great_hall": "大礼堂。失踪的档案钥匙需要通过问话线索追查。",
                "gatehouse": "门房。守门人记得钥匙交还的地点。",
                "kitchen": "厨房。厨师知道钥匙后来存放在哪里。",
                "pantry": "储藏室。蓝色钥匙盒放着取回档案钥匙的最后线索。",
                "library": "书房。带回档案钥匙后登记失踪档案。",
            }
            exits = {
                "great_hall": ("gatehouse", "kitchen", "library"),
                "gatehouse": ("great_hall",),
                "kitchen": ("great_hall", "pantry"),
                "pantry": ("kitchen",),
                "library": ("great_hall",),
            }
            objects = {
                "gatekeeper": ("gatehouse", "守门人。询问钥匙归还地点。"),
                "cook": ("kitchen", "厨师。询问钥匙盒的位置。"),
                "key_box": ("pantry", "蓝色钥匙盒。取得两条口述线索后才可调查。"),
                "library_door": ("great_hall", "书房门锁需要档案钥匙。"),
                "archive_desk": ("library", "登记找回的档案钥匙并结案。"),
            }
            interactions = {
                "gatekeeper": ("where_key",),
                "cook": ("where_stored",),
                "archive_desk": ("register",),
            }
            items = {"archive_key": "pantry"}
            required = {"gatekeeper_key_location", "cook_box_location"}
        elif difficulty == "medium":
            rooms = {
                "hall": "大厅。封存卷轴在午夜前被移走；需交叉核对证词和门禁记录。",
                "watchtower": "钟楼。守卫能确认自己和管事在午夜前的位置。",
                "courtyard": "庭院。管事聲称整晚都在此处。",
                "infirmary": "医务室。医师和病历可核实救治时间。",
                "records_room": "记录室。门禁日志、校时报告和密室门在此。",
                "secret_study": "密室书房。被移走的封存卷轴在这里。",
            }
            exits = {
                "hall": ("watchtower", "courtyard", "infirmary", "records_room"),
                "watchtower": ("hall",),
                "courtyard": ("hall",),
                "infirmary": ("hall",),
                "records_room": ("hall", "secret_study"),
                "secret_study": ("records_room",),
            }
            objects = {
                "guard": ("watchtower", "守卫。询问午夜前的巡逻路线。"),
                "caretaker": ("courtyard", "管事。询问午夜前的行踪。"),
                "physician": ("infirmary", "医师。询问当晚的救治记录。"),
                "access_log": ("records_room", "门禁记录：23:50 使用管事 caretaker badge 开门。"),
                "clock_report": ("records_room", "校时报告：门禁时钟误差不超过 1 分钟。"),
                "secret_study_door": ("records_room", "密室门可由被确认的 caretaker badge 解锁。"),
                "case_board": ("hall", "提交有证据支持的唯一嫌疑人；取回卷轴后结案。"),
            }
            interactions = {
                "guard": ("night_patrol",),
                "caretaker": ("where_were_you",),
                "physician": ("night_records",),
                "secret_study_door": ("open",),
                "case_board": ("close_case",),
            }
            items = {"sealed_scroll": "secret_study"}
            required = {"access_log", "clock_report", "guard_timeline"}
        else:
            rooms = {
                "grand_hall": "王室大厅。封印在 21:00—21:05 间遭到篡改；必须以证据提交唯一结论。",
                "key_archive": "钥匙档案室。唯一青铜钥匙的领取和归还记录在此。",
                "seal_chamber": "封印室。柜门记录与封蜡物证可检查。",
                "watch_post": "守卫岗。守卫名册和签名见证可排除守卫。",
                "infirmary": "医务室。连续救治的病历与患者签名可排除医师。",
                "servant_quarters": "仆役居所。管事可回答钥匙使用问题。",
                "secret_passage": "密道。调查到钥匙线索后可开放的可选捷径。",
            }
            exits = {
                "grand_hall": (
                    "key_archive",
                    "seal_chamber",
                    "watch_post",
                    "infirmary",
                    "servant_quarters",
                ),
                "key_archive": ("grand_hall", "secret_passage"),
                "seal_chamber": ("grand_hall", "secret_passage"),
                "watch_post": ("grand_hall",),
                "infirmary": ("grand_hall",),
                "servant_quarters": ("grand_hall",),
                "secret_passage": ("key_archive", "seal_chamber"),
            }
            objects = {
                "key_ledger": (
                    "key_archive",
                    "钥匙簿：20:50 MARIUS 领取唯一青铜钥匙，21:10 归还。",
                ),
                "seal_wax": ("seal_chamber", "封蜡物证：新蜡含有管事办公室使用的蓝蜡。"),
                "door_record": (
                    "seal_chamber",
                    "门记录：封印柜仅此钥匙可开，篡改发生于 21:00—21:05。",
                ),
                "guard_roster": (
                    "watch_post",
                    "守卫名册：GARETH 在 20:45—21:15 看守南门，有見证签名。",
                ),
                "guard_manuscript": (
                    "watch_post",
                    "守卫手稿：查到钥匙簿并核实名册后，可从钥匙档案室进入密道。",
                ),
                "medical_chart": (
                    "infirmary",
                    "病历：ELISE 在 20:40—21:15 连续救治，两名患者签名。",
                ),
                "marius": ("servant_quarters", "管事 MARIUS。询问其钥匙使用情况。"),
                "gareth": ("watch_post", "守卫 GARETH。询问其值勤地点。"),
                "elise": ("infirmary", "医师 ELISE。询问其当晚行踪。"),
                "verdict_desk": (
                    "grand_hall",
                    "格式：SUSPECT|EVIDENCE_A+EVIDENCE_B；物证 ID 见已调查证据。",
                ),
            }
            interactions = {
                "marius": ("key_access",),
                "gareth": ("where_were_you",),
                "elise": ("where_were_you",),
                "verdict_desk": ("review",),
            }
            items = {}
            required = {
                "key_ledger",
                "seal_wax",
                "door_record",
                "guard_roster",
                "medical_chart",
                "marius_statement",
                "gareth_statement",
                "elise_statement",
            }
        self._required_evidence = required
        definition = {
            "scenario_id": f"CA-{difficulty[0].upper()}",
            "source_design_id": f"CA-{difficulty[0].upper()}",
            "family": "castle",
            "difficulty": difficulty,
            "mechanic_version": "dialogue-evidence-deduction-v2",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": items,
            "required_evidence": sorted(required),
            "private_truth": "MARIUS" if difficulty == "hard" else None,
        }
        super().__init__(
            family="castle",
            difficulty=difficulty,
            scenario_id=f"CA-{difficulty[0].upper()}",
            public_goal=(
                "通过公开证词与物证找回档案钥匙并登记。"
                if difficulty == "easy"
                else "调查证词与物证，依据一致性找回卷轴或提交唯一结论。"
            ),
            world="castle-escape",
            world_version=f"castle-escape-world-v3-{difficulty}-zh",
            mechanic_version="dialogue-evidence-deduction-v2",
            start_room="great_hall"
            if difficulty == "easy"
            else "hall"
            if difficulty == "medium"
            else "grand_hall",
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items=items,
            definition=definition,
            seed=seed,
        )

    def _castle(self) -> CastleState:
        return cast(CastleState, self._require_state())

    def _initial_state(self, seed: int) -> CastleState:
        return CastleState(seed=seed, current_room=self.start_room)

    def _visible_objects(self) -> tuple[str, ...]:
        visible = super()._visible_objects()
        state = self._castle()
        if self._difficulty == "easy" and not self._required_evidence.issubset(state.evidence):
            return tuple(item for item in visible if item != "key_box" and item != "archive_key")
        return visible

    def _edge_is_open(self, source: str, destination: str) -> bool:
        state = self._castle()
        edge = {source, destination}
        if self._difficulty == "easy" and edge == {"great_hall", "library"}:
            return state.library_unlocked
        if self._difficulty == "medium" and edge == {"records_room", "secret_study"}:
            return state.secret_study_open
        if self._difficulty == "hard" and edge == {"key_archive", "secret_passage"}:
            return {"key_ledger", "guard_manuscript"}.issubset(state.evidence)
        return True

    def _apply_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._castle()
        if isinstance(action, InspectAction):
            if action.target == "key_box" and not self._required_evidence.issubset(state.evidence):
                return rejected("先从门卫和厨师处查明钥匙去向，再检查钥匙盒。", "key_box_clue_gate")
            result = super()._apply_action(action)
            if result[0].status is ToolStatus.SUCCESS:
                if action.target in self._evidence_ids:
                    state.evidence.add(action.target)
                if action.target == "key_box":
                    state.key_revealed = True
            return result
        if isinstance(action, PickupAction) and action.item == "archive_key":
            if not state.key_revealed:
                return rejected("钥匙盒尚未根据两条口述线索调查。", "key_not_revealed")
        return super()._apply_action(action)

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        state = self._castle()
        if isinstance(action, InteractAction):
            dialogue = self._dialogue().get((action.target, action.choice))
            if dialogue is not None:
                evidence_id, statement = dialogue
                state.evidence.add(evidence_id)
                return applied(statement, "testimony_recorded")
            if (
                self._difficulty == "easy"
                and action.target == "archive_desk"
                and action.choice == "register"
            ):
                if not state.library_unlocked or "archive_key" not in state.inventory:
                    return rejected("需要用找回的档案钥匙进入书房并登记。", "archive_key_missing")
                state.case_closed = True
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "clues_followed": len(state.evidence),
                    "key_returned": True,
                }
                return applied("档案钥匙已登记，书房重新开放。", "archive_registered")
            if (
                self._difficulty == "medium"
                and action.target == "secret_study_door"
                and action.choice == "open"
            ):
                if not state.verdict_accepted:
                    return rejected(
                        "尚未以门禁和独立证词确认 caretaker badge。", "verdict_required"
                    )
                state.secret_study_open = True
                return applied("caretaker badge 已核实，密室书房门开启。", "secret_study_opened")
            if (
                self._difficulty == "medium"
                and action.target == "case_board"
                and action.choice == "close_case"
            ):
                if not state.verdict_accepted or "sealed_scroll" not in state.inventory:
                    return rejected("需先确认嫌疑人并把封存卷轴带回大厅。", "case_incomplete")
                state.case_closed = True
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "evidence_count": len(state.evidence),
                    "scroll_returned": True,
                }
                return applied("封存卷轴已归档，案件结案。", "case_closed")
            if (
                self._difficulty == "hard"
                and action.target == "verdict_desk"
                and action.choice == "review"
            ):
                return applied(
                    "公开已取得的证据 ID 可用于提交；物证链须同时排除 GARETH 与 ELISE。",
                    "evidence_reviewed",
                )
        if isinstance(action, UseAction) and self._difficulty == "easy":
            if action.item == "archive_key" and action.target == "library_door":
                if state.current_room != "great_hall":
                    return rejected("书房门位于大礼堂。", "door_not_present")
                if "archive_key" not in state.inventory:
                    return rejected("没有档案钥匙，无法解锁书房。", "archive_key_missing")
                state.library_unlocked = True
                return applied("档案钥匙打开了书房门。", "library_unlocked")
        if isinstance(action, SubmitAction):
            return self._submit_verdict(action)
        return rejected("该动作不适用于本关的调查规则。", "castle_action_rejected")

    @property
    def _evidence_ids(self) -> set[str]:
        if self._difficulty == "easy":
            return set()
        if self._difficulty == "medium":
            return {"access_log", "clock_report"}
        return {
            "key_ledger",
            "seal_wax",
            "door_record",
            "guard_roster",
            "medical_chart",
            "guard_manuscript",
        }

    def _dialogue(self) -> dict[tuple[str, str], tuple[str, str]]:
        if self._difficulty == "easy":
            return {
                ("gatekeeper", "where_key"): (
                    "gatekeeper_key_location",
                    "门卫证词：我把档案钥匙交还给了厨房的厨师。",
                ),
                ("cook", "where_stored"): (
                    "cook_box_location",
                    "厨师证词：我把钥匙放进储藏室的蓝色钥匙盒。",
                ),
            }
        if self._difficulty == "medium":
            return {
                ("guard", "night_patrol"): (
                    "guard_timeline",
                    "守卫证词：午夜前我在钟楼值勤，看见 caretaker 从记录室方向离开。",
                ),
                ("caretaker", "where_were_you"): (
                    "caretaker_statement",
                    "管事证词：我整晚都在庭院，没有进入记录室。",
                ),
                ("physician", "night_records"): (
                    "physician_timeline",
                    "医师证词：病历记录能证明我整晚在医务室救治病人。",
                ),
            }
        return {
            ("marius", "key_access"): (
                "marius_statement",
                "MARIUS 证词：我当晚从未领取或碰过青铜钥匙。",
            ),
            ("gareth", "where_were_you"): (
                "gareth_statement",
                "GARETH 证词：我按名册在 20:45—21:15 看守南门。",
            ),
            ("elise", "where_were_you"): (
                "elise_statement",
                "ELISE 证词：我按病历在 20:40—21:15 连续救治病人。",
            ),
        }

    def _submit_verdict(self, action: SubmitAction) -> ScenarioActionResult:
        state = self._castle()
        if self._difficulty == "easy":
            return rejected(
                "本关需要找回实体钥匙并登记，不接受嫌疑人指认。", "wrong_submission_type"
            )
        if self._difficulty == "medium":
            if action.target != "case_board":
                return rejected("提交目标不是案件案板。", "wrong_accusation_target")
            if not self._required_evidence.issubset(state.evidence):
                return rejected("门禁记录、校时信息和独立证词尚未齐全。", "evidence_incomplete")
            if action.answer.strip().upper() != "CARETAKER":
                return rejected("当前指认与已公开证据不一致。", "accusation_inconsistent")
            state.verdict_accepted = True
            return applied("门禁记录、校时报告与独立证词共同确认 caretaker。", "verdict_accepted")
        if action.target != "verdict_desk":
            return rejected("提交目标不是王室判案台。", "wrong_accusation_target")
        if not self._required_evidence.issubset(state.evidence):
            return rejected("证据链尚未齐全，无法完成唯一指认。", "evidence_incomplete")
        suspect, separator, evidence_text = action.answer.strip().upper().partition("|")
        submitted_evidence = set(evidence_text.split("+")) if separator else set()
        allowed_material = {"KEY_LEDGER", "SEAL_WAX", "DOOR_RECORD"}
        if (
            suspect != "MARIUS"
            or len(submitted_evidence) < 2
            or not submitted_evidence.issubset(allowed_material)
            or "KEY_LEDGER" not in submitted_evidence
        ):
            return rejected("证据链不足或结论与现有记录不一致。", "accusation_inconsistent")
        state.verdict_accepted = True
        state.terminal_status = ScenarioStatus.SUCCESS
        state.score_components = {
            "evidence_count": len(state.evidence),
            "submitted_materials": len(submitted_evidence),
            "independent_alibis_checked": 2,
        }
        return applied(
            "钥匙、时间與封蜡证据一致，GARETH 与 ELISE 的独立记录排除两人；MARIUS 指认成立。",
            "verdict_accepted",
        )

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._castle()
        return (
            PublicStatusFact(id="evidence_ids", value=",".join(sorted(state.evidence)) or "none"),
            PublicStatusFact(id="evidence_count", value=str(len(state.evidence))),
            PublicStatusFact(id="key_revealed", value=str(state.key_revealed).lower()),
            PublicStatusFact(id="library_unlocked", value=str(state.library_unlocked).lower()),
            PublicStatusFact(id="verdict_accepted", value=str(state.verdict_accepted).lower()),
            PublicStatusFact(id="secret_study_open", value=str(state.secret_study_open).lower()),
            PublicStatusFact(id="case_closed", value=str(state.case_closed).lower()),
        )


__all__ = ["CastleScenario"]
