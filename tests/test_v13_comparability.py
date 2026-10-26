"""V13 可比性测试：画像、单变量检查、跨实验配对与版本硬拒绝。"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.contracts import ComparisonPolicy
from agent_arena.lab.v13.comparability import (
    VERDICT_COMPARABLE,
    VERDICT_DESCRIPTIVE,
    VERDICT_INCOMPARABLE,
    comparability_profile,
    comparable_group_id,
    compare_profiles,
    cross_experiment_pairs,
    refusal_message,
    single_switch_check,
    summarize_pairs,
)


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "web-1",
        "map_id": "MAP-22",
        "environment_seed": 0,
        "replicate_index": 0,
        "mode": "live",
        "provider_id": "openai_compatible",
        "model": "mimo-v2.6-flash",
        "rule_hash": "rule",
        "metric_hash": "metric",
        "metric_schema_hash": "schema",
        "base_prompt_hash": "base",
        "prompt_hash": "effective",
        "agent_id": "memory.v2",
        "agent_version": "2.0.0",
        "agent_config_hash": "cfg-a",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "decision_cap": 90,
        "history_window": 5,
        "success": True,
        "category": "completed_success",
        "cost_cny": 0.01,
        "cost_known": True,
        "decisions": 10,
        "experiment_id": "lab-a",
    }
    base.update(overrides)
    return base


def test_profile_marks_unknown_fields_instead_of_guessing() -> None:
    profile = comparability_profile({"map_id": "MAP-22"})
    assert profile["model_revision"] == "UNKNOWN"
    assert profile["action_contract_version"] == "UNKNOWN"
    assert profile["sampling_support"] == "UNKNOWN"


def test_same_condition_same_group_id() -> None:
    left = comparability_profile(_record())
    right = comparability_profile(_record(agent_config_hash="cfg-b", prompt_hash="other"))
    assert comparable_group_id(left) == comparable_group_id(right)
    verdict = compare_profiles(left, right)
    assert verdict["verdict"] == VERDICT_COMPARABLE
    assert verdict["same_condition_group"] is True
    assert "agent_config_hash" in verdict["manipulated_variables"]


def test_rule_hash_mismatch_is_hard_incomparable() -> None:
    left = comparability_profile(_record())
    right = comparability_profile(_record(rule_hash="rule-2"))
    verdict = compare_profiles(left, right)
    assert verdict["verdict"] == VERDICT_INCOMPARABLE
    assert any("rule_hash" in reason for reason in verdict["hard_mismatches"])
    assert "不可做因果比较" in refusal_message(verdict)


def test_missing_budget_fields_only_downgrade_to_descriptive() -> None:
    left = comparability_profile(_record(request_cap=90))
    right = comparability_profile(_record(request_cap=None))
    verdict = compare_profiles(left, right)
    assert verdict["verdict"] == VERDICT_DESCRIPTIVE
    assert verdict["hard_mismatches"] == []


def test_single_switch_check_accepts_one_switch() -> None:
    check = single_switch_check(
        {"agent_id": "memory.v2", "config": {"enabled": True, "route_log": False}},
        {"agent_id": "memory.v2", "config": {"enabled": True, "route_log": True}},
    )
    assert check.ok
    assert check.manipulated_variable == "route_log"
    assert check.kind == "single_switch"


def test_single_switch_check_rejects_multiple_switches() -> None:
    check = single_switch_check(
        {"agent_id": "memory.v2", "config": {"enabled": True, "route_log": False}},
        {"agent_id": "memory.v2", "config": {"enabled": False, "route_log": True}},
    )
    assert not check.ok
    assert check.kind == "multi_switch"
    assert set(check.changed_keys) == {"enabled", "route_log"}


def test_single_switch_check_treats_version_bump_as_version_compare() -> None:
    check = single_switch_check(
        {"agent_id": "memory.v1", "config": {"enabled": True}},
        {"agent_id": "memory.v2", "config": {"enabled": True}},
    )
    assert not check.ok
    assert check.kind == "version_compare"


def test_single_switch_check_rejects_identical_configs() -> None:
    check = single_switch_check(
        {"agent_id": "memory.v2", "config": {"enabled": True}},
        {"agent_id": "memory.v2", "config": {"enabled": True}},
    )
    assert not check.ok
    assert check.kind == "no_intervention"


def test_cross_experiment_pairs_match_replicate_index() -> None:
    left = [
        _record(run_id="L0", experiment_id="lab-a", agent_config_hash="cfg-on"),
        _record(run_id="L1", experiment_id="lab-a", agent_config_hash="cfg-on", replicate_index=1),
    ]
    right = [
        _record(run_id="R0", experiment_id="lab-b", agent_config_hash="cfg-off", success=False,
                category="mechanism_failure"),
        _record(run_id="R1", experiment_id="lab-b", agent_config_hash="cfg-off", success=False,
                category="mechanism_failure", replicate_index=1),
    ]
    pairs = cross_experiment_pairs(
        left,
        right,
        left_agent="memory.v2",
        right_agent="memory.v2",
        left_arm={"agent_id": "memory.v2", "config": {"enabled": True}},
        right_arm={"agent_id": "memory.v2", "config": {"enabled": False}},
    )
    assert len(pairs) == 2
    assert {pair.replicate_index for pair in pairs} == {0, 1}
    assert all(pair.verdict == VERDICT_COMPARABLE for pair in pairs)
    summary = summarize_pairs(pairs)
    assert summary["comparable"] == 2
    assert summary["by_seed"][0]["paired_difference"] == -1.0


def test_cross_experiment_pairs_reject_multi_switch() -> None:
    left = [_record(run_id="L0")]
    right = [_record(run_id="R0", agent_config_hash="cfg-b")]
    pairs = cross_experiment_pairs(
        left,
        right,
        left_agent="memory.v2",
        right_agent="memory.v2",
        left_arm={"agent_id": "memory.v2", "config": {"enabled": True, "route_log": False}},
        right_arm={"agent_id": "memory.v2", "config": {"enabled": False, "route_log": True}},
    )
    assert pairs[0].verdict == VERDICT_INCOMPARABLE
    assert any("多个开关" in reason for reason in pairs[0].reasons)


def test_policy_require_same_versions_false_downgrades() -> None:
    left = comparability_profile(_record())
    right = comparability_profile(_record(agent_config_hash="cfg-b"))
    verdict = compare_profiles(
        left, right, policy=ComparisonPolicy(require_same_versions=False)
    )
    assert verdict["verdict"] == VERDICT_DESCRIPTIVE
