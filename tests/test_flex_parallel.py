from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.flex import (
    CastleV2SeededEnvironment,
    build_seeded_items,
    load_castle_v2_definition,
    load_castle_v2_seeded_definition,
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


def test_castle_v2_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_castle_v2_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "castle_escape_v2"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_castle_v2_identities_match_registered_selectors() -> None:
    environment = create_environment("castle-escape", "castle-escape-v2-zh")
    assert environment.identity[:2] == ("castle-escape", "castle-escape-v2-zh")
    assert environment.identity[2] == "castle_escape_v2"
    seeded = create_environment("castle-escape", "castle-escape-v2-seeded-zh")
    assert isinstance(seeded, CastleV2SeededEnvironment)
    assert seeded.identity[:2] == ("castle-escape", "castle-escape-v2-seeded-zh")


def test_castle_v2_parallel_passage_escapes_in_twenty_two_steps() -> None:
    environment = create_environment("castle-escape", "castle-escape-v2-zh")
    observation = environment.reset(0)
    assert observation.current_room == "gate_hall"

    move_to(environment, "stone_tunnel", "armory")
    assert (
        step(environment, {"tool": "inspect", "target": "armory_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "iron_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "storm_cell"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "frost_core"}) is ToolReason.PICKED_UP
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room")
    assert (
        step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.CELL_STAGED
    )
    assert (
        step(environment, {"tool": "use", "item": "frost_core", "target": "frost_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "watch_nook", "stone_tunnel", "gate_hall")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "throne_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "CROWN-250" in (result.summary or "")
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "moat_dock")
    assert (
        step(environment, {"tool": "use", "item": "CROWN-250", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_castle_v2_missing_cell_keeps_power_off() -> None:
    environment = create_environment("castle-escape", "castle-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "stone_tunnel", "armory")
    step(environment, {"tool": "inspect", "target": "armory_chest"})
    step(environment, {"tool": "pickup", "item": "iron_key"})
    step(environment, {"tool": "pickup", "item": "storm_cell"})
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room")
    step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
    step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
    assert (
        rejected(environment, {"tool": "read_terminal", "target": "throne_console"})
        is ToolReason.NOT_VISIBLE
    )
    move_to(environment, "watch_nook", "stone_tunnel", "gate_hall")
    assert (
        rejected(environment, {"tool": "read_terminal", "target": "throne_console"})
        is ToolReason.NO_POWER
    )


def test_castle_v2_cell_before_panel_is_rejected() -> None:
    environment = create_environment("castle-escape", "castle-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "stone_tunnel", "armory")
    step(environment, {"tool": "inspect", "target": "armory_chest"})
    step(environment, {"tool": "pickup", "item": "iron_key"})
    step(environment, {"tool": "pickup", "item": "storm_cell"})
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room")
    assert (
        rejected(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
        is ToolReason.PANEL_CLOSED
    )


def test_castle_v2_deep_decoy_does_not_block_passage() -> None:
    environment = create_environment("castle-escape", "castle-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "stone_tunnel", "watch_nook", "tower_deck", "guard_cell")
    assert step(environment, {"tool": "inspect", "target": "rusty_armor"}) is ToolReason.INSPECTED


def test_castle_v2_seeded_placement_is_deterministic_and_varies() -> None:
    definition = load_castle_v2_seeded_definition()
    first = build_seeded_items(definition, 5)
    second = build_seeded_items(definition, 5)
    assert [(item.id, item.container_id) for item in first] == [
        (item.id, item.container_id) for item in second
    ]
    placements = {
        tuple(sorted((item.id, item.container_id) for item in build_seeded_items(definition, s)))
        for s in range(10)
    }
    assert len(placements) >= 2


def test_castle_v2_seeded_instance_is_solvable() -> None:
    definition = load_castle_v2_seeded_definition()
    placement = {item.id: item.container_id for item in build_seeded_items(definition, 2)}
    environment = CastleV2SeededEnvironment(seed=2)
    environment.reset(2)
    assert {item.id: item.container_id for item in environment._items.values()} == placement

    groups: dict[str, list[str]] = {}
    for tool, container in placement.items():
        groups.setdefault(container, []).append(tool)
    move_to(environment, "stone_tunnel", "armory")
    step(environment, {"tool": "inspect", "target": "armory_chest"})
    for tool in groups.get("armory_chest", []):
        step(environment, {"tool": "pickup", "item": tool})
    move_to(environment, "stone_tunnel", "watch_nook", "tower_deck")
    step(environment, {"tool": "inspect", "target": "old_crate"})
    for tool in groups.get("old_crate", []):
        step(environment, {"tool": "pickup", "item": tool})
    move_to(environment, "watch_nook", "forge_room")
    step(environment, {"tool": "use", "item": "iron_key", "target": "furnace_lid"})
    step(environment, {"tool": "use", "item": "storm_cell", "target": "cold_cell"})
    step(environment, {"tool": "use", "item": "frost_core", "target": "frost_cell"})
    move_to(environment, "watch_nook", "stone_tunnel", "gate_hall")
    step(environment, {"tool": "read_terminal", "target": "throne_console"})
    move_to(environment, "stone_tunnel", "watch_nook", "forge_room", "moat_dock")
    assert (
        step(environment, {"tool": "use", "item": "CROWN-250", "target": "secret_boat"})
        is ToolReason.ESCAPED
    )
