from __future__ import annotations

from agent_arena.agents import ReactAgent
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_react_prompt_requires_flat_action_arguments_for_every_tool() -> None:
    provider = FakeDecisionProvider([{}])
    agent = ReactAgent(provider)

    agent.request(SpaceshipEscapeEnvironment().observe(), correction=False)

    prompt = provider.calls[0].request.system_prompt
    assert "禁止使用 args、arguments 或 parameters 包装" in prompt
    assert "move 的 destination 必须在 available_exits 中" in prompt
    assert "Agent Memory" in prompt
    assert "运行时提醒" in prompt
    assert "优先处理新目标" in prompt
    assert "读取终端使用 read_terminal" in prompt
    assert '"action":{"tool":"move","destination":"corridor"}' in prompt
    assert '"action":{"tool":"inspect","target":"storage_crate"}' in prompt
    assert '"action":{"tool":"pickup","item":"screwdriver"}' in prompt
    assert '"action":{"tool":"use","item":"screwdriver","target":"reactor_panel"}' in prompt
