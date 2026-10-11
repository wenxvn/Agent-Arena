from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.lunar import (
    LunarEasyEnvironment,
    LunarEnvironment,
    LunarHardEnvironment,
    load_lunar_definition,
    load_lunar_easy_definition,
    load_lunar_hard_definition,
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


def test_lunar_definitions_have_expected_room_counts_and_bidirectional_exits() -> None:
    cases = [
        (load_lunar_easy_definition, "lunar_escape_easy", 6),
        (load_lunar_definition, "lunar_escape_v1", 8),
        (load_lunar_hard_definition, "lunar_escape_hard", 10),
    ]
    for loader, world_id, count in cases:
        definition = loader()
        rooms = {room.id: room for room in definition.rooms}
        assert definition.world_id == world_id
        assert len(rooms) == count
        for room in rooms.values():
            for destination in room.exits:
                assert room.id in rooms[destination].exits


def test_lunar_identities_match_registered_selectors() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-easy-zh")
    assert isinstance(environment, LunarEasyEnvironment)
    assert environment.identity[:2] == ("lunar-escape", "lunar-escape-easy-zh")
    assert environment.identity[2] == "lunar_escape_easy"
    environment = create_environment("lunar-escape", "lunar-escape-v1-zh")
    assert isinstance(environment, LunarEnvironment)
    assert environment.identity[:2] == ("lunar-escape", "lunar-escape-v1-zh")
    assert environment.identity[2] == "lunar_escape_v1"
    environment = create_environment("lunar-escape", "lunar-escape-hard-zh")
    assert isinstance(environment, LunarHardEnvironment)
    assert environment.identity[:2] == ("lunar-escape", "lunar-escape-hard-zh")
    assert environment.identity[2] == "lunar_escape_hard"


def test_lunar_easy_public_passage_escapes_in_12_steps() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-easy-zh")
    observation = environment.reset(0)
    assert observation.current_room == "airlock_hall"

    move_to(environment, "regolith_tunnel", "depot_store")
    assert (
        step(environment, {"tool": "inspect", "target": "depot_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_driver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "oxy_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "telemetry_nook", "reactor_bay")
    assert (
        step(environment, {"tool": "use", "item": "torque_driver", "target": "bay_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "oxy_cell", "target": "spent_cell"})
        is ToolReason.POWER_RESTORED
    )
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "mission_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "LUNAR-134" in (result.summary or "")
    move_to(environment, "launch_pad")
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-134", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lunar_medium_public_passage_escapes_in_14_steps() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v1-zh")
    observation = environment.reset(0)
    assert observation.current_room == "airlock_hall"

    move_to(environment, "regolith_tunnel", "depot_store")
    assert (
        step(environment, {"tool": "inspect", "target": "depot_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_driver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "oxy_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "telemetry_nook", "reactor_bay")
    assert (
        step(environment, {"tool": "use", "item": "torque_driver", "target": "bay_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "oxy_cell", "target": "spent_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "telemetry_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "mission_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "LUNAR-572" in (result.summary or "")
    move_to(environment, "reactor_bay", "launch_pad")
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-572", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lunar_hard_public_passage_escapes_in_16_steps() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-hard-zh")
    observation = environment.reset(0)
    assert observation.current_room == "airlock_hall"

    move_to(environment, "regolith_tunnel", "depot_store", "crater_cellar")
    assert (
        step(environment, {"tool": "inspect", "target": "depot_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_driver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "oxy_cell"}) is ToolReason.PICKED_UP
    move_to(environment, "depot_store", "telemetry_nook", "reactor_bay")
    assert (
        step(environment, {"tool": "use", "item": "torque_driver", "target": "bay_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "oxy_cell", "target": "spent_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "telemetry_nook")
    result, _ = environment.step(
        action({"tool": "read_terminal", "target": "mission_console"})
    )
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "LUNAR-908" in (result.summary or "")
    move_to(environment, "reactor_bay", "launch_pad")
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-908", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lunar_terminal_rules_and_gated_escape() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-easy-zh")
    environment.reset(0)

    assert (
        rejected(environment, {"tool": "read_terminal", "target": "mission_board"})
        is ToolReason.NO_POWER
    )
    assert (
        rejected(environment, {"tool": "move", "destination": "launch_pad"})
        is ToolReason.NOT_ADJACENT
    )
    move_to(environment, "regolith_tunnel", "depot_store")
    assert (
        rejected(environment, {"tool": "pickup", "item": "torque_driver"})
        is ToolReason.NOT_REVEALED
    )


def test_lunar_medium_decoys_do_not_block_passage() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v1-zh")
    environment.reset(0)
    move_to(environment, "cupola")
    assert step(environment, {"tool": "inspect", "target": "dome_scope"}) is ToolReason.INSPECTED
    move_to(environment, "sleep_pod")
    assert step(environment, {"tool": "inspect", "target": "bunk"}) is ToolReason.INSPECTED
    move_to(environment, "cupola", "airlock_hall", "regolith_tunnel", "depot_store")
    step(environment, {"tool": "inspect", "target": "depot_crate"})
    assert step(environment, {"tool": "pickup", "item": "patch_kit"}) is ToolReason.PICKED_UP
    assert (
        rejected(environment, {"tool": "use", "item": "patch_kit", "target": "bay_panel"})
        is ToolReason.WRONG_TARGET
    )


def test_lunar_hard_repair_order_and_launch_guards() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-hard-zh")
    environment.reset(0)
    move_to(environment, "regolith_tunnel", "depot_store", "crater_cellar")
    step(environment, {"tool": "inspect", "target": "depot_crate"})
    step(environment, {"tool": "pickup", "item": "torque_driver"})
    step(environment, {"tool": "pickup", "item": "oxy_cell"})
    step(environment, {"tool": "pickup", "item": "dead_sensor"})
    move_to(environment, "depot_store", "telemetry_nook", "reactor_bay")

    assert (
        rejected(environment, {"tool": "use", "item": "oxy_cell", "target": "spent_cell"})
        is ToolReason.PANEL_CLOSED
    )
    step(environment, {"tool": "use", "item": "torque_driver", "target": "bay_panel"})
    step(environment, {"tool": "use", "item": "oxy_cell", "target": "spent_cell"})
    move_to(environment, "telemetry_nook", "regolith_tunnel", "greenhouse")
    assert step(environment, {"tool": "inspect", "target": "wilted_rack"}) is ToolReason.INSPECTED
    move_to(environment, "regolith_tunnel", "telemetry_nook")
    step(environment, {"tool": "read_terminal", "target": "mission_console"})
    move_to(environment, "reactor_bay", "launch_pad")
    assert (
        rejected(
            environment, {"tool": "use", "item": "WRONG-0", "target": "return_capsule"}
        )
        is ToolReason.INCORRECT_CODE
    )
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-908", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
