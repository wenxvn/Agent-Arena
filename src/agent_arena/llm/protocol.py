"""Provider boundary shared by the future Agent Loop and test doubles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import TypeAdapter

from agent_arena.arena import Action
from agent_arena.arena.scenario_models import ScenarioAction

ActionContractVersion = Literal["legacy_v1", "scenario_v3"]


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
    max_output_tokens: int | None = None
    action_contract_version: ActionContractVersion = "legacy_v1"


@dataclass(frozen=True)
class ProviderResponse:
    candidate: object
    input_tokens: int | None = None
    output_tokens: int | None = None


class DecisionProvider(Protocol):
    """Return a candidate decision without knowing Environment internals."""

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        """Return a response candidate for the supplied public observation."""


def decision_response_schema(
    action_contract_version: ActionContractVersion = "legacy_v1",
) -> dict[str, object]:
    """Return the shared JSON Schema for a decision without importing Agent policy."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision_reason", "action"],
        "properties": {
            "decision_reason": {"type": "string", "maxLength": 280},
            "action": TypeAdapter(
                Action if action_contract_version == "legacy_v1" else ScenarioAction
            ).json_schema(),
        },
    }


def decision_response_schema_strict(
    action_contract_version: ActionContractVersion = "legacy_v1",
) -> dict[str, object]:
    """Return a $ref-free strict schema for Responses API gateways.

    Semantically identical to :func:`decision_response_schema`, but inlines
    every Action variant so gateways that reject ``$defs``/``$ref`` (such as
    the OpenCode Zen gateway) can enforce it. The shared contract above stays
    the canonical definition; this helper is only a transport encoding.
    """

    legacy_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision_reason", "action"],
        "properties": {
            "decision_reason": {"type": "string", "maxLength": 280},
            "action": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool"],
                        "properties": {"tool": {"const": "look"}},
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool", "destination"],
                        "properties": {
                            "tool": {"const": "move"},
                            "destination": {"type": "string"},
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool", "target"],
                        "properties": {
                            "tool": {"enum": ["inspect", "read_terminal"]},
                            "target": {"type": "string"},
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool", "item"],
                        "properties": {
                            "tool": {"const": "pickup"},
                            "item": {"type": "string"},
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["tool", "item", "target"],
                        "properties": {
                            "tool": {"const": "use"},
                            "item": {"type": "string"},
                            "target": {"type": "string"},
                        },
                    },
                ]
            },
        },
    }
    if action_contract_version == "legacy_v1":
        return legacy_schema

    properties = legacy_schema.get("properties")
    if not isinstance(properties, dict):
        raise AssertionError("Decision schema must contain properties.")
    action_schema = properties.get("action")
    if not isinstance(action_schema, dict):
        raise AssertionError("Legacy action schema must be an object.")
    action_variants = action_schema["anyOf"]
    if not isinstance(action_variants, list):
        raise AssertionError("Legacy action schema must contain variants.")
    action_variants.extend(
        [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool", "target", "choice"],
                "properties": {
                    "tool": {"const": "interact"},
                    "target": {"type": "string", "minLength": 1, "maxLength": 100},
                    "choice": {"type": "string", "minLength": 1, "maxLength": 100},
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool", "turns"],
                "properties": {"tool": {"const": "wait"}, "turns": {"const": 1}},
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool", "target", "answer"],
                "properties": {
                    "tool": {"const": "submit"},
                    "target": {"type": "string", "minLength": 1, "maxLength": 100},
                    "answer": {"type": "string", "minLength": 1, "maxLength": 240},
                },
            },
        ]
    )
    return legacy_schema


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


def planner_response_schema_strict() -> dict[str, object]:
    """Return a gateway-compatible strict Planner schema.

    Same contract as :func:`planner_response_schema`, except every object
    lists all of its properties in ``required``: strict-mode gateways (such
    as the OpenCode Zen gateway) reject schemas where an optional key exists.
    ``target``/``value`` stay semantically optional: callers that have no
    target use ``""``.
    """

    bounded_text = {"type": "string", "minLength": 1, "maxLength": 240}
    bounded_list = {
        "type": "array",
        "maxItems": 12,
        "items": bounded_text,
    }
    criterion = {
        "type": "object",
        "additionalProperties": False,
        "required": ["criterion_type", "description", "target", "value"],
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
            "target": {"type": "string", "maxLength": 120},
            "value": {"type": "string", "maxLength": 120},
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
                "items": {"anyOf": [bounded_text, criterion]},
            },
            "known_constraints": bounded_list,
            "relevant_resources": bounded_list,
            "unresolved_questions": bounded_list,
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
