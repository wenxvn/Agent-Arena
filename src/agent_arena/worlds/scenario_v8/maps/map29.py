"""MAP-29｜不可靠的证人：8 问预算下的证词分诊与物证交叉。

本图与同世界另两图的机制差异：MAP-28 的证据都可靠，难点是四字段双来源交叉；
MAP-30 是长间隔召回与多事件案卷。本图固定四名 NPC、四种不同的知识边界/偏差，
核心是**在有限问询预算里区分“记错”“故意隐瞒”“诚实但不知道”**，并只在物证或
档案交叉验证后才采信时地结论。

案情（裁判侧）：庭院 Y 的银铃在 23:40 响过一次。固定偏差：
- 甲（L）把停在 00:00 的书房钟当成事件钟，误报 00:05（记忆锚定）。
- 乙（K）知道 23:40，却每次都说地点在书房 L（故意隐瞒）。
- 丙（Y）只听到“低后高”双音，时间和地点都 `UNKNOWN`（诚实但知识受限）。
- 丁（G）保管事件簿；泛问只说“有一份铃声档案”，用 `ARCHIVE_CROSS_INDEX`
  才给出文书事实 23:40 / Y。

动作契约：
- ``move(to)``：H 为中枢，H 连接 L/K/Y/G；1 tick。
- ``ask(npc_id, question_template_id)``：必须在该 NPC 的固定位置；有效提问扣 1 预算
  和 1 tick。重复同一 NPC/模板照样扣预算，但返回完全相同的 answer ID 与文本。
  预算为 0 时返回 ``QUESTION_BUDGET_EXHAUSTED``，**不扣 tick、不扣预算**。
- ``investigate(target_id)``：``study_clock``（L）或 ``courtyard_bell_trace``（Y）；
  1 tick，不占提问预算。
- ``compare_testimony(npc_id, statement_ids, against_evidence_ids)``：只接受已听到的
  answer/source ID 与已发现的物证/档案 ID；比对结果写入公开的 comparison_results。
- ``submit(event_time, event_location, unreliable_npc_id, support_ids,
  unreliability_proof_ids)``：只能在 H，单次终局；拒绝是 truth-neutral 的
  ``CASE_REJECTED``。

失败码：``INVALID_NPC_ID``、``INVALID_QUESTION_TEMPLATE``、``INVALID_LOCATION``、
``QUESTION_BUDGET_EXHAUSTED``、``NO_ADDITIONAL_KNOWLEDGE``、
``COMPARE_INSUFFICIENT_EVIDENCE``、``EVIDENCE_NOT_OBSERVED``、
``INVALID_STATEMENT_ID``、``CASE_REJECTED``。越预算只计 ``query_budget_overruns``，
不改写任何答案。

指标口径（与 ``docs/v7/maps/MAP-29.md`` 一致）：
- ``map29.contradiction_detection_rate``：被规则证实并记录的植入矛盾数 / 2
  （甲的时间矛盾、乙的地点矛盾）；未比对 → 0，合法。
- ``map29.evidence_supported_testimony_ratio``：最终采信且被物证/档案支持的条目数 /
  采信条目数。采信条目固定为 3 项：事件时刻、事件地点、被指认的不可靠证人；没有
  提交 → ``None``（N/A）。
- ``map29.query_budget_overruns``：``QUESTION_BUDGET_EXHAUSTED`` 次数。
- ``map29.single_witness_trust``：提交时采信条目的独立**非证词**来源少于 2 个的
  次数（0–3）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action

NPCS: dict[str, dict[str, str]] = {
    "A": {"location": "L", "role": "书房侍从", "bias": "time_memory_anchored"},
    "B": {"location": "K", "role": "厨房管事", "bias": "deliberate_location_concealment"},
    "C": {"location": "Y", "role": "庭院听者", "bias": "sound_only_knowledge_limit"},
    "D": {"location": "G", "role": "档案看守", "bias": "archive_needs_cross_index"},
}

TEMPLATES = frozenset(
    {
        "OPEN_ACCOUNT",
        "TIME_BASIS",
        "LOCATION_BASIS",
        "ARCHIVE_CROSS_INDEX",
        "SOUND_PATTERN",
    }
)

#: seed0 固定答案表：同一 (npc, template) 永远返回同一 answer ID 与文本。
ANSWERS: dict[str, dict[str, dict[str, Any]]] = {
    "A": {
        "OPEN_ACCOUNT": {
            "answer_id": "A_OPEN_ACCOUNT",
            "source_ids": ["A_TIME_CLAIM_0005", "A_LOCATION_CLAIM_Y"],
            "typed_payload": {"event_time_claim": "00:05", "event_location_claim": "Y"},
            "rendered_text": "我记得铃在00:05响，声源方向像是庭院。",
        },
        "TIME_BASIS": {
            "answer_id": "A_TIME_BASIS",
            "source_ids": ["A_TIME_BASIS_STOPPED_0000"],
            "typed_payload": {"basis": "study_clock_stopped_at_00_00"},
            "rendered_text": "我看的是书房那只钟；后来才发现它停在00:00。",
        },
    },
    "B": {
        "OPEN_ACCOUNT": {
            "answer_id": "B_OPEN_ACCOUNT",
            "source_ids": ["B_LOCATION_CLAIM_L"],
            "typed_payload": {"event_time_claim": "23:40", "event_location_claim": "L"},
            "rendered_text": "那声铃大约在23:40，我记得是在书房L。",
        },
        "LOCATION_BASIS": {
            "answer_id": "B_LOCATION_BASIS",
            "source_ids": ["B_LOCATION_CLAIM_L"],
            "typed_payload": {"repeats_location_claim": "L"},
            "rendered_text": "我还是坚持说是在书房L。",
        },
    },
    "C": {
        "OPEN_ACCOUNT": {
            "answer_id": "C_SOUND_ONLY",
            "source_ids": ["C_SOUND_ONLY"],
            "typed_payload": {
                "event_time_claim": "UNKNOWN",
                "event_location_claim": "UNKNOWN",
                "sound_pattern": "DOUBLE_LOW_HIGH",
            },
            "rendered_text": "我只听见两声低高音；不知道准确时间，也不知道从哪间房传来。",
        },
        "SOUND_PATTERN": {
            "answer_id": "C_SOUND_ONLY",
            "source_ids": ["C_SOUND_ONLY"],
            "typed_payload": {"sound_pattern": "DOUBLE_LOW_HIGH"},
            "rendered_text": "听起来是低音后接高音的双响。",
        },
    },
    "D": {
        "OPEN_ACCOUNT": {
            "answer_id": "D_ARCHIVE_EXISTS",
            "source_ids": ["D_ARCHIVE_EXISTS"],
            "typed_payload": {"fact": "a_signed_bell_docket_is_kept_here"},
            "rendered_text": "守门铃事件簿保存在我这里，但要查索引才能定位那一条。",
        },
        "ARCHIVE_CROSS_INDEX": {
            "answer_id": "ARCHIVE_EVENT_2340_Y",
            "source_ids": ["ARCHIVE_EVENT_2340_Y"],
            "typed_payload": {"event_time": "23:40", "event_location": "Y"},
            "rendered_text": "交叉索引记载：23:40，庭院Y银铃撞击一次。",
        },
    },
}

DEFAULT_ANSWERS: dict[str, dict[str, Any]] = {
    "A": {
        "answer_id": "A_NO_ADDITIONAL_KNOWLEDGE",
        "source_ids": [],
        "typed_payload": {},
        "rendered_text": "我没有其他可补充的事实。",
    },
    "B": {
        "answer_id": "B_NO_ADDITIONAL_KNOWLEDGE",
        "source_ids": [],
        "typed_payload": {},
        "rendered_text": "我没有其他可补充的事实。",
    },
    "C": {
        "answer_id": "C_NO_ADDITIONAL_KNOWLEDGE",
        "source_ids": [],
        "typed_payload": {},
        "rendered_text": "我不知道更多。",
    },
    "D": {
        "answer_id": "D_NO_ADDITIONAL_KNOWLEDGE",
        "source_ids": [],
        "typed_payload": {},
        "rendered_text": "档案里没有这类索引。",
    },
}

PHYSICAL_EVIDENCE: dict[str, dict[str, str]] = {
    "STUDY_CLOCK_STOPPED_0000": {
        "location": "L",
        "source": "study_clock",
        "source_class": "physical_trace",
        "fact": "study_clock_stopped_at_00_00",
    },
    "YARD_BELL_MARK_2340": {
        "location": "Y",
        "source": "courtyard_bell_trace",
        "source_class": "physical_trace",
        "fact": "courtyard_bell_marked_single_strike_at_23_40",
    },
}

#: 独立于证词的来源：停钟物证、庭院撞针、丁的文书。
INDEPENDENT_SOURCES = frozenset(
    {"STUDY_CLOCK_STOPPED_0000", "YARD_BELL_MARK_2340", "ARCHIVE_EVENT_2340_Y"}
)
TIME_LOCATION_SOURCES = frozenset({"YARD_BELL_MARK_2340", "ARCHIVE_EVENT_2340_Y"})
TRUTH = {"event_time": "23:40", "event_location": "Y"}


class Map29Environment(MapEnvironment):
    map_id = "MAP-29"
    title = "不可靠的证人"
    world = "castle"
    level = "中等"
    EDGES = {
        "H_L": ("H", "L"),
        "H_K": ("H", "K"),
        "H_Y": ("H", "Y"),
        "H_G": ("H", "G"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "ask": {frozenset({"tool", "npc_id", "question_template_id"})},
        "investigate": {frozenset({"tool", "target_id"})},
        "compare_testimony": {
            frozenset({"tool", "npc_id", "statement_ids", "against_evidence_ids"})
        },
        "submit": {
            frozenset(
                {
                    "tool",
                    "event_time",
                    "event_location",
                    "unreliable_npc_id",
                    "support_ids",
                    "unreliability_proof_ids",
                }
            )
        },
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "local_neighbors",
            "visible_edges",
            "tick",
            "questions_remaining",
            "questions_used",
            "heard_answers",
            "physical_evidence",
            "comparison_results",
            "npc_locations",
            "goal",
        }
    )
    QUESTION_BUDGET = 8

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "H"
        self.items = []
        self.questions_used = 0
        self.questions_remaining = self.QUESTION_BUDGET
        self.heard: list[dict[str, Any]] = []
        self._asked_keys: set[str] = set()
        self.repeated_questions = 0
        self.overruns = 0
        self.evidence_ids: list[str] = []
        self.comparison_results: dict[str, str] = {}
        self.unreliable_proven: list[str] = []
        self.submitted = False
        self.judge_reason: str | None = None
        self.single_witness_count = 0
        self._adopted_total = 0
        self._adopted_supported = 0
        self._pending_cost = 1

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "local_neighbors": sorted(
                destination
                for edge_id in self.visible_edges()
                if (destination := self.edge_destination(edge_id)) is not None
            ),
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "questions_remaining": self.questions_remaining,
            "questions_used": self.questions_used,
            "heard_answers": [dict(record) for record in self.heard],
            "physical_evidence": [
                {
                    "evidence_id": evidence_id,
                    "fact": PHYSICAL_EVIDENCE[evidence_id]["fact"],
                    "source_class": PHYSICAL_EVIDENCE[evidence_id]["source_class"],
                }
                for evidence_id in self.evidence_ids
            ],
            "comparison_results": dict(self.comparison_results),
            "npc_locations": {npc: info["location"] for npc, info in NPCS.items()},
            "goal": "提交准确的事件时刻与地点，并指出至少一位经固定比对规则证明不可靠的证人。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_cost = 1
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "ask":
            return self._ask(action)
        if tool == "investigate":
            return self._investigate(action)
        if tool == "compare_testimony":
            return self._compare(action)
        if tool == "submit":
            return self._submit(action)
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        if action.to is None:
            return "INVALID_ACTION_SCHEMA"
        for edge_id in self.visible_edges():
            if self.edge_destination(edge_id) == action.to:
                self.node = action.to
                return "MOVE_SUCCEEDED"
        return "EDGE_NOT_ADJACENT"

    def _ask(self, action: V8Action) -> str:
        npc_id = action.npc_id
        template = action.question_template_id
        if npc_id not in NPCS:
            self._pending_cost = 0
            return "INVALID_NPC_ID"
        if template not in TEMPLATES:
            self._pending_cost = 0
            return "INVALID_QUESTION_TEMPLATE"
        if self.node != NPCS[npc_id]["location"]:
            return "INVALID_LOCATION"
        if self.questions_remaining <= 0:
            self._pending_cost = 0
            self.overruns += 1
            return "QUESTION_BUDGET_EXHAUSTED"
        self.questions_remaining -= 1
        self.questions_used += 1
        key = f"{npc_id}:{template}"
        if key in self._asked_keys:
            self.repeated_questions += 1
        else:
            self._asked_keys.add(key)
            spec = ANSWERS[npc_id].get(template)
            if spec is None:
                spec = DEFAULT_ANSWERS[npc_id]
            self.heard.append(
                {
                    "answer_id": spec["answer_id"],
                    "npc_id": npc_id,
                    "question_template_id": template,
                    "rendered_text": spec["rendered_text"],
                    "source_ids": list(spec["source_ids"]),
                    "typed_payload": dict(spec["typed_payload"]),
                }
            )
        spec = ANSWERS[npc_id].get(template)
        if spec is None:
            return "NO_ADDITIONAL_KNOWLEDGE"
        return f"ANSWER_RECEIVED:{spec['answer_id']}"

    def _investigate(self, action: V8Action) -> str:
        for evidence_id, evidence in PHYSICAL_EVIDENCE.items():
            if evidence["source"] != action.target_id:
                continue
            if self.node != evidence["location"]:
                return "TARGET_NOT_VISIBLE"
            if evidence_id not in self.evidence_ids:
                self.evidence_ids.append(evidence_id)
            return f"EVIDENCE_FOUND:{evidence_id}"
        return "TARGET_NOT_VISIBLE"

    def _known_ids(self) -> set[str]:
        known = set(self.evidence_ids)
        for record in self.heard:
            known.add(record["answer_id"])
            known.update(record["source_ids"])
        return known

    def _compare(self, action: V8Action) -> str:
        npc_id = action.npc_id
        if npc_id not in NPCS:
            self._pending_cost = 0
            return "INVALID_NPC_ID"
        statements = [str(item) for item in (action.statement_ids or [])]
        evidence = [str(item) for item in (action.against_evidence_ids or [])]
        known = self._known_ids()
        if any(item not in known for item in statements):
            return "INVALID_STATEMENT_ID"
        if any(item not in known for item in evidence):
            return "EVIDENCE_NOT_OBSERVED"
        statements_set = set(statements)
        evidence_set = set(evidence)

        if npc_id == "A":
            complete = (
                (
                    "A_TIME_CLAIM_0005" in statements_set
                    or "A_OPEN_ACCOUNT" in statements_set
                )
                and "A_TIME_BASIS_STOPPED_0000" in statements_set
                and "STUDY_CLOCK_STOPPED_0000" in evidence_set
                and "ARCHIVE_EVENT_2340_Y" in evidence_set
            )
            result = (
                "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED"
                if complete
                else "COMPARE_INSUFFICIENT_EVIDENCE"
            )
            if complete and "A" not in self.unreliable_proven:
                self.unreliable_proven.append("A")
        elif npc_id == "B":
            complete = (
                (
                    "B_LOCATION_CLAIM_L" in statements_set
                    or "B_OPEN_ACCOUNT" in statements_set
                )
                and "ARCHIVE_EVENT_2340_Y" in evidence_set
                and "YARD_BELL_MARK_2340" in evidence_set
            )
            result = (
                "LOCATION_CLAIM_CONTRADICTED_AND_EXPLAINED"
                if complete
                else "COMPARE_INSUFFICIENT_EVIDENCE"
            )
            if complete and "B" not in self.unreliable_proven:
                self.unreliable_proven.append("B")
        elif npc_id == "C":
            result = (
                "TESTIMONY_CONSISTENT"
                if statements_set
                else "COMPARE_INSUFFICIENT_EVIDENCE"
            )
        else:
            result = (
                "TESTIMONY_CONSISTENT"
                if statements_set
                else "COMPARE_INSUFFICIENT_EVIDENCE"
            )
        self.comparison_results[npc_id] = result
        return result

    # ------------------------------------------------------------------ submit
    def _submit(self, action: V8Action) -> str:
        if self.node != "H":
            return "INVALID_LOCATION"
        known = self._known_ids()
        support = [str(item) for item in (action.support_ids or [])]
        proof = [str(item) for item in (action.unreliability_proof_ids or [])]
        unknown = [item for item in support + proof if item not in known]
        npc_id = action.unreliable_npc_id
        time_ok = action.event_time == TRUTH["event_time"]
        location_ok = action.event_location == TRUTH["event_location"]
        npc_ok = npc_id in self.unreliable_proven

        support_set = set(support)
        proof_set = set(proof)
        time_supported = time_ok and bool(support_set & TIME_LOCATION_SOURCES)
        location_supported = location_ok and bool(support_set & TIME_LOCATION_SOURCES)
        if npc_id == "A":
            required = {"STUDY_CLOCK_STOPPED_0000", "ARCHIVE_EVENT_2340_Y"}
            npc_supported = npc_ok and required <= proof_set
        elif npc_id == "B":
            required = {"YARD_BELL_MARK_2340", "ARCHIVE_EVENT_2340_Y"}
            npc_supported = npc_ok and required <= proof_set
        else:
            npc_supported = False
        self._adopted_total = 3
        self._adopted_supported = sum(
            (time_supported, location_supported, npc_supported)
        )
        self.single_witness_count = 0
        for shown in (support_set, support_set, proof_set):
            if len(shown & INDEPENDENT_SOURCES) < 2:
                self.single_witness_count += 1
        self.submitted = True

        if unknown:
            self.judge_reason = "UNKNOWN_REFERENCE"
            self._fail("CASE_REJECTED")
            return "CASE_REJECTED"
        if not time_ok:
            self.judge_reason = "WRONG_EVENT_TIME"
            self._fail("CASE_REJECTED")
            return "CASE_REJECTED"
        if not location_ok:
            self.judge_reason = "WRONG_EVENT_LOCATION"
            self._fail("CASE_REJECTED")
            return "CASE_REJECTED"
        if not npc_ok:
            self.judge_reason = "NO_PROVEN_UNRELIABLE_WITNESS"
            self._fail("CASE_REJECTED")
            return "CASE_REJECTED"
        self.judge_reason = "ALL_OBJECTIVES_COMPLETE"
        self._succeed("ALL_OBJECTIVES_COMPLETE")
        return "ALL_OBJECTIVES_COMPLETE"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._pending_cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "questions_used": self.questions_used,
            "questions_remaining": self.questions_remaining,
            "repeated_questions": self.repeated_questions,
            "unique_answers": len({record["answer_id"] for record in self.heard}),
            "overruns": self.overruns,
            "heard_answer_ids": [record["answer_id"] for record in self.heard],
            "physical_evidence_ids": list(self.evidence_ids),
            "comparison_results": dict(self.comparison_results),
            "unreliable_proven": list(self.unreliable_proven),
            "submitted": self.submitted,
            "judge_reason": self.judge_reason,
            "single_witness_count": self.single_witness_count,
            "truth": dict(TRUTH),
        }

    def metrics(self) -> dict[str, Any]:
        detected = sum(1 for npc in self.unreliable_proven if npc in ("A", "B"))
        ratio: dict[str, int] | None = None
        if self.submitted:
            ratio = {
                "numerator": self._adopted_supported,
                "denominator": self._adopted_total,
            }
        return {
            "map29.contradiction_detection_rate": {
                "numerator": detected,
                "denominator": 2,
            },
            "map29.evidence_supported_testimony_ratio": ratio,
            "map29.query_budget_overruns": self.overruns,
            "map29.single_witness_trust": self.single_witness_count,
        }


#: 论文手写路线 B：高信息问题优先（13 tick / 3 问）。
_HIGH_INFO_FIRST = [
    {"tool": "move", "to": "G"},
    {"tool": "ask", "npc_id": "D", "question_template_id": "ARCHIVE_CROSS_INDEX"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "L"},
    {"tool": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"},
    {"tool": "ask", "npc_id": "A", "question_template_id": "TIME_BASIS"},
    {"tool": "investigate", "target_id": "study_clock"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "Y"},
    {"tool": "investigate", "target_id": "courtyard_bell_trace"},
    {
        "tool": "compare_testimony",
        "npc_id": "A",
        "statement_ids": ["A_TIME_CLAIM_0005", "A_TIME_BASIS_STOPPED_0000"],
        "against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000", "ARCHIVE_EVENT_2340_Y"],
    },
    {"tool": "move", "to": "H"},
    {
        "tool": "submit",
        "event_time": "23:40",
        "event_location": "Y",
        "unreliable_npc_id": "A",
        "support_ids": ["ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"],
        "unreliability_proof_ids": [
            "A_TIME_CLAIM_0005",
            "A_TIME_BASIS_STOPPED_0000",
            "STUDY_CLOCK_STOPPED_0000",
            "ARCHIVE_EVENT_2340_Y",
        ],
    },
]

#: 论文手写路线 A：广泛询问再收敛（7 问，先证词后核验）。
_BROAD_THEN_NARROW = [
    {"tool": "move", "to": "L"},
    {"tool": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "K"},
    {"tool": "ask", "npc_id": "B", "question_template_id": "OPEN_ACCOUNT"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "Y"},
    {"tool": "ask", "npc_id": "C", "question_template_id": "OPEN_ACCOUNT"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "G"},
    {"tool": "ask", "npc_id": "D", "question_template_id": "OPEN_ACCOUNT"},
    {"tool": "ask", "npc_id": "D", "question_template_id": "ARCHIVE_CROSS_INDEX"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "L"},
    {"tool": "ask", "npc_id": "A", "question_template_id": "TIME_BASIS"},
    {"tool": "investigate", "target_id": "study_clock"},
    {"tool": "move", "to": "H"},
    {"tool": "move", "to": "Y"},
    {"tool": "ask", "npc_id": "C", "question_template_id": "SOUND_PATTERN"},
    {"tool": "investigate", "target_id": "courtyard_bell_trace"},
    {
        "tool": "compare_testimony",
        "npc_id": "A",
        "statement_ids": ["A_TIME_CLAIM_0005", "A_TIME_BASIS_STOPPED_0000"],
        "against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000", "ARCHIVE_EVENT_2340_Y"],
    },
    {"tool": "move", "to": "H"},
    {
        "tool": "submit",
        "event_time": "23:40",
        "event_location": "Y",
        "unreliable_npc_id": "A",
        "support_ids": ["ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"],
        "unreliability_proof_ids": [
            "A_TIME_CLAIM_0005",
            "A_TIME_BASIS_STOPPED_0000",
            "STUDY_CLOCK_STOPPED_0000",
            "ARCHIVE_EVENT_2340_Y",
        ],
    },
]

ORACLE_CASES = (
    {
        "trace_id": "high_information_first",
        "seed": 0,
        "actions": _HIGH_INFO_FIRST,
        "expect_success": True,
    },
    {
        "trace_id": "broad_then_narrow",
        "seed": 0,
        "actions": _BROAD_THEN_NARROW,
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "broad_route_success_seven_questions",
        "seed": 0,
        "actions": _BROAD_THEN_NARROW,
        # 手算：7 问（4 次开放叙述 + 丁索引 + 甲依据 + 丙音型）；只比对出甲的时间
        # 矛盾 → 1/2；时刻/地点各由档案+撞针支持，甲由停钟+档案证明 → 3/3；0 超支。
        "expect": {
            "map29.contradiction_detection_rate": 0.5,
            "map29.evidence_supported_testimony_ratio": 1.0,
            "map29.query_budget_overruns": 0,
            "map29.single_witness_trust": 0,
        },
    },
    {
        "name": "proven_location_lie_still_submitted",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "G"},
            {"tool": "ask", "npc_id": "D", "question_template_id": "ARCHIVE_CROSS_INDEX"},
            {"tool": "move", "to": "H"},
            {"tool": "move", "to": "K"},
            {"tool": "ask", "npc_id": "B", "question_template_id": "OPEN_ACCOUNT"},
            {"tool": "move", "to": "H"},
            {"tool": "move", "to": "Y"},
            {"tool": "investigate", "target_id": "courtyard_bell_trace"},
            {
                "tool": "compare_testimony",
                "npc_id": "B",
                "statement_ids": ["B_LOCATION_CLAIM_L"],
                "against_evidence_ids": [
                    "ARCHIVE_EVENT_2340_Y",
                    "YARD_BELL_MARK_2340",
                ],
            },
            {"tool": "move", "to": "H"},
            {
                "tool": "submit",
                "event_time": "23:40",
                "event_location": "L",
                "unreliable_npc_id": "B",
                "support_ids": ["ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"],
                "unreliability_proof_ids": [
                    "B_LOCATION_CLAIM_L",
                    "ARCHIVE_EVENT_2340_Y",
                    "YARD_BELL_MARK_2340",
                ],
            },
        ],
        # 手算：乙已被撞针+档案证明隐瞒地点 → 1/2；但提交地点 L 与两份独立来源
        # 冲突 → 时刻支持、地点不支持、乙的支持成立 → 2/3；三项采信各有 2 个
        # 独立来源 → 单证人采信 0。
        "expect": {
            "map29.contradiction_detection_rate": 0.5,
            "map29.evidence_supported_testimony_ratio": 0.666667,
            "map29.query_budget_overruns": 0,
            "map29.single_witness_trust": 0,
        },
    },
    {
        "name": "ninth_question_is_refused_free",
        "seed": 0,
        "actions": [{"tool": "move", "to": "L"}]
        + [
            {"tool": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"}
            for _ in range(9)
        ],
        # 手算：第 1–8 问各扣 1 预算与 1 tick；第 9 问 QUESTION_BUDGET_EXHAUSTED
        # 不扣 tick/预算 → 超支 1 次；重复问不产生新证据；未比对、未提交 →
        # 检测率 0.0、采信比为 N/A、单证人 0。
        "expect": {
            "map29.contradiction_detection_rate": 0.0,
            "map29.evidence_supported_testimony_ratio": None,
            "map29.query_budget_overruns": 1,
            "map29.single_witness_trust": 0,
        },
    },
)


__all__ = ["FIXTURES", "Map29Environment", "ORACLE_CASES"]
