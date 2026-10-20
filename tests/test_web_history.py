"""V11 历史筛选、版本对照与本地成绩榜。"""

from __future__ import annotations

from agent_arena.web.history import (
    comparison_rows,
    compatibility,
    compatibility_all,
    filter_runs,
    leaderboard,
    multi_comparison_rows,
)
from agent_arena.web.schemas import RunSummary


def _row(**overrides: object) -> RunSummary:
    payload: dict[str, object] = {
        "run_id": "web-20260101T000000Z-abcdef12",
        "map_id": "MAP-01",
        "world": "spaceship",
        "mode": "offline",
        "provider_id": "offline_public_policy",
        "model": "public-heuristic-policy",
        "environment_seed": 0,
        "state": "SUCCEEDED",
        "outcome": "success",
        "success": True,
        "decisions": 15,
        "created_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "cost_settled_cny": 0.0,
        "cost_unknown": False,
        "rule_hash": "a" * 64,
        "metric_hash": "b" * 64,
        "metric_schema_hash": "c" * 64,
        "display_title": "破损的曙光号",
        "decision_budget": 30,
    }
    payload.update(overrides)
    return RunSummary(**payload)  # type: ignore[arg-type]


def test_filter_runs_by_map_state_mode_and_text() -> None:
    rows = [
        _row(),
        _row(run_id="r2", map_id="MAP-02", state="FAILED", success=False),
        _row(run_id="r3", mode="live", model="mimo-v2.6-flash", provider_id="openai_compatible"),
    ]
    assert len(filter_runs(rows, map_id="MAP-01")) == 2
    assert len(filter_runs(rows, state="FAILED")) == 1
    assert len(filter_runs(rows, mode="live")) == 1
    assert len(filter_runs(rows, provider_id="openai_compatible")) == 1
    assert len(filter_runs(rows, environment_seed=1)) == 0
    assert filter_runs(rows, query="mimo")[0].run_id == "r3"
    assert filter_runs(rows, since="2027-01-01") == []


def test_compatibility_blocks_version_mismatch() -> None:
    left = _row()
    right = _row(run_id="r2")
    assert compatibility(left, right)["compatible"]
    changed = _row(run_id="r3", rule_hash="d" * 64)
    verdict = compatibility(left, changed)
    assert not verdict["compatible"]
    assert "规则 hash 不同" in verdict["mismatches"]
    model_diff = _row(run_id="r4", model="other")
    assert compatibility(left, model_diff)["compatible"]
    assert compatibility(left, model_diff)["warnings"]


def test_comparison_rows_include_versions() -> None:
    rows = comparison_rows(_row(), _row(run_id="r2"))
    fields = {row["字段"] for row in rows}
    assert {"run_id", "rule_hash", "metric_hash", "seed", "费用 CNY"} <= fields


def test_multi_comparison_and_compatibility_all() -> None:
    rows = [_row(), _row(run_id="r2"), _row(run_id="r3", rule_hash="d" * 64)]
    assert not compatibility_all(rows)["compatible"]
    assert "规则 hash 不同" in compatibility_all(rows)["mismatches"]
    table = multi_comparison_rows(rows)
    assert len(table) == 3
    assert "动作 / 预算" in table[0]
    assert "30" in table[0]["动作 / 预算"]


def test_leaderboard_is_grouped_by_model_and_version() -> None:
    rows = [
        _row(run_id="r1", decisions=20),
        _row(run_id="r2", decisions=10),
        _row(run_id="r3", model="other", decisions=5),
        _row(run_id="r4", state="CANCELLED", success=False),
    ]
    board = leaderboard(rows)
    first = [row for row in board if row["model"] == "public-heuristic-policy"]
    assert [row["run_id"] for row in first] == ["r2", "r1"]
    assert all(row["run_id"] != "r4" for row in board)
    assert first[0]["budget"] == 30
    assert len([row for row in board if row["model"] == "other"]) == 1
