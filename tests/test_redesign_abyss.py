from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.abyss import (
    AbyssV2Environment,
    AbyssV3Environment,
    AbyssV4Environment,
    load_abyss_v2_definition,
    load_abyss_v3_definition,
    load_abyss_v4_definition,
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


def test_redesign_abyss_definitions_have_expected_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_abyss_v2_definition, "abyss_escape_v2", 6),
        (load_abyss_v3_definition, "abyss_escape_v3", 8),
        (load_abyss_v4_definition, "abyss_escape_v4", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_redesign_abyss_identities_match_registered_selectors() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v2-zh")
    assert isinstance(environment, AbyssV2Environment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-v2-zh")
    assert environment.identity[2] == "abyss_escape_v2"
    environment = create_environment("abyss-escape", "abyss-escape-v3-zh")
    assert isinstance(environment, AbyssV3Environment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-v3-zh")
    assert environment.identity[2] == "abyss_escape_v3"
    environment = create_environment("abyss-escape", "abyss-escape-v4-zh")
    assert isinstance(environment, AbyssV4Environment)
    assert environment.identity[:2] == ("abyss-escape", "abyss-escape-v4-zh")
    assert environment.identity[2] == "abyss_escape_v4"


def test_redesign_abyss_easy_shortcut_passage_escapes_in_twelve_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v2-zh")
    observation = environment.reset(0)
    assert observation.current_room == "docking_bay"

    move_to(environment, "repair_nook", "cargo_hold")
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
    result, _ = environment.step(action({"tool": "read_terminal", "target": "command_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ABYSS-210" in (result.summary or "")
    move_to(environment, "escape_capsule")
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-210", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_abyss_medium_capsule_next_to_start_escapes_in_sixteen_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v3-zh")
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
    result, _ = environment.step(action({"tool": "read_terminal", "target": "command_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ABYSS-320" in (result.summary or "")
    move_to(environment, "escape_capsule")
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-320", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_abyss_medium_early_capsule_visit_cannot_launch() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v3-zh")
    environment.reset(0)
    move_to(environment, "escape_capsule")
    assert (
        rejected(environment, {"tool": "use", "item": "ABYSS-320", "target": "escape_capsule"})
        is ToolReason.CODE_UNREAD
    )


def test_redesign_abyss_hard_loop_passage_escapes_in_seventeen_steps() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v4-zh")
    observation = environment.reset(0)
    assert observation.current_room == "docking_bay"

    move_to(environment, "central_tunnel", "cargo_hold", "deep_store")
    assert (
        step(environment, {"tool": "inspect", "target": "supply_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "fusion_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "cargo_hold", "central_tunnel", "deep_nook", "reactor_trench")
    assert (
        step(environment, {"tool": "use", "item": "torque_wrench", "target": "hatch_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "fusion_cell", "target": "flooded_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "deep_nook")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "command_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "ABYSS-430" in (result.summary or "")
    move_to(environment, "reactor_trench", "escape_capsule")
    assert (
        step(environment, {"tool": "use", "item": "ABYSS-430", "target": "escape_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_abyss_hard_decoys_do_not_block_passage() -> None:
    environment = create_environment("abyss-escape", "abyss-escape-v4-zh")
    environment.reset(0)
    move_to(environment, "central_tunnel", "cargo_hold")
    assert step(environment, {"tool": "inspect", "target": "empty_tank"}) is ToolReason.INSPECTED
    move_to(environment, "central_tunnel", "lookout_dome")
    assert step(environment, {"tool": "inspect", "target": "viewport"}) is ToolReason.INSPECTED
    move_to(environment, "bunk_pod")
    assert step(environment, {"tool": "inspect", "target": "bunk"}) is ToolReason.INSPECTED
