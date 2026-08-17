"""Deterministic implementation of the first Spaceship Escape world."""

from __future__ import annotations

from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_arena.arena.environment import Environment
from agent_arena.arena.models import (
    Action,
    InspectAction,
    LookAction,
    MoveAction,
    Observation,
    PickupAction,
    ReadTerminalAction,
    ToolReason,
    ToolResult,
    ToolStatus,
    UseAction,
    WorldState,
)


class RoomDefinition(BaseModel):
    """Static definition of one room in the spaceship."""

    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    exits: tuple[str, ...]
    object_ids: tuple[str, ...]


class ObjectDefinition(BaseModel):
    """Static object metadata used by inspect and visibility rules."""

    model_config = ConfigDict(frozen=True)

    id: str
    room_id: str
    kind: Literal["terminal", "container", "fixture"]
    inspect_result: str


class ItemDefinition(BaseModel):
    """Static item metadata used by pickup rules."""

    model_config = ConfigDict(frozen=True)

    id: str
    container_id: str


class WorldDefinition(BaseModel):
    """Versioned, read only data needed to instantiate the world."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["spaceship_escape_v1"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_spaceship_escape_definition() -> WorldDefinition:
    """Load the checked in static definition for the first world version."""

    definition_path = files("agent_arena.worlds").joinpath("data/spaceship_escape_v1.json")
    return WorldDefinition.model_validate_json(definition_path.read_text(encoding="utf-8"))


class SpaceshipEscapeEnvironment(Environment):
    """A six room, deterministic environment with a single escape route."""

    def __init__(self, definition: WorldDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_spaceship_escape_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)

    def reset(self, seed: int = 0) -> Observation:
        self._state = self._initial_state(seed)
        return self.observe()

    def observe(self) -> Observation:
        room = self._current_room()
        return Observation(
            current_room=room.id,
            description=room.description,
            visible_objects=self._visible_objects(),
            available_exits=room.exits,
            inventory=tuple(sorted(self._state.inventory)),
            last_action_result=self._state.last_action_result,
        )

    def step(self, action: Action) -> tuple[ToolResult, Observation]:
        self._state.step_count += 1
        if self._state.escaped:
            result = self._rejected(ToolReason.ALREADY_COMPLETED)
        elif isinstance(action, LookAction):
            result = self._success(ToolReason.LOOKED)
        elif isinstance(action, MoveAction):
            result = self._move(action)
        elif isinstance(action, InspectAction):
            result = self._inspect(action)
        elif isinstance(action, PickupAction):
            result = self._pickup(action)
        elif isinstance(action, UseAction):
            result = self._use(action)
        elif isinstance(action, ReadTerminalAction):
            result = self._read_terminal(action)
        else:
            raise TypeError(f"Unsupported validated action: {action!r}")

        self._state.last_action_result = result
        return result, self.observe()

    def is_success(self) -> bool:
        return self._state.escaped

    def _initial_state(self, seed: int) -> WorldState:
        return WorldState(seed=seed, current_room=self.definition.start_room)

    def _current_room(self) -> RoomDefinition:
        return self._rooms[self._state.current_room]

    def _visible_objects(self) -> tuple[str, ...]:
        visible = list(self._current_room().object_ids)
        if self._state.current_room == "storage_room":
            visible.extend(
                item_id
                for item_id in sorted(self._state.revealed_items)
                if item_id not in self._state.inventory
            )
        if not self._state.reactor_panel_open:
            visible = [object_id for object_id in visible if object_id != "damaged_fuse"]
        return tuple(visible)

    def _move(self, action: MoveAction) -> ToolResult:
        if action.destination not in self._current_room().exits:
            return self._rejected(ToolReason.NOT_ADJACENT)
        self._state.current_room = action.destination
        return self._success(ToolReason.MOVED)

    def _inspect(self, action: InspectAction) -> ToolResult:
        if action.target not in self._visible_objects() or action.target not in self._objects:
            return self._rejected(ToolReason.NOT_VISIBLE)
        if action.target == "storage_crate":
            self._state.revealed_items.update(self._items)
        return self._success(ToolReason.INSPECTED, self._objects[action.target].inspect_result)

    def _pickup(self, action: PickupAction) -> ToolResult:
        if action.item in self._state.inventory:
            return self._rejected(ToolReason.ALREADY_COLLECTED)
        item = self._items.get(action.item)
        if item is None:
            return self._rejected(ToolReason.NOT_PRESENT)
        if action.item not in self._state.revealed_items:
            return self._rejected(ToolReason.NOT_REVEALED)
        container = self._objects[item.container_id]
        if container.room_id != self._state.current_room:
            return self._rejected(ToolReason.NOT_PRESENT)
        self._state.inventory.add(action.item)
        return self._success(ToolReason.PICKED_UP)

    def _use(self, action: UseAction) -> ToolResult:
        if action.target == "reactor_panel":
            return self._open_reactor_panel(action)
        if action.target == "damaged_fuse":
            return self._replace_fuse(action)
        if action.target == "escape_pod":
            return self._launch_escape_pod(action)
        return self._rejected(ToolReason.WRONG_TARGET)

    def _open_reactor_panel(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "reactor_room":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "screwdriver" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if self._state.reactor_panel_open:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.reactor_panel_open = True
        return self._success(ToolReason.PANEL_OPENED)

    def _replace_fuse(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "reactor_room":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "replacement_fuse" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if not self._state.reactor_panel_open:
            return self._rejected(ToolReason.PANEL_CLOSED)
        if self._state.main_power:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.main_power = True
        return self._success(ToolReason.POWER_RESTORED)

    def _launch_escape_pod(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "escape_pod":
            return self._rejected(ToolReason.WRONG_TARGET)
        if not self._state.authorization_code_read:
            return self._rejected(ToolReason.CODE_UNREAD)
        if action.item != self.definition.authorization_code:
            return self._rejected(ToolReason.INCORRECT_CODE)
        self._state.escaped = True
        return self._success(ToolReason.ESCAPED)

    def _read_terminal(self, action: ReadTerminalAction) -> ToolResult:
        if action.target not in self._visible_objects():
            return self._rejected(ToolReason.NOT_VISIBLE)
        if action.target == "diagnostic_terminal":
            if self._state.main_power:
                return self._success(
                    ToolReason.DIAGNOSTIC_READ,
                    "Diagnostics report that main power is stable.",
                )
            return self._success(
                ToolReason.DIAGNOSTIC_READ,
                "Diagnostics report no main power. Repair the reactor manually.",
            )
        if action.target == "control_terminal":
            if not self._state.main_power:
                return self._rejected(ToolReason.NO_POWER)
            self._state.authorization_code_read = True
            return self._success(
                ToolReason.CODE_READ,
                f"Authorization code: {self.definition.authorization_code}",
            )
        return self._rejected(ToolReason.WRONG_TARGET)

    @staticmethod
    def _success(reason: ToolReason, summary: str | None = None) -> ToolResult:
        return ToolResult(
            status=ToolStatus.SUCCESS,
            reason=reason,
            summary=summary or _SUMMARIES[reason],
        )

    @staticmethod
    def _rejected(reason: ToolReason) -> ToolResult:
        return ToolResult(status=ToolStatus.REJECTED, reason=reason, summary=_SUMMARIES[reason])


_SUMMARIES: dict[ToolReason, str] = {
    ToolReason.LOOKED: "You examine the current room.",
    ToolReason.MOVED: "You move to the requested room.",
    ToolReason.INSPECTED: "You inspect the requested object.",
    ToolReason.PICKED_UP: "You add the item to your inventory.",
    ToolReason.PANEL_OPENED: "The reactor panel is now open.",
    ToolReason.POWER_RESTORED: "Main power has been restored.",
    ToolReason.DIAGNOSTIC_READ: "You read the diagnostic terminal.",
    ToolReason.CODE_READ: "You read the control terminal authorization code.",
    ToolReason.ESCAPED: "The escape pod launches successfully.",
    ToolReason.ALREADY_COMPLETED: "The escape sequence is already complete.",
    ToolReason.NOT_ADJACENT: "That room is not reachable from here.",
    ToolReason.NOT_VISIBLE: "That target is not visible in the current room.",
    ToolReason.NOT_REVEALED: "That item has not been revealed yet.",
    ToolReason.NOT_PRESENT: "That item is not present in the current room.",
    ToolReason.ALREADY_COLLECTED: "That item is already in your inventory.",
    ToolReason.MISSING_ITEM: "You do not have the required item.",
    ToolReason.WRONG_TARGET: "That item cannot be used on this target now.",
    ToolReason.PANEL_CLOSED: "Open the reactor panel before replacing the fuse.",
    ToolReason.CODE_UNREAD: "Read the authorization code before launching the pod.",
    ToolReason.INCORRECT_CODE: "That authorization code is not accepted.",
    ToolReason.NO_POWER: "The control terminal has no main power.",
}
