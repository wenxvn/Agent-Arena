"""V12 聚合与配对比较测试：分母、五态、版本门禁与不可比处理。"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.compare import (
    CATEGORY_BUDGET_CENSORED,
    CATEGORY_CANCELLED,
    CATEGORY_INTERRUPTED,
    CATEGORY_MECHANISM_FAILURE,
    CATEGORY_PROVIDER_ERROR,
    CATEGORY_SUCCESS,
    VERDICT_COMPARABLE,
    VERDICT_DESCRIPTIVE,
    VERDICT_INCOMPARABLE,
    aggregate_arm,
    aggregate_metrics,
    build_comparison,
    classify_child,
    pair_records,
    run_record,
)
from agent_arena.lab.contracts import ComparisonPolicy
from agent_arena.v10.metrics.governance import schema_hash
from agent_arena.v10.runtime.catalog import metric_hash, rule_hash

MAP = "MAP-22"


def _record(
    agent: str,
    *,
    seed: int = 0,
    map_id: str = MAP,
    state: str = "SUCCEEDED",
    success: bool = True,
    outcome: str = "success",
    decisions: int = 10,
    requests: int = 10,
    cost: str | None = "0.01",
    cost_known: bool = True,
    metrics: dict[str, Any] | None = None,
    model: str = "mimo-v2.6-flash",
    rule: str | None = None,
    metric: str | None = None,
    schema: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id or f"run-{agent}-{seed}",
        "matrix_index": 0,
        "map_id": map_id,
        "environment_seed": seed,
        "agent_id": agent,
        "agent_version": "1.0.0",
        "agent_config_hash": "h",
        "state": state,
        "outcome": outcome,
        "termination": "",
        "category": classify_child(state, {"outcome": outcome}),
        "success": success,
        "decisions": decisions,
        "decision_budget": 80,
        "requests": requests,
        "input_tokens": 1000,
        "output_tokens": 100,
        "latency_ms": 1200,
        "cost_cny": float(cost) if cost is not None else None,
        "cost_known": cost_known and cost is not None,
        "rejected_actions": 1,
        "invalid_actions": 0,
        "mechanism_triggered": False,
        "primary_metric": "map22.v10.mission_success",
        "primary_state": "VALID",
        "primary_value": 1 if success else 0,
        "metrics": metrics or {},
        "mode": "live",
        "provider_id": "openai_compatible",
        "model": model,
        "rule_hash": rule or rule_hash(map_id),
        "metric_hash": metric or metric_hash(map_id),
        "metric_schema_hash": schema or schema_hash(),
        "agent_events": 0,
        "partial": False,
    }


def test_classify_child_separates_provider_and_mechanism_failures() -> None:
    assert classify_child("SUCCEEDED", {"outcome": "success"}) == CATEGORY_SUCCESS
    assert classify_child("FAILED", {"outcome": "scenario_failure"}) == CATEGORY_MECHANISM_FAILURE
    assert classify_child("FAILED", {"outcome": "policy_error"}) == "invalid_run"
    assert (
        classify_child("PROVIDER_ERROR", {"outcome": "provider_error"})
        == CATEGORY_PROVIDER_ERROR
    )
    assert classify_child("BUDGET_REACHED", {}) == CATEGORY_BUDGET_CENSORED
    assert classify_child("CANCELLED", {}) == CATEGORY_CANCELLED
    assert classify_child("INTERRUPTED", {}) == CATEGORY_INTERRUPTED


def test_valid_denominator_excludes_provider_errors() -> None:
    records = [
        _record("basic.v1"),
        _record("basic.v1", seed=1, state="FAILED", success=False, outcome="scenario_failure"),
        _record(
            "basic.v1",
            seed=2,
            state="PROVIDER_ERROR",
            success=False,
            outcome="provider_error",
        ),
        _record("basic.v1", seed=3, state="CANCELLED", success=False, outcome="cancelled"),
        _record("basic.v1", seed=4, state="INTERRUPTED", success=False, outcome="interrupted"),
    ]
    arm = aggregate_arm("basic.v1", records, map_id=MAP)
    assert arm.runs == 5
    assert arm.valid_denominator == 2
    assert arm.successes == 1
    assert arm.success_rate == 0.5
    assert arm.provider_errors == 1
    assert arm.cancelled == 1
    assert arm.interrupted == 1


def test_metrics_do_not_fill_zero_for_missing_states() -> None:
    metrics = {
        "map22.v10.route_recall": {"state": "NOT_APPLICABLE", "value": None},
        "map22.v10.mission_success": {"state": "CENSORED", "value": None},
    }
    records = [_record("basic.v1", metrics=metrics)]
    aggregated = aggregate_metrics(MAP, records)
    assert aggregated["map22.v10.route_recall"]["mean"] is None
    assert aggregated["map22.v10.route_recall"]["valid_count"] == 0
    assert aggregated["map22.v10.mission_success"]["mean"] is None
    assert aggregated["map22.v10.mission_success"]["states"] == {"CENSORED": 1}
    assert "不补零" in aggregated["map22.v10.route_recall"]["not_computed_reason"]


def test_metrics_pool_ratios_from_numerator_denominator() -> None:
    metrics = {
        "map22.v10.route_recall": {
            "state": "VALID",
            "value": 0.5,
            "numerator": 2,
            "denominator": 4,
        }
    }
    records = [
        _record("basic.v1", metrics=metrics),
        _record("basic.v1", seed=1, metrics={
            "map22.v10.route_recall": {
                "state": "VALID",
                "value": 1.0,
                "numerator": 4,
                "denominator": 4,
            }
        }),
    ]
    aggregated = aggregate_metrics(MAP, records)
    row = aggregated["map22.v10.route_recall"]
    assert row["valid_count"] == 2
    assert row["mean"] == 0.75
    assert row["pooled_ratio"] == 0.75


def test_pair_records_requires_same_map_and_seed() -> None:
    records = [
        _record("basic.v1", seed=0),
        _record("memory.v1", seed=0),
        _record("basic.v1", seed=1),
        _record("memory.v1", seed=2),
    ]
    slots = pair_records(
        records, ComparisonPolicy(), left_agent="basic.v1", right_agent="memory.v1"
    )
    assert len(slots) == 1
    assert slots[0].pairing_key == f"{MAP}|seed=0"
    assert slots[0].verdict == VERDICT_COMPARABLE


def test_comparison_is_comparable_with_three_pairs() -> None:
    records = [
        _record(agent, seed=seed)
        for agent in ("basic.v1", "memory.v1", "planning.v1")
        for seed in (0, 1, 2)
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_COMPARABLE
    assert result.reasons == ()
    assert len(result.pairs) == 3 * 3
    assert all("描述性" in note for note in result.notes)


def test_comparison_is_descriptive_with_one_pair() -> None:
    records = [
        _record("basic.v1", seed=0),
        _record("memory.v1", seed=0),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_DESCRIPTIVE
    assert any("低于" in note for note in result.notes)


def test_comparison_is_incomparable_across_models() -> None:
    records = [
        _record("basic.v1", model="mimo-v2.6-flash"),
        _record("memory.v1", model="qwen2.5:7b"),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_INCOMPARABLE
    assert any("模型不一致" in reason for reason in result.reasons)


def test_comparison_is_incomparable_across_rule_versions() -> None:
    records = [
        _record("basic.v1", rule="rule-a"),
        _record("memory.v1", rule="rule-b"),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_INCOMPARABLE
    assert any("rule_hash" in reason for reason in result.reasons)


def test_comparison_flags_metric_schema_drift() -> None:
    records = [
        _record("basic.v1", schema="old-schema"),
        _record("memory.v1", schema=schema_hash()),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_INCOMPARABLE
    assert any("指标 schema" in reason for reason in result.reasons)


def test_comparison_is_incomparable_with_single_arm() -> None:
    records = [_record("basic.v1", seed=seed) for seed in (0, 1, 2)]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_INCOMPARABLE
    assert any("少于两个实验臂" in reason for reason in result.reasons)


def test_unequal_seed_coverage_reduces_pairs() -> None:
    records = [
        _record("basic.v1", seed=0),
        _record("basic.v1", seed=1),
        _record("memory.v1", seed=0),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert len(result.pairs) == 1
    assert result.verdict == VERDICT_DESCRIPTIVE


def test_all_failures_still_produces_valid_denominator() -> None:
    records = [
        _record(
            agent,
            seed=seed,
            state="FAILED",
            success=False,
            outcome="scenario_failure",
        )
        for agent in ("basic.v1", "memory.v1")
        for seed in (0, 1, 2)
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_COMPARABLE
    for arm in result.arms:
        assert arm["valid_denominator"] == 3
        assert arm["successes"] == 0
        assert arm["success_rate"] == 0.0
        assert arm["mechanism_failures"] == 3


def test_all_successes_report_ceiling_without_claiming_superiority() -> None:
    records = [
        _record(agent, seed=seed)
        for agent in ("basic.v1", "planning.v1")
        for seed in (0, 1, 2)
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_COMPARABLE
    assert all(arm["success_rate"] == 1.0 for arm in result.arms)
    assert not any("提升" in note for note in result.notes)


def test_unknown_cost_excludes_cost_comparison() -> None:
    records = [
        _record("basic.v1", seed=0, cost=None, cost_known=False),
        _record("memory.v1", seed=0, cost="0.02"),
    ]
    result = build_comparison(
        experiment_id="lab-x", records=records, policy=ComparisonPolicy()
    )
    assert result.verdict == VERDICT_INCOMPARABLE
    assert any("费用未知" in reason for reason in result.reasons)
    arm = next(item for item in result.arms if item["agent_id"] == "basic.v1")
    assert arm["mean_cost_cny"] is None
    assert arm["cost_known_runs"] == 0


def test_run_record_normalizes_manifest_and_result() -> None:
    manifest = {
        "state": "SUCCEEDED",
        "config": {"agent": "basic.v1"},
        "map_id": MAP,
        "environment_seed": 1,
        "hashes": {"rule_hash": "r", "metric_hash": "m", "metric_schema_hash": "s"},
    }
    result = {
        "state": "SUCCEEDED",
        "map_id": MAP,
        "environment_seed": 1,
        "agent": "basic.v1",
        "agent_version": "1.0.0",
        "success": True,
        "decision_count": 7,
        "metrics": {},
        "usage": {"requests": 8, "cost_settled_cny": "0.003", "cost_unknown": False},
    }
    record = run_record(run_id="r1", matrix_index=3, manifest=manifest, result=result)
    assert record["category"] == CATEGORY_SUCCESS
    assert record["requests"] == 8
    assert record["cost_cny"] == 0.003
    assert record["cost_known"] is True
    assert record["rule_hash"] == "r"
