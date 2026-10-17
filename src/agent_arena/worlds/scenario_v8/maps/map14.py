"""MAP-14｜说谎的祭司：三锁型 × 三诚实者的九态真值推理与问询预算。

本图与同世界另两图的机制差异：MAP-13 的碑文全部为真、约束静态；MAP-15 的规则随
全局 tick 奇偶切换；本图规则静态，但六条证词只有恰一名祭司全局如实、另外两人逐命题
反报。玩家要在 4 问预算内维护“锁型 × 诚实者”九态一致假设，再到审判门承担最终验证。
共享严格模型把 ``configuration`` / ``configuration_candidate`` 定义为整数列表，故本图
用 ``choice`` 携带锁型候选、用 ``person_id`` 携带诚实者候选、用 ``support_evidence_ids``
携带已观察证据 ID；``claim_id`` 携带命题 ID。

指标口径（与 V7 卡片一致）：
- ``globally_consistent_hypothesis_rate``：每次 ``compare_evidence`` 封存一个
  “锁型 × 诚实者”假设时，按当时已公开的答复、档案与“恰一名诚实者”假设重算该完整
  九态假设是否仍可解释全部陈述；分子为一致假设数，分母为封存假设总数，无封存记
  0/0（N/A）。只评锁型而不评诚实者会把“兼容 A/甲”的歧义藏起来，故本图评完整配对。
- ``minimum_query_gap``：已问数 − 该隐藏状态在冻结六命题真值表上的最少问询数；最少问
  询数由模块在导入时对 9 态 × 全部命题子集穷举得到。欠问时按 0 截尾（登记表要求 ≥ 0）。
- ``query_budget_overruns``：第 5 问及以后被 ``QUERY_BUDGET_EXCEEDED`` 拒绝的次数；
  重复问另记 ``DUPLICATE_QUERY``，不并入本指标。
- ``contradiction_missed``：任一最终提交锁型与已知公开证据矛盾时记 1，否则 0。
- ``queries_used``：实际记入账本的 ``ask`` 次数。
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action

CONFIGURATIONS = ("A_sun_wheel", "B_crescent", "C_star_well")
PRIESTS = ("A_priest", "B_priest", "C_priest")
PRIEST_NAMES = {"A_priest": "甲", "B_priest": "乙", "C_priest": "丙"}
CLAIM_IDS = ("A1", "A2", "B1", "B2", "C1", "C2")
CLAIM_TEXT = {
    "A1": "当前锁型是日轮锁A吗？",
    "A2": "当前锁型是月牙锁B吗？",
    "B1": "当前锁型不是星井锁C吗？",
    "B2": "当前锁型不是月牙锁B吗？",
    "C1": "当前锁型是星井锁C吗？",
    "C2": "当前锁型不是日轮锁A吗？",
}
CLAIM_SPEAKER = {
    "A1": "A_priest",
    "A2": "A_priest",
    "B1": "B_priest",
    "B2": "B_priest",
    "C1": "C_priest",
    "C2": "C_priest",
}
CLAIM_TRUE_FOR = {
    "A1": frozenset({"A_sun_wheel"}),
    "A2": frozenset({"B_crescent"}),
    "B1": frozenset({"A_sun_wheel", "B_crescent"}),
    "B2": frozenset({"A_sun_wheel", "C_star_well"}),
    "C1": frozenset({"C_star_well"}),
    "C2": frozenset({"B_crescent", "C_star_well"}),
}
HIDDEN_STATES = tuple((config, priest) for config in CONFIGURATIONS for priest in PRIESTS)
#: seed 0 固定为设计文档的 B/乙；其余余数各对应一个固定隐藏状态。
SEED_STATES = (
    ("B_crescent", "B_priest"),
    ("A_sun_wheel", "A_priest"),
    ("C_star_well", "C_priest"),
    ("A_sun_wheel", "B_priest"),
    ("A_sun_wheel", "C_priest"),
    ("B_crescent", "A_priest"),
    ("B_crescent", "C_priest"),
    ("C_star_well", "A_priest"),
    ("C_star_well", "B_priest"),
)
QUESTION_BUDGET = 4
WRONG_SUBMISSION_LIMIT = 2
ARCHIVE_EVIDENCE_ID = "ARCHIVE_NOT_C"
ARCHIVE_TEXT = "星井锁C从未安装在当前审判门上。"


def _answer(config: str, priest: str, claim_id: str) -> bool:
    """Return the spoken answer; only the unique truth teller reports the truth."""

    truth = config in CLAIM_TRUE_FOR[claim_id]
    return truth if priest == CLAIM_SPEAKER[claim_id] else not truth


def _minimum_queries(config: str, priest: str) -> int:
    """Smallest question subset whose answer code identifies this hidden state."""

    for size in range(1, len(CLAIM_IDS) + 1):
        for subset in combinations(CLAIM_IDS, size):
            code = tuple(_answer(config, priest, claim) for claim in subset)
            matches = sum(
                1
                for other_config, other_priest in HIDDEN_STATES
                if tuple(_answer(other_config, other_priest, claim) for claim in subset)
                == code
            )
            if matches == 1:
                return size
    return len(CLAIM_IDS)


MINIMUM_QUERIES = {
    state: _minimum_queries(*state) for state in HIDDEN_STATES
}


class Map14Environment(MapEnvironment):
    map_id = "MAP-14"
    title = "说谎的祭司"
    world = "pyramid"
    level = "中等"
    EDGES = {"P_A": ("P", "A"), "A_O": ("A", "O"), "O_J": ("O", "J")}
    EDGE_COST = {"P_A": 1, "A_O": 1, "O_J": 1}
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "read_archive": {frozenset({"tool"})},
        "ask": {frozenset({"tool", "claim_id"})},
        "compare_evidence": {
            frozenset({"tool", "choice", "person_id", "support_evidence_ids"})
        },
        "submit_configuration": {frozenset({"tool", "choice"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tick",
            "public_statement_cards",
            "archive_record_if_read",
            "question_answers",
            "questions_used",
            "questions_remaining",
            "comparison_record",
            "wrong_submissions",
            "wrong_submissions_remaining",
            "gate_open",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        self.node = "P"
        self.items = []
        configuration, truthful_priest = SEED_STATES[seed % len(SEED_STATES)]
        self.configuration = configuration
        self.truthful_priest = truthful_priest
        self.minimum_queries = MINIMUM_QUERIES[(configuration, truthful_priest)]
        self.archive_read = False
        self.answers: list[dict[str, Any]] = []
        self.asked_claim_ids: set[str] = set()
        self.comparison_record: dict[str, Any] | None = None
        self.sealed_hypotheses: list[dict[str, Any]] = []
        self.submissions: list[dict[str, Any]] = []
        self.wrong_submissions = 0
        self.gate_open = False
        self._free_action = False

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        cards: dict[str, dict[str, str]] = {}
        if self.node == "P":
            cards = {
                claim_id: {
                    "speaker": PRIEST_NAMES[CLAIM_SPEAKER[claim_id]],
                    "text": CLAIM_TEXT[claim_id],
                }
                for claim_id in CLAIM_IDS
            }
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "public_statement_cards": cards,
            "archive_record_if_read": (
                {"evidence_id": ARCHIVE_EVIDENCE_ID, "text": ARCHIVE_TEXT}
                if self.archive_read
                else None
            ),
            "question_answers": [
                {
                    "evidence_id": f"ANSWER_{row['claim_id']}",
                    "claim_id": row["claim_id"],
                    "speaker": PRIEST_NAMES[CLAIM_SPEAKER[row["claim_id"]]],
                    "text": CLAIM_TEXT[row["claim_id"]],
                    "answer": "yes" if row["answer"] else "no",
                }
                for row in self.answers
            ],
            "questions_used": len(self.answers),
            "questions_remaining": max(0, QUESTION_BUDGET - len(self.answers)),
            "comparison_record": (
                None
                if self.comparison_record is None
                else {
                    "configuration_candidate": self.comparison_record[
                        "configuration_candidate"
                    ],
                    "truthful_priest_candidate": self.comparison_record[
                        "truthful_priest_candidate"
                    ],
                    "support_evidence_ids": list(
                        self.comparison_record["support_evidence_ids"]
                    ),
                }
            ),
            "wrong_submissions": self.wrong_submissions,
            "wrong_submissions_remaining": max(
                0, WRONG_SUBMISSION_LIMIT - self.wrong_submissions
            ),
            "gate_open": self.gate_open,
            "goal": "在审判门提交正确锁型；整局最多问 4 条命题，最多错交 1 次。",
        }

    # ------------------------------------------------------------------ rules
    def _observed_evidence_ids(self) -> set[str]:
        evidence = {f"ANSWER_{row['claim_id']}" for row in self.answers}
        if self.archive_read:
            evidence.add(ARCHIVE_EVIDENCE_ID)
        return evidence

    def _pair_consistent(self, configuration: str, priest: str) -> bool:
        """Whether one (lock, truth-teller) state explains every public statement."""

        if self.archive_read and configuration == "C_star_well":
            return False
        return all(
            _answer(configuration, priest, row["claim_id"]) == row["answer"]
            for row in self.answers
        )

    def _consistent_priests(self, configuration: str) -> list[str]:
        """Priests whose truth pattern explains every public answer and the archive."""

        return [
            priest
            for priest in PRIESTS
            if self._pair_consistent(configuration, priest)
        ]

    def _apply(self, action: V8Action) -> str:
        self._free_action = False
        tool = action.tool
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            destination, result = self.move_edge(action.edge_id)
            return result if destination is not None else "EDGE_NOT_ADJACENT"
        if tool == "read_archive":
            if self.node != "A":
                return "TARGET_NOT_VISIBLE"
            if self.archive_read:
                return "ARCHIVE_ALREADY_READ"
            self.archive_read = True
            return ARCHIVE_EVIDENCE_ID
        if tool == "ask":
            return self._ask(action)
        if tool == "compare_evidence":
            return self._compare(action)
        if tool == "submit_configuration":
            return self._submit(action)
        return "ACTION_NOT_ALLOWED"

    def _ask(self, action: V8Action) -> str:
        claim_id = action.claim_id
        if claim_id is None:
            return "INVALID_ACTION_SCHEMA"
        if self.node != "P":
            return "TARGET_NOT_VISIBLE"
        if claim_id not in CLAIM_IDS:
            return "UNKNOWN_CLAIM"
        if claim_id in self.asked_claim_ids:
            self._count("DUPLICATE_QUERY")
            self._free_action = True
            return "CLAIM_ALREADY_ASKED"
        if len(self.answers) >= QUESTION_BUDGET:
            self._count("QUERY_BUDGET_EXCEEDED")
            self._free_action = True
            return "QUERY_BUDGET_EXCEEDED"
        answer = _answer(self.configuration, self.truthful_priest, claim_id)
        self.asked_claim_ids.add(claim_id)
        self.answers.append({"claim_id": claim_id, "answer": answer})
        return "ANSWER:yes" if answer else "ANSWER:no"

    def _compare(self, action: V8Action) -> str:
        if self.node != "O":
            return "TARGET_NOT_VISIBLE"
        configuration = action.choice
        priest = action.person_id
        support = action.support_evidence_ids or []
        if configuration not in CONFIGURATIONS:
            return "UNKNOWN_CONFIGURATION"
        if priest not in PRIESTS:
            return "UNKNOWN_PRIEST"
        observed = self._observed_evidence_ids()
        if any(evidence_id not in observed for evidence_id in support):
            return "EVIDENCE_NOT_OBSERVED"
        self.comparison_record = {
            "configuration_candidate": configuration,
            "truthful_priest_candidate": priest,
            "support_evidence_ids": list(support),
        }
        self.sealed_hypotheses.append(
            {
                "configuration": configuration,
                "truthful_priest": priest,
                "consistent": self._pair_consistent(configuration, priest),
                "questions_at_seal": len(self.answers),
                "archive_read": self.archive_read,
                "support_evidence_ids": list(support),
            }
        )
        return "HYPOTHESIS_SEALED_WITHOUT_JUDGMENT"

    def _submit(self, action: V8Action) -> str:
        if self.node != "J":
            return "TARGET_NOT_VISIBLE"
        configuration = action.choice
        if configuration not in CONFIGURATIONS:
            return "UNKNOWN_CONFIGURATION"
        consistent_priests = self._consistent_priests(configuration)
        self.submissions.append(
            {
                "configuration": configuration,
                "correct": configuration == self.configuration,
                "consistent": bool(consistent_priests),
                "contradiction": not consistent_priests,
                "consistent_priests": list(consistent_priests),
                "questions_at_submit": len(self.answers),
                "archive_read": self.archive_read,
            }
        )
        if configuration == self.configuration:
            self.gate_open = True
            self._succeed("GATE_OPENED")
            return "GATE_OPENED"
        self.wrong_submissions += 1
        if self.wrong_submissions >= WRONG_SUBMISSION_LIMIT:
            self._fail("WRONG_SUBMISSION_LIMIT")
            return "WRONG_SUBMISSION_LIMIT"
        return "GATE_STAYED_CLOSED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return 0 if self._free_action else 1

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "configuration": self.configuration,
            "truthful_priest": self.truthful_priest,
            "minimum_queries": self.minimum_queries,
            "archive_read": self.archive_read,
            "asked_claim_ids": sorted(self.asked_claim_ids),
            "answers": [
                {"claim_id": row["claim_id"], "answer": bool(row["answer"])}
                for row in self.answers
            ],
            "comparison_record": (
                None if self.comparison_record is None else dict(self.comparison_record)
            ),
            "sealed_hypotheses": [dict(row) for row in self.sealed_hypotheses],
            "submissions": [dict(row) for row in self.submissions],
            "wrong_submissions": self.wrong_submissions,
            "gate_open": self.gate_open,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        sealed = len(self.sealed_hypotheses)
        consistent = sum(1 for row in self.sealed_hypotheses if row["consistent"])
        contradiction = int(any(row["contradiction"] for row in self.submissions))
        return {
            "map14.globally_consistent_hypothesis_rate": {
                "numerator": consistent,
                "denominator": sealed,
            },
            "map14.minimum_query_gap": max(
                0, len(self.answers) - self.minimum_queries
            ),
            "map14.query_budget_overruns": self.counters.get(
                "QUERY_BUDGET_EXCEEDED", 0
            ),
            "map14.contradiction_missed": contradiction,
            "map14.queries_used": len(self.answers),
        }


ORACLE_CASES = (
    {
        "trace_id": "archive_then_ask",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "read_archive"},
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "ask", "claim_id": "A1"},
            {"tool": "ask", "claim_id": "B1"},
            {"tool": "ask", "claim_id": "B2"},
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "move", "edge_id": "A_O"},
            {
                "tool": "compare_evidence",
                "choice": "B_crescent",
                "person_id": "B_priest",
                "support_evidence_ids": [
                    "ARCHIVE_NOT_C",
                    "ANSWER_A1",
                    "ANSWER_B1",
                    "ANSWER_B2",
                ],
            },
            {"tool": "move", "edge_id": "O_J"},
            {"tool": "submit_configuration", "choice": "B_crescent"},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "adaptive_without_archive",
        "seed": 0,
        "actions": [
            {"tool": "ask", "claim_id": "A1"},
            {"tool": "ask", "claim_id": "A2"},
            {"tool": "ask", "claim_id": "B1"},
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "move", "edge_id": "A_O"},
            {
                "tool": "compare_evidence",
                "choice": "B_crescent",
                "person_id": "B_priest",
                "support_evidence_ids": [
                    "ANSWER_A1",
                    "ANSWER_A2",
                    "ANSWER_B1",
                ],
            },
            {"tool": "move", "edge_id": "O_J"},
            {"tool": "submit_configuration", "choice": "B_crescent"},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "adaptive_three_questions_success",
        "seed": 0,
        "actions": [
            {"tool": "ask", "claim_id": "A1"},
            {"tool": "ask", "claim_id": "A2"},
            {"tool": "ask", "claim_id": "B1"},
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "move", "edge_id": "A_O"},
            {
                "tool": "compare_evidence",
                "choice": "B_crescent",
                "person_id": "B_priest",
                "support_evidence_ids": [
                    "ANSWER_A1",
                    "ANSWER_A2",
                    "ANSWER_B1",
                ],
            },
            {"tool": "move", "edge_id": "O_J"},
            {"tool": "submit_configuration", "choice": "B_crescent"},
        ],
        "expect": {
            "map14.globally_consistent_hypothesis_rate": 1.0,
            "map14.minimum_query_gap": 0,
            "map14.query_budget_overruns": 0,
            "map14.contradiction_missed": 0,
            "map14.queries_used": 3,
        },
    },
    {
        "name": "archive_exclusion_ignored_then_submit_c",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "read_archive"},
            {"tool": "move", "edge_id": "A_O"},
            {
                "tool": "compare_evidence",
                "choice": "C_star_well",
                "person_id": "C_priest",
                "support_evidence_ids": ["ARCHIVE_NOT_C"],
            },
            {"tool": "move", "edge_id": "O_J"},
            {"tool": "submit_configuration", "choice": "C_star_well"},
        ],
        "expect": {
            "map14.globally_consistent_hypothesis_rate": 0.0,
            "map14.contradiction_missed": 1,
            "map14.queries_used": 0,
        },
    },
    {
        "name": "fifth_question_is_refused_without_tick",
        "seed": 0,
        "actions": [
            {"tool": "ask", "claim_id": "A1"},
            {"tool": "ask", "claim_id": "A2"},
            {"tool": "ask", "claim_id": "B1"},
            {"tool": "ask", "claim_id": "B2"},
            {"tool": "ask", "claim_id": "C1"},
        ],
        "expect": {
            "map14.queries_used": 4,
            "map14.query_budget_overruns": 1,
            "map14.minimum_query_gap": 1,
            "map14.contradiction_missed": 0,
        },
    },
    {
        "name": "correct_lock_with_wrong_priest_still_opens_gate",
        "seed": 0,
        "actions": [
            {"tool": "ask", "claim_id": "A1"},
            {"tool": "ask", "claim_id": "A2"},
            {"tool": "ask", "claim_id": "B1"},
            {"tool": "move", "edge_id": "P_A"},
            {"tool": "move", "edge_id": "A_O"},
            {
                "tool": "compare_evidence",
                "choice": "B_crescent",
                "person_id": "A_priest",
                "support_evidence_ids": [
                    "ANSWER_A1",
                    "ANSWER_A2",
                    "ANSWER_B1",
                ],
            },
            {"tool": "move", "edge_id": "O_J"},
            {"tool": "submit_configuration", "choice": "B_crescent"},
        ],
        "expect": {
            "map14.globally_consistent_hypothesis_rate": 0.0,
            "map14.contradiction_missed": 0,
            "map14.queries_used": 3,
            "map14.minimum_query_gap": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map14Environment"]
