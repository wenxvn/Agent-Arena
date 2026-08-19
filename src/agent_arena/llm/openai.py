"""OpenAI Responses API adapter for compatible remote providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import sleep

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from pydantic import BaseModel

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError, ModelVerificationError
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse


@dataclass(frozen=True)
class ModelVerification:
    """Allowlisted result emitted by the model verification command."""

    model: str
    text: str


class OpenAIModelVerifier:
    """Verify a Responses API model without retaining the full provider response."""

    def __init__(self, settings: RuntimeSettings) -> None:
        base_url, api_key = settings.require_openai()
        self._settings = settings
        self._client = OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    def verify(self) -> ModelVerification:
        try:
            response = self._client.responses.create(
                model=self._settings.model_name,
                input="请只回复：Agent Arena 模型配置验证成功。",
                max_output_tokens=32,
                store=False,
            )
        except Exception as exc:
            raise ModelVerificationError("OpenAI model verification request failed.") from exc
        if not response.output_text:
            raise ModelVerificationError("OpenAI model verification returned no final text.")
        return ModelVerification(
            model=response.model or self._settings.model_name,
            text=response.output_text,
        )


class OpenAIDecisionProvider:
    """Request one schema-constrained decision through the Responses API."""

    def __init__(self, settings: RuntimeSettings) -> None:
        base_url, api_key = settings.require_openai()
        self._settings = settings
        self._client = OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
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
                    raise DecisionProviderError("OpenAI request failed.") from exc
                sleep(self._settings.retry_backoff_seconds[attempt])
            except DecisionProviderError:
                raise
            except Exception as exc:
                raise DecisionProviderError("OpenAI request failed.") from exc

        raise AssertionError("Retry loop must return or raise.")

    def _request_once(self, request: DecisionRequest) -> ProviderResponse:
        if not isinstance(request.observation, BaseModel):
            raise DecisionProviderError("OpenAI provider requires a structured observation.")
        correction_instruction = (
            "上一条输出不符合格式。请只返回规定的 JSON 结构。"
            if request.correction
            else "请只返回规定的 JSON 结构。"
        )
        input_parts = []
        if request.memory_data:
            input_parts.append(request.memory_data)
        input_parts.append(f"当前观察：{request.observation.model_dump_json()}")
        if request.runtime_feedback:
            input_parts.append(f"运行时提醒（仅来自公开轨迹）：{request.runtime_feedback}")
        input_parts.append(correction_instruction)
        response = self._client.responses.create(
            model=self._settings.model_name,
            instructions=request.system_prompt,
            input="\n".join(input_parts),
            temperature=0,
            text={"format": {"type": "json_object"}},
            store=False,
        )
        if not response.output_text:
            raise DecisionProviderError("OpenAI provider returned no decision.")
        try:
            usage = response.usage
            return ProviderResponse(
                candidate=json.loads(response.output_text),
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
            )
        except json.JSONDecodeError as exc:
            raise DecisionProviderError("OpenAI provider returned malformed JSON.") from exc
