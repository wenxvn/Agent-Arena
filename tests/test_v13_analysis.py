"""V13 分析层测试：消融模板、证据包、地图效度、归因分层与能力画像。"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.v13.ablation import (
    ABLATION_TEMPLATES,
    KIND_SINGLE_SWITCH,
    KIND_VERSION_COMPARE,
    LEVEL_INSUFFICIENT,
    LEVEL_NOT_TESTED,
    LEVEL_SUPPORTED,
    LEVEL_TENTATIVE,
    build_ablation_specs,
    build_evidence_pack,
    classify_pair,
    template_table,
)
from agent_arena.lab.v13.capability import (
    DIMENSIONS,
    LEVEL_THIN,
    LEVEL_UNTESTED,
    capability_markdown,
    capability_profile,
    dimension_profile,
)
from agent_arena.lab.v13.history import load_v12_history
from agent_arena.lab.v13.taxonomy import (
    BUDGET,
    INTERFACE,
    MEASUREMENT,
    MECHANISM,
    POLICY,
    PROVIDER,
    UNKNOWN,
    attribute_run,
    check_fixtures,
    classify_category,
    taxonomy_markdown,
    taxonomy_report,
)
from agent_arena.lab.v13.validity import (
    LABEL_CEILING,
    LABEL_CENSORED,
    LABEL_SUITABLE,
    budget_capacity,
    map30_failure_class,
    map30_ladder,
    map_validity,
    six_map_audit,
    validity_markdown,
)


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "r1",
        "map_id": "MAP-16",
        "environment_seed": 0,
        "agent_id": "planning.v1",
        "agent_version": "1.0.0",
        "category": "mechanism_failure",
        "success": False,
        "cost_known": True,
        "cost_cny": 0.01,
        "decisions": 20,
        "requests": 20,
        "input_tokens": 20_000,
        "invalid_actions": 0,
        "termination": "DEADLOCK",
        "source": "HISTORICAL",
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------- ablation
def test_all_templates_are_single_switch() -> None:
    rows = template_table()
    assert len(rows) == len(ABLATION_TEMPLATES)
    assert all(row["single_switch_ok"] for row in rows)
    assert all(row["kind"] == KIND_SINGLE_SWITCH for row in rows)


def test_ablation_specs_are_two_independent_experiments() -> None:
    control, treatment = build_ablation_specs(
        ABLATION_TEMPLATES["memory.on_off"], maps=["MAP-22"], seeds=[0], replicates=3
    )
    assert control.name != treatment.name
    assert control.fingerprint() != treatment.fingerprint()
    assert len(control.matrix()) == 3
    assert control.experiment_kind == "ablation"
    assert control.comparison.min_paired_samples == 3
    # 只差一个开关。
    assert control.agent_arms[0].config != treatment.agent_arms[0].config
    assert control.agent_arms[0].agent_id == treatment.agent_arms[0].agent_id


def test_version_bump_is_not_an_ablation() -> None:
    assert (
        classify_pair("memory.v1", {"enabled": True}, "memory.v2", {"enabled": True})
        == KIND_VERSION_COMPARE
    )


def test_multi_switch_is_rejected() -> None:
    assert (
        classify_pair(
            "memory.v2",
            {"enabled": True, "route_log": False},
            "memory.v2",
            {"enabled": False, "route_log": True},
        )
        == "MULTI_SWITCH_COMBINATION"
    )


def test_evidence_pack_reports_denominator_and_levels() -> None:
    records = load_v12_history(names=["main-54-runs.csv"])
    pack = build_evidence_pack(
        "MAP-16", records, question="planning 是否有效？", source="HISTORICAL"
    )
    payload = pack.as_dict()
    assert payload["runs"] == 9
    assert payload["valid_denominator"] <= payload["runs"]
    assert payload["conclusion_level"] in {
        LEVEL_SUPPORTED,
        LEVEL_TENTATIVE,
        LEVEL_INSUFFICIENT,
        LEVEL_NOT_TESTED,
    }
    assert payload["by_arm"]
    assert "证据包" in pack.markdown()


def test_evidence_pack_with_no_records_is_not_tested() -> None:
    pack = build_evidence_pack(
        "MAP-99", [], question="q", source="HISTORICAL"
    )
    assert pack.conclusion_level() == LEVEL_NOT_TESTED


# ------------------------------------------------------------------- validity
def test_map30_failure_classes() -> None:
    assert map30_failure_class({"category": "completed_success"}) == "SUCCESS"
    assert map30_failure_class({"category": "budget_censored"}) == "BUDGET_CENSORED"
    assert (
        map30_failure_class(
            {"category": "mechanism_failure", "termination": "ACCUSATION_REJECTED"}
        )
        == "ACCUSATION_REJECTED"
    )
    assert (
        map30_failure_class(
            {"category": "mechanism_failure", "termination": "EVIDENCE_INCOMPLETE"}
        )
        == "EVIDENCE_INSUFFICIENT"
    )
    assert (
        map30_failure_class({"category": "mechanism_failure", "termination": "DEADLOCK"})
        == "REASONING_CHAIN_MIDWAY"
    )


def test_map30_ladder_separates_budget_tiers() -> None:
    records = load_v12_history()
    ladder = map30_ladder(records)
    tiers = {tier["tier"]: tier for tier in ladder["tiers"]}
    assert set(tiers) == {
        "req=90|tok=200000",
        "req=180|tok=200000",
        "req=180|tok=600000",
    }
    assert tiers["req=180|tok=200000"]["accusation_rejected"] == 4
    assert tiers["req=180|tok=200000"]["censored"] == 5
    assert tiers["req=180|tok=600000"]["censored"] == 7
    assert "需批准" in ladder["candidate_note"]
    assert "预算阶梯" in map30_markdown_contains(ladder)


def map30_markdown_contains(ladder: dict[str, Any]) -> str:
    from agent_arena.lab.v13.validity import map30_markdown

    return map30_markdown(ladder)


def test_budget_capacity_uses_observed_distribution_only() -> None:
    records = [
        _record(decisions=10, input_tokens=10_000),
        _record(decisions=20, input_tokens=40_000),
    ]
    capacity = budget_capacity(records, input_token_cap=600_000, request_cap=180)
    assert capacity["available"] is True
    low, high = capacity["estimated_supported_decisions"]
    assert low <= high
    assert "不是对真实模型的承诺" in capacity["note"]
    empty = budget_capacity([], input_token_cap=1000, request_cap=10)
    assert empty["available"] is False


def test_map_validity_labels_are_composite_and_evidence_backed() -> None:
    records = load_v12_history()
    ceiling = map_validity("MAP-08", records)
    assert LABEL_CEILING in ceiling["labels"]
    assert ceiling["reasons"]
    suitable = map_validity("MAP-16", records)
    assert LABEL_SUITABLE in suitable["labels"]
    censored = map_validity("MAP-30", records)
    assert LABEL_CENSORED in censored["labels"]
    assert "构念效度" in censored["restriction"]


def test_six_map_audit_recommends_regression_for_ceiling() -> None:
    records = load_v12_history()
    audit = six_map_audit(records)
    assert set(audit["ceiling_maps"]) == {"MAP-08", "MAP-26"}
    recommendations = {item["map_id"]: item["recommendation"] for item in audit["recommendations"]}
    assert "回归" in recommendations["MAP-08"]
    assert "预算扩展" in recommendations["MAP-30"]
    assert "30/30" in audit["note"]
    assert "构念" in validity_markdown(audit)


# ------------------------------------------------------------------- taxonomy
def test_category_layers_cover_v12_findings() -> None:
    assert classify_category("memory_payload_rejected") == INTERFACE
    assert classify_category("memory_key_not_in_metric") == MEASUREMENT
    assert classify_category("budget_censored") == BUDGET
    assert classify_category("unsupported_accusation") == MECHANISM
    assert classify_category("repeated_action_loop") == POLICY
    assert classify_category("provider_error") == PROVIDER
    assert classify_category("something_new") == UNKNOWN


def test_fixtures_have_positive_and_negative() -> None:
    report = check_fixtures()
    assert report["ok"], report["failures"]
    assert report["checked"] == 8


def test_attribute_run_prioritises_non_agent_layers() -> None:
    from agent_arena.lab.contracts import Finding

    record = _record(run_id="r-1")
    findings = [
        Finding(
            category="repeated_action_loop",
            map_id="MAP-16",
            run_id="r-1",
            summary="重复动作",
            evidence_steps=(3,),
            evidence_event_ids=("step-3",),
        ),
        Finding(
            category="memory_payload_rejected",
            map_id="MAP-16",
            run_id="r-1",
            summary="载荷被拒",
            evidence_steps=(4,),
            evidence_event_ids=("step-4",),
        ),
    ]
    attribution = attribute_run(record, findings)
    assert attribution.primary_layer == INTERFACE, attribution.as_dict()
    assert attribution.layers[POLICY] == 1
    assert {anchor["decision_steps"][0] for anchor in attribution.anchors} == {3, 4}


def test_taxonomy_report_marks_unclassified_runs() -> None:
    records = [
        _record(run_id="a", category="mechanism_failure"),
        _record(run_id="b", category="completed_success", success=True),
    ]
    report = taxonomy_report(records, findings=[])
    assert report["runs"] == 2
    assert "a" in report["unclassified_runs"]
    assert "b" not in report["unclassified_runs"]
    assert "失败归因分层" in taxonomy_markdown(report)


# ----------------------------------------------------------------- capability
def test_capability_profile_has_six_dimensions_and_no_zero_fill() -> None:
    records = load_v12_history()
    profile = capability_profile(records)
    assert len(profile["dimensions"]) == 6
    assert [item["dimension"] for item in profile["dimensions"]] == list(DIMENSIONS)
    for item in profile["dimensions"]:
        if item["measurable_runs"] == 0:
            assert item["success_rate"] is None
            assert item["evidence_level"] == LEVEL_UNTESTED
    assert profile["label_status"] == "agent_reviewed"
    assert "human_approved" in profile["label_note"]
    assert "机制级能力画像" in capability_markdown(profile)


def test_dimension_profile_marks_thin_samples() -> None:
    records = [_record(map_id="MAP-22")]
    item = dimension_profile("memory_tracking", records)
    assert item["measurable_runs"] == 1
    assert item["evidence_level"] == LEVEL_THIN
    assert item["success_rate"] is None
