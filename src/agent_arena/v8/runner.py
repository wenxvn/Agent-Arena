"""Bounded V8 episode runner over the isolated thirty-map runtime.

The runner only consumes public Observations and the map-declared action shapes.
It writes one immutable directory per episode: trace, judge metrics, V8 metrics,
manifest and usage. Provider calls are reserved in the V8 ledger before they are
sent and settled from the supplier's reported token usage afterwards.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest
from agent_arena.v8.budget import (
    MAX_PROVIDER_CONSECUTIVE_ERRORS,
    MAX_SCHEMA_CONSECUTIVE_ERRORS,
    V8BudgetClosed,
    V8BudgetLedger,
)
from agent_arena.v8.metrics import (
    metric_schema_hash,
    project_metrics,
    summarize,
)
from agent_arena.v8.prompts import system_prompt
from agent_arena.worlds.scenario_v8.catalog import (
    CONDITIONS,
    LEVEL_OF,
    MAP_IDS,
    WORLD_OF,
    create_environment,
    rule_hash,
    scenario_hash,
    source_hash,
)
from agent_arena.worlds.scenario_v8.models import V8Action, V8Observation

DECISION_BUDGETS = {"简单": 30, "中等": 38, "困难": 46}
#: Wall-clock safety only; the registered binding limit is the decision budget.
#: Set high enough that a slow provider cannot censor a full 46-decision episode.
MAX_EPISODE_SECONDS = 30 * 60
MAX_DECISION_INDEX = 60


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return observation


def _repeat_hint(results: list[str]) -> str | None:
    if len(results) < 3 or len(set(results[-3:])) != 1:
        return None
    result = results[-1]
    if not result.startswith(("INVALID", "NO_", "TICK_MISMATCH", "TARGET_", "EDGE_", "ALREADY")):
        return None
    return (
        f"最近 3 次动作都返回 {result}。请重新阅读动作契约与当前 Observation，"
        "改用字段合法且能改变状态的动作。"
    )


def _status_of(environment: Any) -> str:
    if environment.is_success:
        return "success"
    if environment.status.value == "scenario_failure":
        return "failure"
    if environment.status.value == "step_limit_reached":
        return "censored"
    return "running"


def _failure_codes(outcome: str, environment: Any, invalid_count: int) -> list[str]:
    codes: list[str] = []
    if outcome.startswith("provider"):
        codes.append("PROVIDER_ERROR")
    if outcome in {"censored", "decision_budget_reached", "episode_timeout"}:
        codes.append("CENSORED")
    if invalid_count:
        codes.append("INVALID_ACTION")
    if environment.terminal_reason:
        codes.append(str(environment.terminal_reason))
    if not codes:
        codes.append("SUCCESS" if outcome == "success" else "UNCLASSIFIED_OUTCOME")
    return sorted(set(codes))


@dataclass(frozen=True)
class V8EpisodeSpec:
    map_id: str
    replicate_id: int
    decision_budget: int
    seed: int = 0

    @property
    def condition_id(self) -> str:
        return CONDITIONS.get(self.map_id, "default")

    @property
    def world(self) -> str:
        return WORLD_OF[self.map_id]

    @property
    def level(self) -> str:
        return LEVEL_OF[self.map_id]


def registered_specs() -> list[V8EpisodeSpec]:
    return [
        V8EpisodeSpec(map_id, replicate, DECISION_BUDGETS[LEVEL_OF[map_id]])
        for map_id in MAP_IDS
        for replicate in range(3)
    ]


class V8Runner:
    def __init__(
        self,
        *,
        provider: DecisionProvider,
        settings: RuntimeSettings,
        ledger: V8BudgetLedger,
        output_dir: Path,
        commit: str,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.provider = provider
        self.settings = settings
        self.ledger = ledger
        self.output_dir = output_dir
        self.commit = commit
        self.progress = progress or (lambda _: None)

    def run(self, spec: V8EpisodeSpec) -> dict[str, Any]:
        if spec.map_id not in MAP_IDS:
            raise ValueError(f"未注册的 V8 地图：{spec.map_id}")
        if not 0 <= spec.replicate_id <= 2:
            raise ValueError("V8 replicate_id 只能是 0/1/2。")
        if not 1 <= spec.decision_budget <= MAX_DECISION_INDEX:
            raise ValueError("V8 decision_budget 超出登记范围。")

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_id = (
            f"V8-{spec.map_id}-R{spec.replicate_id}-{stamp}-{uuid4().hex[:8]}"
        )
        episode_dir = self.output_dir / "episodes" / run_id
        episode_dir.mkdir(parents=True, exist_ok=False)
        trace_path = episode_dir / "agent_trace.jsonl"

        environment = create_environment(spec.map_id, seed=spec.seed, step_limit=160)
        observation = environment.observe()
        system = system_prompt(environment, decision_budget=spec.decision_budget)
        header = {
            "event": "trace_header",
            "experiment_id": self.ledger.experiment_id,
            "run_id": run_id,
            "map_id": spec.map_id,
            "world": spec.world,
            "difficulty": spec.level,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "replicate_id": spec.replicate_id,
            "scenario_hash": scenario_hash(spec.map_id),
            "rule_hash": rule_hash(spec.map_id),
            "source_hash": source_hash(spec.map_id),
            "prompt_hash": _sha256_bytes(system.encode("utf-8")),
            "metric_schema_hash": metric_schema_hash(spec.map_id),
            "commit": self.commit,
            "provider": self.settings.provider,
            "model_id": self.settings.model_name,
            "temperature": 0,
            "decision_budget": spec.decision_budget,
            "agent_visible_only": True,
        }
        _write_json(episode_dir / "episode_manifest.json", {**header, "status": "running"})
        _append_jsonl(trace_path, header)

        self.ledger.start_episode(
            run_id,
            map_id=spec.map_id,
            seed=spec.seed,
            condition_id=spec.condition_id,
        )
        self.progress({"event": "episode_started", "run_id": run_id, "map_id": spec.map_id})

        history: list[dict[str, Any]] = []
        recent_results: list[str] = []
        invalid_streak = 0
        invalid_count = 0
        decision_count = 0
        outcome = "running"
        provider_error: str | None = None
        unknown_spend = False
        start = time.monotonic()
        observation_model = V8Observation.model_validate(observation)

        with trace_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.flush()

        while outcome == "running":
            if environment.is_terminal:
                outcome = _status_of(environment)
                break
            if decision_count >= spec.decision_budget:
                outcome = "decision_budget_reached"
                break
            if time.monotonic() - start >= MAX_EPISODE_SECONDS:
                outcome = "episode_timeout"
                break
            if self.ledger.closed:
                outcome = "budget_closed"
                break
            request_index = decision_count + 1
            request_hash = _sha256_bytes(
                json.dumps(
                    {
                        "map": spec.map_id,
                        "index": request_index,
                        "observation": observation,
                        "history": history[-5:],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            )
            try:
                request_id = self.ledger.reserve_request(
                    run_id,
                    decision_index=request_index,
                    request_hash=request_hash,
                )
            except V8BudgetClosed:
                outcome = "budget_closed"
                break
            request = DecisionRequest(
                observation=observation_model,
                system_prompt=system,
                correction=invalid_streak > 0,
                invalid_output_reason="schema" if invalid_streak else None,
                recent_history=(
                    json.dumps(history[-5:], ensure_ascii=False, sort_keys=True)
                    if history
                    else None
                ),
                runtime_feedback=_repeat_hint(recent_results),
                max_output_tokens=700,
                action_contract_version="scenario_v4",
            )
            started = time.monotonic()
            try:
                response = self.provider.decide(request)
            except DecisionProviderError as exc:
                latency_ms = max(0, round((time.monotonic() - started) * 1000))
                self.ledger.fail_request(
                    request_id,
                    error_category=exc.error_category[:80],
                    latency_ms=latency_ms,
                    retryable=exc.retryable,
                    unknown_spend=exc.unknown_spend,
                )
                provider_error = exc.error_category
                unknown_spend = bool(exc.unknown_spend)
                if unknown_spend:
                    self.ledger.close("UNKNOWN_PROVIDER_SPEND", run_id=run_id)
                    outcome = "unknown_provider_spend"
                elif self.ledger.consecutive_provider_errors() >= MAX_PROVIDER_CONSECUTIVE_ERRORS:
                    self.ledger.close("THREE_CONSECUTIVE_PROVIDER_ERRORS", run_id=run_id)
                    outcome = "provider_error_limit"
                else:
                    outcome = "provider_error"
                break
            except Exception as exc:  # noqa: BLE001 - unconfirmed transport outcome
                latency_ms = max(0, round((time.monotonic() - started) * 1000))
                self.ledger.fail_request(
                    request_id,
                    error_category=type(exc).__name__[:80],
                    latency_ms=latency_ms,
                    retryable=False,
                    unknown_spend=True,
                )
                self.ledger.close("UNKNOWN_PROVIDER_SPEND", run_id=run_id)
                provider_error = type(exc).__name__
                unknown_spend = True
                outcome = "unknown_provider_spend"
                break

            latency_ms = max(0, round((time.monotonic() - started) * 1000))
            before = _compact_observation(observation)
            action, invalid_reason = _parse_action(response.candidate)
            if action is None:
                result = environment.reject_invalid_action()
                action_payload: dict[str, Any] | None = None
            else:
                action_payload = action.model_dump(mode="json", exclude_none=True)
                result = environment.step(action)
                if invalid_reason is None and result.result == "INVALID_ACTION_SCHEMA":
                    invalid_reason = "schema_shape"
            after = environment.observe()
            self.ledger.settle_request(
                request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
                latency_ms=latency_ms,
                decision_payload={
                    "action": action_payload,
                    "invalid_output_reason": invalid_reason,
                    "result": result.result,
                },
            )
            row = {
                "event": "decision",
                "run_id": run_id,
                "decision_index": request_index,
                "request_id": request_id,
                "action": action_payload,
                "invalid_output_reason": invalid_reason,
                "result": result.result,
                "status": result.status.value,
                "observation_before": before,
                "observation_after": after,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cached_input_tokens": response.cached_input_tokens,
                "latency_ms": latency_ms,
                "state_hash_after": environment.state_hash(),
            }
            _append_jsonl(trace_path, row)
            decision_count += 1
            history.append(
                {
                    "action": action_payload,
                    "result": result.result,
                    "tick": after.get(
                        "tick", after.get("current_tick", after.get("movement_steps"))
                    ),
                }
            )
            recent_results.append(result.result)
            if invalid_reason is not None:
                invalid_streak += 1
                invalid_count += 1
            else:
                invalid_streak = 0
            if invalid_streak >= MAX_SCHEMA_CONSECUTIVE_ERRORS:
                outcome = "schema_fault_limit"
                break
            observation = after
            observation_model = V8Observation.model_validate(observation)

        if outcome == "running":
            outcome = _status_of(environment)
        if outcome == "schema_fault_limit":
            self.ledger.record(
                "schema_fault_limit", run_id=run_id, decision_count=decision_count
            )

        usage = self._episode_usage(run_id)
        projected = project_metrics(environment, outcome)
        v8_metrics = {
            "experiment_id": self.ledger.experiment_id,
            "run_id": run_id,
            "map_id": spec.map_id,
            "world": spec.world,
            "difficulty": spec.level,
            "condition_id": spec.condition_id,
            "status": outcome,
            "success": environment.is_success,
            "termination_reason": environment.terminal_reason,
            "metric_schema_hash": metric_schema_hash(spec.map_id),
            "metrics": projected,
            "status_counts": summarize(projected),
        }
        judge = {
            "experiment_id": self.ledger.experiment_id,
            "run_id": run_id,
            "map_id": spec.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "replicate_id": spec.replicate_id,
            "scenario_hash": scenario_hash(spec.map_id),
            "rule_hash": rule_hash(spec.map_id),
            "source_hash": source_hash(spec.map_id),
            "commit": self.commit,
            "status": outcome,
            "environment_status": environment.status.value,
            "success": environment.is_success,
            "termination_reason": environment.terminal_reason,
            "judge_state_hash": environment.state_hash(),
            "judge_state": environment.judge_state(),
            "metrics": environment.metrics(),
            "failure_codes": _failure_codes(outcome, environment, invalid_count),
            "decision_count": decision_count,
            "invalid_action_count": invalid_count,
            "usage": usage,
            "finished_at": utc_now(),
        }
        _write_json(episode_dir / "judge_metrics.json", judge)
        _write_json(episode_dir / "v8_metrics.json", v8_metrics)
        manifest = {
            **header,
            "status": outcome,
            "success": environment.is_success,
            "termination_reason": environment.terminal_reason,
            "decision_count": decision_count,
            "invalid_action_count": invalid_count,
            "agent_trace_path": str(trace_path),
            "judge_metrics_path": str(episode_dir / "judge_metrics.json"),
            "v8_metrics_path": str(episode_dir / "v8_metrics.json"),
            "usage": usage,
            "provider_error": provider_error,
            "unknown_spend": unknown_spend,
            "finished_at": utc_now(),
        }
        _write_json(episode_dir / "episode_manifest.json", manifest)
        if not self.ledger.closed:
            self.ledger.record(
                "episode_completed",
                run_id=run_id,
                map_id=spec.map_id,
                status=outcome,
                success=environment.is_success,
                decision_count=decision_count,
                trace_sha256=_sha256_bytes(trace_path.read_bytes()),
            )
        self.progress(
            {
                "event": "episode_finished",
                "run_id": run_id,
                "map_id": spec.map_id,
                "status": outcome,
                "decision_count": decision_count,
                "cost": usage["cost"],
            }
        )
        return manifest

    def _episode_usage(self, run_id: str) -> dict[str, Any]:
        events = self.ledger.read_events()
        settled = [
            event
            for event in events
            if event["event"] == "request_settled" and event.get("episode_id") == run_id
        ]
        failed = [
            event
            for event in events
            if event["event"] == "request_failed" and event.get("episode_id") == run_id
        ]
        cost = sum(
            (Decimal(str(event.get("actual_cost", "0"))) for event in settled),
            Decimal(0),
        )
        return {
            "requests": len(settled),
            "failed_requests": len(failed),
            "input_tokens": sum(int(event["input_tokens"]) for event in settled),
            "output_tokens": sum(int(event["output_tokens"]) for event in settled),
            "cached_input_tokens": sum(
                int(event.get("cached_input_tokens") or 0) for event in settled
            ),
            "cost": str(cost),
            "currency": self.ledger.prices.currency,
            "provider_wall_seconds": round(
                sum(
                    float(event.get("latency_ms", 0)) / 1000
                    for event in [*settled, *failed]
                ),
                3,
            ),
        }


def _parse_action(candidate: object) -> tuple[V8Action | None, str | None]:
    if not isinstance(candidate, dict):
        return None, "missing_action"
    raw = candidate.get("action")
    if not isinstance(raw, dict):
        return None, "missing_action"
    try:
        action = V8Action.model_validate(raw, strict=True)
    except (ValidationError, TypeError, ValueError):
        return None, "schema_error"
    return action, None


__all__ = [
    "DECISION_BUDGETS",
    "V8EpisodeSpec",
    "V8Runner",
    "registered_specs",
]
