"""V11 预算门禁：请求、token、费用与未知消费。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent_arena.web.budget import (
    MIMO_PRICE,
    BudgetExceeded,
    BudgetLimits,
    RunBudget,
    UnknownUsageError,
    price_for_model,
)


def _limits(**overrides: object) -> BudgetLimits:
    payload: dict[str, object] = {
        "max_requests": 3,
        "max_input_tokens": 100_000,
        "max_output_tokens": 10_000,
        "max_cost_cny": Decimal("1.00"),
        "price": MIMO_PRICE,
    }
    payload.update(overrides)
    return BudgetLimits(**payload)  # type: ignore[arg-type]


def test_request_cap_stops_before_fourth_request() -> None:
    budget = RunBudget(_limits(max_requests=3))
    for _ in range(3):
        budget.reserve(estimated_input_tokens=100, output_limit=10)
        budget.settle(input_tokens=90, output_tokens=9)
    with pytest.raises(BudgetExceeded) as info:
        budget.reserve(estimated_input_tokens=100, output_limit=10)
    assert info.value.reason == "request_limit_exceeded"


def test_input_token_cap_is_reserved_before_request() -> None:
    budget = RunBudget(_limits(max_input_tokens=1_000))
    with pytest.raises(BudgetExceeded) as info:
        budget.reserve(estimated_input_tokens=1_001, output_limit=10)
    assert info.value.reason == "input_token_limit_exceeded"


def test_output_token_cap() -> None:
    budget = RunBudget(_limits(max_output_tokens=100))
    with pytest.raises(BudgetExceeded) as info:
        budget.reserve(estimated_input_tokens=100, output_limit=101)
    assert info.value.reason == "output_token_limit_exceeded"


def test_unknown_usage_fails_closed_and_keeps_reservation() -> None:
    budget = RunBudget(_limits())
    budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    with pytest.raises(UnknownUsageError):
        budget.settle(input_tokens=None, output_tokens=None)
    snapshot = budget.snapshot()
    assert snapshot["cost_unknown"] is True
    assert snapshot["reserved_input_tokens"] == 1_000
    with pytest.raises(BudgetExceeded):
        budget.reserve(estimated_input_tokens=10, output_limit=10)


def test_known_failure_releases_reservation() -> None:
    budget = RunBudget(_limits())
    budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    budget.fail(unknown_spend=False)
    assert budget.snapshot()["reserved_input_tokens"] == 0
    budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    budget.settle(input_tokens=999, output_tokens=10)
    assert budget.snapshot()["requests"] == 1


def test_cost_cap_uses_mimo_price_only() -> None:
    strict = RunBudget(_limits(max_cost_cny=Decimal("0.03")))
    strict.reserve(estimated_input_tokens=16_384, output_limit=1_024)
    strict.settle(input_tokens=16_384, output_tokens=1_024)
    with pytest.raises(BudgetExceeded) as info:
        strict.reserve(estimated_input_tokens=16_384, output_limit=1_024)
    assert info.value.reason == "cost_limit_exceeded"


def test_unknown_model_has_no_cost_gate_but_keeps_request_gate() -> None:
    assert price_for_model("gpt-5.6-terra") is None
    budget = RunBudget(_limits(price=None, max_requests=1, max_cost_cny=Decimal("0.01")))
    budget.reserve(estimated_input_tokens=100_000, output_limit=1_000)
    budget.settle(input_tokens=100_000, output_tokens=1_000)
    snapshot = budget.snapshot()
    assert snapshot["cost_enforced"] is False
    assert snapshot["cost_projected_cny"] is None
    with pytest.raises(BudgetExceeded):
        budget.reserve(estimated_input_tokens=10, output_limit=10)


def test_snapshot_is_json_serializable() -> None:
    import json

    budget = RunBudget(_limits())
    budget.reserve(estimated_input_tokens=100, output_limit=10)
    budget.settle(input_tokens=90, output_tokens=9)
    json.dumps(budget.snapshot())


def test_double_reservation_is_rejected() -> None:
    budget = RunBudget(_limits())
    budget.reserve(estimated_input_tokens=100, output_limit=10)
    with pytest.raises(BudgetExceeded) as info:
        budget.reserve(estimated_input_tokens=100, output_limit=10)
    assert info.value.reason == "internal_double_reservation"


def test_cached_tokens_cannot_exceed_input() -> None:
    budget = RunBudget(_limits())
    budget.reserve(estimated_input_tokens=100, output_limit=10)
    with pytest.raises(UnknownUsageError):
        budget.settle(input_tokens=10, output_tokens=1, cached_input_tokens=11)
