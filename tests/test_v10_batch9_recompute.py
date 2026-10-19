"""Batch 9 补强：公式级复算的覆盖与结果测试。"""

from __future__ import annotations

from agent_arena.v10 import recompute
from agent_arena.v10.runtime.catalog import V10_MAPS


def test_formulas_cover_24_of_27_native_maps() -> None:
    assert set(recompute.FORMULAS) <= set(V10_MAPS)
    assert len(recompute.FORMULAS) == 24
    assert set(recompute.SKIP_REASONS) == {"MAP-13", "MAP-14", "MAP-21"}


def test_audit_reports_no_mismatch() -> None:
    payload = recompute.audit()
    if not payload["rows"]:
        return
    assert payload["totals"]["mismatch"] == 0, payload["mismatches"][:3]
    assert payload["totals"]["checks"] == len(payload["rows"])


def test_render_mentions_coverage_and_skips() -> None:
    text = recompute.render(recompute.audit())
    assert "公式级独立复算" in text
    assert "未覆盖的图与原因" in text
