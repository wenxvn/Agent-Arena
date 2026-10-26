"""``AgentRunnerV12``：单局执行器。

一条运行链路：

```
V10 Environment ──public observation──> AgentPolicy ──action candidate──> V8Action 校验
        ▲                                      │
        │                               DecisionGateway（预算唯一出口）
        └──────── public result ───────────────┘
```

约束：

- 策略拿到的是 ``PublicObservation`` / ``AgentContext``，不是 Environment；
- 每个候选动作都必须通过 ``V8Action`` 与 ``environment.accepts``；
- Planner / Reflection 的额外请求共享同一个 ``RunBudget``；
- 结果文件兼容 V11 ``manifest/events/result``，并追加 V12 provenance 与
  ``agent_events``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contract_v12 import augment_prompt, provenance_block
from agent_arena.lab.contracts import AGENT_CONTRACT_VERSION, config_hash
from agent_arena.lab.gateway import (
    DecisionGateway,
    GatewayBudgetExceeded,
    GatewayProviderError,
)
from agent_arena.lab.metrics_v12 import project_metrics
from agent_arena.lab.policies.base import call_hook, normalize_decision
from agent_arena.lab.registry import get_agent
from agent_arena.v10.baselines.runner import REJECT_MARKERS
from agent_arena.v10.contract import action_contract
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.attribution import attribute_steps
from agent_arena.web.budget import BudgetLimits, RunBudget, price_for_model
from agent_arena.web.execution import DEFAULT_REQUEST_OUTPUT_TOKENS, build_result
from agent_arena.web.prompting import system_prompt
from agent_arena.web.safety import error_hint, sanitize_payload
from agent_arena.web.schemas import RunConfig, RunState
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

EventSink = Any
StopCheck = Any

RESULT_SCHEMA_VERSION = "v12-lab-result-1"


@dataclass(frozen=True)
class LabRunOutcome:
    state: RunState
    outcome: str
    termination: str
    success: bool
    result: dict[str, Any]


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


def _rejected(result: str) -> bool:
    return str(result).startswith(REJECT_MARKERS)


def agent_provenance(
    agent_id: str, agent_config: dict[str, Any], system: str
) -> dict[str, Any]:
    """策略与提示的版本指纹；``base_prompt_hash`` 与 V11 完全同口径。"""

    registration = get_agent(agent_id)
    normalized = registration.normalize_config(agent_config)
    base = sha256(system.encode("utf-8")).hexdigest()
    combined = sha256(
        json.dumps(
            {
                "base_prompt_hash": base,
                "agent_id": agent_id,
                "agent_version": registration.identity.version,
                "agent_config_hash": config_hash(
                    {"agent_id": agent_id, "config": normalized}
                ),
                "contract_version": AGENT_CONTRACT_VERSION,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "agent_id": agent_id,
        "agent_version": registration.identity.version,
        "agent_config": normalized,
        "agent_config_hash": config_hash({"agent_id": agent_id, "config": normalized}),
        "agent_contract_version": AGENT_CONTRACT_VERSION,
        "base_prompt_hash": base,
        "prompt_hash": combined,
        "capabilities": list(registration.identity.capabilities),
        "extra_model_requests": registration.identity.extra_model_requests,
    }


def run_lab_episode(
    config: RunConfig,
    *,
    provider: Any,
    on_event: EventSink = None,
    should_stop: StopCheck = None,
    run_id: str = "",
) -> LabRunOutcome:
    """执行一局 Lab 策略；返回与 V11 兼容的结果载荷。"""

    sink = on_event or (lambda _event: None)
    stop = should_stop or (lambda: False)

    environment = create_environment(
        config.map_id, environment_seed=config.environment_seed
    )
    system = system_prompt(config.map_id, environment)
    # DCR-V12-01：为"形状可见、内部字段名不可见"的动作字段补充公开说明。
    # 补丁只影响 V12 的 prompt，并写入 provenance；V10/V11 的提示不受影响。
    system, contract_hints = augment_prompt(system, environment)
    rules_hook = getattr(environment, "public_rules", None)
    public_rules = tuple(rules_hook()) if callable(rules_hook) else ()
    provenance = agent_provenance(config.agent, config.agent_config, system)
    registration = get_agent(config.agent)
    policy = registration.factory()(provenance["agent_config"])

    limits = BudgetLimits(
        max_requests=config.max_requests,
        max_input_tokens=config.max_input_tokens,
        max_output_tokens=config.max_output_tokens,
        max_cost_cny=config.max_cost_cny,
        price=price_for_model(config.model),
    )
    budget = RunBudget(limits)
    gateway = DecisionGateway(
        provider,
        budget,
        system_prompt=system,
        output_limit=min(DEFAULT_REQUEST_OUTPUT_TOKENS, config.max_output_tokens),
    )
    episode_context = PublicEpisodeContext(
        run_id=run_id,
        experiment_id=config.experiment_id,
        map_id=config.map_id,
        environment_seed=config.environment_seed,
        agent_id=provenance["agent_id"],
        agent_version=str(provenance["agent_version"]),
        agent_config=dict(provenance["agent_config"]),
        decision_budget=config.max_decisions,
        max_requests=config.max_requests,
        public_rules=public_rules,
        action_contract=action_contract(environment.SHAPES),
        system_prompt=system,
        history_window=5,
        mode=config.mode.value,
    )
    history: list[PublicActionResult] = []
    step_events: list[dict[str, Any]] = []
    agent_events: list[dict[str, Any]] = []
    #: 公开的被接受 move 方位序列（用于 V12 投影指标，不含隐藏真值）。
    public_route: list[str] = []
    final_notes: list[dict[str, Any]] = []
    starting_observation = PublicObservation.from_environment(environment.observe())
    decisions = invalid = rejected = 0
    invalid_streak = reject_streak = 0
    provider_error: str | None = None
    message: str | None = None
    state: RunState | None = None
    outcome = ""
    termination = ""
    from agent_arena.web.clock import utc_now

    started_at = utc_now()

    try:
        reset_hook = getattr(policy, "reset", None)
        if callable(reset_hook):
            call_hook(reset_hook, episode_context)
    except Exception as exc:  # noqa: BLE001 - 插件初始化失败不得击穿服务进程
        state = RunState.FAILED
        outcome = "policy_error"
        termination = f"policy_reset_error:{type(exc).__name__}"
        message = f"策略初始化异常（{type(exc).__name__}）；已停止，未自动重试。"

    while state is None and not environment.is_terminal and decisions < config.max_decisions:
        if stop():
            state, outcome, termination = (
                RunState.CANCELLED,
                "cancelled",
                "cancelled_by_user",
            )
            break
        observation = PublicObservation.from_environment(environment.observe())
        context = AgentContext(
            decision_index=decisions,
            remaining_decisions=max(0, config.max_decisions - decisions),
            history=tuple(history),
            gateway=gateway,
            invalid_streak=invalid_streak,
            reject_streak=reject_streak,
            no_progress_streak=0,
            invalid_total=invalid,
        )
        try:
            decision = normalize_decision(policy.decide(observation, context))
        except GatewayBudgetExceeded as exc:
            state, outcome, termination = (
                RunState.BUDGET_REACHED,
                "budget_reached",
                exc.category,
            )
            break
        except GatewayProviderError as exc:
            provider_error = exc.category
            message = error_hint(exc.category)
            state = RunState.PROVIDER_ERROR
            outcome = "unknown_provider_spend" if exc.unknown_spend else "provider_error"
            termination = exc.category
            break
        except Exception as exc:  # noqa: BLE001 - 第三方策略不得击穿服务进程
            provider_error = None
            message = f"策略异常（{type(exc).__name__}）；已停止，未自动重试。"
            state, outcome, termination = (
                RunState.FAILED,
                "policy_error",
                f"policy_error:{type(exc).__name__}",
            )
            break

        action: V8Action | None = None
        if decision.action is not None:
            try:
                action = V8Action.model_validate(decision.action, strict=True)
            except Exception:  # noqa: BLE001 - invalid policy output is a legal outcome
                action = None
        if action is None or not environment.accepts(action):
            step_result = environment.reject_invalid_action()
            invalid += 1
            invalid_streak += 1
            entry: dict[str, Any] = {
                "invalid_output": sanitize_payload(decision.action, secrets=())
            }
        else:
            step_result = environment.step(action)
            if _rejected(str(step_result.result)):
                rejected += 1
                reject_streak += 1
            else:
                reject_streak = 0
                if action.tool == "move" and isinstance(action.bearing, str):
                    public_route.append(action.bearing)
            invalid_streak = 0
            entry = action.model_dump(mode="json", exclude_none=True)

        decisions += 1
        observation_after = PublicObservation.from_environment(environment.observe())
        raw_notes = observation_after.as_dict().get("agent_notes")
        if isinstance(raw_notes, list):
            final_notes = [dict(item) for item in raw_notes if isinstance(item, dict)]
        outcome_record = PublicActionResult(
            decision_index=decisions,
            action=entry,
            result=str(step_result.result),
            status=step_result.status.value,
            rejected=_rejected(str(step_result.result)),
            invalid="invalid_output" in entry,
            terminal=observation_after.terminal,
            observation=observation_after,
        )
        history.append(outcome_record)
        try:
            observe_hook = getattr(policy, "observe_result", None)
            if callable(observe_hook):
                call_hook(observe_hook, outcome_record)
        except Exception as exc:  # noqa: BLE001 - 策略回调失败也不击穿
            message = f"策略回调异常（{type(exc).__name__}）；已停止。"
            state, outcome, termination = (
                RunState.FAILED,
                "policy_error",
                f"policy_callback_error:{type(exc).__name__}",
            )
            break

        event = {
            "event": "decision",
            "decision_index": decisions,
            "agent_id": provenance["agent_id"],
            "agent_version": provenance["agent_version"],
            "agent_config_hash": provenance["agent_config_hash"],
            "action": sanitize_payload(entry),
            "result": str(step_result.result),
            "status": step_result.status.value,
            "observation_after": sanitize_payload(observation_after.as_dict()),
            "input_tokens": gateway.stats.input_tokens,
            "output_tokens": gateway.stats.output_tokens,
            "latency_ms": gateway.stats.latency_ms,
            "decision_reason": sanitize_payload(decision.decision_reason or ""),
            "decision_requests": decision.requests,
            "state_hash_after": environment.state_hash(),
            "budget": budget.snapshot(),
        }
        step_events.append(event)
        sink(event)

        for agent_event in decision.events():
            payload = {
                "event": "agent_event",
                "decision_index": decisions,
                "agent_id": provenance["agent_id"],
                "kind": agent_event.kind,
                "agent_event": agent_event.event,
                "summary": agent_event.summary,
                "payload": sanitize_payload(agent_event.payload),
                "requests": agent_event.requests,
                "input_tokens": agent_event.input_tokens,
                "output_tokens": agent_event.output_tokens,
            }
            agent_events.append(payload)
            sink(payload)

        if state is not None:
            break

    try:
        policy.close()
    except Exception:  # noqa: BLE001 - close 失败不影响已落盘事实
        pass

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
        prompts_hash=provenance["prompt_hash"],
        decision_count=decisions,
        invalid=invalid,
        rejected=rejected,
        usage=gateway.snapshot(),
        started_at=started_at,
        provider_error=provider_error,
        message=message,
    )
    payload["result_schema_version"] = RESULT_SCHEMA_VERSION
    payload["agent"] = provenance["agent_id"]
    payload["agent_version"] = provenance["agent_version"]
    payload["agent_config"] = provenance["agent_config"]
    payload["agent_config_hash"] = provenance["agent_config_hash"]
    payload["agent_contract_version"] = provenance["agent_contract_version"]
    payload["agent_identity"] = registration.identity.as_dict()
    payload["base_prompt_hash"] = provenance["base_prompt_hash"]
    payload["experiment_id"] = config.experiment_id
    payload["matrix_index"] = config.matrix_index
    payload["starting_observation"] = sanitize_payload(starting_observation.as_dict())
    payload["provenance"] = {
        "agent": {
            key: provenance[key]
            for key in (
                "agent_id",
                "agent_version",
                "agent_config_hash",
                "agent_contract_version",
                "base_prompt_hash",
                "prompt_hash",
            )
        },
        "run": {
            "experiment_id": config.experiment_id,
            "matrix_index": config.matrix_index,
            "map_id": config.map_id,
            "environment_seed": config.environment_seed,
            "mode": config.mode.value,
            "provider_id": config.provider_id,
            "model": config.model,
            "scenario_hash": payload.get("scenario_hash"),
            "rule_hash": payload.get("rule_hash"),
            "metric_hash": payload.get("metric_hash"),
            "metric_schema_hash": payload.get("metric_schema_hash"),
        },
        "gateway": gateway.stats.snapshot(),
        "policy": _policy_snapshot(policy),
        "contract_augmentation": provenance_block(contract_hints),
    }
    payload["agent_events"] = agent_events
    payload["metrics_v12"] = project_metrics(
        config.map_id, notes=final_notes, route=public_route
    )
    payload["attribution"] = attribute_steps(
        config.map_id,
        step_events,
        invalid_actions=invalid,
        mechanism_triggered=payload.get("mechanism_triggered"),
        outcome=outcome,
    )
    return LabRunOutcome(
        state=state,
        outcome=outcome,
        termination=termination,
        success=bool(payload.get("success")),
        result=payload,
    )


def _policy_snapshot(policy: Any) -> dict[str, Any]:
    """策略自检快照（记忆规模/计划次数/反思次数）；不可用则标记 unknown。"""

    snapshot = getattr(policy, "snapshot", None)
    if not callable(snapshot):
        return {"available": False}
    try:
        payload = snapshot()
    except Exception:  # noqa: BLE001 - 自检不得影响结果
        return {"available": False}
    return payload if isinstance(payload, dict) else {"available": False}


__all__ = [
    "RESULT_SCHEMA_VERSION",
    "LabRunOutcome",
    "agent_provenance",
    "run_lab_episode",
]
