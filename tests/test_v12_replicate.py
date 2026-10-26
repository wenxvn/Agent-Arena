"""V12 重复实验测试：同版本同配置再跑一次，用于测量抽样波动。"""

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
        "name": "base",
        "maps": ["MAP-16"],
        "agent_arms": [AgentArm(agent_id="basic.v1")],
        "environment_seeds": [0, 1],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
        "budget": ExperimentBudget(
            per_run_request_cap=20,
            per_run_decision_cap=6,
            experiment_request_cap=200,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def _services(tmp_path: Path) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def test_replicate_creates_new_experiment_with_same_conditions(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        rep_id = lab.create_replicate(source_id, conditions=conditions)
        assert rep_id != source_id
        spec = lab._spec(rep_id)
        assert spec.only_conditions == conditions
        assert spec.supplement_of == source_id
        assert "重复实验" in spec.supplement_reason
        assert spec.runtime_version == lab._spec(source_id).runtime_version
    finally:
        runs.shutdown()


def test_replicate_produces_new_run_ids(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        lab.submit(source_id)
        lab.wait(source_id, timeout=300)
        source_runs = {child["run_id"] for child in lab.status(source_id).children}

        rep_id = lab.create_replicate(source_id, conditions=conditions)
        lab.submit(rep_id)
        lab.wait(rep_id, timeout=300)
        rep_runs = {child["run_id"] for child in lab.status(rep_id).children}
        assert rep_runs
        assert not (source_runs & rep_runs), "重复实验必须产生新的 run_id"
    finally:
        runs.shutdown()


def test_replicate_rejects_version_mismatch(tmp_path: Path) -> None:
    """源实验是旧版本时，重复会变成"版本复跑"，必须拒绝并提示改用 --rerun-of。"""

    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        payload = lab.store.load_spec(source_id)
        payload["runtime_version"] = "v12-lab-1+old"
        lab.store.write_json(source_id, "experiment.json", payload)
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        with pytest.raises(ExperimentError):
            lab.create_replicate(source_id, conditions=conditions)
    finally:
        runs.shutdown()


def test_replicate_rejects_unknown_conditions(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        with pytest.raises(ExperimentError):
            lab.create_replicate(source_id, conditions=["MAP-99|seed=0|x"])
        with pytest.raises(ExperimentError):
            lab.create_replicate(source_id, conditions=[])
    finally:
        runs.shutdown()


def test_replicate_is_idempotent(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        conditions = [cell.condition_key for cell in lab._spec(source_id).matrix()]
        first = lab.create_replicate(source_id, conditions=conditions)
        second = lab.create_replicate(source_id, conditions=conditions)
        assert first == second
        assert len(lab.store.list_ids()) == 2
    finally:
        runs.shutdown()
