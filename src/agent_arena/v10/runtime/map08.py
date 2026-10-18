"""MAP-08 V10｜漏点诊断：诊断封存成为修复前提（DCR-V10-16）。

V9 的疑点：接口修复后仍 0/1；`no_hypothesis` 却成功——“主动测试缩小漏点假设集”
可能不是必要条件。V10 的修复：

- **封存诊断是修复的前提**：`seal_diagnosis(diagnosis_code)` 只有在候选集**已被测试
  缩成唯一站点**时才成立（`DIAGNOSIS_INCOMPLETE`）；`repair(target_id)` 只有在已封存
  同一站点时才执行（`DIAGNOSIS_REQUIRED` / `DIAGNOSIS_MISMATCH`）。盲目换件无法出手。
- **测试必须真的缩小假设集**：每个测试的读数按公开分区映射到站点子集，候选集取交集；
  `hypothesis_reduction = (初始候选数 − 封存时候选数) / (初始 − 1)`，成功的局必须为 1.0。
- 4 个预登记实例：漏点站点、测试分区与最少测试数都不同。
- 备件成本：修错站点会浪费一个备件并耗 2 tick，两次错修即失败（保留“侥幸盲修”的
  合法代价，而不是删掉它）。
"""

from __future__ import annotations

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

SITES = ("S1", "S2", "S3", "S4", "S5")
TESTS = ("T1", "T2", "T3")
REPAIR_TICKS = 2
MAX_WRONG_REPAIRS = 2
DEADLINE = 14


class Variant08:
    def __init__(
        self,
        label: str,
        leak: str,
        partitions: dict[str, dict[str, str]],
    ) -> None:
        self.label = label
        self.leak = leak
        self.partitions = partitions

    def reading(self, test_id: str, site: str) -> str:
        return self.partitions[test_id][site]

    def minimum_tests(self) -> int:
        for size in range(0, len(TESTS) + 1):
            for subset in combinations(TESTS, size):
                codes: set[tuple[str, ...]] = set()
                unique = True
                for site in SITES:
                    code = tuple(self.partitions[test][site] for test in subset)
                    if code in codes:
                        unique = False
                        break
                    codes.add(code)
                if unique:
                    return size
        return len(TESTS)


VARIANTS: dict[int, Variant08] = {
    0: Variant08(
        "binary_split",
        "S3",
        {
            "T1": {"S1": "HIGH", "S2": "HIGH", "S3": "LOW", "S4": "LOW", "S5": "LOW"},
            "T2": {"S1": "A", "S2": "B", "S3": "A", "S4": "B", "S5": "A"},
            "T3": {"S1": "x", "S2": "x", "S3": "y", "S4": "x", "S5": "z"},
        },
    ),
    1: Variant08(
        "triple_partition",
        "S5",
        {
            "T1": {"S1": "A", "S2": "B", "S3": "C", "S4": "A", "S5": "B"},
            "T2": {"S1": "p", "S2": "q", "S3": "p", "S4": "q", "S5": "r"},
            "T3": {"S1": "u", "S2": "u", "S3": "v", "S4": "v", "S5": "w"},
        },
    ),
    2: Variant08(
        "asymmetric",
        "S1",
        {
            "T1": {"S1": "LOW", "S2": "LOW", "S3": "HIGH", "S4": "HIGH", "S5": "HIGH"},
            "T2": {"S1": "A", "S2": "B", "S3": "A", "S4": "B", "S5": "B"},
            "T3": {"S1": "z", "S2": "y", "S3": "z", "S4": "y", "S5": "z"},
        },
    ),
    3: Variant08(
        "wide_leaf",
        "S4",
        {
            "T1": {"S1": "A", "S2": "A", "S3": "B", "S4": "C", "S5": "B"},
            "T2": {"S1": "m", "S2": "n", "S3": "m", "S4": "n", "S5": "o"},
            "T3": {"S1": "p", "S2": "q", "S3": "p", "S4": "q", "S5": "p"},
        },
    ),
}


class Map08V10Environment(V10Map):
    map_id = "MAP-08"
    title = "漏点诊断"
    world = "abyss"
    level = "中等"
    RULE_VERSION = "v10.map08.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "run_test": {frozenset({"tool", "test_id"})},
        "seal_diagnosis": {frozenset({"tool", "diagnosis_code"})},
        "repair": {frozenset({"tool", "target_id"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "deadline_tick",
            "sites",
            "available_tests",
            "test_partitions",
            "test_results",
            "candidate_sites",
            "sealed_diagnosis",
            "wrong_repairs",
            "spares_remaining",
            "goal",
        }
    )
    PRIMARY_METRIC = "map08.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map08.v10.mission_success",
            "primary",
            "higher",
            "在截止前修好真实漏点",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map08.v10.hypothesis_reduction",
            "secondary",
            "higher",
            "（初始候选 − 封存时候选）/（初始 − 1）",
            "封存过诊断的局（1）",
            zero_denominator="未封存 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map08.v10.tests_used",
            "diagnostic",
            "lower",
            "执行的测试数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map08.v10.wrong_repairs",
            "guardrail",
            "lower",
            "修错站点的次数",
            "—",
            unit="count",
            valid_range=(0.0, 5.0),
        ),
        MetricSpec(
            "map08.v10.unjustified_repairs",
            "guardrail",
            "lower",
            "缺少封存诊断或与封存不一致的修复尝试",
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
        self.tests_run: list[str] = []
        self.sealed: str | None = None
        self.sealed_candidates: int | None = None
        self.wrong_repairs = 0
        self.unjustified = 0
        self.repaired = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "sites": list(SITES),
            "tests": list(TESTS),
            "deadline_tick": DEADLINE,
            "max_wrong_repairs": MAX_WRONG_REPAIRS,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "leak": self.variant.leak,
            "minimum_tests": self.variant.minimum_tests(),
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            f"候选站点 {', '.join(SITES)}；其中恰有一处是真实漏点。",
            "run_test(test_id) 耗 1 tick，按**公开分区**返回读数；每个测试只能读一次。",
            "candidate_sites 是全部读数与初始候选的交集，随测试实时更新。",
            "seal_diagnosis(diagnosis_code)：只有候选集**缩成唯一站点**时才成立；"
            "封存后不可更改。",
            "repair(target_id) 耗 2 tick，只有与封存诊断一致时才执行；修错会浪费一个备件，"
            "两次错修即失败。",
            f"截止 tick {DEADLINE}。",
        )

    # ------------------------------------------------------------------ public
    def candidates(self) -> set[str]:
        allowed = set(SITES)
        for test_id in self.tests_run:
            reading = self.variant.reading(test_id, self.variant.leak)
            allowed &= {
                site
                for site in SITES
                if self.variant.partitions[test_id][site] == reading
            }
        return allowed

    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "deadline_tick": DEADLINE,
            "sites": list(SITES),
            "available_tests": [test for test in TESTS if test not in self.tests_run],
            "test_partitions": {
                test: dict(self.variant.partitions[test]) for test in sorted(TESTS)
            },
            "test_results": {
                test: self.variant.reading(test, self.variant.leak) for test in self.tests_run
            },
            "candidate_sites": sorted(self.candidates()),
            "sealed_diagnosis": self.sealed,
            "wrong_repairs": self.wrong_repairs,
            "spares_remaining": max(0, MAX_WRONG_REPAIRS - self.wrong_repairs),
            "goal": "用测试把漏点候选缩成唯一站点，封存诊断后再修复。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "run_test":
            return self._run_test(action)
        if tool == "seal_diagnosis":
            return self._seal(action)
        if tool == "repair":
            return self._repair(action)
        if tool == "wait":
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _run_test(self, action: V8Action) -> str:
        test_id = action.test_id
        if test_id not in TESTS:
            return "UNKNOWN_TEST"
        if test_id in self.tests_run:
            return "TEST_ALREADY_RUN"
        self.tests_run.append(str(test_id))
        return f"TEST_RESULT:{test_id}={self.variant.reading(str(test_id), self.variant.leak)}"

    def _seal(self, action: V8Action) -> str:
        code = action.diagnosis_code
        if code not in SITES:
            return "UNKNOWN_SITE"
        candidates = self.candidates()
        if len(candidates) != 1:
            return "DIAGNOSIS_INCOMPLETE"
        if code not in candidates:
            return "DIAGNOSIS_MISMATCH"
        self.sealed = str(code)
        self.sealed_candidates = len(candidates)
        return f"DIAGNOSIS_SEALED:{code}"

    def _repair(self, action: V8Action) -> str:
        target = action.target_id
        if target not in SITES:
            return "UNKNOWN_SITE"
        if self.sealed is None:
            self.unjustified += 1
            return "DIAGNOSIS_REQUIRED"
        if self.sealed != target:
            self.unjustified += 1
            return "DIAGNOSIS_MISMATCH"
        if target == self.variant.leak:
            self.repaired = True
            self._succeed("LEAK_REPAIRED")
            return "LEAK_REPAIRED"
        self.wrong_repairs += 1
        if self.wrong_repairs >= MAX_WRONG_REPAIRS:
            self._fail("SPARES_EXHAUSTED")
        return "WRONG_SITE"

    def _action_cost(self, action: V8Action) -> int:
        return REPAIR_TICKS if action.tool == "repair" else 1

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if self.tick_count >= DEADLINE and not self.repaired:
            self._fail("DEADLINE_EXCEEDED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "tests_run": list(self.tests_run),
            "candidates": sorted(self.candidates()),
            "sealed": self.sealed,
            "sealed_candidates": self.sealed_candidates,
            "wrong_repairs": self.wrong_repairs,
            "unjustified": self.unjustified,
            "repaired": self.repaired,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
        if self.sealed_candidates is None:
            reduction: MValue = not_applicable("未封存诊断")
        else:
            denominator = len(SITES) - 1
            reduction = ratio(len(SITES) - self.sealed_candidates, denominator)
        return {
            "map08.v10.mission_success": success,
            "map08.v10.hypothesis_reduction": reduction,
            "map08.v10.tests_used": valid(len(self.tests_run)),
            "map08.v10.wrong_repairs": valid(self.wrong_repairs),
            "map08.v10.unjustified_repairs": valid(self.unjustified),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：测试把候选集缩成唯一站点并封存。"""

        return self.sealed is not None


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：取能唯一识别的最小测试子集，封存后修复。"""

    variant = VARIANTS[environment_seed]
    chosen: tuple[str, ...] = TESTS
    for size in range(0, len(TESTS) + 1):
        found = False
        for subset in combinations(TESTS, size):
            codes = {
                tuple(variant.partitions[test][site] for test in subset) for site in SITES
            }
            if len(codes) == len(SITES):
                chosen = subset
                found = True
                break
        if found:
            break
    actions: list[dict[str, Any]] = [
        {"tool": "run_test", "test_id": test} for test in chosen
    ]
    actions.append({"tool": "seal_diagnosis", "diagnosis_code": variant.leak})
    actions.append({"tool": "repair", "target_id": variant.leak})
    return actions


__all__ = [
    "DEADLINE",
    "Map08V10Environment",
    "SITES",
    "TESTS",
    "VARIANTS",
    "Variant08",
    "oracle_actions",
]
