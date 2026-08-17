from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import SpaceshipEscapeEnvironment, load_spaceship_escape_definition


def action(payload: Mapping[str, Any]) -> Any:
    return action_adapter.validate_python(payload)


def step(environment: SpaceshipEscapeEnvironment, payload: Mapping[str, Any]) -> ToolReason:
    result, _ = environment.step(action(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def move_to(environment: SpaceshipEscapeEnvironment, *destinations: str) -> None:
    for destination in destinations:
        assert step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def collect_reactor_tools(environment: SpaceshipEscapeEnvironment) -> None:
    move_to(environment, "corridor", "storage_room")
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP


def restore_main_power(environment: SpaceshipEscapeEnvironment) -> None:
    collect_reactor_tools(environment)
    move_to(environment, "corridor", "maintenance_room", "reactor_room")
    assert (
        step(environment, {"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"})
        is ToolReason.POWER_RESTORED
    )


def test_world_definition_has_six_rooms_and_bidirectional_exits() -> None:
    definition = load_spaceship_escape_definition()
    rooms = {room.id: room for room in definition.rooms}

    assert definition.world_id == "spaceship_escape_v1"
    assert len(rooms) == 6
    for room in rooms.values():
        for destination in room.exits:
            assert room.id in rooms[destination].exits


def test_action_schema_is_a_strict_discriminated_union() -> None:
    assert action({"tool": "look"}).tool == "look"

    with pytest.raises(ValidationError):
        action({"tool": "move"})
    with pytest.raises(ValidationError):
        action({"tool": "move", "destination": "corridor", "unexpected": True})
    with pytest.raises(ValidationError):
        action({"tool": "teleport", "destination": "escape_pod"})


@pytest.mark.parametrize(
    "payload",
    [
        {"tool": "move", "destination": 1},
        {"tool": "inspect", "target": None},
        {"tool": "pickup", "item": ["screwdriver"]},
        {"tool": "use", "item": "screwdriver"},
    ],
)
def test_action_schema_rejects_invalid_parameter_types(payload: Mapping[str, Any]) -> None:
    with pytest.raises(ValidationError):
        action(payload)


def test_storage_visibility_and_pickup_rules() -> None:
    environment = SpaceshipEscapeEnvironment()
    move_to(environment, "corridor", "storage_room")

    _, observation = environment.step(action({"tool": "look"}))
    assert observation.visible_objects == ("storage_crate",)

    result, _ = environment.step(action({"tool": "pickup", "item": "screwdriver"}))
    assert result.reason is ToolReason.NOT_REVEALED
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    _, observation = environment.step(action({"tool": "look"}))
    assert observation.visible_objects == ("storage_crate", "replacement_fuse", "screwdriver")

    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    result, observation = environment.step(action({"tool": "pickup", "item": "screwdriver"}))
    assert result.status is ToolStatus.REJECTED
    assert result.reason is ToolReason.ALREADY_COLLECTED
    assert observation.inventory == ("screwdriver",)


def test_reactor_panel_reveals_the_damaged_fuse_only_after_opening() -> None:
    environment = SpaceshipEscapeEnvironment()
    collect_reactor_tools(environment)
    move_to(environment, "corridor", "maintenance_room", "reactor_room")

    _, observation = environment.step(action({"tool": "look"}))
    assert observation.visible_objects == ("reactor_panel",)
    result, _ = environment.step(action({"tool": "inspect", "target": "damaged_fuse"}))
    assert result.reason is ToolReason.NOT_VISIBLE

    assert (
        step(environment, {"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
        is ToolReason.PANEL_OPENED
    )
    _, observation = environment.step(action({"tool": "look"}))
    assert observation.visible_objects == ("reactor_panel", "damaged_fuse")


def test_manual_escape_path_uses_only_public_tools() -> None:
    environment = SpaceshipEscapeEnvironment(seed=7)
    initial = environment.reset(seed=7)

    assert initial.current_room == "control_room"
    assert initial.visible_objects == ("control_terminal",)
    assert initial.last_action_result is None

    move_to(environment, "corridor", "storage_room")
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP
    move_to(environment, "corridor", "maintenance_room")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "diagnostic_terminal"}))
    assert result.reason is ToolReason.DIAGNOSTIC_READ
    assert "手动" in result.summary
    move_to(environment, "reactor_room")
    assert (
        step(environment, {"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
        is ToolReason.PANEL_OPENED
    )
    assert (
        step(environment, {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"})
        is ToolReason.POWER_RESTORED
    )
    move_to(environment, "maintenance_room", "corridor", "control_room")
    result, _ = environment.step(action({"tool": "read_terminal", "target": "control_terminal"}))
    assert result.reason is ToolReason.CODE_READ
    assert "ALPHA-731" in result.summary
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    assert (
        step(environment, {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_power_and_escape_rejections_do_not_change_puzzle_state() -> None:
    environment = SpaceshipEscapeEnvironment()

    result, _ = environment.step(action({"tool": "read_terminal", "target": "control_terminal"}))
    assert result.reason is ToolReason.NO_POWER
    assert not environment._state.main_power

    move_to(environment, "corridor", "maintenance_room", "reactor_room")
    result, _ = environment.step(
        action({"tool": "use", "item": "screwdriver", "target": "reactor_panel"})
    )
    assert result.reason is ToolReason.MISSING_ITEM
    assert not environment._state.reactor_panel_open

    move_to(environment, "maintenance_room", "corridor")
    move_to(environment, "storage_room")
    assert step(environment, {"tool": "inspect", "target": "storage_crate"}) is ToolReason.INSPECTED
    assert step(environment, {"tool": "pickup", "item": "screwdriver"}) is ToolReason.PICKED_UP
    assert step(environment, {"tool": "pickup", "item": "replacement_fuse"}) is ToolReason.PICKED_UP
    move_to(environment, "corridor", "maintenance_room", "reactor_room")
    result, _ = environment.step(
        action({"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"})
    )
    assert result.reason is ToolReason.PANEL_CLOSED
    assert not environment._state.main_power

    move_to(environment, "escape_pod")
    result, _ = environment.step(
        action({"tool": "use", "item": "ALPHA-731", "target": "escape_pod"})
    )
    assert result.reason is ToolReason.CODE_UNREAD
    assert not environment.is_success()


def test_observations_exclude_internal_state_and_unrevealed_values() -> None:
    environment = SpaceshipEscapeEnvironment()
    observation = environment.observe()
    serialized = observation.model_dump(mode="json")

    assert set(serialized) == {
        "current_room",
        "description",
        "visible_objects",
        "available_exits",
        "inventory",
        "last_action_result",
    }
    assert "ALPHA-731" not in str(serialized)
    assert "main_power" not in serialized
    assert "reactor_panel_open" not in serialized
    assert "replacement_fuse" not in serialized["visible_objects"]


def test_reset_is_deterministic_and_every_valid_action_counts_as_a_step() -> None:
    first = SpaceshipEscapeEnvironment(seed=0)
    second = SpaceshipEscapeEnvironment(seed=0)
    different_seed = SpaceshipEscapeEnvironment(seed=23)

    assert first.observe() == second.observe() == different_seed.observe()
    assert first._state.seed == 0
    assert different_seed._state.seed == 23

    result, _ = first.step(action({"tool": "move", "destination": "escape_pod"}))
    assert result.reason is ToolReason.NOT_ADJACENT
    assert first._state.step_count == 1
    assert first._state.current_room == "control_room"


def test_reset_removes_progress_and_returns_a_clean_observation() -> None:
    environment = SpaceshipEscapeEnvironment()
    move_to(environment, "corridor", "storage_room")
    step(environment, {"tool": "inspect", "target": "storage_crate"})
    step(environment, {"tool": "pickup", "item": "screwdriver"})

    observation = environment.reset(seed=-4)

    assert observation.current_room == "control_room"
    assert observation.visible_objects == ("control_terminal",)
    assert observation.inventory == ()
    assert observation.last_action_result is None
    assert environment._state.seed == -4
    assert environment._state.step_count == 0


def test_escape_pod_rejects_an_incorrect_code_after_authorization() -> None:
    environment = SpaceshipEscapeEnvironment()
    restore_main_power(environment)
    move_to(environment, "maintenance_room", "corridor", "control_room")
    assert (
        step(environment, {"tool": "read_terminal", "target": "control_terminal"})
        is ToolReason.CODE_READ
    )
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")

    result, _ = environment.step(action({"tool": "use", "item": "WRONG", "target": "escape_pod"}))

    assert result.status is ToolStatus.REJECTED
    assert result.reason is ToolReason.INCORRECT_CODE
    assert not environment.is_success()


def test_actions_after_escape_are_rejected_without_state_mutation() -> None:
    environment = SpaceshipEscapeEnvironment()
    restore_main_power(environment)
    move_to(environment, "maintenance_room", "corridor", "control_room")
    step(environment, {"tool": "read_terminal", "target": "control_terminal"})
    move_to(environment, "corridor", "maintenance_room", "reactor_room", "escape_pod")
    step(environment, {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"})
    steps_before = environment._state.step_count

    result, observation = environment.step(action({"tool": "look"}))

    assert result.status is ToolStatus.REJECTED
    assert result.reason is ToolReason.ALREADY_COMPLETED
    assert environment._state.step_count == steps_before + 1
    assert observation.current_room == "escape_pod"
