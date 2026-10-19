"""Batch 9 补强：截尾口径归一（DCR-V10-26）的单元测试。"""

from __future__ import annotations

from agent_arena.v10.metrics.governance import truncation_censored


def _metrics(**states: str) -> dict[str, dict[str, object]]:
    return {
        key: {"state": value, "value": 1.0 if value == "VALID" else None}
        for key, value in states.items()
    }


def test_truncated_valid_becomes_censored_when_spec_says_so() -> None:
    # MAP-10 mission_success 的 censored_rule 是「截尾 → CENSORED」
    metrics = _metrics(**{"map10.v10.mission_success": "VALID"})
    normalized = truncation_censored("MAP-10", metrics, truncated=True)
    assert normalized["map10.v10.mission_success"]["state"] == "CENSORED"
    assert normalized["map10.v10.mission_success"]["value"] is None


def test_partial_progress_metrics_stay_valid() -> None:
    # MAP-18 service_rate 的规则是「部分送达在截尾/失败时仍 VALID」
    metrics = _metrics(**{"map18.v10.service_rate": "VALID"})
    normalized = truncation_censored("MAP-18", metrics, truncated=True)
    assert normalized["map18.v10.service_rate"]["state"] == "VALID"


def test_not_applicable_becomes_censored_only_when_zero_rule_says_so() -> None:
    # MAP-30 q4_recall_accuracy：zero_denominator 含「截尾 → CENSORED」
    metrics = _metrics(**{"map30.v10.q4_recall_accuracy": "NOT_APPLICABLE"})
    normalized = truncation_censored("MAP-30", metrics, truncated=True)
    assert normalized["map30.v10.q4_recall_accuracy"]["state"] == "CENSORED"
    # MAP-30 evidence_chain_coverage：zero 只写 NOT_APPLICABLE → 不改
    metrics = _metrics(**{"map30.v10.evidence_chain_coverage": "NOT_APPLICABLE"})
    normalized = truncation_censored("MAP-30", metrics, truncated=True)
    assert normalized["map30.v10.evidence_chain_coverage"]["state"] == "NOT_APPLICABLE"


def test_not_truncated_is_untouched() -> None:
    metrics = _metrics(**{"map10.v10.mission_success": "VALID"})
    assert truncation_censored("MAP-10", metrics, truncated=False) is metrics


def test_v8_fallback_maps_are_untouched() -> None:
    metrics = _metrics(**{"legacy.metric": "VALID"})
    assert truncation_censored("MAP-16", metrics, truncated=True) is metrics


def test_unknown_metric_ids_pass_through() -> None:
    metrics = _metrics(**{"map10.v10.not_registered": "VALID"})
    normalized = truncation_censored("MAP-10", metrics, truncated=True)
    assert normalized["map10.v10.not_registered"]["state"] == "VALID"
