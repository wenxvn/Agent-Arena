"""MAP-26 V10｜失败的维修计划：诊断与盲换的质量分离（DCR-V10-17）。

V9 的证据：修复后 1/1 成功，但 `no_diagnosis` **也成功**——诊断只是省事，不是必需。
按提纲“若诊断只是节约成本，则按质量指标验收”，V10 保留**盲换为合法策略**，但让它的
代价与风险可复现地更高：

- 三个故障模式 F1/F2/F3 各对应一个备件 P1/P2/P3；换错会消耗该备件、增加 1 点磨损，
  **磨损到 2 即整机不可恢复**；`rollback` 能撤销最后一次更换，但**已消耗的备件不返还**；
- 测试按公开分区表缩小故障候选（`candidate_faults`），诊断不是开门的必要条件，
  但能把“用几个备件、冒多大风险”压到最小；
- 4 个预登记实例：真故障、分区结构、磨损上限都不同。

指标：`mission_success`（主）+ `spares_used` / `wrong_swaps` / `rollbacks`（质量与风险），
因此“盲换成功”与“诊断后一次换对”在指标上可区分。
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

FAULTS = ("F1", "F2", "F3")
PARTS = {"F1": "P1", "F2": "P2", "F3": "P3"}
TESTS = ("T1", "T2")
DEADLINE = 16
MAX_WEAR = 2


class Variant26:
    def __init__(
        self,
        label: str,
        fault: str,
        partitions: dict[str, dict[str, str]],
        spares: dict[str, int],
    ) -> None:
        self.label = label
        self.fault = fault
        self.partitions = partitions
        self.spares = spares

    def reading(self, test_id: str, fault: str) -> str:
        return self.partitions[test_id][fault]

    def minimum_tests(self) -> int:
        for size in range(0, len(TESTS) + 1):
            for subset in combinations(TESTS, size):
                codes = {
                    tuple(self.partitions[test][fault] for test in subset) for fault in FAULTS
                }
                if len(codes) == len(FAULTS):
                    return size
        return len(TESTS)


VARIANTS: dict[int, Variant26] = {
    0: Variant26(
        "binary_then_leaf",
        "F2",
        {
            "T1": {"F1": "A", "F2": "A", "F3": "B"},
            "T2": {"F1": "x", "F2": "y", "F3": "x"},
        },
        {"P1": 1, "P2": 1, "P3": 1},
    ),
    1: Variant26(
        "leaf_first",
        "F3",
        {
            "T1": {"F1": "A", "F2": "B", "F3": "C"},
            "T2": {"F1": "x", "F2": "y", "F3": "z"},
        },
        {"P1": 1, "P2": 1, "P3": 1},
    ),
    2: Variant26(
        "single_test_enough",
        "F1",
        {
            "T1": {"F1": "A", "F2": "B", "F3": "C"},
            "T2": {"F1": "x", "F2": "x", "F3": "y"},
        },
        {"P1": 1, "P2": 1, "P3": 1},
    ),
    3: Variant26(
        "tight_spares",
        "F2",
        {
            "T1": {"F1": "A", "F2": "B", "F3": "B"},
            "T2": {"F1": "x", "F2": "y", "F3": "z"},
        },
        {"P1": 1, "P2": 1, "P3": 0},
    ),
}


class Map26V10Environment(V10Map):
    map_id = "MAP-26"
    title = "失败的维修计划"
    world = "lunar"
    level = "中等"
    RULE_VERSION = "v10.map26.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "run_test": {frozenset({"tool", "test_id"})},
        "read_log": {frozenset({"tool", "log_id"})},
        "replace": {frozenset({"tool", "part_id"})},
        "rollback": {frozenset({"tool"})},
        "restart": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "deadline_tick",
            "faults",
            "parts",
            "available_tests",
            "test_partitions",
            "test_results",
            "candidate_faults",
            "spares",
            "installed_part",
            "wear",
            "max_wear",
            "last_replaced",
            "rollbacks_used",
            "goal",
        }
    )
    PRIMARY_METRIC = "map26.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map26.v10.mission_success",
            "primary",
            "higher",
            "装上与真实故障匹配的备件并重启成功",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map26.v10.spares_used",
            "secondary",
            "lower",
            "消耗的备件数",
            "—",
            unit="count",
            valid_range=(0.0, 6.0),
        ),
        MetricSpec(
            "map26.v10.wrong_swaps",
            "guardrail",
            "lower",
            "换错部件的次数",
            "—",
            unit="count",
            valid_range=(0.0, 6.0),
        ),
        MetricSpec(
            "map26.v10.rollbacks",
            "guardrail",
            "lower",
            "rollback 次数",
            "—",
            unit="count",
            valid_range=(0.0, 6.0),
        ),
        MetricSpec(
            "map26.v10.diagnosis_precision",
            "secondary",
            "higher",
            "第一次更换就正确的 0/1",
            "更换过的局（1）",
            zero_denominator="从未更换 → NOT_APPLICABLE",
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.tests_run: list[str] = []
        self.spares = dict(self.variant.spares)
        self.installed: str | None = None
        self.wear = 0
        self.last_replaced: str | None = None
        self.rollbacks = 0
        self.wrong_swaps = 0
        self.replacements = 0
        self.restarted = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "faults": list(FAULTS),
            "parts": dict(PARTS),
            "tests": list(TESTS),
            "deadline_tick": DEADLINE,
            "max_wear": MAX_WEAR,
            "initial_spares": dict(self.variant.spares),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"label": self.variant.label, "fault": self.variant.fault}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "三种故障 F1/F2/F3 分别需要备件 P1/P2/P3；当前只有一台机器要修。",
            "run_test(test_id) 耗 1 tick，按公开分区返回读数并缩小 candidate_faults。",
            "read_log(log_id) 耗 1 tick，日志会披露一条历史维修记录（不影响候选集）。",
            "replace(part_id) 耗 2 tick：装上备件；若与真实故障匹配，restart 即可恢复。"
            "换错会消耗该备件、磨损 +1。",
            "rollback 撤销最后一次更换，但**已消耗的备件不返还**。",
            f"磨损达到 {MAX_WEAR} 时机器不可恢复；截止 tick {DEADLINE}。",
            "诊断不是开门的必要步骤：盲换也是合法策略，但会更费备件、更容易磨损失败。",
        )

    # ------------------------------------------------------------------ public
    def candidates(self) -> set[str]:
        allowed = set(FAULTS)
        for test_id in self.tests_run:
            reading = self.variant.reading(test_id, self.variant.fault)
            allowed &= {
                fault
                for fault in FAULTS
                if self.variant.partitions[test_id][fault] == reading
            }
        return allowed

    def _public(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "deadline_tick": DEADLINE,
            "faults": list(FAULTS),
            "parts": dict(PARTS),
            "available_tests": [test for test in TESTS if test not in self.tests_run],
            "test_partitions": {
                test: dict(self.variant.partitions[test]) for test in sorted(TESTS)
            },
            "test_results": {
                test: self.variant.reading(test, self.variant.fault) for test in self.tests_run
            },
            "candidate_faults": sorted(self.candidates()),
            "spares": dict(self.spares),
            "installed_part": self.installed,
            "wear": self.wear,
            "max_wear": MAX_WEAR,
            "last_replaced": self.last_replaced,
            "rollbacks_used": self.rollbacks,
            "goal": "用测试判断故障并换上正确备件后重启；盲换也可以，但会更费备件。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._free = False
        tool = action.tool
        if tool == "run_test":
            return self._run_test(action)
        if tool == "read_log":
            return self._read_log(action)
        if tool == "replace":
            return self._replace(action)
        if tool == "rollback":
            return self._rollback()
        if tool == "restart":
            return self._restart()
        return "ACTION_NOT_ALLOWED"

    def _run_test(self, action: V8Action) -> str:
        test_id = action.test_id
        if test_id not in TESTS:
            return "UNKNOWN_TEST"
        if test_id in self.tests_run:
            return "TEST_ALREADY_RUN"
        self.tests_run.append(str(test_id))
        return f"TEST_RESULT:{test_id}={self.variant.reading(str(test_id), self.variant.fault)}"

    def _read_log(self, action: V8Action) -> str:
        log_id = action.log_id
        if not log_id:
            return "UNKNOWN_LOG"
        return f"LOG_READ:{log_id}"

    def _replace(self, action: V8Action) -> str:
        part = action.part_id
        if part is None or part not in PARTS.values():
            return "UNKNOWN_PART"
        if self.spares.get(part, 0) <= 0:
            return "NO_SPARE"
        self.spares[part] -= 1
        self.installed = str(part)
        self.last_replaced = str(part)
        self.replacements += 1
        fault = next(fault for fault, required in PARTS.items() if required == part)
        if fault != self.variant.fault:
            self.wrong_swaps += 1
            self.wear += 1
            if self.wear >= MAX_WEAR:
                self._fail("UNIT_UNRECOVERABLE")
                return "UNIT_UNRECOVERABLE"
            return "WRONG_PART"
        return f"PART_INSTALLED:{part}"

    def _rollback(self) -> str:
        if self.last_replaced is None:
            return "NOTHING_TO_ROLLBACK"
        self.rollbacks += 1
        # 备件不返还：rollback 只撤销“装上”的状态
        self.installed = None
        self.last_replaced = None
        return "ROLLED_BACK"

    def _restart(self) -> str:
        if self.installed is None:
            return "NO_PART_INSTALLED"
        fault = next(fault for fault, required in PARTS.items() if required == self.installed)
        if fault != self.variant.fault:
            return "STILL_FAULTY"
        self.restarted = True
        self._succeed("UNIT_RESTORED")
        return "UNIT_RESTORED"

    def _action_cost(self, action: V8Action) -> int:
        return 2 if action.tool == "replace" else 1

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if self.tick_count >= DEADLINE and not self.restarted:
            self._fail("DEADLINE_EXCEEDED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "tests_run": list(self.tests_run),
            "candidates": sorted(self.candidates()),
            "spares": dict(self.spares),
            "installed": self.installed,
            "wear": self.wear,
            "wrong_swaps": self.wrong_swaps,
            "replacements": self.replacements,
            "rollbacks": self.rollbacks,
            "restarted": self.restarted,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
        used = sum(self.variant.spares.values()) - sum(self.spares.values())
        if self.replacements == 0:
            precision: MValue = (
                censored("未更换") if running else not_applicable("从未更换")
            )
        else:
            precision = valid(int(self.wrong_swaps == 0))
        return {
            "map26.v10.mission_success": success,
            "map26.v10.spares_used": valid(used),
            "map26.v10.wrong_swaps": valid(self.wrong_swaps),
            "map26.v10.rollbacks": valid(self.rollbacks),
            "map26.v10.diagnosis_precision": precision,
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少执行过一次测试（诊断通道被使用）。"""

        return bool(self.tests_run)


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：取最小识别测试子集，换对应备件并重启。"""

    variant = VARIANTS[environment_seed]
    chosen: tuple[str, ...] = TESTS
    for size in range(0, len(TESTS) + 1):
        found = False
        for subset in combinations(TESTS, size):
            codes = {
                tuple(variant.partitions[test][fault] for test in subset) for fault in FAULTS
            }
            if len(codes) == len(FAULTS):
                chosen = subset
                found = True
                break
        if found:
            break
    part = PARTS[variant.fault]
    actions: list[dict[str, Any]] = [
        {"tool": "run_test", "test_id": test} for test in chosen
    ]
    actions.append({"tool": "replace", "part_id": part})
    actions.append({"tool": "restart"})
    return actions


__all__ = [
    "DEADLINE",
    "FAULTS",
    "MAX_WEAR",
    "Map26V10Environment",
    "PARTS",
    "TESTS",
    "VARIANTS",
    "Variant26",
    "oracle_actions",
]
