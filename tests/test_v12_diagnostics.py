"""V12 诊断测试：证据定位、否定 fixture、降级与轨迹 Diff。"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.lab.diagnostics import (
    NOT_ENOUGH_EVIDENCE,
    diagnose_run,
    diff_hypotheses,
    pairwise_diff,
    summarize_findings,
)


def _step(
    index: int,
    tool: str,
    *,
    result: str = "OK",
    observation: dict[str, Any] | None = None,
    action_extra: dict[str, Any] | None = None,
    invalid: bool = False,
) -> dict[str, Any]:
    action: dict[str, Any]
    if invalid:
        action = {"invalid_output": {"bad": True}}
    else:
        action = {"tool": tool, **(action_extra or {})}
    return {
        "event": "decision",
        "decision_index": index,
        "action": action,
        "result": result,
        "status": "running",
        "observation_after": observation or {},
    }


def _result(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "map_id": "MAP-22",
        "state": "FAILED",
        "outcome": "scenario_failure",
        "success": False,
        "mechanism_triggered": False,
        "metrics": {},
    }
    payload.update(overrides)
    return payload


def test_repeated_action_loop_points_at_every_step() -> None:
    steps = [_step(index, "move", action_extra={"bearing": "west"}) for index in range(1, 5)]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    loops = [item for item in findings if item.category == "repeated_action_loop"]
    assert loops, [item.category for item in findings]
    assert loops[0].evidence_steps == (1, 2, 3, 4)
    assert loops[0].evidence_event_ids == ("step-1", "step-2", "step-3", "step-4")


def test_repeated_rejected_action_is_distinguished() -> None:
    steps = [
        _step(index, "move", result="BEARING_NOT_AVAILABLE", action_extra={"bearing": "nowhere"})
        for index in range(1, 4)
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    assert any(item.category == "repeated_rejected_action" for item in findings)


def test_no_progress_window_uses_public_progress() -> None:
    observation = {"moves_used": 2, "tick": 2}
    steps = [
        _step(index, "observe_signpost", observation=dict(observation)) for index in range(1, 6)
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    assert any(item.category == "no_progress_window" for item in findings)


def test_contract_artifact_when_invalid_dominates() -> None:
    steps = [_step(index, "<invalid>", invalid=True) for index in range(1, 5)]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    artifact = [item for item in findings if item.category == "contract_artifact"]
    assert artifact and artifact[0].severity == "critical"
    assert artifact[0].confidence_scope == "interface_not_behavior"


def test_provider_error_is_not_a_strategy_failure() -> None:
    findings = diagnose_run(
        map_id="MAP-22",
        run_id="r",
        steps=[],
        result=_result(state="PROVIDER_ERROR", outcome="provider_error"),
    )
    categories = {item.category for item in findings}
    assert "provider_error" in categories
    assert "repeated_action_loop" not in categories
    provider = next(item for item in findings if item.category == "provider_error")
    assert provider.confidence_scope == "infrastructure_not_behavior"


def test_budget_censored_is_informational() -> None:
    findings = diagnose_run(
        map_id="MAP-22",
        run_id="r",
        steps=[],
        result=_result(state="BUDGET_REACHED", outcome="decision_budget_exhausted"),
    )
    assert any(item.category == "budget_censored" and item.severity == "info" for item in findings)


def test_clean_run_returns_not_enough_evidence() -> None:
    steps = [
        _step(1, "move", observation={"moves_used": 1, "current_sign": "a"}),
        _step(2, "move", observation={"moves_used": 2, "current_sign": "b"}),
    ]
    findings = diagnose_run(
        map_id="MAP-01",
        run_id="r",
        steps=steps,
        result=_result(map_id="MAP-01", mechanism_triggered=True, success=True, state="SUCCEEDED"),
    )
    assert findings
    assert findings[0].category == NOT_ENOUGH_EVIDENCE


def test_map08_flags_repair_without_tests() -> None:
    steps = [
        _step(1, "repair", result="REPAIRED", observation={"tick": 2}),
    ]
    findings = diagnose_run(
        map_id="MAP-08", run_id="r", steps=steps, result=_result(map_id="MAP-08")
    )
    assert any(item.category == "unused_public_tests" for item in findings)


def test_map08_flags_premature_seal() -> None:
    steps = [
        _step(
            1,
            "seal_diagnosis",
            result="INVALID_SEAL",
            observation={"candidate_sites": ["S1", "S2"]},
        )
    ]
    findings = diagnose_run(
        map_id="MAP-08", run_id="r", steps=steps, result=_result(map_id="MAP-08")
    )
    assert any(item.category == "premature_commit" for item in findings)


def test_map16_flags_frame_mismatch() -> None:
    steps = [_step(1, "move_train", result="NO_ROUTE", observation={"tick": 1})]
    findings = diagnose_run(
        map_id="MAP-16", run_id="r", steps=steps, result=_result(map_id="MAP-16")
    )
    assert any(item.category == "frame_mismatch" for item in findings)


def test_map18_flags_window_violation() -> None:
    steps = [_step(1, "set_timetable", result="DISPATCH_WINDOW_VIOLATION", observation={"tick": 2})]
    findings = diagnose_run(
        map_id="MAP-18", run_id="r", steps=steps, result=_result(map_id="MAP-18")
    )
    assert any(item.category == "window_violation" for item in findings)


def test_map22_flags_missing_memory() -> None:
    steps = [
        _step(1, "move", observation={"moves_used": 1, "current_sign": "a"}),
        _step(2, "move", observation={"moves_used": 2, "current_sign": "b"}),
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    assert any(item.category == "memory_not_used" for item in findings)


def test_map22_memory_without_bearing_is_flagged() -> None:
    """写入成功但键名不在指标口径内 → 单独一类诊断（不是"没用记忆"）。"""

    steps = [
        _step(
            1,
            "write_memory",
            result="MEMORY_WRITTEN",
            action_extra={"facts": [{"key": "note", "value": "x"}]},
            observation={"moves_used": 1},
        )
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    categories = {item.category for item in findings}
    assert "memory_key_not_in_metric" in categories
    assert "memory_not_used" not in categories
    metric_finding = next(
        item for item in findings if item.category == "memory_key_not_in_metric"
    )
    assert "bearing" in metric_finding.summary or "bearing" in metric_finding.detail
    assert metric_finding.confidence_scope == "metric_coverage_not_behavior"


def test_map22_rejected_payload_is_an_interface_finding() -> None:
    steps = [
        _step(
            1,
            "write_memory",
            result="INVALID_MEMORY_PAYLOAD",
            action_extra={"facts": [{"at_sign": "x"}]},
            observation={"moves_used": 1},
        )
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    payload = [item for item in findings if item.category == "memory_payload_rejected"]
    assert payload
    assert payload[0].confidence_scope == "interface_not_behavior"


def test_map22_no_writes_at_all_is_memory_not_used() -> None:
    steps = [
        _step(1, "move", observation={"moves_used": 1, "current_sign": "a"}),
        _step(2, "move", observation={"moves_used": 2, "current_sign": "b"}),
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    assert any(item.category == "memory_not_used" for item in findings)


def test_map22_short_sequence_is_flagged_separately() -> None:
    """键名合规但只写 1 个方位、实际走了 6 步 → memory_sequence_short。"""

    steps = [
        _step(
            1,
            "write_memory",
            result="MEMORY_WRITTEN",
            action_extra={"facts": [{"key": "path_state", "value": "north"}]},
            observation={"moves_used": 0},
        )
    ]
    steps += [
        _step(index, "move", action_extra={"bearing": "north"}, observation={"moves_used": index})
        for index in range(2, 8)
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    categories = {item.category for item in findings}
    assert "memory_sequence_short" in categories
    assert "memory_key_not_in_metric" not in categories
    finding = next(item for item in findings if item.category == "memory_sequence_short")
    assert "6" in finding.summary
    assert finding.confidence_scope == "behavior_observed_not_internal_cause"


def test_map22_full_sequence_is_not_flagged() -> None:
    """写满路线的局不应报"序列过短"。"""

    route = ["north", "east", "south"]
    steps = [
        _step(
            1,
            "write_memory",
            result="MEMORY_WRITTEN",
            action_extra={"facts": [{"key": "path_state", "value": ",".join(route)}]},
            observation={"moves_used": 0},
        )
    ]
    steps += [
        _step(index + 2, "move", action_extra={"bearing": b}, observation={"moves_used": index + 1})
        for index, b in enumerate(route)
    ]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    assert not any(item.category == "memory_sequence_short" for item in findings)


def test_map26_flags_blind_swap() -> None:
    steps = [_step(1, "replace", result="PART_INSTALLED", action_extra={"part_id": "P1"})]
    findings = diagnose_run(
        map_id="MAP-26", run_id="r", steps=steps, result=_result(map_id="MAP-26")
    )
    assert any(item.category == "blind_swap" for item in findings)


def test_map30_flags_rejected_accusation() -> None:
    steps = [_step(1, "formal_accuse", result="EVIDENCE_MISSING")]
    findings = diagnose_run(
        map_id="MAP-30", run_id="r", steps=steps, result=_result(map_id="MAP-30")
    )
    accusation = [item for item in findings if item.category == "unsupported_accusation"]
    assert accusation and accusation[0].severity == "critical"


def test_findings_are_sorted_by_severity() -> None:
    steps = [_step(index, "<invalid>", invalid=True) for index in range(1, 5)]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    severities = [item.severity for item in findings]
    order = {"critical": 0, "warning": 1, "info": 2}
    assert severities == sorted(severities, key=lambda item: order[item])


def test_findings_do_not_leak_hidden_truth() -> None:
    steps = [_step(1, "move", observation={"moves_used": 1, "current_sign": "a"})]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    text = json.dumps([item.as_dict() for item in findings], ensure_ascii=False).lower()
    for forbidden in ("sealed_truth", "judge_state", "truth_seal", "oracle"):
        assert forbidden not in text


# ------------------------------------------------------------------- trace diff
def test_pairwise_diff_finds_first_divergence() -> None:
    left = [
        _step(1, "observe_signpost", observation={"tick": 1}),
        _step(2, "move", action_extra={"bearing": "west"}, observation={"tick": 2}),
    ]
    right = [
        _step(1, "observe_signpost", observation={"tick": 1}),
        _step(2, "write_memory", action_extra={"facts": []}, observation={"tick": 2}),
    ]
    diff = pairwise_diff(
        pairing_key="MAP-22|seed=0",
        left_run_id="l",
        right_run_id="r",
        left_agent="basic.v1",
        right_agent="memory.v1",
        left_steps=left,
        right_steps=right,
    )
    assert diff.first_divergence_step == 2
    assert "首次出现不同行为" in diff.first_divergence_summary
    assert diff.verdict == "COMPARABLE"


def test_pairwise_diff_handles_length_mismatch_without_naive_subtraction() -> None:
    left = [_step(index, "observe_signpost", observation={"tick": index}) for index in range(1, 4)]
    right = [_step(1, "observe_signpost", observation={"tick": 1})]
    diff = pairwise_diff(
        pairing_key="MAP-22|seed=0",
        left_run_id="l",
        right_run_id="r",
        left_agent="basic.v1",
        right_agent="memory.v1",
        left_steps=left,
        right_steps=right,
    )
    assert diff.first_divergence_step == 2
    assert diff.first_divergence_anchor == "长度差异"


def test_pairwise_diff_identical_sequences() -> None:
    steps = [_step(1, "observe_signpost", observation={"tick": 1})]
    diff = pairwise_diff(
        pairing_key="MAP-22|seed=0",
        left_run_id="l",
        right_run_id="r",
        left_agent="basic.v1",
        right_agent="memory.v1",
        left_steps=steps,
        right_steps=list(steps),
    )
    assert diff.first_divergence_step is None
    assert "完全一致" in diff.first_divergence_summary


def test_pairwise_diff_reports_metric_deltas_and_hypotheses() -> None:
    left_result = {"success": True, "metrics": {"m": {"state": "VALID", "value": 1}}}
    right_result = {"success": False, "metrics": {"m": {"state": "CENSORED", "value": None}}}
    diff = pairwise_diff(
        pairing_key="MAP-22|seed=0",
        left_run_id="l",
        right_run_id="r",
        left_agent="basic.v1",
        right_agent="memory.v1",
        left_steps=[_step(1, "move", observation={"tick": 1})],
        right_steps=[_step(1, "move", observation={"tick": 1})],
        left_result=left_result,
        right_result=right_result,
    )
    assert diff.stage_deltas[0]["metric_id"] == "m"
    hypotheses = diff_hypotheses(diff)
    assert any(item["kind"] == "hypothesis" for item in hypotheses)
    assert all("内部" not in item["text"] for item in hypotheses)


def test_summarize_findings_groups_by_severity() -> None:
    steps = [_step(index, "<invalid>", invalid=True) for index in range(1, 5)]
    findings = diagnose_run(map_id="MAP-22", run_id="r", steps=steps, result=_result())
    summary = summarize_findings(findings)
    assert summary["total"] == len(findings)
    assert summary["by_severity"]["critical"] >= 1
    assert summary["critical"]
