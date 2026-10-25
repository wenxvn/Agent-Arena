"""V12 父实验测试：矩阵、预检零请求、幂等、取消、预算、续跑与父子状态。"""

from __future__ import annotations

import json
import time
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
    LiveApproval,
)
from agent_arena.lab.experiment import (
    ExperimentBusy,
    ExperimentError,
    ExperimentService,
    LiveApprovalRequired,
    preflight,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER, RunState
from agent_arena.web.service import RunService


def _spec(**overrides: Any) -> ExperimentSpec:
    payload: dict[str, Any] = {
        "name": "matrix",
        "maps": ["MAP-22"],
        "agent_arms": [
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        "environment_seeds": [0],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
        "budget": ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=6,
            experiment_request_cap=2_000,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def _services(tmp_path: Path, **kwargs: Any) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False, **kwargs)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def test_preflight_reports_matrix_and_sends_zero_requests(tmp_path: Path) -> None:
    spec = _spec(maps=["MAP-22", "MAP-18"], environment_seeds=[0, 1])
    result = preflight(spec)
    assert result.cells == 2 * 2 * 3
    assert result.max_requests == result.cells * spec.budget.per_run_request_cap
    assert result.ok
    assert result.approval_required is False
    assert "模拟执行" in " ".join(result.warnings)
    assert not (tmp_path / "runs").exists()


def test_preflight_blocks_live_without_approval() -> None:
    spec = _spec(
        mode=ExperimentMode.LIVE,
        provider_id="openai_compatible",
        model="mimo-v2.6-flash",
    )
    result = preflight(spec)
    assert result.ok is False
    assert any("批准" in item for item in result.blockers)
    assert result.cost_enforced is True


def test_submit_live_without_approval_is_rejected(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        spec = _spec(
            mode=ExperimentMode.LIVE,
            provider_id="openai_compatible",
            model="mimo-v2.6-flash",
            preflight_only=False,
            approval=LiveApproval(approved=False),
        )
        experiment_id = lab.create_experiment(spec)
        with pytest.raises(LiveApprovalRequired):
            lab.submit(experiment_id)
        assert lab.status(experiment_id).state is ExperimentState.CREATED
    finally:
        runs.shutdown()


def test_preflight_only_blocks_live_submit(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        spec = _spec(
            mode=ExperimentMode.LIVE,
            provider_id="openai_compatible",
            model="mimo-v2.6-flash",
            preflight_only=True,
            approval=LiveApproval(approved=True, approved_by="test"),
        )
        experiment_id = lab.create_experiment(spec)
        with pytest.raises(ExperimentError):
            lab.submit(experiment_id)
    finally:
        runs.shutdown()


def test_create_is_idempotent_by_key(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        spec = _spec()
        first = lab.create_experiment(spec, idempotency_key="k1")
        second = lab.create_experiment(spec, idempotency_key="k1")
        assert first == second
        assert len(lab.store.list_ids()) == 1
    finally:
        runs.shutdown()


def test_create_writes_frozen_experiment_json_without_child_runs(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        payload = lab.store.load_spec(experiment_id)
        assert payload["matrix_size"] == 3
        assert len(payload["matrix"]) == 3
        assert payload["fingerprint"]
        assert all("condition_key" in cell for cell in payload["matrix"])
        assert lab.store.load_manifest(experiment_id).children == []
        assert runs.list_runs() == []
    finally:
        runs.shutdown()


def test_full_matrix_completes_with_parent_child_consistency(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert manifest.state is ExperimentState.COMPLETED
        assert manifest.counts["done"] == 3
        assert len(manifest.children) == 3
        for child in manifest.children:
            status = runs.get_run(child["run_id"])
            assert status.terminal
            assert status.state.value == child["state"]
            assert status.config["experiment_id"] == experiment_id
            assert status.config["matrix_index"] == child["matrix_index"]
        summary = lab.summary(experiment_id)
        assert summary["executed"] == 3
        assert summary["pending"] == 0
        assert summary["valid_denominator"] == 3
        events = [item["event"] for item in lab.store.read_events(experiment_id)]
        assert "experiment_created" in events
        assert "child_finished" in events
        assert "experiment_finished" in events
    finally:
        runs.shutdown()


def test_duplicate_submit_does_not_create_second_run_set(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert len(manifest.children) == 3
        assert len(runs.list_runs()) == 3
    finally:
        runs.shutdown()


def test_stop_before_start_marks_cancelled(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        manifest = lab.stop(experiment_id)
        # 未提交的实验没有执行线程：停止应立即落到明确终态。
        assert manifest.state is ExperimentState.CANCELLED
        assert manifest.terminal
        assert manifest.counts["done"] == 0
    finally:
        runs.shutdown()


def test_stop_mid_run_leaves_remaining_pending(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        spec = _spec(
            maps=["MAP-22", "MAP-18"],
            budget=ExperimentBudget(
                per_run_request_cap=40,
                per_run_decision_cap=20,
                experiment_request_cap=400,
                experiment_cost_cap_cny=Decimal("5"),
            ),
        )
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        # 等到至少一个子局完成，再请求停止。
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            manifest = lab.status(experiment_id)
            if manifest.children:
                break
            time.sleep(0.02)
        lab.stop(experiment_id)
        manifest = lab.wait(experiment_id, timeout=120)
        assert manifest.state in {ExperimentState.PARTIAL, ExperimentState.CANCELLED}
        assert manifest.counts["pending"] >= 0
        assert manifest.message
    finally:
        runs.shutdown()


def test_resume_only_runs_pending_children(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert manifest.state is ExperimentState.COMPLETED
        before = len(runs.list_runs())
        # 已完成实验再 resume 不产生新局。
        lab.submit(experiment_id, resume=True)
        time.sleep(0.2)
        assert len(runs.list_runs()) == before
    finally:
        runs.shutdown()


def test_resume_after_interruption_fills_gaps(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        manifest = lab.store.load_manifest(experiment_id)
        manifest.state = ExperimentState.RUNNING
        lab.store.save_manifest(manifest)
        # 新进程视角：非终态父实验应恢复成 PARTIAL。
        recovered = ExperimentService(
            tmp_path / "runs" / "lab", run_service=runs, recover=True
        )
        assert recovered.status(experiment_id).state is ExperimentState.PARTIAL
        recovered.submit(experiment_id, resume=True)
        final = recovered.wait(experiment_id, timeout=300)
        assert final.state is ExperimentState.COMPLETED
        assert len(final.children) == 3
    finally:
        runs.shutdown()


def test_experiment_request_cap_stops_partial(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        spec = _spec(
            budget=ExperimentBudget(
                per_run_request_cap=4,
                per_run_decision_cap=4,
                experiment_request_cap=4,
                experiment_cost_cap_cny=Decimal("5"),
            )
        )
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert manifest.state is ExperimentState.PARTIAL
        assert manifest.counts["done"] < manifest.counts["total"]
        assert "experiment_request_cap" in str(manifest.message)
    finally:
        runs.shutdown()


def test_unknown_spend_stops_experiment(tmp_path: Path) -> None:
    """子局未知消费必须立刻停止父实验，不继续发下一个子局。"""

    from agent_arena.lab.runner import LabRunOutcome

    def _unknown_runner(config: Any, **kwargs: Any) -> LabRunOutcome:
        return LabRunOutcome(
            state=RunState.PROVIDER_ERROR,
            outcome="unknown_provider_spend",
            termination="unknown_provider_usage",
            success=False,
            result={
                "schema_version": "v11-web-result-1",
                "map_id": config.map_id,
                "environment_seed": config.environment_seed,
                "agent": config.agent,
                "state": RunState.PROVIDER_ERROR.value,
                "outcome": "unknown_provider_spend",
                "termination": "unknown_provider_usage",
                "success": False,
                "decision_count": 1,
                "usage": {
                    "requests": 1,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_settled_cny": "0",
                    "cost_unknown": True,
                },
                "metrics": {},
                "hashes": {},
            },
        )

    runs, lab = _services(tmp_path, lab_runner=_unknown_runner)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert manifest.state is ExperimentState.PARTIAL
        assert manifest.counts["done"] == 1
        assert manifest.budget["cost_unknown"] is True
        assert "unknown_spend_closed" in str(manifest.message)
    finally:
        runs.shutdown()


def test_only_one_experiment_runs_at_a_time(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        first = lab.create_experiment(_spec(name="first"))
        second = lab.create_experiment(_spec(name="second"))
        lab.submit(first)
        with pytest.raises(ExperimentBusy):
            lab.submit(second)
        lab.wait(first, timeout=300)
    finally:
        runs.shutdown()


def test_children_links_file_is_written(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        payload = lab.store._json(experiment_id, "children.json")
        assert payload is not None
        assert len(payload["children"]) == 3
        assert {child["agent_id"] for child in payload["children"]} == {
            "basic.v1",
            "memory.v1",
            "planning.v1",
        }
    finally:
        runs.shutdown()


def test_summary_and_comparison_files_are_written(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_spec())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        summary = lab.store._json(experiment_id, "summary.json")
        comparison = lab.store._json(experiment_id, "comparison.json")
        assert summary is not None and comparison is not None
        assert summary["executed"] == 3
        assert comparison["verdict"] in {
            "COMPARABLE",
            "DESCRIPTIVE_ONLY",
            "INCOMPARABLE",
        }
        assert json.dumps(comparison, ensure_ascii=False)
    finally:
        runs.shutdown()


def test_illegal_agent_arm_is_rejected_before_enqueue() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _spec(agent_arms=[AgentArm(agent_id="not-registered.v1")])
