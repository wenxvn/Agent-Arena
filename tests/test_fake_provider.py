from __future__ import annotations

import pytest

from agent_arena.llm.fake import FakeDecisionProvider, FakeProviderExhausted
from agent_arena.llm.protocol import DecisionRequest


def test_fake_provider_returns_responses_and_records_correction() -> None:
    provider = FakeDecisionProvider([{"tool": "look"}])
    observation = {"location": "bridge"}

    response = provider.decide(
        DecisionRequest(observation=observation, system_prompt="prompt", correction=True)
    )

    assert response.candidate == {"tool": "look"}
    assert provider.calls[0].request.observation == observation
    assert provider.calls[0].request.correction is True


def test_fake_provider_queue_exhaustion_is_explicit() -> None:
    provider = FakeDecisionProvider([])

    with pytest.raises(FakeProviderExhausted, match="exhausted"):
        provider.decide(DecisionRequest(observation={}, system_prompt="prompt", correction=False))
