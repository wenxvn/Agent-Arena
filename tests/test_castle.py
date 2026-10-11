from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.castle import (
    CastleEasyEnvironment,
    CastleEnvironment,
    CastleHardEnvironment,
    load_castle_definition,
    load_castle_easy_definition,
    load_castle_hard_definition,
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


def test_castle_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_castle_easy_definition, "castle_escape_easy", 6),
        (load_castle_definition, "castle_escape_v1", 8),
        (load_castle_hard_definition, "castle_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_castle_identities_match_registered_selectors() -> None:
    environment = create_environment("castle-escape", "castle-escape-easy-zh")
    assert isinstance(environment, CastleEasyEnvironment)
    assert environment.identity[:2] == ("castle-escape", "castle-escape-easy-zh")
    assert environment.identity[2] == "castle_escape_easy"
    environment = create_environment("castle-escape", "castle-escape-v1-zh")
    assert isinstance(environment, CastleEnvironment)
    assert environment.identity[:2] == ("castle-escape", "castle-escape-v1-zh")
    assert environment.identity[2] == "castle_escape_v1"
    environment = create_environment("castle-escape", "castle-escape-hard-zh")
    assert isinstance(environment, CastleHardEnvironment)
    assert environment.identity[:2] == ("castle-escape", "castle-escape-hard-zh")
    assert environment.identity[2] == "castle_escape_hard"


def test_castle_easy_public_passage_escapes_in_13_steps() -> None:
    environment = create_environment("castle-escape", "castle-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "gate_hall"

    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "armory")
    assert (
        step(environment, {"tool": "inspect", "target": "armory_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "iron_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "storm_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "forge_room")
    assert (
        step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "throne_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "CROWN-142" in (result.summary or "")
    move_to(environment, "moat_dock")
    assert (
        step(environment, {"tool": "use", "item": "CROWN-142", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_castle_medium_public_passage_escapes_in_19_steps() -> None:
    environment = create_environment("castle-escape", "castle-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "gate_hall"

    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "armory")
    assert (
        step(environment, {"tool": "inspect", "target": "armory_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "iron_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "storm_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "forge_room")
    assert (
        step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "watch_nook", "stone_tunnel", "gate_hall")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "throne_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "CROWN-386" in (result.summary or "")
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "moat_dock")
    assert (
        step(environment, {"tool": "use", "item": "CROWN-386", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_castle_hard_public_passage_escapes_in_21_steps() -> None:
    environment = create_environment("castle-escape", "castle-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "gate_hall"

    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "armory", "dungeon_vault")
    assert (
        step(environment, {"tool": "inspect", "target": "armory_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "iron_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "storm_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "armory", "forge_room")
    assert (
        step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "watch_nook", "stone_tunnel", "gate_hall")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "throne_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "CROWN-927" in (result.summary or "")
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "moat_dock")
    assert (
        step(environment, {"tool": "use", "item": "CROWN-927", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_castle_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("castle-escape", "castle-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "tapestry_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "moat_dock"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "armory")
    assert (
        rejected(environment, {"tool": "pickup", "item": "iron_key"})
        is ToolReason.NOT_REVEALED
    )


def test_castle_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("castle-escape", "castle-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "tower_deck")
    assert step(environment, {"tool": "inspect", "target": "far_glass"}) is ToolReason.INSPECTED
    move_to(environment, "guard_cell")
    assert step(environment, {"tool": "inspect", "target": "straw_bed"}) is ToolReason.INSPECTED
    move_to(environment, "tower_deck", "forge_room", "armory")
    step(environment, {"tool": "inspect", "target": "armory_chest"})
    assert step(environment, {"tool": "pickup", "item": "cloth_strip"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "cloth_strip", "target": "furnace_lid"})
        is ToolReason.WRONG_TARGET
    )


def test_castle_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("castle-escape", "castle-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "armory", "dungeon_vault")
    step(environment, {"tool": "inspect", "target": "armory_chest"})
    step(environment, {"tool": "pickup", "item": "iron_key"})
    step(environment, {"tool": "pickup", "item": "storm_cell"})
    step(environment, {"tool": "pickup", "item": "bent_nail"})
    move_to(environment, "armory", "forge_room")

    assert (
        rejected(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
    step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
    move_to(environment, "watch_nook", "stone_tunnel", "stable")
    assert step(environment, {"tool": "inspect", "target": "rusty_shoe"}) is ToolReason.INSPECTED
    move_to(environment, "stone_tunnel", "gate_hall")
    step(environment, {"tool": "read_terminal", "target": "throne_console"})
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "moat_dock")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "secret_boat"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "CROWN-927", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
