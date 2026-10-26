"""V12 导出与报告测试：文件齐全、CSV 可复算、报告口径诚实。"""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path

from agent_arena.lab.contracts import (
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.experiment import ExperimentService
from agent_arena.lab.report import (
    FINDINGS_CSV,
    METRICS_CSV,
    PAIRED_CSV,
    RUNS_CSV,
    build_report,
    csv_bytes,
    metrics_rows,
    paired_rows,
    runs_rows,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER
from agent_arena.web.service import RunService


def _spec() -> ExperimentSpec:
    return ExperimentSpec(
        name="export",
        maps=["MAP-22", "MAP-26"],
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
        ],
        environment_seeds=[0, 1],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=5,
            experiment_request_cap=2_000,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    )


def _run_experiment(tmp_path: Path) -> tuple[ExperimentService, RunService, str]:
    runs = RunService(tmp_path / "runs" / "web", recover=False)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    experiment_id = lab.create_experiment(_spec())
    lab.submit(experiment_id)
    lab.wait(experiment_id, timeout=600)
    return lab, runs, experiment_id


def test_export_writes_all_documents(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        for name in (
            RUNS_CSV,
            METRICS_CSV,
            PAIRED_CSV,
            "report.md",
            "summary.json",
            "comparison.json",
            "experiment.json",
        ):
            assert name in files, name
            assert Path(files[name]).is_file()
        assert FINDINGS_CSV in files
    finally:
        runs.shutdown()


def test_runs_csv_can_recompute_summary(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        rows = list(
            csv.DictReader(io.StringIO(Path(files[RUNS_CSV]).read_text(encoding="utf-8-sig")))
        )
        summary = json.loads(Path(files["summary.json"]).read_text(encoding="utf-8"))
        assert len(rows) == summary["executed"]
        valid = sum(
            1
            for row in rows
            if row["category"] in {"completed_success", "mechanism_failure", "budget_censored"}
        )
        assert valid == summary["valid_denominator"]
        successes = sum(1 for row in rows if row["category"] == "completed_success")
        assert successes == summary["successes"]
        # 每行都能追溯到真实 run_id。
        for row in rows:
            assert row["run_id"].startswith("web-")
            assert row["agent_id"] in {"basic.v1", "memory.v1"}
    finally:
        runs.shutdown()


def test_metrics_csv_matches_result_metrics(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        rows = list(
            csv.DictReader(
                io.StringIO(Path(files[METRICS_CSV]).read_text(encoding="utf-8-sig"))
            )
        )
        v10_expected = 0
        v12_expected = 0
        for record in lab.records(experiment_id):
            v10_expected += len(record["metrics"])
            v12_expected += len(record.get("metrics_v12") or {})
        v10_rows = [row for row in rows if row["namespace"] == "v10"]
        v12_rows = [row for row in rows if row["namespace"] == "v12.projection"]
        assert len(v10_rows) == v10_expected
        assert len(v12_rows) == v12_expected
        for row in rows:
            assert row["metric_id"]
            assert row["namespace"] in {"v10", "v12.projection"}
            assert row["state"] in {
                "VALID",
                "CENSORED",
                "NOT_APPLICABLE",
                "INVALID_TRACE",
                "UNAVAILABLE",
            }
            if row["state"] != "VALID":
                assert row["value"] == "", "非 VALID 不得有取值"
    finally:
        runs.shutdown()


def test_paired_csv_declares_verdict_and_reasons(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        rows = list(
            csv.DictReader(io.StringIO(Path(files[PAIRED_CSV]).read_text(encoding="utf-8-sig")))
        )
        assert rows
        assert {row["verdict"] for row in rows} <= {
            "COMPARABLE",
            "DESCRIPTIVE_ONLY",
            "INCOMPARABLE",
        }
        assert all(row["left_run_id"] and row["right_run_id"] for row in rows)
    finally:
        runs.shutdown()


def test_report_declares_simulated_mode_and_limits(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        report = lab.report(experiment_id)
        assert "SIMULATED" in report
        assert "不代表任何真实模型能力" in report
        assert "不作显著性断言" in report
        assert "不可比声明" in report or "配对比较判定" in report
        assert "复现" in report
        for forbidden in ("sealed_truth", "judge_state", "sk-"):
            assert forbidden not in report.lower()
    finally:
        runs.shutdown()


def test_report_uses_real_numbers_only(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        report = lab.report(experiment_id)
        summary = lab.summary(experiment_id)
        assert f"{summary['executed']} / {summary['total_cells']}" in report
        for arm in summary["arms"]:
            assert arm["agent_id"] in report
    finally:
        runs.shutdown()


def test_csv_bytes_is_utf8_bom() -> None:
    blob = csv_bytes([{"a": 1}], ("a",))
    assert blob.startswith(b"\xef\xbb\xbf")


def test_runs_rows_include_category_label() -> None:
    rows = runs_rows(
        [
            {
                "run_id": "r",
                "map_id": "MAP-22",
                "category": "completed_success",
                "agent_id": "basic.v1",
            }
        ]
    )
    assert rows[0]["category_label"] == "完成且成功"


def test_metrics_rows_skip_non_dict_payloads() -> None:
    rows = metrics_rows(
        [{"run_id": "r", "metrics": {"a": {"state": "VALID", "value": 1}, "b": "bad"}}]
    )
    assert len(rows) == 1
    assert rows[0]["metric_id"] == "a"


def test_paired_rows_join_reasons() -> None:
    rows = paired_rows(
        {"pairs": [{"left_run_id": "a", "right_run_id": "b", "reasons": ["x", "y"]}]}
    )
    assert rows[0]["reasons"] == "x；y"


def test_build_report_without_records_is_honest() -> None:
    report = build_report(
        experiment={"name": "empty", "mode": "simulated"},
        summary={
            "experiment_id": "lab-x",
            "state": "CREATED",
            "maps": [],
            "seeds": [],
            "arms": [],
            "executed": 0,
            "total_cells": 0,
            "pending": 0,
            "categories": {},
            "model": SIMULATED_MODEL,
            "provider_id": SIMULATED_PROVIDER,
        },
        comparison={"verdict": "INCOMPARABLE", "reasons": ["未执行"], "arms": [], "per_map": []},
        records=[],
        findings=[],
    )
    assert "尚未执行" in report
    assert "没有产生诊断结论" in report


def test_exported_json_has_no_hidden_truth(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        for name in ("summary.json", "comparison.json", "experiment.json"):
            text = Path(files[name]).read_text(encoding="utf-8").lower()
            for forbidden in ("sealed_truth", "judge_state", "truth_seal"):
                assert forbidden not in text, name
    finally:
        runs.shutdown()


def test_findings_csv_has_evidence_steps(tmp_path: Path) -> None:
    lab, runs, experiment_id = _run_experiment(tmp_path)
    try:
        files = lab.export(experiment_id)
        rows = list(
            csv.DictReader(io.StringIO(Path(files[FINDINGS_CSV]).read_text(encoding="utf-8-sig")))
        )
        assert rows
        assert all(row["category"] for row in rows)
        assert all(row["severity"] in {"critical", "warning", "info"} for row in rows)
    finally:
        runs.shutdown()
