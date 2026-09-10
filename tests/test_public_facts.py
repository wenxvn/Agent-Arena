from __future__ import annotations

from agent_arena.arena import action_adapter
from agent_arena.evaluation import (
    EpisodeKnowledge,
    ProgressDetector,
    extract_public_facts,
)
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_first_no_power_result_is_a_new_public_fact() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python(
        {"tool": "read_terminal", "target": "control_terminal"}
    )
    result, after = environment.step(action)
    detector = ProgressDetector()

    facts = extract_public_facts(after, action, result)
    event = detector.evaluate(before, action, result, after)

    assert facts[0].subject == "control_terminal"
    assert facts[0].value == "no_power"
    assert event.epistemic_progress is True
    assert event.new_facts == facts


def test_repeated_no_power_result_is_known_and_not_progress() -> None:
    environment = SpaceshipEscapeEnvironment()
    current = environment.reset(0)
    action = action_adapter.validate_python(
        {"tool": "read_terminal", "target": "control_terminal"}
    )
    detector = ProgressDetector()

    first_result, first_after = environment.step(action)
    first = detector.evaluate(current, action, first_result, first_after)
    second_result, second_after = environment.step(action)
    second = detector.evaluate(first_after, action, second_result, second_after)

    assert first.epistemic_progress is True
    assert second.new_facts == ()
    assert second.epistemic_progress is False
    assert second.progress is False
    assert detector.knowledge == EpisodeKnowledge(discovered_facts=first.new_facts)
