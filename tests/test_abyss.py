from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.abyss import AbyssEnvironment, load_abyss_definition


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: AbyssEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(environment: AbyssEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: AbyssEnvironment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_abyss_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_abyss_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "abyss_escape_v1"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_abyss_identity_matches_registered_selector() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v1-zh")
    assert isinstance(environment, AbyssEnvironment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-v1-zh")
    assert environment.identity[2] == "abyss_escape_v1"


def test_abyss_public_passage_escapes_in_nineteen_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "docking_bay"

    move_to(environment, "central_tunnel", "repair_nook", "cargo_hold")
    assert (
        step(environment, {"tool": "inspect", "target": "supply_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "fusion_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "repair_nook", "reactor_trench")
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
    assert "ABYSS-618" in (result.summary or "")
    move_to(environment, "central_tunnel", "repair_nook", "reactor_trench", "escape_capsule")
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-618", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_abyss_terminal_rules_and_gated_capsule() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v1-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "command_console"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "read_terminal", "target": "status_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "escape_capsule"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "central_tunnel", "repair_nook", "cargo_hold")
    assert (
        rejected(environment, {"tool": "pickup", "item": "torque_wrench"})
        is ToolReason.NOT_REVEALED
    )


def test_abyss_decoys_do_not_block_passage() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "central_tunnel", "lookout_dome")
    assert step(environment, {"tool": "inspect", "target": "viewport"}) is ToolReason.INSPECTED
    move_to(environment, "bunk_pod")
    assert step(environment, {"tool": "inspect", "target": "bunk"}) is ToolReason.INSPECTED
    move_to(environment, "lookout_dome", "central_tunnel", "repair_nook", "cargo_hold")
    step(environment, {"tool": "inspect", "target": "supply_crate"})
    assert step(environment, {"tool": "pickup", "item": "kelp_tape"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "kelp_tape", "target": "hatch_cover"})
        is ToolReason.WRONG_TARGET
    )


def test_abyss_repair_order_and_launch_guards() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "central_tunnel", "repair_nook", "cargo_hold")
    step(environment, {"tool": "inspect", "target": "supply_crate"})
    step(environment, {"tool": "pickup", "item": "torque_wrench"})
    step(environment, {"tool": "pickup", "item": "fusion_cell"})
    move_to(environment, "repair_nook", "reactor_trench")

    assert (
        rejected(environment, {"tool": "use", "item": "fusion_cell", "target": "flooded_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "torque_wrench", "target": "hatch_cover"})
    step(environment, {"tool": "use", "item": "fusion_cell", "target": "flooded_cell"})
    move_to(environment, "repair_nook", "central_tunnel", "docking_bay")
    step(environment, {"tool": "read_terminal", "target": "command_console"})
    move_to(
        environment, "central_tunnel", "repair_nook", "reactor_trench", "escape_capsule"
    )
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "escape_capsule"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-618", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
