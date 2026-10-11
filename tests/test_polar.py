from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.polar import (
    PolarEasyEnvironment,
    PolarEnvironment,
    PolarHardEnvironment,
    load_polar_definition,
    load_polar_easy_definition,
    load_polar_hard_definition,
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


def test_polar_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_polar_easy_definition, "polar_escape_easy", 6),
        (load_polar_definition, "polar_escape_v1", 8),
        (load_polar_hard_definition, "polar_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_polar_identities_match_registered_selectors() -> None:
    environment = create_environment("polar-escape", "polar-escape-easy-zh")
    assert isinstance(environment, PolarEasyEnvironment)
    assert environment.identity[:2] == ("polar-escape", "polar-escape-easy-zh")
    assert environment.identity[2] == "polar_escape_easy"
    environment = create_environment("polar-escape", "polar-escape-v1-zh")
    assert isinstance(environment, PolarEnvironment)
    assert environment.identity[:2] == ("polar-escape", "polar-escape-v1-zh")
    assert environment.identity[2] == "polar_escape_v1"
    environment = create_environment("polar-escape", "polar-escape-hard-zh")
    assert isinstance(environment, PolarHardEnvironment)
    assert environment.identity[:2] == ("polar-escape", "polar-escape-hard-zh")
    assert environment.identity[2] == "polar_escape_hard"


def test_polar_easy_public_passage_escapes_in_11_steps() -> None:
    environment = create_environment("polar-escape", "polar-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "storm_hall"

    move_to(environment, "gear_store")
    assert (
        step(environment, {"tool": "inspect", "target": "gear_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "ice_axe"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "heater_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "weather_nook", "generator_cave")
    assert (
        step(environment, {"tool": "use", "item": "ice_axe", "target": "engine_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "heater_cell", "target": "frozen_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "comm_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "POLAR-214" in (result.summary or "")
    move_to(environment, "escape_ridge")
    assert (
        step(environment, {"tool": "use", "item": "POLAR-214", "target": "snow_tractor"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_polar_medium_public_passage_escapes_in_19_steps() -> None:
    environment = create_environment("polar-escape", "polar-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "storm_hall"

    move_to(environment, "ice_tunnel", "weather_nook", "generator_cave", "gear_store")
    assert (
        step(environment, {"tool": "inspect", "target": "gear_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "ice_axe"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "heater_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "generator_cave")
    assert (
        step(environment, {"tool": "use", "item": "ice_axe", "target": "engine_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "heater_cell", "target": "frozen_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "weather_nook", "ice_tunnel", "storm_hall")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "comm_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "POLAR-537" in (result.summary or "")
    move_to(environment, "ice_tunnel", "weather_nook", "generator_cave", "escape_ridge")
    assert (
        step(environment, {"tool": "use", "item": "POLAR-537", "target": "snow_tractor"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_polar_hard_public_passage_escapes_in_21_steps() -> None:
    environment = create_environment("polar-escape", "polar-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "storm_hall"

    move_to(environment, "ice_tunnel", "weather_nook", "gear_store", "ice_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "gear_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "ice_axe"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "heater_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "gear_store", "weather_nook", "generator_cave")
    assert (
        step(environment, {"tool": "use", "item": "ice_axe", "target": "engine_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "heater_cell", "target": "frozen_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "weather_nook", "ice_tunnel", "storm_hall")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "comm_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "POLAR-862" in (result.summary or "")
    move_to(environment, "ice_tunnel", "weather_nook", "generator_cave", "escape_ridge")
    assert (
        step(environment, {"tool": "use", "item": "POLAR-862", "target": "snow_tractor"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_polar_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("polar-escape", "polar-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "notice_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "escape_ridge"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "gear_store")
    assert (
        rejected(environment, {"tool": "pickup", "item": "ice_axe"})
        is ToolReason.NOT_REVEALED
    )


def test_polar_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("polar-escape", "polar-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "ice_tunnel", "aurora_deck")
    assert step(environment, {"tool": "inspect", "target": "telescope"}) is ToolReason.INSPECTED
    move_to(environment, "sleep_pod")
    assert step(environment, {"tool": "inspect", "target": "cot"}) is ToolReason.INSPECTED
    move_to(environment, "aurora_deck", "ice_tunnel", "weather_nook", "generator_cave", "gear_store")
    step(environment, {"tool": "inspect", "target": "gear_crate"})
    assert step(environment, {"tool": "pickup", "item": "rope_coil"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "rope_coil", "target": "engine_hatch"})
        is ToolReason.WRONG_TARGET
    )


def test_polar_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("polar-escape", "polar-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "ice_tunnel", "weather_nook", "gear_store", "ice_cellar")
    step(environment, {"tool": "inspect", "target": "gear_crate"})
    step(environment, {"tool": "pickup", "item": "ice_axe"})
    step(environment, {"tool": "pickup", "item": "heater_cell"})
    step(environment, {"tool": "pickup", "item": "torn_tent"})
    move_to(environment, "gear_store", "weather_nook", "generator_cave")

    assert (
        rejected(environment, {"tool": "use", "item": "heater_cell", "target": "frozen_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "ice_axe", "target": "engine_hatch"})
    step(environment, {"tool": "use", "item": "heater_cell", "target": "frozen_cell"})
    move_to(environment, "weather_nook", "drill_room")
    assert step(environment, {"tool": "inspect", "target": "rusty_drill"}) is ToolReason.INSPECTED
    move_to(environment, "weather_nook", "ice_tunnel", "storm_hall")
    step(environment, {"tool": "read_terminal", "target": "comm_console"})
    move_to(environment, "ice_tunnel", "weather_nook", "generator_cave", "escape_ridge")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "snow_tractor"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "POLAR-862", "target": "snow_tractor"})
        is ToolReason.ESCAPED
    )
