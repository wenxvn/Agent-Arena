from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.jungle import (
    JungleEasyEnvironment,
    JungleEnvironment,
    JungleHardEnvironment,
    load_jungle_definition,
    load_jungle_easy_definition,
    load_jungle_hard_definition,
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


def test_jungle_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_jungle_easy_definition, "jungle_escape_easy", 6),
        (load_jungle_definition, "jungle_escape_v1", 8),
        (load_jungle_hard_definition, "jungle_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_jungle_identities_match_registered_selectors() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-easy-zh")
    assert isinstance(environment, JungleEasyEnvironment)
    assert environment.identity[:2] == ("jungle-escape", "jungle-escape-easy-zh")
    assert environment.identity[2] == "jungle_escape_easy"
    environment = create_environment("jungle-escape", "jungle-escape-v1-zh")
    assert isinstance(environment, JungleEnvironment)
    assert environment.identity[:2] == ("jungle-escape", "jungle-escape-v1-zh")
    assert environment.identity[2] == "jungle_escape_v1"
    environment = create_environment("jungle-escape", "jungle-escape-hard-zh")
    assert isinstance(environment, JungleHardEnvironment)
    assert environment.identity[:2] == ("jungle-escape", "jungle-escape-hard-zh")
    assert environment.identity[2] == "jungle_escape_hard"


def test_jungle_easy_public_passage_escapes_in_13_steps() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "camp_clearing"

    move_to(environment, "vine_tunnel", "ranger_nook", "cache_store")
    assert (
        step(environment, {"tool": "inspect", "target": "cache_box"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "machete"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "solar_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "ranger_nook", "temple_engine")
    assert (
        step(environment, {"tool": "use", "item": "machete", "target": "mossy_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "solar_cell", "target": "dead_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "altar_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "VINE-126" in (result.summary or "")
    move_to(environment, "river_pier")
    assert (
        step(environment, {"tool": "use", "item": "VINE-126", "target": "river_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_jungle_medium_public_passage_escapes_in_20_steps() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "camp_clearing"

    move_to(environment, "vine_tunnel", "cache_store")
    assert (
        step(environment, {"tool": "inspect", "target": "cache_box"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "machete"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "solar_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "ranger_nook", "temple_engine")
    assert (
        step(environment, {"tool": "use", "item": "machete", "target": "mossy_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "solar_cell", "target": "dead_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "ranger_nook", "cache_store", "vine_tunnel", "camp_clearing")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "altar_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "VINE-463" in (result.summary or "")
    move_to(environment, "vine_tunnel", "cache_store", "ranger_nook", "temple_engine", "river_pier")
    assert (
        step(environment, {"tool": "use", "item": "VINE-463", "target": "river_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_jungle_hard_public_passage_escapes_in_22_steps() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "camp_clearing"

    move_to(environment, "vine_tunnel", "cache_store", "root_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "cache_box"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "machete"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "solar_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "cache_store", "ranger_nook", "temple_engine")
    assert (
        step(environment, {"tool": "use", "item": "machete", "target": "mossy_hatch"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "solar_cell", "target": "dead_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "ranger_nook", "cache_store", "vine_tunnel", "camp_clearing")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "altar_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "VINE-791" in (result.summary or "")
    move_to(environment, "vine_tunnel", "cache_store", "ranger_nook", "temple_engine", "river_pier")
    assert (
        step(environment, {"tool": "use", "item": "VINE-791", "target": "river_boat"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_jungle_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "broken_sign"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "river_pier"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "vine_tunnel", "ranger_nook", "cache_store")
    assert (
        rejected(environment, {"tool": "pickup", "item": "machete"})
        is ToolReason.NOT_REVEALED
    )


def test_jungle_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "vine_tunnel", "canopy_deck")
    assert step(environment, {"tool": "inspect", "target": "old_scope"}) is ToolReason.INSPECTED
    move_to(environment, "hammock_hut")
    assert step(environment, {"tool": "inspect", "target": "hammock"}) is ToolReason.INSPECTED
    move_to(environment, "canopy_deck", "vine_tunnel", "cache_store")
    step(environment, {"tool": "inspect", "target": "cache_box"})
    assert step(environment, {"tool": "pickup", "item": "vine_rope"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "vine_rope", "target": "mossy_hatch"})
        is ToolReason.WRONG_TARGET
    )


def test_jungle_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("jungle-escape", "jungle-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "vine_tunnel", "cache_store", "root_cellar")
    step(environment, {"tool": "inspect", "target": "cache_box"})
    step(environment, {"tool": "pickup", "item": "machete"})
    step(environment, {"tool": "pickup", "item": "solar_cell"})
    step(environment, {"tool": "pickup", "item": "wet_matches"})
    move_to(environment, "cache_store", "ranger_nook", "temple_engine")

    assert (
        rejected(environment, {"tool": "use", "item": "solar_cell", "target": "dead_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "machete", "target": "mossy_hatch"})
    step(environment, {"tool": "use", "item": "solar_cell", "target": "dead_cell"})
    move_to(environment, "ranger_nook", "mill_room")
    assert step(environment, {"tool": "inspect", "target": "jammed_wheel"}) is ToolReason.INSPECTED
    move_to(environment, "ranger_nook", "cache_store", "vine_tunnel", "camp_clearing")
    step(environment, {"tool": "read_terminal", "target": "altar_console"})
    move_to(environment, "vine_tunnel", "cache_store", "ranger_nook", "temple_engine", "river_pier")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "river_boat"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "VINE-791", "target": "river_boat"})
        is ToolReason.ESCAPED
    )
