"""Provider boundary shared by the future Agent Loop and test doubles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import TypeAdapter

from agent_arena.arena import Action


@dataclass(frozen=True)
class DecisionRequest:
    observation: object
    system_prompt: str
    correction: bool
    memory_data: str | None = None
    runtime_feedback: str | None = None
    invalid_output_reason: str | None = None
    recent_history: str | None = None
    output_contract: Literal["action", "candidate_selection"] = "action"


@dataclass(frozen=True)
class ProviderResponse:
    candidate: object
    input_tokens: int | None = None
    output_tokens: int | None = None


class DecisionProvider(Protocol):
    """Return a candidate decision without knowing Environment internals."""

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        """Return a response candidate for the supplied public observation."""


def decision_response_schema() -> dict[str, object]:
    """Return the shared JSON Schema for a decision without importing Agent policy."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision_reason", "action"],
        "properties": {
            "decision_reason": {"type": "string", "maxLength": 280},
            "action": TypeAdapter(Action).json_schema(),
        },
    }


def candidate_selection_response_schema() -> dict[str, object]:
    """Return the compact schema used by the public candidate-selection experiment."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision_reason", "candidate_id"],
        "properties": {
            "decision_reason": {"type": "string", "maxLength": 280},
            "candidate_id": {"type": "string", "pattern": r"^a[1-9][0-9]*$"},
        },
    }
