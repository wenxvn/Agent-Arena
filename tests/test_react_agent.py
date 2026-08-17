from __future__ import annotations

from agent_arena.agents import ReactAgent
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_react_prompt_requires_flat_action_arguments_for_every_tool() -> None:
    provider = FakeDecisionProvider([{}])
    agent = ReactAgent(provider)

    agent.request(SpaceshipEscapeEnvironment().observe(), correction=False)

    prompt = provider.calls[0].request.system_prompt
    assert "绝对不要使用 args、arguments、parameters" in prompt
    assert '"action":{"tool":"move","destination":"corridor"}' in prompt
    assert '"action":{"tool":"inspect","target":"storage_crate"}' in prompt
    assert '"action":{"tool":"pickup","item":"screwdriver"}' in prompt
    assert '"action":{"tool":"use","item":"screwdriver","target":"reactor_panel"}' in prompt
    assert '"action":{"tool":"read_terminal","target":"diagnostic_terminal"}' in prompt
