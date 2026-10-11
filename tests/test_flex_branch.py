from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.flex import (
    LunarV2SeededEnvironment,
    build_seeded_items,
    load_lunar_v2_definition,
    load_lunar_v2_seeded_definition,
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


def test_lunar_v2_definition_has_eight_rooms_and_bidirectional_exits() -> None:
    definition = load_lunar_v2_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "lunar_escape_v2"
    assert len(rooms) == 8
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_lunar_v2_identities_match_registered_selectors() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v2-zh")
    assert environment.identity[:2] == ("lunar-escape", "lunar-escape-v2-zh")
    assert environment.identity[2] == "lunar_escape_v2"
    seeded = create_environment("lunar-escape", "lunar-escape-v2-seeded-zh")
    assert isinstance(seeded, LunarV2SeededEnvironment)
    assert seeded.identity[:2] == ("lunar-escape", "lunar-escape-v2-seeded-zh")


def test_lunar_v2_short_branch_passage_escapes_in_nineteen_steps() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v2-zh")
    observation = environment.reset(0)
    assert observation.current_room == "airlock_hall"

    move_to(environment, "regolith_tunnel", "telemetry_nook", "depot_store")
    assert (
        step(environment, {"tool": "inspect", "target": "depot_crate"})
        is ToolReason.INSPECTED
    )
    assert step(environment, {"tool": "pickup", "item": "torque_driver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "core_cell_a"}) is ToolReason.PICKED_UP
    move_to(environment, "telemetry_nook", "reactor_bay")
    assert (
        step(environment, {"tool": "use", "item": "torque_driver", "target": "main_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "core_cell_a", "target": "main_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "telemetry_nook", "regolith_tunnel", "airlock_hall")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "mission_console"}))
    assert result.status is ToolStatus.SUCCESS
    assert result.reason is ToolReason.CODE_READ
    assert "LUNAR-220" in (result.summary or "")
    move_to(environment, "regolith_tunnel", "telemetry_nook", "reactor_bay", "launch_pad")
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-220", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_lunar_v2_long_branch_also_restores_power() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "regolith_tunnel", "telemetry_nook", "depot_store")
    step(environment, {"tool": "inspect", "target": "depot_crate"})
    step(environment, {"tool": "pickup", "item": "hex_driver"})
    step(environment, {"tool": "pickup", "item": "core_cell_b"})
    move_to(environment, "telemetry_nook", "reactor_bay", "aux_bay")
    assert (
        step(environment, {"tool": "use", "item": "hex_driver", "target": "aux_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "core_cell_b", "target": "aux_cell"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "reactor_bay", "telemetry_nook", "regolith_tunnel", "airlock_hall")
    step(environment, {"tool": "read_terminal", "target": "mission_console"})
    move_to(
        environment, "regolith_tunnel", "telemetry_nook", "reactor_bay", "launch_pad"
    )
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-220", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )


def test_lunar_v2_branch_tools_are_not_interchangeable() -> None:
    environment = create_environment("lunar-escape", "lunar-escape-v2-zh")
    environment.reset(0)
    move_to(environment, "regolith_tunnel", "telemetry_nook", "depot_store")
    step(environment, {"tool": "inspect", "target": "depot_crate"})
    step(environment, {"tool": "pickup", "item": "torque_driver"})
    step(environment, {"tool": "pickup", "item": "core_cell_a"})
    move_to(environment, "telemetry_nook", "reactor_bay", "aux_bay")
    assert (
        rejected(environment, {"tool": "use", "item": "torque_driver", "target": "aux_panel"})
        is ToolReason.MISSING_ITEM
    )
    assert (
        rejected(environment, {"tool": "use", "item": "core_cell_a", "target": "aux_cell"})
        is ToolReason.MISSING_ITEM
    )


def test_lunar_v2_seeded_placement_is_deterministic_and_varies() -> None:
    definition = load_lunar_v2_seeded_definition()
    first = build_seeded_items(definition, 3)
    second = build_seeded_items(definition, 3)
    assert [(item.id, item.container_id) for item in first] == [
        (item.id, item.container_id) for item in second
    ]
    placements = {
        tuple(sorted((item.id, item.container_id) for item in build_seeded_items(definition, s)))
        for s in range(10)
    }
    assert len(placements) >= 2


def test_lunar_v2_seeded_instance_is_solvable() -> None:
    definition = load_lunar_v2_seeded_definition()
    placement = {item.id: item.container_id for item in build_seeded_items(definition, 1)}
    environment = LunarV2SeededEnvironment(seed=1)
    environment.reset(1)
    assert {item.id: item.container_id for item in environment._items.values()} == placement

    groups: dict[str, list[str]] = {}
    for tool, container in placement.items():
        groups.setdefault(container, []).append(tool)
    assert set(groups) <= {"depot_crate", "spare_crate"}
    move_to(environment, "regolith_tunnel", "telemetry_nook", "depot_store")
    step(environment, {"tool": "inspect", "target": "depot_crate"})
    for tool in groups.get("depot_crate", []):
        step(environment, {"tool": "pickup", "item": tool})
    move_to(environment, "telemetry_nook", "regolith_tunnel", "cupola")
    step(environment, {"tool": "inspect", "target": "spare_crate"})
    for tool in groups.get("spare_crate", []):
        step(environment, {"tool": "pickup", "item": tool})
    # All four tools are collected above, so the main branch is always available.
    move_to(environment, "regolith_tunnel", "telemetry_nook", "reactor_bay")
    step(environment, {"tool": "use", "item": "torque_driver", "target": "main_panel"})
    step(environment, {"tool": "use", "item": "core_cell_a", "target": "main_cell"})
    move_to(environment, "telemetry_nook", "regolith_tunnel", "airlock_hall")
    step(environment, {"tool": "read_terminal", "target": "mission_console"})
    move_to(environment, "regolith_tunnel", "telemetry_nook", "reactor_bay", "launch_pad")
    assert (
        step(environment, {"tool": "use", "item": "LUNAR-220", "target": "return_capsule"})
        is ToolReason.ESCAPED
    )
