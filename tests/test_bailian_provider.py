from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from agent_arena.arena.models import Observation
from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import BailianDecisionProvider
from agent_arena.llm.protocol import DecisionRequest


def test_bailian_decision_passes_per_request_output_cap(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create_completion))

        def create_completion(self, **kwargs: Any) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "decision_reason": "查看。",
                                    "action": {"tool": "look"},
                                }
                            )
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8),
            )

    monkeypatch.setattr("agent_arena.llm.bailian.OpenAI", FakeOpenAI)
    settings = RuntimeSettings.load(
        {
            "provider": "bailian",
            "base_url": "https://bailian.example/v1",
            "dashscope_api_key": "test-key",
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

    response = BailianDecisionProvider(settings).decide(
        DecisionRequest(
            observation=observation,
            system_prompt="按格式返回动作。",
            correction=False,
            max_output_tokens=64,
        )
    )

    assert captured["request"]["max_tokens"] == 64
    assert response.input_tokens == 12
    assert response.output_tokens == 8
