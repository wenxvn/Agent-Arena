"""V13 重复稳定性测试：必须能复现 V12 公布的 22.2% / 25.0%。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.lab.v13.history import (
    V12_REAL_RUNS,
    history_index,
    load_v12_history,
)
from agent_arena.lab.v13.stability import (
    EVIDENCE_SINGLE,
    EVIDENCE_STABLE,
    EVIDENCE_UNSTABLE,
    flip_interval,
    group_records,
    replicate_variability,
    seed_blocks,
    variability_markdown,
    wilson_interval,
    write_variability,
)

TWO_OBS = ["main-54-runs.csv", "replicate-16-18-runs.csv"]
THREE_OBS = [*TWO_OBS, "replicate-16-18-b-runs.csv"]


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": "r",
        "map_id": "MAP-16",
        "environment_seed": 0,
        "agent_id": "basic.v1",
        "agent_config_hash": "cfg",
        "agent_version": "1.0.0",
        "replicate_index": 0,
        "category": "mechanism_failure",
        "success": False,
        "cost_known": True,
        "cost_cny": 0.01,
        "decisions": 10,
        "request_cap": 90,
        "input_token_cap": 200_000,
        "model": "mimo",
        "mode": "live",
    }
    base.update(overrides)
    return base


def test_reproduces_v12_two_observation_flip_rate() -> None:
    records = load_v12_history(names=TWO_OBS)
    report = replicate_variability(records, min_obs=2)
    assert report["records"] == 72
    assert report["comparable_groups"] == 18
    assert report["groups_with_flip"] == 4
    assert report["flip_rate"] == 0.2222
    assert report["excluded_not_comparable"] == 0


def test_reproduces_v12_three_observation_flip_rate() -> None:
    records = load_v12_history(names=THREE_OBS)
    report = replicate_variability(records, min_obs=2)
    assert report["records"] == 90
    assert report["comparable_groups"] == 12
    assert report["groups_with_flip"] == 3
    assert report["flip_rate"] == 0.25
    # 6 组 memory.v1 因默认配置变化跨版本，必须被排除（DCR-V12-06）。
    assert report["excluded_not_comparable"] == 6


def test_planning_seed1_is_the_only_three_of_three() -> None:
    records = load_v12_history(names=THREE_OBS)
    report = replicate_variability(records, min_obs=2)
    always = report["always_success_conditions"]
    assert "MAP-16|seed=1|planning.v1" in always
    assert all("basic.v1" not in item for item in always)


def test_cross_version_group_is_excluded_not_counted() -> None:
    records = [
        _record(
            replicate_index=0,
            agent_config_hash="old",
            category="completed_success",
            success=True,
        ),
        _record(replicate_index=1, agent_config_hash="new", category="mechanism_failure"),
    ]
    report = replicate_variability(records, min_obs=2)
    assert report["comparable_groups"] == 0
    assert report["flip_rate"] is None
    assert report["excluded_not_comparable"] == 1
    row = report["rows"][0]
    assert "跨版本" in row["mismatch"]
    assert row["evidence"] == "NOT_COMPARABLE"


def test_cross_budget_group_is_excluded() -> None:
    records = [
        _record(replicate_index=0, request_cap=90),
        _record(replicate_index=1, request_cap=180),
    ]
    report = replicate_variability(records, min_obs=2)
    assert report["excluded_not_comparable"] == 1
    assert "跨预算" in report["rows"][0]["mismatch"]


def test_single_observation_is_labeled_single_not_stable() -> None:
    report = replicate_variability([_record()], min_obs=2)
    assert report["rows"][0]["evidence"] == EVIDENCE_SINGLE
    assert report["comparable_groups"] == 0


def test_stable_group_requires_three_observations() -> None:
    two = [_record(replicate_index=index) for index in range(2)]
    three = [_record(replicate_index=index) for index in range(3)]
    assert group_records(two)["MAP-16|seed=0|basic.v1"].evidence_label != EVIDENCE_STABLE
    assert group_records(three)["MAP-16|seed=0|basic.v1"].evidence_label == EVIDENCE_STABLE


def test_flip_detected_within_group() -> None:
    records = [
        _record(replicate_index=0),
        _record(replicate_index=1, category="completed_success", success=True),
    ]
    group = group_records(records)["MAP-16|seed=0|basic.v1"]
    assert group.flips
    assert group.evidence_label == EVIDENCE_UNSTABLE


def test_seed_blocks_do_not_treat_repeats_as_new_seeds() -> None:
    records = [_record(replicate_index=index) for index in range(3)]
    blocks = seed_blocks(records)
    assert len(blocks) == 1
    assert blocks[0]["arms"][0]["observations"] == 3


def test_wilson_interval_is_bounded() -> None:
    low, high = wilson_interval(4, 18)
    assert 0 <= low < high <= 1
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_flip_interval_carries_premise() -> None:
    records = load_v12_history(names=TWO_OBS)
    report = replicate_variability(records, min_obs=2)
    interval = flip_interval(report)
    assert interval["n_groups"] == 18
    assert "描述性" in interval["premise"]


def test_writes_three_files_without_touching_source(tmp_path: Path) -> None:
    records = load_v12_history(names=TWO_OBS)
    before = sorted(path.name for path in V12_REAL_RUNS.iterdir())
    report = replicate_variability(records, min_obs=2)
    written = write_variability(report, tmp_path)
    assert set(written) == {"repeat_variability.csv", "repeat_variability.json",
                            "repeat_variability.md"}
    payload = json.loads((tmp_path / "repeat_variability.json").read_text(encoding="utf-8"))
    assert payload["flip_rate"] == 0.2222
    markdown = (tmp_path / "repeat_variability.md").read_text(encoding="utf-8")
    assert "重复不是新的环境 seed" in markdown
    assert "DESCRIPTIVE_ONLY" in markdown or "DESCRIPTIVE" in markdown
    after = sorted(path.name for path in V12_REAL_RUNS.iterdir())
    assert before == after


def test_history_index_groups_by_experiment() -> None:
    records = load_v12_history(names=THREE_OBS)
    index = history_index(records)
    assert index["runs"] == 90
    assert len(index["experiments"]) == 3
    assert all(item["runs"] > 0 for item in index["experiments"].values())


def test_markdown_marks_historical_source() -> None:
    records = load_v12_history(names=TWO_OBS)
    report = replicate_variability(records, min_obs=2)
    markdown = variability_markdown(report)
    assert "HISTORICAL" in markdown
    assert "Wilson" in markdown
