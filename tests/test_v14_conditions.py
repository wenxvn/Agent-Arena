"""V14 Batch 2（P0-3）：8 维观测条件身份、seed 白名单、公平性判定。"""

from __future__ import annotations

import pytest

from agent_arena.lab.v14.conditions import (
    CONDITION_FIELDS,
    MISMATCH_BUDGET,
    MISMATCH_CONTRACT,
    UNKNOWN,
    VERDICT_COMPARABLE,
    VERDICT_DESCRIPTIVE,
    VERDICT_INCOMPARABLE,
    budget_profile,
    build_pairs,
    condition_comparison,
    descriptive_only_preconditions,
    observation_condition,
    observation_condition_id,
    sampling_profile,
    seed_coverage,
    summarize_pairing,
    validate_seed,
)


def _record(**overrides):
    base = {
        "run_id": "run-1",
        "map_id": "MAP-22",
        "environment_seed": 0,
        "replicate_index": 0,
        "agent_id": "memory.v2",
        "agent_config_hash": "cfg-aaa",
        "agent_contract_version": "v12-contract-2",
        "prompt_hash": "prompt-1",
        "mode": "SIMULATED",
        "provider_id": "simulated_scripted",
        "model": "simulated-agent-policy",
        "rule_hash": "rule-1",
        "metric_hash": "metric-1",
        "metric_schema_hash": "schema-1",
        "request_cap": 90,
        "input_token_cap": 200_000,
        "decision_cap": 90,
        "cost_cap_cny": "0.50",
        "category": "completed_success",
        "success": True,
        "requests": 20,
        "input_tokens": 30_000,
        "cost_cny": 0.01,
        "sampling": {"temperature": 0.0, "top_p": 1.0, "support": "SUPPORTED"},
    }
    base.update(overrides)
    return base

# ------------------------------------------------------------ condition identity
def test_condition_fields_are_the_documented_eight() -> None:
    assert CONDITION_FIELDS == (
        "map_id",
        "environment_seed",
        "agent_id",
        "config_hash",
        "contract_version",
        "effective_prompt_version",
        "budget_profile",
        "sampling_profile",
    )
    condition = observation_condition(_record())
    assert set(condition["fields"]) == set(CONDITION_FIELDS)
    assert condition["complete"] is True
    assert condition["unrecorded_fields"] == []

def test_replicate_index_does_not_change_condition_id() -> None:
    first = observation_condition_id(_record(replicate_index=0))
    second = observation_condition_id(_record(replicate_index=1))
    third = observation_condition_id(_record(replicate_index=2))
    assert first == second == third
    # 但配对键不同：重复不是同一条观测
    assert observation_condition(_record(replicate_index=2))["replicate_index"] == 2

def test_config_hash_change_changes_condition_id() -> None:
    left = observation_condition_id(_record(agent_config_hash="cfg-a"))
    right = observation_condition_id(_record(agent_config_hash="cfg-b"))
    assert left != right

def test_budget_change_changes_condition_id() -> None:
    left = observation_condition_id(_record(request_cap=90))
    right = observation_condition_id(_record(request_cap=180))
    assert left != right

def test_prompt_change_changes_condition_id() -> None:
    left = observation_condition_id(_record(prompt_hash="p1"))
    right = observation_condition_id(_record(prompt_hash="p2"))
    assert left != right

def test_historical_record_without_metadata_is_marked_incomplete() -> None:
    historical = {
        "map_id": "MAP-16",
        "environment_seed": 0,
        "agent_id": "planning.v1",
        "category": "mechanism_failure",
    }
    condition = observation_condition(historical)
    assert condition["complete"] is False
    assert set(condition["unrecorded_fields"]) == {
        "config_hash",
        "contract_version",
        "effective_prompt_version",
    }
    assert condition["fields"]["contract_version"] == UNKNOWN
    assert condition["budget"]["recorded"] is False
    assert condition["sampling"]["recorded"] is False
    assert condition["sampling"]["support"] == UNKNOWN

def test_budget_profile_keeps_unrecorded_as_none() -> None:
    profile = budget_profile({"request_cap": 90})
    assert profile["request_cap"] == 90
    assert profile["input_token_cap"] is None
    assert profile["recorded"] is True
    assert "UNKNOWN" in profile["display"]
    empty = budget_profile({})
    assert empty["recorded"] is False

def test_sampling_profile_never_claims_determinism_without_record() -> None:
    profile = sampling_profile({})
    assert profile["recorded"] is False
    assert profile["deterministic_claim"] == UNKNOWN
    supported = sampling_profile(
        {"sampling": {"temperature": 0.0, "seed_requested": 7, "support": "SUPPORTED"}}
    )
    assert supported["deterministic_claim"] == "SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED"

# ---------------------------------------------------------------- seed whitelist
def test_validate_seed_accepts_registered_and_rejects_unknown() -> None:
    ok = validate_seed("MAP-22", 0)
    assert ok["valid"] is True
    assert 0 in ok["allowed"]
    bad = validate_seed("MAP-22", 99)
    assert bad["valid"] is False
    assert "只登记了 seed" in bad["reason"]
    unknown_map = validate_seed("MAP-99", 0)
    assert unknown_map["valid"] is False

def test_seed_coverage_separates_seeds_from_replicates() -> None:
    records = [
        _record(environment_seed=0, replicate_index=0),
        _record(environment_seed=0, replicate_index=1),
        _record(environment_seed=0, replicate_index=2),
        _record(environment_seed=1, replicate_index=0),
    ]
    coverage = seed_coverage(records)
    row = coverage["maps"][0]
    assert row["independent_seed_count"] == 2
    assert row["max_replicates"] == 3
    assert row["runs"] == 4
    assert coverage["illegal_seeds"] == []
    assert row["replicates_are_not_seeds"] is True

def test_seed_coverage_flags_illegal_seed() -> None:
    coverage = seed_coverage([_record(environment_seed=42)])
    assert len(coverage["illegal_seeds"]) == 1
    assert coverage["illegal_seeds"][0]["seed"] == 42

# --------------------------------------------------------------- fairness verdict
def test_identical_conditions_are_comparable() -> None:
    comparison = condition_comparison(_record(), _record(run_id="run-2"))
    assert comparison["verdict"] == VERDICT_COMPARABLE
    assert comparison["same_condition"] is True
    assert comparison["hard_mismatches"] == []

def test_budget_mismatch_is_hard_rejected() -> None:
    comparison = condition_comparison(_record(), _record(request_cap=180))
    assert comparison["verdict"] == VERDICT_INCOMPARABLE
    assert any(item["code"] == MISMATCH_BUDGET for item in comparison["hard_mismatches"])
    assert "预算" in comparison["reason"]

def test_contract_mismatch_is_hard_rejected() -> None:
    comparison = condition_comparison(
        _record(agent_contract_version="v12-contract-1"),
        _record(agent_contract_version="v12-contract-2"),
    )
    assert comparison["verdict"] == VERDICT_INCOMPARABLE
    assert any(
        item["code"] == MISMATCH_CONTRACT for item in comparison["hard_mismatches"]
    )

def test_prompt_mismatch_is_hard_rejected() -> None:
    comparison = condition_comparison(_record(prompt_hash="p1"), _record(prompt_hash="p2"))
    assert comparison["verdict"] == VERDICT_INCOMPARABLE

def test_unrecorded_versions_degrade_to_descriptive_not_incomparable() -> None:
    left = _record(agent_contract_version=None, prompt_hash=None, sampling=None)
    right = _record(agent_contract_version=None, prompt_hash=None, sampling=None)
    comparison = condition_comparison(left, right)
    assert comparison["verdict"] == VERDICT_DESCRIPTIVE
    assert comparison["hard_mismatches"] == []
    assert any("未登记" in item["detail"] for item in comparison["soft_mismatches"])

def test_agent_change_is_soft_descriptive() -> None:
    comparison = condition_comparison(_record(), _record(agent_id="planning.v2"))
    assert comparison["verdict"] == VERDICT_DESCRIPTIVE
    assert any(item["code"] == "AGENT" for item in comparison["soft_mismatches"])

def test_different_sampling_is_hard_rejected_when_recorded() -> None:
    comparison = condition_comparison(
        _record(),
        _record(sampling={"temperature": 0.7, "top_p": 1.0, "support": "SUPPORTED"}),
    )
    assert comparison["verdict"] == VERDICT_INCOMPARABLE

# ------------------------------------------------------------------ pairing stats
def test_build_pairs_keeps_incomparable_pairs() -> None:
    left = [_record(replicate_index=index) for index in range(3)]
    right = [
        _record(replicate_index=0, request_cap=180),
        _record(replicate_index=1),
        _record(replicate_index=2),
    ]
    pairs = build_pairs(left, right)
    assert len(pairs) == 3
    verdicts = [pair["verdict"] for pair in pairs]
    assert verdicts.count(VERDICT_INCOMPARABLE) == 1
    assert verdicts.count(VERDICT_COMPARABLE) == 2

def test_summarize_pairing_separates_comparable_from_descriptive() -> None:
    left = [
        _record(replicate_index=0, category="mechanism_failure", success=False),
        _record(replicate_index=1, category="completed_success", success=True),
        _record(replicate_index=2, category="budget_censored", success=False),
    ]
    right = [
        _record(replicate_index=0, category="completed_success", success=True, cost_cny=0.02),
        _record(replicate_index=1, category="completed_success", success=True, cost_cny=0.02),
        _record(replicate_index=2, category="budget_censored", success=False, cost_cny=0.03),
    ]
    summary = summarize_pairing(build_pairs(left, right))
    assert summary["pairs"] == 3
    assert summary["comparable_pairs"] == 3
    assert summary["descriptive_pairs"] == 0
    assert summary["incomparable_pairs"] == 0
    assert summary["right_successes"] == 2
    assert summary["left_censored"] == 1
    row = summary["by_seed"][0]
    assert row["right_only"] == 1
    assert row["both_success"] == 1
    assert row["neither"] == 1
    # 默认 cost_cny=0.01 → 0.02/0.02/0.03，差值 0.01/0.01/0.02
    assert row["cost_cny_delta_mean"] == pytest.approx(0.013333, abs=1e-5)
    assert row["cost_cny_delta_total"] == pytest.approx(0.04, abs=1e-6)

def test_summarize_pairing_does_not_pad_missing_cost() -> None:
    left = [_record(cost_cny=None)]
    right = [_record(cost_cny=0.02)]
    summary = summarize_pairing(build_pairs(left, right))
    row = summary["by_seed"][0]
    assert row["cost_cny_delta_mean"] is None
    assert row["cost_cny_delta_total"] is None

def test_descriptive_only_preconditions_explain_small_samples() -> None:
    pairs = build_pairs([_record()], [_record()])
    preconditions = descriptive_only_preconditions(pairs)
    assert preconditions["descriptive_only"] is True
    assert preconditions["independent_seed_count"] == 1
    assert any("可比对仅" in reason for reason in preconditions["reasons"])
    assert "environment_seed" in preconditions["sampling_unit"]

def test_three_seeds_and_three_pairs_can_leave_descriptive() -> None:
    left = [
        _record(environment_seed=seed, replicate_index=0) for seed in (0, 1, 2)
    ]
    right = [
        _record(environment_seed=seed, replicate_index=0) for seed in (0, 1, 2)
    ]
    preconditions = descriptive_only_preconditions(build_pairs(left, right))
    assert preconditions["descriptive_only"] is False
    assert preconditions["independent_seed_count"] == 3
