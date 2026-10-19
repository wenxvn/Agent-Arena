"""Batch 9：报告生成器（构念效度 / MiMo 结果 / 成本审计 / 基线对照）的结构测试。"""

from __future__ import annotations

from agent_arena.v10.construct_validity import render as render_validity
from agent_arena.v10.difficulty import calibrate, render_baselines
from agent_arena.v10.mimo_report import render_cost_audit, render_results


def test_construct_validity_lists_all_maps_and_dimensions() -> None:
    text = render_validity()
    for map_id in ("MAP-01", "MAP-18", "MAP-30"):
        assert map_id in text
    assert "构念标签说明“机制是否通关必要条件”" in text
    assert "`BYPASS`" in text and "`OPTIONAL`" in text


def test_baseline_table_has_all_v10_maps() -> None:
    text = render_baselines(calibrate())
    for map_id in ("MAP-03", "MAP-15", "MAP-30"):
        assert f"| {map_id} |" in text
    assert "legal_random" in text


def test_cost_audit_separates_unknown_spend_from_settled() -> None:
    text = render_cost_audit()
    assert "未知/未结预留" in text
    assert "未拆分账本规避上限" in text
    assert "未知费用未被当作 0" in text


def test_results_report_states_scope_limits() -> None:
    text = render_results()
    assert "不作显著性断言" in text
    assert "V8 回退图" in text
    assert "不得据此声称 30/30" in text
