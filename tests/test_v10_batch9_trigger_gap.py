"""Batch 9 补强：未触发机制局判读与古堡预算剖面的结构测试（无产物则跳过）。"""

from __future__ import annotations

from agent_arena.v10 import trigger_gap

ALLOWED = {
    "BUDGET",
    "THRESHOLD",
    "ENTRY_NOT_ATTEMPTED",
    "ENTRY_REJECTED",
    "USED_NO_THRESHOLD",
}


def test_analyse_only_reports_untriggered_effective_runs() -> None:
    payload = trigger_gap.analyse()
    if not payload["rows"]:
        return
    assert payload["totals"]["runs"] == len(payload["rows"])
    for row in payload["rows"]:
        assert row["judgement"] in ALLOWED, row
        assert row["budget"] > 0
        assert row["decisions"] >= 0


def test_render_has_sections() -> None:
    text = trigger_gap.render(trigger_gap.analyse())
    assert "未触发机制局的逐局判读" in text
    assert "## 1. 分布" in text
    assert "## 3. 逐局明细" in text


def test_castle_budget_covers_three_maps() -> None:
    payload = trigger_gap.castle_budget()
    maps = {row["map_id"] for row in payload["rows"]}
    if not payload["rows"]:
        return
    assert maps <= {"MAP-28", "MAP-29", "MAP-30"}
    for row in payload["rows"]:
        assert row["budget"] > 0
        assert isinstance(row["histogram"], dict)


def test_castle_render_mentions_budget() -> None:
    text = trigger_gap.render_castle(trigger_gap.castle_budget())
    assert "决策预算剖面" in text
    assert "Oracle 动作" in text
