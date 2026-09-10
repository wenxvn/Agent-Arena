"""Structured contracts for the generic PlanningAgent v1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

BoundedText = Annotated[str, Field(min_length=1, max_length=240)]
PlannerReason = Annotated[str, Field(min_length=1, max_length=280)]


class SuccessCriterion(BaseModel):
    """A machine-checkable public condition for completing a subgoal."""

    model_config = ConfigDict(extra="forbid", strict=True)

    criterion_type: Literal[
        "inventory_contains",
        "room_reached",
        "object_visible",
        "exit_available",
        "tool_result_status",
        "tool_result_reason",
        "public_fact",
    ]
    target: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, min_length=1, max_length=120)
    description: BoundedText


Criterion = SuccessCriterion | BoundedText


class PlanState(BaseModel):
    """The small, persistent public plan carried by one episode."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    plan_version: str = "planning_v1"
    plan_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    overall_goal: BoundedText
    current_subgoal: BoundedText
    success_criteria: tuple[Criterion, ...] = Field(min_length=1, max_length=8)
    known_constraints: tuple[BoundedText, ...] = Field(default=(), max_length=12)
    relevant_resources: tuple[BoundedText, ...] = Field(default=(), max_length=12)
    completed_subgoals: tuple[BoundedText, ...] = Field(default=(), max_length=24)
    unresolved_questions: tuple[BoundedText, ...] = Field(default=(), max_length=12)
    replan_reason: str | None = Field(default=None, max_length=120)


class PlannerDecision(BaseModel):
    """Allowlisted Planner output; it never contains an executable Action."""

    model_config = ConfigDict(extra="forbid")

    decision_reason: PlannerReason
    current_subgoal: BoundedText
    success_criteria: tuple[Criterion, ...] = Field(min_length=1, max_length=8)
    known_constraints: tuple[BoundedText, ...] = Field(default=(), max_length=12)
    relevant_resources: tuple[BoundedText, ...] = Field(default=(), max_length=12)
    unresolved_questions: tuple[BoundedText, ...] = Field(default=(), max_length=12)


planner_decision_adapter: TypeAdapter[PlannerDecision] = TypeAdapter(PlannerDecision)


PlanSignalStatus = Literal[
    "continue",
    "subgoal_completed",
    "no_progress",
    "repeated_failure",
    "plan_invalid",
]


class PlanSignal(BaseModel):
    """A monitor signal that may cause the next Planner request."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status: PlanSignalStatus
    reason: str | None = Field(default=None, max_length=120)


@dataclass(frozen=True)
class PlanningMetadata:
    """Trace-safe metadata exposed by an Agent request."""

    plan_id: str | None = None
    plan_version: str | None = None
    current_subgoal: str | None = None
    planner_called: bool = False
    replan_reason: str | None = None
    plan_signal: str | None = None
    subgoal_completed: bool = False
    planner_latency_ms: int | None = None
    planner_input_tokens: int | None = None
    planner_output_tokens: int | None = None
    executor_latency_ms: int | None = None
    executor_input_tokens: int | None = None
    executor_output_tokens: int | None = None
