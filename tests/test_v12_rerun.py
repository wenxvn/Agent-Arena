"""V12 版本复跑测试：新版本下重跑已完成条件，独立成实验且不污染源实验。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from agent_arena.lab.contracts import (
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.experiment import ExperimentError, ExperimentService
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER
from agent_arena.web.service import RunService


def _spec(**overrides: Any) -> ExperimentSpec:
    payload: dict[str, Any] = {
        "name": "v1",
        "maps": ["MAP-22", "MAP-26"],
        "agent_arms": [AgentArm(agent_id="basic.v1")],
        "environment_seeds": [0],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
        "budget": ExperimentBudget(
            per_run_request_cap=20,
            per_run_decision_cap=4,
            experiment_request_cap=400,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def _services(tmp_path: Path) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def test_version_rerun_can_target_completed_conditions(tmp_path: Path) -> None:
    """与补跑不同：已完成的子局**可以**在新版本下重跑。"""

    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        lab.submit(source_id)
        lab.wait(source_id, timeout=300)
        # 源实验全部完成 → 补跑候选为 0。
        assert lab.supplement_candidates(source_id)["count"] == 0

        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        rerun_id = lab.create_version_rerun(
            source_id, conditions=conditions, reason="契约修复后重测"
        )
        assert rerun_id != source_id
        spec = lab._spec(rerun_id)
        assert spec.supplement_of == source_id
        assert spec.supplement_reason == "契约修复后重测"
        assert spec.only_conditions == conditions
        assert len(spec.matrix()) == len(conditions)
    finally:
        runs.shutdown()


def test_version_rerun_rejects_unknown_conditions(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        with pytest.raises(ExperimentError):
            lab.create_version_rerun(
                source_id, conditions=["MAP-99|seed=9|nope"], reason="x"
            )
        with pytest.raises(ExperimentError):
            lab.create_version_rerun(source_id, conditions=[], reason="x")
    finally:
        runs.shutdown()


def test_version_rerun_is_independent_and_idempotent(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        first = lab.create_version_rerun(source_id, conditions=conditions, reason="r")
        second = lab.create_version_rerun(source_id, conditions=conditions, reason="r")
        assert first == second
        assert len(lab.store.list_ids()) == 2
        # 源实验仍未被提交，子局数不变。
        assert lab.status(source_id).children == []
    finally:
        runs.shutdown()


def test_version_rerun_report_declares_lineage(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        rerun_id = lab.create_version_rerun(
            source_id, conditions=conditions, reason="契约补丁 v12-contract-1"
        )
        lab.submit(rerun_id)
        lab.wait(rerun_id, timeout=300)
        summary = lab.summary(rerun_id)
        assert summary["supplement_of"] == source_id
        report = lab.report(rerun_id)
        assert "补充实验" in report
        assert source_id in report
        assert "契约补丁" in report
    finally:
        runs.shutdown()


def test_version_rerun_fingerprint_differs_from_source(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        rerun_id = lab.create_version_rerun(source_id, conditions=conditions, reason="r")
        assert lab._spec(source_id).fingerprint() != lab._spec(rerun_id).fingerprint()
    finally:
        runs.shutdown()


def test_runtime_version_is_part_of_experiment_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """改了代码/契约版本后，同一配置必须得到**新**实验而不是命中旧实验。"""

    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        first = lab.create_version_rerun(
            source_id, conditions=conditions, reason="契约 v1"
        )
        assert lab._spec(first).runtime_version

        from agent_arena.lab import experiment as experiment_module

        monkeypatch.setattr(
            experiment_module, "current_runtime_version", lambda: "v12-lab-1+test-2"
        )
        second = lab.create_version_rerun(
            source_id, conditions=conditions, reason="契约 v2"
        )
        assert second != first
        assert lab._spec(second).runtime_version == "v12-lab-1+test-2"
        assert lab._spec(first).fingerprint() != lab._spec(second).fingerprint()
    finally:
        runs.shutdown()


def test_preflight_reports_runtime_version() -> None:
    from agent_arena.lab.experiment import preflight
    from agent_arena.lab.runtime_version import current_runtime_version

    result = preflight(_spec())
    assert any(current_runtime_version() in note for note in result.notes)
