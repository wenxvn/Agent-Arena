"""MAP-30 V10｜午夜审判：公开案卷条目、跨阶段依赖与可审计召回（DCR-V10-07）。

与 V4/V8 的差异：

- **公开接口**：`record(entry_id)` 的合法条目 ID 就是四个公开 `topic_id`
  （EVENT_1_HANDOFF / EVENT_2_WAX / EVENT_3_SIGNAL / Q4_CODEBOOK）；公开“每个事件条目
  需要**现场记录 + 证人确认**成对才完整”、`formal_accuse` 只能在法庭节点 J、
  以及“近期窗口只有 5 条事件，案卷是唯一跨窗口可引用的记忆”；
- **跨阶段依赖随 seed 变化**：seed 1 的事件 2 解锁条件是“出示事件 1 的完整条目 +
  事件 2 物证”，seed 2 换入一个**诱饵事件**（记录了但引用它会失败），
  seed 3 要求先归档事件 1 才能解锁事件 3；
- **指标修复**（V9 DCR-30 候选 C）：`accusation_claim_precision` 只统计**被接受**的
  `formal_accuse`（在 J 且链条已核对）；`q4_recall_accuracy` 要求 Q4 条目**真的记录过**
  且被引用，否则 N/A；两者都不再给未发生的指控打分；
- `evidence_chain_coverage` 是过程量（截尾仍 VALID），`chain_reconciled` 与
  `window_pressure_events` 分别记录“链条是否核对”与“长间隔召回是否被触发”。
"""

from __future__ import annotations

from dataclasses import dataclass
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

EDGES = {
    "H_B": ("H", "B"),
    "H_J": ("H", "J"),
    "H_L": ("H", "L"),
    "L_K": ("L", "K"),
    "K_T": ("K", "T"),
    "T_A": ("T", "A"),
}
ADJACENCY: dict[str, tuple[str, ...]] = {
    "H": ("B", "J", "L"),
    "B": ("H",),
    "J": ("H",),
    "L": ("H", "K"),
    "K": ("L", "T"),
    "T": ("K", "A"),
    "A": ("T",),
}
WINDOW = 5
COURTROOM = "J"


@dataclass(frozen=True)
class Event30:
    entry_id: str
    room: str
    evidence_id: str
    witness_id: str
    witness_answer_id: str
    duty_code: str
    time: str
    location: str
    unlock_by: str = "previous_entry"  # previous_entry / evidence / both / archive_previous
    is_decoy: bool = False


@dataclass(frozen=True)
class Scenario30:
    label: str
    culprit_code: str
    culprit_person: str
    doc_id: str
    archive_room: str
    archive_evidence: str
    archive_witness: str
    archive_answer: str
    events: tuple[Event30, ...]

    @property
    def truth_events(self) -> tuple[Event30, ...]:
        return tuple(event for event in self.events if not event.is_decoy)

    @property
    def entry_ids(self) -> tuple[str, ...]:
        return tuple([*(event.entry_id for event in self.events), "Q4_CODEBOOK"])

    @property
    def required_entry_ids(self) -> tuple[str, ...]:
        return tuple([*(event.entry_id for event in self.truth_events), "Q4_CODEBOOK"])


SCENARIOS: dict[int, Scenario30] = {
    0: Scenario30(
        label="three_events_banquet_kitchen_tower",
        culprit_code="M4",
        culprit_person="MARA_VENN",
        doc_id="Q4",
        archive_room="A",
        archive_evidence="Q4_ARCHIVE_DOCKET",
        archive_witness="ARCHIVE_CLERK",
        archive_answer="Q4_CODE_INDEX",
        events=(
            Event30(
                "EVENT_1_HANDOFF",
                "B",
                "B_KEY_STUB_2310",
                "BANQUET_CLERK",
                "B_WITNESS_HANDOFF",
                "M4",
                "23:10",
                "B",
                "evidence",
            ),
            Event30(
                "EVENT_2_WAX",
                "K",
                "K_WAX_PLATE_2322",
                "KITCHEN_COOK",
                "K_WITNESS_WAX_ROUTE",
                "M4",
                "23:22",
                "K",
            ),
            Event30(
                "EVENT_3_SIGNAL",
                "T",
                "T_CHAIN_REGISTER_2340",
                "TOWER_WATCH",
                "T_WITNESS_SIGNAL_ROUTE",
                "M4",
                "23:40",
                "T",
            ),
        ),
    ),
    1: Scenario30(
        label="rotated_rooms_dual_unlock",
        culprit_code="K7",
        culprit_person="ADA_SORREL",
        doc_id="Q7",
        archive_room="A",
        archive_evidence="Q7_ARCHIVE_DOCKET",
        archive_witness="ARCHIVE_CLERK",
        archive_answer="Q7_CODE_INDEX",
        events=(
            Event30(
                "EVENT_1_HANDOFF",
                "K",
                "K_SEAL_STUB_2205",
                "KITCHEN_COOK",
                "K_WITNESS_HANDOFF",
                "K7",
                "22:05",
                "K",
                "evidence",
            ),
            Event30(
                "EVENT_2_WAX",
                "T",
                "T_ROPE_MARK_2220",
                "TOWER_WATCH",
                "T_WITNESS_ROPE_ROUTE",
                "K7",
                "22:20",
                "T",
                "both",
            ),
            Event30(
                "EVENT_3_SIGNAL",
                "B",
                "B_BELL_STUB_2255",
                "BANQUET_CLERK",
                "B_WITNESS_BELL_ROUTE",
                "K7",
                "22:55",
                "B",
                "archive_previous",
            ),
        ),
    ),
    2: Scenario30(
        label="decoy_event_and_false_lead",
        culprit_code="D5",
        culprit_person="BASIL_ORNE",
        doc_id="Q2",
        archive_room="A",
        archive_evidence="Q2_ARCHIVE_DOCKET",
        archive_witness="ARCHIVE_CLERK",
        archive_answer="Q2_CODE_INDEX",
        events=(
            Event30(
                "EVENT_1_HANDOFF",
                "B",
                "B_KEY_STUB_2340",
                "BANQUET_CLERK",
                "B_WITNESS_HANDOFF",
                "D5",
                "23:40",
                "B",
                "evidence",
            ),
            Event30(
                "EVENT_2_WAX",
                "K",
                "K_WAX_PLATE_2352",
                "KITCHEN_COOK",
                "K_WITNESS_WAX_ROUTE",
                "D5",
                "23:52",
                "K",
            ),
            Event30(
                "EVENT_4_DECOY_STAIRS",
                "L",
                "L_STAIR_DUST_2300",
                "GUARD_AT_L",
                "L_GENERIC_STAIR_MEMORY",
                "XX",
                "23:00",
                "L",
                "evidence",
                is_decoy=True,
            ),
            Event30(
                "EVENT_3_SIGNAL",
                "T",
                "T_CHAIN_REGISTER_0011",
                "TOWER_WATCH",
                "T_WITNESS_SIGNAL_ROUTE",
                "D5",
                "00:11",
                "T",
                "previous_entry",
            ),
        ),
    ),
}

ROOM_OF_EVIDENCE: dict[int, dict[str, str]] = {
    seed: {
        **{event.evidence_id: event.room for event in scenario.events},
        scenario.archive_evidence: scenario.archive_room,
    }
    for seed, scenario in SCENARIOS.items()
}
WITNESS_OF: dict[int, dict[str, str]] = {
    seed: {
        **{event.witness_id: event.room for event in scenario.events},
        scenario.archive_witness: scenario.archive_room,
    }
    for seed, scenario in SCENARIOS.items()
}


class Map30V10Environment(V10Map):
    map_id = "MAP-30"
    title = "午夜审判"
    world = "castle"
    level = "困难"
    RULE_VERSION = "v10.map30.1"
    SEED_SPACE = tuple(sorted(SCENARIOS))
    EDGES = EDGES
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "inspect": {frozenset({"tool", "evidence_id"})},
        "interview": {
            frozenset(
                {
                    "tool",
                    "npc_id",
                    "topic_id",
                    "shown_evidence_ids",
                    "shown_casebook_entry_ids",
                }
            )
        },
        "record": {frozenset({"tool", "entry_id", "evidence_ids"})},
        "compare_records": {frozenset({"tool", "entry_ids"})},
        "formal_accuse": {
            frozenset({"tool", "person_id", "event_claims", "cited_entry_ids"})
        },
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "local_neighbors",
            "visible_edges",
            "tick",
            "case_label",
            "npc_locations",
            "evidence_locations",
            "entry_ids",
            "entry_requirements",
            "courtroom_node",
            "recent_action_window",
            "visible_local_evidence",
            "casebook",
            "chain_reconciled",
            "goal",
        }
    )
    PRIMARY_METRIC = "map30.v10.evidence_chain_coverage"
    METRIC_SPECS = (
        MetricSpec(
            "map30.v10.evidence_chain_coverage",
            "primary",
            "higher",
            "已完整的案卷条目数 / 需要的条目数（3 事件 + 1 文书）",
            "需要的条目数（4）",
        ),
        MetricSpec(
            "map30.v10.accusation_claim_precision",
            "primary",
            "higher",
            "被接受的 formal_accuse 中匹配的事件主张数 / 3",
            "已接受指控的局（1）",
            zero_denominator="无被接受指控 → NOT_APPLICABLE（截尾 → CENSORED）",
        ),
        MetricSpec(
            "map30.v10.q4_recall_accuracy",
            "secondary",
            "higher",
            "人名正确且 Q4 条目已记录并被引用",
            "已提交指控的局（1）",
            zero_denominator="未提交指控 → NOT_APPLICABLE（截尾 → CENSORED）",
        ),
        MetricSpec(
            "map30.v10.chain_reconciled",
            "secondary",
            "higher",
            "compare_records 返回 CHAIN_COHERENT",
            "1",
        ),
        MetricSpec(
            "map30.v10.window_pressure_events",
            "diagnostic",
            "lower",
            "因 5 条近期窗口而过期的 record 尝试次数（长间隔召回证据）",
            "—",
            unit="count",
            valid_range=(0.0, 30.0),
        ),
        MetricSpec(
            "map30.v10.unsupported_accusations",
            "guardrail",
            "lower",
            "被拒绝或引用不完整链条的指控次数",
            "—",
            unit="count",
            valid_range=(0.0, 5.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.scenario = SCENARIOS[seed]
        self.node = "H"
        self.items = []
        self.events: list[dict[str, Any]] = []
        self.casebook: dict[str, list[str]] = {}
        self.chain_reconciled = False
        self.window_pressure = 0
        self.unsupported_accusations = 0
        self.accepted_accusation = False
        self.accuse_events: list[dict[str, Any]] = []
        self.cited_entries: list[str] = []
        self.accuse_person: str | None = None
        self._pending_cost = 1
        self._evidence_seen: set[str] = set()
        self._seen_objects: set[str] = set()

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "case_label": self.scenario.label,
            "entry_ids": list(self.scenario.entry_ids),
            "courtroom_node": COURTROOM,
            "recent_window": WINDOW,
            "truth_event_entries": [event.entry_id for event in self.scenario.truth_events],
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.scenario.label,
            "culprit_person": self.scenario.culprit_person,
            "culprit_code": self.scenario.culprit_code,
            "doc_id": self.scenario.doc_id,
            "events": [
                {
                    "event_id": event.entry_id,
                    "time": event.time,
                    "location": event.location,
                    "duty_code": event.duty_code,
                }
                for event in self.scenario.truth_events
            ],
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "房间图：H 连 B/J/L；L—K—T—A 为一条走廊。move(to) 1 tick；"
            f"正式指控 formal_accuse 只能在法庭节点 {COURTROOM}。",
            f"record(entry_id) 的合法条目 ID 仅：{', '.join(self.scenario.entry_ids)}。",
            "每个事件条目需要**现场记录 + 证人确认**两件证据；Q4_CODEBOOK 只需交叉索引文书。",
            "interview 的 topic_id 也用同一套条目 ID；证人分条件作答：需要出示对应物证，"
            "通常还需要**更早事件的完整条目**（档案看守要求先归档第一件事件），否则只给泛泛回忆。",
            "档案看守给出的交叉索引把值班代号（duty_code）映射到人名；"
            "现场物证同时公开该事件的 time / location / duty_code。",
            f"近期动作窗口只保留最近 {WINDOW} 条事件；窗口外只能通过 casebook 引用。",
            "compare_records(entry_ids) 返回 CHAIN_COHERENT 需四个条目都完整且交叉索引一致。",
        )

    # ------------------------------------------------------------------ helpers
    def _room_of_evidence(self, evidence_id: str) -> str | None:
        return ROOM_OF_EVIDENCE[self.environment_seed].get(evidence_id)

    def _available(self) -> set[str]:
        recent = {str(item["object_id"]) for item in self.events[-WINDOW:]}
        casebook = {item for ids in self.casebook.values() for item in ids}
        return recent | casebook

    def _required(self, entry_id: str) -> list[str]:
        if entry_id == "Q4_CODEBOOK":
            return [self.scenario.archive_answer]
        for event in self.scenario.events:
            if event.entry_id == entry_id:
                return [event.evidence_id, event.witness_answer_id]
        return []

    def _complete(self, entry_id: str) -> bool:
        recorded = set(self.casebook.get(entry_id, []))
        return bool(self._required(entry_id)) and set(self._required(entry_id)) <= recorded

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
            "case_label": self.scenario.label,
            "npc_locations": {
                **{event.witness_id: event.room for event in self.scenario.events},
                self.scenario.archive_witness: self.scenario.archive_room,
            },
            "evidence_locations": dict(ROOM_OF_EVIDENCE[self.environment_seed]),
            "entry_ids": list(self.scenario.entry_ids),
            "entry_requirements": {
                event.entry_id: [event.evidence_id, event.witness_answer_id]
                for event in self.scenario.events
            },
            "courtroom_node": COURTROOM,
            "recent_action_window": self._window(),
            "visible_local_evidence": self._visible_evidence(),
            "casebook": {
                entry_id: sorted(ids) for entry_id, ids in sorted(self.casebook.items())
            },
            "chain_reconciled": self.chain_reconciled,
            "goal": (
                "把三次近期事件从现场观察沉淀成可引用的案卷，用案卷解锁证人记忆，"
                "核对链条后在法庭节点提交一次有据指控。"
            ),
        }

    def _window(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.events[-WINDOW:]]

    def _visible_evidence(self) -> dict[str, Any]:
        """当前房间内**尚未取走**的物证。"""

        visible: dict[str, Any] = {}
        for event in self.scenario.events:
            if event.room == self.node and event.evidence_id not in self._evidence_seen:
                visible[event.evidence_id] = {
                    "time": event.time,
                    "location": event.location,
                    "duty_code": event.duty_code,
                }
        if (
            self.scenario.archive_room == self.node
            and self.scenario.archive_evidence not in self._evidence_seen
        ):
            visible[self.scenario.archive_evidence] = {"document_id": self.scenario.doc_id}
        return visible

    def _push(self, object_id: str, payload: dict[str, Any] | None = None) -> None:
        entry: dict[str, Any] = {
            "index": len(self.events),
            "object_id": object_id,
            "tick": self.tick_count,
        }
        if payload:
            entry["payload"] = payload
        self.events.append(entry)
        self._seen_objects.add(object_id)

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_cost = 1
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "inspect":
            return self._inspect(action)
        if tool == "interview":
            return self._interview(action)
        if tool == "record":
            return self._record(action)
        if tool == "compare_records":
            return self._compare(action)
        if tool == "formal_accuse":
            return self._accuse(action)
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        if action.to is None:
            return "INVALID_ACTION_SCHEMA"
        for edge_id in self.visible_edges():
            if self.edge_destination(edge_id) == action.to:
                self.node = action.to
                return "MOVE_SUCCEEDED"
        return "INVALID_MOVE"

    def _inspect(self, action: V8Action) -> str:
        evidence_id = str(action.evidence_id)
        room = self._room_of_evidence(evidence_id)
        if room is None:
            return "NO_SUCH_EVIDENCE"
        if room != self.node:
            return "EVIDENCE_NOT_HERE"
        if evidence_id in self._evidence_seen:
            return "EVIDENCE_ALREADY_TAKEN"
        self._evidence_seen.add(evidence_id)
        self._push(evidence_id)
        return f"INSPECTED:{evidence_id}"

    def _interview(self, action: V8Action) -> str:
        npc_id = str(action.npc_id)
        topic_id = str(action.topic_id)
        if npc_id not in WITNESS_OF[self.environment_seed]:
            return "UNKNOWN_NPC"
        if WITNESS_OF[self.environment_seed][npc_id] != self.node:
            return "NPC_NOT_HERE"
        if topic_id not in self.scenario.entry_ids:
            return "UNKNOWN_TOPIC"
        shown_evidence = {str(item) for item in (action.shown_evidence_ids or [])}
        shown_entries = {str(item) for item in (action.shown_casebook_entry_ids or [])}
        available = self._available()
        if any(item not in available for item in shown_evidence):
            if shown_evidence & self._seen_objects:
                self.window_pressure += 1
                return "EVIDENCE_NOT_AVAILABLE"
            return "STATEMENT_NOT_KNOWN"
        if any(item not in self.casebook for item in shown_entries):
            return "CASEBOOK_ENTRY_NOT_FOUND"

        for event in self.scenario.events:
            if event.witness_id != npc_id or event.entry_id != topic_id:
                continue
            if self._unlocked(event, shown_evidence, shown_entries):
                self._push(event.witness_answer_id)
                return f"ANSWER_RECEIVED:{event.witness_answer_id}"
            self._push(f"{npc_id}_GENERIC_MEMORY")
            return f"ANSWER_RECEIVED:{npc_id}_GENERIC_MEMORY"

        if npc_id == self.scenario.archive_witness and topic_id == "Q4_CODEBOOK":
            if self.scenario.archive_evidence in shown_evidence:
                self._push(
                    self.scenario.archive_answer,
                    {
                        "document_id": self.scenario.doc_id,
                        self.scenario.culprit_code: self.scenario.culprit_person,
                    },
                )
                return f"ANSWER_RECEIVED:{self.scenario.archive_answer}"
            self._push(f"{npc_id}_GENERIC_INDEX_MEMORY")
            return f"ANSWER_RECEIVED:{npc_id}_GENERIC_INDEX_MEMORY"
        self._push(f"{npc_id}_GENERIC_MEMORY")
        return f"ANSWER_RECEIVED:{npc_id}_GENERIC_MEMORY"

    def _unlocked(
        self, event: Event30, shown_evidence: set[str], shown_entries: set[str]
    ) -> bool:
        index = self.scenario.events.index(event)
        earlier = [item for item in self.scenario.events[:index] if not item.is_decoy]
        own = event.evidence_id in shown_evidence
        prev_ok = any(item.entry_id in shown_entries for item in earlier)
        if event.unlock_by == "evidence":
            return own
        if event.unlock_by == "both":
            return own and prev_ok
        if event.unlock_by == "archive_previous":
            first = self.scenario.truth_events[0]
            return own and first.entry_id in shown_entries
        return prev_ok

    def _record(self, action: V8Action) -> str:
        entry_id = str(action.entry_id)
        if entry_id not in self.scenario.entry_ids:
            self._pending_cost = 0
            return "INVALID_CASEBOOK_ENTRY"
        evidence = [str(item) for item in (action.evidence_ids or [])]
        if not evidence:
            self._pending_cost = 0
            return "EMPTY_ENTRY"
        available = self._available()
        if any(item not in available for item in evidence):
            if any(item in self._seen_objects for item in evidence):
                self.window_pressure += 1
                return "EVIDENCE_NOT_AVAILABLE"
            self._pending_cost = 0
            return "EVIDENCE_NOT_OBSERVED"
        current = self.casebook.setdefault(entry_id, [])
        for item in evidence:
            if item not in current:
                current.append(item)
        return f"ENTRY_RECORDED:{entry_id}"

    def _compare(self, action: V8Action) -> str:
        entry_ids = [str(item) for item in (action.entry_ids or [])]
        if any(item not in self.scenario.entry_ids for item in entry_ids):
            return "CASEBOOK_ENTRY_NOT_FOUND"
        if "Q4_CODEBOOK" not in self.casebook:
            return "CODE_KEY_NOT_RECORDED"
        if not all(self._complete(item) for item in self.scenario.required_entry_ids):
            return "CHAIN_INCOMPLETE"
        recorded = set(self.casebook.get("Q4_CODEBOOK", []))
        if self.scenario.archive_answer not in recorded:
            return "CODE_KEY_NOT_RECORDED"
        if set(self.scenario.required_entry_ids) - set(entry_ids):
            return "CHAIN_INCOMPLETE"
        self.chain_reconciled = True
        return "CHAIN_COHERENT"

    def _accuse(self, action: V8Action) -> str:
        if self.node != COURTROOM:
            return "COURTROOM_REQUIRED"
        cited = [str(item) for item in (action.cited_entry_ids or [])]
        claims = [
            {
                "event_id": claim.event_id,
                "time": claim.time,
                "location": claim.location,
                "duty_code": claim.duty_code,
            }
            for claim in (action.event_claims or [])
        ]
        self.accuse_person = action.person_id
        self.accuse_events = claims
        self.cited_entries = cited
        self.accepted_accusation = False

        truth = [
            {
                "event_id": event.entry_id,
                "time": event.time,
                "location": event.location,
                "duty_code": event.duty_code,
            }
            for event in self.scenario.truth_events
        ]
        complete_entries = all(self._complete(item) for item in self.scenario.required_entry_ids)
        cited_all = set(self.scenario.required_entry_ids) <= set(cited)
        no_decoy = not any(
            event.is_decoy and event.entry_id in cited for event in self.scenario.events
        )
        person_ok = action.person_id == self.scenario.culprit_person
        claims_ok = claims == truth

        accepted = (
            self.chain_reconciled
            and complete_entries
            and cited_all
            and no_decoy
            and person_ok
            and claims_ok
        )
        if accepted:
            self.accepted_accusation = True
            self._succeed(f"ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_{self.scenario.culprit_person}_PROVEN")
            return "ACCEPTED"
        self.unsupported_accusations += 1
        self._fail("ACCUSATION_REJECTED")
        if not complete_entries or not cited_all or not no_decoy:
            return "EVIDENCE_NOT_IN_CASEBOOK"
        return "ACCUSATION_CONTRADICTS_TRUTH"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._pending_cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "case_label": self.scenario.label,
            "location": self.node,
            "casebook": {key: sorted(ids) for key, ids in sorted(self.casebook.items())},
            "chain_reconciled": self.chain_reconciled,
            "window_events": len(self.events),
            "window_pressure_events": self.window_pressure,
            "unsupported_accusations": self.unsupported_accusations,
            "accepted_accusation": self.accepted_accusation,
            "accuse_person": self.accuse_person,
            "accuse_events": list(self.accuse_events),
            "cited_entries": list(self.cited_entries),
            "truth_seal": self.truth_seal(),
        }

    def _covered_entries(self) -> int:
        return sum(1 for item in self.scenario.required_entry_ids if self._complete(item))

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        required = list(self.scenario.required_entry_ids)
        coverage = ratio(self._covered_entries(), len(required))
        if self.accepted_accusation:
            truth = [
                {
                    "event_id": event.entry_id,
                    "time": event.time,
                    "location": event.location,
                    "duty_code": event.duty_code,
                }
                for event in self.scenario.truth_events
            ]
            matched = sum(1 for item in self.accuse_events if item in truth)
            precision: MValue = ratio(matched, len(truth))
        elif self.accuse_person is not None:
            precision = not_applicable("指控未被接受（未在法庭或链条未核对）")
        elif running:
            precision = censored("未提交指控即截尾")
        else:
            precision = not_applicable("无被接受指控")

        if self.accepted_accusation:
            q4_recorded = set(self.casebook.get("Q4_CODEBOOK", []))
            recall: MValue = valid(
                int(
                    self.accuse_person == self.scenario.culprit_person
                    and self.scenario.archive_answer in q4_recorded
                    and "Q4_CODEBOOK" in self.cited_entries
                )
            )
        elif self.accuse_person is not None or running:
            recall = censored("无被接受的指控")
        else:
            recall = not_applicable("未提交指控")
        return {
            "map30.v10.evidence_chain_coverage": coverage,
            "map30.v10.accusation_claim_precision": precision,
            "map30.v10.q4_recall_accuracy": recall,
            "map30.v10.chain_reconciled": valid(int(self.chain_reconciled)),
            "map30.v10.window_pressure_events": valid(self.window_pressure),
            "map30.v10.unsupported_accusations": valid(self.unsupported_accusations),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制被真实触发：至少有一个事件条目是“物证 + 证人确认”成对完整的。"""

        return any(
            self._complete(event.entry_id) for event in self.scenario.events if not event.is_decoy
        )


def _route(start: str, destination: str) -> list[str]:
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        path = queue.pop(0)
        for neighbor in ADJACENCY[path[-1]]:
            if neighbor == destination:
                return [*path, neighbor]
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append([*path, neighbor])
    raise ValueError(f"no route {start}->{destination}")


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    scenario = SCENARIOS[environment_seed]
    environment = Map30V10Environment(seed=environment_seed)
    actions: list[dict[str, Any]] = []

    def step(payload: dict[str, Any]) -> None:
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))

    def walk(destination: str) -> None:
        while environment.node != destination:
            step({"tool": "move", "to": _route(environment.node, destination)[1]})

    for index, event in enumerate(scenario.events):
        if event.is_decoy:
            continue
        walk(event.room)
        step({"tool": "inspect", "evidence_id": event.evidence_id})
        previous = None
        for item in scenario.events[:index]:
            if not item.is_decoy:
                previous = item
        shown_entries: list[str] = []
        needs_previous = event.unlock_by in ("previous_entry", "both", "archive_previous")
        if needs_previous and previous is not None:
            shown_entries = [previous.entry_id]
            if event.unlock_by == "archive_previous":
                shown_entries = [scenario.truth_events[0].entry_id, previous.entry_id]
        step(
            {
                "tool": "interview",
                "npc_id": event.witness_id,
                "topic_id": event.entry_id,
                "shown_evidence_ids": [event.evidence_id],
                "shown_casebook_entry_ids": sorted(set(shown_entries)),
            }
        )
        step(
            {
                "tool": "record",
                "entry_id": event.entry_id,
                "evidence_ids": [event.evidence_id, event.witness_answer_id],
            }
        )

    walk(scenario.archive_room)
    step({"tool": "inspect", "evidence_id": scenario.archive_evidence})
    step(
        {
            "tool": "interview",
            "npc_id": scenario.archive_witness,
            "topic_id": "Q4_CODEBOOK",
            "shown_evidence_ids": [scenario.archive_evidence],
            "shown_casebook_entry_ids": [],
        }
    )
    step(
        {
            "tool": "record",
            "entry_id": "Q4_CODEBOOK",
            "evidence_ids": [scenario.archive_answer],
        }
    )
    step({"tool": "compare_records", "entry_ids": list(scenario.required_entry_ids)})
    walk(COURTROOM)
    step(
        {
            "tool": "formal_accuse",
            "person_id": scenario.culprit_person,
            "event_claims": [
                {
                    "event_id": event.entry_id,
                    "time": event.time,
                    "location": event.location,
                    "duty_code": event.duty_code,
                }
                for event in scenario.truth_events
            ],
            "cited_entry_ids": list(scenario.required_entry_ids),
        }
    )
    return actions


__all__ = [
    "COURTROOM",
    "EDGES",
    "Event30",
    "Map30V10Environment",
    "SCENARIOS",
    "Scenario30",
    "WINDOW",
    "oracle_actions",
]
