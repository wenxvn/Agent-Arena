"""Validated contracts shared by agents and deterministic environments."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ActionModel(BaseModel):
    """Base for every command an agent may send to an environment."""

    model_config = ConfigDict(extra="forbid", strict=True)


class LookAction(ActionModel):
    tool: Literal["look"]


class MoveAction(ActionModel):
    tool: Literal["move"]
    destination: str


class InspectAction(ActionModel):
    tool: Literal["inspect"]
    target: str


class PickupAction(ActionModel):
    tool: Literal["pickup"]
    item: str


class UseAction(ActionModel):
    tool: Literal["use"]
    item: str
    target: str


class ReadTerminalAction(ActionModel):
    tool: Literal["read_terminal"]
    target: str


Action = Annotated[
    LookAction | MoveAction | InspectAction | PickupAction | UseAction | ReadTerminalAction,
    Field(discriminator="tool"),
]
action_adapter: TypeAdapter[Action] = TypeAdapter(Action)


class ToolStatus(StrEnum):
    SUCCESS = "success"
    REJECTED = "rejected"


class ToolReason(StrEnum):
    LOOKED = "looked"
    MOVED = "moved"
    INSPECTED = "inspected"
    PICKED_UP = "picked_up"
    PANEL_OPENED = "panel_opened"
    POWER_RESTORED = "power_restored"
    DIAGNOSTIC_READ = "diagnostic_read"
    CODE_READ = "code_read"
    ESCAPED = "escaped"
    ALREADY_COMPLETED = "already_completed"
    NOT_ADJACENT = "not_adjacent"
    NOT_VISIBLE = "not_visible"
    NOT_REVEALED = "not_revealed"
    NOT_PRESENT = "not_present"
    ALREADY_COLLECTED = "already_collected"
    MISSING_ITEM = "missing_item"
    WRONG_TARGET = "wrong_target"
    PANEL_CLOSED = "panel_closed"
    CODE_UNREAD = "code_unread"
    INCORRECT_CODE = "incorrect_code"
    NO_POWER = "no_power"


class ToolResult(BaseModel):
    """Stable, allowlisted result of one validated tool call."""

    model_config = ConfigDict(frozen=True)

    status: ToolStatus
    reason: ToolReason
    summary: str


class Observation(BaseModel):
    """The complete allowlisted view made available to an agent."""

    model_config = ConfigDict(frozen=True)

    current_room: str
    description: str
    visible_objects: tuple[str, ...]
    available_exits: tuple[str, ...]
    inventory: tuple[str, ...]
    last_action_result: ToolResult | None


class WorldState(BaseModel):
    """Mutable per episode state, owned exclusively by the environment."""

    seed: int
    current_room: str
    inventory: set[str] = Field(default_factory=set)
    revealed_items: set[str] = Field(default_factory=set)
    step_count: int = Field(default=0, ge=0)
    reactor_panel_open: bool = False
    main_power: bool = False
    authorization_code_read: bool = False
    escaped: bool = False
    last_action_result: ToolResult | None = None
