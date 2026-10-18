"""MAP-28 V10｜消失的王冠：多样本案卷、公开枚举与可区分失败码（DCR-V10-06）。

与 V8 的差异：

- 4 个预登记案卷种子，**真值人物、跨入路径、时间与证据依赖图都不同**（不是只换名字）：
  seed 0 复刻 V8 原案；seed 1 证词误记人物；seed 2 仪器日志缺失一侧出口记录，
  出口时刻只能由物证 + 诚实证词两类来源支持；seed 3 证词误记路径（把 H 记成 G）；
- 公开 `PERSONS` / `ENTRY_PATHS` 合法**枚举**，不再靠盲试；公开“每个字段至少两种
  不同来源类别”“引用必须是已 `record` 的证据”“提交一次终局”等规则；
- 失败码可区分三种误判：`EVIDENCE_MISSING`（引用了未记录/未观察的证据）、
  `CLAIM_CONTRADICTS_RECORDED_EVIDENCE`（误记）、`ACCUSATION_WITHOUT_TWO_SOURCES`
  （值可能对但来源类别 <2）；终局拒绝统一为 `CASE_REJECTED`（truth-neutral）；
- 指标拆开“过程量”与“提交质量”：`record_coverage` 是过程量（截尾仍 VALID），
  `timeline_constraint_satisfaction` 只在**真的提交过**时有分母，未提交区分
  NOT_APPLICABLE（终局失败）与 CENSORED（截尾）——不再把所有 0/4 混为一谈。
"""

from __future__ import annotations

import re
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

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CLAIM_FIELDS = ("person_id", "entry_path_id", "entry_time", "exit_time")
EDGES = {
    "H_V": ("H", "V"),
    "V_G": ("V", "G"),
    "G_K": ("G", "K"),
    "K_S": ("K", "S"),
    "S_V": ("S", "V"),
    "A_G": ("A", "G"),
}


def _ev(
    source: str, location: str, source_class: str, fact: str, **claims: Any
) -> dict[str, Any]:
    return {
        "source": source,
        "location": location,
        "source_class": source_class,
        "fact": fact,
        "claims": claims,
    }


@dataclass(frozen=True)
class Case28:
    label: str
    truth: dict[str, str]
    persons: tuple[str, ...]
    paths: tuple[str, ...]
    evidence: dict[str, dict[str, Any]]
    sources: dict[str, tuple[str, ...]]
    key_evidence: tuple[str, ...]
    note: str


CASES: dict[int, Case28] = {
    0: Case28(
        label="instrument_first_misremembered_person",
        truth={
            "person_id": "CELINE",
            "entry_path_id": "SECRET_S_V",
            "entry_time": "21:06",
            "exit_time": "21:14",
        },
        persons=("ADA", "BASIL", "CELINE"),
        paths=("BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"),
        evidence={
            "LOCK_ENTRY_K3_2106": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "K3 于 21:06 从 S 侧开启 V 锁舌",
                person_id=("eq", "CELINE"),
                entry_path_id=("eq", "SECRET_S_V"),
                entry_time=("eq", "21:06"),
            ),
            "LOCK_EXIT_S_2114": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "21:14 从 S 侧退出并关闭 V 锁舌",
                entry_path_id=("eq", "SECRET_S_V"),
                exit_time=("eq", "21:14"),
            ),
            "PRINT_C7_ROUTE_SV": _ev(
                "footprint_trail",
                "S",
                "physical_trace",
                "C7 靴纹匹配 Celine；连续 S-V 方向痕迹；进入 21:05-21:07、离开 21:13-21:15",
                person_id=("eq", "CELINE"),
                entry_path_id=("eq", "SECRET_S_V"),
                entry_time=("window", "21:05", "21:07"),
                exit_time=("window", "21:13", "21:15"),
            ),
            "KEY_REGISTER_K3_CELINE": _ev(
                "key_registry",
                "A",
                "documentary_register",
                "K3 于 20:58 登记给 Celine，案发时段无转交",
                person_id=("eq", "CELINE"),
            ),
            "WITNESS_BASIL_S_WINDOW": _ev(
                "kitchen_cook",
                "K",
                "testimony",
                "厨师猜测是 Basil；描述 S 路径与 21:05-21:07 / 21:13-21:15 时间窗",
                entry_path_id=("eq", "SECRET_S_V"),
                entry_time=("window", "21:05", "21:07"),
                exit_time=("window", "21:13", "21:15"),
            ),
        },
        sources={
            "vault_lock_events": ("LOCK_ENTRY_K3_2106", "LOCK_EXIT_S_2114"),
            "footprint_trail": ("PRINT_C7_ROUTE_SV",),
            "key_registry": ("KEY_REGISTER_K3_CELINE",),
            "kitchen_cook": ("WITNESS_BASIL_S_WINDOW",),
        },
        key_evidence=(
            "KEY_REGISTER_K3_CELINE",
            "LOCK_ENTRY_K3_2106",
            "PRINT_C7_ROUTE_SV",
            "WITNESS_BASIL_S_WINDOW",
        ),
        note="V8 原案：证词误记人物，但路径与时间窗有效。",
    ),
    1: Case28(
        label="guard_path_misremembered_person",
        truth={
            "person_id": "BASIL",
            "entry_path_id": "GUARD_G_V",
            "entry_time": "22:31",
            "exit_time": "22:47",
        },
        persons=("ADA", "BASIL", "CELINE"),
        paths=("BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"),
        evidence={
            "LOCK_ENTRY_G4_2231": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "G4 于 22:31 从 G 侧开启 V 锁舌",
                person_id=("eq", "BASIL"),
                entry_path_id=("eq", "GUARD_G_V"),
                entry_time=("eq", "22:31"),
            ),
            "LOCK_EXIT_G_2247": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "22:47 从 G 侧退出并关闭 V 锁舌",
                entry_path_id=("eq", "GUARD_G_V"),
                exit_time=("eq", "22:47"),
            ),
            "PRINT_D2_ROUTE_GV": _ev(
                "footprint_trail",
                "S",
                "physical_trace",
                "D2 靴纹匹配 Basil；连续 G-V 方向痕迹；进入 22:30-22:32、离开 22:46-22:48",
                person_id=("eq", "BASIL"),
                entry_path_id=("eq", "GUARD_G_V"),
                entry_time=("window", "22:30", "22:32"),
                exit_time=("window", "22:46", "22:48"),
            ),
            "KEY_REGISTER_G4_BASIL": _ev(
                "key_registry",
                "A",
                "documentary_register",
                "G4 于 22:20 登记给 Basil，案发时段无转交",
                person_id=("eq", "BASIL"),
            ),
            "WITNESS_CELINE_G_WINDOW": _ev(
                "kitchen_cook",
                "K",
                "testimony",
                "厨房管事猜测是 Celine；描述 G 路径与 22:30-22:32 / 22:46-22:48 时间窗",
                entry_path_id=("eq", "GUARD_G_V"),
                entry_time=("window", "22:30", "22:32"),
                exit_time=("window", "22:46", "22:48"),
            ),
        },
        sources={
            "vault_lock_events": ("LOCK_ENTRY_G4_2231", "LOCK_EXIT_G_2247"),
            "footprint_trail": ("PRINT_D2_ROUTE_GV",),
            "key_registry": ("KEY_REGISTER_G4_BASIL",),
            "kitchen_cook": ("WITNESS_CELINE_G_WINDOW",),
        },
        key_evidence=(
            "KEY_REGISTER_G4_BASIL",
            "LOCK_ENTRY_G4_2231",
            "PRINT_D2_ROUTE_GV",
            "WITNESS_CELINE_G_WINDOW",
        ),
        note="证词把人物误记为 Celine；G 侧路径与时间窗仍有效。",
    ),
    2: Case28(
        label="missing_exit_log_honest_witness",
        truth={
            "person_id": "ADA",
            "entry_path_id": "BANQUET_H_V",
            "entry_time": "23:12",
            "exit_time": "23:26",
        },
        persons=("ADA", "BASIL", "CELINE"),
        paths=("BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"),
        evidence={
            "LOCK_ENTRY_H5_2312": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "H5 于 23:12 从 H 侧开启 V 锁舌（出口侧日志缺失）",
                person_id=("eq", "ADA"),
                entry_path_id=("eq", "BANQUET_H_V"),
                entry_time=("eq", "23:12"),
            ),
            "PRINT_A9_ROUTE_HV": _ev(
                "footprint_trail",
                "S",
                "physical_trace",
                "A9 靴纹匹配 Ada；连续 H-V 方向痕迹；进入 23:11-23:13、离开 23:25-23:27",
                person_id=("eq", "ADA"),
                entry_path_id=("eq", "BANQUET_H_V"),
                entry_time=("window", "23:11", "23:13"),
                exit_time=("window", "23:25", "23:27"),
            ),
            "KEY_REGISTER_H5_ADA": _ev(
                "key_registry",
                "A",
                "documentary_register",
                "H5 于 23:01 登记给 Ada，案发时段无转交",
                person_id=("eq", "ADA"),
            ),
            "WITNESS_ADA_H_WINDOW": _ev(
                "kitchen_cook",
                "K",
                "testimony",
                "厨房管事如实回忆 Ada 从 H 侧进入，并给出 23:11-23:13 / 23:25-23:27 时间窗",
                entry_path_id=("eq", "BANQUET_H_V"),
                entry_time=("window", "23:11", "23:13"),
                exit_time=("window", "23:25", "23:27"),
            ),
        },
        sources={
            "vault_lock_events": ("LOCK_ENTRY_H5_2312",),
            "footprint_trail": ("PRINT_A9_ROUTE_HV",),
            "key_registry": ("KEY_REGISTER_H5_ADA",),
            "kitchen_cook": ("WITNESS_ADA_H_WINDOW",),
        },
        key_evidence=(
            "KEY_REGISTER_H5_ADA",
            "LOCK_ENTRY_H5_2312",
            "PRINT_A9_ROUTE_HV",
            "WITNESS_ADA_H_WINDOW",
        ),
        note="仪器日志缺出口侧：离开时刻只能由物证 + 诚实证词交叉支持。",
    ),
    3: Case28(
        label="misremembered_path_trap",
        truth={
            "person_id": "CELINE",
            "entry_path_id": "BANQUET_H_V",
            "entry_time": "20:44",
            "exit_time": "21:02",
        },
        persons=("ADA", "BASIL", "CELINE"),
        paths=("BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"),
        evidence={
            "LOCK_ENTRY_H5_2044": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "H5 于 20:44 从 H 侧开启 V 锁舌",
                person_id=("eq", "CELINE"),
                entry_path_id=("eq", "BANQUET_H_V"),
                entry_time=("eq", "20:44"),
            ),
            "LOCK_EXIT_H_2102": _ev(
                "vault_lock_events",
                "V",
                "instrument_log",
                "21:02 从 H 侧退出并关闭 V 锁舌",
                entry_path_id=("eq", "BANQUET_H_V"),
                exit_time=("eq", "21:02"),
            ),
            "PRINT_C3_ROUTE_HV": _ev(
                "footprint_trail",
                "S",
                "physical_trace",
                "C3 靴纹匹配 Celine；连续 H-V 方向痕迹；进入 20:43-20:45、离开 21:01-21:03",
                person_id=("eq", "CELINE"),
                entry_path_id=("eq", "BANQUET_H_V"),
                entry_time=("window", "20:43", "20:45"),
                exit_time=("window", "21:01", "21:03"),
            ),
            "KEY_REGISTER_H5_CELINE": _ev(
                "key_registry",
                "A",
                "documentary_register",
                "H5 于 20:35 登记给 Celine，案发时段无转交",
                person_id=("eq", "CELINE"),
            ),
            "WITNESS_BASIL_G_WINDOW": _ev(
                "kitchen_cook",
                "K",
                "testimony",
                "厨房管事猜测是 Basil，并把路径误记为 G 侧；时间窗 20:43-20:45 / 21:01-21:03",
                entry_path_id=("eq", "GUARD_G_V"),
                entry_time=("window", "20:43", "20:45"),
                exit_time=("window", "21:01", "21:03"),
            ),
        },
        sources={
            "vault_lock_events": ("LOCK_ENTRY_H5_2044", "LOCK_EXIT_H_2102"),
            "footprint_trail": ("PRINT_C3_ROUTE_HV",),
            "key_registry": ("KEY_REGISTER_H5_CELINE",),
            "kitchen_cook": ("WITNESS_BASIL_G_WINDOW",),
        },
        key_evidence=(
            "KEY_REGISTER_H5_CELINE",
            "LOCK_ENTRY_H5_2044",
            "PRINT_C3_ROUTE_HV",
            "WITNESS_BASIL_G_WINDOW",
        ),
        note="证词误记路径（H→G）：引用它支持路径会与已记录证据矛盾。",
    ),
}


class Map28V10Environment(V10Map):
    map_id = "MAP-28"
    title = "消失的王冠"
    world = "castle"
    level = "简单"
    RULE_VERSION = "v10.map28.1"
    SEED_SPACE = tuple(sorted(CASES))
    EDGES = EDGES
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "investigate": {frozenset({"tool", "target_id"})},
        "read_record": {frozenset({"tool", "record_id"})},
        "interview": {frozenset({"tool", "witness_id"})},
        "record": {frozenset({"tool", "clue_id"})},
        "submit": {frozenset({"tool", "claims", "citations_by_claim"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "local_neighbors",
            "visible_edges",
            "tick",
            "observed_evidence",
            "recorded_evidence_ids",
            "persons",
            "entry_paths",
            "required_key_evidence",
            "case_label",
            "goal",
        }
    )
    PRIMARY_METRIC = "map28.v10.timeline_constraint_satisfaction"
    METRIC_SPECS = (
        MetricSpec(
            "map28.v10.timeline_constraint_satisfaction",
            "primary",
            "higher",
            "值等于真值且引用 ≥2 个不同来源类别的字段数 / 4",
            "已提交的局（1）",
            zero_denominator="未提交 → NOT_APPLICABLE（截尾 → CENSORED）",
        ),
        MetricSpec(
            "map28.v10.record_coverage",
            "secondary",
            "higher",
            "已 record 的关键证据数 / 4（过程量，截尾仍 VALID）",
            "4",
        ),
        MetricSpec(
            "map28.v10.submission_attempted",
            "diagnostic",
            "none",
            "是否发生过 submit",
            "1",
            unit="count",
            valid_range=(0.0, 1.0),
        ),
        MetricSpec(
            "map28.v10.unsupported_accusations",
            "guardrail",
            "lower",
            "提交时任一字段来源类别 <2",
            "1",
        ),
        MetricSpec(
            "map28.v10.time_contradictions",
            "guardrail",
            "lower",
            "被已记录证据排除的时间字段数 + 时序矛盾",
            "—",
            unit="count",
            valid_range=(0.0, 4.0),
        ),
        MetricSpec(
            "map28.v10.missing_evidence_citations",
            "diagnostic",
            "lower",
            "提交引用中未记录/未观察的证据数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.case = CASES[seed]
        self.node = "H"
        self.items = []
        self.observed_ids: list[str] = []
        self.recorded_ids: list[str] = []
        self.submitted = False
        self.satisfied_fields = 0
        self.contradictions = 0
        self.unsupported_accusations = 0
        self.missing_citations = 0
        self.verdict: str | None = None
        self.judge_reason: str | None = None
        self._pending_cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "case_label": self.case.label,
            "persons": list(self.case.persons),
            "entry_paths": list(self.case.paths),
            "required_key_evidence": list(self.case.key_evidence),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"label": self.case.label, "truth": dict(self.case.truth)}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "六室环路 H—V—G—K—S—V 加 A—G 档案支线；move(to) 沿公共边移动，1 tick。",
            "取证动作：investigate(vault_lock_events)（V）、investigate(footprint_trail)（S）、"
            "read_record(key_registry)（A）、interview(kitchen_cook)（K）。",
            "record(clue_id) 只能记录**已观察**的具体证据 ID；观察过但没记录的证据不能作为来源。",
            "submit 一次终局：claims 四个字段 person_id / entry_path_id / entry_time / exit_time，"
            "citations_by_claim 为每个字段的已记录证据 ID 列表。",
            f"person_id 合法值仅：{', '.join(self.case.persons)}；"
            f"entry_path_id 合法值仅：{', '.join(self.case.paths)}；时间格式 HH:MM。",
            "每个字段必须由**至少两种不同来源类别**（instrument_log / physical_trace / "
            "documentary_register / testimony）支持，且值必须正确。",
            "失败码：引用未记录/未观察的证据 → EVIDENCE_MISSING；值被已记录证据排除 → "
            "CLAIM_CONTRADICTS_RECORDED_EVIDENCE；值可能正确但来源类别 <2 → "
            "ACCUSATION_WITHOUT_TWO_SOURCES；终局拒绝统一为 CASE_REJECTED。",
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
            "observed_evidence": [
                {
                    "evidence_id": evidence_id,
                    "fact": self.case.evidence[evidence_id]["fact"],
                    "source_class": self.case.evidence[evidence_id]["source_class"],
                }
                for evidence_id in self.observed_ids
            ],
            "recorded_evidence_ids": list(self.recorded_ids),
            "persons": list(self.case.persons),
            "entry_paths": list(self.case.paths),
            "required_key_evidence": list(self.case.key_evidence),
            "case_label": self.case.label,
            "goal": (
                "在 H 提交人物、跨入宝库的门、进入分钟与离开分钟；每个字段至少引用两种不同"
                "来源类别，且值必须正确。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._pending_cost = 1
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "investigate":
            return self._investigate(action)
        if tool == "read_record":
            return self._read_record(action)
        if tool == "interview":
            return self._interview(action)
        if tool == "record":
            return self._record(action)
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

    def _reveal(self, source: str) -> tuple[str, ...]:
        revealed = self.case.sources[source]
        for evidence_id in revealed:
            if evidence_id not in self.observed_ids:
                self.observed_ids.append(evidence_id)
        return revealed

    def _investigate(self, action: V8Action) -> str:
        target = action.target_id
        if target not in ("vault_lock_events", "footprint_trail"):
            return "TARGET_NOT_VISIBLE"
        revealed = self.case.sources[target]
        if self.node != self.case.evidence[revealed[0]]["location"]:
            return "TARGET_NOT_VISIBLE"
        self._reveal(target)
        if target == "vault_lock_events":
            return "LOCK_EVIDENCE_FOUND"
        return "FOOTPRINT_EVIDENCE_FOUND"

    def _read_record(self, action: V8Action) -> str:
        if action.record_id != "key_registry" or self.node != "A":
            return "TARGET_NOT_VISIBLE"
        self._reveal("key_registry")
        return "REGISTER_READ"

    def _interview(self, action: V8Action) -> str:
        if action.witness_id != "kitchen_cook" or self.node != "K":
            return "TARGET_NOT_VISIBLE"
        self._reveal("kitchen_cook")
        return "WITNESS_INTERVIEWED"

    def _record(self, action: V8Action) -> str:
        evidence_id = action.clue_id
        if evidence_id not in self.case.evidence:
            self._pending_cost = 0
            return "INVALID_EVIDENCE_ID"
        if evidence_id not in self.observed_ids:
            self._pending_cost = 0
            return "EVIDENCE_NOT_OBSERVED"
        if evidence_id in self.recorded_ids:
            return "EVIDENCE_ALREADY_RECORDED"
        self.recorded_ids.append(evidence_id)
        return "EVIDENCE_RECORDED"

    # ------------------------------------------------------------------ submit
    def _parse_claims(self, action: V8Action) -> tuple[dict[str, str], dict[str, list[str]]] | str:
        rows = action.claims or []
        claims: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                return "INVALID_CLAIM_PAYLOAD"
            claim_id = row.get("claim_id")
            value = row.get("value")
            if claim_id not in CLAIM_FIELDS or not isinstance(value, str):
                return "INVALID_CLAIM_PAYLOAD"
            claims[claim_id] = value
        if set(claims) != set(CLAIM_FIELDS):
            return "INVALID_CLAIM_PAYLOAD"
        if (
            claims["person_id"] not in self.case.persons
            or claims["entry_path_id"] not in self.case.paths
        ):
            return "INVALID_ACTION_ENUM"
        if not _TIME.match(claims["entry_time"]) or not _TIME.match(claims["exit_time"]):
            return "INVALID_ACTION_ENUM"
        citations: dict[str, list[str]] = {}
        raw = action.citations_by_claim or {}
        for field in CLAIM_FIELDS:
            cited = raw.get(field, [])
            if isinstance(cited, str) or not isinstance(cited, list):
                return "INVALID_CLAIM_PAYLOAD"
            if any(not isinstance(evidence_id, str) for evidence_id in cited):
                return "INVALID_CLAIM_PAYLOAD"
            citations[field] = list(cited)
        return claims, citations

    def _satisfies(self, constraint: tuple[Any, ...], value: str) -> bool:
        if constraint[0] == "eq":
            return bool(value == constraint[1])
        return bool(constraint[1] <= value <= constraint[2])

    def _classes_for(
        self, field: str, value: str, cited: list[str]
    ) -> tuple[set[str], bool, bool]:
        """返回（支持来源类别，被**引用**证据否决，被任何已记录证据否决）。"""

        classes: set[str] = set()
        cited_contradicted = False
        any_contradicted = False
        recorded = set(self.recorded_ids)
        for evidence_id in cited:
            evidence = self.case.evidence.get(evidence_id)
            if evidence is None or evidence_id not in recorded:
                continue
            constraint = evidence["claims"].get(field)
            if constraint is None:
                continue
            if not self._satisfies(constraint, value):
                cited_contradicted = True
                continue
            classes.add(evidence["source_class"])
        for evidence_id in self.recorded_ids:
            constraint = self.case.evidence[evidence_id]["claims"].get(field)
            if constraint is not None and not self._satisfies(constraint, value):
                any_contradicted = True
        return classes, cited_contradicted, any_contradicted

    def _submit(self, action: V8Action) -> str:
        if self.node != "H":
            return "INVALID_LOCATION"
        parsed = self._parse_claims(action)
        if isinstance(parsed, str):
            self._pending_cost = 0
            return parsed
        claims, citations = parsed

        satisfied = 0
        unsupported_fields: list[str] = []
        contradictions = 0
        cited_contradiction = False
        missing = 0
        known = set(self.observed_ids)
        for field in CLAIM_FIELDS:
            for evidence_id in citations[field]:
                if evidence_id not in known or evidence_id not in self.recorded_ids:
                    missing += 1
            value = claims[field]
            classes, cited_contradicted, any_contradicted = self._classes_for(
                field, value, citations[field]
            )
            if cited_contradicted:
                cited_contradiction = True
            if field in ("entry_time", "exit_time") and any_contradicted:
                contradictions += 1
            if len(classes) < 2 or cited_contradicted:
                unsupported_fields.append(field)
            if value == self.case.truth[field] and len(classes) >= 2 and not cited_contradicted:
                satisfied += 1
        if claims["entry_time"] >= claims["exit_time"]:
            contradictions += 1

        self.submitted = True
        self.satisfied_fields = satisfied
        self.contradictions = contradictions
        self.unsupported_accusations = 1 if unsupported_fields else 0
        self.missing_citations = missing
        self._pending_cost = 1

        if not unsupported_fields and satisfied == len(CLAIM_FIELDS):
            self.verdict = "ALL_CLAIMS_SUPPORTED_AND_CORRECT"
            self._succeed(self.verdict)
            return self.verdict
        self.verdict = "CASE_REJECTED"
        if missing:
            self.judge_reason = "EVIDENCE_MISSING"
            self._violate("EVIDENCE_MISSING")
            result_code = "EVIDENCE_MISSING"
        elif cited_contradiction:
            self.judge_reason = "CLAIM_CONTRADICTS_RECORDED_EVIDENCE"
            self._violate("CLAIM_CONTRADICTS_RECORDED_EVIDENCE")
            result_code = "CLAIM_CONTRADICTS_RECORDED_EVIDENCE"
        else:
            self.judge_reason = "UNSUPPORTED_OR_INCOMPLETE"
            self._violate("ACCUSATION_WITHOUT_TWO_SOURCES")
            result_code = "ACCUSATION_WITHOUT_TWO_SOURCES"
        self._fail(self.verdict)
        return result_code

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._pending_cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "case_label": self.case.label,
            "location": self.node,
            "observed_evidence_ids": list(self.observed_ids),
            "recorded_evidence_ids": list(self.recorded_ids),
            "submitted": self.submitted,
            "satisfied_fields": self.satisfied_fields,
            "time_contradictions": self.contradictions,
            "unsupported_accusations": self.unsupported_accusations,
            "missing_citations": self.missing_citations,
            "judge_reason": self.judge_reason,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        covered = sum(1 for item in self.case.key_evidence if item in self.recorded_ids)
        if self.submitted:
            score: MValue = ratio(self.satisfied_fields, len(CLAIM_FIELDS))
        elif self.status.value == "step_limit_reached":
            score = censored("未提交即截尾")
        else:
            score = not_applicable("终局失败且未提交")
        return {
            "map28.v10.timeline_constraint_satisfaction": score,
            "map28.v10.record_coverage": ratio(covered, len(self.case.key_evidence)),
            "map28.v10.submission_attempted": valid(int(self.submitted)),
            "map28.v10.unsupported_accusations": valid(self.unsupported_accusations),
            "map28.v10.time_contradictions": valid(self.contradictions),
            "map28.v10.missing_evidence_citations": valid(self.missing_citations),
        }

    def mechanism_triggered(self) -> bool:
        """本局核心机制被真实触发：至少记录过一件关键证据并提交过。"""

        return self.submitted and bool(set(self.recorded_ids) & set(self.case.key_evidence))


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知路线：走完四类来源、逐条 record、回 H 提交双来源引用。"""

    case = CASES[environment_seed]
    environment = Map28V10Environment(seed=environment_seed)
    actions: list[dict[str, Any]] = []

    def step(payload: dict[str, Any]) -> None:
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))

    def walk(destination: str) -> None:
        while environment.node != destination:
            next_hop = _route(environment.node, destination)[1]
            step({"tool": "move", "to": next_hop})

    step({"tool": "move", "to": "V"})
    step({"tool": "investigate", "target_id": "vault_lock_events"})
    walk("S")
    step({"tool": "investigate", "target_id": "footprint_trail"})
    walk("K")
    step({"tool": "interview", "witness_id": "kitchen_cook"})
    walk("A")
    step({"tool": "read_record", "record_id": "key_registry"})
    for evidence_id in sorted(environment.observed_ids):
        if evidence_id in case.evidence and evidence_id not in environment.recorded_ids:
            step({"tool": "record", "clue_id": evidence_id})
    walk("H")

    citations: dict[str, list[str]] = {}
    for field in CLAIM_FIELDS:
        support: list[str] = []
        for evidence_id in environment.recorded_ids:
            constraint = case.evidence[evidence_id]["claims"].get(field)
            if constraint is None:
                continue
            if environment._satisfies(constraint, case.truth[field]):
                support.append(evidence_id)
            if len({case.evidence[item]["source_class"] for item in support}) >= 2:
                break
        citations[field] = support
    step(
        {
            "tool": "submit",
            "claims": [{"claim_id": field, "value": case.truth[field]} for field in CLAIM_FIELDS],
            "citations_by_claim": citations,
        }
    )
    return actions


ADJACENCY: dict[str, tuple[str, ...]] = {
    "H": ("V",),
    "V": ("H", "G", "S"),
    "G": ("V", "K", "A"),
    "K": ("G", "S"),
    "S": ("K", "V"),
    "A": ("G",),
}


def _route(start: str, destination: str) -> list[str]:
    """BFS 最短节点路径；`oracle_actions` 用它逐跳移动。"""

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


__all__ = ["CASES", "CLAIM_FIELDS", "Case28", "Map28V10Environment", "oracle_actions"]
