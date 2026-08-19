"""Bounded execution loop for one deterministic Agent Arena episode."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from pydantic import ValidationError

from agent_arena.agents.candidate import CandidateSelectionAgent, candidate_selection_adapter
from agent_arena.agents.react import AgentDecision, ReactAgent, agent_decision_adapter
from agent_arena.arena import (
    Action,
    Environment,
    Observation,
    ToolReason,
    ToolResult,
    ToolStatus,
    action_adapter,
)
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation.loop import PublicLoopDetector
from agent_arena.evaluation.trace import (
    EpisodeOutcome,
    EpisodeTrace,
    EpisodeTraceHeader,
    ExperimentProvenance,
    InvalidOutputReason,
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
                reasoning_effort=self._settings.reasoning_effort,
                response_format=self._settings.response_format,
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
                public_phase_context_enabled=self._enable_public_phase_context,
                candidate_selection_enabled=self._enable_candidate_selection,
                memory_schema_version=(
                    "memory_v1" if self._agent.name in {"memory", "planner_assisted"} else None
                ),
                memory_renderer_version=(
                    "memory_v1" if self._agent.name in {"memory", "planner_assisted"} else None
                ),
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
        phase_tracker = PublicPhaseTracker()
        phase_tracker.initialize(observation)
        candidate_tracker = PublicCandidateTracker()
        candidate_tracker.initialize(observation)
        runtime_feedback = (
            _public_action_hints(observation) if self._enable_public_action_hints else None
        )
        if self._enable_concrete_action_candidates:
            runtime_feedback = _join_feedback(
                runtime_feedback, _concrete_action_candidates(observation)
            )
        if self._enable_public_phase_context:
            runtime_feedback = _join_feedback(runtime_feedback, phase_tracker.render(observation))
        recent_history: list[tuple[Observation, Action, ToolResult]] = []

        while decision_attempts < self._settings.step_limit:
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
                        observation=observation,
                        decision_reason=decision.decision_reason,
                        action=decision.action,
                        latency_ms=latency_ms,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        runtime_feedback=guard_error,
                        summary="公开动作校验拒绝了该 Action；环境未执行。",
                    )
                    steps.append(guarded_step)
                    if self._on_step_complete:
                        self._on_step_complete(guarded_step)
                    continue
            result, observation = self._environment.step(decision.action)
            self._agent.observe(decision.action, result, observation)
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
            if self._enable_public_phase_context:
                feedback_parts.append(phase_tracker.render(observation))
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
        invalid_output_reason: str | None,
        recent_history: str | None,
        candidates: PublicCandidateSet,
    ) -> tuple[
        AgentDecision | None,
        int,
        bool,
        int | None,
        int | None,
        InvalidOutputReason | None,
    ]:
        started_at = perf_counter()
        try:
            response = self._agent.request(
                observation,
                correction=correction,
                runtime_feedback=runtime_feedback,
                invalid_output_reason=invalid_output_reason,
                recent_history=recent_history,
            )
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
    ) -> AgentDecision:
        if not self._enable_candidate_selection:
            return agent_decision_adapter.validate_python(response.candidate)
        if not isinstance(self._agent, CandidateSelectionAgent):
            raise ValueError("Candidate selection requires CandidateSelectionAgent.")
        selection = candidate_selection_adapter.validate_python(response.candidate)
        action = candidates.resolve(selection.candidate_id)
        if action is None:
            raise ValueError("Candidate id is not in the current public candidate set.")
        return AgentDecision(decision_reason=selection.decision_reason, action=action)

    @staticmethod
    def _invalid_event(
        observation: Observation,
        *,
        correction: bool,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        invalid_output_reason: InvalidOutputReason | None,
    ) -> StepTrace:
        return StepTrace(
            event=TraceEvent.ACTION_INVALID,
            observation=observation,
            correction=correction,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            summary="模型输出不符合决策格式。",
            invalid_output_reason=invalid_output_reason,
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
    }
    if tool not in required_arguments:
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
        action: Action,
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


def _action_identity(action: Action) -> str:
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


def _render_action(action: Action) -> str:
    values = action.model_dump(mode="json")
    tool = values.pop("tool")
    arguments = ",".join(f"{name}={value}" for name, value in values.items())
    return f"{tool}({arguments})" if arguments else f"{tool}()"


@dataclass
class PublicPhaseTracker:
    """Track only public milestone results for the optional A6 context."""

    _panel_open: bool = False
    _power_restored: bool = False
    _authorization_code_read: bool = False

    def initialize(self, observation: Observation) -> None:
        del observation
        self._panel_open = False
        self._power_restored = False
        self._authorization_code_read = False

    def observe(self, result: ToolResult) -> None:
        self._panel_open = self._panel_open or result.reason is ToolReason.PANEL_OPENED
        self._power_restored = self._power_restored or result.reason is ToolReason.POWER_RESTORED
        self._authorization_code_read = (
            self._authorization_code_read or result.reason is ToolReason.CODE_READ
        )

    def render(self, observation: Observation) -> str:
        tools = {"screwdriver", "replacement_fuse"}
        missing_tools = tools - set(observation.inventory)
        if missing_tools:
            missing = "、".join(sorted(missing_tools))
            return f"当前公开阶段：收集修理工具。已完成：无。未完成：获得 {missing}。"
        if not self._panel_open:
            return "当前公开阶段：恢复主电源。已完成：修理工具。未完成：打开反应堆面板。"
        if not self._power_restored:
            return "当前公开阶段：恢复主电源。已完成：修理工具和反应堆面板。未完成：恢复主电源。"
        if not self._authorization_code_read:
            return "当前公开阶段：读取逃生授权码。已完成：修理工具和主电源。未完成：读取授权码。"
        return "当前公开阶段：启动逃生舱。已完成：修理工具、主电源和授权码。未完成：启动逃生舱。"


def _render_recent_history(history: list[tuple[Observation, Action, ToolResult]]) -> str | None:
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


def _public_action_violation(action: Action, observation: Observation) -> str | None:
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
    return None
