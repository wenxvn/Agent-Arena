from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.volcano import (
    VolcanoEasyEnvironment,
    VolcanoEnvironment,
    VolcanoHardEnvironment,
    load_volcano_definition,
    load_volcano_easy_definition,
    load_volcano_hard_definition,
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


def test_volcano_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_volcano_easy_definition, "volcano_escape_easy", 6),
        (load_volcano_definition, "volcano_escape_v1", 8),
        (load_volcano_hard_definition, "volcano_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_volcano_identities_match_registered_selectors() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-easy-zh")
    assert isinstance(environment, VolcanoEasyEnvironment)
    assert environment.identity[:2] == ("volcano-escape", "volcano-escape-easy-zh")
    assert environment.identity[2] == "volcano_escape_easy"
    environment = create_environment("volcano-escape", "volcano-escape-v1-zh")
    assert isinstance(environment, VolcanoEnvironment)
    assert environment.identity[:2] == ("volcano-escape", "volcano-escape-v1-zh")
    assert environment.identity[2] == "volcano_escape_v1"
    environment = create_environment("volcano-escape", "volcano-escape-hard-zh")
    assert isinstance(environment, VolcanoHardEnvironment)
    assert environment.identity[:2] == ("volcano-escape", "volcano-escape-hard-zh")
    assert environment.identity[2] == "volcano_escape_hard"


def test_volcano_easy_public_passage_escapes_in_13_steps() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "base_lobby"

    move_to(environment, "equip_store")
    assert (
        step(environment, {"tool": "inspect", "target": "equip_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "hex_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "thermo_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "base_lobby", "lava_tunnel", "seismic_nook", "turbine_room")
    assert (
        step(environment, {"tool": "use", "item": "hex_key", "target": "vent_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "thermo_cell", "target": "cracked_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "observatory_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "MAGMA-203" in (result.summary or "")
    move_to(environment, "cable_station")
    assert (
        step(environment, {"tool": "use", "item": "MAGMA-203", "target": "cable_car"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_volcano_medium_public_passage_escapes_in_19_steps() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "base_lobby"

    move_to(environment, "equip_store")
    assert (
        step(environment, {"tool": "inspect", "target": "equip_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "hex_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "thermo_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "base_lobby", "lava_tunnel", "seismic_nook", "turbine_room")
    assert (
        step(environment, {"tool": "use", "item": "hex_key", "target": "vent_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "thermo_cell", "target": "cracked_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "seismic_nook", "lava_tunnel", "base_lobby")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "observatory_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "MAGMA-515" in (result.summary or "")
    move_to(environment, "lava_tunnel", "seismic_nook", "turbine_room", "cable_station")
    assert (
        step(environment, {"tool": "use", "item": "MAGMA-515", "target": "cable_car"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_volcano_hard_public_passage_escapes_in_17_steps() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "base_lobby"

    move_to(environment, "equip_store", "ash_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "equip_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "hex_key"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "thermo_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "equip_store", "base_lobby", "lava_tunnel", "seismic_nook", "turbine_room")
    assert (
        step(environment, {"tool": "use", "item": "hex_key", "target": "vent_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "thermo_cell", "target": "cracked_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "seismic_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "observatory_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "MAGMA-948" in (result.summary or "")
    move_to(environment, "turbine_room", "cable_station")
    assert (
        step(environment, {"tool": "use", "item": "MAGMA-948", "target": "cable_car"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_volcano_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "poster_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "cable_station"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "equip_store")
    assert (
        rejected(environment, {"tool": "pickup", "item": "hex_key"})
        is ToolReason.NOT_REVEALED
    )


def test_volcano_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "lava_tunnel", "seismic_nook", "crater_deck")
    assert step(environment, {"tool": "inspect", "target": "fixed_scope"}) is ToolReason.INSPECTED
    move_to(environment, "rest_pod")
    assert step(environment, {"tool": "inspect", "target": "cot"}) is ToolReason.INSPECTED
    move_to(environment, "crater_deck", "seismic_nook", "lava_tunnel", "base_lobby", "equip_store")
    step(environment, {"tool": "inspect", "target": "equip_crate"})
    assert step(environment, {"tool": "pickup", "item": "spare_rope"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "spare_rope", "target": "vent_cover"})
        is ToolReason.WRONG_TARGET
    )


def test_volcano_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("volcano-escape", "volcano-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "equip_store", "ash_cellar")
    step(environment, {"tool": "inspect", "target": "equip_crate"})
    step(environment, {"tool": "pickup", "item": "hex_key"})
    step(environment, {"tool": "pickup", "item": "thermo_cell"})
    step(environment, {"tool": "pickup", "item": "burnt_filter"})
    move_to(environment, "equip_store", "base_lobby", "lava_tunnel", "seismic_nook", "turbine_room")

    assert (
        rejected(environment, {"tool": "use", "item": "thermo_cell", "target": "cracked_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "hex_key", "target": "vent_cover"})
    step(environment, {"tool": "use", "item": "thermo_cell", "target": "cracked_cell"})
    move_to(environment, "seismic_nook", "sample_room")
    assert step(environment, {"tool": "inspect", "target": "dull_drill"}) is ToolReason.INSPECTED
    move_to(environment, "seismic_nook")
    step(environment, {"tool": "read_terminal", "target": "observatory_console"})
    move_to(environment, "turbine_room", "cable_station")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "cable_car"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "MAGMA-948", "target": "cable_car"})
        is ToolReason.ESCAPED
    )
