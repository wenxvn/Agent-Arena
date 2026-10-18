"""MAP-29 V10｜不可靠的证人：多样本案卷、公开比较语义与部分真实分诊（DCR-V10-06）。

与 V8 的差异：

- 4 个预登记案卷种子，**真值时刻/地点、NPC 角色分配与证据依赖图都不同**；
  seed 2 换入一名“部分真实”证人（地点对、时刻错），seed 3 的档案索引要求先听到
  声型才能解析（跨阶段依赖），不再是固定的单条短路；
- 公开 `compare_testimony` 的合法语句/证据集合与返回码：`INSUFFICIENT`（证据不够）、
  `CONTRADICTED_AND_EXPLAINED`（可证伪且有解释）、`TESTIMONY_PARTIALLY_SUPPORTED`
  （部分真实）、`TESTIMONY_CONSISTENT`（无关但可信）；不公开任何证人真值；
- `submit` 成功要求：时刻与地点都对、被指认 NPC 已被固定比对规则证明不可靠、
  引用覆盖对应独立来源；
- 新增分诊质量指标 `partial_truth_classified`：把“部分真实”识破为部分支持，
  而不是笼统采信或笼统否定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    ratio,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

ROOMS = ("H", "L", "K", "Y", "G")
TEMPLATES = (
    "OPEN_ACCOUNT",
    "TIME_BASIS",
    "LOCATION_BASIS",
    "ARCHIVE_CROSS_INDEX",
    "SOUND_PATTERN",
)
#: **公开**的 NPC 职业标签（只说明职业，不说明知识边界或偏差）。
NPC_LABEL = {
    "A": "书房侍从",
    "B": "厨房管事",
    "C": "庭院听者",
    "D": "档案看守",
}
#: **隐藏**的角色语义，只用于密封真值与离线复盘，不进入 Observation。
ROLE_DESCRIPTION = {
    "time_anchored": "把停摆钟当事件钟的时间锚定证人",
    "location_concealer": "故意隐瞒地点的证人",
    "sound_only": "只听到声音、时刻地点都不知道的证人",
    "archive_keeper": "保管事件簿、需要索引才给文书的证人",
    "partial": "地点正确但时刻记错的部分真实证人",
}


@dataclass(frozen=True)
class Scenario29:
    label: str
    truth_time: str
    truth_location: str
    clock_time: str
    bell_time: str
    sound_pattern: str
    archive_doc: str
    rooms: dict[str, str]
    roles: dict[str, str]
    archive_prereq: str | None = None
    partial_wrong_time: str | None = None

    @property
    def clock_evidence(self) -> str:
        return f"STUDY_CLOCK_STOPPED_{self.clock_time.replace(':', '')}"

    @property
    def bell_evidence(self) -> str:
        return f"BELL_MARK_{self.truth_location}_{self.bell_time.replace(':', '')}"

    @property
    def archive_evidence(self) -> str:
        return f"ARCHIVE_EVENT_{self.bell_time.replace(':', '')}_{self.truth_location}"

    @property
    def planted(self) -> tuple[str, ...]:
        return tuple(
            npc
            for npc, role in sorted(self.roles.items())
            if role in ("time_anchored", "location_concealer")
        )

    @property
    def partial_npc(self) -> str | None:
        for npc, role in sorted(self.roles.items()):
            if role == "partial":
                return npc
        return None

    def npc_at(self, role: str) -> str:
        for npc, item in sorted(self.roles.items()):
            if item == role:
                return npc
        raise KeyError(role)

    @property
    def time_location_sources(self) -> frozenset[str]:
        return frozenset({self.bell_evidence, self.archive_evidence})

    @property
    def independent_sources(self) -> frozenset[str]:
        return frozenset({self.clock_evidence, self.bell_evidence, self.archive_evidence})


SCENARIOS: dict[int, Scenario29] = {
    0: Scenario29(
        label="courtyard_bell_two_contradictions",
        truth_time="23:40",
        truth_location="Y",
        clock_time="00:05",
        bell_time="23:40",
        sound_pattern="DOUBLE_LOW_HIGH",
        archive_doc="Q4",
        rooms={"A": "L", "B": "K", "C": "Y", "D": "G"},
        roles={
            "A": "time_anchored",
            "B": "location_concealer",
            "C": "sound_only",
            "D": "archive_keeper",
        },
    ),
    1: Scenario29(
        label="kitchen_bell_location_secret",
        truth_time="22:15",
        truth_location="K",
        clock_time="00:05",
        bell_time="22:15",
        sound_pattern="TRIPLE_LOW",
        archive_doc="Q7",
        rooms={"A": "L", "B": "K", "C": "Y", "D": "G"},
        roles={
            "A": "location_concealer",
            "B": "time_anchored",
            "C": "sound_only",
            "D": "archive_keeper",
        },
    ),
    2: Scenario29(
        label="partial_truth_witness",
        truth_time="21:05",
        truth_location="K",
        clock_time="00:05",
        bell_time="21:05",
        sound_pattern="DOUBLE_HIGH_LOW",
        archive_doc="Q2",
        rooms={"A": "L", "B": "K", "C": "Y", "D": "G"},
        roles={
            "A": "location_concealer",
            "B": "time_anchored",
            "C": "partial",
            "D": "archive_keeper",
        },
        partial_wrong_time="21:20",
    ),
    3: Scenario29(
        label="archive_needs_sound_match",
        truth_time="23:40",
        truth_location="Y",
        clock_time="01:30",
        bell_time="23:40",
        sound_pattern="DOUBLE_LOW_HIGH",
        archive_doc="Q9",
        rooms={"A": "L", "B": "K", "C": "Y", "D": "G"},
        roles={
            "A": "sound_only",
            "B": "time_anchored",
            "C": "location_concealer",
            "D": "archive_keeper",
        },
        archive_prereq="SOUND_PATTERN",
    ),
}


@dataclass
class Answer:
    answer_id: str
    source_ids: list[str] = field(default_factory=list)
    typed_payload: dict[str, Any] = field(default_factory=dict)
    rendered_text: str = ""


def _compact(value: str) -> str:
    return value.replace(":", "")


def build_scenario(scenario: Scenario29) -> tuple[dict[str, dict[str, Answer]], dict[str, Answer]]:
    """按角色生成每个 NPC 的答案表（确定性、无随机）。"""

    answers: dict[str, dict[str, Answer]] = {}
    defaults: dict[str, Answer] = {}
    for npc, role in sorted(scenario.roles.items()):
        table: dict[str, Answer] = {}
        if role == "time_anchored":
            clock = _compact(scenario.clock_time)
            table["OPEN_ACCOUNT"] = Answer(
                f"{npc}_TIME_CLAIM_{clock}",
                [f"{npc}_TIME_CLAIM_{clock}"],
                {
                    "event_time_claim": scenario.clock_time,
                    "event_location_claim": scenario.truth_location,
                },
                f"我记得铃在{scenario.clock_time}响，声源方向像是{scenario.truth_location}。",
            )
            table["TIME_BASIS"] = Answer(
                f"{npc}_TIME_BASIS_STOPPED_{clock}",
                [f"{npc}_TIME_BASIS_STOPPED_{clock}"],
                {"basis": f"study_clock_stopped_at_{clock}"},
                f"我看的是书房那只钟；后来才发现它停在{scenario.clock_time}。",
            )
            defaults[npc] = Answer(
                f"{npc}_NO_ADDITIONAL_KNOWLEDGE", [], {}, "我没有其他可补充的事实。"
            )
        elif role == "location_concealer":
            table["OPEN_ACCOUNT"] = Answer(
                f"{npc}_LOCATION_CLAIM_L",
                [f"{npc}_LOCATION_CLAIM_L"],
                {
                    "event_time_claim": scenario.truth_time,
                    "event_location_claim": "L",
                },
                f"那声铃大约在{scenario.truth_time}，我记得是在书房L。",
            )
            table["LOCATION_BASIS"] = Answer(
                f"{npc}_LOCATION_BASIS_L",
                [f"{npc}_LOCATION_CLAIM_L"],
                {"repeats_location_claim": "L"},
                "我还是坚持说是在书房L。",
            )
            defaults[npc] = Answer(
                f"{npc}_NO_ADDITIONAL_KNOWLEDGE", [], {}, "我没有其他可补充的事实。"
            )
        elif role == "sound_only":
            table["OPEN_ACCOUNT"] = Answer(
                f"{npc}_SOUND_ONLY",
                [f"{npc}_SOUND_ONLY"],
                {
                    "event_time_claim": "UNKNOWN",
                    "event_location_claim": "UNKNOWN",
                    "sound_pattern": scenario.sound_pattern,
                },
                "我只听见声音；不知道准确时间，也不知道从哪间房传来。",
            )
            table["SOUND_PATTERN"] = Answer(
                f"{npc}_SOUND_ONLY",
                [f"{npc}_SOUND_ONLY"],
                {"sound_pattern": scenario.sound_pattern},
                f"听起来是{scenario.sound_pattern}。",
            )
            defaults[npc] = Answer(f"{npc}_NO_ADDITIONAL_KNOWLEDGE", [], {}, "我不知道更多。")
        elif role == "archive_keeper":
            table["OPEN_ACCOUNT"] = Answer(
                f"{npc}_ARCHIVE_EXISTS",
                [f"{npc}_ARCHIVE_EXISTS"],
                {"fact": "a_signed_bell_docket_is_kept_here"},
                "守门铃事件簿保存在我这里，但要查索引才能定位那一条。",
            )
            table["ARCHIVE_CROSS_INDEX"] = Answer(
                scenario.archive_evidence,
                [scenario.archive_evidence],
                {
                    "document_id": scenario.archive_doc,
                    "event_time": scenario.truth_time,
                    "event_location": scenario.truth_location,
                },
                f"交叉索引记载：{scenario.truth_time}，{scenario.truth_location}银铃撞击一次。",
            )
            defaults[npc] = Answer(
                f"{npc}_NO_ADDITIONAL_KNOWLEDGE", [], {}, "档案里没有这类索引。"
            )
        else:  # partial
            table["OPEN_ACCOUNT"] = Answer(
                f"{npc}_PARTIAL_CLAIM",
                [f"{npc}_PARTIAL_CLAIM"],
                {
                    "event_time_claim": scenario.partial_wrong_time,
                    "event_location_claim": scenario.truth_location,
                },
                f"我确定声音是从{scenario.truth_location}方向来的，看钟像是{scenario.partial_wrong_time}。",
            )
            defaults[npc] = Answer(f"{npc}_NO_ADDITIONAL_KNOWLEDGE", [], {}, "我只记得这些。")
        answers[npc] = table
    return answers, defaults


class Map29V10Environment(V10Map):
    map_id = "MAP-29"
    title = "不可靠的证人"
    world = "castle"
    level = "中等"
    RULE_VERSION = "v10.map29.1"
    SEED_SPACE = tuple(sorted(SCENARIOS))
    EDGES = {
        "H_L": ("H", "L"),
        "H_K": ("H", "K"),
        "H_Y": ("H", "Y"),
        "H_G": ("H", "G"),
    }
    QUESTION_BUDGET = 12
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
            "scenario_label",
            "npc_labels",
            "npc_locations",
            "questions_remaining",
            "questions_used",
            "heard_answers",
            "physical_evidence",
            "comparison_results",
            "goal",
        }
    )
    PRIMARY_METRIC = "map29.v10.contradiction_detection_rate"
    METRIC_SPECS = (
        MetricSpec(
            "map29.v10.contradiction_detection_rate",
            "primary",
            "higher",
            "被固定比对规则证明并记录的植入矛盾数 / 该案卷植入矛盾数",
            "该案卷植入矛盾数（2）",
        ),
        MetricSpec(
            "map29.v10.evidence_supported_testimony_ratio",
            "primary",
            "higher",
            "最终采信的三项（时刻/地点/被指认证人）中被独立来源支持的条目数 / 3",
            "已提交的局（1）",
            zero_denominator="未提交 → NOT_APPLICABLE（截尾 → CENSORED）",
        ),
        MetricSpec(
            "map29.v10.partial_truth_classified",
            "secondary",
            "higher",
            "部分真实证人被判为 TESTIMONY_PARTIALLY_SUPPORTED",
            "该案卷存在部分真实证人（1）",
            zero_denominator="案卷无部分真实证人 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map29.v10.query_budget_overruns",
            "guardrail",
            "lower",
            "QUESTION_BUDGET_EXHAUSTED 次数",
            "—",
            unit="count",
            valid_range=(0.0, 30.0),
        ),
        MetricSpec(
            "map29.v10.single_witness_trust",
            "guardrail",
            "lower",
            "采信条目中独立非证词来源 <2 的条目数",
            "—",
            unit="count",
            valid_range=(0.0, 3.0),
        ),
        MetricSpec(
            "map29.v10.questions_used",
            "diagnostic",
            "lower",
            "消耗的提问预算",
            "—",
            unit="count",
            valid_range=(0.0, 8.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.scenario = SCENARIOS[seed]
        self.answers, self.defaults = build_scenario(self.scenario)
        self.node = "H"
        self.items = []
        self.questions_used = 0
        self.questions_remaining = self.QUESTION_BUDGET
        self.heard: list[dict[str, Any]] = []
        self._asked_keys: set[str] = set()
        self._topics_heard: set[str] = set()
        self.repeated_questions = 0
        self.overruns = 0
        self.evidence_ids: list[str] = []
        self.comparison_results: dict[str, str] = {}
        self.unreliable_proven: list[str] = []
        self.submitted = False
        self.judge_reason: str | None = None
        self.single_witness_count = 0
        self._adopted_supported = 0
        self._pending_cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "scenario_label": self.scenario.label,
            "npc_locations": dict(self.scenario.rooms),
            "planted_contradictions": len(self.scenario.planted),
            "has_partial_witness": self.scenario.partial_npc is not None,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.scenario.label,
            "event_time": self.scenario.truth_time,
            "event_location": self.scenario.truth_location,
            "planted": list(self.scenario.planted),
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "H 是中枢，直连 L/K/Y/G；move(to) 沿公共边移动，1 tick。",
            "ask(npc_id, question_template_id) 必须在该 NPC 所在房间；有效提问扣 1 预算与 1 tick。"
            f"预算 {self.QUESTION_BUDGET}；预算耗尽返回 QUESTION_BUDGET_EXHAUSTED，不扣 tick。",
            "investigate(target_id) 取物证（study_clock / bell_trace），1 tick，不占提问预算。",
            "compare_testimony(npc_id, statement_ids, against_evidence_ids)：两个列表都只能引用"
            "已听到的 answer/source ID 与已发现的物证。返回 INSUFFICIENT（证据不够）、"
            "CONTRADICTED_AND_EXPLAINED（可证伪且给出解释）、TESTIMONY_PARTIALLY_SUPPORTED"
            "（部分真实）、TESTIMONY_CONSISTENT（无关但可信）。",
            "submit 只能在 H，一次终局：提交时刻、地点、被指认的不可靠 NPC，以及支持证据与"
            "“不可靠证明”引用；被指认者必须已被比对规则证明。",
            "模板：OPEN_ACCOUNT / TIME_BASIS / LOCATION_BASIS / ARCHIVE_CROSS_INDEX / "
            "SOUND_PATTERN。不同 NPC 只掌握其中一部分；证人可能记错、隐瞒或诚实但不知道。",
        )

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
            "scenario_label": self.scenario.label,
            "npc_labels": dict(NPC_LABEL),
            "npc_locations": dict(self.scenario.rooms),
            "questions_remaining": self.questions_remaining,
            "questions_used": self.questions_used,
            "heard_answers": [dict(record) for record in self.heard],
            "physical_evidence": [
                {
                    "evidence_id": evidence_id,
                    "fact": self._evidence_fact(evidence_id),
                    "source_class": "physical_trace",
                }
                for evidence_id in self.evidence_ids
            ],
            "comparison_results": dict(self.comparison_results),
            "goal": "提交准确的事件时刻与地点，并指出至少一位经固定比对规则证明不可靠的证人。",
        }

    def _evidence_fact(self, evidence_id: str) -> str:
        if evidence_id == self.scenario.clock_evidence:
            return f"书房钟停在{self.scenario.clock_time}"
        if evidence_id == self.scenario.bell_evidence:
            return f"铃痕标记：{self.scenario.bell_time} 在 {self.scenario.truth_location} 撞击一次"
        return evidence_id

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
        if npc_id not in self.scenario.roles:
            self._pending_cost = 0
            return "INVALID_NPC_ID"
        if template not in TEMPLATES:
            self._pending_cost = 0
            return "INVALID_QUESTION_TEMPLATE"
        if self.node != self.scenario.rooms[npc_id]:
            return "INVALID_LOCATION"
        if self.questions_remaining <= 0:
            self._pending_cost = 0
            self.overruns += 1
            return "QUESTION_BUDGET_EXHAUSTED"
        self.questions_remaining -= 1
        self.questions_used += 1
        known_spec = self.answers[npc_id].get(template)
        if (
            known_spec is not None
            and template == "ARCHIVE_CROSS_INDEX"
            and self.scenario.archive_prereq is not None
            and self.scenario.archive_prereq not in self._topics_heard
        ):
            return "ARCHIVE_NEEDS_PREREQ"
        key = f"{npc_id}:{template}"
        if key in self._asked_keys:
            self.repeated_questions += 1
        else:
            self._asked_keys.add(key)
            spec = self.answers[npc_id].get(template)
            if spec is None:
                spec = self.defaults[npc_id]
                self.heard.append(
                    {
                        "answer_id": spec.answer_id,
                        "npc_id": npc_id,
                        "question_template_id": template,
                        "rendered_text": spec.rendered_text,
                        "source_ids": list(spec.source_ids),
                        "typed_payload": dict(spec.typed_payload),
                    }
                )
                return "NO_ADDITIONAL_KNOWLEDGE"
            self._topics_heard.add(template)
            self.heard.append(
                {
                    "answer_id": spec.answer_id,
                    "npc_id": npc_id,
                    "question_template_id": template,
                    "rendered_text": spec.rendered_text,
                    "source_ids": list(spec.source_ids),
                    "typed_payload": dict(spec.typed_payload),
                }
            )
        spec = self.answers[npc_id].get(template)
        if spec is None:
            return "NO_ADDITIONAL_KNOWLEDGE"
        return f"ANSWER_RECEIVED:{spec.answer_id}"

    def _investigate(self, action: V8Action) -> str:
        if action.target_id == "study_clock" and self.node == "L":
            if self.scenario.clock_evidence not in self.evidence_ids:
                self.evidence_ids.append(self.scenario.clock_evidence)
            return f"EVIDENCE_FOUND:{self.scenario.clock_evidence}"
        if action.target_id == "bell_trace" and self.node == self.scenario.truth_location:
            if self.scenario.bell_evidence not in self.evidence_ids:
                self.evidence_ids.append(self.scenario.bell_evidence)
            return f"EVIDENCE_FOUND:{self.scenario.bell_evidence}"
        return "TARGET_NOT_VISIBLE"

    def _known_ids(self) -> set[str]:
        known = set(self.evidence_ids)
        for record in self.heard:
            known.add(record["answer_id"])
            known.update(record["source_ids"])
        return known

    def _claim_statement_ids(self, npc_id: str) -> set[str]:
        """该 NPC 的“主张语句”ID（引用它的回答 ID 或 source ID 都可）。"""

        ids: set[str] = set()
        role = self.scenario.roles[npc_id]
        for record in self.heard:
            if record["npc_id"] != npc_id:
                continue
            if role == "time_anchored" and record["question_template_id"] == "TIME_BASIS":
                continue
            if role == "location_concealer" and record["question_template_id"] == "LOCATION_BASIS":
                continue
            ids.add(record["answer_id"])
            ids.update(record["source_ids"])
        if role == "location_concealer":
            ids.discard(f"{npc_id}_LOCATION_BASIS_L")
        return ids

    def _compare(self, action: V8Action) -> str:
        npc_id = action.npc_id
        if npc_id not in self.scenario.roles:
            self._pending_cost = 0
            return "INVALID_NPC_ID"
        statements = {str(item) for item in (action.statement_ids or [])}
        evidence = {str(item) for item in (action.against_evidence_ids or [])}
        known = self._known_ids()
        if any(item not in known for item in statements | evidence):
            return "EVIDENCE_NOT_OBSERVED"
        role = self.scenario.roles[npc_id]
        sc = self.scenario

        if role == "time_anchored":
            complete = (
                bool(statements & self._claim_statement_ids(npc_id))
                and f"{npc_id}_TIME_BASIS_STOPPED_{_compact(sc.clock_time)}" in statements
                and sc.clock_evidence in evidence
                and sc.archive_evidence in evidence
            )
            if complete:
                self._mark(npc_id, "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED")
            else:
                self.comparison_results[npc_id] = "INSUFFICIENT"
            return self.comparison_results[npc_id]
        if role == "location_concealer":
            complete = (
                bool(statements & self._claim_statement_ids(npc_id))
                and sc.bell_evidence in evidence
                and sc.archive_evidence in evidence
            )
            if complete:
                self._mark(npc_id, "LOCATION_CLAIM_CONTRADICTED_AND_EXPLAINED")
            else:
                self.comparison_results[npc_id] = "INSUFFICIENT"
            return self.comparison_results[npc_id]
        if role == "partial":
            if sc.archive_evidence not in evidence:
                self.comparison_results[npc_id] = "INSUFFICIENT"
                return "INSUFFICIENT"
            time_ok = sc.partial_wrong_time == sc.truth_time
            location_ok = True
            if time_ok and location_ok:
                self.comparison_results[npc_id] = "TESTIMONY_CONSISTENT"
            elif time_ok or location_ok:
                self.comparison_results[npc_id] = "TESTIMONY_PARTIALLY_SUPPORTED"
            else:
                self.comparison_results[npc_id] = "TESTIMONY_CONTRADICTED"
            return self.comparison_results[npc_id]
        self.comparison_results[npc_id] = (
            "TESTIMONY_CONSISTENT" if statements else "INSUFFICIENT"
        )
        return self.comparison_results[npc_id]

    def _mark(self, npc_id: str, code: str) -> None:
        self.comparison_results[npc_id] = code
        if npc_id not in self.unreliable_proven:
            self.unreliable_proven.append(npc_id)

    # ------------------------------------------------------------------ submit
    def _submit(self, action: V8Action) -> str:
        if self.node != "H":
            return "INVALID_LOCATION"
        sc = self.scenario
        known = self._known_ids()
        support = {str(item) for item in (action.support_ids or [])}
        proof = {str(item) for item in (action.unreliability_proof_ids or [])}
        unknown = [item for item in support | proof if item not in known]
        npc_id = action.unreliable_npc_id
        time_ok = action.event_time == sc.truth_time
        location_ok = action.event_location == sc.truth_location
        npc_ok = npc_id in self.unreliable_proven

        time_supported = time_ok and bool(support & sc.time_location_sources)
        location_supported = location_ok and bool(support & sc.time_location_sources)
        npc_supported = False
        if npc_id in sc.roles and npc_ok:
            role = sc.roles[npc_id]
            if role == "time_anchored":
                required = {sc.clock_evidence, sc.archive_evidence}
                npc_supported = required <= proof
            elif role == "location_concealer":
                required = {sc.bell_evidence, sc.archive_evidence}
                npc_supported = required <= proof
        self._adopted_supported = sum((time_supported, location_supported, npc_supported))
        self.single_witness_count = 0
        for shown in (support, support, proof):
            if len(shown & sc.independent_sources) < 2:
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
        sc = self.scenario
        return {
            "environment_seed": self.environment_seed,
            "scenario_label": sc.label,
            "location": self.node,
            "questions_used": self.questions_used,
            "questions_remaining": self.questions_remaining,
            "repeated_questions": self.repeated_questions,
            "overruns": self.overruns,
            "heard_answer_ids": [record["answer_id"] for record in self.heard],
            "physical_evidence_ids": list(self.evidence_ids),
            "comparison_results": dict(self.comparison_results),
            "unreliable_proven": list(self.unreliable_proven),
            "submitted": self.submitted,
            "judge_reason": self.judge_reason,
            "single_witness_count": self.single_witness_count,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        sc = self.scenario
        planted = set(sc.planted)
        detected = sum(1 for npc in self.unreliable_proven if npc in planted)
        if self.submitted:
            adoption: MValue = ratio(self._adopted_supported, 3)
        elif self.status.value == "step_limit_reached":
            adoption = censored("未提交即截尾")
        else:
            adoption = not_applicable("终局失败且未提交")
        partial_npc = sc.partial_npc
        if partial_npc is None:
            partial: MValue = not_applicable("案卷无部分真实证人")
        else:
            partial = valid(
                int(self.comparison_results.get(partial_npc) == "TESTIMONY_PARTIALLY_SUPPORTED")
            )
        return {
            "map29.v10.contradiction_detection_rate": ratio(detected, len(planted)),
            "map29.v10.evidence_supported_testimony_ratio": adoption,
            "map29.v10.partial_truth_classified": partial,
            "map29.v10.query_budget_overruns": valid(self.overruns),
            "map29.v10.single_witness_trust": valid(self.single_witness_count),
            "map29.v10.questions_used": valid(self.questions_used),
        }

    def mechanism_triggered(self) -> bool:
        """至少证明过一名植入矛盾证人（时间锚定或地点隐瞒）。"""

        return any(npc in self.scenario.planted for npc in self.unreliable_proven)


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    sc = SCENARIOS[environment_seed]
    environment = Map29V10Environment(seed=environment_seed)
    actions: list[dict[str, Any]] = []

    def step(payload: dict[str, Any]) -> None:
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))

    def go(room: str) -> None:
        if environment.node == room:
            return
        if environment.node != "H":
            step({"tool": "move", "to": "H"})
        step({"tool": "move", "to": room})

    time_npc = sc.npc_at("time_anchored")
    place_npc = sc.npc_at("location_concealer")
    archive_npc = sc.npc_at("archive_keeper")

    go(sc.rooms[archive_npc])
    if sc.archive_prereq is not None:
        sound_npc = sc.npc_at("sound_only")
        go(sc.rooms[sound_npc])
        step(
            {
                "tool": "ask",
                "npc_id": sound_npc,
                "question_template_id": "SOUND_PATTERN",
            }
        )
        go(sc.rooms[archive_npc])
    step({"tool": "ask", "npc_id": archive_npc, "question_template_id": "ARCHIVE_CROSS_INDEX"})

    go(sc.rooms[time_npc])
    step({"tool": "ask", "npc_id": time_npc, "question_template_id": "OPEN_ACCOUNT"})
    step({"tool": "ask", "npc_id": time_npc, "question_template_id": "TIME_BASIS"})
    go("L")
    step({"tool": "investigate", "target_id": "study_clock"})
    if sc.roles.get(place_npc) == "location_concealer":
        go(sc.rooms[place_npc])
        step({"tool": "ask", "npc_id": place_npc, "question_template_id": "OPEN_ACCOUNT"})

    go(sc.truth_location)
    step({"tool": "investigate", "target_id": "bell_trace"})

    step(
        {
            "tool": "compare_testimony",
            "npc_id": time_npc,
            "statement_ids": sorted(environment._claim_statement_ids(time_npc))
            + [f"{time_npc}_TIME_BASIS_STOPPED_{_compact(sc.clock_time)}"],
            "against_evidence_ids": [sc.clock_evidence, sc.archive_evidence],
        }
    )
    go("H")
    proof = [
        f"{time_npc}_TIME_CLAIM_{_compact(sc.clock_time)}",
        f"{time_npc}_TIME_BASIS_STOPPED_{_compact(sc.clock_time)}",
        sc.clock_evidence,
        sc.archive_evidence,
    ]
    step(
        {
            "tool": "submit",
            "event_time": sc.truth_time,
            "event_location": sc.truth_location,
            "unreliable_npc_id": time_npc,
            "support_ids": [sc.archive_evidence, sc.bell_evidence],
            "unreliability_proof_ids": proof,
        }
    )
    return actions


ROOM_LABEL = {
    "H": "中枢",
    "L": "书房",
    "K": "厨房",
    "Y": "庭院",
    "G": "档案室",
}

__all__ = [
    "NPC_LABEL",
    "ROLE_DESCRIPTION",
    "ROOM_LABEL",
    "ROOMS",
    "SCENARIOS",
    "Answer",
    "Map29V10Environment",
    "Scenario29",
    "build_scenario",
    "oracle_actions",
]
