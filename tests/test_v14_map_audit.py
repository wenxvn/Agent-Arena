"""V14 Batch 7（P1-1 / P1-2）：MAP-30 三维阶梯、六图复算、候选图审计。"""

from __future__ import annotations

import pytest

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v14.map_audit import (
    CANDIDATE_MAPS,
    MAP30_TIERS,
    candidate_map_audit,
    map30_conservative_interval,
    map30_three_axis,
    map_audit_markdown,
    map_audit_report,
    six_map_recheck,
)

REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"

@pytest.fixture(scope="module")
def records():
    if not REAL_RUNS.is_dir():
        pytest.skip("需要 docs/v12/real-runs 只读历史")
    from agent_arena.lab.v13.history import load_v12_history

    return load_v12_history()

# ------------------------------------------------------------------ MAP-30 3D
def test_map30_three_axes_are_reported_per_tier(records) -> None:
    axis = map30_three_axis(records)
    assert axis["map_id"] == "MAP-30"
    assert len(axis["tiers"]) == 3
    for tier in axis["tiers"]:
        assert tier["bottleneck_axis"] in {
            "REQUESTS",
            "INPUT_TOKENS",
            "COST_CNY",
            "UNSPECIFIED",
            "UNKNOWN",
        }
        assert tier["bottleneck_evidence"]
        assert tier["capacity"]["available"] is True

def test_first_tier_is_request_bound(records) -> None:
    axis = map30_three_axis(records)
    first = axis["tiers"][0]
    assert first["request_cap"] == 90
    assert first["bottleneck_axis"] == "REQUESTS"
    assert first["hit_requests"] == first["censored"]

def test_unspecified_axis_is_not_forced(records) -> None:
    axis = map30_three_axis(records)
    unspecified = [t for t in axis["tiers"] if t["bottleneck_axis"] == "UNSPECIFIED"]
    for tier in unspecified:
        assert "不能强行归因" in tier["bottleneck_evidence"]

def test_conservative_interval_is_a_range_not_a_promise(records) -> None:
    interval = map30_conservative_interval(map30_three_axis(records))
    assert len(interval["intervals"]) == 3
    for item in interval["intervals"]:
        if not item["available"]:
            continue
        low, high = item["supported_decisions"]
        assert low <= high
        assert item["observed_max_decisions"] >= 0
        assert set(item["tokens_per_decision"]) == {"p10", "p50", "p90"}
    assert "不是对真实模型的承诺" in interval["note"]

def test_candidate_tiers_require_approval(records) -> None:
    axis = map30_three_axis(records)
    assert axis["candidate_tiers"] == [dict(item) for item in MAP30_TIERS]
    assert "需批准" in axis["caution"]

# ------------------------------------------------------------------ six maps
def test_six_map_recheck_marks_unknown_trigger(records) -> None:
    recheck = six_map_recheck(records)
    assert len(recheck["maps"]) == 6
    for row in recheck["maps"]:
        assert row["trigger_display"].startswith("UNKNOWN")
        assert row["trigger_status"] == "UNKNOWN"
        assert row["status"] == "DESCRIPTIVE_ONLY"
        assert row["evidence_version"]

def test_six_map_labels_unchanged(records) -> None:
    labels = {row["map_id"]: row["composite"] for row in six_map_recheck(records)["maps"]}
    assert labels["MAP-08"] == "CEILING"
    assert labels["MAP-26"] == "CEILING"
    assert labels["MAP-30"] == "CENSORED"
    for map_id in ("MAP-16", "MAP-18", "MAP-22"):
        assert labels[map_id] == "SUITABLE"

def test_independent_seeds_are_listed(records) -> None:
    recheck = six_map_recheck(records)
    by_map = {row["map_id"]: row for row in recheck["maps"]}
    assert by_map["MAP-18"]["independent_seeds"] == [0, 1, 2, 3, 4]
    assert by_map["MAP-08"]["independent_seeds"] == [0, 1, 2]

# ------------------------------------------------------------------ candidates
def test_candidate_maps_are_read_only_and_flagged(records) -> None:
    for map_id in CANDIDATE_MAPS:
        audit = candidate_map_audit(map_id, records)
        assert audit["available"] is True
        assert audit["seed_space"], map_id
        assert audit["public_field_count"] > 0
        assert audit["actions"], map_id
        assert audit["reflection_candidate"] in {
            "PLAUSIBLE",
            "UNLIKELY",
            "NEEDS_MORE_EVIDENCE",
        }
        # V12 没有这三张图的数据 → 只能是 NEEDS_MORE_EVIDENCE
        assert audit["reflection_candidate"] == "NEEDS_MORE_EVIDENCE"
        assert "不修改地图规则" in audit["note"]

def test_candidate_audit_never_invents_seeds(records) -> None:
    from agent_arena.v10.runtime.catalog import seed_space

    for map_id in CANDIDATE_MAPS:
        audit = candidate_map_audit(map_id, records)
        assert audit["seed_space"] == list(seed_space(map_id))

def test_unknown_map_is_rejected() -> None:
    audit = candidate_map_audit("MAP-99", [])
    assert audit["available"] is False

# ------------------------------------------------------------------- document
def test_markdown_states_limits(records) -> None:
    text = map_audit_markdown(map_audit_report(records))
    assert "不能推出" in text
    assert "UNKNOWN (0 observed" in text
    assert "保守可达区间" in text
    assert "NEEDS_MORE_EVIDENCE" in text
