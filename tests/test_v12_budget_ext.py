"""V12 预算扩展测试：截尾局在更高预算下重测，独立成实验。"""

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
        "maps": ["MAP-22"],
        "agent_arms": [AgentArm(agent_id="basic.v1")],
        "environment_seeds": [0, 1],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
        "budget": ExperimentBudget(
            per_run_request_cap=10,
            per_run_decision_cap=10,
            experiment_request_cap=40,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def _services(tmp_path: Path) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def test_budget_extension_raises_caps(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        ext_id = lab.create_budget_extension(
            source_id,
            conditions=conditions,
            per_run_request_cap=40,
            per_run_cost_cap_cny=Decimal("1.5"),
            reason="截尾重测",
        )
        spec = lab._spec(ext_id)
        assert spec.budget.per_run_request_cap == 40
        assert spec.budget.per_run_decision_cap == 40
        assert spec.budget.per_run_cost_cap_cny == Decimal("1.5")
        assert spec.budget.experiment_request_cap == 40 * len(conditions)
        assert spec.supplement_of == source_id
        assert spec.supplement_reason == "截尾重测"
        assert spec.only_conditions == conditions
    finally:
        runs.shutdown()


def test_budget_extension_raises_token_cap(tmp_path: Path) -> None:
    """观测长的图会先撞输入 token 上限；扩展预算必须同时抬高它。"""

    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        ext_id = lab.create_budget_extension(
            source_id, conditions=conditions, per_run_request_cap=200, reason="token 也抬"
        )
        spec = lab._spec(ext_id)
        assert spec.budget.per_run_input_token_cap >= 200 * 2_500
        assert spec.budget.per_run_input_token_cap > 200_000
    finally:
        runs.shutdown()


def test_budget_extension_explicit_token_cap_wins(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        ext_id = lab.create_budget_extension(
            source_id,
            conditions=conditions,
            per_run_request_cap=200,
            per_run_input_token_cap=900_000,
            reason="显式 token",
        )
        assert lab._spec(ext_id).budget.per_run_input_token_cap == 900_000
    finally:
        runs.shutdown()


def test_budget_extension_requires_known_conditions(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        with pytest.raises(ExperimentError):
            lab.create_budget_extension(
                source_id,
                conditions=["MAP-99|seed=0|x"],
                per_run_request_cap=40,
                reason="x",
            )
        with pytest.raises(ExperimentError):
            lab.create_budget_extension(
                source_id, conditions=[], per_run_request_cap=40, reason="x"
            )
    finally:
        runs.shutdown()


def test_budget_extension_is_separate_experiment(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        lab.submit(source_id)
        lab.wait(source_id, timeout=300)
        before_runs = len(runs.list_runs())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        ext_id = lab.create_budget_extension(
            source_id, conditions=conditions, per_run_request_cap=40, reason="截尾重测"
        )
        assert ext_id != source_id
        assert len(runs.list_runs()) == before_runs
        lab.submit(ext_id)
        manifest = lab.wait(ext_id, timeout=300)
        assert manifest.state.value == "COMPLETED"
        assert manifest.counts["done"] == len(conditions)
        # 源实验记录未变（除对账外）。
        assert lab.status(source_id).counts["done"] == len(conditions)
    finally:
        runs.shutdown()


def test_budget_extension_report_declares_budget_change(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        ext_id = lab.create_budget_extension(
            source_id,
            conditions=conditions[:1],
            per_run_request_cap=40,
            reason="预算从 10 提到 40",
        )
        lab.submit(ext_id)
        lab.wait(ext_id, timeout=300)
        report = lab.report(ext_id)
        assert "补充实验" in report
        assert source_id in report
        assert "预算从 10 提到 40" in report
        summary = lab.summary(ext_id)
        assert summary["budget"]["per_run_request_cap"] == 40
    finally:
        runs.shutdown()


def test_budget_extension_is_idempotent(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        first = lab.create_budget_extension(
            source_id, conditions=conditions, per_run_request_cap=40, reason="r"
        )
        second = lab.create_budget_extension(
            source_id, conditions=conditions, per_run_request_cap=40, reason="r"
        )
        assert first == second
        assert len(lab.store.list_ids()) == 2
    finally:
        runs.shutdown()
