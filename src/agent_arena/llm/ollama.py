"""Ollama native API adapters with JSON-constrained, non-thinking decisions."""

from __future__ import annotations

import json
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError, ModelVerification, ModelVerificationError
from agent_arena.llm.protocol import (
    DecisionRequest,
    ProviderResponse,
    candidate_selection_response_schema,
)


class _OllamaClient:
    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": self._settings.ollama_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "format": response_schema,
            "options": {
                "temperature": 0,
                "num_predict": self._settings.ollama_max_output_tokens,
            },
        }
        for attempt in range(self._settings.retry_count + 1):
            try:
                request = Request(
                    f"{self._settings.ollama_native_base_url}/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                    parsed = json.load(response)
                if not isinstance(parsed, dict):
                    raise DecisionProviderError("Ollama returned an invalid response.")
                return parsed
            except HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise DecisionProviderError("Ollama request failed.") from exc
            except (URLError, OSError, TimeoutError):
                pass
            if attempt == self._settings.retry_count:
                raise DecisionProviderError("Ollama request failed.")
            sleep(self._settings.retry_backoff_seconds[attempt])
        raise AssertionError("Retry loop must return or raise.")


class OllamaModelVerifier:
    """Verify a locally installed Ollama model through the native JSON API."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings
        self._client = _OllamaClient(settings)

    def verify(self) -> ModelVerification:
        try:
            response = self._client.chat(
                [
                    {
                        "role": "system",
                        "content": "只返回 JSON 对象，格式为 {\"text\":\"...\"}。",
                    },
                    {
                        "role": "user",
                        "content": "text 的值必须是：Agent Arena 模型配置验证成功。",
                    },
                ],
                response_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["text"],
                    "properties": {"text": {"type": "string"}},
                },
            )
            text = _json_content(response).get("text")
        except (DecisionProviderError, ValueError, TypeError) as exc:
            raise ModelVerificationError("Ollama model verification request failed.") from exc
        if not isinstance(text, str) or not text:
            raise ModelVerificationError("Ollama model verification returned no final text.")
        model = response.get("model") or self._settings.ollama_model
        return ModelVerification(model=model, text=text)


class OllamaDecisionProvider:
    """Request JSON decisions from Ollama without generating model reasoning."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self._client = _OllamaClient(settings)

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        correction_instruction = (
            "上一条输出不符合格式。请只返回规定的 JSON 结构。"
            if request.correction
            else "请只返回规定的 JSON 结构。"
        )
        messages = [{"role": "system", "content": request.system_prompt}]
        if request.memory_data:
            messages.append({"role": "user", "content": request.memory_data})
        request_content = f"当前观察：{_observation_json(request.observation)}\n"
        if request.output_contract == "candidate_selection":
            request_content += (
                '输出必须是 {"decision_reason":"...","candidate_id":"aN"}，'
                "candidate_id 必须来自当前公开候选列表。\n"
            )
        if request.runtime_feedback:
            request_content += f"运行时提醒（仅来自公开轨迹）：{request.runtime_feedback}\n"
        if request.recent_history:
            request_content += f"最近公开轨迹（仅供参考）：{request.recent_history}\n"
        request_content += correction_instruction
        messages.append({"role": "user", "content": request_content})
        schema = (
            candidate_selection_response_schema()
            if request.output_contract == "candidate_selection"
            else ACTION_RESPONSE_SCHEMA
        )
        response = self._client.chat(messages, response_schema=schema)
        response_content = _json_content(response)
        return ProviderResponse(
            candidate=response_content,
            input_tokens=_non_negative_int(response.get("prompt_eval_count")),
            output_tokens=_non_negative_int(response.get("eval_count")),
        )


def _observation_json(observation: object) -> str:
    model_dump_json = getattr(observation, "model_dump_json", None)
    if not callable(model_dump_json):
        raise DecisionProviderError("Ollama requires a structured observation.")
    value = model_dump_json()
    if not isinstance(value, str):
        raise DecisionProviderError("Ollama requires a structured observation.")
    return value


def _json_content(response: dict[str, Any]) -> dict[str, Any]:
    message = response.get("message")
    if not isinstance(message, dict):
        raise DecisionProviderError("Ollama returned no message.")
    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise DecisionProviderError("Ollama returned no final content.")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise DecisionProviderError("Ollama returned non-object JSON.")
    return parsed


def _non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


ACTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision_reason", "action"],
    "properties": {
        "decision_reason": {"type": "string"},
        "action": {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool"],
                    "properties": {"tool": {"const": "look"}},
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "destination"],
                    "properties": {
                        "tool": {"const": "move"},
                        "destination": {"type": "string"},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "target"],
                    "properties": {
                        "tool": {"enum": ["inspect", "read_terminal"]},
                        "target": {"type": "string"},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "item"],
                    "properties": {
                        "tool": {"const": "pickup"},
                        "item": {"type": "string"},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tool", "item", "target"],
                    "properties": {
                        "tool": {"const": "use"},
                        "item": {"type": "string"},
                        "target": {"type": "string"},
                    },
                },
            ]
        },
    },
}
