"""Bounded execution loop for one deterministic Agent Arena episode."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from pydantic import ValidationError

from agent_arena.agents.react import AgentDecision, ReactAgent, agent_decision_adapter
from agent_arena.arena import Environment, Observation, ToolStatus
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation.loop import PublicLoopDetector
from agent_arena.evaluation.trace import (
    EpisodeOutcome,
    EpisodeTrace,
    EpisodeTraceHeader,
    ExperimentProvenance,
    StepTrace,
    TraceEvent,
)
from agent_arena.llm.protocol import ProviderResponse


class EpisodeRunner:
    """Drive an agent through a world without exposing mutable world state."""

    def __init__(
        self,
        environment: Environment,
        agent: ReactAgent,
        settings: RuntimeSettings,
        on_decision_start: Callable[[int, bool], None] | None = None,
        on_step_complete: Callable[[StepTrace], None] | None = None,
    ) -> None:
        self._environment = environment
        self._agent = agent
        self._settings = settings
        self._on_decision_start = on_decision_start
        self._on_step_complete = on_step_complete

    def run(self) -> EpisodeTrace:
        """Return a terminal trace for one reset world instance."""

        observation = self._environment.reset(self._settings.seed)
        self._agent.reset(observation)
        trace_header = EpisodeTrace.start(
            world_version=self._settings.world_version,
            seed=self._settings.seed,
            agent=self._agent.name,
            prompt_version=self._agent.prompt_version,
            provider=self._settings.provider,
            provenance=ExperimentProvenance(
                model_name=self._settings.selected_model_name,
                enable_thinking=self._settings.enable_thinking,
                request_timeout_seconds=self._settings.request_timeout_seconds,
                retry_count=self._settings.retry_count,
                retry_backoff_seconds=tuple(self._settings.retry_backoff_seconds),
                step_limit=self._settings.step_limit,
                provider_request_version="decision_request_v1",
                base_prompt_version=self._agent.base_prompt_version,
                base_prompt_hash=self._agent.base_prompt_hash,
                memory_schema_version="memory_v1" if self._agent.name == "memory" else None,
                memory_renderer_version="memory_v1" if self._agent.name == "memory" else None,
            ),
        )
        steps: list[StepTrace] = []
        executed_actions = 0
        invalid_outputs = 0
        consecutive_invalid = 0
        rejected_actions = 0
        total_latency_ms = 0
        loop_detector = PublicLoopDetector()
        loop_detector.initialize(observation)
        runtime_feedback: str | None = None

        while executed_actions < self._settings.step_limit:
            if self._on_decision_start:
                self._on_decision_start(executed_actions + 1, False)
            decision, latency_ms, provider_failed, input_tokens, output_tokens = self._request(
                observation, correction=False, runtime_feedback=runtime_feedback
            )
            total_latency_ms += latency_ms
            if provider_failed:
                steps.append(
                    self._provider_error_event(
                        observation,
                        correction=False,
                        latency_ms=latency_ms,
                    )
                )
                return self._complete(
                    trace_header,
                    EpisodeOutcome.PROVIDER_ERROR,
                    executed_actions,
                    invalid_outputs,
                    rejected_actions,
                    total_latency_ms,
                    steps,
                )

            if decision is None:
                invalid_outputs += 1
                consecutive_invalid += 1
                steps.append(
                    self._invalid_event(
                        observation,
                        correction=False,
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                )
                if consecutive_invalid == 3:
                    return self._complete(
                        trace_header,
                        EpisodeOutcome.INVALID_ACTION_LIMIT,
                        executed_actions,
                        invalid_outputs,
                        rejected_actions,
                        total_latency_ms,
                        steps,
                    )
                steps.append(
                    StepTrace(
                        event=TraceEvent.CORRECTION_REQUESTED,
                        observation=observation,
                        latency_ms=0,
                        summary="已请求模型按规定格式重新输出决策。",
                    )
                )
                if self._on_decision_start:
                    self._on_decision_start(executed_actions + 1, True)
                decision, latency_ms, provider_failed, input_tokens, output_tokens = self._request(
                    observation, correction=True, runtime_feedback=runtime_feedback
                )
                total_latency_ms += latency_ms
                if provider_failed:
                    steps.append(
                        self._provider_error_event(
                            observation,
                            correction=True,
                            latency_ms=latency_ms,
                        )
                    )
                    return self._complete(
                        trace_header,
                        EpisodeOutcome.PROVIDER_ERROR,
                        executed_actions,
                        invalid_outputs,
                        rejected_actions,
                        total_latency_ms,
                        steps,
                    )
                if decision is None:
                    invalid_outputs += 1
                    consecutive_invalid += 1
                    steps.append(
                        self._invalid_event(
                            observation,
                            correction=True,
                            latency_ms=latency_ms,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        )
                    )
                    if consecutive_invalid == 3:
                        return self._complete(
                            trace_header,
                            EpisodeOutcome.INVALID_ACTION_LIMIT,
                            executed_actions,
                            invalid_outputs,
                            rejected_actions,
                            total_latency_ms,
                            steps,
                        )
                    continue

            consecutive_invalid = 0
            decision_observation = observation
            result, observation = self._environment.step(decision.action)
            self._agent.observe(decision.action, result, observation)
            runtime_feedback = loop_detector.observe(
                decision_observation, decision.action, result, observation
            )
            executed_actions += 1
            if result.status is ToolStatus.REJECTED:
                rejected_actions += 1
                event = TraceEvent.ACTION_REJECTED
            else:
                event = TraceEvent.ACTION_VALIDATED
            completed_step = StepTrace(
                event=event,
                observation=decision_observation,
                decision_reason=decision.decision_reason,
                action=decision.action,
                result=result,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                runtime_feedback=runtime_feedback,
            )
            steps.append(completed_step)
            if self._on_step_complete:
                self._on_step_complete(completed_step)
            if self._environment.is_success():
                return self._complete(
                    trace_header,
                    EpisodeOutcome.SUCCESS,
                    executed_actions,
                    invalid_outputs,
                    rejected_actions,
                    total_latency_ms,
                    steps,
                )

        return self._complete(
            trace_header,
            EpisodeOutcome.STEP_LIMIT,
            executed_actions,
            invalid_outputs,
            rejected_actions,
            total_latency_ms,
            steps,
        )

    def _request(
        self,
        observation: Observation,
        *,
        correction: bool,
        runtime_feedback: str | None,
    ) -> tuple[AgentDecision | None, int, bool, int | None, int | None]:
        started_at = perf_counter()
        try:
            response = self._agent.request(
                observation, correction=correction, runtime_feedback=runtime_feedback
            )
        except Exception:
            return None, _elapsed_ms(started_at), True, None, None
        if not isinstance(response, ProviderResponse):
            return None, _elapsed_ms(started_at), True, None, None
        try:
            return (
                agent_decision_adapter.validate_python(response.candidate),
                _elapsed_ms(started_at),
                False,
                response.input_tokens,
                response.output_tokens,
            )
        except ValidationError:
            return (
                None,
                _elapsed_ms(started_at),
                False,
                response.input_tokens,
                response.output_tokens,
            )

    @staticmethod
    def _invalid_event(
        observation: Observation,
        *,
        correction: bool,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> StepTrace:
        return StepTrace(
            event=TraceEvent.ACTION_INVALID,
            observation=observation,
            correction=correction,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            summary="模型输出不符合决策格式。",
        )

    @staticmethod
    def _provider_error_event(
        observation: Observation,
        *,
        correction: bool,
        latency_ms: int,
    ) -> StepTrace:
        return StepTrace(
            event=TraceEvent.PROVIDER_ERROR,
            observation=observation,
            correction=correction,
            latency_ms=latency_ms,
            summary="模型服务请求失败。",
        )

    def _complete(
        self,
        header: EpisodeTraceHeader,
        outcome: EpisodeOutcome,
        executed_actions: int,
        invalid_outputs: int,
        rejected_actions: int,
        total_latency_ms: int,
        steps: list[StepTrace],
    ) -> EpisodeTrace:
        self._agent.finish(outcome)
        return EpisodeTrace.model_validate(
            {
                **header.model_dump(),
                "outcome": outcome,
                "executed_action_count": executed_actions,
                "invalid_output_count": invalid_outputs,
                "rejected_action_count": rejected_actions,
                "latency_ms": total_latency_ms,
                "steps": tuple(steps),
            }
        )


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1_000))
