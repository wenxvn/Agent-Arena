"""独立复算：MAP-25（其余地图见 part_a/part_c/part_d）。"""

from __future__ import annotations

from agent_arena.v9.metric_checks.base import Check, EvidenceRun


def map25_coverage(run: EvidenceRun) -> float | None:
    done = run.judge_state.get("required_done")
    if not isinstance(done, list):
        return None
    return len(done) / 7


def map25_dependency_order(run: EvidenceRun) -> float | None:
    correct = run.judge_state.get("required_correct")
    attempted = run.judge_state.get("required_attempted")
    if not isinstance(correct, int) or not isinstance(attempted, int) or attempted <= 0:
        return None
    return correct / attempted


CHECKS: dict[str, list[Check]] = {
    "MAP-25": [
        Check(
            "map25.required_check_coverage",
            map25_coverage,
            "required_done 列表长度/7（注意：被拒 diagnose 也被记入，见审计 §6）",
        ),
        Check(
            "map25.dependency_order_correctness",
            map25_dependency_order,
            "required_correct/required_attempted",
            kind="diagnostic",
        ),
    ]
}

__all__ = ["CHECKS"]
