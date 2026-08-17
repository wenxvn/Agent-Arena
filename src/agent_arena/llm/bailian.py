"""OpenAI compatible Bailian adapters kept outside the agent loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import sleep

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError
from pydantic import BaseModel

from agent_arena.config import RuntimeSettings


class ModelVerificationError(RuntimeError):
    """Raised without preserving provider response bodies in user output."""


class DecisionProviderError(RuntimeError):
    """A safe provider failure that never exposes response or exception bodies."""


@dataclass(frozen=True)
class ModelVerification:
    """Allowlisted result emitted by the model verification command."""

    model: str
    text: str


class BailianModelVerifier:
    """Make one explicit, non fallback model verification request."""

    def __init__(self, settings: RuntimeSettings) -> None:
        base_url, api_key = settings.require_bailian()
        self._settings = settings
        self._client = OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    def verify(self) -> ModelVerification:
        try:
            response = self._client.chat.completions.create(
                model=self._settings.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": "请只回复：Agent Arena 模型配置验证成功。",
                    }
                ],
                temperature=0,
                max_tokens=32,
                extra_body={"enable_thinking": self._settings.enable_thinking},
            )
        except Exception as exc:
            raise ModelVerificationError("Model verification request failed.") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise ModelVerificationError("Model verification returned no final text.")
        return ModelVerification(model=response.model or self._settings.model_name, text=text)


class BailianDecisionProvider:
    """Request one JSON decision with bounded retries for transient failures."""

    def __init__(self, settings: RuntimeSettings) -> None:
        base_url, api_key = settings.require_bailian()
        self._settings = settings
        self._client = OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    def decide(self, observation: object, prompt: str, correction: bool) -> object:
        """Return parsed JSON only; raw provider responses never leave this adapter."""

        for attempt in range(self._settings.retry_count + 1):
            try:
                return self._request_once(observation, prompt, correction)
            except (
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            ) as exc:
                if attempt == self._settings.retry_count:
                    raise DecisionProviderError("Bailian request failed.") from exc
                sleep(self._settings.retry_backoff_seconds[attempt])
            except DecisionProviderError:
                raise
            except Exception as exc:
                raise DecisionProviderError("Bailian request failed.") from exc

        raise AssertionError("Retry loop must return or raise.")

    def _request_once(self, observation: object, prompt: str, correction: bool) -> object:
        if not isinstance(observation, BaseModel):
            raise DecisionProviderError("Bailian requires a structured observation.")
        correction_instruction = (
            "上一条输出不符合格式。请只返回规定的 JSON 结构。"
            if correction
            else "请只返回规定的 JSON 结构。"
        )
        response = self._client.chat.completions.create(
            model=self._settings.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"当前观察：{observation.model_dump_json()}\n{correction_instruction}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": self._settings.enable_thinking},
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise DecisionProviderError("Bailian returned no decision.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise DecisionProviderError("Bailian returned malformed JSON.") from exc
