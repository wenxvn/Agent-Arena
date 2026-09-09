"""Public-data plan monitoring for PlanningAgent v1."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from agent_arena.arena import Action, Observation, ToolResult, ToolStatus
from agent_arena.planning.models import PlanSignal, PlanState


class PublicProgressState(BaseModel):
    """A bounded public state projection used for progress comparisons."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    current_room: str
    visible_objects: tuple[str, ...]
    available_exits: tuple[str, ...]
    inventory: tuple[str, ...]
    last_result_status: str | None = None
    last_result_reason: str | None = None


def public_progress_state(
    observation: Observation, result: ToolResult | None = None
) -> PublicProgressState:
    """Project only public observation/result fields; never read WorldState."""

    public_result = result or observation.last_action_result
    return PublicProgressState(
        current_room=observation.current_room,
        visible_objects=tuple(observation.visible_objects),
        available_exits=tuple(observation.available_exits),
        inventory=tuple(observation.inventory),
        last_result_status=public_result.status.value if public_result else None,
        last_result_reason=public_result.reason.value if public_result else None,
    )


@dataclass
class PlanMonitor:
    """Detect public completion, repeated failure, and sustained no-progress."""

    no_progress_threshold: int = 3
    _no_progress_count: int = 0
    _failure_key: tuple[object, ...] | None = None
    _failure_count: int = 0

    def reset(self) -> None:
        self._no_progress_count = 0
        self._failure_key = None
        self._failure_count = 0

    def evaluate(
        self,
        plan: PlanState,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> PlanSignal:
        """Return a signal based solely on public before/after data."""

        if _criteria_satisfied(plan, after, result):
            self.reset()
            return PlanSignal(status="subgoal_completed", reason="success_criteria_met")

        before_public = public_progress_state(before)
        after_public = public_progress_state(after, result)
        before_persistent = _persistent_key(before_public)
        after_persistent = _persistent_key(after_public)
        failure_key = (
            after_persistent,
            action.model_dump_json(),
            result.status.value,
            result.reason.value,
        )

        if result.status is ToolStatus.REJECTED:
            if failure_key == self._failure_key:
                self._failure_count += 1
            else:
                self._failure_key = failure_key
                self._failure_count = 1
            if self._failure_count >= 2:
                self._no_progress_count = 0
                return PlanSignal(status="repeated_failure", reason="repeated_failure")
        else:
            self._failure_key = None
            self._failure_count = 0

        if before_persistent == after_persistent:
            self._no_progress_count += 1
        else:
            self._no_progress_count = 0

        if self._no_progress_count >= self.no_progress_threshold:
            return PlanSignal(status="no_progress", reason="no_progress")
        return PlanSignal(status="continue")


def _persistent_key(state: PublicProgressState) -> tuple[object, ...]:
    return (
        state.current_room,
        state.visible_objects,
        state.available_exits,
        state.inventory,
    )


def _criteria_satisfied(plan: PlanState, observation: Observation, result: ToolResult) -> bool:
    """Match only evidence patterns that can be proved from public data.

    v1 deliberately supports a small, transparent vocabulary. Unknown criteria
    are not guessed as complete; they cause the plan to continue until a new
    public observation or result makes the criterion recognizable.
    """

    return all(
        _criterion_satisfied(criteria, observation, result) for criteria in plan.success_criteria
    )


def _criterion_satisfied(criteria: str, observation: Observation, result: ToolResult) -> bool:
    normalized = criteria.lower().replace(" ", "")
    if "toolresult" in normalized or "工具结果" in normalized or "公开结果" in normalized:
        if "success" in normalized or "成功" in normalized:
            return result.status is ToolStatus.SUCCESS
        for reason in (result.reason.value, result.reason.value.replace("_", "")):
            if reason.lower() in normalized:
                return True

    public_values = {
        observation.current_room,
        *observation.visible_objects,
        *observation.available_exits,
        *observation.inventory,
        result.reason.value,
        result.summary,
    }
    if "inventory" in normalized or "背包" in normalized:
        tokens = _criterion_tokens(criteria)
        return bool(tokens) and all(token in observation.inventory for token in tokens)
    if "visible_objects" in normalized or "可见对象" in normalized:
        tokens = _criterion_tokens(criteria)
        return bool(tokens) and all(token in observation.visible_objects for token in tokens)
    if "available_exits" in normalized or "出口" in normalized:
        tokens = _criterion_tokens(criteria)
        return bool(tokens) and all(token in observation.available_exits for token in tokens)
    if "room" in normalized or "房间" in normalized or "到达" in normalized:
        return (
            observation.current_room.lower() in normalized
            or observation.current_room in criteria
        )

    tokens = _criterion_tokens(criteria)
    return bool(tokens) and all(
        any(token.lower() in value.lower() for value in public_values) for token in tokens
    )


def _ascii_tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)))


def _criterion_tokens(value: str) -> tuple[str, ...]:
    ignored = {
        "inventory",
        "visible_objects",
        "available_exits",
        "contains",
        "contain",
        "the",
        "is",
        "in",
        "and",
        "reason",
    }
    return tuple(token for token in _ascii_tokens(value) if token.lower() not in ignored)
