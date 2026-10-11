from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.spaceship_escape import (
    SpaceshipV3Environment,
    load_spaceship_v3_definition,
)


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: SpaceshipV3Environment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(
    environment: SpaceshipV3Environment, payload: Mapping[str, Any]
) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: SpaceshipV3Environment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_spaceship_hard_definition_has_ten_rooms_and_bidirectional_exits() -> None:
    definition = load_spaceship_v3_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "spaceship_escape_v3"
    assert len(rooms) == 10
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_spaceship_hard_identity_matches_registered_selector() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v4-zh")
    assert isinstance(environment, SpaceshipV3Environment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-v4-zh")
    assert environment.identity[2] == "spaceship_escape_v3"


def test_spaceship_hard_public_passage_escapes_in_twenty_one_steps() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v4-zh")
    observation = environment.reset(0)
    assert observation.current_room == "control_room"

    move_to(environment, "corridor", "maintenance_room", "cargo_bay", "deep_cellar")
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert (
        step(environment, {"tool": "pickup", "item": "replacement_fuse"})
        is ToolReason.PICKED_UP
    )
    move_to(environment, "cargo_bay", "maintenance_room", "reactor_room")
    assert (
        step(environment, {"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "maintenance_room", "corridor", "control_room")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "control_terminal"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "GAMMA-904" in (result.summary or "")
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "GAMMA-904", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_spaceship_hard_decoys_and_gated_pod() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v4-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "move", "destination": "escape_pod"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "corridor", "maintenance_room", "supply_closet")
    assert (
        step(environment, {"tool": "inspect", "target": "spare_uniform"})
        is ToolReason.INSPECTED
    )
    move_to(environment, "maintenance_room", "cargo_bay")
    assert (
        step(environment, {"tool": "inspect", "target": "cargo_manifest"})
        is ToolReason.INSPECTED
    )
    move_to(environment, "deep_cellar")
    step(environment, {"tool": "inspect", "target": "storage_crate"})
    assert step(environment, {"tool": "pickup", "item": "spare_bulb"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "spare_bulb", "target": "damaged_fuse"})
        is ToolReason.WRONG_TARGET
    )
    assert (
        rejected(environment, {"tool": "use", "item": "BETA-512", "target": "escape_pod"})
        is ToolReason.WRONG_TARGET
    )
