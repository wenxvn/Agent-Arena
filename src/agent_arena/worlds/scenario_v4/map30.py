"""V4 MAP-30, bounded courtroom investigation with long-gap evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4EventClaim,
    V4Map30Observation,
    V4Status,
)

NODES = {"H", "B", "K", "Y", "L", "A", "T", "J"}
EDGES = {
    frozenset(edge)
    for edge in (
        ("H", "B"),
        ("B", "K"),
        ("K", "Y"),
        ("H", "L"),
        ("L", "A"),
        ("A", "T"),
        ("K", "T"),
        ("H", "J"),
    )
}
NODE_NPCS = {"A": "ARCHIVE_CLERK", "B": "BANQUET_CLERK", "K": "KITCHEN_COOK", "T": "TOWER_WATCH"}
NODE_EVIDENCE = {
    "A": {"Q4_ARCHIVE_DOCKET"},
    "B": {"B_KEY_STUB_2310"},
    "K": {"K_WAX_PLATE_2322"},
    "T": {"T_CHAIN_REGISTER_2340"},
}
ENTRY_ALLOWED = {
    "Q4_CODEBOOK": {"Q4_CODE_INDEX"},
    "EVENT_1_HANDOFF": {"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"},
    "EVENT_2_WAX": {"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"},
    "EVENT_3_SIGNAL": {"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"},
}
ENTRY_REQUIRED = {key: set(values) for key, values in ENTRY_ALLOWED.items()}
ENTRY_ORDER = ("Q4_CODEBOOK", "EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL")
CLAIMS = (
    V4EventClaim(event_id="EVENT_1_HANDOFF", time="23:10", location="B", duty_code="M4"),
    V4EventClaim(event_id="EVENT_2_WAX", time="23:22", location="K", duty_code="M4"),
    V4EventClaim(event_id="EVENT_3_SIGNAL", time="23:40", location="T", duty_code="M4"),
)
EVIDENCE = {
    "Q4_ARCHIVE_DOCKET": {
        "location": "A",
        "source_class": "sealed_archive_envelope",
        "fact": {"document_id": "Q4", "requires_archive_clerk_interview": True},
        "text": "书架后的封套标为Q4，封口要求档案员当面核验。",
    },
    "Q4_CODE_INDEX": {
        "location": "A",
        "source_class": "signed_duty_archive",
        "fact": {"document_id": "Q4", "M4": "MARA_VENN"},
        "text": "Q4的值勤暗码索引写明：M-4对应档案员玛拉·维恩。",
    },
    "B_KEY_STUB_2310": {
        "location": "B",
        "source_class": "physical_receipt",
        "fact": {"time": "23:10", "location": "B", "object": "K7", "signed_code": "M4"},
        "text": "宴会厅钥匙回执记载：23:10，K7由M-4签收。",
    },
    "B_WITNESS_HANDOFF": {
        "location": "B",
        "source_class": "witness_confirmation",
        "fact": {"time": "23:10", "location": "B", "object": "K7", "signed_code": "M4"},
        "text": "宴会管事核对回执后确认，23:10是M-4本人取走K7。",
    },
    "K_WAX_PLATE_2322": {
        "location": "K",
        "source_class": "physical_trace",
        "fact": {"time": "23:22", "location": "K", "object": "wax_plate", "duty_code": "M4"},
        "text": "炉边蜡板的余温刻度停在23:22，压痕旁留有M-4记号。",
    },
    "K_WITNESS_WAX_ROUTE": {
        "location": "K",
        "source_class": "witness_confirmation",
        "fact": {"time": "23:22", "location": "K", "action": "heated_wax_plate", "duty_code": "M4"},
        "text": "厨师想起：看到上一段K7交接记录后，他认出M-4在23:22用蜡板加热封蜡。",
    },
    "T_CHAIN_REGISTER_2340": {
        "location": "T",
        "source_class": "mechanical_register",
        "fact": {"time": "23:40", "location": "T", "mechanism": "bell_chain", "duty_code": "M4"},
        "text": "塔楼链轮计数器在23:40推进一格，操作牌刻着M-4。",
    },
    "T_WITNESS_SIGNAL_ROUTE": {
        "location": "T",
        "source_class": "witness_confirmation",
        "fact": {
            "time": "23:40",
            "location": "T",
            "route": "K_T_secret_passage",
            "duty_code": "M4",
        },
        "text": "守塔人看到出示厨房封蜡记录后，才想起M-4于23:40从K-T密道侧进入并拉动铃链。",
    },
}
NPC_ANSWERS = {
    "ARCHIVE_CLERK": {
        "Q4_without_docket": (
            "ARCHIVE_Q4_UNLOCATED",
            (),
            "没有封套编号，我无法确认你要查哪份值勤表。",
        ),
        "Q4_with_docket": (
            "ARCHIVE_Q4_INDEX_CONFIRMED",
            ("Q4_CODE_INDEX",),
            "Q4的值勤暗码索引写明：M-4对应档案员玛拉·维恩。",
        ),
    },
    "BANQUET_CLERK": {
        "HANDOFF_without_stub": (
            "B_GENERIC_HANDOFF_MEMORY",
            (),
            "我记得钥匙离开过宴会厅，但没有回执就想不起具体时刻和签领人。",
        ),
        "HANDOFF_with_stub": (
            "B_WITNESS_HANDOFF",
            ("B_WITNESS_HANDOFF",),
            "核对回执后，我确认23:10是M-4本人取走K7。",
        ),
    },
    "KITCHEN_COOK": {
        "WAX_without_event_1": (
            "K_GENERIC_OVEN_MEMORY",
            (),
            "那晚炉子开过；我想不起是哪一段工作之后。",
        ),
        "WAX_with_event_1": (
            "K_WITNESS_WAX_ROUTE",
            ("K_WITNESS_WAX_ROUTE",),
            "看到上一段K7交接记录后，我认出M-4在23:22用蜡板加热封蜡。",
        ),
    },
    "TOWER_WATCH": {
        "SIGNAL_without_event_2": (
            "T_GENERIC_NIGHT_MEMORY",
            (),
            "午夜前有人经过塔楼，但我记不清是哪一次巡更。",
        ),
        "SIGNAL_with_event_2": (
            "T_WITNESS_SIGNAL_ROUTE",
            ("T_WITNESS_SIGNAL_ROUTE",),
            "看到厨房封蜡记录后，我想起M-4于23:40从K-T密道侧进入并拉动铃链。",
        ),
    },
}


@dataclass(frozen=True)
class WitnessRule:
    """One ordered witness answer rule; prerequisite-free rules act as fallback."""

    answer_id: str
    evidence_ids: tuple[str, ...]
    text: str
    requires_shown_evidence: str | None = None
    requires_casebook_entry: str | None = None
    condition_key: str | None = None


def _default_witness_rules() -> dict[str, tuple[WitnessRule, ...]]:
    return {
        "ARCHIVE_CLERK": (
            WitnessRule(
                "ARCHIVE_Q4_INDEX_CONFIRMED",
                ("Q4_CODE_INDEX",),
                "Q4的值勤暗码索引写明：M-4对应档案员玛拉·维恩。",
                requires_shown_evidence="Q4_ARCHIVE_DOCKET",
                condition_key="Q4_with_docket",
            ),
            WitnessRule(
                "ARCHIVE_Q4_UNLOCATED",
                (),
                "没有封套编号，我无法确认你要查哪份值勤表。",
                condition_key="Q4_without_docket",
            ),
        ),
        "BANQUET_CLERK": (
            WitnessRule(
                "B_WITNESS_HANDOFF",
                ("B_WITNESS_HANDOFF",),
                "核对回执后，我确认23:10是M-4本人取走K7。",
                requires_shown_evidence="B_KEY_STUB_2310",
                condition_key="HANDOFF_with_stub",
            ),
            WitnessRule(
                "B_GENERIC_HANDOFF_MEMORY",
                (),
                "我记得钥匙离开过宴会厅，但没有回执就想不起具体时刻和签领人。",
                condition_key="HANDOFF_without_stub",
            ),
        ),
        "KITCHEN_COOK": (
            WitnessRule(
                "K_WITNESS_WAX_ROUTE",
                ("K_WITNESS_WAX_ROUTE",),
                "看到上一段K7交接记录后，我认出M-4在23:22用蜡板加热封蜡。",
                requires_casebook_entry="EVENT_1_HANDOFF",
                condition_key="WAX_with_event_1",
            ),
            WitnessRule(
                "K_GENERIC_OVEN_MEMORY",
                (),
                "那晚炉子开过；我想不起是哪一段工作之后。",
                condition_key="WAX_without_event_1",
            ),
        ),
        "TOWER_WATCH": (
            WitnessRule(
                "T_WITNESS_SIGNAL_ROUTE",
                ("T_WITNESS_SIGNAL_ROUTE",),
                "看到厨房封蜡记录后，我想起M-4于23:40从K-T密道侧进入并拉动铃链。",
                requires_casebook_entry="EVENT_2_WAX",
                condition_key="SIGNAL_with_event_2",
            ),
            WitnessRule(
                "T_GENERIC_NIGHT_MEMORY",
                (),
                "午夜前有人经过塔楼，但我记不清是哪一次巡更。",
                condition_key="SIGNAL_without_event_2",
            ),
        ),
    }


@dataclass(frozen=True)
class Map30Case:
    """One courtroom case definition shared by the rule engine and V6 fixtures."""

    nodes: frozenset[str] = frozenset(NODES)
    edges: frozenset[frozenset[str]] = frozenset(EDGES)
    node_evidence: dict[str, set[str]] = field(
        default_factory=lambda: {k: set(v) for k, v in NODE_EVIDENCE.items()}
    )
    node_npcs: dict[str, str] = field(default_factory=lambda: dict(NODE_NPCS))
    entry_allowed: dict[str, set[str]] = field(
        default_factory=lambda: {k: set(v) for k, v in ENTRY_ALLOWED.items()}
    )
    entry_order: tuple[str, ...] = ENTRY_ORDER
    claims: tuple[V4EventClaim, ...] = CLAIMS
    evidence: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(EVIDENCE))
    witness_rules: dict[str, tuple[WitnessRule, ...]] = field(
        default_factory=_default_witness_rules
    )
    culprit: str = "MARA_VENN"
    code_entry: str = "Q4_CODEBOOK"
    code_index_evidence: str = "Q4_CODE_INDEX"
    deadline: int = 40
    casebook_capacity: int = 4

    @property
    def entry_required(self) -> dict[str, set[str]]:
        return {key: set(values) for key, values in self.entry_allowed.items()}


DEFAULT_CASE = Map30Case()


class Map30Environment(ScenarioV4Environment):
    map_id = "MAP-30"

    def __init__(
        self,
        *,
        casebook_visible: bool = True,
        step_limit: int = 100,
        case: Map30Case | None = None,
    ) -> None:
        # Optional case parameter lets the V6 fixture layer build independent
        # investigations from the same engine. Defaults reproduce reviewed V4 MAP-30.
        self.casebook_visible = casebook_visible
        self.step_limit = min(step_limit, 100)
        self.case = case if case is not None else DEFAULT_CASE
        self.seed = 0
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(0)

    @property
    def tick(self) -> int:
        return self.current_tick

    def _reset_state(self, seed: int) -> None:
        if seed not in {0, 1, 2}:
            raise ValueError("MAP-30 only accepts the three registered fixed-scene repeat labels.")
        self.node = "H"
        self.current_tick = 0
        self.casebook: dict[str, set[str]] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.seen_evidence: set[str] = set()
        self.npc_answers: list[dict[str, Any]] = []
        self.current_hypothesis: dict[str, Any] | None = None
        self.hypothesis_count = 0
        self.chain_reconciled = False
        self.unsupported_formal_accusations = 0
        self.last_result = "INITIAL"
        self.last_action: dict[str, Any] | None = None
        self.final_claim: dict[str, Any] | None = None
        self.q4_gap_observed = False

    def _casebook_view(self) -> tuple[dict[str, Any], ...]:
        if not self.casebook_visible:
            return ()
        return tuple(
            {
                "entry_id": key,
                "evidence_ids": tuple(sorted(ids)),
                "recorded_evidence": tuple(
                    {
                        "evidence_id": evidence_id,
                        "source_class": self.case.evidence[evidence_id]["source_class"],
                        "fact": self.case.evidence[evidence_id]["fact"],
                        "rendered_text": self.case.evidence[evidence_id]["text"],
                    }
                    for evidence_id in sorted(ids)
                ),
            }
            for key, ids in self.casebook.items()
        )

    def _observation(self) -> V4Map30Observation:
        neighbors = tuple(
            sorted(
                next(n for n in edge if n != self.node)
                for edge in self.case.edges
                if self.node in edge
            )
        )
        recent = self.recent_events[-5:]
        recent_ids = {
            evidence_id for event in recent for evidence_id in event.get("evidence_ids", [])
        }
        if (
            self.case.code_index_evidence not in recent_ids
            and self.case.code_entry in self.casebook
        ):
            self.q4_gap_observed = True
        return V4Map30Observation(
            current_tick=self.current_tick,
            current_node=self.node,
            local_neighbors=neighbors,
            public_alert="MIDNIGHT_TRIAL_PENDING",
            visible_local_evidence=tuple(
                sorted(self.case.node_evidence.get(self.node, set()) - self.seen_evidence)
            ),
            recent_action_window=tuple(recent),
            casebook=self._casebook_view(),
            current_hypothesis=self.current_hypothesis,
            unsupported_formal_accusations=self.unsupported_formal_accusations,
            last_action_result=self.last_result,
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _available_evidence(self) -> set[str]:
        recent_ids = {
            evidence_id
            for event in self.recent_events[-5:]
            for evidence_id in event.get("evidence_ids", [])
        }
        recorded_ids = {evidence_id for ids in self.casebook.values() for evidence_id in ids}
        return recent_ids | recorded_ids

    def _record(self, result: str, payload: dict[str, Any] | None) -> None:
        row: dict[str, Any] = {
            "tick": self.current_tick,
            "action": self.last_action,
            "result": result,
            "public_payload": payload,
        }
        if payload:
            row["evidence_ids"] = list(payload.get("evidence_ids", []))
        if result != "INITIAL":
            self.recent_events.append(row)
        self.last_result = result

    def _advance(self, result: str, payload: dict[str, Any] | None = None) -> str:
        self.current_tick += 1
        if self.status is V4Status.RUNNING and self.current_tick >= self.case.deadline:
            self.status = V4Status.FAILURE
            self.terminal_reason = "DEADLINE_REACHED"
            result = self.terminal_reason
        self._record(result, payload)
        return result

    def _apply(self, action: ScenarioV4Action) -> str:
        self.last_action = action.model_dump(exclude_none=True)
        payload: dict[str, Any] | None = None
        name = action.tool
        if name == "move":
            target = action.to
            if (
                target not in self.case.nodes
                or frozenset((self.node, target)) not in self.case.edges
            ):
                return self._reject("INVALID_MOVE")
            self.node = target
            result = "MOVE_SUCCEEDED"
        elif name == "inspect":
            evidence_id = action.evidence_id
            if evidence_id not in self.case.node_evidence.get(self.node, set()):
                return self._reject("EVIDENCE_NOT_AVAILABLE")
            assert evidence_id is not None
            item = self.case.evidence[evidence_id]
            self.seen_evidence.add(evidence_id)
            payload = {
                "evidence_ids": [evidence_id],
                "evidence": [
                    {
                        "evidence_id": evidence_id,
                        "source_class": item["source_class"],
                        "fact": item["fact"],
                        "rendered_text": item["text"],
                    }
                ],
            }
            result = f"EVIDENCE_FOUND:{evidence_id}"
        elif name == "interview":
            npc_id = action.npc_id
            if (
                npc_id not in self.case.witness_rules
                or self.case.node_npcs.get(self.node) != npc_id
            ):
                return self._reject("NPC_NOT_HERE")
            shown_ids = set(action.shown_evidence_ids or [])
            shown_entries = set(action.shown_casebook_entry_ids or [])
            if not shown_ids.issubset(self._available_evidence()) or not shown_entries.issubset(
                self.casebook
            ):
                return self._reject("EVIDENCE_NOT_AVAILABLE")
            answer = self._interview_answer(npc_id, shown_ids, shown_entries)
            self.seen_evidence.update(answer["evidence_ids"])
            self.npc_answers.append(answer)
            payload = {
                "evidence_ids": answer["evidence_ids"],
                "npc_answer": answer,
                "evidence": [
                    {
                        "evidence_id": evidence_id,
                        "source_class": self.case.evidence[evidence_id]["source_class"],
                        "fact": self.case.evidence[evidence_id]["fact"],
                        "rendered_text": self.case.evidence[evidence_id]["text"],
                    }
                    for evidence_id in answer["evidence_ids"]
                ],
            }
            result = f"ANSWER_RECEIVED:{answer['answer_id']}"
        elif name == "record":
            entry_id = action.entry_id
            evidence_ids = set(action.evidence_ids or [])
            if entry_id not in self.case.entry_allowed or not evidence_ids:
                return self._reject("INVALID_CASEBOOK_ENTRY")
            if not evidence_ids.issubset(self._available_evidence()) or not evidence_ids.issubset(
                self.case.entry_allowed[entry_id]
            ):
                return self._reject("EVIDENCE_NOT_AVAILABLE")
            if entry_id not in self.casebook:
                if len(self.casebook) >= self.case.casebook_capacity:
                    return self._reject("CASEBOOK_FULL")
                self.casebook[entry_id] = set()
            self.casebook[entry_id].update(evidence_ids)
            result = f"ENTRY_RECORDED:{entry_id}"
            payload = {"entry_id": entry_id, "evidence_ids": sorted(evidence_ids)}
        elif name == "submit_intermediate_hypothesis":
            self.current_hypothesis = {
                "candidate_person": action.candidate_person,
                "confidence": action.confidence,
                "event_ids_known": list(action.event_ids_known or []),
            }
            self.hypothesis_count += 1
            payload = {"hypothesis": self.current_hypothesis}
            result = "HYPOTHESIS_RECORDED"
        elif name == "compare_records":
            entry_ids = set(action.entry_ids or [])
            if not entry_ids.issubset(self.casebook):
                return self._reject("CASEBOOK_ENTRY_NOT_FOUND")
            code_required = self.case.entry_required[self.case.code_entry]
            if (
                self.case.code_entry not in self.casebook
                or not code_required.issubset(self.casebook[self.case.code_entry])
            ):
                result = "CODE_KEY_NOT_RECORDED"
            elif not set(self.case.entry_order).issubset(entry_ids):
                result = "RECORDS_DO_NOT_ALIGN"
            elif all(
                entry in self.casebook
                and self.case.entry_required[entry].issubset(self.casebook[entry])
                for entry in self.case.entry_order
            ):
                self.chain_reconciled = True
                result = "CHAIN_COHERENT"
            else:
                result = "RECORDS_DO_NOT_ALIGN"
        elif name == "formal_accuse":
            if self.node != "J":
                return self._reject("COURTROOM_REQUIRED")
            self.final_claim = {
                "person_id": action.person_id,
                "event_claims": [claim.model_dump() for claim in (action.event_claims or [])],
                "cited_entry_ids": list(action.cited_entry_ids or []),
            }
            complete = (
                set(self.case.entry_order).issubset(set(action.cited_entry_ids or []))
                and self.chain_reconciled
                and all(
                    entry in self.casebook
                    and self.case.entry_required[entry].issubset(self.casebook[entry])
                    for entry in self.case.entry_order
                )
            )
            accurate = (
                action.person_id == self.case.culprit
                and tuple(action.event_claims or ()) == self.case.claims
            )
            if complete and accurate:
                self.status = V4Status.SUCCESS
                self.terminal_reason = "ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN"
                result = self.terminal_reason
            else:
                self.unsupported_formal_accusations += 1
                if self.unsupported_formal_accusations > 1:
                    self.status = V4Status.FAILURE
                    self.terminal_reason = "ACCUSATION_LIMIT_EXCEEDED"
                    result = self.terminal_reason
                else:
                    result = "ACCUSATION_NOT_SUSTAINED"
        else:
            return self._reject("ACTION_NOT_AVAILABLE")
        return self._advance(result, payload)

    def _interview_answer(
        self, npc_id: str, shown_ids: set[str], shown_entries: set[str]
    ) -> dict[str, Any]:
        rules = self.case.witness_rules.get(npc_id, ())
        required = self.case.entry_required
        selected: WitnessRule | None = None
        for rule in rules:
            if (
                rule.requires_shown_evidence is not None
                and rule.requires_shown_evidence not in shown_ids
            ):
                continue
            if rule.requires_casebook_entry is not None:
                entry = rule.requires_casebook_entry
                if entry not in shown_entries or not required[entry].issubset(
                    self.casebook.get(entry, set())
                ):
                    continue
            selected = rule
            break
        if selected is None and rules:
            selected = rules[-1]
        if selected is None:
            raise AssertionError("MAP-30 witness has no answer rules.")
        return {
            "npc_id": npc_id,
            "answer_id": selected.answer_id,
            "evidence_ids": list(selected.evidence_ids),
            "rendered_text": selected.text,
            "condition_key": selected.condition_key or selected.answer_id,
        }

    def _reject(self, reason: str) -> str:
        self.last_result = reason
        return reason

    def _invalid_action(self) -> str:
        return self._reject("INVALID_ACTION_SCHEMA")

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "node": self.node,
            "tick": self.current_tick,
            "casebook": {key: sorted(ids) for key, ids in self.casebook.items()},
            "recent_events": self.recent_events[-5:],
            "seen_evidence": sorted(self.seen_evidence),
            "chain_reconciled": self.chain_reconciled,
            "unsupported_formal_accusations": self.unsupported_formal_accusations,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
        }

    def metrics(self) -> dict[str, Any]:
        final = self.final_claim or {}
        claims = final.get("event_claims", [])
        correct_count = sum(
            claim == expected.model_dump()
            for claim, expected in zip(claims, self.case.claims, strict=False)
        )
        evidence_ids = {evidence_id for ids in self.casebook.values() for evidence_id in ids}
        return {
            "success": self.is_success,
            "finish_tick": self.current_tick,
            "terminal_reason": self.terminal_reason,
            "unsupported_formal_accusations": self.unsupported_formal_accusations,
            "casebook_entry_count": len(self.casebook),
            "casebook_source_count": len(evidence_ids),
            "q4_recorded": self.case.code_entry in self.casebook,
            "q4_gap_observed": self.q4_gap_observed,
            "q4_recalled_after_gap": (
                None
                if not self.q4_gap_observed or self.final_claim is None
                else self.final_claim.get("person_id") == self.case.culprit
                and self.case.code_entry in self.final_claim.get("cited_entry_ids", [])
            ),
            "event_claim_accuracy": f"{correct_count}/3",
            "timeline_consistent": [claim.get("time") for claim in claims]
            == [claim.time for claim in self.case.claims],
            "comparison_succeeded": self.chain_reconciled,
            "hypothesis_count": self.hypothesis_count,
            "hypotheses_adjudicated": False,
            "npc_answer_ids": [answer["answer_id"] for answer in self.npc_answers],
            "npc_condition_keys": [answer["condition_key"] for answer in self.npc_answers],
            "weak_tower_answer_then_conditioned_answer": (
                "T_GENERIC_NIGHT_MEMORY" in {answer["answer_id"] for answer in self.npc_answers}
                and "T_WITNESS_SIGNAL_ROUTE" in {answer["answer_id"] for answer in self.npc_answers}
            ),
        }
