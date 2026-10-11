from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.lighthouse import LighthouseV2Environment, load_lighthouse_v2_definition


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: LighthouseV2Environment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def rejected(
    environment: LighthouseV2Environment, payload: Mapping[str, Any]
) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.REJECTED
    return result.reason


def move_to(environment: LighthouseV2Environment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def test_lighthouse_v2_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_lighthouse_v2_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "lighthouse_escape_v2"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_lighthouse_v2_identity_matches_registered_selector() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v2-zh")
    assert isinstance(environment, LighthouseV2Environment)
    assert environment.identity[:2] == ("lighthouse-escape", "lighthouse-escape-v2-zh")
    assert environment.identity[2] == "lighthouse_escape_v2"


def test_lighthouse_v2_public_passage_escapes_in_sixteen_steps() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v2-zh")
    observation = environment.reset(0)
    assert observation.current_room == "cliff_base"

    move_to(environment, "supply_shed", "storage_cellar")
    assert step(environment, {"tool": "inspect", "target": "tool_chest"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "spare_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "supply_shed", "cliff_base", "workshop_path", "engine_cave")
    assert (
        step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "lamp_room")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "lamp_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "TIDE-3160" in (result.summary or "")
    move_to(environment, "engine_cave", "skiff_cove")
    assert (
        step(environment, {"tool": "use", "item": "TIDE-3160", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lighthouse_v2_decoys_and_gated_cove() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v2-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "move", "destination": "skiff_cove"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "tide_pool")
    assert step(environment, {"tool": "inspect", "target": "tidal_rock"}) is ToolReason.INSPECTED
    move_to(environment, "cliff_base", "supply_shed", "storage_cellar")
    assert (
        rejected(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.NOT_REVEALED
    )
    step(environment, {"tool": "inspect", "target": "tool_chest"})
    assert step(environment, {"tool": "pickup", "item": "barnacle_glue"}) is ToolReason.PICKED_UP
    assert (
        rejected(
            environment, {"tool": "use", "item": "barnacle_glue", "target": "engine_cover"}
        )
        is ToolReason.WRONG_TARGET
    )


def test_lighthouse_v2_old_code_is_rejected() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "supply_shed", "storage_cellar")
    step(environment, {"tool": "inspect", "target": "tool_chest"})
    step(environment, {"tool": "pickup", "item": "wrench"})
    step(environment, {"tool": "pickup", "item": "spare_cell"})
    move_to(environment, "supply_shed", "cliff_base", "workshop_path", "engine_cave")
    step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
    step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
    move_to(environment, "lamp_room")
    step(environment, {"tool": "read_terminal", "target": "lamp_console"})
    move_to(environment, "engine_cave", "skiff_cove")
    assert (
        rejected(environment, {"tool": "use", "item": "TIDE-2049", "target": "harbor_skiff"})
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "TIDE-3160", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
