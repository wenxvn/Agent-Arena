from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.lighthouse import (
    LighthouseV3Environment,
    load_lighthouse_v3_definition,
)


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: LighthouseV3Environment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(
    environment: LighthouseV3Environment, payload: Mapping[str, Any]
) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: LighthouseV3Environment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_lighthouse_hard_definition_has_ten_rooms_and_bidirectional_exits() -> None:
    definition = load_lighthouse_v3_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "lighthouse_escape_v3"
    assert len(rooms) == 10
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_lighthouse_hard_identity_matches_registered_selector() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v3-zh")
    assert isinstance(environment, LighthouseV3Environment)
    assert environment.identity[:2] == ("lighthouse-escape", "lighthouse-escape-v3-zh")
    assert environment.identity[2] == "lighthouse_escape_v3"


def test_lighthouse_hard_public_passage_escapes_in_twenty_steps() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v3-zh")
    observation = environment.reset(0)
    assert observation.current_room == "cliff_base"

    move_to(environment, "supply_shed", "storage_cellar", "smuggler_nook")
    assert step(environment, {"tool": "inspect", "target": "tool_chest"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "spare_cell"}) is ToolReason.PICKED_UP
    move_to(
        environment, "storage_cellar", "supply_shed", "cliff_base", "workshop_path", "engine_cave"
    )
    assert (
        step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "lamp_room", "signal_tower")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "lamp_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "TIDE-5280" in (result.summary or "")
    move_to(environment, "lamp_room", "engine_cave", "skiff_cove")
    assert (
        step(environment, {"tool": "use", "item": "TIDE-5280", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lighthouse_hard_decoys_and_gated_cove() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v3-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "move", "destination": "skiff_cove"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "supply_shed", "storage_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "empty_barrel"})
        is ToolReason.INSPECTED
    )
    move_to(environment, "smuggler_nook")
    step(environment, {"tool": "inspect", "target": "tool_chest"})
    assert step(environment, {"tool": "pickup", "item": "fishing_hook"}) is ToolReason.PICKED_UP
    assert (
        rejected(
            environment, {"tool": "use", "item": "fishing_hook", "target": "engine_cover"}
        )
        is ToolReason.WRONG_TARGET
    )
    move_to(
        environment,
        "storage_cellar",
        "supply_shed",
        "cliff_base",
        "workshop_path",
        "engine_cave",
        "lamp_room",
    )
    assert (
        step(environment, {"tool": "inspect", "target": "burnt_bulb"}) is ToolReason.INSPECTED
    )
