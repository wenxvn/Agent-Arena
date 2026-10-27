"""V14 Batch 1（P0-2）：未知 vs 零、协议隔离、预算表算术。"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.validity import (
    TRIGGER_MIXED,
    TRIGGER_OBSERVED_FALSE,
    TRIGGER_OBSERVED_TRUE,
    TRIGGER_UNKNOWN,
    format_trigger_ratio,
    map_validity,
    mechanism_triggered_summary,
    six_map_audit,
    validity_markdown,
)
from agent_arena.lab.v14.data_audit import (
    ESTIMATE_MARGIN,
    PROTOCOL_POOLED,
    PROTOCOL_SINGLE,
    budget_proposal_check,
    parse_budget_rows,
    protocol_group,
    validity_diff,
    version_isolation,
)

REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"
PROPOSAL = REPO_ROOT / "docs" / "v13" / "live-budget-proposal.md"

def _record(**overrides):
    base = {
        "map_id": "MAP-16",
        "environment_seed": 0,
        "agent_id": "memory.v1",
        "category": "completed_success",
        "success": True,
        "decisions": 10,
        "invalid_actions": 0,
        "cost_known": True,
        "cost_cny": 0.01,
        "source": "HISTORICAL",
        "source_file": "main-54-runs.csv",
        "experiment_kind": "matrix",
    }
    base.update(overrides)
    return base

# ------------------------------------------------------------ unknown vs zero
def test_all_unknown_is_unknown_not_zero() -> None:
    summary = mechanism_triggered_summary([_record() for _ in range(5)])
    assert summary["status"] == TRIGGER_UNKNOWN
    assert summary["available"] is False
    assert summary["observed"] == 0
    assert summary["unknown"] == 5
    assert summary["observed_true"] == 0
    assert format_trigger_ratio(summary).startswith("UNKNOWN (0 observed")

def test_all_true_is_observed_true() -> None:
    summary = mechanism_triggered_summary(
        [_record(mechanism_triggered=True) for _ in range(3)]
    )
    assert summary["status"] == TRIGGER_OBSERVED_TRUE
    assert summary["observed"] == 3
    assert summary["unknown"] == 0
    assert format_trigger_ratio(summary) == "3/3"

def test_all_false_is_observed_false() -> None:
    summary = mechanism_triggered_summary(
        [_record(mechanism_triggered=False) for _ in range(4)]
    )
    assert summary["status"] == TRIGGER_OBSERVED_FALSE
    assert summary["observed_false"] == 4
    assert format_trigger_ratio(summary) == "0/4"

def test_mixed_known_and_unknown_uses_observed_denominator() -> None:
    records = [
        _record(mechanism_triggered=True),
        _record(mechanism_triggered=False),
        _record(),
        _record(),
    ]
    summary = mechanism_triggered_summary(records)
    assert summary["status"] == TRIGGER_MIXED
    assert summary["observed"] == 2
    assert summary["unknown"] == 2
    assert format_trigger_ratio(summary) == "1/2 (2 unknown)"

def test_map_validity_unknown_does_not_claim_never_triggered() -> None:
    records = [
        _record(map_id="MAP-16", category="completed_success", success=True),
        _record(map_id="MAP-16", category="mechanism_failure", success=False),
        _record(map_id="MAP-16", category="completed_success", success=True),
    ]
    row = map_validity("MAP-16", records)
    assert row["mechanism_triggered_available"] is False
    assert row["mechanism_triggered_unknown"] == 3
    assert row["mechanism_triggered_display"].startswith("UNKNOWN")
    assert "NEEDS_EVIDENCE" not in row["labels"]
    assert all("从未被触发" not in reason for reason in row["reasons"])

def test_map_validity_observed_false_flags_needs_evidence() -> None:
    records = [
        _record(category="completed_success", success=True, mechanism_triggered=False),
        _record(category="mechanism_failure", success=False, mechanism_triggered=False),
        _record(category="completed_success", success=True, mechanism_triggered=False),
    ]
    row = map_validity("MAP-16", records)
    assert row["mechanism_triggered_status"] == TRIGGER_OBSERVED_FALSE
    assert "NEEDS_EVIDENCE" in row["labels"]
    assert any("从未被触发" in reason for reason in row["reasons"])

def test_validity_markdown_never_renders_unknown_as_zero() -> None:
    records = [
        _record(map_id=map_id, category="completed_success", success=True)
        for map_id in ("MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30")
        for _ in range(3)
    ]
    text = validity_markdown(six_map_audit(records))
    assert "| 0/3 |" not in text
    assert text.count("UNKNOWN (0 observed") == 6

# ------------------------------------------------------------ protocol isolation
def test_protocol_group_separates_files() -> None:
    left = protocol_group(_record(source_file="main-54-runs.csv"))
    right = protocol_group(
        _record(source_file="map22-contract2-runs.csv", experiment_kind="version_rerun")
    )
    assert left["file"] != right["file"]
    assert left["kind"] == "matrix"
    assert right["kind"] == "version_rerun"
    assert left["prompt_hash_recorded"] is False

def test_version_isolation_refuses_pooling() -> None:
    records = [
        _record(source_file="main-54-runs.csv"),
        _record(source_file="map22-contract2-runs.csv", experiment_kind="version_rerun"),
    ]
    isolation = version_isolation(records, "MAP-16")
    assert isolation["protocol_groups"] == 2
    assert isolation["status"] == PROTOCOL_POOLED
    assert isolation["pooling_allowed"] is False
    single = version_isolation([_record(), _record()], "MAP-16")
    assert single["status"] == PROTOCOL_SINGLE
    assert single["pooling_allowed"] is True

# ------------------------------------------------------------ budget proposal
_SYNTHETIC_PROPOSAL = """
## 2. 每组的上界与预估

| 组 | 内容 | 地图 / seed | 条件 × 重复 | 子局 | 单局硬上限 | 上界 CNY | 预估 CNY |
|---|---|---|---|---:|---|---:|---:|
| E1-a | route_log | MAP-22 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.90 |
| E2-a | planning | MAP-16 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.31 |

**合计**：**40 局**，上界 **¥18.00**，预估 **¥1.21**。
"""

def test_parse_budget_rows_reads_every_group() -> None:
    rows = parse_budget_rows(_SYNTHETIC_PROPOSAL)
    assert [row["group"] for row in rows] == ["E1-a", "E2-a"]
    assert rows[0]["runs"] == 18
    assert rows[0]["upper_cny"] == 9.0

def test_budget_check_detects_declared_total_mismatch() -> None:
    records = [
        _record(map_id="MAP-22", cost_cny=0.033446),
        _record(map_id="MAP-16", cost_cny=0.011533),
    ]
    check = budget_proposal_check(_SYNTHETIC_PROPOSAL, records)
    assert check["totals"]["runs"] == 36
    assert check["declared_total_runs"] == 40
    assert check["declared_total_matches"] is False
    assert check["plans"]["A"]["runs"] == 36
    assert check["plans"]["A"]["recomputed_estimate_cny"] == pytest.approx(
        round(18 * 0.033446 * ESTIMATE_MARGIN, 2) + round(18 * 0.011533 * ESTIMATE_MARGIN, 2),
        abs=0.02,
    )

@pytest.mark.skipif(not REAL_RUNS.is_dir(), reason="需要 docs/v12/real-runs 只读历史")
def test_real_history_six_map_diff_only_changes_trigger_display() -> None:
    from agent_arena.lab.v13.history import load_v12_history

    records = load_v12_history()
    diff = validity_diff(records)
    assert len(diff["rows"]) == 6
    for row in diff["rows"]:
        assert row["v13_label"] == row["v14_label"]
        assert row["v13_valid_denominator"] == row["v14_valid_denominator"]
        assert row["v14_trigger_status"] == TRIGGER_UNKNOWN
        assert row["v14_trigger"].startswith("UNKNOWN")

@pytest.mark.skipif(
    not (REAL_RUNS.is_dir() and PROPOSAL.is_file()), reason="需要历史数据与预算文档"
)
def test_real_budget_proposal_now_self_consistent() -> None:
    from agent_arena.lab.v13.history import load_v12_history

    records = load_v12_history()
    text = PROPOSAL.read_text(encoding="utf-8")
    check = budget_proposal_check(text, records)
    assert check["totals"]["runs"] == 221
    assert check["declared_total_matches"] is True
    assert check["plans"]["A"]["runs"] == 54
    assert check["plans"]["B"]["runs"] == 186
    assert check["plans"]["C"]["runs"] == 221
    # 修正后每行都应按文档自己声明的 1.5 倍余量公式重算一致
    for row in check["rows"]:
        assert row["estimate_matches_formula"] is True, row["group"]

def test_data_validity_doc_exists_after_generation() -> None:
    path = Path(REPO_ROOT) / "docs" / "v14" / "data-validity.md"
    if not path.is_file():
        pytest.skip("尚未生成 docs/v14/data-validity.md")
    text = path.read_text(encoding="utf-8")
    assert "UNKNOWN (0 observed" in text
    assert "221" in text
