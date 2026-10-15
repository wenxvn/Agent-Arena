"""OpenAI Responses API adapter for compatible remote providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import sleep
from typing import Any, cast
from urllib.parse import urlparse

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from pydantic import BaseModel

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError, ModelVerificationError
from agent_arena.llm.protocol import (
    DecisionRequest,
    ProviderResponse,
    candidate_selection_response_schema,
    decision_response_schema_strict,
    planner_response_schema_strict,
)


def _session_headers(settings: RuntimeSettings) -> dict[str, str]:
    """Keep the gateway session header away from the direct Xiaomi API."""
    if settings.base_url and urlparse(settings.base_url).hostname == "api.xiaomimimo.com":
        return {}
    return {"x-opencode-session": settings.openai_session_id}


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
            default_headers=_session_headers(settings),
        )

    def verify(self) -> ModelVerification:
        try:
            response = self._client.responses.create(
                model=self._settings.model_name,
                input="请只回复：Agent Arena 模型配置验证成功。",
                max_output_tokens=1024,
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
            default_headers=_session_headers(settings),
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
                if request.action_contract_version == "scenario_v4":
                    raise DecisionProviderError(
                        "OpenAI-compatible request outcome is unconfirmed.",
                        error_category=type(exc).__name__,
                        retryable=False,
                        unknown_spend=True,
                    ) from exc
                if attempt == self._settings.retry_count:
                    raise DecisionProviderError(
                        "OpenAI request failed.",
                        error_category=type(exc).__name__,
                        retryable=True,
                        unknown_spend=False,
                    ) from exc
                sleep(self._settings.retry_backoff_seconds[attempt])
            except DecisionProviderError:
                raise
            except Exception as exc:
                raise DecisionProviderError("OpenAI request failed.") from exc

        raise AssertionError("Retry loop must return or raise.")

    def _request_once(self, request: DecisionRequest) -> ProviderResponse:
        if not isinstance(request.observation, BaseModel):
            raise DecisionProviderError("OpenAI provider requires a structured observation.")
        correction_instruction = _correction_instruction(request)
        input_parts = []
        if request.memory_data:
            input_parts.append(request.memory_data)
        input_parts.append(f"当前观察：{request.observation.model_dump_json()}")
        if request.output_contract == "candidate_selection":
            input_parts.append(
                '输出必须是 {"decision_reason":"...","candidate_id":"aN"}，'
                "candidate_id 必须来自当前公开候选列表。"
            )
        if request.plan_data:
            input_parts.append(f"当前计划状态（公开结构化数据）：{request.plan_data}")
        if request.output_contract == "planner":
            input_parts.append(
                "你当前是 Planner，只能输出计划字段，不得输出 tool、action 或任何具体动作。"
            )
        if request.runtime_feedback:
            input_parts.append(f"运行时提醒（仅来自公开轨迹）：{request.runtime_feedback}")
        if request.recent_history:
            input_parts.append(f"最近公开轨迹（仅供参考）：{request.recent_history}")
        input_parts.append(correction_instruction)
        request_kwargs: dict[str, object] = {
            "model": self._settings.model_name,
            "instructions": request.system_prompt,
            "input": "\n".join(input_parts),
            "temperature": 0,
            "text": {"format": _response_format(self._settings.response_format, request)},
        }
        if request.action_contract_version == "scenario_v4":
            # MiMo defaults to enabled reasoning; explicitly disable it for the
            # frozen V5 condition even when the shared settings default to none.
            request_kwargs["reasoning"] = {"effort": "none"}
        else:
            request_kwargs["store"] = False
        if request.max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = request.max_output_tokens
        if (
            request.action_contract_version != "scenario_v4"
            and self._settings.reasoning_effort != "none"
        ):
            request_kwargs["reasoning"] = {"effort": self._settings.reasoning_effort}
        response = self._client.responses.create(**cast(Any, request_kwargs))
        try:
            usage = response.usage
            details = getattr(usage, "input_tokens_details", None) if usage else None
            cached_tokens = getattr(details, "cached_tokens", None)
            input_tokens = usage.input_tokens if usage else None
            output_tokens = usage.output_tokens if usage else None
            cached_input_tokens = cached_tokens if isinstance(cached_tokens, int) else None
            if not response.output_text:
                if request.action_contract_version == "scenario_v4":
                    return ProviderResponse(
                        candidate=None,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_input_tokens=cached_input_tokens,
                    )
                raise DecisionProviderError("OpenAI provider returned no decision.")
            return ProviderResponse(
                candidate=json.loads(response.output_text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached_input_tokens,
            )
        except json.JSONDecodeError as exc:
            if request.action_contract_version == "scenario_v4":
                usage = response.usage
                details = getattr(usage, "input_tokens_details", None) if usage else None
                cached_tokens = getattr(details, "cached_tokens", None)
                return ProviderResponse(
                    candidate=None,
                    input_tokens=usage.input_tokens if usage else None,
                    output_tokens=usage.output_tokens if usage else None,
                    cached_input_tokens=(cached_tokens if isinstance(cached_tokens, int) else None),
                )
            raise DecisionProviderError("OpenAI provider returned malformed JSON.") from exc


def _correction_instruction(request: DecisionRequest) -> str:
    if not request.correction:
        return "请只返回规定的 JSON 结构。"
    if request.invalid_output_reason == "missing_argument":
        return "上一条 Action 缺少必填参数。请按所选 tool 补全所有必填参数后只返回 JSON。"
    return "上一条输出不符合格式。请只返回规定的 JSON 结构。"


def _response_format(mode: str, request: DecisionRequest) -> dict[str, object]:
    if mode == "json_schema":
        return {
            "type": "json_schema",
            "name": "agent_decision",
            "strict": True,
            "schema": (
                candidate_selection_response_schema()
                if request.output_contract == "candidate_selection"
                else (
                    planner_response_schema_strict()
                    if request.output_contract == "planner"
                    else decision_response_schema_strict(request.action_contract_version)
                )
            ),
        }
    return {"type": "json_object"}
