from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.spaceship_escape import (
    SpaceshipV4Environment,
    SpaceshipV5Environment,
    SpaceshipV6Environment,
    load_spaceship_v4_definition,
    load_spaceship_v5_definition,
    load_spaceship_v6_definition,
)


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: Any, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(environment: Any, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: Any, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_redesign_ship_definitions_have_expected_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_spaceship_v4_definition, "spaceship_escape_v4", 6),
        (load_spaceship_v5_definition, "spaceship_escape_v5", 8),
        (load_spaceship_v6_definition, "spaceship_escape_v6", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_redesign_ship_identities_match_registered_selectors() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-easy-zh")
    assert isinstance(environment, SpaceshipV4Environment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-easy-zh")
    assert environment.identity[2] == "spaceship_escape_v4"
    environment = create_environment("spaceship-escape", "spaceship-escape-v1-zh")
    assert isinstance(environment, SpaceshipV5Environment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-v1-zh")
    assert environment.identity[2] == "spaceship_escape_v5"
    environment = create_environment("spaceship-escape", "spaceship-escape-hard-zh")
    assert isinstance(environment, SpaceshipV6Environment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-hard-zh")
    assert environment.identity[2] == "spaceship_escape_v6"


def test_redesign_ship_easy_chain_passage_escapes_in_twenty_steps() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "control_room"

    move_to(environment, "corridor", "parts_room")
    assert (
        step(environment, {"tool": "inspect", "target": "storage_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP
    move_to(environment, "maintenance_room", "reactor_room")
    assert (
        step(environment, {"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "maintenance_room", "parts_room", "corridor", "control_room")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "control_terminal"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ALPHA-204" in (result.summary or "")
    move_to(environment, "corridor", "parts_room", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "ALPHA-204", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_ship_easy_terminal_rules() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-easy-zh")
    environment.reset(0)
    assert (
        rejected(environment, {"tool": "read_terminal", "target": "control_terminal"})
        is ToolReason.NO_POWER
    )
    move_to(environment, "corridor", "parts_room")
    assert (
        rejected(environment, {"tool": "pickup", "item": "screwdriver"})
        is ToolReason.NOT_REVEALED
    )


def test_redesign_ship_medium_split_containers_passage_escapes_in_twenty_two_steps() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "control_room"

    move_to(environment, "corridor", "parts_room")
    assert (
        step(environment, {"tool": "inspect", "target": "storage_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    move_to(environment, "corridor", "maintenance_room", "backup_locker")
    assert (
        step(environment, {"tool": "inspect", "target": "cargo_crate"}) is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP
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
    assert "BETA-416" in (result.summary or "")
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "BETA-416", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_ship_medium_decoy_does_not_block_passage() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "corridor", "viewport_hall")
    assert step(environment, {"tool": "inspect", "target": "viewport"}) is ToolReason.INSPECTED


def test_redesign_ship_hard_split_deep_passage_escapes_in_twenty_four_steps() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "control_room"

    move_to(environment, "corridor", "supply_closet")
    assert (
        step(environment, {"tool": "inspect", "target": "cargo_crate"}) is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP
    move_to(environment, "corridor", "maintenance_room", "cargo_bay", "deep_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "storage_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
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
    assert "GAMMA-730" in (result.summary or "")
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "GAMMA-730", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_ship_hard_repair_order_and_decoys() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "corridor", "supply_closet")
    step(environment, {"tool": "inspect", "target": "cargo_crate"})
    step(environment, {"tool": "pickup", "item": "replacement_fuse"})
    step(environment, {"tool": "pickup", "item": "spare_bulb"})
    move_to(environment, "corridor", "maintenance_room", "cargo_bay", "deep_cellar")
    step(environment, {"tool": "inspect", "target": "storage_crate"})
    step(environment, {"tool": "pickup", "item": "screwdriver"})
    move_to(environment, "cargo_bay", "maintenance_room", "reactor_room")
    assert (
        rejected(
            environment,
            {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"},
        )
        is ToolReason.PANEL_CLOSED
    )
    assert (
        rejected(environment, {"tool": "use", "item": "spare_bulb", "target": "reactor_panel"})
        is ToolReason.MISSING_ITEM
    )
