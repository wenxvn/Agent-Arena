from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.pyramid import (
    PyramidEasyEnvironment,
    PyramidEnvironment,
    PyramidHardEnvironment,
    load_pyramid_definition,
    load_pyramid_easy_definition,
    load_pyramid_hard_definition,
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


def test_pyramid_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_pyramid_easy_definition, "pyramid_escape_easy", 6),
        (load_pyramid_definition, "pyramid_escape_v1", 8),
        (load_pyramid_hard_definition, "pyramid_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_pyramid_identities_match_registered_selectors() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-easy-zh")
    assert isinstance(environment, PyramidEasyEnvironment)
    assert environment.identity[:2] == ("pyramid-escape", "pyramid-escape-easy-zh")
    assert environment.identity[2] == "pyramid_escape_easy"
    environment = create_environment("pyramid-escape", "pyramid-escape-v1-zh")
    assert isinstance(environment, PyramidEnvironment)
    assert environment.identity[:2] == ("pyramid-escape", "pyramid-escape-v1-zh")
    assert environment.identity[2] == "pyramid_escape_v1"
    environment = create_environment("pyramid-escape", "pyramid-escape-hard-zh")
    assert isinstance(environment, PyramidHardEnvironment)
    assert environment.identity[:2] == ("pyramid-escape", "pyramid-escape-hard-zh")
    assert environment.identity[2] == "pyramid_escape_hard"


def test_pyramid_easy_public_passage_escapes_in_11_steps() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "entrance_hall"

    move_to(environment, "sand_tunnel", "relic_store")
    assert (
        step(environment, {"tool": "inspect", "target": "relic_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "chisel"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "sun_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "engine_crypt")
    assert (
        step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "glyph_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "SAND-107" in (result.summary or "")
    move_to(environment, "skiff_dock")
    assert (
        step(environment, {"tool": "use", "item": "SAND-107", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_pyramid_medium_public_passage_escapes_in_15_steps() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "entrance_hall"

    move_to(environment, "sand_tunnel", "relic_store")
    assert (
        step(environment, {"tool": "inspect", "target": "relic_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "chisel"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "sun_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "engine_crypt")
    assert (
        step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "relic_store", "sand_tunnel", "survey_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "glyph_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "SAND-429" in (result.summary or "")
    move_to(environment, "engine_crypt", "skiff_dock")
    assert (
        step(environment, {"tool": "use", "item": "SAND-429", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_pyramid_hard_public_passage_escapes_in_17_steps() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "entrance_hall"

    move_to(environment, "sand_tunnel", "relic_store", "burial_vault")
    assert (
        step(environment, {"tool": "inspect", "target": "relic_chest"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "chisel"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "sun_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "relic_store", "engine_crypt")
    assert (
        step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "relic_store", "sand_tunnel", "survey_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "glyph_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "SAND-756" in (result.summary or "")
    move_to(environment, "engine_crypt", "skiff_dock")
    assert (
        step(environment, {"tool": "use", "item": "SAND-756", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_pyramid_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "blank_stele"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "skiff_dock"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "sand_tunnel", "relic_store")
    assert (
        rejected(environment, {"tool": "pickup", "item": "chisel"})
        is ToolReason.NOT_REVEALED
    )


def test_pyramid_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "sand_tunnel", "relic_store", "mural_hall")
    assert step(environment, {"tool": "inspect", "target": "faded_mural"}) is ToolReason.INSPECTED
    move_to(environment, "priest_cell")
    assert step(environment, {"tool": "inspect", "target": "stone_bed"}) is ToolReason.INSPECTED
    move_to(environment, "mural_hall", "relic_store")
    step(environment, {"tool": "inspect", "target": "relic_chest"})
    assert step(environment, {"tool": "pickup", "item": "linen_wrap"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "linen_wrap", "target": "stone_slab"})
        is ToolReason.WRONG_TARGET
    )


def test_pyramid_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "sand_tunnel", "relic_store", "burial_vault")
    step(environment, {"tool": "inspect", "target": "relic_chest"})
    step(environment, {"tool": "pickup", "item": "chisel"})
    step(environment, {"tool": "pickup", "item": "sun_cell"})
    step(environment, {"tool": "pickup", "item": "cracked_amulet"})
    move_to(environment, "relic_store", "engine_crypt")

    assert (
        rejected(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "chisel", "target": "stone_slab"})
    step(environment, {"tool": "use", "item": "sun_cell", "target": "drained_cell"})
    move_to(environment, "relic_store", "sand_tunnel", "survey_nook", "well_room")
    assert step(environment, {"tool": "inspect", "target": "dry_winch"}) is ToolReason.INSPECTED
    move_to(environment, "survey_nook")
    step(environment, {"tool": "read_terminal", "target": "glyph_console"})
    move_to(environment, "engine_crypt", "skiff_dock")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "sand_skiff"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "SAND-756", "target": "sand_skiff"})
        is ToolReason.ESCAPED
    )
