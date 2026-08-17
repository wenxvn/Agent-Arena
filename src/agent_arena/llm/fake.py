"""Deterministic provider used by local runs and tests."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from agent_arena.llm.protocol import DecisionRequest, ProviderResponse


class FakeProviderExhausted(RuntimeError):
    """Raised when a fixture did not provide enough provider responses."""


@dataclass(frozen=True)
class FakeProviderCall:
    """A record of one provider request for test assertions."""

    request: DecisionRequest


class FakeDecisionProvider:
    """Return ordered fixture responses and never contact a real provider."""

    def __init__(self, responses: Iterable[object]) -> None:
        self._responses: deque[object] = deque(responses)
        self.calls: list[FakeProviderCall] = []

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        self.calls.append(FakeProviderCall(request=request))
        if not self._responses:
            raise FakeProviderExhausted("Fake provider response queue is exhausted.")

        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        if isinstance(response, ProviderResponse):
            return response
        return ProviderResponse(candidate=response)
