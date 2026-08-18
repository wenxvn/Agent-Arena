"""Provider boundary shared by the future Agent Loop and test doubles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DecisionRequest:
    observation: object
    system_prompt: str
    correction: bool
    memory_data: str | None = None
    runtime_feedback: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    candidate: object
    input_tokens: int | None = None
    output_tokens: int | None = None


class DecisionProvider(Protocol):
    """Return a candidate decision without knowing Environment internals."""

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        """Return a response candidate for the supplied public observation."""
