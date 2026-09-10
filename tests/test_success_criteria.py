from __future__ import annotations

import pytest

from agent_arena.arena import ToolReason, ToolResult, ToolStatus
from agent_arena.evaluation import EpisodeKnowledge, PublicFact
from agent_arena.planning import SuccessCriterion, criterion_satisfied
from agent_arena.worlds import SpaceshipEscapeEnvironment


@pytest.fixture()
def observation():
    environment = SpaceshipEscapeEnvironment()
    return environment.reset(0).model_copy(
        update={
            "current_room": "storage_room",
            "visible_objects": ("storage_crate", "screwdriver"),
            "available_exits": ("corridor",),
            "inventory": ("replacement_fuse",),
        }
    )


@pytest.mark.parametrize(
    ("criterion", "expected"),
    [
        (
            SuccessCriterion(
                criterion_type="inventory_contains",
                target="replacement_fuse",
                description="获得保险丝",
            ),
            True,
        ),
        (
            SuccessCriterion(
                criterion_type="room_reached",
                target="storage_room",
                description="到达储藏室",
            ),
            True,
        ),
        (
            SuccessCriterion(
                criterion_type="object_visible",
                target="screwdriver",
                description="看到螺丝刀",
            ),
            True,
        ),
        (
            SuccessCriterion(
                criterion_type="exit_available",
                target="corridor",
                description="出口可用",
            ),
            True,
        ),
    ],
)
def test_structured_observation_criteria(
    observation, criterion: SuccessCriterion, expected: bool
) -> None:
    assert criterion_satisfied(criterion, observation, None, EpisodeKnowledge()) is expected


def test_structured_observation_criteria_have_negative_results(observation) -> None:
    criteria = (
        SuccessCriterion(
            criterion_type="inventory_contains", target="screwdriver", description="获得螺丝刀"
        ),
        SuccessCriterion(
            criterion_type="room_reached", target="reactor_room", description="到达反应堆室"
        ),
        SuccessCriterion(
            criterion_type="object_visible", target="reactor_core", description="看到反应堆"
        ),
        SuccessCriterion(
            criterion_type="exit_available", target="reactor_room", description="出口可用"
        ),
    )

    assert all(
        not criterion_satisfied(criterion, observation, None, EpisodeKnowledge())
        for criterion in criteria
    )


@pytest.mark.parametrize(
    ("criterion_type", "value"),
    [("tool_result_status", "success"), ("tool_result_reason", "power_restored")],
)
def test_structured_tool_result_criteria(criterion_type: str, value: str, observation) -> None:
    result = ToolResult(
        status=ToolStatus.SUCCESS,
        reason=ToolReason.POWER_RESTORED,
        summary="主电源已恢复。",
    )
    criterion = SuccessCriterion(
        criterion_type=criterion_type, value=value, description="公开结果已确认"
    )

    assert criterion_satisfied(criterion, observation, result, EpisodeKnowledge()) is True
    negative = criterion.model_copy(update={"value": "wrong"})
    assert criterion_satisfied(negative, observation, result, EpisodeKnowledge()) is False


def test_public_fact_criterion_uses_episode_knowledge(observation) -> None:
    fact = PublicFact(subject="control_terminal", predicate="result", value="no_power")
    criterion = SuccessCriterion(
        criterion_type="public_fact",
        target="control_terminal",
        value="no_power",
        description="确认终端无电",
    )

    assert criterion_satisfied(
        criterion, observation, None, EpisodeKnowledge(discovered_facts=(fact,))
    ) is True
    assert criterion_satisfied(criterion, observation, None, EpisodeKnowledge()) is False
