"""T4：终点误操作与重复读码的离线契约测试（只读真实 trace，不调用模型）。"""
from __future__ import annotations

import json
from pathlib import Path

from agent_arena.evaluation.progress import ProgressDetector
from agent_arena.evaluation.public_facts import extract_public_facts
from agent_arena.evaluation.trace import read_episode_trace

RUNS = Path(__file__).resolve().parent.parent / "runs"
LIGHTHOUSE_SEED0 = RUNS / "muse-3maps-lightv2" / "episode_20261011T060651Z_memory_seed-0_cd0d1ccd.json"
SHIP_SEED1 = RUNS / "muse-3maps-shipv3" / "episode_20261011T063025Z_memory_seed-1_9a351a08.json"

TERMINAL_TARGETS = {"harbor_skiff", "escape_pod", "escape_capsule"}


def _steps(trace) -> list:
    return list(trace.steps)


def test_wrong_tool_at_terminal_is_always_rejected() -> None:
    trace = read_episode_trace(LIGHTHOUSE_SEED0)
    misuses = [
        s for s in _steps(trace)
        if s.action is not None
        and s.action.tool == "read_terminal"
        and s.action.target in TERMINAL_TARGETS
    ]
    assert len(misuses) == 3
    for step in misuses:
        assert step.result is not None
        assert step.result.reason.value == "wrong_target"


def test_repeated_code_read_has_no_new_facts() -> None:
    trace = read_episode_trace(SHIP_SEED1)
    reads = [
        s for s in _steps(trace)
        if s.action is not None
        and s.action.tool == "read_terminal"
        and s.result is not None
        and s.result.reason.value == "code_read"
    ]
    assert len(reads) == 18
    # 第二次起 CODE_READ 不应产生新公开事实（重放判定）。
    facts_before: set = set()
    detector = ProgressDetector()
    second_has_new_facts = None
    for step in _steps(trace):
        if step.observation is None or step.action is None or step.result is None:
            continue
        after = step.next_observation if step.next_observation is not None else step.observation
        detector.evaluate(step.observation, step.action, step.result, after)
        facts = extract_public_facts(step.observation, step.action, step.result)
        key = {(f.subject, f.predicate, f.value) for f in facts}
        if step.result.reason.value == "code_read":
            if not facts_before:
                facts_before |= key
            elif second_has_new_facts is None:
                second_has_new_facts = bool(key - facts_before)
                break
    assert second_has_new_facts is False


def test_correct_escape_uses_code_not_terminal() -> None:
    data = json.loads(LIGHTHOUSE_SEED0.read_text(encoding="utf-8"))
    last = data["steps"][-1]
    assert last["action"]["tool"] == "use"
    assert last["action"]["target"] == "harbor_skiff"
    assert data["outcome"] == "success"
