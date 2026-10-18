"""Batch 8：V10 独立账本与全局额度共享的单元测试（无任何网络调用）。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from agent_arena.v10.ledger import (
    CAP_CNY,
    MAX_INPUT_TOKENS_PER_REQUEST,
    V10BudgetClosed,
    V10BudgetLedger,
    global_spend,
    ledger_spend,
)


def _ledger(
    path: Path, *, prior_spend: Decimal = Decimal(0), resume: bool = False
) -> V10BudgetLedger:
    return V10BudgetLedger(
        path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"manifest": "m", "schema": "s"},
        prior_spend=prior_spend,
        resume=resume,
    )


def test_reserve_then_settle_tracks_cost(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    reservation = ledger.prices.reserve_per_request()
    assert ledger.projected_cost() == reservation
    ledger.settle_request(
        request_id,
        input_tokens=1_000,
        output_tokens=100,
        cached_input_tokens=0,
        latency_ms=12,
        decision_payload={"candidate": {"tool": "wait"}},
    )
    expected = Decimal(1_000) / Decimal(1_000_000) + Decimal(200) / Decimal(1_000_000)
    assert ledger.projected_cost() == expected
    assert ledger.episode_usage("ep-1")["cost"] == str(expected)
    assert ledger.snapshot()["settled_requests"] == 1


def test_prior_spend_counts_toward_global_cap(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl", prior_spend=Decimal("9.99"))
    with pytest.raises(V10BudgetClosed):
        ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    assert ledger.closed
    assert ledger.snapshot()["projected_cost"] == "9.99"


def test_unknown_provider_spend_seals_and_retains_reservation(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    ledger.fail_request(
        request_id,
        error_category="APIConnectionError",
        latency_ms=5,
        retryable=False,
        unknown_spend=True,
    )
    assert ledger.projected_cost() == ledger.prices.reserve_per_request()
    with pytest.raises(V10BudgetClosed):
        ledger.reserve_request("ep-1", decision_index=1, request_hash="h2")


def test_missing_usage_seals_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    with pytest.raises(V10BudgetClosed):
        ledger.settle_request(
            request_id,
            input_tokens=None,
            output_tokens=None,
            cached_input_tokens=None,
            latency_ms=1,
            decision_payload={},
        )
    assert ledger.closed
    reasons = [
        event["reason"]
        for event in ledger.read_events()
        if event["event"] == "experiment_closed"
    ]
    assert reasons == ["UNKNOWN_PROVIDER_USAGE"]


def test_usage_above_registered_cap_seals_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    with pytest.raises(V10BudgetClosed):
        ledger.settle_request(
            request_id,
            input_tokens=MAX_INPUT_TOKENS_PER_REQUEST + 1,
            output_tokens=1,
            cached_input_tokens=0,
            latency_ms=1,
            decision_payload={},
        )
    assert ledger.closed


def test_episode_start_and_complete_are_idempotent(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl")
    ledger.start_episode("ep-1", map_id="MAP-18", seed=2, condition_id="v10")
    ledger.start_episode("ep-1", map_id="MAP-18", seed=2, condition_id="v10")
    ledger.complete_episode("ep-1", status="success", success=True, decision_count=7)
    ledger.complete_episode("ep-1", status="success", success=True, decision_count=7)
    assert ledger.completed_episode_ids() == {"ep-1"}
    snapshot = ledger.snapshot()
    assert snapshot["episodes_started"] == 1
    assert snapshot["episodes_completed"] == 1


def test_resume_rejects_mismatched_source_hashes(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    _ledger(path)
    with pytest.raises(V10BudgetClosed):
        V10BudgetLedger(
            path,
            currency="CNY",
            model="mimo-v2.6-flash",
            source_hashes={"manifest": "other", "schema": "s"},
            resume=True,
        )


def test_resume_detects_unresolved_request(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = _ledger(path)
    ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    with pytest.raises(V10BudgetClosed):
        _ledger(path, resume=True)
    reasons = [
        event["reason"]
        for event in ledger.read_events()
        if event["event"] == "experiment_closed"
    ]
    assert reasons == ["UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST"]


def test_global_spend_sums_multiple_ledgers(tmp_path: Path) -> None:
    first = tmp_path / "ledger.jsonl"
    second = tmp_path / "ledger_supplement_001.jsonl"
    ledger_a = _ledger(first)
    request_a = ledger_a.reserve_request("ep-a", decision_index=0, request_hash="a")
    ledger_a.settle_request(
        request_a,
        input_tokens=1_000,
        output_tokens=0,
        cached_input_tokens=0,
        latency_ms=1,
        decision_payload={},
    )
    ledger_b = _ledger(second)
    ledger_b.reserve_request("ep-b", decision_index=0, request_hash="b")

    settled, pending, requests = global_spend([first, second])
    assert settled == Decimal("0.001")
    assert pending == ledger_b.prices.reserve_per_request()
    assert requests == 2
    assert ledger_spend(tmp_path / "missing.jsonl") == (Decimal(0), Decimal(0), 0)


def test_cap_is_hard_ten_cny(tmp_path: Path) -> None:
    ledger = V10BudgetLedger(
        tmp_path / "ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"manifest": "m", "schema": "s"},
        max_cost=Decimal("9999"),
    )
    assert ledger.max_cost == CAP_CNY


def test_budget_warning_recorded_once(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "ledger.jsonl", prior_spend=Decimal("4.99"))
    request_id = ledger.reserve_request("ep-1", decision_index=0, request_hash="h")
    ledger.settle_request(
        request_id,
        input_tokens=10_000,
        output_tokens=1_000,
        cached_input_tokens=0,
        latency_ms=1,
        decision_payload={},
    )
    fractions = [
        event["fraction"]
        for event in ledger.read_events()
        if event["event"] == "budget_warning"
    ]
    assert fractions[:1] == ["0.50"] or "0.50" in fractions


def test_created_event_records_registered_limits(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    _ledger(path)
    created = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert created["max_input_tokens_per_request"] == MAX_INPUT_TOKENS_PER_REQUEST
    assert created["max_cost"] == str(CAP_CNY)
