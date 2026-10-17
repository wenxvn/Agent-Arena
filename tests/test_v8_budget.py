"""V8 独立账本的预留、结算、预警与 fail-closed 行为。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from agent_arena.v8 import budget as budget_module
from agent_arena.v8.budget import PriceSheet, V8BudgetClosed, V8BudgetLedger


def make_ledger(
    path: Path,
    *,
    source_hashes: dict[str, str] | None = None,
    resume: bool = False,
) -> V8BudgetLedger:
    return V8BudgetLedger(
        path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes=source_hashes or {"MAP-01": "abc"},
        resume=resume,
    )


def test_cost_uses_uncached_and_output_rates() -> None:
    sheet = PriceSheet(
        "CNY",
        input_uncached_per_million=Decimal("1"),
        input_cached_per_million=Decimal("0.02"),
        output_per_million=Decimal("2"),
        max_cost=Decimal("10"),
    )
    assert sheet.cost(1_000_000, 1_000_000) == Decimal("3")
    assert sheet.cost(1_000_000, 0, 1_000_000) == Decimal("0.02")


def test_reservation_is_released_after_settlement(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("EP-1", decision_index=1, request_hash="h1")
    assert ledger.projected_cost() == ledger.prices.reserve_per_request()
    ledger.settle_request(
        request_id,
        input_tokens=1000,
        output_tokens=100,
        cached_input_tokens=None,
        latency_ms=10,
        decision_payload={"action": {"tool": "wait"}},
    )
    snapshot = ledger.snapshot()
    assert snapshot["pending_reserved_cost"] == "0"
    assert Decimal(snapshot["settled_cost"]) == Decimal("0.0012")
    assert snapshot["settled_requests"] == 1


def test_unknown_usage_closes_the_ledger(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("EP-1", decision_index=1, request_hash="h1")
    with pytest.raises(V8BudgetClosed):
        ledger.settle_request(
            request_id,
            input_tokens=None,
            output_tokens=None,
            cached_input_tokens=None,
            latency_ms=10,
            decision_payload={},
        )
    assert ledger.closed


def test_usage_outside_registered_cap_closes_the_ledger(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("EP-1", decision_index=1, request_hash="h1")
    with pytest.raises(V8BudgetClosed):
        ledger.settle_request(
            request_id,
            input_tokens=99_999,
            output_tokens=10,
            cached_input_tokens=0,
            latency_ms=10,
            decision_payload={},
        )
    assert ledger.closed


def test_hard_cost_limit_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tiny = PriceSheet(
        "CNY",
        input_uncached_per_million=Decimal("1"),
        input_cached_per_million=Decimal("0.02"),
        output_per_million=Decimal("2"),
        max_cost=Decimal("0.005"),
    )
    monkeypatch.setitem(budget_module.PRICE_SHEETS, "CNY", tiny)
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(V8BudgetClosed):
        ledger.reserve_request("EP-1", decision_index=1, request_hash="h1")
    assert ledger.closed


def test_warning_thresholds_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = PriceSheet(
        "CNY",
        input_uncached_per_million=Decimal("1"),
        input_cached_per_million=Decimal("0.02"),
        output_per_million=Decimal("2"),
        max_cost=Decimal("0.05"),
    )
    monkeypatch.setitem(budget_module.PRICE_SHEETS, "CNY", sheet)
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    for index in range(1, 5):
        request_id = ledger.reserve_request("EP-1", decision_index=index, request_hash="h")
        ledger.settle_request(
            request_id,
            input_tokens=8192,
            output_tokens=1024,
            cached_input_tokens=0,
            latency_ms=1,
            decision_payload={},
        )
    assert ledger.snapshot()["warnings"] == ["0.50", "0.80"]


def test_unknown_spend_failure_retains_reservation(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    request_id = ledger.reserve_request("EP-1", decision_index=1, request_hash="h1")
    ledger.fail_request(
        request_id,
        error_category="APIConnectionError",
        latency_ms=5,
        retryable=False,
        unknown_spend=True,
    )
    # Unknown spend keeps the worst-case reservation in the projected total.
    assert ledger.snapshot()["pending_reserved_cost"] == str(
        ledger.prices.reserve_per_request()
    )
    assert ledger.snapshot()["failed_requests"] == 1
    ledger.close("UNKNOWN_PROVIDER_SPEND")
    assert ledger.closed


def test_resume_rejects_identity_change(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    make_ledger(path)
    with pytest.raises(V8BudgetClosed):
        make_ledger(path, source_hashes={"MAP-01": "different"}, resume=True)


def test_resume_rejects_closed_ledger(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = make_ledger(path)
    ledger.close("GLOBAL_REQUEST_LIMIT")
    with pytest.raises(V8BudgetClosed):
        make_ledger(path, resume=True)


def test_episode_limit_is_registered(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path / "ledger.jsonl")
    for index in range(budget_module.MAX_EPISODES):
        ledger.start_episode(f"EP-{index}", map_id="MAP-01", seed=0, condition_id="default")
    with pytest.raises(V8BudgetClosed):
        ledger.start_episode("EP-new", map_id="MAP-01", seed=0, condition_id="default")
