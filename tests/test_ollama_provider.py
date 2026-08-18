from __future__ import annotations

import io
import json
from typing import Any

from agent_arena.arena.models import Observation
from agent_arena.config import RuntimeSettings
from agent_arena.llm.ollama import OllamaDecisionProvider
from agent_arena.llm.protocol import DecisionRequest


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> io.BytesIO:
        return self._body

    def __exit__(self, *args: object) -> None:
        self._body.close()


def test_ollama_decision_uses_native_non_thinking_json_request(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, *, timeout: int) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "model": "test-model",
                "message": {
                    "content": json.dumps(
                        {
                            "decision_reason": "前往出口继续探索。",
                            "action": {"tool": "move", "destination": "corridor"},
                        }
                    )
                },
                "prompt_eval_count": 12,
                "eval_count": 8,
            }
        )

    monkeypatch.setattr("agent_arena.llm.ollama.urlopen", fake_urlopen)
    settings = RuntimeSettings.load(
        {
            "provider": "ollama",
            "ollama_base_url": "http://localhost:11434/v1",
            "ollama_model": "test-model",
            "ollama_max_output_tokens": 64,
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

    response = OllamaDecisionProvider(settings).decide(
        DecisionRequest(observation=observation, system_prompt="按格式返回动作。", correction=False)
    )

    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["timeout"] == settings.request_timeout_seconds
    assert captured["payload"]["think"] is False
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"] == {"temperature": 0, "num_predict": 64}
    assert captured["payload"]["format"]["required"] == ["decision_reason", "action"]
    assert captured["payload"]["messages"][-1]["content"].startswith("当前观察：")
    assert response.candidate == {
        "decision_reason": "前往出口继续探索。",
        "action": {"tool": "move", "destination": "corridor"},
    }
    assert response.input_tokens == 12
    assert response.output_tokens == 8
