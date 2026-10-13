"""T4：公开终点事实与重复读码判定（合成离线输入，不调用模型）。"""
from __future__ import annotations

from agent_arena.arena import (
    Observation,
    ToolReason,
    ToolResult,
    ToolStatus,
    action_adapter,
)
from agent_arena.evaluation.progress import ProgressDetector
from agent_arena.evaluation.public_facts import extract_public_facts

TERMINAL_TARGETS = ("harbor_skiff", "escape_pod", "escape_capsule")


def _observation() -> Observation:
    return Observation(
        current_room="cliff_base",
        description="A rocky path leads toward the harbor.",
        visible_objects=(),
        available_exits=(),
        inventory=(),
        last_action_result=None,
    )


def test_wrong_terminal_targets_are_recorded_as_public_facts() -> None:
    observation = _observation()
    result = ToolResult(
        status=ToolStatus.REJECTED,
        reason=ToolReason.WRONG_TARGET,
        summary="This object is not a terminal.",
    )

    facts = [
        extract_public_facts(
            observation,
            action_adapter.validate_python({"tool": "read_terminal", "target": target}),
            result,
        )
        for target in TERMINAL_TARGETS
    ]

    assert [items[0].subject for items in facts] == list(TERMINAL_TARGETS)
    assert all(items[0].value == ToolReason.WRONG_TARGET.value for items in facts)


def test_repeated_code_read_has_no_new_public_facts() -> None:
    observation = _observation()
    action = action_adapter.validate_python(
        {"tool": "read_terminal", "target": "control_terminal"}
    )
    result = ToolResult(
        status=ToolStatus.SUCCESS,
        reason=ToolReason.CODE_READ,
        summary="A public authorization code was revealed.",
    )
    detector = ProgressDetector()

    first = detector.evaluate(observation, action, result, observation)
    second = detector.evaluate(observation, action, result, observation)

    assert first.epistemic_progress is True
    assert len(first.new_facts) == 1
    assert second.epistemic_progress is False
    assert second.new_facts == ()
