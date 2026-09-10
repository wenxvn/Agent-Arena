from __future__ import annotations

from agent_arena.arena import action_adapter
from agent_arena.evaluation import ProgressDetector
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_move_is_state_progress() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python({"tool": "move", "destination": "corridor"})
    result, after = environment.step(action)

    event = ProgressDetector().evaluate(before, action, result, after)

    assert event.state_progress is True
    assert event.epistemic_progress is False
    assert event.state_changes == ("current_room", "visible_objects", "available_exits")
    assert event.progress is True


def test_new_public_fact_is_epistemic_progress() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python(
        {"tool": "read_terminal", "target": "control_terminal"}
    )
    result, after = environment.step(action)

    event = ProgressDetector().evaluate(before, action, result, after)

    assert event.state_progress is False
    assert event.epistemic_progress is True
    assert event.progress is True


def test_repeated_known_fact_without_state_change_is_no_progress() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python(
        {"tool": "read_terminal", "target": "control_terminal"}
    )
    detector = ProgressDetector()
    first_result, first_after = environment.step(action)
    detector.evaluate(before, action, first_result, first_after)
    second_result, second_after = environment.step(action)

    event = detector.evaluate(first_after, action, second_result, second_after)

    assert event.state_changes == ()
    assert event.new_facts == ()
    assert event.progress is False
