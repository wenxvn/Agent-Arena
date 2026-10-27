"""V14 Batch 8（P1-3 / P1-4 / P1-6）：锚点、正反 fixture、画像缺口、结论强度。"""

from __future__ import annotations

import pytest

from agent_arena.lab.contracts import Finding
from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v14.failure_capability import (
    ANCHOR_COMPLETE,
    ANCHOR_MISSING,
    ANCHOR_PARTIAL,
    CAPABILITY_ELIGIBLE_LAYERS,
    FIXTURE_PROGRESS_THEN_BUDGET,
    FIXTURE_REJECTED_NO_PROGRESS,
    NON_CAPABILITY_LAYERS,
    audit_findings,
    capability_with_gaps,
    conclusion_strength,
    conclusion_strength_markdown,
    failure_capability_markdown,
    failure_capability_report,
    failure_fixtures,
    finding_anchor,
    interface_artifact_fixture,
    progress_then_budget_fixture,
    rejected_no_progress_fixture,
)

REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"

# ------------------------------------------------------------------- anchors
def test_complete_anchor_requires_run_step_action_result() -> None:
    anchor = finding_anchor(
        {
            "category": "repeated_action_loop",
            "run_id": "r-1",
            "evidence_steps": (3, 4),
            "action": {"tool": "move", "bearing": "north"},
            "public_result": "BEARING_NOT_AVAILABLE",
        }
    )
    assert anchor["status"] == ANCHOR_COMPLETE
    assert anchor["anchor"] == "r-1#3"
    assert anchor["decision_index"] == 3

def test_partial_anchor_without_action_or_result() -> None:
    anchor = finding_anchor(
        {"category": "no_progress_window", "run_id": "r-1", "evidence_steps": (5,)}
    )
    assert anchor["status"] == ANCHOR_PARTIAL
    assert "只能作线索" in anchor["note"]

def test_missing_anchor_is_flagged() -> None:
    anchor = finding_anchor({"category": "no_progress_window"})
    assert anchor["status"] == ANCHOR_MISSING
    assert "不得据此断言" in anchor["note"]

def test_audit_findings_counts_by_status() -> None:
    findings = [
        Finding(
            category="repeated_action_loop",
            map_id="MAP-22",
            run_id="r-1",
            evidence_steps=(1, 2),
            summary="重复动作",
        ),
        Finding(category="no_progress_window", map_id="MAP-22", summary="无锚点"),
    ]
    audit = audit_findings(findings)
    assert audit["findings"] == 2
    assert audit["partial"] == 1
    assert audit["unanchored"] == 1
    assert audit["anchored"] == 0
    assert "UNANCHORED" in audit["rule"]

# ---------------------------------------------------------------- fixtures
def test_rejected_no_progress_fixture_is_policy_layer() -> None:
    fixture = rejected_no_progress_fixture()
    assert fixture["fixture"] == FIXTURE_REJECTED_NO_PROGRESS
    assert fixture["expected_layer"] == "POLICY_BEHAVIOUR"
    assert fixture["expected_capability_eligible"] is True
    assert fixture["rejected_steps"] == 3
    assert fixture["public_progress_after_step_0"] is False
    assert fixture["anchor"]["status"] == ANCHOR_COMPLETE

def test_progress_then_budget_fixture_is_not_capability() -> None:
    fixture = progress_then_budget_fixture()
    assert fixture["fixture"] == FIXTURE_PROGRESS_THEN_BUDGET
    assert fixture["expected_layer"] == "BUDGET_CENSORED"
    assert fixture["expected_capability_eligible"] is False
    assert fixture["rejected_steps"] == 0
    assert fixture["public_progress_after_step_0"] is True
    assert "不得" in fixture["reading"]

def test_interface_artifact_is_also_not_capability() -> None:
    fixture = interface_artifact_fixture()
    assert fixture["expected_layer"] == "INTERFACE_CONTRACT"
    assert fixture["expected_capability_eligible"] is False
    # 与"被拒无进展"形态相同，但层不同 —— 这正是正反 fixture 的意义
    assert fixture["public_progress_after_step_0"] is False

def test_layer_eligibility_matrix() -> None:
    fixtures = failure_fixtures()
    eligibility = fixtures["layer_eligibility"]
    for layer in NON_CAPABILITY_LAYERS:
        assert eligibility[layer] is False, layer
    for layer in CAPABILITY_ELIGIBLE_LAYERS:
        assert eligibility[layer] is True, layer

# --------------------------------------------------------------- capability
@pytest.fixture(scope="module")
def records():
    if not REAL_RUNS.is_dir():
        pytest.skip("需要 docs/v12/real-runs 只读历史")
    from agent_arena.lab.v13.history import load_v12_history

    return load_v12_history()

def test_unavailable_dimension_is_not_zero(records) -> None:
    profile = capability_with_gaps(records)
    by_dim = {row["dimension"]: row for row in profile["dimensions"]}
    unavailable = by_dim["failure_recovery"]
    assert unavailable["status"] == "UNAVAILABLE"
    assert unavailable["measurable_runs"] == 0
    assert unavailable["success_rate"] is None
    assert "UNAVAILABLE" in unavailable["gaps"]
    assert "不是能力为 0" in unavailable["note"]

def test_every_dimension_reports_samples_seeds_replicates(records) -> None:
    profile = capability_with_gaps(records)
    assert profile["dimension_count"] == 6
    for row in profile["dimensions"]:
        assert "independent_seeds" in row
        assert "replicate_indices" in row
        assert isinstance(row["gaps"], list)
        assert row["status"] in {"AVAILABLE", "UNAVAILABLE"}

def test_planning_dimension_has_replicates(records) -> None:
    profile = capability_with_gaps(records)
    by_dim = {row["dimension"]: row for row in profile["dimensions"]}
    planning = by_dim["planning_replanning"]
    assert planning["independent_seed_count"] == 5
    assert planning["replicate_indices"] == [0, 1, 2]
    assert "NO_REPLICATES" not in planning["gaps"]

def test_no_total_score_is_produced(records) -> None:
    profile = capability_with_gaps(records)
    assert "total_score" not in profile
    assert "不对异质指标求总分" in profile["aggregation_rule"]
    for row in profile["dimensions"]:
        assert "total_score" not in row

# ---------------------------------------------------------- conclusion strength
def test_conclusion_strength_forbids_overclaiming() -> None:
    item = conclusion_strength(
        evidence_level="SUPPORTED",
        mechanism_exposure="NO_TREATMENT_EXPOSURE",
        effect_direction="NOT_MEASURABLE",
    )
    assert item["evidence_level"] == "SUPPORTED"
    assert any("干预从未发生" in text for text in item["forbidden_claims"])
    assert any("不等于显著改善" in text for text in item["forbidden_claims"])

def test_supported_alone_never_means_improvement() -> None:
    item = conclusion_strength(
        evidence_level="SUPPORTED",
        mechanism_exposure="EXPOSED",
        effect_direction="NO_DIFFERENCE",
    )
    assert any("不等于显著改善" in text for text in item["forbidden_claims"])
    assert "三个字段独立" in item["reading"]

def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        conclusion_strength(
            evidence_level="PROVEN",
            mechanism_exposure="EXPOSED",
            effect_direction="IMPROVED",
        )
    with pytest.raises(ValueError):
        conclusion_strength(
            evidence_level="SUPPORTED",
            mechanism_exposure="MAYBE",
            effect_direction="IMPROVED",
        )

def test_markdown_reports_three_fields(records) -> None:
    text = failure_capability_markdown(failure_capability_report(records))
    assert "evidence_level" in text
    assert "mechanism_exposure" in text
    assert "effect_direction" in text
    assert "UNAVAILABLE" in text
    assert "禁止的读法" in text
    assert conclusion_strength_markdown(
        conclusion_strength(
            evidence_level="INSUFFICIENT",
            mechanism_exposure="UNKNOWN",
            effect_direction="NOT_MEASURABLE",
        )
    )
