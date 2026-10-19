"""MiMo 有效局选择：新阶段优先、完整优先。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.evidence_state import _run_priority


def _row(run_id: str, outcome: str = "success") -> dict[str, Any]:
    return {"run_id": run_id, "outcome": outcome}


def test_later_phases_outrank_earlier_phases() -> None:
    assert _run_priority(_row("V10-MAP-19-S0-u2")) > _run_priority(_row("V10-MAP-19-S0-t2"))
    assert _run_priority(_row("V10-MAP-19-S0-t2")) > _run_priority(_row("V10-MAP-20-S0-j2"))
    assert _run_priority(_row("V10-MAP-16-S0-r2")) > _run_priority(_row("V10-MAP-16-S0-ext"))


def test_completed_run_outranks_interrupted_newer_run() -> None:
    interrupted = _row("V10-MAP-19-S0-u2", outcome="unknown_provider_spend")
    completed = _row("V10-MAP-19-S0-j2")
    assert _run_priority(interrupted) < _run_priority(completed)
