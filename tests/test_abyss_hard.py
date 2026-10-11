from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.abyss import AbyssHardEnvironment, load_abyss_hard_definition


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: AbyssHardEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(environment: AbyssHardEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: AbyssHardEnvironment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_abyss_hard_definition_has_ten_rooms_and_bidirectional_exits() -> None:
    definition = load_abyss_hard_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "abyss_escape_hard"
    assert len(rooms) == 10
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_abyss_hard_identity_matches_registered_selector() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-hard-zh")
    assert isinstance(environment, AbyssHardEnvironment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-hard-zh")
    assert environment.identity[2] == "abyss_escape_hard"


def test_abyss_hard_public_passage_escapes_in_twenty_one_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "docking_bay"

    move_to(environment, "central_tunnel", "repair_nook", "cargo_hold", "deep_store")
    assert (
        step(environment, {"tool": "inspect", "target": "supply_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "fusion_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "cargo_hold", "repair_nook", "reactor_trench")
    assert (
        step(environment, {"tool": "use", "item": "torque_wrench", "target": "hatch_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "fusion_cell", "target": "flooded_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "repair_nook", "central_tunnel", "docking_bay")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "command_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ABYSS-909" in (result.summary or "")
    move_to(
        environment, "central_tunnel", "repair_nook", "reactor_trench", "escape_capsule"
    )
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-909", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_abyss_hard_decoys_do_not_block_passage() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "central_tunnel", "repair_nook", "pump_room")
    assert step(environment, {"tool": "inspect", "target": "rusty_valve"}) is ToolReason.INSPECTED
    move_to(environment, "repair_nook", "cargo_hold")
    assert step(environment, {"tool": "inspect", "target": "empty_tank"}) is ToolReason.INSPECTED
    move_to(environment, "deep_store")
    step(environment, {"tool": "inspect", "target": "supply_crate"})
    assert step(environment, {"tool": "pickup", "item": "torn_net"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "torn_net", "target": "hatch_cover"})
        is ToolReason.WRONG_TARGET
    )
