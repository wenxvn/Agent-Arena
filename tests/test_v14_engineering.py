"""V14 Batch 11（P2-2 / P2-4 / P2-5 / P2-6）：工程边界。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.perf import synthesize_history
from agent_arena.lab.v14.engineering import (
    DEFAULT_LEDGER_PATH,
    EXTERNAL_BILL_STATUS,
    V12_LEDGER_EXPECTATION,
    cold_start_measurement,
    concurrent_read_during_write,
    corrupted_manifest_handling,
    engineering_markdown,
    export_consistency,
    ledger_recompute,
    long_history_export,
    sdk_hardening,
    ttl_refresh,
)

REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"

@pytest.fixture()
def temp_base() -> Path:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v14-test-") as temporary:
        yield Path(temporary)

# ----------------------------------------------------------------- perf basics
def test_cold_start_reports_cold_and_warm_separately(temp_base) -> None:
    base = temp_base / "cold"
    synthesize_history(base, 50)
    report = cold_start_measurement(base)
    labels = [item["label"] for item in report["measurements"]]
    assert labels == ["cold_first_open", "warm_page_first_50", "warm_index_rebuild"]
    assert all(item["milliseconds"] >= 0 for item in report["measurements"])
    assert "不可互相替代" in report["note"]

def test_corrupted_manifest_is_skipped_not_counted(temp_base) -> None:
    report = corrupted_manifest_handling(temp_base / "corrupted")
    assert report["crashed"] is False
    assert report["bad_run_indexed"] is False
    assert report["good_runs"] == 5
    assert report["page_entries"] == 5
    assert report["no_private_fields"] is True

def test_concurrent_read_during_write_has_no_errors(temp_base) -> None:
    report = concurrent_read_during_write(temp_base / "concurrent", rounds=10)
    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["final_indexed_runs"] >= 20
    assert report["min_page_entries"] >= 1

def test_ttl_refresh_sees_new_run(temp_base) -> None:
    report = ttl_refresh(temp_base / "ttl")
    assert report["ok"] is True
    assert report["after_ttl_expiry"] > report["before"]

def test_long_history_export_counts_rows(temp_base) -> None:
    report = long_history_export(temp_base / "long", count=200)
    assert report["runs"] == 200
    assert report["rows_exported"] == 200
    assert report["ok"] is True

# ---------------------------------------------------------- export consistency
_RUNS_CSV = (
    "run_id,map_id,environment_seed,agent_id,category,mode,cost_cny\n"
    "r1,MAP-22,0,basic.v1,completed_success,simulated,0.01\n"
    "r2,MAP-22,0,memory.v1,mechanism_failure,simulated,0.01\n"
)

_METRICS_CSV = (
    "metric,state,value\n"
    "map22.v10.mission_success,VALID,0.5\n"
    "map22.v10.route_recall,NOT_APPLICABLE,\n"
)

def test_export_consistency_passes_for_matching_files() -> None:
    result = export_consistency(
        {"runs.csv": _RUNS_CSV, "metrics.csv": _METRICS_CSV},
        metrics={"runs": 2, "valid_denominator": 2},
        report_text="模式：simulated（SIMULATED）",
        expected_mode="simulated",
    )
    assert result["ok"] is True
    assert result["problems"] == []

def test_export_consistency_detects_row_count_mismatch() -> None:
    result = export_consistency(
        {"runs.csv": _RUNS_CSV},
        metrics={"runs": 3, "valid_denominator": 2},
        report_text="simulated",
        expected_mode="simulated",
    )
    assert result["ok"] is False
    assert any("行数" in item for item in result["problems"])

def test_export_consistency_detects_denominator_mismatch() -> None:
    result = export_consistency(
        {"runs.csv": _RUNS_CSV},
        metrics={"runs": 2, "valid_denominator": 5},
        report_text="simulated",
        expected_mode="simulated",
    )
    assert any(
        "有效分母" in item or "valid_denominator" in item for item in result["problems"]
    )

def test_export_consistency_detects_mode_mix() -> None:
    mixed = _RUNS_CSV.replace(
        "r2,MAP-22,0,memory.v1,mechanism_failure,simulated",
        "r2,MAP-22,0,memory.v1,mechanism_failure,live",
    )
    result = export_consistency(
        {"runs.csv": mixed},
        metrics={"runs": 2, "valid_denominator": 2},
        report_text="simulated",
        expected_mode="simulated",
    )
    assert any(
        "mode" in item or "模式" in item or "执行模式" in item
        for item in result["problems"]
    )

def test_valid_metric_with_empty_value_is_flagged() -> None:
    bad_metrics = "metric,state,value\nmap22.v10.mission_success,VALID,\n"
    result = export_consistency(
        {"runs.csv": _RUNS_CSV, "metrics.csv": bad_metrics},
        metrics={"runs": 2, "valid_denominator": 2},
        report_text="simulated",
        expected_mode="simulated",
    )
    assert result["silent_zero_metrics"]
    assert any("VALID" in item for item in result["problems"])

def test_non_nullable_empty_cell_is_flagged() -> None:
    bad_runs = (
        "run_id,map_id,environment_seed,agent_id,category,mode,cost_cny\n"
        "r1,MAP-22,0,basic.v1,,simulated,0.01\n"
    )
    result = export_consistency(
        {"runs.csv": bad_runs},
        metrics={"runs": 1, "valid_denominator": 0},
        report_text="simulated",
        expected_mode="simulated",
    )
    assert result["empty_cells"] == ["category"]

# ------------------------------------------------------------------ SDK checks
def test_sdk_hardening_runs_all_checks() -> None:
    report = sdk_hardening()
    names = {item["name"] for item in report["extra_checks"]}
    assert names == {
        "legacy_signature_compatible",
        "policy_exception_isolated",
        "budget_gateway_not_bypassable",
    }
    assert report["ok"] is True
    assert "不声称可以安全运行任意第三方代码" in report["note"]

# --------------------------------------------------------------------- ledger
def test_ledger_expectation_constants() -> None:
    assert V12_LEDGER_EXPECTATION["runs"] == 159
    assert V12_LEDGER_EXPECTATION["requests"] == 5_641
    assert V12_LEDGER_EXPECTATION["settled_cost_cny"] == "5.43680012"

def test_ledger_absent_is_reported_not_faked(tmp_path: Path) -> None:
    report = ledger_recompute([], ledger_path=tmp_path / "missing.jsonl")
    assert report["status"] == "LEDGER_NOT_PRESENT_LOCALLY"
    assert report["open_ledger"] is None
    assert report["matches_v13_record"] is False
    assert report["external_bill"]["status"] == EXTERNAL_BILL_STATUS

def _settled(run_id: str, requests: int = 10, cost: str = "0.01000000") -> str:
    return json.dumps(
        {
            "event": "run_settled",
            "run_id": run_id,
            "requests": requests,
            "cost_settled_cny": cost,
        }
    )

def test_ledger_recompute_from_synthetic_ledger(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    lines = [
        json.dumps({"event": "run_started", "run_id": "r0"}),
        _settled("r0"),
        json.dumps({"event": "run_started", "run_id": "r1"}),
        _settled("r1"),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = ledger_recompute([], ledger_path=path)
    assert report["status"] == "RECOMPUTED"
    open_ledger = report["open_ledger"]
    assert open_ledger["settled"] == 2
    assert open_ledger["requests"] == 20
    assert open_ledger["settled_cost_cny"] == "0.02000000"
    assert open_ledger["duplicates"] == 0
    assert open_ledger["orphans"] == 0
    # 与 V13 的 159 局不一致 → 必须显式 False
    assert report["matches_v13_record"] is False

def test_ledger_detects_orphan_and_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    lines = [
        _settled("orphan", requests=1),
        json.dumps({"event": "run_started", "run_id": "r1"}),
        _settled("r1", requests=1),
        _settled("r1", requests=1),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = ledger_recompute([], ledger_path=path)
    assert report["open_ledger"]["orphans"] == 1
    assert report["open_ledger"]["duplicates"] == 1
    assert report["matches_v13_record"] is False

@pytest.mark.skipif(
    not (REAL_RUNS.is_dir() and DEFAULT_LEDGER_PATH.is_file()),
    reason="需要 docs/v12/real-runs 与 runs/web/_ledger（本机只读）",
)
def test_real_ledger_matches_v13_record() -> None:
    from agent_arena.lab.v13.history import load_v12_history

    report = ledger_recompute(load_v12_history())
    assert report["status"] == "RECOMPUTED"
    assert report["matches_v13_record"] is True
    open_ledger = report["open_ledger"]
    assert open_ledger["settled"] == 159
    assert open_ledger["requests"] == 5641
    assert open_ledger["settled_cost_cny"] == "5.43680012"
    assert open_ledger["duplicates"] == 0
    assert open_ledger["orphans"] == 0

# -------------------------------------------------------------------- document
def test_markdown_contains_all_sections() -> None:
    report = {
        "cold_start": {
            "runs": 1,
            "measurements": [
                {"label": "cold_first_open", "milliseconds": 1.0, "detail": "d"}
            ],
            "note": "n",
        },
        "corrupted_manifest": {
            "bad_run_indexed": False,
            "indexed_runs": 1,
            "page_entries": 1,
        },
        "concurrent": {
            "ok": True,
            "rounds": 1,
            "error_count": 0,
            "final_indexed_runs": 1,
        },
        "ttl_refresh": {
            "ok": True,
            "before": 1,
            "after_ttl_expiry": 2,
            "after_invalidate": 2,
            "ttl_seconds": 30.0,
        },
        "long_export": {
            "rows_exported": 1,
            "runs": 1,
            "export_ms": 1.0,
            "index_bytes_estimate": 10,
            "note": "n",
        },
        "sdk": {"base_checks": [], "extra_checks": [], "ok": True, "note": "n"},
        "ledger": {
            "status": "LEDGER_NOT_PRESENT_LOCALLY",
            "open_ledger": None,
            "csv_subset": {"runs": 1, "requests": 1, "settled_cost_cny": "0.00000001"},
            "expected": V12_LEDGER_EXPECTATION,
            "matches_v13_record": False,
            "external_bill": {"status": EXTERNAL_BILL_STATUS, "note": "n"},
            "note": "n",
        },
        "export_consistency": {
            "files": {"runs.csv": 1},
            "modes": ["simulated"],
            "valid_denominator_computed": 1,
            "empty_cells": [],
            "problems": [],
            "ok": True,
            "note": "n",
        },
    }
    text = engineering_markdown(report)
    for heading in (
        "冷启动与预热",
        "异常负载",
        "长历史导出",
        "SDK 加固",
        "账本复算",
        "导出一致性",
    ):
        assert heading in text
    assert EXTERNAL_BILL_STATUS in text