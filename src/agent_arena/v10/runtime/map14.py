"""MAP-14 V10｜说谎的祭司：推理成为必要条件与多样本实例（DCR-V10-09）。

与 V8 的差异：

- **公开推理规则**：system prompt 与 `public_rules()` 明确写出“恰有一名祭司对每一条命题都
  如实作答，另外两人对每一条命题都反报”，不再只靠标题暗示；
- **成功判据要求推理**：`submit_configuration` 只有在**当前封存的假设与提交锁型一致、
  且该假设与全部已观察答复/档案相容**时才开门；不封存或封存不一致的盲目提交得到
  `NO_CONSISTENT_HYPOTHESIS`，只计 `wrong_submissions`；
- 预登记 6 个实例：锁型数 3 或 4、真值 (锁型, 诚实者)、档案排除项、六条命题的**划分方式**
  都不同（命题集合由 seed 确定，不是固定表）；
- 主指标 `deduction_success` 同时要求“门开 + 封存假设一致 + 问数不超过最少问数”，
  把“问到最少就问出来”和“问了一堆才猜中”分开；`blind_submit_attempts` 作为护栏。
"""

from __future__ import annotations

import random
from itertools import combinations
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

PRIESTS = ("P0", "P1", "P2")
PRIEST_NAMES = {"P0": "甲", "P1": "乙", "P2": "丙"}
QUESTION_BUDGET = 4
WRONG_SUBMISSION_LIMIT = 2
EDGES = {"P_A": ("P", "A"), "A_O": ("A", "O"), "O_J": ("O", "J")}


class Variant14:
    def __init__(self, seed: int) -> None:
        rng = random.Random(f"map14-v10|{seed}")
        count = 4 if seed % 3 == 2 else 3
        self.configurations = tuple(f"LOCK_{index}" for index in range(count))
        self.truth_configuration = self.configurations[seed % count]
        self.truth_priest = PRIESTS[(seed // 1 + 1) % 3]
        excluded_index = (seed + 1) % count
        self.excluded_configuration = self.configurations[excluded_index]
        self.claims: dict[str, tuple[str, frozenset[str]]] = {}
        for priest in PRIESTS:
            subsets: list[frozenset[str]] = []
            for _ in range(2):
                while True:
                    size = rng.choice([1, 2, max(1, count - 1)])
                    size = max(1, min(size, count))
                    subset = frozenset(rng.sample(self.configurations, size))
                    if subset not in subsets:
                        subsets.append(subset)
                        break
            for index, subset in enumerate(subsets):
                self.claims[f"{priest[-1]}_{index + 1}"] = (priest, subset)

    @property
    def states(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (config, priest) for config in self.configurations for priest in PRIESTS
        )

    def answer(self, config: str, priest: str, claim_id: str) -> bool:
        speaker, subset = self.claims[claim_id]
        truth = config in subset
        return truth if priest == speaker else not truth

    def archive_excludes(self, config: str) -> bool:
        return config == self.excluded_configuration

    def minimum_queries(self, *, archive: bool) -> int:
        for size in range(0, len(self.claims) + 1):
            for subset in combinations(sorted(self.claims), size):
                if self._identifies(subset, archive=archive):
                    return size
        return len(self.claims)

    def _identifies(self, subset: tuple[str, ...], *, archive: bool) -> bool:
        seen: set[tuple[bool, ...]] = set()
        for config, priest in self.states:
            if archive and self.archive_excludes(config):
                continue
            code = tuple(self.answer(config, priest, claim) for claim in subset)
            if code in seen:
                return False
            seen.add(code)
        return True


VARIANTS: dict[int, Variant14] = {seed: Variant14(seed) for seed in range(6)}


class Map14V10Environment(V10Map):
    map_id = "MAP-14"
    title = "说谎的祭司"
    world = "pyramid"
    level = "中等"
    RULE_VERSION = "v10.map14.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGES
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
            "configurations",
            "truth_rule",
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
    PRIMARY_METRIC = "map14.v10.deduction_success"
    METRIC_SPECS = (
        MetricSpec(
            "map14.v10.deduction_success",
            "primary",
            "higher",
            "门开 且 封存假设一致 且 问数 ≤ 最少问数",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map14.v10.consistent_hypothesis_rate",
            "secondary",
            "higher",
            "封存的假设中与全部已观察答复/档案相容的比例",
            "封存过的局（≥1）",
            zero_denominator="从未封存 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map14.v10.blind_submit_attempts",
            "guardrail",
            "lower",
            "没有相容封存假设的提交次数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map14.v10.queries_used",
            "diagnostic",
            "lower",
            "已消耗的提问数",
            "—",
            unit="count",
            valid_range=(0.0, 8.0),
        ),
        MetricSpec(
            "map14.v10.query_budget_overruns",
            "guardrail",
            "lower",
            "超出预算被拒的提问次数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.node = "P"
        self.items = []
        self.archive_read = False
        self.answers: list[dict[str, Any]] = []
        self.asked_claim_ids: set[str] = set()
        self.sealed: list[dict[str, Any]] = []
        self.submissions: list[dict[str, Any]] = []
        self.wrong_submissions = 0
        self.blind_submit_attempts = 0
        self.gate_open = False
        self._free_action = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "configurations": list(self.variant.configurations),
            "claim_ids": sorted(self.variant.claims),
            "question_budget": QUESTION_BUDGET,
            "wrong_submission_limit": WRONG_SUBMISSION_LIMIT,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "configuration": self.variant.truth_configuration,
            "truthful_priest": self.variant.truth_priest,
            "excluded_configuration": self.variant.excluded_configuration,
            "claims": {
                claim: [str(item) for item in sorted(subset)]
                for claim, (_, subset) in sorted(self.variant.claims.items())
            },
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "P—A—O—J 三点链条：P 是证词厅、A 是档案室、O 是比对台、J 是审判门。",
            f"锁型候选只有 {len(self.variant.configurations)} 种（见 configurations）。",
            "**推理规则**：三名祭司中恰有一人对每一条命题都如实作答，另外两人对每一条命题"
            "都反报（说反话）。谁诚实未知。",
            f"整局最多问 {QUESTION_BUDGET} 条命题（在 P），"
            f"最多错交 {WRONG_SUBMISSION_LIMIT - 1} 次。",
            "read_archive 在 A 读取一条排除性档案（有且只有一条）。",
            "compare_evidence 在 O 封存一个（锁型, 诚实者）假设，只记录、不判对错。",
            "submit_configuration 在 J：只有当**最近一次封存的假设与提交锁型一致、且该假设与"
            "全部已观察答复/档案相容**时门才打开；否则记一次错交。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        cards: dict[str, dict[str, Any]] = {}
        if self.node == "P":
            for claim_id, (priest, subset) in sorted(self.variant.claims.items()):
                cards[claim_id] = {
                    "speaker": PRIEST_NAMES[priest],
                    "question": f"当前锁型属于 {{{', '.join(sorted(subset))}}} 吗？",
                    "truth_set": sorted(subset),
                }
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tick": self.tick_count,
            "configurations": list(self.variant.configurations),
            "truth_rule": "恰一名祭司全真、其余两人逐命题反报",
            "public_statement_cards": cards,
            "archive_record_if_read": (
                {
                    "evidence_id": "ARCHIVE_EXCLUDE",
                    "text": f"{self.variant.excluded_configuration} 从未安装在当前审判门上。",
                    "excluded": self.variant.excluded_configuration,
                }
                if self.archive_read
                else None
            ),
            "question_answers": [
                {
                    "evidence_id": f"ANSWER_{row['claim_id']}",
                    "claim_id": row["claim_id"],
                    "speaker": PRIEST_NAMES[self.variant.claims[row["claim_id"]][0]],
                    "answer": "yes" if row["answer"] else "no",
                }
                for row in self.answers
            ],
            "questions_used": len(self.answers),
            "questions_remaining": max(0, QUESTION_BUDGET - len(self.answers)),
            "comparison_record": (dict(self.sealed[-1]) if self.sealed else None),
            "wrong_submissions": self.wrong_submissions,
            "wrong_submissions_remaining": max(0, WRONG_SUBMISSION_LIMIT - self.wrong_submissions),
            "gate_open": self.gate_open,
            "goal": "判断真实锁型并开门；推理规则已公开，盲猜不会开门。",
        }

    # ------------------------------------------------------------------ rules
    def observed_evidence_ids(self) -> set[str]:
        evidence = {f"ANSWER_{row['claim_id']}" for row in self.answers}
        if self.archive_read:
            evidence.add("ARCHIVE_EXCLUDE")
        return evidence

    def consistent(self, configuration: str, priest: str) -> bool:
        if self.archive_read and self.variant.archive_excludes(configuration):
            return False
        return all(
            self.variant.answer(configuration, priest, row["claim_id"]) == row["answer"]
            for row in self.answers
        )

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
            return "ARCHIVE_EXCLUDE"
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
        if claim_id not in self.variant.claims:
            return "UNKNOWN_CLAIM"
        if claim_id in self.asked_claim_ids:
            self._count("DUPLICATE_QUERY")
            self._free_action = True
            return "CLAIM_ALREADY_ASKED"
        if len(self.answers) >= QUESTION_BUDGET:
            self._count("QUERY_BUDGET_EXCEEDED")
            self._free_action = True
            return "QUERY_BUDGET_EXCEEDED"
        answer = self.variant.answer(
            self.variant.truth_configuration, self.variant.truth_priest, claim_id
        )
        self.asked_claim_ids.add(claim_id)
        self.answers.append({"claim_id": claim_id, "answer": answer})
        return "ANSWER:yes" if answer else "ANSWER:no"

    def _compare(self, action: V8Action) -> str:
        if self.node != "O":
            return "TARGET_NOT_VISIBLE"
        configuration = action.choice
        priest = action.person_id
        support = [str(item) for item in (action.support_evidence_ids or [])]
        if configuration not in self.variant.configurations:
            return "UNKNOWN_CONFIGURATION"
        if priest not in PRIESTS:
            return "UNKNOWN_PRIEST"
        observed = self.observed_evidence_ids()
        if any(item not in observed for item in support):
            return "EVIDENCE_NOT_OBSERVED"
        self.sealed.append(
            {
                "configuration_candidate": str(configuration),
                "truthful_priest_candidate": str(priest),
                "consistent": self.consistent(str(configuration), str(priest)),
                "support_evidence_ids": support,
            }
        )
        return "HYPOTHESIS_SEALED_WITHOUT_JUDGMENT"

    def _submit(self, action: V8Action) -> str:
        if self.node != "J":
            return "TARGET_NOT_VISIBLE"
        configuration = action.choice
        if configuration not in self.variant.configurations:
            return "UNKNOWN_CONFIGURATION"
        latest = self.sealed[-1] if self.sealed else None
        justified = bool(
            latest
            and latest["consistent"]
            and latest["configuration_candidate"] == configuration
        )
        self.submissions.append(
            {
                "configuration": str(configuration),
                "correct": configuration == self.variant.truth_configuration,
                "justified": justified,
            }
        )
        if not justified:
            self.blind_submit_attempts += 1
        if configuration == self.variant.truth_configuration and justified:
            self.gate_open = True
            self._succeed("GATE_OPENED_WITH_CONSISTENT_HYPOTHESIS")
            return "GATE_OPENED"
        self.wrong_submissions += 1
        if self.wrong_submissions >= WRONG_SUBMISSION_LIMIT:
            self._fail("WRONG_SUBMISSION_LIMIT")
            return "WRONG_SUBMISSION_LIMIT"
        if not justified:
            return "NO_CONSISTENT_HYPOTHESIS"
        return "GATE_STAYED_CLOSED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return 0 if self._free_action else 1

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "location": self.node,
            "configuration": self.variant.truth_configuration,
            "truthful_priest": self.variant.truth_priest,
            "minimum_queries_no_archive": self.variant.minimum_queries(archive=False),
            "minimum_queries_with_archive": self.variant.minimum_queries(archive=True),
            "archive_read": self.archive_read,
            "asked_claim_ids": sorted(self.asked_claim_ids),
            "answers": [
                {"claim_id": row["claim_id"], "answer": bool(row["answer"])}
                for row in self.answers
            ],
            "sealed": [dict(item) for item in self.sealed],
            "submissions": [dict(item) for item in self.submissions],
            "wrong_submissions": self.wrong_submissions,
            "blind_submit_attempts": self.blind_submit_attempts,
            "gate_open": self.gate_open,
            "counters": dict(sorted(self.counters.items())),
            "truth_seal": self.truth_seal(),
        }

    def _plan_minimum(self) -> int:
        return min(
            self.variant.minimum_queries(archive=False),
            self.variant.minimum_queries(archive=True),
        )

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        minimum = self._plan_minimum()
        consistent = [item for item in self.sealed if item["consistent"]]
        if self.gate_open and consistent and len(self.answers) <= minimum:
            deduction: MValue = valid(1)
        elif running:
            deduction = censored("截尾未开门")
        else:
            deduction = valid(0)
        if self.sealed:
            rate: MValue = ratio(len(consistent), len(self.sealed))
        else:
            rate = not_applicable("从未封存假设")
        return {
            "map14.v10.deduction_success": deduction,
            "map14.v10.consistent_hypothesis_rate": rate,
            "map14.v10.blind_submit_attempts": valid(self.blind_submit_attempts),
            "map14.v10.queries_used": valid(len(self.answers)),
            "map14.v10.query_budget_overruns": valid(self.counters.get("QUERY_BUDGET_EXCEEDED", 0)),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少封存过一个与已观察信息相容的 (锁型, 诚实者) 假设。"""

        return any(item["consistent"] for item in self.sealed)


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：读档案（若省问）→ 问最少识别子集 → 封存 → 提交。"""

    variant = VARIANTS[environment_seed]
    with_archive = variant.minimum_queries(archive=True)
    without_archive = variant.minimum_queries(archive=False)
    use_archive = with_archive < without_archive
    subset = _identifying_subset(variant, archive=use_archive)
    actions: list[dict[str, Any]] = []
    if use_archive:
        actions.append({"tool": "move", "edge_id": "P_A"})
        actions.append({"tool": "read_archive"})
        actions.append({"tool": "move", "edge_id": "P_A"})
    for claim in subset:
        actions.append({"tool": "ask", "claim_id": claim})
    actions.append({"tool": "move", "edge_id": "P_A"})
    actions.append({"tool": "move", "edge_id": "A_O"})
    support = [f"ANSWER_{claim}" for claim in subset]
    if use_archive:
        support.append("ARCHIVE_EXCLUDE")
    actions.append(
        {
            "tool": "compare_evidence",
            "choice": variant.truth_configuration,
            "person_id": variant.truth_priest,
            "support_evidence_ids": support,
        }
    )
    actions.append({"tool": "move", "edge_id": "O_J"})
    actions.append({"tool": "submit_configuration", "choice": variant.truth_configuration})
    return actions


def _identifying_subset(variant: Variant14, *, archive: bool) -> tuple[str, ...]:
    for size in range(0, len(variant.claims) + 1):
        for subset in combinations(sorted(variant.claims), size):
            if variant._identifies(subset, archive=archive):
                return subset
    raise RuntimeError("no identifying subset")  # pragma: no cover


__all__ = [
    "EDGES",
    "Map14V10Environment",
    "PRIESTS",
    "QUESTION_BUDGET",
    "VARIANTS",
    "Variant14",
    "oracle_actions",
]
