from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.config import RuntimeSettings
from agent_arena.worlds import create_environment
from agent_arena.worlds.spaceship_escape import (
    SpaceshipV2Environment,
    load_spaceship_v2_definition,
)


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: SpaceshipV2Environment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(
    environment: SpaceshipV2Environment, payload: Mapping[str, Any]
) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: SpaceshipV2Environment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_v2_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_spaceship_v2_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "spaceship_escape_v2"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_v2_identity_matches_registered_selector() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v3-zh")
    assert isinstance(environment, SpaceshipV2Environment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-v3-zh")
    assert environment.identity[2] == "spaceship_escape_v2"


def test_v2_public_passage_escapes_with_new_code() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v3-zh")
    observation = environment.reset(0)
    assert observation.current_room == "control_room"

    move_to(environment, "corridor", "maintenance_room", "cargo_bay")
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert (
        step(environment, {"tool": "pickup", "item": "replacement_fuse"})
        is ToolReason.PICKED_UP
    )
    move_to(environment, "maintenance_room", "reactor_room")
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
    assert "BETA-512" in (result.summary or "")
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "BETA-512", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_v2_decoys_do_not_block_passage() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v3-zh")
    environment.reset(0)
    move_to(environment, "corridor", "observation_deck")
    assert step(environment, {"tool": "inspect", "target": "viewport"}) is ToolReason.INSPECTED
    move_to(environment, "corridor", "maintenance_room", "cargo_bay")
    step(environment, {"tool": "inspect", "target": "storage_crate"})
    assert step(environment, {"tool": "pickup", "item": "duct_tape"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "duct_tape", "target": "reactor_panel"})
        is ToolReason.WRONG_TARGET
    )
    assert (
        rejected(environment, {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"})
        is ToolReason.WRONG_TARGET
    )


def test_step_limit_zero_means_unlimited() -> None:
    settings = RuntimeSettings.load({"step_limit": 0}, env_file=None)
    assert settings.step_limit == 0
