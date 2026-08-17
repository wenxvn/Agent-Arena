from __future__ import annotations

from agent_arena.agents.memory import MemoryAgent, MemoryReducer
from agent_arena.arena import ToolReason, ToolResult, ToolStatus
from agent_arena.arena.models import LookAction
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_memory_reducer_tracks_public_failure_and_resolves_power_question() -> None:
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    reducer = MemoryReducer()
    state = reducer.initialize(observation)
    action = LookAction(tool="look")
    rejected = ToolResult(
        status=ToolStatus.REJECTED, reason=ToolReason.NO_POWER, summary="OPENAI_API_KEY=hidden"
    )

    state = reducer.apply(state, action, rejected, observation)

    assert state.failed_actions[0].result_summary == "OPENAI_API_KEY=[REDACTED]"
    assert state.open_questions[0].key == "main_power"
    restored = ToolResult(
        status=ToolStatus.SUCCESS, reason=ToolReason.POWER_RESTORED, summary="主电源已恢复。"
    )
    state = reducer.apply(state, action, restored, observation)
    assert state.open_questions == ()


def test_memory_agent_sends_separate_sanitized_memory_data_and_clears_on_finish() -> None:
    provider = FakeDecisionProvider([{}])
    agent = MemoryAgent(provider)
    observation = SpaceshipEscapeEnvironment().observe()

    agent.reset(observation)
    agent.request(observation, correction=False)

    request = provider.calls[0].request
    assert request.system_prompt == agent._prompt
    assert request.memory_data is not None
    assert "Agent Memory" in request.memory_data
    agent.finish("success")
    try:
        agent.request(observation, correction=False)
    except RuntimeError:
        pass
    else:
        raise AssertionError("finished agent must not reuse memory")
