from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from agent_arena.arena.models import Observation
from agent_arena.config import RuntimeSettings
from agent_arena.llm.openai import OpenAIDecisionProvider, OpenAIModelVerifier
from agent_arena.llm.protocol import DecisionRequest


class _FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="relay-model",
            output_text=json.dumps(
                {
                    "decision_reason": "前往走廊继续探索。",
                    "action": {"tool": "move", "destination": "corridor"},
                }
            ),
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        )


class _FakeClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.responses = _FakeResponses()


def test_openai_decision_uses_responses_api_with_json_output(monkeypatch) -> None:
    client = _FakeClient()

    def create_client(**kwargs: Any) -> _FakeClient:
        client.kwargs = kwargs
        return client

    monkeypatch.setattr("agent_arena.llm.openai.OpenAI", create_client)
    settings = RuntimeSettings.load(
        {
            "provider": "openai",
            "base_url": "https://relay.example/v1",
            "openai_api_key": "test-key",
            "model_name": "test-model",
        },
        env_file=None,
    )
    observation = Observation(
        current_room="bridge",
        description="控制台前方有一条通道。",
        visible_objects=("console",),
        available_exits=("corridor",),
        inventory=(),
        last_action_result=None,
    )

    response = OpenAIDecisionProvider(settings).decide(
        DecisionRequest(
            observation=observation,
            system_prompt="按格式返回动作。",
            correction=False,
            memory_data="公开记忆：无。",
            runtime_feedback="不要重复失败动作。",
        )
    )

    call = client.responses.calls[0]
    assert client.kwargs["base_url"] == "https://relay.example/v1"
    assert call["model"] == "test-model"
    assert call["instructions"] == "按格式返回动作。"
    assert call["text"] == {"format": {"type": "json_object"}}
    assert call["store"] is False
    assert "公开记忆：无。" in call["input"]
    assert "运行时提醒（仅来自公开轨迹）：不要重复失败动作。" in call["input"]
    assert response.candidate == {
        "decision_reason": "前往走廊继续探索。",
        "action": {"tool": "move", "destination": "corridor"},
    }
    assert response.input_tokens == 12
    assert response.output_tokens == 8


def test_openai_verifier_uses_responses_api(monkeypatch) -> None:
    client = _FakeClient()

    def create_client(**kwargs: Any) -> _FakeClient:
        client.kwargs = kwargs
        return client

    monkeypatch.setattr("agent_arena.llm.openai.OpenAI", create_client)
    settings = RuntimeSettings.load(
        {
            "provider": "openai",
            "base_url": "https://relay.example/v1",
            "openai_api_key": "test-key",
            "model_name": "test-model",
        },
        env_file=None,
    )

    verification = OpenAIModelVerifier(settings).verify()

    call = client.responses.calls[0]
    assert call["max_output_tokens"] == 32
    assert call["store"] is False
    assert verification.model == "relay-model"
