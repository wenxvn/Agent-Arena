"""V9 公开信息补充与指标叠加层的边界测试。"""

from __future__ import annotations

from agent_arena.v7.metrics.schema import MetricStatus
from agent_arena.v9.metric_overlay import (
    OVERLAY_SPECS,
    overlay_metrics,
    overlay_schema_hash,
)
from agent_arena.v9.metrics import empty_status
from agent_arena.v9.prompts import V9_PUBLIC_ADDENDA, prompt_hashes, system_prompt
from agent_arena.worlds.scenario_v8.catalog import create_environment


def test_v8_compat_prompt_is_unchanged_for_fixed_maps() -> None:
    from agent_arena.v8.prompts import system_prompt as v8_prompt

    for map_id in V9_PUBLIC_ADDENDA:
        environment = create_environment(map_id)
        budget = 46
        assert system_prompt(environment, decision_budget=budget, arm="v8_compat") == v8_prompt(
            environment, decision_budget=budget
        )
        assert system_prompt(environment, decision_budget=budget, arm="v9_fixed") != v8_prompt(
            environment, decision_budget=budget
        )
        hashes = prompt_hashes(environment, decision_budget=budget)
        assert hashes["v8_compat"] != hashes["v9_fixed"]


def test_addenda_do_not_leak_internal_identifiers() -> None:
    forbidden = ("judge_state", "oracle_trace", "hidden_state", "metric_id", "score")
    for map_id, text in V9_PUBLIC_ADDENDA.items():
        lowered = text.lower()
        for token in forbidden:
            assert token not in lowered, f"{map_id} 泄漏 {token}"
        for spec in OVERLAY_SPECS.get(map_id, []):
            assert spec["metric_id"] not in text


def test_addenda_are_bounded_public_rules() -> None:
    assert set(V9_PUBLIC_ADDENDA) == {
        "MAP-05",
        "MAP-07",
        "MAP-08",
        "MAP-09",
        "MAP-10",
        "MAP-11",
        "MAP-12",
        "MAP-16",
        "MAP-25",
        "MAP-26",
    }
    for text in V9_PUBLIC_ADDENDA.values():
        assert 40 <= len(text) <= 400


def test_overlay_schema_hash_is_stable_and_map_specific() -> None:
    assert overlay_schema_hash("MAP-21") == overlay_schema_hash("MAP-21")
    assert overlay_schema_hash("MAP-21") != overlay_schema_hash("MAP-25")
    assert overlay_schema_hash("MAP-01")  # 空 overlay 也有稳定 hash


def test_map21_overlay_discriminates_direct_evacuation() -> None:
    direct = {
        "status": "scenario_success",
        "carried_sample": None,
        "measurement_outcome": None,
    }
    scientific = {
        "status": "scenario_success",
        "carried_sample": "W_LAYERED_CORE",
        "measurement_outcome": "LATE_WARNING",
    }
    assert overlay_metrics("MAP-21", direct, [])["map21.scientific_units_evacuated"][
        "value"
    ] == 1
    assert overlay_metrics("MAP-21", scientific, [])["map21.scientific_units_evacuated"][
        "value"
    ] == 3


def test_map12_overlay_exposes_research_points() -> None:
    state = {"research_points": 12}
    value = overlay_metrics("MAP-12", state, [])["map12.research_points_completion"]
    assert value["status"] == "valid"
    assert value["value"] == 1.0
    assert value["denominator"] == 12


def test_map25_overlay_does_not_credit_rejected_diagnosis() -> None:
    state = {
        "required_done": ["equipment", "suit", "tether", "depressurize", "diagnosed"],
        "diagnosed": False,
    }
    value = overlay_metrics("MAP-25", state, [])["map25.required_check_coverage_corrected"]
    assert value["value"] == round(4 / 7, 6)


def test_map13_overlay_counts_only_illegal_doors() -> None:
    rows = [
        {"result": "ILLEGAL_DOOR"},
        {"result": "STATE_RESET"},
        {"result": "STATE_RESET"},
    ]
    value = overlay_metrics("MAP-13", {}, rows)["map13.illegal_door_attempts_corrected"]
    assert value["value"] == 1


def test_map14_overlay_allows_negative_query_gap() -> None:
    state = {"asked_claim_ids": [], "minimum_queries": 3}
    value = overlay_metrics("MAP-14", state, [])["map14.query_gap_signed"]
    assert value["value"] == -3


def test_map19_overlay_normalises_area_by_ticks() -> None:
    state = {"settled_states": [{"A": 10, "B": 8, "C": 8}, {"A": 8, "B": 8, "C": 8}]}
    value = overlay_metrics("MAP-19", state, [])["map19.exceedance_area_per_tick"]
    assert value["value"] == 1.0
    assert value["denominator"] == 2


def test_budget_censoring_marks_none_as_censored() -> None:
    assert empty_status("decision_budget_reached") is MetricStatus.CENSORED
