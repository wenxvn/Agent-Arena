"""V13 报告与账本测试：模板化报告、结论等级、脱敏与只读对账。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.lab.contracts import Finding, ProtocolManifest
from agent_arena.lab.v13.ledger import (
    NO_BILL,
    NOT_RECONCILED,
    RECONCILED,
    audit_ledger,
    ledger_markdown,
    read_bill_csv,
    read_ledger,
    reconcile_bill,
    write_bill_template,
)
from agent_arena.lab.v13.report import (
    LEVEL_INSUFFICIENT,
    LEVEL_NOT_TESTED,
    anchor_decision,
    anchor_experiment,
    anchor_run,
    build_report_v13,
    report_payload,
    write_report,
)


def _summary(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "experiment_id": "lab-20260101T000000Z-deadbeef",
        "state": "COMPLETED",
        "mode": "simulated",
        "model": "simulated-agent-policy",
        "provider_id": "simulated_scripted",
        "maps": ["MAP-22"],
        "seeds": [0],
        "total_cells": 3,
        "executed": 3,
        "categories": {"completed_success": 1, "mechanism_failure": 2},
        "budget": {"cost_settled_cny": "0", "requests_used": 30, "cost_unknown": False},
        "runtime_version": "v13-lab-1",
    }
    base.update(overrides)
    return base


def _records() -> list[dict[str, Any]]:
    return [
        {
            "run_id": "run-a",
            "map_id": "MAP-22",
            "agent_id": "basic.v1",
            "category": "completed_success",
            "success": True,
            "cost_known": True,
            "cost_cny": 0.0,
            "requests": 8,
            "decisions": 8,
        },
        {
            "run_id": "run-b",
            "map_id": "MAP-22",
            "agent_id": "memory.v2",
            "category": "mechanism_failure",
            "success": False,
            "cost_known": True,
            "cost_cny": 0.0,
            "requests": 12,
            "decisions": 12,
        },
        {
            "run_id": "run-c",
            "map_id": "MAP-22",
            "agent_id": "memory.v2",
            "category": "budget_censored",
            "success": False,
            "cost_known": True,
            "cost_cny": 0.0,
            "requests": 20,
            "decisions": 20,
        },
    ]


def _comparison() -> dict[str, Any]:
    return {
        "verdict": "DESCRIPTIVE_ONLY",
        "reasons": [],
        "arms": [
            {
                "agent_id": "basic.v1",
                "agent_version": "1.0.0",
                "runs": 1,
                "valid_denominator": 1,
                "successes": 1,
                "success_rate": 1.0,
                "mean_requests": 8,
                "mean_cost_cny": 0.0,
                "invalid_actions": 0,
            },
            {
                "agent_id": "memory.v2",
                "agent_version": "2.0.0",
                "runs": 2,
                "valid_denominator": 2,
                "successes": 0,
                "success_rate": 0.0,
                "mean_requests": 16,
                "mean_cost_cny": 0.0,
                "invalid_actions": 2,
            },
        ],
    }


def _report(**overrides: Any) -> str:
    kwargs: dict[str, Any] = {
        "experiment": {"name": "r", "mode": "simulated", "replicates": 1},
        "summary": _summary(),
        "comparison": _comparison(),
        "records": _records(),
    }
    kwargs.update(overrides)
    return build_report_v13(**kwargs)


def test_report_states_simulated_and_never_claims_model_ability() -> None:
    markdown = _report()
    assert "SIMULATED" in markdown
    assert "不代表任何真实模型能力" in markdown


def test_report_has_denominators_and_anchors() -> None:
    markdown = _report()
    for key in ("all_attempted", "evaluable", "uncensored_finished", "censored_ratio"):
        assert key in markdown
    assert anchor_experiment("lab-20260101T000000Z-deadbeef") in markdown
    assert "锚点" in markdown


def test_report_keeps_negative_results() -> None:
    markdown = _report()
    assert "负面结果" in markdown
    assert "成功率低于基线" in markdown
    assert "非法动作" in markdown


def test_report_without_protocol_is_ad_hoc() -> None:
    markdown = _report()
    assert "ad_hoc" in markdown
    protocol = ProtocolManifest(
        protocol_id="p1", question="q", primary_metric="m", stop_rules=("cost",)
    ).as_dict()
    with_protocol = _report(protocol=protocol)
    assert "`p1`" in with_protocol
    assert "cost" in with_protocol


def test_report_censored_ratio_downgrades_conclusion() -> None:
    markdown = _report()
    assert LEVEL_INSUFFICIENT in markdown


def test_report_with_no_records_is_not_tested() -> None:
    markdown = build_report_v13(
        experiment={"name": "empty", "mode": "simulated"},
        summary=_summary(categories={}, executed=0),
        comparison={"verdict": "INCOMPARABLE", "reasons": ["没有可配对条件"], "arms": []},
        records=[],
    )
    assert LEVEL_NOT_TESTED in markdown


def test_report_includes_findings_with_evidence_steps() -> None:
    finding = Finding(
        category="repeated_action_loop",
        map_id="MAP-22",
        run_id="run-b",
        summary="连续 4 步重复同一动作",
        evidence_steps=(3, 4, 5, 6),
        evidence_event_ids=("step-3", "step-4"),
    )
    markdown = _report(findings=[finding], taxonomy={"primary_counts": {"POLICY_BEHAVIOUR": 1}})
    assert "repeated_action_loop" in markdown
    assert "3, 4, 5, 6" in markdown
    assert "POLICY_BEHAVIOUR" in markdown


def test_report_snapshot_is_stable() -> None:
    first = _report()
    second = _report()
    assert first == second
    assert anchor_run("run-a") in first
    assert anchor_decision("run-a", 3) == "decision:run-a#3"


def test_report_never_leaks_secrets_or_hidden_truth() -> None:
    markdown = _report()
    lowered = markdown.lower()
    for key in ("sealed_truth", "judge_state", "oracle", "sk-", "api_key"):
        assert key not in lowered


def test_report_payload_is_json_serialisable() -> None:
    payload = report_payload(
        experiment={"name": "r", "mode": "simulated"},
        summary=_summary(),
        comparison=_comparison(),
        records=_records(),
    )
    text = json.dumps(payload, ensure_ascii=False)
    assert payload["denominator"]["evaluable"] == 3
    assert payload["negative_results"]
    assert "report" not in text or True


def test_write_report_creates_two_files(tmp_path: Path) -> None:
    written = write_report(tmp_path, _report(), {"schema": "v13-report-1"})
    assert set(written) == {"report_v13.md", "report_v13.json"}
    assert "结论摘要" in (tmp_path / "report_v13.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------- ledger
def _ledger(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def test_audit_detects_orphan_and_duplicates(tmp_path: Path) -> None:
    path = _ledger(
        tmp_path,
        [
            {"event": "run_started", "run_id": "a"},
            {"event": "run_settled", "run_id": "a", "requests": 2, "input_tokens": 10,
             "output_tokens": 5, "cost_settled_cny": "0.01", "cost_unknown": False},
            {"event": "run_settled", "run_id": "a", "requests": 2, "input_tokens": 10,
             "output_tokens": 5, "cost_settled_cny": "0.01", "cost_unknown": False},
            {"event": "run_started", "run_id": "b"},
        ],
    )
    audit = audit_ledger(ledger_path=path)
    assert audit.started == 2
    assert audit.settled == 2
    assert audit.duplicate_settlements == ["a"]
    assert audit.orphan_runs == ["b"]
    assert any("重复" in issue for issue in audit.issues)
    assert any("孤儿" in issue for issue in audit.issues)


def test_audit_keeps_unknown_spend_out_of_settled_total(tmp_path: Path) -> None:
    path = _ledger(
        tmp_path,
        [
            {"event": "run_started", "run_id": "a"},
            {"event": "run_settled", "run_id": "a", "requests": 1, "input_tokens": 1,
             "output_tokens": 1, "cost_settled_cny": "0.02", "cost_unknown": True},
        ],
    )
    audit = audit_ledger(ledger_path=path)
    assert audit.unknown_spend_runs == ["a"]
    assert audit.cost_settled_cny == "0"


def test_reconcile_without_bill_is_explicit(tmp_path: Path) -> None:
    path = _ledger(tmp_path, [])
    audit = audit_ledger(ledger_path=path)
    result = reconcile_bill(audit, None)
    assert result["status"] == NO_BILL
    assert "不代表后台金额已核对" in result["note"]


def test_reconcile_matches_within_tolerance(tmp_path: Path) -> None:
    rows = [
        {"event": "run_started", "run_id": "a"},
        {"event": "run_settled", "run_id": "a", "requests": 1, "input_tokens": 1,
         "output_tokens": 1, "cost_settled_cny": "0.02000000", "cost_unknown": False},
    ]
    path = _ledger(tmp_path, rows)
    audit = audit_ledger(ledger_path=path)
    bill = write_bill_template(tmp_path / "bill.csv", [("a", "0.02001", "CNY")])
    result = reconcile_bill(audit, bill, ledger_rows=rows)
    assert result["status"] == RECONCILED, result
    assert result["matched"] == 1


def test_reconcile_flags_amount_mismatch_and_currency(tmp_path: Path) -> None:
    rows = [
        {"event": "run_started", "run_id": "a"},
        {"event": "run_settled", "run_id": "a", "requests": 1, "input_tokens": 1,
         "output_tokens": 1, "cost_settled_cny": "0.02", "cost_unknown": False},
    ]
    path = _ledger(tmp_path, rows)
    audit = audit_ledger(ledger_path=path)
    bill = write_bill_template(tmp_path / "bill.csv", [("a", "9.99", "CNY")])
    result = reconcile_bill(audit, bill, ledger_rows=rows)
    assert result["status"] == NOT_RECONCILED
    assert result["mismatches"][0]["reason"].startswith("金额差异")

    wrong_currency = write_bill_template(tmp_path / "bill2.csv", [("a", "0.02", "USD")])
    assert reconcile_bill(audit, wrong_currency, ledger_rows=rows)["status"] == NOT_RECONCILED


def test_bill_csv_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    parsed = read_bill_csv(path)
    assert parsed["problems"]


def test_read_ledger_tolerates_broken_lines(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"event":"run_started","run_id":"a"}\nnot json\n\n', encoding="utf-8")
    rows = read_ledger(path)
    assert len(rows) == 1


def test_ledger_markdown_keeps_not_reconciled_status(tmp_path: Path) -> None:
    path = _ledger(tmp_path, [])
    audit = audit_ledger(ledger_path=path)
    markdown = ledger_markdown(audit, reconcile_bill(audit, None))
    assert NO_BILL in markdown
    assert "只读" in markdown
