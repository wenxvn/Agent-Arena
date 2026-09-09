from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_arena.agents import PlanningAgent
from agent_arena.arena import ToolReason, WorldState, action_adapter
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def planner_response(criteria: str = "ToolResult status is success") -> dict[str, object]:
    return {
        "decision_reason": "根据公开证据建立当前子目标。",
        "current_subgoal": "获得一个公开成功结果",
        "success_criteria": [criteria],
        "known_constraints": ["只能使用公开 Observation"],
        "relevant_resources": [],
        "unresolved_questions": [],
    }


def action_response() -> dict[str, object]:
    return {
        "decision_reason": "执行能够获得公开结果的动作。",
        "action": {"tool": "look"},
    }


def test_planner_and_executor_are_separate_provider_requests() -> None:
    provider = FakeDecisionProvider([planner_response(), action_response()])
    agent = PlanningAgent(provider)
    observation = SpaceshipEscapeEnvironment().reset(0)
    agent.reset(observation)

    response = agent.request(observation, correction=False)

    assert response.candidate == action_response()
    assert [call.request.output_contract for call in provider.calls] == ["planner", "action"]
    assert provider.calls[0].request.plan_data is None
    assert provider.calls[1].request.plan_data is not None
    assert not isinstance(provider.calls[0].request.observation, WorldState)
    assert agent.plan_state is not None
    assert agent.plan_state.current_subgoal == "获得一个公开成功结果"


def test_executor_cannot_modify_plan_state_and_reset_clears_episode_plan() -> None:
    provider = FakeDecisionProvider([planner_response(), action_response()])
    agent = PlanningAgent(provider)
    observation = SpaceshipEscapeEnvironment().reset(0)
    agent.reset(observation)
    agent.request(observation, correction=False)
    before = agent.plan_state

    assert before is not None
    agent.finish("step_limit")
    assert agent.plan_state is None
    with pytest.raises(RuntimeError, match="reset"):
        agent.request(observation, correction=False)


def test_planner_replans_after_a_completed_public_criterion() -> None:
    provider = FakeDecisionProvider(
        [
            planner_response("ToolResult reason is looked"),
            action_response(),
            planner_response("ToolResult reason is moved"),
            action_response(),
        ]
    )
    agent = PlanningAgent(provider)
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    agent.reset(observation)

    agent.request(observation, correction=False)
    action = action_adapter.validate_python({"tool": "look"})
    result, after = environment.step(action)
    assert result.reason is ToolReason.LOOKED
    agent.observe(action, result, after)
    assert agent.planning_metadata.subgoal_completed is True

    agent.request(after, correction=False)
    assert [call.request.output_contract for call in provider.calls] == [
        "planner",
        "action",
        "planner",
        "action",
    ]
    assert provider.calls[2].request.runtime_feedback == "重新规划原因：success_criteria_met"


def test_planner_observe_requires_public_tool_result() -> None:
    provider = FakeDecisionProvider([planner_response(), action_response()])
    agent = PlanningAgent(provider)
    observation = SpaceshipEscapeEnvironment().reset(0)
    agent.reset(observation)
    agent.request(observation, correction=False)

    with pytest.raises(TypeError, match="ToolResult"):
        agent.observe(action_adapter.validate_python({"tool": "look"}), object(), observation)


def test_planner_result_contract_does_not_accept_hidden_state() -> None:
    provider = FakeDecisionProvider(
        [
            {**planner_response(), "world_state": "hidden"},
            action_response(),
        ]
    )
    agent = PlanningAgent(provider)
    observation = SpaceshipEscapeEnvironment().reset(0)
    agent.reset(observation)

    with pytest.raises(ValidationError):
        agent.request(observation, correction=False)
