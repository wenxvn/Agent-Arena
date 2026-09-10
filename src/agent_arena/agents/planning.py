"""Generic high-level planning with a separate action Executor."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from agent_arena.agents.react import ReactAgent
from agent_arena.arena import Action, Observation, ToolResult
from agent_arena.llm import DecisionProvider
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse
from agent_arena.planning import (
    PlanningMetadata,
    PlanSignal,
    PlanState,
    planner_decision_adapter,
)
from agent_arena.planning.monitor import PlanMonitor


class PlanningAgent(ReactAgent):
    """Maintain one public PlanState while reusing the common Action Executor."""

    name = "planning"
    prompt_version = "planning_v1"
    base_prompt_version = "planning_executor_v1"

    def __init__(
        self,
        provider: DecisionProvider,
        planner_prompt_path: Path | None = None,
        executor_prompt_path: Path | None = None,
        *,
        overall_goal: str = "完成当前环境要求的最终任务",
        no_progress_threshold: int = 3,
    ) -> None:
        super().__init__(provider, executor_prompt_path or self._executor_prompt_path())
        planner_path = planner_prompt_path or self._planner_prompt_path()
        self._planner_prompt = planner_path.read_text(encoding="utf-8")
        self._overall_goal = overall_goal
        self._monitor = PlanMonitor(no_progress_threshold=no_progress_threshold)
        self._plan_state: PlanState | None = None
        self._pending_signal: PlanSignal | None = None
        self._last_observation: Observation | None = None
        self._metadata = PlanningMetadata()
        self._active = False

    @property
    def planning_enabled(self) -> bool:
        return True

    @property
    def planner_prompt_version(self) -> str | None:
        return "planning_v1"

    @property
    def executor_prompt_version(self) -> str | None:
        return "planning_executor_v1"

    @property
    def plan_monitor_version(self) -> str | None:
        return "plan_monitor_v2"

    @property
    def planning_policy(self) -> str | None:
        return "event_triggered"

    @property
    def planning_metadata(self) -> PlanningMetadata:
        return self._metadata

    @property
    def plan_state(self) -> PlanState | None:
        return self._plan_state

    def reset(self, observation: Observation) -> None:
        del observation
        self._active = True
        self._plan_state = None
        self._pending_signal = None
        self._last_observation = None
        self._monitor.reset()
        self._metadata = PlanningMetadata()

    def observe(self, action: Action, result: object, observation: Observation) -> None:
        if not self._active:
            raise RuntimeError("PlanningAgent requires reset before observe.")
        if not isinstance(result, ToolResult):
            raise TypeError("PlanningAgent requires ToolResult.")
        if self._plan_state is None:
            raise RuntimeError("PlanningAgent requires a plan before observe.")
        before = self._last_observation or observation
        signal = self._monitor.evaluate(self._plan_state, before, action, result, observation)
        if signal.status != "continue":
            self._pending_signal = signal
        self._metadata = replace(
            self._metadata,
            plan_signal=signal.status if signal.status != "continue" else None,
            subgoal_completed=signal.status == "subgoal_completed",
        )
        self._last_observation = observation

    def finish(self, outcome: object) -> None:
        del outcome
        self._active = False
        self._plan_state = None
        self._pending_signal = None
        self._last_observation = None
        self._monitor.reset()
        self._metadata = PlanningMetadata()

    def request(
        self,
        observation: Observation,
        *,
        correction: bool,
        runtime_feedback: str | None = None,
        invalid_output_reason: str | None = None,
        recent_history: str | None = None,
    ) -> ProviderResponse:
        if not self._active:
            raise RuntimeError("PlanningAgent requires reset before request.")
        pending = self._pending_signal
        trigger = pending.reason if pending and pending.reason else "episode_start"
        plan_signal = pending.status if pending else None
        planner_latency_ms: int | None = None
        planner_input_tokens: int | None = None
        planner_output_tokens: int | None = None
        planner_called = self._plan_state is None or pending is not None

        self._metadata = PlanningMetadata(
            plan_id=self._plan_state.plan_id if self._plan_state else None,
            plan_version=self._plan_state.plan_version if self._plan_state else None,
            current_subgoal=self._plan_state.current_subgoal if self._plan_state else None,
            planner_called=planner_called,
            replan_reason=trigger if planner_called else None,
            plan_signal=plan_signal,
        )

        if planner_called:
            planner_started = perf_counter()
            planner_response = self._provider.decide(
                DecisionRequest(
                    observation=observation,
                    system_prompt=self._planner_prompt,
                    correction=False,
                    runtime_feedback=f"重新规划原因：{trigger}",
                    recent_history=recent_history,
                    plan_data=self._render_plan_state(),
                    output_contract="planner",
                )
            )
            planner_latency_ms = _elapsed_ms(planner_started)
            if not isinstance(planner_response, ProviderResponse):
                raise TypeError("Planner provider must return ProviderResponse.")
            planner_input_tokens = planner_response.input_tokens
            planner_output_tokens = planner_response.output_tokens
            decision = planner_decision_adapter.validate_python(planner_response.candidate)
            completed = list(self._plan_state.completed_subgoals) if self._plan_state else []
            if pending and pending.status == "subgoal_completed" and self._plan_state:
                if self._plan_state.current_subgoal not in completed:
                    completed.append(self._plan_state.current_subgoal)
            self._plan_state = PlanState(
                overall_goal=self._plan_state.overall_goal
                if self._plan_state
                else self._overall_goal,
                current_subgoal=decision.current_subgoal,
                success_criteria=decision.success_criteria,
                known_constraints=decision.known_constraints,
                relevant_resources=decision.relevant_resources,
                completed_subgoals=tuple(completed),
                unresolved_questions=decision.unresolved_questions,
                replan_reason=trigger,
            )
            self._pending_signal = None

        if self._plan_state is None:
            raise RuntimeError("PlanningAgent failed to create PlanState.")

        executor_started = perf_counter()
        executor_response = self._provider.decide(
            DecisionRequest(
                observation=observation,
                system_prompt=self._prompt,
                correction=correction,
                runtime_feedback=runtime_feedback,
                invalid_output_reason=invalid_output_reason,
                recent_history=recent_history,
                plan_data=self._render_plan_state(),
                output_contract="action",
            )
        )
        executor_latency_ms = _elapsed_ms(executor_started)
        if not isinstance(executor_response, ProviderResponse):
            raise TypeError("Executor provider must return ProviderResponse.")
        self._last_observation = observation
        self._metadata = PlanningMetadata(
            plan_id=self._plan_state.plan_id,
            plan_version=self._plan_state.plan_version,
            current_subgoal=self._plan_state.current_subgoal,
            planner_called=planner_called,
            replan_reason=trigger if planner_called else None,
            plan_signal=plan_signal,
            planner_latency_ms=planner_latency_ms,
            planner_input_tokens=planner_input_tokens,
            planner_output_tokens=planner_output_tokens,
            executor_latency_ms=executor_latency_ms,
            executor_input_tokens=executor_response.input_tokens,
            executor_output_tokens=executor_response.output_tokens,
        )
        return ProviderResponse(
            candidate=executor_response.candidate,
            input_tokens=_sum_tokens(planner_input_tokens, executor_response.input_tokens),
            output_tokens=_sum_tokens(planner_output_tokens, executor_response.output_tokens),
        )

    def _render_plan_state(self) -> str | None:
        if self._plan_state is None:
            return None
        return json.dumps(
            self._plan_state.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
        )

    @staticmethod
    def _planner_prompt_path() -> Path:
        return Path(__file__).resolve().parents[3] / "prompts" / "planning_v1.txt"

    @staticmethod
    def _executor_prompt_path() -> Path:
        return Path(__file__).resolve().parents[3] / "prompts" / "planning_executor_v1.txt"


def _sum_tokens(first: int | None, second: int | None) -> int | None:
    if first is None and second is None:
        return None
    return (first or 0) + (second or 0)


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1_000))
