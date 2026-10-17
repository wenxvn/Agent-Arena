"""V8 公开 prompt：动作契约、交互词表与泄露边界。"""

from __future__ import annotations

from agent_arena.v8.prompts import system_prompt, user_prompt, vocabulary
from agent_arena.worlds.scenario_v8 import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action


def test_vocabulary_lists_public_interaction_names() -> None:
    prompt = system_prompt(create_environment("MAP-01"), decision_budget=30)
    assert "oxygen_relay/start_support" in prompt
    assert "bridge_console/confirm_repair" in prompt
    assert "连续断供超过 3 tick" in prompt
    assert "可用动作名" in prompt


def test_vocabulary_covers_numeric_control_maps() -> None:
    environment = create_environment("MAP-19")
    text = vocabulary(environment)
    assert "set_cooling" in text
    assert "read_temperature" in text
    assert "map19." not in system_prompt(environment, decision_budget=30)


def test_map22_memory_fact_schema_is_public() -> None:
    prompt = system_prompt(create_environment("MAP-22"), decision_budget=30)
    assert "traversed_edge_page" in prompt
    assert "arrival_reverse_bearing" in prompt
    assert "write_memory" in prompt


def test_vocabulary_does_not_leak_private_state() -> None:
    environment = create_environment("MAP-02")
    environment.step(V8Action.model_validate({"tool": "wait", "turns": 1}, strict=True))
    observation = environment.observe()
    prompt = system_prompt(environment, decision_budget=38)
    user = user_prompt(
        environment,
        observation=observation,
        history=[],
        decision_index=1,
        decision_budget=38,
    )
    assert "crew_pressure_ticks" in user
    for text in (prompt, user):
        assert "true_leak" not in text
        assert "judge_state" not in text
        assert "map02." not in text
