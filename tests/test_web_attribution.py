"""V11 公开动作级失败归因。"""

from __future__ import annotations

from agent_arena.web.attribution import attribute_steps


def _step(tool: str, result: str = "OK") -> dict[str, object]:
    return {"action": {"tool": tool}, "result": result}


def test_triggered_when_mechanism_true() -> None:
    result = attribute_steps(
        "MAP-01",
        [_step("move", "MOVED:B")],
        invalid_actions=0,
        mechanism_triggered=True,
        outcome="success",
    )
    assert result["label"] == "TRIGGERED"
    assert result["attempts"] == 1


def test_contract_artifact_when_invalid_ratio_high() -> None:
    result = attribute_steps(
        "MAP-01",
        [_step("move", "INVALID_ACTION_SCHEMA"), _step("move", "INVALID_ACTION_SCHEMA")],
        invalid_actions=2,
        mechanism_triggered=False,
        outcome="failure",
    )
    assert result["label"] == "CONTRACT_ARTIFACT"


def test_never_attempted_and_attempted_rejected() -> None:
    never = attribute_steps(
        "MAP-01",
        [_step("inspect", "inspected")],
        invalid_actions=0,
        mechanism_triggered=False,
        outcome="failure",
    )
    assert never["label"] == "KEY_ACTION_NEVER_ATTEMPTED"
    rejected = attribute_steps(
        "MAP-01",
        [_step("move", "EDGE_NOT_ADJACENT")],
        invalid_actions=0,
        mechanism_triggered=False,
        outcome="failure",
    )
    assert rejected["label"] == "KEY_ACTION_ATTEMPTED_REJECTED"


def test_used_without_trigger_and_incomplete() -> None:
    used = attribute_steps(
        "MAP-19",
        [_step("forecast_next", "FORECAST_ACCEPTED")],
        invalid_actions=0,
        mechanism_triggered=False,
        outcome="failure",
    )
    assert used["label"] == "KEY_ACTION_USED_NO_TRIGGER"
    incomplete = attribute_steps(
        "MAP-19",
        [],
        invalid_actions=0,
        mechanism_triggered=False,
        outcome="cancelled",
    )
    assert incomplete["label"] == "INCOMPLETE"
