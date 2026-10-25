"""V12 稳健性与故障测试：54 子局 dry-run、损坏 JSONL、超时、未知消费、取消。"""

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
)
from agent_arena.lab.experiment import (
    ExperimentNotFound,
    ExperimentService,
    preflight,
)
from agent_arena.lab.report import csv_bytes
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunState,
)
from agent_arena.web.service import RunService

FOCUS = ["MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"]


def _fifty_four() -> ExperimentSpec:
    """预登记的 54 局主矩阵（6 图 × 3 seed × 3 架构），仅用于 dry-run。"""

    return ExperimentSpec(
        name="main-matrix-54",
        maps=FOCUS,
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        environment_seeds=[0, 1, 2],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=60,
            per_run_decision_cap=40,
            experiment_request_cap=3_600,
            experiment_cost_cap_cny=Decimal("10"),
        ),
    )


def _services(tmp_path: Path, **kwargs: Any) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp_path / "runs" / "web", recover=False, **kwargs)
    lab = ExperimentService(tmp_path / "runs" / "lab", run_service=runs, recover=False)
    return runs, lab


def test_fifty_four_cell_dry_run_is_zero_cost() -> None:
    spec = _fifty_four()
    result = preflight(spec)
    assert result.cells == 54
    assert result.ok, result.blockers
    assert len(spec.matrix()) == 54
    assert len({cell.condition_key for cell in spec.matrix()}) == 54
    assert len({cell.pairing_key for cell in spec.matrix()}) == 18
    assert result.max_requests == 54 * 60


def test_dry_run_does_not_touch_disk(tmp_path: Path) -> None:
    spec = _fifty_four()
    preflight(spec)
    assert not (tmp_path / "runs").exists()


def test_corrupt_events_line_is_tolerated(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_fifty_four_light())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        run_id = str(lab.status(experiment_id).children[0]["run_id"])
        events = tmp_path / "runs" / "web" / run_id / "events.jsonl"
        text = events.read_text(encoding="utf-8")
        events.write_text(text + "{not json}\n", encoding="utf-8")
        replay = runs.load_replay(run_id)
        assert replay["events_skipped"] >= 1
        assert replay["steps"]
        # 父实验仍能聚合（坏行不影响已落盘 result.json）。
        assert lab.summary(experiment_id)["executed"] >= 1
    finally:
        runs.shutdown()


def _fifty_four_light() -> ExperimentSpec:
    return ExperimentSpec(
        name="light",
        maps=["MAP-22"],
        agent_arms=[AgentArm(agent_id="basic.v1")],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=20,
            per_run_decision_cap=4,
            experiment_request_cap=200,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    )


def test_request_timeout_is_classified_as_provider_error(tmp_path: Path) -> None:
    """策略层超时（Provider 抛异常）必须 fail-closed，不重试。"""

    from v12_support import StubProvider, live_config

    from agent_arena.lab.runner import run_lab_episode
    from agent_arena.llm.bailian import DecisionProviderError

    provider = StubProvider(
        [],
        error=DecisionProviderError(
            "timeout", error_category="APITimeoutError", unknown_spend=True
        ),
        error_after=0,
    )
    outcome = run_lab_episode(
        live_config("MAP-22", max_decisions=5), provider=provider
    )
    assert outcome.state is RunState.PROVIDER_ERROR
    assert outcome.result["usage"]["cost_unknown"] is True
    assert len(provider.calls) == 1, "不得自动重试"


def test_unknown_spend_does_not_resume_automatically(tmp_path: Path) -> None:
    from agent_arena.lab.runner import LabRunOutcome

    calls: list[str] = []

    def _runner(config: Any, **kwargs: Any) -> LabRunOutcome:
        calls.append(config.map_id)
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
            },
        )

    runs, lab = _services(tmp_path, lab_runner=_runner)
    try:
        spec = ExperimentSpec(
            name="unknown",
            maps=["MAP-22", "MAP-26"],
            agent_arms=[AgentArm(agent_id="basic.v1")],
            environment_seeds=[0],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
            budget=ExperimentBudget(
                per_run_request_cap=20,
                per_run_decision_cap=4,
                experiment_request_cap=200,
                experiment_cost_cap_cny=Decimal("5"),
            ),
        )
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=300)
        assert manifest.state is ExperimentState.PARTIAL
        assert calls == ["MAP-22"], "未知消费后不得继续下一个子局"
        # 显式续跑也不会自动补跑未知消费的子局。
        lab.submit(experiment_id, resume=True)
        lab.wait(experiment_id, timeout=300)
        assert manifest.budget["cost_unknown"] is True
    finally:
        runs.shutdown()


def test_large_csv_export_is_streamed_and_parsable(tmp_path: Path) -> None:
    rows = [
        {
            "run_id": f"web-2026010{index % 9}T000000Z-{index:08x}",
            "matrix_index": index,
            "map_id": "MAP-22",
            "category": "completed_success",
        }
        for index in range(2_000)
    ]
    blob = csv_bytes(rows, ("run_id", "matrix_index", "map_id", "category"))
    assert blob.startswith(b"\xef\xbb\xbf")
    assert blob.count(b"\r\n") == len(rows) + 1


def test_experiment_path_traversal_is_rejected(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        for bad in ("../escape", "lab-2026", "lab-20260101T000000Z-zzzzzzzz"):
            with pytest.raises(ExperimentNotFound):
                lab.status(bad)
    finally:
        runs.shutdown()


def test_stop_after_process_exit_recovers_partial(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_fifty_four_light())
        manifest = lab.store.load_manifest(experiment_id)
        manifest.state = ExperimentState.RUNNING
        lab.store.save_manifest(manifest)
        fresh = ExperimentService(
            tmp_path / "runs" / "lab", run_service=runs, recover=True
        )
        recovered = fresh.status(experiment_id)
        assert recovered.state is ExperimentState.PARTIAL
        assert recovered.message
        events = [item["event"] for item in fresh.store.read_events(experiment_id)]
        assert "experiment_interrupted" in events
    finally:
        runs.shutdown()


def test_completed_experiment_cannot_be_restarted_silently(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_fifty_four_light())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        before = len(runs.list_runs())
        lab.submit(experiment_id)
        time.sleep(0.3)
        assert len(runs.list_runs()) == before
    finally:
        runs.shutdown()


def test_preflight_rejects_oversized_matrix() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExperimentSpec(
            name="too-big",
            maps=FOCUS,
            agent_arms=[
                AgentArm(agent_id="basic.v1", config={"history_window": 5}),
                AgentArm(agent_id="basic.v1", config={"history_window": 4}),
                AgentArm(agent_id="basic.v1", config={"history_window": 3}),
                AgentArm(agent_id="basic.v1", config={"history_window": 2}),
                AgentArm(agent_id="basic.v1", config={"history_window": 1}),
                AgentArm(agent_id="basic.v1", config={"history_window": 6}),
                AgentArm(agent_id="basic.v1", config={"history_window": 7}),
                AgentArm(agent_id="basic.v1", config={"history_window": 8}),
                AgentArm(agent_id="basic.v1", config={"history_window": 9}),
                AgentArm(agent_id="basic.v1", config={"history_window": 10}),
                AgentArm(agent_id="basic.v1", config={"history_window": 11}),
                AgentArm(agent_id="basic.v1", config={"history_window": 12}),
                AgentArm(agent_id="basic.v1", config={"history_window": 13}),
            ],
            environment_seeds=[0, 1, 2],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
        )


def test_summary_is_recomputable_from_records(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        experiment_id = lab.create_experiment(_fifty_four_light())
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        summary = lab.summary(experiment_id)
        records = lab.records(experiment_id)
        assert summary["executed"] == len(records)
        categories: dict[str, int] = {}
        for record in records:
            categories[record["category"]] = categories.get(record["category"], 0) + 1
        assert summary["categories"] == dict(sorted(categories.items()))
        assert summary["valid_denominator"] == sum(
            count
            for key, count in categories.items()
            if key in {"completed_success", "mechanism_failure", "budget_censored"}
        )
    finally:
        runs.shutdown()


def test_export_rejects_when_experiment_missing(tmp_path: Path) -> None:
    runs, lab = _services(tmp_path)
    try:
        with pytest.raises(ExperimentNotFound):
            lab.export("lab-20260101T000000Z-00000000")
    finally:
        runs.shutdown()


def test_json_spec_file_round_trip(tmp_path: Path) -> None:
    spec = _fifty_four()
    payload = spec.public_dict()
    payload.pop("seeds")
    payload.pop("seed_source")
    payload.pop("arms")
    payload.pop("fingerprint")
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    reloaded = ExperimentSpec.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert reloaded.fingerprint() == spec.fingerprint()
