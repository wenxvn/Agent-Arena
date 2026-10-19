"""动作循环扫描：判定规则。"""

from __future__ import annotations

from agent_arena.v10.trace_scan import classify


def _actions(tool: str, count: int) -> list[dict[str, str]]:
    return [{"tool": tool}] * count


def test_free_action_loop_is_flagged_when_tick_stalls() -> None:
    best, verdict, key = classify(_actions("set_flow", 8), [0] * 8)
    assert best == 8
    assert verdict == "FREE_ACTION_LOOP"
    assert "set_flow" in key


def test_invalid_output_loop_is_classified_separately() -> None:
    action = {"invalid_output": {"tool": "submit"}}
    best, verdict, _ = classify([action] * 8, [0] * 8)
    assert best == 8
    assert verdict == "INVALID_OUTPUT_LOOP"


def test_repeat_is_ok_when_tick_advances() -> None:
    _, verdict, _ = classify(_actions("assign", 8), list(range(8)))
    assert verdict == "OK"


def test_short_repeat_is_ok() -> None:
    _, verdict, _ = classify(_actions("wait", 7), [0] * 7)
    assert verdict == "OK"
