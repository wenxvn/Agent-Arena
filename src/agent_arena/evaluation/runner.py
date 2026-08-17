"""Bounded execution loop for one deterministic Agent Arena episode."""

from __future__ import annotations

from time import perf_counter

from pydantic import ValidationError

from agent_arena.agents.react import AgentDecision, ReactAgent, agent_decision_adapter
from agent_arena.arena import Environment, Observation, ToolStatus
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation.trace import (
    EpisodeOutcome,
    EpisodeTrace,
    EpisodeTraceHeader,
    StepTrace,
    TraceEvent,
)


class EpisodeRunner:
    """Drive an agent through a world without exposing mutable world state."""

    def __init__(
        self,
        environment: Environment,
        agent: ReactAgent,
        settings: RuntimeSettings,
    ) -> None:
        self._environment = environment
        self._agent = agent
        self._settings = settings

    def run(self) -> EpisodeTrace:
        """Return a terminal trace for one reset world instance."""

        observation = self._environment.reset(self._settings.seed)
        trace_header = EpisodeTrace.start(
            world_version=self._settings.world_version,
            seed=self._settings.seed,
            agent=self._agent.name,
            prompt_version=self._agent.prompt_version,
            provider=self._settings.provider,
        )
        steps: list[StepTrace] = []
        executed_actions = 0
        invalid_outputs = 0
        consecutive_invalid = 0
        rejected_actions = 0
        total_latency_ms = 0

        while executed_actions < self._settings.step_limit:
            decision, latency_ms, provider_failed = self._request(observation, correction=False)
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
                    self._invalid_event(observation, correction=False, latency_ms=latency_ms)
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
                        summary="A corrected structured decision was requested.",
                    )
                )
                decision, latency_ms, provider_failed = self._request(observation, correction=True)
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
                        self._invalid_event(observation, correction=True, latency_ms=latency_ms)
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
            executed_actions += 1
            if result.status is ToolStatus.REJECTED:
                rejected_actions += 1
                event = TraceEvent.ACTION_REJECTED
            else:
                event = TraceEvent.ACTION_VALIDATED
            steps.append(
                StepTrace(
                    event=event,
                    observation=decision_observation,
                    decision_reason=decision.decision_reason,
                    action=decision.action,
                    result=result,
                    latency_ms=latency_ms,
                )
            )
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
    ) -> tuple[AgentDecision | None, int, bool]:
        started_at = perf_counter()
        try:
            candidate = self._agent.request(observation, correction=correction)
        except Exception:
            return None, _elapsed_ms(started_at), True
        try:
            return agent_decision_adapter.validate_python(candidate), _elapsed_ms(started_at), False
        except ValidationError:
            return None, _elapsed_ms(started_at), False

    @staticmethod
    def _invalid_event(observation: Observation, *, correction: bool, latency_ms: int) -> StepTrace:
        return StepTrace(
            event=TraceEvent.ACTION_INVALID,
            observation=observation,
            correction=correction,
            latency_ms=latency_ms,
            summary="The provider response did not match the decision schema.",
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
            summary="The provider request failed.",
        )

    @staticmethod
    def _complete(
        header: EpisodeTraceHeader,
        outcome: EpisodeOutcome,
        executed_actions: int,
        invalid_outputs: int,
        rejected_actions: int,
        total_latency_ms: int,
        steps: list[StepTrace],
    ) -> EpisodeTrace:
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
