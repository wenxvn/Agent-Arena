"""V11 单局执行适配：离线策略、真实循环、预算与 fail-closed。"""

from __future__ import annotations

import importlib
from collections import deque
from decimal import Decimal
from typing import Any

from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse
from agent_arena.v10.baselines.runner import run_policy
from agent_arena.web.execution import execute_live, execute_offline
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
    RunState,
)


def _config(**overrides: object) -> RunConfig:
    payload: dict[str, object] = {
        "map_id": "MAP-01",
        "environment_seed": 0,
        "mode": RunMode.LIVE,
        "provider_id": "openai_compatible",
        "model": "mimo-v2.6-flash",
        "agent": "v10_action_loop",
        "max_decisions": 40,
        "max_requests": 40,
        "max_input_tokens": 200_000,
        "max_output_tokens": 20_000,
        "max_cost_cny": Decimal("1.00"),
    }
    payload.update(overrides)
    return RunConfig.model_validate(payload)


def _winning_actions(map_id: str = "MAP-01") -> list[dict[str, Any]]:
    module = importlib.import_module(f"agent_arena.v10.baselines.map{map_id[-2:]}")
    run = run_policy(map_id, module.HEURISTIC(), environment_seed=0, decision_budget=60)
    assert run.success
    return [item["action"] for item in run.actions]


class _SequenceProvider:
    def __init__(
        self,
        actions: list[dict[str, Any]],
        *,
        usage: tuple[int | None, int | None] = (120, 20),
    ) -> None:
        self._actions = deque(actions)
        self.calls = 0
        self._usage = usage

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        del request
        self.calls += 1
        action = self._actions.popleft() if self._actions else {"tool": "__invalid__"}
        return ProviderResponse(
            candidate=action,
            input_tokens=self._usage[0],
            output_tokens=self._usage[1],
            cached_input_tokens=0,
        )


class _FailingProvider:
    def __init__(self, *, unknown_spend: bool = True) -> None:
        self.calls = 0
        self._unknown = unknown_spend

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        del request
        self.calls += 1
        raise DecisionProviderError(
            "boom",
            error_category="APIConnectionError",
            retryable=False,
            unknown_spend=self._unknown,
        )


def test_offline_run_reaches_success_with_real_hashes() -> None:
    config = RunConfig(
        map_id="MAP-01",
        environment_seed=0,
        mode=RunMode.OFFLINE,
        provider_id=OFFLINE_PROVIDER,
        model=OFFLINE_MODEL,
        agent="public_heuristic_policy",
        max_decisions=30,
        max_requests=1,
        max_input_tokens=10_000,
        max_output_tokens=1_000,
        max_cost_cny=Decimal("0.01"),
    )
    outcome = execute_offline(config)
    assert outcome.state is RunState.SUCCEEDED
    assert outcome.success
    result = outcome.result
    assert len(str(result["prompt_hash"])) == 64
    assert result["usage"]["requests"] == 0
    assert result["rule_hash"] and result["metric_hash"]


def test_live_success_records_steps_tokens_and_metrics() -> None:
    actions = _winning_actions()
    provider = _SequenceProvider(actions)
    outcome = execute_live(_config(max_decisions=len(actions)), provider=provider)
    assert outcome.state is RunState.SUCCEEDED
    assert outcome.success
    result = outcome.result
    assert result["decision_count"] == len(actions)
    assert result["usage"]["requests"] == len(actions)
    assert result["usage"]["input_tokens"] == 120 * len(actions)
    assert len(str(result["prompt_hash"])) == 64
    states = {value["state"] for value in result["metrics"].values()}
    assert states <= {"VALID", "CENSORED", "NOT_APPLICABLE", "MISSING", "INVALID"}
    assert result["primary_metric_state"] in {"VALID", "CENSORED"}
    assert result["attribution"]["label"] == "TRIGGERED"


def test_invalid_model_output_is_counted_not_crashed() -> None:
    provider = _SequenceProvider([])
    outcome = execute_live(_config(max_decisions=3, max_requests=3), provider=provider)
    assert outcome.state is RunState.BUDGET_REACHED
    assert outcome.result["invalid_actions"] == 3
    assert outcome.termination == "decision_budget_exhausted"


def test_provider_error_with_unknown_spend_fails_closed() -> None:
    provider = _FailingProvider(unknown_spend=True)
    outcome = execute_live(_config(), provider=provider)
    assert outcome.state is RunState.PROVIDER_ERROR
    assert outcome.termination == "APIConnectionError"
    assert outcome.result["cost_unknown"] is True
    assert provider.calls == 1


def test_missing_usage_is_unknown_spend() -> None:
    actions = _winning_actions()
    provider = _SequenceProvider(actions, usage=(None, None))
    outcome = execute_live(_config(), provider=provider)
    assert outcome.state is RunState.PROVIDER_ERROR
    assert outcome.termination == "unknown_provider_usage"
    assert outcome.result["cost_unknown"] is True


def test_cancellation_stops_between_steps() -> None:
    actions = _winning_actions()
    provider = _SequenceProvider(actions)
    state = {"stop": False}

    def on_event(event: dict[str, Any]) -> None:
        if event.get("event") == "decision":
            state["stop"] = True

    outcome = execute_live(
        _config(),
        provider=provider,
        on_event=on_event,
        should_stop=lambda: state["stop"],
    )
    assert outcome.state is RunState.CANCELLED
    assert outcome.termination == "cancelled_by_user"
    assert outcome.result["decision_count"] == 1
    assert provider.calls == 1


def test_request_cap_stops_before_second_request() -> None:
    provider = _SequenceProvider([])
    outcome = execute_live(_config(max_requests=1, max_decisions=10), provider=provider)
    assert outcome.state is RunState.BUDGET_REACHED
    assert outcome.termination == "request_limit_exceeded"
    assert provider.calls == 1


def test_cost_cap_blocks_before_any_request() -> None:
    provider = _SequenceProvider([])
    outcome = execute_live(_config(max_cost_cny=Decimal("0.001")), provider=provider)
    assert outcome.state is RunState.BUDGET_REACHED
    assert outcome.termination == "cost_limit_exceeded"
    assert provider.calls == 0
