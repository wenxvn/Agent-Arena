"""V9 预算账本、公开策略与 runner 边界测试。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from agent_arena.v9.baselines import RandomPolicy, ShapeSampler, run_policy
from agent_arena.v9.budget import PRICE_SHEETS, V9BudgetClosed, V9BudgetLedger
from agent_arena.worlds.scenario_v8.catalog import create_environment


def _ledger(tmp_path: Path, **kwargs: object) -> V9BudgetLedger:
    return V9BudgetLedger(
        tmp_path / "ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-01": "hash"},
        **kwargs,  # type: ignore[arg-type]
    )


def test_ledger_reserves_before_settles(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.start_episode("e1", map_id="MAP-01", seed=0, condition_id="default")
    request_id = ledger.reserve_request("e1", decision_index=1, request_hash="r1")
    assert ledger.projected_cost() == PRICE_SHEETS["CNY"].reserve_per_request()
    ledger.settle_request(
        request_id,
        input_tokens=1_000,
        output_tokens=100,
        cached_input_tokens=0,
        latency_ms=10,
        decision_payload={"result": "MOVED:L1"},
    )
    assert ledger.projected_cost() == Decimal("0.0012")
    snapshot = ledger.snapshot()
    assert snapshot["settled_requests"] == 1
    assert snapshot["closed"] is False


def test_unknown_spend_requires_explicit_close(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.start_episode("e1", map_id="MAP-01", seed=0, condition_id="default")
    request_id = ledger.reserve_request("e1", decision_index=1, request_hash="r1")
    ledger.fail_request(
        request_id,
        error_category="APIConnectionError",
        latency_ms=1,
        retryable=False,
        unknown_spend=True,
    )
    ledger.close("UNKNOWN_PROVIDER_SPEND")
    with pytest.raises(V9BudgetClosed):
        ledger.reserve_request("e1", decision_index=2, request_hash="r2")


def test_ledger_refuses_reuse_and_cap(tmp_path: Path) -> None:
    _ledger(tmp_path)
    with pytest.raises(FileExistsError):
        _ledger(tmp_path)
    tiny = _ledger(tmp_path / "tiny", max_cost=Decimal("0.0001"))
    tiny.start_episode("e1", map_id="MAP-01", seed=0, condition_id="default")
    with pytest.raises(V9BudgetClosed):
        tiny.reserve_request("e1", decision_index=1, request_hash="r1")
    assert tiny.snapshot()["closed"] is True


def test_random_policy_is_deterministic_and_public() -> None:
    environment = create_environment("MAP-01")
    sampler = ShapeSampler.from_environment(environment, {})
    first = run_policy("MAP-01", RandomPolicy(sampler, seed=3), seed=0, decision_budget=5)
    second = run_policy("MAP-01", RandomPolicy(sampler, seed=3), seed=0, decision_budget=5)
    assert first.actions == second.actions
    assert first.decisions <= 5
    assert first.status in {"decision_budget_reached", "failure", "success", "censored"}
    assert first.to_json() == second.to_json()


def test_policy_sees_only_public_observation() -> None:
    seen: list[dict[str, object]] = []

    class Spy:
        name = "spy"

        def reset(self) -> None:
            seen.clear()

        def act(
            self, observation: dict[str, object], history: list[dict[str, object]]
        ) -> dict[str, object]:
            seen.append(dict(observation))
            del history
            return {"tool": "wait", "turns": 1}

    run_policy("MAP-01", Spy(), seed=0, decision_budget=3)
    assert seen
    for observation in seen:
        assert "judge_state" not in observation
        assert "oracle_trace" not in observation
        assert observation["map_id"] == "MAP-01"


def test_v9_heuristics_run_without_policy_errors() -> None:
    from agent_arena.v9.policies import heuristics

    registry = heuristics()
    assert set(registry) == set(f"MAP-{index:02d}" for index in range(1, 31))
    for map_id, factory in registry.items():
        run = run_policy(map_id, factory(), seed=0, decision_budget=3)
        assert run.policy == "public_heuristic"
        assert isinstance(run.success, bool)
        assert run.decisions <= 3
        json.dumps(run.as_dict(), ensure_ascii=False)
