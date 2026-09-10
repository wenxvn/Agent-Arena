"""Structured and legacy success-criterion evaluation."""

from __future__ import annotations

import re
from collections.abc import Iterable

from agent_arena.arena import Observation, ToolResult, ToolStatus
from agent_arena.evaluation.public_facts import EpisodeKnowledge
from agent_arena.planning.models import SuccessCriterion

LegacyCriterion = str
Criterion = SuccessCriterion | LegacyCriterion


def criterion_satisfied(
    criterion: Criterion,
    observation: Observation,
    result: ToolResult | None,
    knowledge: EpisodeKnowledge,
) -> bool:
    """Evaluate a structured criterion, or safely adapt a v1 string criterion."""

    if isinstance(criterion, str):
        return _legacy_criterion_satisfied(criterion, observation, result)
    if criterion.criterion_type == "inventory_contains":
        return bool(criterion.target) and criterion.target in observation.inventory
    if criterion.criterion_type == "room_reached":
        return bool(criterion.target) and observation.current_room == criterion.target
    if criterion.criterion_type == "object_visible":
        return bool(criterion.target) and criterion.target in observation.visible_objects
    if criterion.criterion_type == "exit_available":
        return bool(criterion.target) and criterion.target in observation.available_exits
    if criterion.criterion_type == "tool_result_status":
        return (
            result is not None
            and bool(criterion.value)
            and result.status.value == criterion.value
        )
    if criterion.criterion_type == "tool_result_reason":
        return (
            result is not None
            and bool(criterion.value)
            and result.reason.value == criterion.value
        )
    if criterion.criterion_type == "public_fact":
        return any(
            (criterion.target is None or fact.subject == criterion.target)
            and (criterion.value is None or fact.value == criterion.value)
            for fact in knowledge.discovered_facts
        )
    return False


def all_criteria_satisfied(
    criteria: Iterable[Criterion],
    observation: Observation,
    result: ToolResult | None,
    knowledge: EpisodeKnowledge,
) -> bool:
    values = tuple(criteria)
    return bool(values) and all(
        criterion_satisfied(criterion, observation, result, knowledge) for criterion in values
    )


class LegacySuccessCriterionAdapter:
    """Compatibility adapter kept for v1 traces and v1 Planner output."""

    @staticmethod
    def adapt(value: str | SuccessCriterion) -> Criterion:
        return value


def _legacy_criterion_satisfied(
    criteria: str, observation: Observation, result: ToolResult | None
) -> bool:
    """Preserve the small transparent v1 vocabulary; never guess prose."""

    if result is None:
        return False
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
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)
    return tuple(token for token in tokens if token.lower() not in ignored)
