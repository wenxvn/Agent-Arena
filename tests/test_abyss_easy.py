from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.abyss import AbyssEasyEnvironment, load_abyss_easy_definition


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: AbyssEasyEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(environment: AbyssEasyEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: AbyssEasyEnvironment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_abyss_easy_definition_has_six_rooms_and_bidirectional_exits() -> None:
    definition = load_abyss_easy_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "abyss_escape_easy"
    assert len(rooms) == 6
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_abyss_easy_identity_matches_registered_selector() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-easy-zh")
    assert isinstance(environment, AbyssEasyEnvironment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-easy-zh")
    assert environment.identity[2] == "abyss_escape_easy"


def test_abyss_easy_public_passage_escapes_in_thirteen_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "docking_bay"

    move_to(environment, "cargo_hold")
    assert (
        step(environment, {"tool": "inspect", "target": "supply_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "fusion_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "docking_bay", "central_tunnel", "repair_nook", "reactor_trench")
    assert (
        step(environment, {"tool": "use", "item": "torque_wrench", "target": "hatch_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "fusion_cell", "target": "flooded_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "command_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ABYSS-102" in (result.summary or "")
    move_to(environment, "escape_capsule")
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-102", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_abyss_easy_terminal_rules_and_gated_capsule() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "status_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "escape_capsule"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "cargo_hold")
    assert (
        rejected(environment, {"tool": "pickup", "item": "torque_wrench"})
        is ToolReason.NOT_REVEALED
    )
