from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.flex import (
    PyramidV2SeededEnvironment,
    build_seeded_items,
    load_pyramid_v2_definition,
    load_pyramid_v2_seeded_definition,
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


def test_pyramid_v2_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_pyramid_v2_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "pyramid_escape_v2"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_pyramid_v2_identities_match_registered_selectors() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v2-zh")
    assert environment.identity[:2] == ("pyramid-escape", "pyramid-escape-v2-zh")
    assert environment.identity[2] == "pyramid_escape_v2"
    seeded = create_environment("pyramid-escape", "pyramid-escape-v2-seeded-zh")
    assert isinstance(seeded, PyramidV2SeededEnvironment)
    assert seeded.identity[:2] == ("pyramid-escape", "pyramid-escape-v2-seeded-zh")


def test_pyramid_v2_code_first_passage_escapes_in_sixteen_steps() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v2-zh")
    observation = environment.reset(0)
    assert observation.current_room == "entrance_hall"

    move_to(environment, "sand_tunnel", "survey_nook")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "glyph_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "SAND-260" in (result.summary or "")
    move_to(environment, "sand_tunnel", "relic_store")
    assert (
        step(environment, {"tool": "inspect", "target": "relic_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "chisel"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "sun_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "sand_tunnel", "survey_nook", "engine_crypt")
    assert (
        step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "skiff_dock")
    assert (
        step(environment, {"tool": "use", "item": "SAND-260", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_pyramid_v2_escape_still_needs_power() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "sand_tunnel", "survey_nook")
    step(environment, {"tool": "read_terminal", "target": "glyph_console"})
    move_to(environment, "engine_crypt", "skiff_dock")
    assert (
        rejected(environment, {"tool": "use", "item": "SAND-260", "target": "sand_skiff"})
        is ToolReason.NO_POWER
    )


def test_pyramid_v2_deep_decoy_does_not_block_passage() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "sand_tunnel", "survey_nook", "mural_hall", "priest_cell")
    assert step(environment, {"tool": "inspect", "target": "sealed_urn"}) is ToolReason.INSPECTED


def test_pyramid_v2_seeded_placement_is_deterministic_and_varies() -> None:
    definition = load_pyramid_v2_seeded_definition()
    first = build_seeded_items(definition, 7)
    second = build_seeded_items(definition, 7)
    assert [(item.id, item.container_id) for item in first] == [
        (item.id, item.container_id) for item in second
    ]
    placements = {
        tuple(sorted((item.id, item.container_id) for item in build_seeded_items(definition, s)))
        for s in range(10)
    }
    assert len(placements) >= 2


def test_pyramid_v2_seeded_instance_is_solvable() -> None:
    definition = load_pyramid_v2_seeded_definition()
    placement = {item.id: item.container_id for item in build_seeded_items(definition, 4)}
    environment = PyramidV2SeededEnvironment(seed=4)
    environment.reset(4)
    assert {item.id: item.container_id for item in environment._items.values()} == placement

    groups: dict[str, list[str]] = {}
    for tool, container in placement.items():
        groups.setdefault(container, []).append(tool)
    move_to(environment, "sand_tunnel", "survey_nook")
    step(environment, {"tool": "read_terminal", "target": "glyph_console"})
    move_to(environment, "sand_tunnel", "relic_store")
    step(environment, {"tool": "inspect", "target": "relic_chest"})
    for tool in groups.get("relic_chest", []):
        step(environment, {"tool": "pickup", "item": tool})
    move_to(environment, "sand_tunnel", "survey_nook", "mural_hall")
    step(environment, {"tool": "inspect", "target": "sand_crate"})
    for tool in groups.get("sand_crate", []):
        step(environment, {"tool": "pickup", "item": tool})
    move_to(environment, "survey_nook", "engine_crypt")
    step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
    step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
    move_to(environment, "skiff_dock")
    assert (
        step(environment, {"tool": "use", "item": "SAND-260", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
