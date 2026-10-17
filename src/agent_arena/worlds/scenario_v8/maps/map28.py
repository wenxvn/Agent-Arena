"""MAP-28｜消失的王冠：四字段双来源交叉的证据时间线重建。

本图与同世界另两图的机制差异：MAP-29 的证词**不可靠且有植入矛盾**，核心是分诊
（判断谁记错、谁说谎、谁只是不知道）；MAP-30 有长间隔召回与多事件案卷。本图只有
一条短证据链和一处人名误认，难点在**每个正式主张都必须由至少两种不同来源类别
交叉支持**，并把“猜中真相”与“证明真相”分开：即使四个字段值全对，只要某一栏只
引用单一来源类别，提交仍被拒绝。

地形与真相（裁判侧）：``H—V—G—K—S—V`` 环路加 ``A—G`` 档案支线。唯一真相是
Celine 于 21:06 从 ``S-V`` 密道门进入、21:14 从同一门离开。V 有三个真实入口：
``BANQUET_H_V``、``GUARD_G_V``、``SECRET_S_V``，路径枚举严格匹配，不接受近义词。

四类来源：仪器锁芯日志（V 调查）、物证脚印（S 调查）、档案钥匙登记（A 阅读）、
厨房目击（K 访谈）。厨师把深色衣服误认成 Basil，但目击对**路径与时间窗**仍是
有效来源；它不能单独支持任何人名。

动作契约：
- ``move(to)``：沿六室边移动，1 tick。
- ``investigate(target_id)``：``vault_lock_events``（V）或 ``footprint_trail``（S）。
- ``read_record(record_id)``：``key_registry``（A）。
- ``interview(witness_id)``：``kitchen_cook``（K）。
- ``record(clue_id)``：只能记录**已观察**的具体证据 ID（V8Action 的单值字段名是
  ``clue_id``），不创建也不改写证据。
- ``submit(claims, citations_by_claim)``：``claims`` 是
  ``[{"claim_id": ..., "value": ...}]``，四个 claim_id 为 ``person_id`` /
  ``entry_path_id`` / ``entry_time`` / ``exit_time``；``citations_by_claim`` 是
  ``{claim_id: [evidence_id, ...]}``。一次提交终局，拒绝不泄漏正确答案，也不给重试。

失败码：``CASE_REJECTED``（终局拒绝的 terminal_reason，truth-neutral）、
``ACCUSATION_WITHOUT_TWO_SOURCES``（提交动作结果：任一字段的支持来源类别少于 2，
同时写入违规账）、``CLAIM_CONTRADICTS_RECORDED_EVIDENCE`` 造成的拒绝仍以
``CASE_REJECTED`` 作为动作结果、``EVIDENCE_NOT_OBSERVED``、``INVALID_EVIDENCE_ID``、
``TARGET_NOT_VISIBLE``、``EDGE_NOT_ADJACENT``、``INVALID_ACTION_ENUM``（路径/人物/
时间格式非法，0 tick，不消耗唯一提交）、``EVIDENCE_ALREADY_RECORDED``。

指标口径（与 ``docs/v7/maps/MAP-28.md`` 一致）：
- ``map28.timeline_constraint_satisfaction``：同时满足“值等于真相 + 至少 2 个不同
  来源类别”的字段数 / 4；未提交 → 0/4。
- ``map28.key_evidence_coverage``：已记录的关键证据数 / 4（K3 登记、K3 锁日志、
  C7 脚印、厨师证词）；未调查 → 0，合法。
- ``map28.unsupported_accusations``：提交时任一字段无两类来源记 1，否则 0；单次提交
  至多 1。
- ``map28.time_contradictions``：被**已记录**证据排除的提交时间字段数（entry/exit
  分别计数）；另加“进入时刻不早于离开时刻”的时序矛盾计数。
"""

from __future__ import annotations

import re
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

#: 证据 ID → 来源类别、披露位置与它对每个主张字段给出的约束。
#: ``("eq", value)`` 表示该来源精确锁定这个值；``("window", lo, hi)`` 表示时间窗。
EVIDENCE: dict[str, dict[str, Any]] = {
    "LOCK_ENTRY_K3_2106": {
        "source": "vault_lock_events",
        "location": "V",
        "source_class": "instrument_log",
        "fact": "K3 于 21:06 从 S 侧开启 V 锁舌",
        "claims": {
            "person_id": ("eq", "CELINE"),
            "entry_path_id": ("eq", "SECRET_S_V"),
            "entry_time": ("eq", "21:06"),
        },
    },
    "LOCK_EXIT_S_2114": {
        "source": "vault_lock_events",
        "location": "V",
        "source_class": "instrument_log",
        "fact": "21:14 从 S 侧退出并关闭 V 锁舌",
        "claims": {
            "entry_path_id": ("eq", "SECRET_S_V"),
            "exit_time": ("eq", "21:14"),
        },
    },
    "PRINT_C7_ROUTE_SV": {
        "source": "footprint_trail",
        "location": "S",
        "source_class": "physical_trace",
        "fact": "C7 靴纹匹配 Celine；连续 S-V 方向痕迹；进入 21:05-21:07、离开 21:13-21:15",
        "claims": {
            "person_id": ("eq", "CELINE"),
            "entry_path_id": ("eq", "SECRET_S_V"),
            "entry_time": ("window", "21:05", "21:07"),
            "exit_time": ("window", "21:13", "21:15"),
        },
    },
    "KEY_REGISTER_K3_CELINE": {
        "source": "key_registry",
        "location": "A",
        "source_class": "documentary_register",
        "fact": "K3 于 20:58 登记给 Celine，案发时段无转交",
        "claims": {"person_id": ("eq", "CELINE")},
    },
    "WITNESS_BASIL_S_WINDOW": {
        "source": "kitchen_cook",
        "location": "K",
        "source_class": "testimony",
        "fact": "厨师猜测是 Basil；描述 S 路径和 21:05-21:07 / 21:13-21:15 时间窗",
        "claims": {
            "entry_path_id": ("eq", "SECRET_S_V"),
            "entry_time": ("window", "21:05", "21:07"),
            "exit_time": ("window", "21:13", "21:15"),
        },
    },
}

_SOURCE_REVEALS = {
    "vault_lock_events": ("LOCK_ENTRY_K3_2106", "LOCK_EXIT_S_2114"),
    "footprint_trail": ("PRINT_C7_ROUTE_SV",),
    "key_registry": ("KEY_REGISTER_K3_CELINE",),
    "kitchen_cook": ("WITNESS_BASIL_S_WINDOW",),
}

TRUTH = {
    "person_id": "CELINE",
    "entry_path_id": "SECRET_S_V",
    "entry_time": "21:06",
    "exit_time": "21:14",
}
CLAIM_FIELDS = ("person_id", "entry_path_id", "entry_time", "exit_time")
PERSONS = frozenset({"ADA", "BASIL", "CELINE"})
ENTRY_PATHS = frozenset({"BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"})
KEY_EVIDENCE = (
    "KEY_REGISTER_K3_CELINE",
    "LOCK_ENTRY_K3_2106",
    "PRINT_C7_ROUTE_SV",
    "WITNESS_BASIL_S_WINDOW",
)


def _satisfies(constraint: tuple[str, ...], value: str) -> bool:
    if constraint[0] == "eq":
        return value == constraint[1]
    return constraint[1] <= value <= constraint[2]


class Map28Environment(MapEnvironment):
    map_id = "MAP-28"
    title = "消失的王冠"
    world = "castle"
    level = "简单"
    EDGES = {
        "H_V": ("H", "V"),
        "V_G": ("V", "G"),
        "G_K": ("G", "K"),
        "K_S": ("K", "S"),
        "S_V": ("S", "V"),
        "A_G": ("A", "G"),
    }
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
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "H"
        self.items = []
        self.observed_ids: list[str] = []
        self.recorded_ids: list[str] = []
        self.submitted = False
        self.satisfied_fields = 0
        self.contradictions = 0
        self.unsupported_accusations = 0
        self.verdict: str | None = None
        self.judge_reason: str | None = None
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
            "observed_evidence": [
                {
                    "evidence_id": evidence_id,
                    "fact": EVIDENCE[evidence_id]["fact"],
                    "source_class": EVIDENCE[evidence_id]["source_class"],
                }
                for evidence_id in self.observed_ids
            ],
            "recorded_evidence_ids": list(self.recorded_ids),
            "goal": (
                "在 H 提交人物、跨入宝库的门、进入分钟与离开分钟；每个字段至少引用"
                "两种不同来源类别，且值必须正确。"
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
        revealed = _SOURCE_REVEALS[source]
        for evidence_id in revealed:
            if evidence_id not in self.observed_ids:
                self.observed_ids.append(evidence_id)
        return revealed

    def _investigate(self, action: V8Action) -> str:
        target = action.target_id
        if target not in ("vault_lock_events", "footprint_trail"):
            return "TARGET_NOT_VISIBLE"
        if self.node != EVIDENCE[next(iter(_SOURCE_REVEALS[target]))]["location"]:
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
        if evidence_id not in EVIDENCE:
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
    def _parse_claims(
        self, action: V8Action
    ) -> tuple[dict[str, str], dict[str, list[str]]] | str:
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
        if claims["person_id"] not in PERSONS or claims["entry_path_id"] not in ENTRY_PATHS:
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

    def _classes_for(
        self, field: str, value: str, cited: list[str]
    ) -> tuple[set[str], bool]:
        """Return supporting source classes and whether recorded evidence excludes it."""

        classes: set[str] = set()
        contradicted = False
        recorded = set(self.recorded_ids)
        for evidence_id in cited:
            evidence = EVIDENCE.get(evidence_id)
            if evidence is None or evidence_id not in recorded:
                continue
            constraint = evidence["claims"].get(field)
            if constraint is None:
                continue
            if not _satisfies(constraint, value):
                contradicted = True
                continue
            classes.add(evidence["source_class"])
        for evidence_id in self.recorded_ids:
            constraint = EVIDENCE[evidence_id]["claims"].get(field)
            if constraint is not None and not _satisfies(constraint, value):
                contradicted = True
        return classes, contradicted

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
        hard_contradiction = False
        for field in CLAIM_FIELDS:
            value = claims[field]
            classes, contradicted = self._classes_for(field, value, citations[field])
            if contradicted and field in ("person_id", "entry_path_id"):
                hard_contradiction = True
            if field in ("entry_time", "exit_time") and contradicted:
                contradictions += 1
            if len(classes) < 2:
                unsupported_fields.append(field)
            if value == TRUTH[field] and len(classes) >= 2:
                satisfied += 1
        if claims["entry_time"] >= claims["exit_time"]:
            contradictions += 1

        self.submitted = True
        self.satisfied_fields = satisfied
        self.contradictions = contradictions
        self.unsupported_accusations = 1 if unsupported_fields else 0
        self._pending_cost = 1

        if not unsupported_fields and satisfied == len(CLAIM_FIELDS):
            self.verdict = "ALL_CLAIMS_SUPPORTED_AND_CORRECT"
            self._succeed(self.verdict)
            return self.verdict
        self.verdict = "CASE_REJECTED"
        self._pending_cost = 1
        if contradictions or hard_contradiction:
            self.judge_reason = "CLAIM_CONTRADICTS_RECORDED_EVIDENCE"
            self._violate("CLAIM_CONTRADICTS_RECORDED_EVIDENCE")
            result_code = "CASE_REJECTED"
        else:
            self.judge_reason = "INSUFFICIENT_INDEPENDENT_SUPPORT"
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
            "location": self.node,
            "observed_evidence_ids": list(self.observed_ids),
            "recorded_evidence_ids": list(self.recorded_ids),
            "submitted": self.submitted,
            "satisfied_fields": self.satisfied_fields,
            "time_contradictions": self.contradictions,
            "unsupported_accusations": self.unsupported_accusations,
            "judge_reason": self.judge_reason,
            "violations": dict(self.violations),
            "truth": dict(TRUTH),
        }

    def metrics(self) -> dict[str, Any]:
        covered = sum(
            1 for evidence_id in KEY_EVIDENCE if evidence_id in self.recorded_ids
        )
        return {
            "map28.timeline_constraint_satisfaction": {
                "numerator": self.satisfied_fields,
                "denominator": len(CLAIM_FIELDS),
            },
            "map28.key_evidence_coverage": {
                "numerator": covered,
                "denominator": len(KEY_EVIDENCE),
            },
            "map28.unsupported_accusations": self.unsupported_accusations,
            "map28.time_contradictions": self.contradictions,
        }


def _claim(claim_id: str, value: str) -> dict[str, str]:
    return {"claim_id": claim_id, "value": value}


#: 论文手写路线：先物证后证词，四项各由两类来源交叉，tick 20 提交成功。
_EVIDENCE_FIRST = [
    {"tool": "move", "to": "V"},
    {"tool": "investigate", "target_id": "vault_lock_events"},
    {"tool": "move", "to": "S"},
    {"tool": "investigate", "target_id": "footprint_trail"},
    {"tool": "move", "to": "K"},
    {"tool": "move", "to": "G"},
    {"tool": "move", "to": "A"},
    {"tool": "read_record", "record_id": "key_registry"},
    {"tool": "record", "clue_id": "KEY_REGISTER_K3_CELINE"},
    {"tool": "record", "clue_id": "LOCK_ENTRY_K3_2106"},
    {"tool": "record", "clue_id": "LOCK_EXIT_S_2114"},
    {"tool": "record", "clue_id": "PRINT_C7_ROUTE_SV"},
    {"tool": "move", "to": "G"},
    {"tool": "move", "to": "K"},
    {"tool": "interview", "witness_id": "kitchen_cook"},
    {"tool": "record", "clue_id": "WITNESS_BASIL_S_WINDOW"},
    {"tool": "move", "to": "G"},
    {"tool": "move", "to": "V"},
    {"tool": "move", "to": "H"},
    {
        "tool": "submit",
        "claims": [
            _claim("person_id", "CELINE"),
            _claim("entry_path_id", "SECRET_S_V"),
            _claim("entry_time", "21:06"),
            _claim("exit_time", "21:14"),
        ],
        "citations_by_claim": {
            "person_id": ["KEY_REGISTER_K3_CELINE", "LOCK_ENTRY_K3_2106"],
            "entry_path_id": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"],
            "entry_time": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"],
            "exit_time": ["LOCK_EXIT_S_2114", "PRINT_C7_ROUTE_SV"],
        },
    },
]

ORACLE_CASES = (
    {
        "trace_id": "evidence_first_two_source",
        "seed": 0,
        "actions": _EVIDENCE_FIRST,
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "four_fields_two_sources_success",
        "seed": 0,
        "actions": _EVIDENCE_FIRST,
        # 手算：四栏值全对且各有两个来源类别 → 4/4；四件关键证据全记录；
        # 无不支持指控、无时间矛盾。
        "expect": {
            "map28.timeline_constraint_satisfaction": 1.0,
            "map28.key_evidence_coverage": 1.0,
            "map28.unsupported_accusations": 0,
            "map28.time_contradictions": 0,
        },
    },
    {
        "name": "window_guess_contradicts_lock_minute",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "V"},
            {"tool": "investigate", "target_id": "vault_lock_events"},
            {"tool": "record", "clue_id": "LOCK_ENTRY_K3_2106"},
            {"tool": "move", "to": "S"},
            {"tool": "investigate", "target_id": "footprint_trail"},
            {"tool": "record", "clue_id": "PRINT_C7_ROUTE_SV"},
            {"tool": "move", "to": "V"},
            {"tool": "move", "to": "H"},
            {
                "tool": "submit",
                "claims": [
                    _claim("person_id", "CELINE"),
                    _claim("entry_path_id", "SECRET_S_V"),
                    _claim("entry_time", "21:05"),
                    _claim("exit_time", "21:14"),
                ],
                "citations_by_claim": {
                    "person_id": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"],
                    "entry_path_id": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"],
                    "entry_time": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"],
                    "exit_time": ["PRINT_C7_ROUTE_SV"],
                },
            },
        ],
        # 手算：人物/路径各两类来源且值正确 → 2 满足；21:05 被 21:06 锁芯精确记录
        # 排除 → 1 次时间矛盾，且该栏只剩 physical_trace 一类；离开分钟只引用
        # physical_trace 一类 → 不满足。满足 2/4；覆盖 2/4；不支持指控 1。
        "expect": {
            "map28.timeline_constraint_satisfaction": 0.5,
            "map28.key_evidence_coverage": 0.5,
            "map28.unsupported_accusations": 1,
            "map28.time_contradictions": 1,
        },
    },
    {
        "name": "unobserved_record_and_invalid_path_alias",
        "seed": 0,
        "actions": [
            {"tool": "record", "clue_id": "LOCK_ENTRY_K3_2106"},
            {"tool": "move", "to": "V"},
            {"tool": "investigate", "target_id": "vault_lock_events"},
            {"tool": "record", "clue_id": "LOCK_ENTRY_K3_2106"},
            {"tool": "move", "to": "H"},
            {
                "tool": "submit",
                "claims": [
                    _claim("person_id", "CELINE"),
                    _claim("entry_path_id", "secret_tunnel"),
                    _claim("entry_time", "21:06"),
                    _claim("exit_time", "21:14"),
                ],
                "citations_by_claim": {
                    "person_id": ["LOCK_ENTRY_K3_2106"],
                    "entry_path_id": ["LOCK_ENTRY_K3_2106"],
                    "entry_time": ["LOCK_ENTRY_K3_2106"],
                    "exit_time": ["LOCK_ENTRY_K3_2106"],
                },
            },
            {
                "tool": "submit",
                "claims": [
                    _claim("person_id", "CELINE"),
                    _claim("entry_path_id", "SECRET_S_V"),
                    _claim("entry_time", "21:06"),
                    _claim("exit_time", "21:14"),
                ],
                "citations_by_claim": {
                    "person_id": [],
                    "entry_path_id": [],
                    "entry_time": [],
                    "exit_time": [],
                },
            },
        ],
        # 手算：未观察的记录 0 tick 且不写笔记；非法路径别名 0 tick 且不消耗唯一
        # 提交；最终提交无任何引用 → 0/4 满足、覆盖 1/4、不支持指控 1、矛盾 0。
        "expect": {
            "map28.timeline_constraint_satisfaction": 0.0,
            "map28.key_evidence_coverage": 0.25,
            "map28.unsupported_accusations": 1,
            "map28.time_contradictions": 0,
        },
    },
)


__all__ = ["FIXTURES", "Map28Environment", "ORACLE_CASES"]
