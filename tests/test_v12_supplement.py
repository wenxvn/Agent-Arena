"""V12 补充实验测试：中断/未知消费子局只在新实验里补跑，原实验不动。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from agent_arena.lab.contracts import (
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
    ExperimentState,
)
from agent_arena.lab.experiment import ExperimentError, ExperimentService
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunState,
)
from agent_arena.web.service import RunService


def _spec(**overrides: Any) -> ExperimentSpec:
    payload: dict[str, Any] = {
        "name": "source",
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


def _services(tmp_path: Path, **kwargs: Any) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False, **kwargs)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def _mark_child(
    lab: ExperimentService,
    experiment_id: str,
    matrix_index: int,
    *,
    state: str,
    cost_unknown: bool = False,
) -> None:
    """把某个子局改成"需要补充"的状态（模拟中断 / Provider 错误）。"""

    manifest = lab.store.load_manifest(experiment_id)
    for child in manifest.children:
        if int(child["matrix_index"]) == matrix_index:
            child["state"] = state
            child["cost_unknown"] = cost_unknown
            child["success"] = False
    lab.store.save_manifest(manifest)


def test_no_candidates_when_all_completed(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        plan = lab.supplement_candidates(experiment_id)
        assert plan["count"] == 0
        with pytest.raises(ExperimentError):
            lab.create_supplement(experiment_id)
    finally:
        runs.shutdown()


def test_interrupted_child_becomes_candidate(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        _mark_child(lab, experiment_id, 0, state=RunState.INTERRUPTED.value)
        plan = lab.supplement_candidates(experiment_id)
        assert plan["count"] == 1
        assert plan["candidates"][0]["reason"] == "interrupted"
        assert plan["candidates"][0]["matrix_index"] == 0
    finally:
        runs.shutdown()


def test_unknown_spend_child_becomes_candidate(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        _mark_child(
            lab, experiment_id, 1, state=RunState.PROVIDER_ERROR.value, cost_unknown=True
        )
        plan = lab.supplement_candidates(experiment_id)
        assert plan["count"] == 1
        assert plan["candidates"][0]["reason"] == "unknown_spend"
    finally:
        runs.shutdown()


def test_not_executed_cell_is_candidate(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        # 不提交：所有子局都是未执行。
        plan = lab.supplement_candidates(experiment_id)
        assert plan["count"] == 2
        assert {item["reason"] for item in plan["candidates"]} == {"not_executed"}
    finally:
        runs.shutdown()


def test_supplement_creates_new_experiment_without_touching_source(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        lab.submit(source_id)
        lab.wait(source_id, timeout=300)
        _mark_child(lab, source_id, 0, state=RunState.INTERRUPTED.value)
        source_before = lab.status(source_id).as_dict()
        source_runs_before = len(runs.list_runs())

        supplement_id = lab.create_supplement(source_id, reason="中断补跑")
        assert supplement_id != source_id
        spec = lab._spec(supplement_id)
        assert spec.supplement_of == source_id
        assert spec.supplement_reason == "中断补跑"
        assert len(spec.matrix()) == 1
        assert spec.matrix()[0].matrix_index == 0

        lab.submit(supplement_id)
        manifest = lab.wait(supplement_id, timeout=300)
        assert manifest.state is ExperimentState.COMPLETED
        assert manifest.counts["total"] == 1

        # 原实验的 manifest 与子局记录未被改写（除我们手动标记的那一处）。
        source_after = lab.status(source_id).as_dict()
        assert source_after["children"] == source_before["children"]
        assert source_after["state"] == source_before["state"]
        assert len(runs.list_runs()) == source_runs_before + 1
    finally:
        runs.shutdown()


def test_supplement_summary_and_report_declare_lineage(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        lab.submit(source_id)
        lab.wait(source_id, timeout=300)
        _mark_child(lab, source_id, 1, state=RunState.INTERRUPTED.value)
        supplement_id = lab.create_supplement(source_id, reason="中断补跑")
        lab.submit(supplement_id)
        lab.wait(supplement_id, timeout=300)

        summary = lab.summary(supplement_id)
        assert summary["supplement_of"] == source_id
        assert summary["supplement_reason"] == "中断补跑"
        report = lab.report(supplement_id)
        assert "补充实验" in report
        assert source_id in report
        assert "原始实验的记录与账本未被修改" in report
        # 原实验的报告不应出现"补充实验"字样。
        assert "补充实验" not in lab.report(source_id)
    finally:
        runs.shutdown()


def test_supplement_condition_filter(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        plan = lab.supplement_candidates(source_id)
        target = plan["candidates"][0]["condition_key"]
        supplement_id = lab.create_supplement(
            source_id, conditions=[target], reason="只补一个"
        )
        spec = lab._spec(supplement_id)
        assert spec.only_conditions == [target]
        assert len(spec.matrix()) == 1
        with pytest.raises(ExperimentError):
            lab.create_supplement(source_id, conditions=["MAP-99|seed=9|nope"])
    finally:
        runs.shutdown()


def test_supplement_is_idempotent(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        first = lab.create_supplement(source_id)
        second = lab.create_supplement(source_id)
        assert first == second
        assert len(lab.store.list_ids()) == 2
    finally:
        runs.shutdown()


def test_only_conditions_changes_fingerprint() -> None:
    base = _spec()
    narrowed = base.model_copy(
        update={"only_conditions": ["MAP-22|seed=0|basic.v1"]}
    )
    assert base.fingerprint() != narrowed.fingerprint()
    assert len(base.matrix()) == 2
    assert len(narrowed.matrix()) == 1
    # matrix_index 在过滤后重新从 0 连续编号。
    assert [cell.matrix_index for cell in narrowed.matrix()] == [0]


def test_only_conditions_survives_json_round_trip() -> None:
    spec = _spec().model_copy(update={"only_conditions": ["MAP-22|seed=0|basic.v1"]})
    payload = json.loads(json.dumps(spec.public_dict(), ensure_ascii=False))
    derived = {"seeds", "seed_source", "arms", "fingerprint", "only_conditions"}
    cleaned = {key: value for key, value in payload.items() if key not in derived}
    cleaned["only_conditions"] = payload["only_conditions"]
    reloaded = ExperimentSpec.model_validate(cleaned)
    assert reloaded.only_conditions == spec.only_conditions
    assert reloaded.fingerprint() == spec.fingerprint()


def test_supplement_requires_preflight_ok(tmp_path: Path) -> None:
    """补充实验若继承到不合法预算，必须拒绝而不是静默提交。"""

    runs, lab = _services(tmp_path)
    try:
        source_id = lab.create_experiment(_spec())
        # 人为把实验请求上限调到比单局上限还小，使预检失败。
        payload = lab.store.load_spec(source_id)
        payload["budget"]["experiment_request_cap"] = 5
        payload["budget"]["per_run_request_cap"] = 20
        lab.store.write_json(source_id, "experiment.json", payload)
        with pytest.raises(Exception):
            lab.create_supplement(source_id)
    finally:
        runs.shutdown()
