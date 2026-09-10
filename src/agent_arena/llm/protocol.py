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
    output_contract: Literal["action", "candidate_selection", "planner"] = "action"
    plan_data: str | None = None


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


def planner_response_schema() -> dict[str, object]:
    """Return the structured, non-executable Planner contract."""

    bounded_text = {"type": "string", "minLength": 1, "maxLength": 240}
    bounded_list = {
        "type": "array",
        "maxItems": 12,
        "items": bounded_text,
    }
    criterion = {
        "type": "object",
        "additionalProperties": False,
        "required": ["criterion_type", "description"],
        "properties": {
            "criterion_type": {
                "type": "string",
                "enum": [
                    "inventory_contains",
                    "room_reached",
                    "object_visible",
                    "exit_available",
                    "tool_result_status",
                    "tool_result_reason",
                    "public_fact",
                ],
            },
            "target": {"type": "string", "minLength": 1, "maxLength": 120},
            "value": {"type": "string", "minLength": 1, "maxLength": 120},
            "description": {"type": "string", "minLength": 1, "maxLength": 240},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "decision_reason",
            "current_subgoal",
            "success_criteria",
            "known_constraints",
            "relevant_resources",
            "unresolved_questions",
        ],
        "properties": {
            "decision_reason": {"type": "string", "minLength": 1, "maxLength": 280},
            "current_subgoal": bounded_text,
            "success_criteria": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                # String criteria remain valid for the frozen planning_v1
                # prompt; structured criteria are the Evaluation v2 path.
                "items": {"anyOf": [bounded_text, criterion]},
            },
            "known_constraints": bounded_list,
            "relevant_resources": bounded_list,
            "unresolved_questions": bounded_list,
        },
    }
