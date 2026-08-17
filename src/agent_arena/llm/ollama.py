"""Ollama's local OpenAI-compatible decision and verification adapters."""

from __future__ import annotations

import json
from time import sleep
from typing import Any, cast

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from pydantic import BaseModel

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError, ModelVerification, ModelVerificationError
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse


class OllamaModelVerifier:
    """Verify a locally installed Ollama model without using an API key."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings
        self._client = OpenAI(
            api_key="ollama",
            base_url=settings.ollama_base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    def verify(self) -> ModelVerification:
        try:
            response = self._client.chat.completions.create(
                model=self._settings.ollama_model,
                messages=[{"role": "user", "content": "请只回复：Agent Arena 模型配置验证成功。"}],
                temperature=0,
                max_tokens=32,
            )
        except Exception as exc:
            raise ModelVerificationError("Ollama model verification request failed.") from exc
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise ModelVerificationError("Ollama model verification returned no final text.")
        return ModelVerification(model=response.model or self._settings.ollama_model, text=text)


class OllamaDecisionProvider:
    """Request JSON decisions from a local Ollama model with bounded retries."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings
        self._client = OpenAI(
            api_key="ollama",
            base_url=settings.ollama_base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        for attempt in range(self._settings.retry_count + 1):
            try:
                return self._request_once(request)
            except (
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            ) as exc:
                if attempt == self._settings.retry_count:
                    raise DecisionProviderError("Ollama request failed.") from exc
                sleep(self._settings.retry_backoff_seconds[attempt])
            except DecisionProviderError:
                raise
            except Exception as exc:
                raise DecisionProviderError("Ollama request failed.") from exc
        raise AssertionError("Retry loop must return or raise.")

    def _request_once(self, request: DecisionRequest) -> ProviderResponse:
        if not isinstance(request.observation, BaseModel):
            raise DecisionProviderError("Ollama requires a structured observation.")
        correction_instruction = (
            "上一条输出不符合格式。请只返回规定的 JSON 结构。"
            if request.correction
            else "请只返回规定的 JSON 结构。"
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": request.system_prompt},
            {
                "role": "user",
                "content": (
                    f"当前观察：{request.observation.model_dump_json()}\n{correction_instruction}"
                ),
            },
        ]
        if request.memory_data:
            messages.append({"role": "user", "content": request.memory_data})
        response = self._client.chat.completions.create(
            model=self._settings.ollama_model,
            messages=cast(Any, messages),
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise DecisionProviderError("Ollama returned no decision.")
        try:
            usage = response.usage
            return ProviderResponse(
                candidate=json.loads(content),
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
            )
        except json.JSONDecodeError as exc:
            raise DecisionProviderError("Ollama returned malformed JSON.") from exc
