"""单局 V10 执行适配：离线公开策略与真实模型共用同一结果 schema。

- 离线模式显式标注 ``public_heuristic_policy``，不是模型挑战；
- 真实模式逐请求检查预算，未知 usage / 传输异常立即 fail-closed，不自动重试；
- 每个动作通过 ``on_event`` 回调交给服务层持久化，UI 不参与执行。
"""

from __future__ import annotations

import importlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any

from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest
from agent_arena.v10.baselines.runner import REJECT_MARKERS
from agent_arena.v10.baselines.suite import decision_budget
from agent_arena.v10.metrics.governance import schema_hash, truncation_censored
from agent_arena.v10.runtime.base import V10Map
from agent_arena.v10.runtime.catalog import (
    LEVEL_OF,
    WORLD_OF,
    create_environment,
    metric_hash,
    rule_hash,
    scenario_hash,
)
from agent_arena.web.budget import (
    BudgetExceeded,
    BudgetLimits,
    RunBudget,
    UnknownUsageError,
    price_for_model,
)
from agent_arena.web.catalog import DISPLAY_TITLES, WORLD_LABELS
from agent_arena.web.clock import utc_now
from agent_arena.web.explain import failure_summary, mode_label
from agent_arena.web.prompting import system_prompt
from agent_arena.web.safety import error_hint, sanitize_payload
from agent_arena.web.schemas import RunConfig, RunState
from agent_arena.worlds.scenario_v8.models import V8Action, V8Observation, V8Status

EventSink = Callable[[dict[str, Any]], None]
StopCheck = Callable[[], bool]

HISTORY_WINDOW = 5
MAX_REQUEST_OUTPUT_TOKENS = 1_024
DEFAULT_REQUEST_OUTPUT_TOKENS = 700


@dataclass(frozen=True)
class ExecutionOutcome:
    state: RunState
    outcome: str
    termination: str
    success: bool
    result: dict[str, Any]


def _noop(_: dict[str, Any]) -> None:
    return None


def _never() -> bool:
    return False


def _status_to_state(status: V8Status) -> RunState:
    if status is V8Status.SUCCESS:
        return RunState.SUCCEEDED
    if status is V8Status.FAILURE:
        return RunState.FAILED
    return RunState.BUDGET_REACHED


def _status_to_outcome(status: V8Status) -> str:
    if status is V8Status.SUCCESS:
        return "success"
    if status is V8Status.FAILURE:
        return "scenario_failure"
    return "step_limit_reached"


def _estimate_input_tokens(system: str, observation: dict[str, Any], history: list[Any]) -> int:
    text = (
        system
        + json.dumps(observation, ensure_ascii=False)
        + json.dumps(history, ensure_ascii=False)
    )
    return max(512, min(16_384, len(text.encode("utf-8")) // 2))


def _public_history(history: list[dict[str, Any]]) -> str | None:
    if not history:
        return None
    return json.dumps(history[-HISTORY_WINDOW:], ensure_ascii=False, sort_keys=True)


def _rejected(result: str) -> bool:
    return str(result).startswith(REJECT_MARKERS)


def _metric_payload(environment: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metrics: dict[str, Any] = environment.metrics()
    if isinstance(environment, V10Map):
        metrics = truncation_censored(
            environment.map_id, metrics, truncated=not environment.is_terminal
        )
        specs = [asdict(spec) for spec in environment.METRIC_SPECS]
    else:  # pragma: no cover - V11 catalog 目前全部是 V10 原生图
        specs = []
    return metrics, specs


def build_result(
    config: RunConfig,
    environment: Any,
    *,
    state: RunState,
    outcome: str,
    termination: str,
    prompts_hash: str,
    decision_count: int,
    invalid: int,
    rejected: int,
    usage: dict[str, Any],
    started_at: str,
    provider_error: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    metrics, specs = _metric_payload(environment)
    primary = str(getattr(environment, "PRIMARY_METRIC", "") or "")
    primary_value = metrics.get(primary, {}) if primary else {}
    triggered = (
        environment.mechanism_triggered() if isinstance(environment, V10Map) else None
    )
    finished_at = utc_now()
    result: dict[str, Any] = {
        "schema_version": "v11-web-result-1",
        "map_id": config.map_id,
        "world": WORLD_OF[config.map_id],
        "world_label": WORLD_LABELS[WORLD_OF[config.map_id]],
        "title": DISPLAY_TITLES[config.map_id],
        "design_difficulty": LEVEL_OF[config.map_id],
        "environment_seed": config.environment_seed,
        "mode": config.mode.value,
        "mode_label": mode_label(config.mode.value),
        "provider_id": config.provider_id,
        "model": config.model,
        "agent": config.agent,
        "policy_seed": config.policy_seed,
        "decision_budget": decision_budget(config.map_id),
        "max_decisions": config.max_decisions,
        "scenario_hash": scenario_hash(config.map_id, config.environment_seed),
        "rule_hash": rule_hash(config.map_id),
        "metric_hash": metric_hash(config.map_id),
        "metric_schema_hash": schema_hash(),
        "prompt_hash": prompts_hash,
        "state": state.value,
        "outcome": outcome,
        "success": environment.is_success,
        "termination": termination,
        "decision_count": decision_count,
        "invalid_actions": invalid,
        "rejected_actions": rejected,
        "mechanism_triggered": triggered,
        "primary_metric": primary,
        "primary_metric_state": primary_value.get("state"),
        "primary_metric_value": primary_value.get("value"),
        "primary_metric_unit": primary_value.get("unit"),
        "metrics": metrics,
        "metric_specs": specs,
        "usage": usage,
        "cost_settled_cny": usage.get("cost_settled_cny"),
        "cost_unknown": bool(usage.get("cost_unknown")),
        "provider_error": provider_error,
        "message": message,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    result["failure"] = failure_summary(result)
    return result


def execute_offline(
    config: RunConfig,
    *,
    on_event: EventSink = _noop,
    should_stop: StopCheck = _never,
) -> ExecutionOutcome:
    """零 API 的公开规则策略演示，明确不冒充模型。"""

    environment = create_environment(config.map_id, environment_seed=config.environment_seed)
    module = importlib.import_module(f"agent_arena.v10.baselines.map{config.map_id[-2:]}")
    policy = module.HEURISTIC()
    policy.reset()
    observation = environment.observe()
    history: list[dict[str, Any]] = []
    budget = min(config.max_decisions, decision_budget(config.map_id))
    decisions = invalid = rejected = 0
    started_at = utc_now()
    cancelled = False

    while not environment.is_terminal and decisions < budget:
        if should_stop():
            cancelled = True
            break
        visible = json.loads(json.dumps(observation, ensure_ascii=False))
        window = [dict(item) for item in history[-HISTORY_WINDOW:]] if history else []
        payload = policy.act(visible, window)
        if not isinstance(payload, dict) or not isinstance(payload.get("tool"), str):
            payload = {"tool": "__invalid__"}
        try:
            action: V8Action | None = V8Action.model_validate(payload, strict=True)
        except Exception:  # noqa: BLE001 - invalid policy output is a legal outcome
            action = None
        if action is None or not environment.accepts(action):
            step_result = environment.reject_invalid_action()
            invalid += 1
            entry: dict[str, Any] = {"invalid_shape": payload}
        else:
            step_result = environment.step(action)
            if _rejected(str(step_result.result)):
                rejected += 1
            entry = action.model_dump(mode="json", exclude_none=True)
        observation = environment.observe()
        decisions += 1
        history.append({"action": entry, "result": step_result.result})
        on_event(
            {
                "event": "decision",
                "decision_index": decisions,
                "action": sanitize_payload(entry),
                "result": str(step_result.result),
                "status": step_result.status.value,
                "observation_after": sanitize_payload(observation),
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "decision_reason": "公开启发式规则策略（离线演示，非模型决策）",
                "state_hash_after": environment.state_hash(),
            }
        )

    if cancelled:
        state, outcome, termination = RunState.CANCELLED, "cancelled", "cancelled_by_user"
    elif environment.is_terminal:
        state = _status_to_state(environment.status)
        outcome = _status_to_outcome(environment.status)
        termination = environment.terminal_reason or outcome
    else:
        state = RunState.BUDGET_REACHED
        outcome = "decision_budget_exhausted"
        termination = "decision_budget_exhausted"

    usage = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_settled_cny": "0",
        "cost_projected_cny": "0",
        "cost_unknown": False,
        "cost_enforced": False,
        "currency": None,
        "mode_note": "离线演示不发送任何 Provider 请求。",
    }
    payload = build_result(
        config,
        environment,
        state=state,
        outcome=outcome,
        termination=termination,
        prompts_hash=sha256(b"offline-public-heuristic-policy-v1").hexdigest(),
        decision_count=decisions,
        invalid=invalid,
        rejected=rejected,
        usage=usage,
        started_at=started_at,
    )
    return ExecutionOutcome(
        state=state,
        outcome=outcome,
        termination=termination,
        success=bool(payload.get("success")),
        result=payload,
    )


def execute_live(
    config: RunConfig,
    *,
    provider: DecisionProvider,
    on_event: EventSink = _noop,
    should_stop: StopCheck = _never,
) -> ExecutionOutcome:
    """真实模型单局执行；任何未确认结果都 fail-closed。"""

    environment = create_environment(config.map_id, environment_seed=config.environment_seed)
    system = system_prompt(config.map_id, environment)
    prompts_hash = sha256(system.encode("utf-8")).hexdigest()
    limits = BudgetLimits(
        max_requests=config.max_requests,
        max_input_tokens=config.max_input_tokens,
        max_output_tokens=config.max_output_tokens,
        max_cost_cny=config.max_cost_cny,
        price=price_for_model(config.model),
    )
    budget = RunBudget(limits)
    observation = environment.observe()
    history: list[dict[str, Any]] = []
    decisions = invalid = rejected = 0
    started_at = utc_now()
    provider_error: str | None = None
    message: str | None = None
    state: RunState | None = None
    outcome = ""
    termination = ""

    while not environment.is_terminal and decisions < config.max_decisions:
        if should_stop():
            state, outcome, termination = RunState.CANCELLED, "cancelled", "cancelled_by_user"
            break
        estimated = _estimate_input_tokens(system, observation, history)
        output_limit = min(DEFAULT_REQUEST_OUTPUT_TOKENS, config.max_output_tokens)
        try:
            budget.reserve(
                estimated_input_tokens=estimated,
                output_limit=output_limit,
            )
        except BudgetExceeded as exc:
            state, outcome, termination = (
                RunState.BUDGET_REACHED,
                "budget_reached",
                exc.reason,
            )
            break

        request = DecisionRequest(
            observation=V8Observation(**observation),
            system_prompt=system,
            correction=invalid > 0,
            invalid_output_reason="schema" if invalid else None,
            recent_history=_public_history(history),
            runtime_feedback=None,
            max_output_tokens=output_limit,
            action_contract_version="scenario_v4",
        )
        started = time.monotonic()
        try:
            response = provider.decide(request)
        except DecisionProviderError as exc:
            budget.fail(unknown_spend=exc.unknown_spend)
            provider_error = exc.error_category
            message = error_hint(exc.error_category)
            state, outcome, termination = (
                RunState.PROVIDER_ERROR,
                "provider_error",
                exc.error_category,
            )
            break
        except Exception as exc:  # noqa: BLE001 - unconfirmed transport outcome
            budget.fail(unknown_spend=True)
            provider_error = type(exc).__name__
            message = error_hint(type(exc).__name__)
            state, outcome, termination = (
                RunState.PROVIDER_ERROR,
                "unknown_provider_spend",
                "unknown_provider_spend",
            )
            break
        latency = max(0, round((time.monotonic() - started) * 1000))
        try:
            budget.settle(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
            )
        except UnknownUsageError:
            provider_error = "unknown_provider_usage"
            message = error_hint("unknown_provider_usage")
            state, outcome, termination = (
                RunState.PROVIDER_ERROR,
                "unknown_provider_spend",
                "unknown_provider_usage",
            )
            break
        except BudgetExceeded as exc:
            state, outcome, termination = (
                RunState.BUDGET_REACHED,
                "budget_reached",
                exc.reason,
            )
            break

        candidate = response.candidate
        try:
            action: V8Action | None = V8Action.model_validate(candidate, strict=True)
        except Exception:  # noqa: BLE001 - invalid model output is a legal outcome
            action = None
        if action is None or not environment.accepts(action):
            step_result = environment.reject_invalid_action()
            invalid += 1
            entry: dict[str, Any] = {
                "invalid_output": sanitize_payload(candidate, secrets=()),
            }
        else:
            step_result = environment.step(action)
            if _rejected(str(step_result.result)):
                rejected += 1
            entry = action.model_dump(mode="json", exclude_none=True)
        observation = environment.observe()
        decisions += 1
        history.append({"action": entry, "result": step_result.result})
        on_event(
            {
                "event": "decision",
                "decision_index": decisions,
                "action": sanitize_payload(entry),
                "result": str(step_result.result),
                "status": step_result.status.value,
                "observation_after": sanitize_payload(observation),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": latency,
                "decision_reason": None,
                "state_hash_after": environment.state_hash(),
                "budget": budget.snapshot(),
            }
        )

    if state is None:
        if environment.is_terminal:
            state = _status_to_state(environment.status)
            outcome = _status_to_outcome(environment.status)
            termination = environment.terminal_reason or outcome
        else:
            state, outcome, termination = (
                RunState.BUDGET_REACHED,
                "decision_budget_exhausted",
                "decision_budget_exhausted",
            )

    payload = build_result(
        config,
        environment,
        state=state,
        outcome=outcome,
        termination=termination,
        prompts_hash=prompts_hash,
        decision_count=decisions,
        invalid=invalid,
        rejected=rejected,
        usage=budget.snapshot(),
        started_at=started_at,
        provider_error=provider_error,
        message=message,
    )
    return ExecutionOutcome(
        state=state,
        outcome=outcome,
        termination=termination,
        success=bool(payload.get("success")),
        result=payload,
    )


__all__ = [
    "DEFAULT_REQUEST_OUTPUT_TOKENS",
    "ExecutionOutcome",
    "MAX_REQUEST_OUTPUT_TOKENS",
    "build_result",
    "execute_live",
    "execute_offline",
]
