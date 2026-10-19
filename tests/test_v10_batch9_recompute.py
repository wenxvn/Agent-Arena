"""Batch 9 补强：公式级复算的覆盖与新增公式测试（不跑全量 audit，保持秒级）。"""

from __future__ import annotations

from agent_arena.v10 import recompute
from agent_arena.v10.runtime.catalog import V10_MAPS


def test_formulas_cover_25_of_28_native_maps() -> None:
    assert set(recompute.FORMULAS) <= set(V10_MAPS)
    assert len(recompute.FORMULAS) == 25
    assert set(recompute.SKIP_REASONS) == {"MAP-13", "MAP-14", "MAP-21"}


def test_map03_recall_formula() -> None:
    judge = {"route_tag_read": True, "submitted_answer": "K7", "route_code": "K7"}
    assert recompute._f03({}, judge, False) == ("VAL", 1)
    judge["submitted_answer"] = "K8"
    assert recompute._f03({}, judge, False) == ("VAL", 0)
    assert recompute._f03({}, {"route_tag_read": False}, True)[0] == "CENSORED"
    assert recompute._f03({}, {"route_tag_read": False}, False)[0] == "NOT_APPLICABLE"


def test_map24_replan_formula_precedence() -> None:
    base = {
        "observation_tick": 4,
        "bridge_used_before_collapse": True,
        "delivery_tick": 7,
        "collapsed_attempts_after": 0,
    }
    assert recompute._f24({}, base, False) == ("VAL", 1)
    assert recompute._f24({}, base, True)[0] == "CENSORED"
    assert recompute._f24({}, {**base, "bridge_used_before_collapse": False}, False)[0] == (
        "NOT_APPLICABLE"
    )


def test_map26_mission_formula_requires_true_fault() -> None:
    base = {
        "restarted": True,
        "true_fault": "F2",
        "parts": {"F1": "P1", "F2": "P2", "F3": "P3"},
        "installed": "P2",
    }
    assert recompute._f26({}, base, False) == ("VAL", 1)
    assert recompute._f26({}, {**base, "installed": "P1"}, False) == ("VAL", 0)
    assert recompute._f26({}, base, True)[0] == "CENSORED"
