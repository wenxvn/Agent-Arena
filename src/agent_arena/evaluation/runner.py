"""Bounded execution loop for one deterministic Agent Arena episode."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from time import perf_counter

from pydantic import ValidationError

from agent_arena.agents.candidate import CandidateSelectionAgent, candidate_selection_adapter
from agent_arena.agents.react import (
    AgentDecision,
    ReactAgent,
    ScenarioAgentDecision,
    agent_decision_adapter,
    scenario_agent_decision_adapter,
)
from agent_arena.arena import (
    Action,
    Environment,
    Observation,
    PublicMilestone,
    ScenarioAction,
    ScenarioObservation,
    ScenarioStatus,
    SubmitAction,
    ToolResult,
    ToolStatus,
    action_adapter,
)
from agent_arena.arena.models import (
    InspectAction,
    LookAction,
    MoveAction,
    PickupAction,
    ReadTerminalAction,
    UseAction,
)
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation.loop import PublicLoopDetector
from agent_arena.evaluation.progress import ProgressDetector
from agent_arena.evaluation.trace import (
    EpisodeOutcome,
    EpisodeTrace,
    EpisodeTraceHeader,
    ExperimentProvenance,
    InvalidOutputReason,
    MemoryStatisticsTrace,
    StepTrace,
    TraceEvent,
)
from agent_arena.llm.budget import ProviderBudgetExceeded
from agent_arena.llm.protocol import ActionContractVersion, ProviderResponse
from agent_arena.safety import sanitize_text
from agent_arena.worlds.scenario.base import ScenarioEnvironment


class EpisodeRunner:
    """Drive an agent through a world without exposing mutable world state."""

    def __init__(
        self,
        environment: Environment,
        agent: ReactAgent,
        settings: RuntimeSettings,
        on_decision_start: Callable[[int, bool], None] | None = None,
        on_step_complete: Callable[[StepTrace], None] | None = None,
        enable_runtime_feedback: bool = True,
        enable_public_action_hints: bool = False,
        recent_history_window: int = 0,
        enable_structured_milestones: bool = False,
        enable_public_action_guard: bool = False,
        enable_stuck_recovery: bool | None = None,
        enable_concrete_action_candidates: bool = False,
        enable_public_phase_context: bool = False,
        enable_candidate_selection: bool = False,
    ) -> None:
        self._environment = environment
        self._agent = agent
        self._settings = settings
        self._is_scenario_environment = isinstance(environment, ScenarioEnvironment)
        self._action_contract_version: ActionContractVersion = (
            "scenario_v3" if self._is_scenario_environment else "legacy_v1"
        )
        if self._is_scenario_environment and (agent.name != "react" or enable_candidate_selection):
            raise ValueError("V3 Scenario 当前只支持 ReactAgent 的公开 Action 契约。")
        if (
            agent.name == "memory"
            and getattr(agent, "memory_version", "v2") != settings.memory_version
        ):
            raise ValueError("运行配置与 MemoryAgent 记忆策略不一致。")
        self._on_decision_start = on_decision_start
        self._on_step_complete = on_step_complete
        self._enable_runtime_feedback = enable_runtime_feedback
        self._enable_public_action_hints = enable_public_action_hints
        self._recent_history_window = recent_history_window
        self._enable_structured_milestones = enable_structured_milestones
        self._enable_public_action_guard = enable_public_action_guard
        self._enable_concrete_action_candidates = enable_concrete_action_candidates
        self._enable_public_phase_context = enable_public_phase_context
        self._enable_candidate_selection = enable_candidate_selection
        self._enable_stuck_recovery = (
            enable_runtime_feedback if enable_stuck_recovery is None else enable_stuck_recovery
        )

    def run(self) -> EpisodeTrace:
        """Return a terminal trace for one reset world instance."""

        world, world_version, definition_id, definition_hash = self._environment.identity
        if (self._settings.world, self._settings.world_version) != (world, world_version):
            raise ValueError("运行配置与实际环境身份不一致。")
        observation = self._environment.reset(self._settings.seed)
        self._agent.reset(observation)
        # 阶段文本完全来自世界声明的里程碑；无里程碑的世界不受影响。
        phase_milestones = (
            self._environment.public_milestones if self._enable_public_phase_context else ()
        )
        trace_header = EpisodeTrace.start(
            world_version=world_version,
            seed=self._settings.seed,
            agent=self._agent.name,
            prompt_version=self._agent.prompt_version,
            provider=self._settings.provider,
            scenario_id=(
                self._require_scenario_environment().scenario_id
                if self._is_scenario_environment
                else None
            ),
            trace_schema_version=3 if self._is_scenario_environment else 2,
            provenance=ExperimentProvenance(
                trace_contract_version=(
                    "scenario_v3" if self._is_scenario_environment else "experiment_v2"
                ),
                world=world,
                world_definition_id=definition_id,
                world_definition_hash=definition_hash,
                action_contract_version=self._action_contract_version,
                source_design_id=(
                    self._require_scenario_environment().source_design_id
                    if self._is_scenario_environment
                    else None
                ),
                source_design_hash=(
                    self._require_scenario_environment().source_design_hash
                    if self._is_scenario_environment
                    else None
                ),
                scenario_family=(
                    self._require_scenario_environment().family
                    if self._is_scenario_environment
                    else None
                ),
                scenario_difficulty=(
                    self._require_scenario_environment().difficulty
                    if self._is_scenario_environment
                    else None
                ),
                mechanic_version=(
                    self._require_scenario_environment().mechanic_version
                    if self._is_scenario_environment
                    else None
                ),
                ruleset_sha=(
                    self._require_scenario_environment().ruleset_sha
                    if self._is_scenario_environment
                    else None
                ),
                max_output_tokens=(
                    self._settings.max_provider_output_tokens
                    if self._settings.max_provider_output_tokens is not None
                    else (
                        self._settings.ollama_max_output_tokens
                        if self._settings.provider == "ollama"
                        else None
                    )
                ),
                max_provider_requests=self._settings.max_provider_requests,
                max_provider_tokens=self._settings.max_provider_tokens,
                max_provider_output_tokens=self._settings.max_provider_output_tokens,
                provider_budget_timeout_seconds=self._settings.provider_budget_timeout_seconds,
                provider_budget_experiment_id=self._settings.provider_budget_experiment_id,
                model_name=(
                    "fake-scripted"
                    if self._settings.provider == "fake"
                    else self._settings.selected_model_name
                ),
                enable_thinking=(
                    False if self._settings.provider == "ollama" else self._settings.enable_thinking
                ),
                request_timeout_seconds=self._settings.request_timeout_seconds,
                retry_count=self._settings.retry_count,
                retry_backoff_seconds=tuple(self._settings.retry_backoff_seconds),
                step_limit=self._settings.step_limit,
                reasoning_effort=self._settings.reasoning_effort,
                response_format=(
                    "json_schema"
                    if self._settings.provider == "ollama"
                    else self._settings.response_format
                ),
                provider_request_version="decision_request_v1",
                base_prompt_version=self._agent.base_prompt_version,
                base_prompt_hash=self._agent.base_prompt_hash,
                runtime_feedback_enabled=self._enable_runtime_feedback,
                public_action_hints_enabled=self._enable_public_action_hints,
                recent_history_enabled=self._recent_history_window > 0,
                recent_history_window=self._recent_history_window,
                structured_milestones_enabled=self._enable_structured_milestones,
                public_action_guard_enabled=self._enable_public_action_guard,
                stuck_recovery_enabled=self._enable_stuck_recovery,
                concrete_action_candidates_enabled=self._enable_concrete_action_candidates,
                public_phase_context_enabled=bool(phase_milestones),
                candidate_selection_enabled=self._enable_candidate_selection,
                memory_schema_version=(
                    getattr(self._agent, "memory_schema_version", "memory_v1")
                    if self._agent.name in {"memory", "planner_assisted"}
                    else None
                ),
                memory_renderer_version=(
                    getattr(self._agent, "memory_renderer_version", "memory_v1")
                    if self._agent.name in {"memory", "planner_assisted"}
                    else None
                ),
                planning_enabled=self._agent.planning_enabled,
                planner_prompt_version=self._agent.planner_prompt_version,
                executor_prompt_version=self._agent.executor_prompt_version,
                plan_monitor_version=self._agent.plan_monitor_version,
                planning_policy=self._agent.planning_policy,
            ),
        )
        steps: list[StepTrace] = []
        executed_actions = 0
        decision_attempts = 0
        invalid_outputs = 0
        consecutive_invalid = 0
        rejected_actions = 0
        total_latency_ms = 0
        loop_detector = PublicLoopDetector()
        loop_detector.initialize(observation)
        phase_tracker = PublicPhaseTracker(milestones=phase_milestones)
        phase_tracker.initialize(observation)
        candidate_tracker = PublicCandidateTracker()
        candidate_tracker.initialize(observation)
        progress_detector = ProgressDetector()
        progress_detector.reset(observation)
        runtime_feedback = (
            _public_action_hints(observation) if self._enable_public_action_hints else None
        )
        if self._enable_concrete_action_candidates:
            runtime_feedback = _join_feedback(
                runtime_feedback, _concrete_action_candidates(observation)
            )
        if phase_milestones:
            runtime_feedback = _join_feedback(runtime_feedback, phase_tracker.render(observation))
        recent_history: list[
            tuple[Observation | ScenarioObservation, ScenarioAction, ToolResult]
        ] = []

        while self._settings.step_limit == 0 or decision_attempts < self._settings.step_limit:
            corrected = False
            candidates = candidate_tracker.candidates(observation)
            request_feedback = runtime_feedback
            if self._enable_candidate_selection:
                request_feedback = _join_feedback(request_feedback, candidates.render())
            if self._on_decision_start:
                self._on_decision_start(executed_actions + 1, False)
            (
                decision,
                latency_ms,
                provider_failed,
                input_tokens,
                output_tokens,
                invalid_reason,
            ) = self._request(
                observation,
                correction=False,
                runtime_feedback=request_feedback,
                invalid_output_reason=None,
                recent_history=_render_recent_history(recent_history),
                candidates=candidates,
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
                        invalid_output_reason=invalid_reason,
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
                corrected = True
                if self._on_decision_start:
                    self._on_decision_start(executed_actions + 1, True)
                (
                    decision,
                    latency_ms,
                    provider_failed,
                    input_tokens,
                    output_tokens,
                    invalid_reason,
                ) = self._request(
                    observation,
                    correction=True,
                    runtime_feedback=request_feedback,
                    invalid_output_reason=invalid_reason.value if invalid_reason else None,
                    recent_history=_render_recent_history(recent_history),
                    candidates=candidates,
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
                            invalid_output_reason=invalid_reason,
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
            decision_attempts += 1
            if self._enable_public_action_guard:
                guard_error = _public_action_violation(decision.action, observation)
                if guard_error:
                    rejected_actions += 1
                    runtime_feedback = guard_error
                    guarded_step = StepTrace(
                        event=TraceEvent.ACTION_REJECTED,
                        correction=corrected,
                        observation=observation,
                        decision_reason=decision.decision_reason,
                        action=_trace_action(
                            decision.action,
                            redact_scenario_answer=self._is_scenario_environment,
                        ),
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        runtime_feedback=guard_error,
                        summary="公开动作校验拒绝了该 Action；环境未执行。",
                    )
                    guarded_step = self._with_guidance(guarded_step)
                    steps.append(guarded_step)
                    if self._on_step_complete:
                        self._on_step_complete(guarded_step)
                    continue
            if self._is_scenario_environment:
                result, observation = self._require_scenario_environment().step(decision.action)
            else:
                if not isinstance(
                    decision.action,
                    (
                        LookAction,
                        MoveAction,
                        InspectAction,
                        PickupAction,
                        UseAction,
                        ReadTerminalAction,
                    ),
                ):
                    raise TypeError("Legacy environment received a V3-only Action.")
                result, observation = self._environment.step(decision.action)
                self._agent.observe(decision.action, result, observation)
            progress_event = progress_detector.evaluate(
                decision_observation, decision.action, result, observation
            )
            phase_tracker.observe(result)
            candidate_tracker.observe(decision_observation, decision.action, result, observation)
            loop_feedback = loop_detector.observe(
                decision_observation, decision.action, result, observation
            )
            feedback_parts: list[str] = []
            if self._enable_stuck_recovery and loop_feedback:
                feedback_parts.append(loop_feedback)
            if self._enable_public_action_hints:
                feedback_parts.append(_public_action_hints(observation))
            if self._enable_concrete_action_candidates:
                feedback_parts.append(_concrete_action_candidates(observation))
            if phase_milestones:
                phase_text = phase_tracker.render(observation)
                if phase_text:
                    feedback_parts.append(phase_text)
            runtime_feedback = "\n".join(feedback_parts) or None
            if self._recent_history_window > 0:
                recent_history.append((decision_observation, decision.action, result))
                del recent_history[: -self._recent_history_window]
            executed_actions += 1
            if result.status is ToolStatus.REJECTED:
                rejected_actions += 1
                event = TraceEvent.ACTION_REJECTED
            else:
                event = TraceEvent.ACTION_VALIDATED
            completed_step = StepTrace(
                event=event,
                correction=corrected,
                observation=decision_observation,
                decision_reason=decision.decision_reason,
                action=_trace_action(
                    decision.action,
                    redact_scenario_answer=self._is_scenario_environment,
                ),
                result=result,
                next_observation=observation,
                progress=progress_event,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                memory_statistics=(
                    MemoryStatisticsTrace.model_validate(self._agent.memory_statistics)
                    if self._agent.memory_statistics is not None
                    else None
                ),
                scenario_event=(
                    self._require_scenario_environment().step_metadata.scenario_event
                    if self._is_scenario_environment
                    else None
                ),
                scenario_status=(
                    self._require_scenario_environment().step_metadata.scenario_status
                    if self._is_scenario_environment
                    else None
                ),
                failure_reason=(
                    self._require_scenario_environment().step_metadata.failure_reason
                    if self._is_scenario_environment
                    else None
                ),
                score_components=(
                    self._require_scenario_environment().step_metadata.score_components
                    if self._is_scenario_environment
                    else None
                ),
                runtime_feedback=(
                    sanitize_text(runtime_feedback, max_length=500) if runtime_feedback else None
                ),
            )
            completed_step = self._with_guidance(completed_step)
            steps.append(completed_step)
            if self._on_step_complete:
                self._on_step_complete(completed_step)
            terminal_outcome = self._terminal_outcome()
            if terminal_outcome is not None:
                return self._complete(
                    trace_header,
                    terminal_outcome,
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
        invalid_output_reason: str | None,
        recent_history: str | None,
        candidates: PublicCandidateSet,
    ) -> tuple[
        AgentDecision | ScenarioAgentDecision | None,
        int,
        bool,
        int | None,
        int | None,
        InvalidOutputReason | None,
    ]:
        started_at = perf_counter()
        try:
            response = self._agent.request_for_contract(
                observation,
                correction=correction,
                runtime_feedback=runtime_feedback,
                invalid_output_reason=invalid_output_reason,
                recent_history=recent_history,
                action_contract_version=self._action_contract_version,
            )
        except ProviderBudgetExceeded:
            raise
        except Exception:
            return None, _elapsed_ms(started_at), True, None, None, None
        if not isinstance(response, ProviderResponse):
            return None, _elapsed_ms(started_at), True, None, None, None
        try:
            decision = self._validate_decision(response, candidates)
            return (
                decision,
                _elapsed_ms(started_at),
                False,
                response.input_tokens,
                response.output_tokens,
                None,
            )
        except (ValidationError, ValueError):
            return (
                None,
                _elapsed_ms(started_at),
                False,
                response.input_tokens,
                response.output_tokens,
                _classify_invalid_candidate(response.candidate),
            )

    def _validate_decision(
        self, response: ProviderResponse, candidates: PublicCandidateSet
    ) -> AgentDecision | ScenarioAgentDecision:
        if not self._enable_candidate_selection:
            if self._is_scenario_environment:
                return scenario_agent_decision_adapter.validate_python(response.candidate)
            return agent_decision_adapter.validate_python(response.candidate)
        if not isinstance(self._agent, CandidateSelectionAgent):
            raise ValueError("Candidate selection requires CandidateSelectionAgent.")
        selection = candidate_selection_adapter.validate_python(response.candidate)
        action = candidates.resolve(selection.candidate_id)
        if action is None:
            raise ValueError("Candidate id is not in the current public candidate set.")
        return AgentDecision(decision_reason=selection.decision_reason, action=action)

    def _invalid_event(
        self,
        observation: Observation,
        *,
        correction: bool,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        invalid_output_reason: InvalidOutputReason | None,
    ) -> StepTrace:
        return self._with_guidance(
            StepTrace(
                event=TraceEvent.ACTION_INVALID,
                observation=observation,
                correction=correction,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                summary="模型输出不符合决策格式。",
                invalid_output_reason=invalid_output_reason,
            )
        )

    def _provider_error_event(
        self,
        observation: Observation,
        *,
        correction: bool,
        latency_ms: int,
    ) -> StepTrace:
        return self._with_guidance(
            StepTrace(
                event=TraceEvent.PROVIDER_ERROR,
                observation=observation,
                correction=correction,
                latency_ms=latency_ms,
                summary="模型服务请求失败。",
            )
        )

    def _with_guidance(self, step: StepTrace) -> StepTrace:
        feedback = self._agent.planner_feedback
        planning = self._agent.planning_metadata
        return step.model_copy(
            update={
                "planner_feedback": feedback,
                "planner_feedback_hash": sha256(feedback.encode("utf-8")).hexdigest()
                if feedback
                else None,
                "suggested_action": self._agent.suggested_action,
                "plan_id": planning.plan_id,
                "plan_version": planning.plan_version,
                "current_subgoal": planning.current_subgoal,
                "planner_called": planning.planner_called,
                "replan_reason": planning.replan_reason,
                "plan_signal": planning.plan_signal,
                "subgoal_completed": planning.subgoal_completed,
                "planner_latency_ms": planning.planner_latency_ms,
                "planner_input_tokens": planning.planner_input_tokens,
                "planner_output_tokens": planning.planner_output_tokens,
                "executor_latency_ms": planning.executor_latency_ms,
                "executor_input_tokens": planning.executor_input_tokens,
                "executor_output_tokens": planning.executor_output_tokens,
            }
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
        trace_data: dict[str, object] = {
            **header.model_dump(),
            "outcome": outcome,
            "executed_action_count": executed_actions,
            "invalid_output_count": invalid_outputs,
            "rejected_action_count": rejected_actions,
            "latency_ms": total_latency_ms,
            "steps": tuple(steps),
        }
        if self._is_scenario_environment:
            scenario = self._require_scenario_environment()
            terminal = scenario.terminal_status
            trace_data.update(
                {
                    "scenario_status": terminal.status,
                    "failure_reason": terminal.failure_reason,
                    "score_components": dict(scenario.scenario_state.score_components),
                }
            )
        return EpisodeTrace.model_validate(trace_data)

    def _require_scenario_environment(self) -> ScenarioEnvironment:
        if not isinstance(self._environment, ScenarioEnvironment):
            raise TypeError("Scenario action contract requires ScenarioEnvironment.")
        return self._environment

    def _terminal_outcome(self) -> EpisodeOutcome | None:
        if not self._is_scenario_environment:
            return EpisodeOutcome.SUCCESS if self._environment.is_success() else None
        status = self._require_scenario_environment().terminal_status.status
        if status is ScenarioStatus.SUCCESS:
            return EpisodeOutcome.SCENARIO_SUCCESS
        if status is ScenarioStatus.PARTIAL_SUCCESS:
            return EpisodeOutcome.PARTIAL_SUCCESS
        if status is ScenarioStatus.FAILURE:
            return EpisodeOutcome.SCENARIO_FAILURE
        return None


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1_000))


def _trace_action(action: ScenarioAction, *, redact_scenario_answer: bool) -> ScenarioAction:
    if redact_scenario_answer and isinstance(action, SubmitAction):
        return action.model_copy(update={"answer": "[redacted]"})
    return action


def _classify_invalid_candidate(candidate: object) -> InvalidOutputReason:
    """Classify schema failures without retaining candidate text or values."""

    if not isinstance(candidate, dict):
        return InvalidOutputReason.NOT_OBJECT
    if "decision_reason" not in candidate or "action" not in candidate:
        return InvalidOutputReason.MISSING_FIELD
    if set(candidate) != {"decision_reason", "action"}:
        return InvalidOutputReason.EXTRA_FIELD
    if not isinstance(candidate["action"], dict):
        return InvalidOutputReason.ACTION_NOT_OBJECT
    action = candidate["action"]
    if "tool" not in action:
        return InvalidOutputReason.MISSING_TOOL
    tool = action["tool"]
    required_arguments = {
        "look": (),
        "move": ("destination",),
        "inspect": ("target",),
        "pickup": ("item",),
        "use": ("item", "target"),
        "read_terminal": ("target",),
        "interact": ("target", "choice"),
        "wait": ("turns",),
        "submit": ("target", "answer"),
    }
    if not isinstance(tool, str) or tool not in required_arguments:
        return InvalidOutputReason.UNKNOWN_TOOL
    required = required_arguments[tool]
    if any(argument not in action for argument in required):
        return InvalidOutputReason.MISSING_ARGUMENT
    allowed = {"tool", *required}
    if set(action) != allowed:
        return InvalidOutputReason.EXTRA_FIELD
    return InvalidOutputReason.INVALID_VALUE


def _public_action_hints(observation: Observation) -> str:
    """Render candidate action shapes using only the current public observation."""

    moves = ", ".join(f"move(destination={exit_name})" for exit_name in observation.available_exits)
    targets = ", ".join(observation.visible_objects) or "无"
    inventory = ", ".join(observation.inventory) or "无"
    return (
        "公开动作候选（只根据当前 Observation，不代表任务答案）："
        f"look()；move 可选：{moves or '无'}；visible_objects：{targets}；"
        f"inventory：{inventory}。inspect/read_terminal/pickup 只能使用 visible_objects 中的目标；"
        "use 只能使用 inventory 中的物品和 visible_objects 中的目标。"
    )


def _join_feedback(*parts: str | None) -> str | None:
    values = [part for part in parts if part]
    return "\n".join(values) or None


def _concrete_action_candidates(observation: Observation) -> str:
    """List only concrete actions whose arguments come from public data."""

    candidates = ["look()"]
    candidates.extend(
        f"move(destination={destination})" for destination in observation.available_exits
    )
    candidates.extend(f"inspect(target={target})" for target in observation.visible_objects)
    candidates.extend(f"read_terminal(target={target})" for target in observation.visible_objects)
    candidates.extend(f"pickup(item={item})" for item in observation.visible_objects)
    for item in observation.inventory:
        candidates.extend(
            f"use(item={item},target={target})" for target in observation.visible_objects
        )
    if observation.last_action_result is not None:
        code = _public_authorization_code(observation.last_action_result.summary)
        if code:
            candidates.extend(
                f"use(item={code},target={target})" for target in observation.visible_objects
            )
    prefix = "公开具体候选动作（只根据当前 Observation 和公开结果生成，不代表任务答案）："
    return prefix + "；".join(candidates)


def _public_authorization_code(summary: str) -> str | None:
    marker = "授权码："
    if marker not in summary:
        return None
    value = summary.split(marker, maxsplit=1)[1].strip().split()[0]
    return value if value.isascii() and value.isalnum() or "-" in value else None


@dataclass(frozen=True)
class PublicCandidate:
    """One concrete Action identified only by an opaque, model-selectable id."""

    candidate_id: str
    action: Action


@dataclass(frozen=True)
class PublicCandidateSet:
    """A bounded set of currently admissible Actions for the selection experiment."""

    values: tuple[PublicCandidate, ...]

    def resolve(self, candidate_id: str) -> Action | None:
        for candidate in self.values:
            if candidate.candidate_id == candidate_id:
                return candidate.action
        return None

    def render(self) -> str:
        rendered = "；".join(
            f"{candidate.candidate_id}={_render_action(candidate.action)}"
            for candidate in self.values
        )
        return (
            "公开候选动作（仅由当前 Observation 与已发生的公开结果生成；"
            "不代表路线或任务答案）：" + rendered
        )


@dataclass
class PublicCandidateTracker:
    """Suppress actions already disproved under the same public conditions."""

    _excluded: dict[str, set[str]] | None = None
    _public_values: tuple[str, ...] = ()

    def initialize(self, observation: Observation) -> None:
        del observation
        self._excluded = {}
        self._public_values = ()

    def candidates(self, observation: Observation) -> PublicCandidateSet:
        if self._excluded is None:
            raise RuntimeError("PublicCandidateTracker requires initialize before candidates.")
        excluded = self._excluded.get(_public_state_key(observation), set())
        actions = _public_concrete_actions(observation, self._public_values)
        values = tuple(
            PublicCandidate(candidate_id=f"a{index}", action=action)
            for index, action in enumerate(actions, start=1)
            if _action_identity(action) not in excluded
        )
        if values:
            return PublicCandidateSet(values)
        # look is always legal and ensures a malformed public history cannot exhaust the contract.
        fallback = PublicCandidate(
            candidate_id="a1", action=action_adapter.validate_python({"tool": "look"})
        )
        return PublicCandidateSet((fallback,))

    def observe(
        self,
        observation: Observation,
        action: ScenarioAction,
        result: ToolResult,
        next_observation: Observation,
    ) -> None:
        if self._excluded is None:
            raise RuntimeError("PublicCandidateTracker requires initialize before observe.")
        code = _public_authorization_code(result.summary)
        if code and code not in self._public_values:
            self._public_values = (*self._public_values, code)
        if result.status is ToolStatus.REJECTED:
            self._excluded.setdefault(_public_state_key(next_observation), set()).add(
                _action_identity(action)
            )
        elif _public_state_key(observation) == _public_state_key(next_observation):
            self._excluded.setdefault(_public_state_key(observation), set()).add(
                _action_identity(action)
            )


def _public_concrete_actions(
    observation: Observation, public_values: tuple[str, ...]
) -> tuple[Action, ...]:
    """Enumerate parameter-complete Actions from public values without scoring a route."""

    raw_actions: list[dict[str, str]] = [{"tool": "look"}]
    raw_actions.extend(
        {"tool": "move", "destination": destination} for destination in observation.available_exits
    )
    raw_actions.extend(
        {"tool": "inspect", "target": target} for target in observation.visible_objects
    )
    raw_actions.extend(
        {"tool": "read_terminal", "target": target} for target in observation.visible_objects
    )
    raw_actions.extend(
        {"tool": "pickup", "item": item}
        for item in observation.visible_objects
        if item not in observation.inventory
    )
    raw_actions.extend(
        {"tool": "use", "item": item, "target": target}
        for item in observation.inventory
        for target in observation.visible_objects
    )
    raw_actions.extend(
        {"tool": "use", "item": value, "target": target}
        for value in public_values
        for target in observation.visible_objects
    )
    return tuple(action_adapter.validate_python(action) for action in raw_actions)


def _action_identity(action: ScenarioAction) -> str:
    return json.dumps(action.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _public_state_key(observation: Observation) -> str:
    """Use persistent public facts, excluding the latest result event."""

    # ToolResult is an event, not a persistent world fact. Excluding it lets the
    # selector identify a successful no-op such as repeated terminal reads.
    public_state = observation.model_dump(mode="json", exclude={"last_action_result"})
    return json.dumps(
        public_state,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _render_action(action: ScenarioAction) -> str:
    values = action.model_dump(mode="json")
    tool = values.pop("tool")
    arguments = ",".join(f"{name}={value}" for name, value in values.items())
    return f"{tool}({arguments})" if arguments else f"{tool}()"


@dataclass
class PublicPhaseTracker:
    """Render the first incomplete world milestone as public phase context."""

    milestones: tuple[PublicMilestone, ...] = ()
    completed: set[int] = field(default_factory=set)

    def initialize(self, observation: Observation) -> None:
        del observation
        self.completed.clear()

    def observe(self, result: ToolResult) -> None:
        for index, milestone in enumerate(self.milestones):
            if milestone.trigger_reasons and result.reason in milestone.trigger_reasons:
                self.completed.add(index)

    def render(self, observation: Observation) -> str | None:
        if not self.milestones:
            return None
        for index, milestone in enumerate(self.milestones):
            if milestone.key_items:
                missing = milestone.key_items - set(observation.inventory)
                if not missing:
                    continue
                return (
                    f"当前公开阶段：{milestone.stage}。"
                    f"已完成：{milestone.done_text}。"
                    f"未完成：{milestone.undone.format(missing='、'.join(sorted(missing)))}。"
                )
            if index in self.completed:
                continue
            return (
                f"当前公开阶段：{milestone.stage}。"
                f"已完成：{milestone.done_text}。"
                f"未完成：{milestone.undone}。"
            )
        return None


def _render_recent_history(
    history: list[tuple[Observation | ScenarioObservation, ScenarioAction, ToolResult]],
) -> str | None:
    if not history:
        return None
    values = []
    for observation, action, result in history:
        values.append(
            {
                "observation": observation.model_dump(mode="json"),
                "action": action.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            }
        )
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _public_action_violation(action: ScenarioAction, observation: Observation) -> str | None:
    """Check only arguments that are directly decidable from public Observation."""

    data = action.model_dump(mode="json")
    tool = data["tool"]
    if tool == "move" and data["destination"] not in observation.available_exits:
        return (
            "公开动作校验：move 的 destination 不在 available_exits 中；"
            "请只选择当前 Observation 提供的出口。"
        )
    if tool in {"inspect", "read_terminal"} and data["target"] not in observation.visible_objects:
        return "公开动作校验：目标不在 visible_objects 中；请只操作当前 Observation 可见目标。"
    if tool == "pickup" and data["item"] not in observation.visible_objects:
        return (
            "公开动作校验：pickup 的 item 不在 visible_objects 中；"
            "请先到达目标所在位置或发现该物品。"
        )
    if tool == "use":
        if data["target"] not in observation.visible_objects:
            return "公开动作校验：use 的 target 不在 visible_objects 中。"
        if data["target"] != "escape_pod" and data["item"] not in observation.inventory:
            return "公开动作校验：维修动作的 item 不在 inventory 中。"
    if tool == "interact":
        valid_choices = {
            option.target: option.choices
            for option in getattr(observation, "available_interactions", ())
        }
        if data["target"] not in observation.visible_objects:
            return "公开动作校验：交互目标当前不可见。"
        if data["choice"] not in valid_choices.get(data["target"], ()):
            return "公开动作校验：交互选择不在当前公开选项中。"
    if tool == "submit" and data["target"] not in observation.visible_objects:
        return "公开动作校验：提交目标当前不可见。"
    return None
