from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.subway import (
    SubwayEasyEnvironment,
    SubwayEnvironment,
    SubwayHardEnvironment,
    load_subway_definition,
    load_subway_easy_definition,
    load_subway_hard_definition,
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


def test_subway_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_subway_easy_definition, "subway_escape_easy", 6),
        (load_subway_definition, "subway_escape_v1", 8),
        (load_subway_hard_definition, "subway_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_subway_identities_match_registered_selectors() -> None:
    environment = create_environment("subway-escape", "subway-escape-easy-zh")
    assert isinstance(environment, SubwayEasyEnvironment)
    assert environment.identity[:2] == ("subway-escape", "subway-escape-easy-zh")
    assert environment.identity[2] == "subway_escape_easy"
    environment = create_environment("subway-escape", "subway-escape-v1-zh")
    assert isinstance(environment, SubwayEnvironment)
    assert environment.identity[:2] == ("subway-escape", "subway-escape-v1-zh")
    assert environment.identity[2] == "subway_escape_v1"
    environment = create_environment("subway-escape", "subway-escape-hard-zh")
    assert isinstance(environment, SubwayHardEnvironment)
    assert environment.identity[:2] == ("subway-escape", "subway-escape-hard-zh")
    assert environment.identity[2] == "subway_escape_hard"


def test_subway_easy_public_passage_escapes_in_13_steps() -> None:
    environment = create_environment("subway-escape", "subway-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "concourse"

    move_to(environment, "main_tunnel", "locker_room")
    assert (
        step(environment, {"tool": "inspect", "target": "toolbox"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "crowbar"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "power_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "main_tunnel", "service_nook", "power_room")
    assert (
        step(environment, {"tool": "use", "item": "crowbar", "target": "cabinet_door"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "power_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "dispatch_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "METRO-118" in (result.summary or "")
    move_to(environment, "siding_track")
    assert (
        step(environment, {"tool": "use", "item": "METRO-118", "target": "service_train"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_subway_medium_public_passage_escapes_in_15_steps() -> None:
    environment = create_environment("subway-escape", "subway-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "concourse"

    move_to(environment, "main_tunnel", "locker_room")
    assert (
        step(environment, {"tool": "inspect", "target": "toolbox"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "crowbar"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "power_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "main_tunnel", "service_nook", "power_room")
    assert (
        step(environment, {"tool": "use", "item": "crowbar", "target": "cabinet_door"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "power_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "service_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "dispatch_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "METRO-440" in (result.summary or "")
    move_to(environment, "power_room", "siding_track")
    assert (
        step(environment, {"tool": "use", "item": "METRO-440", "target": "service_train"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_subway_hard_public_passage_escapes_in_21_steps() -> None:
    environment = create_environment("subway-escape", "subway-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "concourse"

    move_to(environment, "main_tunnel", "locker_room", "storage_room")
    assert (
        step(environment, {"tool": "inspect", "target": "toolbox"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "crowbar"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "power_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "locker_room", "main_tunnel", "service_nook", "power_room")
    assert (
        step(environment, {"tool": "use", "item": "crowbar", "target": "cabinet_door"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "power_cell", "target": "burnt_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "service_nook", "main_tunnel", "concourse")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "dispatch_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "METRO-783" in (result.summary or "")
    move_to(environment, "main_tunnel", "service_nook", "power_room", "siding_track")
    assert (
        step(environment, {"tool": "use", "item": "METRO-783", "target": "service_train"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_subway_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("subway-escape", "subway-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "ad_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "siding_track"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "main_tunnel", "locker_room")
    assert (
        rejected(environment, {"tool": "pickup", "item": "crowbar"})
        is ToolReason.NOT_REVEALED
    )


def test_subway_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("subway-escape", "subway-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "main_tunnel", "service_nook", "mural_platform")
    assert step(environment, {"tool": "inspect", "target": "old_poster"}) is ToolReason.INSPECTED
    move_to(environment, "kiosk")
    assert step(environment, {"tool": "inspect", "target": "shutter"}) is ToolReason.INSPECTED
    move_to(environment, "mural_platform", "service_nook", "main_tunnel", "locker_room")
    step(environment, {"tool": "inspect", "target": "toolbox"})
    assert step(environment, {"tool": "pickup", "item": "duct_tape"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "duct_tape", "target": "cabinet_door"})
        is ToolReason.WRONG_TARGET
    )


def test_subway_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("subway-escape", "subway-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "main_tunnel", "locker_room", "storage_room")
    step(environment, {"tool": "inspect", "target": "toolbox"})
    step(environment, {"tool": "pickup", "item": "crowbar"})
    step(environment, {"tool": "pickup", "item": "power_cell"})
    step(environment, {"tool": "pickup", "item": "dead_bulb"})
    move_to(environment, "locker_room", "main_tunnel", "service_nook", "power_room")

    assert (
        rejected(environment, {"tool": "use", "item": "power_cell", "target": "burnt_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "crowbar", "target": "cabinet_door"})
    step(environment, {"tool": "use", "item": "power_cell", "target": "burnt_cell"})
    move_to(environment, "drain_room")
    assert step(environment, {"tool": "inspect", "target": "rusty_valve"}) is ToolReason.INSPECTED
    move_to(environment, "power_room", "service_nook", "main_tunnel", "concourse")
    step(environment, {"tool": "read_terminal", "target": "dispatch_console"})
    move_to(environment, "main_tunnel", "service_nook", "power_room", "siding_track")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "service_train"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "METRO-783", "target": "service_train"})
        is ToolReason.ESCAPED
    )
