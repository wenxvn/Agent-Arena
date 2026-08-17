from __future__ import annotations

import pytest

from agent_arena.llm.fake import FakeDecisionProvider, FakeProviderExhausted


def test_fake_provider_returns_responses_and_records_correction() -> None:
    provider = FakeDecisionProvider([{"tool": "look"}])
    observation = {"location": "bridge"}

    response = provider.decide(observation, "prompt", correction=True)

    assert response == {"tool": "look"}
    assert provider.calls[0].observation == observation
    assert provider.calls[0].correction is True


def test_fake_provider_queue_exhaustion_is_explicit() -> None:
    provider = FakeDecisionProvider([])

    with pytest.raises(FakeProviderExhausted, match="exhausted"):
        provider.decide({}, "prompt", correction=False)
