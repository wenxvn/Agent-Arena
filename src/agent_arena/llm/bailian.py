"""Minimal OpenAI compatible Bailian client used by verify-model."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from agent_arena.config import RuntimeSettings


class ModelVerificationError(RuntimeError):
    """Raised without preserving provider response bodies in user output."""


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
                        "content": "Reply with: Agent Arena model configuration verified.",
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
