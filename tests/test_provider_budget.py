from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread

import pytest

from agent_arena.arena.models import Observation
from agent_arena.llm import (
    BudgetedDecisionProvider,
    FakeDecisionProvider,
    ProviderBudgetController,
    ProviderBudgetExceeded,
    ProviderBudgetLimits,
    ProviderResponse,
)
from agent_arena.llm.budget import estimate_input_tokens_upper_bound
from agent_arena.llm.protocol import DecisionRequest


def make_request() -> DecisionRequest:
    return DecisionRequest(
        observation=Observation(
            current_room="bridge",
            description="控制台前方有一条通道。",
            visible_objects=("console",),
            available_exits=("corridor",),
            inventory=(),
            last_action_result=None,
        ),
        system_prompt="请根据公开观察返回结构化动作。",
        correction=False,
        memory_data="已访问 bridge。",
    )


def make_controller(path, *, requests: int = 2, tokens: int = 40_000):
    return ProviderBudgetController(
        ProviderBudgetLimits(
            experiment_id="budget-test",
            expected_provider="openai",
            expected_model="test-model",
            expected_world_definition_hash="world-hash",
            expected_base_prompt_hash="prompt-hash",
            max_requests=requests,
            max_tokens=tokens,
            max_output_tokens_per_request=64,
            timeout_seconds=600,
            input_overhead_tokens=128,
        ),
        path,
    )


def test_budgeted_provider_caps_calls_and_persists_shared_experiment_usage(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    provider = FakeDecisionProvider(
        [
            ProviderResponse(
                candidate={"action": {"tool": "look"}}, input_tokens=20, output_tokens=7
            ),
            ProviderResponse(
                candidate={"action": {"tool": "look"}}, input_tokens=23, output_tokens=9
            ),
        ]
    )
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="memory-v2:seed=1",
        provider_name="openai",
        model_name="test-model",
    )

    bounded.decide(make_request())
    assert provider.calls[0].request.max_output_tokens == 64
    assert controller.snapshot().requests_used == 1
    assert controller.snapshot().tokens_used == 27

    resumed_controller = make_controller(ledger)
    resumed_provider = FakeDecisionProvider(
        [ProviderResponse(candidate={}, input_tokens=23, output_tokens=9)]
    )
    BudgetedDecisionProvider(
        resumed_provider,
        resumed_controller,
        context="memory-v3:seed=1",
        provider_name="openai",
        model_name="test-model",
    ).decide(make_request())

    assert resumed_controller.snapshot().requests_used == 2
    assert resumed_controller.snapshot().tokens_used == 59
    persisted = json.loads(ledger.read_text(encoding="utf-8"))
    assert [item["status"] for item in persisted["requests"]] == ["completed", "completed"]
    assert persisted["requests"][1]["context"] == "memory-v3:seed=1"
    assert "请根据公开观察" not in ledger.read_text(encoding="utf-8")

    blocked_provider = FakeDecisionProvider([{}])
    with pytest.raises(ProviderBudgetExceeded, match="request budget"):
        BudgetedDecisionProvider(
            blocked_provider,
            resumed_controller,
            context="memory-v3:seed=2",
            provider_name="openai",
            model_name="test-model",
        ).decide(make_request())
    assert blocked_provider.calls == []


def test_budget_preflight_refuses_oversized_prompt_before_provider_call(tmp_path) -> None:
    controller = make_controller(tmp_path / "budget.json", tokens=1_000)
    provider = FakeDecisionProvider([{}])

    with pytest.raises(ProviderBudgetExceeded, match="cannot reserve"):
        BudgetedDecisionProvider(
            provider,
            controller,
            context="oversized-input",
            provider_name="openai",
            model_name="test-model",
        ).decide(make_request())

    assert provider.calls == []
    assert controller.snapshot().requests_used == 0
    assert controller.snapshot().closed_reason == "token_budget_exhausted"


@pytest.mark.parametrize(
    ("provider_name", "model_name"),
    [("bailian", "test-model"), ("openai", "other-model")],
)
def test_unregistered_provider_or_model_is_refused_before_provider_call(
    tmp_path, provider_name: str, model_name: str
) -> None:
    controller = make_controller(tmp_path / "budget.json")
    provider = FakeDecisionProvider([{}])
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="identity-mismatch",
        provider_name=provider_name,
        model_name=model_name,
    )

    with pytest.raises(ProviderBudgetExceeded, match="does not match"):
        bounded.decide(make_request())

    assert provider.calls == []
    assert controller.snapshot().requests_used == 0


def test_missing_usage_closes_ledger_and_prevents_later_provider_calls(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    provider = FakeDecisionProvider([{"action": {"tool": "look"}}])
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="missing-usage",
        provider_name="openai",
        model_name="test-model",
    )

    with pytest.raises(ProviderBudgetExceeded, match="usage is missing"):
        bounded.decide(make_request())

    resumed = make_controller(ledger)
    untouched = FakeDecisionProvider([{}])
    with pytest.raises(ProviderBudgetExceeded, match="budget is closed"):
        BudgetedDecisionProvider(
            untouched,
            resumed,
            context="after-missing-usage",
            provider_name="openai",
            model_name="test-model",
        ).decide(make_request())
    assert untouched.calls == []
    assert resumed.snapshot().closed_reason == "usage_missing_unknown_spend"


def test_provider_usage_above_reservation_closes_budget(tmp_path) -> None:
    controller = make_controller(tmp_path / "budget.json")
    input_limit = estimate_input_tokens_upper_bound(make_request(), overhead_tokens=128)
    provider = FakeDecisionProvider(
        [ProviderResponse(candidate={}, input_tokens=input_limit + 1, output_tokens=1)]
    )
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="provider-usage-over-reservation",
        provider_name="openai",
        model_name="test-model",
    )

    with pytest.raises(ProviderBudgetExceeded, match="exceeded its pre-request reservation"):
        bounded.decide(make_request())

    assert controller.snapshot().closed_reason == "provider_exceeded_reservation"
    untouched = FakeDecisionProvider([{}])
    with pytest.raises(ProviderBudgetExceeded, match="budget is closed"):
        BudgetedDecisionProvider(
            untouched,
            controller,
            context="after-provider-overrun",
            provider_name="openai",
            model_name="test-model",
        ).decide(make_request())
    assert untouched.calls == []


def test_provider_error_charges_reservation_and_closes_budget(tmp_path) -> None:
    controller = make_controller(tmp_path / "budget.json")
    provider = FakeDecisionProvider([RuntimeError("transport unavailable")])
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="failed-provider-call",
        provider_name="openai",
        model_name="test-model",
    )

    with pytest.raises(ProviderBudgetExceeded, match="Provider request failed"):
        bounded.decide(make_request())

    state = controller.snapshot()
    assert state.requests_used == 1
    assert state.tokens_used > 0
    assert state.closed_reason == "provider_error_unknown_spend"


def test_terminal_failure_event_requires_matching_closed_reason(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    provider = FakeDecisionProvider([RuntimeError("transport unavailable")])
    bounded = BudgetedDecisionProvider(
        provider,
        controller,
        context="failed-provider-call",
        provider_name="openai",
        model_name="test-model",
    )

    with pytest.raises(ProviderBudgetExceeded):
        bounded.decide(make_request())

    persisted = json.loads(ledger.read_text(encoding="utf-8"))
    persisted["closed_reason"] = None
    ledger.write_text(json.dumps(persisted), encoding="utf-8")
    with pytest.raises(ProviderBudgetExceeded, match="close reason does not match"):
        make_controller(ledger)


def test_request_completing_after_global_timeout_is_charged_and_rejected(
    monkeypatch, tmp_path
) -> None:
    clock = [100.0]
    monkeypatch.setattr("agent_arena.llm.budget.time", lambda: clock[0])
    controller = ProviderBudgetController(
        ProviderBudgetLimits(
            experiment_id="timeout-test",
            expected_provider="openai",
            expected_model="test-model",
            expected_world_definition_hash="world-hash",
            expected_base_prompt_hash="prompt-hash",
            max_requests=2,
            max_tokens=40_000,
            max_output_tokens_per_request=64,
            timeout_seconds=1,
            input_overhead_tokens=128,
        ),
        tmp_path / "timeout-budget.json",
    )

    class DelayedProvider:
        def decide(self, request):
            clock[0] = 102.0
            return ProviderResponse(candidate={}, input_tokens=2, output_tokens=1)

    bounded = BudgetedDecisionProvider(
        DelayedProvider(),
        controller,
        context="request-crossed-deadline",
        provider_name="openai",
        model_name="test-model",
    )

    with pytest.raises(ProviderBudgetExceeded, match="timeout expired while"):
        bounded.decide(make_request())

    state = controller.snapshot()
    assert state.closed_reason == "global_timeout"
    assert state.requests_used == 1
    assert state.tokens_used == 3
    persisted = json.loads((tmp_path / "timeout-budget.json").read_text(encoding="utf-8"))
    assert persisted["requests"][0]["status"] == "completed_after_timeout"


def test_active_request_lease_prevents_second_controller_from_recovering_it(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    provider_entered = Event()
    release_provider = Event()
    errors: list[BaseException] = []

    class BlockingProvider:
        def decide(self, request):
            provider_entered.set()
            if not release_provider.wait(timeout=5):
                raise TimeoutError("provider release timed out")
            return ProviderResponse(candidate={}, input_tokens=1, output_tokens=1)

    bounded = BudgetedDecisionProvider(
        BlockingProvider(),
        controller,
        context="active-request",
        provider_name="openai",
        model_name="test-model",
    )

    def call_provider() -> None:
        try:
            bounded.decide(make_request())
        except BaseException as exc:
            errors.append(exc)

    worker = Thread(target=call_provider)
    worker.start()
    assert provider_entered.wait(timeout=5)
    try:
        with pytest.raises(ProviderBudgetExceeded, match="refusing to overlap"):
            make_controller(ledger)
    finally:
        release_provider.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert errors == []
    assert controller.snapshot().closed_reason is None
    assert controller.snapshot().requests_used == 1


def test_invocation_lease_prevents_benchmark_interleaving(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    first = make_controller(ledger)
    second = make_controller(ledger)

    with first.invocation_lease():
        with pytest.raises(ProviderBudgetExceeded, match="refusing to overlap"):
            with second.invocation_lease():
                pass


def test_active_request_lease_blocks_a_separate_process(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    controller.reserve(
        input_token_upper_bound=100,
        context="in-flight",
        provider="openai",
        model="test-model",
    )
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    child_code = """
import sys
from pathlib import Path
from agent_arena.llm.budget import (
    ProviderBudgetController,
    ProviderBudgetExceeded,
    ProviderBudgetLimits,
)
limits = ProviderBudgetLimits(
    experiment_id="budget-test",
    expected_provider="openai",
    expected_model="test-model",
    expected_world_definition_hash="world-hash",
    expected_base_prompt_hash="prompt-hash",
    max_requests=2,
    max_tokens=40000,
    max_output_tokens_per_request=64,
    timeout_seconds=600,
    input_overhead_tokens=128,
)
try:
    ProviderBudgetController(limits, Path(sys.argv[1]))
except ProviderBudgetExceeded as exc:
    if "refusing to overlap" not in str(exc):
        raise
    print("blocked")
else:
    sys.exit(2)
"""

    with controller.request_lease():
        result = subprocess.run(
            [sys.executable, "-c", child_code, str(ledger)],
            check=False,
            capture_output=True,
            cwd=repo_root,
            env=env,
            text=True,
            timeout=10,
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "blocked"


def test_abandoned_request_and_mismatched_ledger_fail_closed(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    controller = make_controller(ledger)
    reservation = controller.reserve(
        input_token_upper_bound=100,
        context="in-flight",
        provider="openai",
        model="test-model",
    )
    assert reservation.reserved_tokens == 164

    recovered = make_controller(ledger)
    state = recovered.snapshot()
    assert state.closed_reason == "abandoned_request_unknown_spend"
    assert state.tokens_used == reservation.reserved_tokens

    with pytest.raises(ProviderBudgetExceeded, match="limits do not match"):
        ProviderBudgetController(
            ProviderBudgetLimits(
                experiment_id="budget-test",
                expected_provider="openai",
                expected_model="test-model",
                expected_world_definition_hash="world-hash",
                expected_base_prompt_hash="prompt-hash",
                max_requests=3,
                max_tokens=40_000,
                max_output_tokens_per_request=64,
                timeout_seconds=600,
                input_overhead_tokens=128,
            ),
            ledger,
        )


def test_inconsistent_ledger_counters_fail_closed(tmp_path) -> None:
    ledger = tmp_path / "budget.json"
    make_controller(ledger)
    persisted = json.loads(ledger.read_text(encoding="utf-8"))
    persisted["tokens_used"] = 1
    ledger.write_text(json.dumps(persisted), encoding="utf-8")

    with pytest.raises(ProviderBudgetExceeded, match="counters are inconsistent"):
        make_controller(ledger)
