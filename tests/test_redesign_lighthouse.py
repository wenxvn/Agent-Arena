from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.lighthouse import (
    LighthouseV4Environment,
    LighthouseV5Environment,
    LighthouseV6Environment,
    load_lighthouse_v4_definition,
    load_lighthouse_v5_definition,
    load_lighthouse_v6_definition,
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


def test_redesign_lighthouse_definitions_have_expected_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_lighthouse_v4_definition, "lighthouse_escape_v4", 6),
        (load_lighthouse_v5_definition, "lighthouse_escape_v5", 8),
        (load_lighthouse_v6_definition, "lighthouse_escape_v6", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_redesign_lighthouse_identities_match_registered_selectors() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v4-zh")
    assert isinstance(environment, LighthouseV4Environment)
    assert environment.identity[:2] == ("lighthouse-escape", "lighthouse-escape-v4-zh")
    assert environment.identity[2] == "lighthouse_escape_v4"
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v5-zh")
    assert isinstance(environment, LighthouseV5Environment)
    assert environment.identity[:2] == ("lighthouse-escape", "lighthouse-escape-v5-zh")
    assert environment.identity[2] == "lighthouse_escape_v5"
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v6-zh")
    assert isinstance(environment, LighthouseV6Environment)
    assert environment.identity[:2] == ("lighthouse-escape", "lighthouse-escape-v6-zh")
    assert environment.identity[2] == "lighthouse_escape_v6"


def test_redesign_lighthouse_easy_forked_passage_escapes_in_thirteen_steps() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v4-zh")
    observation = environment.reset(0)
    assert observation.current_room == "cliff_base"

    move_to(environment, "workshop_path", "supply_shed")
    assert (
        step(environment, {"tool": "inspect", "target": "tool_chest"}) is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "spare_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "workshop_path", "engine_cave")
    assert (
        step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(action({"tool": "read_terminal", "target": "lamp_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "TIDE-310" in (result.summary or "")
    move_to(environment, "skiff_cove")
    assert (
        step(environment, {"tool": "use", "item": "TIDE-310", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_lighthouse_easy_dead_end_radio_and_decoy_terminal() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v4-zh")
    environment.reset(0)
    assert (
        rejected(environment, {"tool": "read_terminal", "target": "signal_board"})
        is ToolReason.NO_POWER
    )
    move_to(environment, "foam_path")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "field_radio"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.DIAGNOSTIC_READ


def test_redesign_lighthouse_medium_tower_code_passage_escapes_in_twenty_one_steps() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v5-zh")
    observation = environment.reset(0)
    assert observation.current_room == "cliff_base"

    move_to(environment, "tide_pool", "workshop_path", "supply_shed")
    assert (
        step(environment, {"tool": "inspect", "target": "tool_chest"}) is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "spare_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "workshop_path", "engine_cave")
    assert (
        step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "workshop_path", "tide_pool", "storage_cellar", "signal_tower")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "lamp_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "TIDE-420" in (result.summary or "")
    move_to(environment, "storage_cellar", "tide_pool", "workshop_path", "engine_cave", "skiff_cove")
    assert (
        step(environment, {"tool": "use", "item": "TIDE-420", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_lighthouse_hard_chain_passage_escapes_in_nineteen_steps() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v6-zh")
    observation = environment.reset(0)
    assert observation.current_room == "cliff_base"

    move_to(environment, "coast_path", "workshop_path", "supply_shed")
    assert (
        step(environment, {"tool": "inspect", "target": "tool_chest"}) is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "wrench"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "spare_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "workshop_path", "engine_cave")
    assert (
        step(environment, {"tool": "use", "item": "wrench", "target": "engine_cover"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "spare_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "workshop_path", "coast_path", "cliff_base")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "lamp_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "TIDE-530" in (result.summary or "")
    move_to(environment, "coast_path", "workshop_path", "engine_cave", "skiff_cove")
    assert (
        step(environment, {"tool": "use", "item": "TIDE-530", "target": "harbor_skiff"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_redesign_lighthouse_hard_decoys_do_not_block_passage() -> None:
    environment = create_environment("lighthouse-escape", "lighthouse-escape-v6-zh")
    environment.reset(0)
    move_to(environment, "coast_path", "tide_pool")
    assert step(environment, {"tool": "inspect", "target": "empty_barrel"}) is ToolReason.INSPECTED
    move_to(environment, "sleep_pod")
    assert step(environment, {"tool": "inspect", "target": "cot"}) is ToolReason.INSPECTED
    move_to(environment, "tide_pool", "coast_path", "workshop_path", "anchor_room")
    assert step(environment, {"tool": "inspect", "target": "rusty_anchor"}) is ToolReason.INSPECTED
    move_to(environment, "sail_loft")
    assert step(environment, {"tool": "inspect", "target": "torn_sail"}) is ToolReason.INSPECTED
