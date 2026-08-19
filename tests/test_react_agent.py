from __future__ import annotations

from agent_arena.agents import ReactAgent
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_react_autonomous_prompt_contains_only_general_action_rules() -> None:
    provider = FakeDecisionProvider([{}])
    agent = ReactAgent(provider)

    agent.request(SpaceshipEscapeEnvironment().observe(), correction=False)

    prompt = provider.calls[0].request.system_prompt
    assert agent.prompt_version == "react_v12_autonomous"
    assert "禁止使用 args、arguments 或 parameters 包装" in prompt
    assert "available_exits" in prompt
    assert "visible_objects" in prompt
    assert "把失败 ToolResult 当作事实" in prompt
    assert "优先选择能够获得新信息" in prompt
    assert "storage_room" not in prompt
    assert "screwdriver" not in prompt
    assert "reactor_panel" not in prompt
    assert "ALPHA-731" not in prompt
