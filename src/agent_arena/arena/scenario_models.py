"""Versioned public contracts used by V3 scenario worlds only."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent_arena.arena.models import (
    InspectAction,
    LookAction,
    MoveAction,
    Observation,
    PickupAction,
    ReadTerminalAction,
    UseAction,
)


class InteractAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool: Literal["interact"]
    target: str = Field(min_length=1, max_length=100)
    choice: str = Field(min_length=1, max_length=100)


class WaitAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool: Literal["wait"]
    turns: Literal[1] = 1


class SubmitAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool: Literal["submit"]
    target: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=240)


ScenarioAction = Annotated[
    LookAction
    | MoveAction
    | InspectAction
    | PickupAction
    | UseAction
    | ReadTerminalAction
    | InteractAction
    | WaitAction
    | SubmitAction,
    Field(discriminator="tool"),
]
scenario_action_adapter: TypeAdapter[ScenarioAction] = TypeAdapter(ScenarioAction)


class ScenarioStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "scenario_success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "scenario_failure"


class ScenarioTerminalStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ScenarioStatus
    failure_reason: str | None = None


class PublicStatusFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=240)


class InteractionOption(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str = Field(min_length=1, max_length=100)
    choices: tuple[str, ...]


class ScenarioObservation(Observation):
    """An Observation with only the currently public V3 scenario context."""

    scenario_id: str
    family: str
    difficulty: Literal["easy", "medium", "hard"]
    public_goal: str = Field(max_length=500)
    tick: int = Field(ge=0)
    public_status: tuple[PublicStatusFact, ...] = ()
    available_interactions: tuple[InteractionOption, ...] = ()


class ScenarioStepMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_event: str | None = Field(default=None, max_length=240)
    scenario_status: ScenarioStatus = ScenarioStatus.RUNNING
    failure_reason: str | None = Field(default=None, max_length=240)
    score_components: dict[str, int | float | str | bool] = Field(default_factory=dict)


__all__ = [
    "InteractAction",
    "InteractionOption",
    "PublicStatusFact",
    "ScenarioAction",
    "ScenarioObservation",
    "ScenarioStatus",
    "ScenarioStepMetadata",
    "ScenarioTerminalStatus",
    "SubmitAction",
    "WaitAction",
    "scenario_action_adapter",
]
