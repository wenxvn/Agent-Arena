"""Provider boundary shared by the future Agent Loop and test doubles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import TypeAdapter

from agent_arena.arena import Action
from agent_arena.arena.scenario_models import ScenarioAction
from agent_arena.worlds.scenario_v4.models import ScenarioV4Action, V4HypothesisTable

ActionContractVersion = Literal["legacy_v1", "scenario_v3", "scenario_v4"]


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
    cached_input_tokens: int | None = None


class DecisionProvider(Protocol):
    """Return a candidate decision without knowing Environment internals."""

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        """Return a response candidate for the supplied public observation."""


def decision_response_schema(
    action_contract_version: ActionContractVersion = "legacy_v1",
) -> dict[str, object]:
    """Return the shared JSON Schema for a decision without importing Agent policy."""

    action_type = (
        Action
        if action_contract_version == "legacy_v1"
        else (ScenarioAction if action_contract_version == "scenario_v3" else ScenarioV4Action)
    )
    properties: dict[str, object] = {
        "decision_reason": {"type": "string", "maxLength": 280},
        "action": TypeAdapter(action_type).json_schema(),
    }
    required = ["decision_reason", "action"]
    if action_contract_version == "scenario_v4":
        properties["agent_hypothesis_table"] = {
            "anyOf": [TypeAdapter(V4HypothesisTable).json_schema(), {"type": "null"}]
        }
        required.append("agent_hypothesis_table")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
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
    if action_contract_version == "scenario_v4":
        return _scenario_v4_decision_schema_strict()

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


def _scenario_v4_decision_schema_strict() -> dict[str, object]:
    """Return the strict Responses API schema for the V4 action union."""

    def variant(tool: str, fields: dict[str, object] | None = None) -> dict[str, object]:
        properties: dict[str, object] = {"tool": {"const": tool}}
        properties.update(fields or {})
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }

    string = {"type": "string"}
    train_id = {"type": "string", "enum": ["a", "b", "T_R1", "T_R2", "T_R3", "T_B", "T_G", "T_X"]}
    scalar_tools = (
        "inspect_network",
        "move_train",
        "observe_signpost",
        "check_goal",
        "return_to_camp",
        "rollback",
        "restart",
    )
    actions = [variant(tool) for tool in scalar_tools]
    actions.extend(variant("move", {field: string}) for field in ("edge_id", "to", "bearing"))
    actions.extend(variant("inspect", {field: string}) for field in ("target_id", "evidence_id"))
    actions.extend(
        [
            variant(
                "interact",
                {"target_id": string, "operation": string},
            ),
            variant("wait", {"turns": {"type": "integer", "const": 1}}),
            variant("set_route", {"train_id": train_id, "next_node": string}),
            variant("occupy_siding", {"train_id": train_id, "next_node": string}),
            variant("release_section", {"train_id": train_id, "section_id": string}),
        ]
    )

    def joint_op(op: str, fields: dict[str, object] | None = None) -> dict[str, object]:
        properties: dict[str, object] = {"op": {"const": op}}
        properties.update(fields or {})
        return {
            "type": "object",
            "additionalProperties": False,
            "required": list(properties),
            "properties": properties,
        }

    joint_operations = {
        "anyOf": [
            joint_op("release", {"to": string}),
            joint_op("detour", {"to": string}),
            joint_op("temporary_stop"),
            joint_op(
                "turnback",
                {
                    "reverse_toward": string,
                    "duration_ticks": {"type": "integer", "minimum": 1, "maximum": 2},
                },
            ),
            joint_op("cancel_service", {"task_id": string}),
        ]
    }
    operations_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["T_R1", "T_R2", "T_R3", "T_B", "T_G", "T_X"],
        "properties": {
            train: {"anyOf": [{"type": "null"}, joint_operations]}
            for train in ("T_R1", "T_R2", "T_R3", "T_B", "T_G", "T_X")
        },
    }
    node_fact = {
        "type": "object",
        "additionalProperties": False,
        "required": ["fact_type", "sign_id", "exit_bearings"],
        "properties": {
            "fact_type": {"const": "node_page"},
            "sign_id": string,
            "exit_bearings": {"type": "array", "items": string},
        },
    }
    edge_fact = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "fact_type",
            "from_sign_id",
            "departure_bearing",
            "to_sign_id",
            "arrival_reverse_bearing",
        ],
        "properties": {
            "fact_type": {"const": "traversed_edge_page"},
            "from_sign_id": string,
            "departure_bearing": string,
            "to_sign_id": string,
            "arrival_reverse_bearing": string,
        },
    }
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": ["event_id", "time", "location", "duty_code"],
        "properties": {
            "event_id": string,
            "time": string,
            "location": string,
            "duty_code": string,
        },
    }
    hypothesis_table = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "belief_B",
            "belief_D",
            "belief_F",
            "test_X_result",
            "test_Y_result",
            "next_test",
        ],
        "properties": {
            "belief_B": {"type": "number", "minimum": 0, "maximum": 1},
            "belief_D": {"type": "number", "minimum": 0, "maximum": 1},
            "belief_F": {"type": "number", "minimum": 0, "maximum": 1},
            "test_X_result": {
                "anyOf": [
                    {"type": "string", "enum": ["pulse_amber", "pulse_slate"]},
                    {"type": "null"},
                ]
            },
            "test_Y_result": {
                "anyOf": [
                    {"type": "string", "enum": ["pulse_cobalt", "pulse_slate"]},
                    {"type": "null"},
                ]
            },
            "next_test": {"type": "string", "enum": ["X", "Y", "repair"]},
        },
    }
    actions.extend(
        [
            variant(
                "set_timetable",
                {
                    "tick": {"type": "integer", "minimum": 0},
                    "operations": operations_schema,
                },
            ),
            variant(
                "write_memory",
                {"facts": {"type": "array", "items": {"anyOf": [node_fact, edge_fact]}}},
            ),
            variant("read_log", {"log_id": string}),
            variant("test", {"test_id": string}),
            variant("take_spare", {"part_id": string}),
            variant("replace", {"part_id": string}),
            variant(
                "interview",
                {
                    "npc_id": string,
                    "topic_id": string,
                    "shown_evidence_ids": {"type": "array", "items": string},
                    "shown_casebook_entry_ids": {"type": "array", "items": string},
                },
            ),
            variant(
                "record",
                {"entry_id": string, "evidence_ids": {"type": "array", "items": string}},
            ),
            variant(
                "submit_intermediate_hypothesis",
                {
                    "candidate_person": string,
                    "confidence": {"type": "string", "enum": ["low", "tentative"]},
                    "event_ids_known": {"type": "array", "items": string},
                },
            ),
            variant("compare_records", {"entry_ids": {"type": "array", "items": string}}),
            variant(
                "formal_accuse",
                {
                    "person_id": string,
                    "event_claims": {"type": "array", "items": claim},
                    "cited_entry_ids": {"type": "array", "items": string},
                },
            ),
        ]
    )
    # The provider must emit all six MAP-18 train keys. The runner removes
    # null values before applying the strict sparse-operation Action model.
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision_reason", "action", "agent_hypothesis_table"],
        "properties": {
            "decision_reason": {"type": "string", "maxLength": 280},
            "action": {"anyOf": actions},
            "agent_hypothesis_table": {"anyOf": [hypothesis_table, {"type": "null"}]},
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
