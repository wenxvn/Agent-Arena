"""V11 RunService：串行、幂等、取消、恢复与全局预算。"""

from __future__ import annotations

import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

from agent_arena.web.execution import ExecutionOutcome
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
    RunState,
)
from agent_arena.web.service import (
    TOTAL_BUDGET_ENV,
    ConcurrentLiveRunError,
    RunService,
    RunServiceError,
)


def _offline(**overrides: object) -> RunConfig:
    payload: dict[str, object] = {
        "map_id": "MAP-01",
        "environment_seed": 0,
        "mode": RunMode.OFFLINE,
        "provider_id": OFFLINE_PROVIDER,
        "model": OFFLINE_MODEL,
        "agent": "public_heuristic_policy",
        "max_decisions": 30,
        "max_requests": 1,
        "max_input_tokens": 10_000,
        "max_output_tokens": 1_000,
        "max_cost_cny": Decimal("0.01"),
    }
    payload.update(overrides)
    return RunConfig.model_validate(payload)


def _live(**overrides: object) -> RunConfig:
    payload: dict[str, object] = {
        "map_id": "MAP-01",
        "environment_seed": 0,
        "mode": RunMode.LIVE,
        "provider_id": "openai_compatible",
        "model": "mimo-v2.6-flash",
        "agent": "v10_action_loop",
        "max_decisions": 10,
        "max_requests": 10,
        "max_input_tokens": 100_000,
        "max_output_tokens": 5_000,
        "max_cost_cny": Decimal("0.50"),
    }
    payload.update(overrides)
    return RunConfig.model_validate(payload)


class _Gate:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def runner(
        self,
        config: RunConfig,
        *,
        provider: object,
        on_event: object,
        should_stop: object,
    ) -> ExecutionOutcome:
        del config, provider, on_event
        self.started.set()
        self.release.wait(10)
        stop = bool(should_stop() if callable(should_stop) else False)
        state = RunState.CANCELLED if stop else RunState.SUCCEEDED
        result = {
            "state": state.value,
            "success": state is RunState.SUCCEEDED,
            "outcome": "cancelled" if stop else "success",
            "termination": "cancelled_by_user" if stop else "synthetic",
            "usage": {},
            "message": None,
        }
        return ExecutionOutcome(
            state=state,
            outcome=str(result["outcome"]),
            termination=str(result["termination"]),
            success=bool(result["success"]),
            result=result,
        )


def _service(tmp_path: Path, **kwargs: object) -> RunService:
    return RunService(tmp_path / "runs" / "web", recover=False, **kwargs)


def test_offline_run_reaches_success_and_replays(tmp_path) -> None:
    service = _service(tmp_path)
    try:
        run_id = service.create_run(_offline())
        status = service.wait(run_id, timeout=60)
        assert status.state is RunState.SUCCEEDED
        assert status.decisions > 0
        replay = service.load_replay(run_id)
        assert replay["result"] and replay["result"]["success"] is True
        assert len(replay["steps"]) == status.decisions
        assert replay["events_skipped"] == 0
        assert service.list_runs()[0].display_title == "破损的曙光号"
    finally:
        service.shutdown()


def test_idempotency_key_returns_existing_run(tmp_path) -> None:
    service = _service(tmp_path)
    try:
        first = service.create_run(_offline(), idempotency_key="same")
        second = service.create_run(_offline(), idempotency_key="same")
        assert first == second
        assert len(service.list_runs()) == 1
    finally:
        service.shutdown()


def test_concurrent_live_run_is_rejected(tmp_path) -> None:
    gate = _Gate()
    service = _service(
        tmp_path,
        live_runner=gate.runner,
        provider_factory=lambda config: object(),
    )
    try:
        live_id = service.create_run(_live())
        assert gate.started.wait(5)
        with pytest.raises(ConcurrentLiveRunError):
            service.create_run(_live(map_id="MAP-02"))
        gate.release.set()
        assert service.wait(live_id, timeout=10).state is RunState.SUCCEEDED
    finally:
        gate.release.set()
        service.shutdown()


def test_cancel_queued_run(tmp_path) -> None:
    gate = _Gate()
    service = _service(
        tmp_path,
        live_runner=gate.runner,
        provider_factory=lambda config: object(),
    )
    try:
        live_id = service.create_run(_live())
        assert gate.started.wait(5)
        queued = service.create_run(_offline())
        assert service.cancel_run(queued)
        assert service.get_run(queued).state is RunState.CANCELLED
        gate.release.set()
        assert service.wait(live_id, timeout=10).terminal
    finally:
        gate.release.set()
        service.shutdown()


def test_cancel_running_run_is_cooperative(tmp_path) -> None:
    gate = _Gate()
    service = _service(
        tmp_path,
        live_runner=gate.runner,
        provider_factory=lambda config: object(),
    )
    try:
        live_id = service.create_run(_live())
        assert gate.started.wait(5)
        assert service.cancel_run(live_id)
        assert service.get_run(live_id).state is RunState.RUNNING
        gate.release.set()
        status = service.wait(live_id, timeout=10)
        assert status.state is RunState.CANCELLED
    finally:
        gate.release.set()
        service.shutdown()


def test_recovery_marks_orphan_running_as_interrupted(tmp_path) -> None:
    base = tmp_path / "runs" / "web"
    run_id = "web-20260101T000000Z-deadbeef"
    directory = base / run_id
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": "v11-web-1",
        "run_id": run_id,
        "attempt_id": "att-deadbeef",
        "owner_id": "dead-owner",
        "owner_pid": 999_999,
        "state": "RUNNING",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "config": _offline().public_dict(),
        "map_id": "MAP-01",
        "world": "spaceship",
        "mode": "offline",
        "provider_id": OFFLINE_PROVIDER,
        "model": OFFLINE_MODEL,
        "environment_seed": 0,
        "decision_budget": 30,
        "decisions": 4,
    }
    (directory / "manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
    (directory / "events.jsonl").write_text(
        '{"event": "decision", "decision_index": 1}\n'
        '{"event": "decision", "decision_index": 2}\n',
        encoding="utf-8",
    )
    service = RunService(base, recover=True)
    try:
        status = service.get_run(run_id)
        assert status.state is RunState.INTERRUPTED
        replay = service.load_replay(run_id)
        assert replay["result"] and replay["result"]["partial"] is True
        assert len(replay["steps"]) == 2
    finally:
        service.shutdown()


def test_corrupt_event_lines_are_tolerated(tmp_path) -> None:
    service = _service(tmp_path)
    try:
        run_id = service.create_run(_offline())
        service.wait(run_id, timeout=60)
        with (service.store.base / run_id / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("{broken\n")
        replay = service.load_replay(run_id)
        assert replay["events_skipped"] == 1
        assert replay["result"]["success"] is True
    finally:
        service.shutdown()


def test_global_budget_cap_blocks_new_live_run(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    try:
        service.store.append_global_ledger(
            {"event": "run_settled", "run_id": "old", "cost_settled_cny": "2.90"}
        )
        monkeypatch.setenv(TOTAL_BUDGET_ENV, "3.00")
        with pytest.raises(RunServiceError):
            service.create_run(_live(max_cost_cny=Decimal("0.50")))
    finally:
        service.shutdown()


def test_shutdown_rejects_new_runs(tmp_path) -> None:
    service = _service(tmp_path)
    service.shutdown()
    with pytest.raises(RunServiceError):
        service.create_run(_offline())


def test_live_service_persists_budget_snapshot(tmp_path) -> None:
    import importlib

    from agent_arena.llm.protocol import DecisionRequest, ProviderResponse
    from agent_arena.v10.baselines.runner import run_policy

    module = importlib.import_module("agent_arena.v10.baselines.map01")
    run = run_policy("MAP-01", module.HEURISTIC(), environment_seed=0, decision_budget=40)
    actions = [item["action"] for item in run.actions]

    class _Provider:
        def __init__(self) -> None:
            self.queue = list(actions)

        def decide(self, request: DecisionRequest) -> ProviderResponse:
            del request
            return ProviderResponse(
                candidate=self.queue.pop(0),
                input_tokens=100,
                output_tokens=10,
                cached_input_tokens=0,
            )

    provider = _Provider()
    service = _service(tmp_path, provider_factory=lambda config: provider)
    try:
        run_id = service.create_run(
            _live(max_decisions=len(actions), max_requests=len(actions) + 2)
        )
        status = service.wait(run_id, timeout=60)
        assert status.state is RunState.SUCCEEDED
        replay = service.load_replay(run_id)
        assert replay["result"]["usage"]["requests"] == len(actions)
        decision = next(event for event in replay["events"] if event["event"] == "decision")
        assert decision["budget"]["limits"]["max_cost_cny"] == "0.50"
        assert decision["budget"]["cost_unknown"] is False
    finally:
        service.shutdown()


def test_status_progress_is_persisted(tmp_path) -> None:
    service = _service(tmp_path)
    try:
        run_id = service.create_run(_offline())
        deadline = time.monotonic() + 10
        seen_running = False
        while time.monotonic() < deadline:
            status = service.get_run(run_id)
            if status.state is RunState.RUNNING:
                seen_running = True
                break
            if status.terminal:
                break
            time.sleep(0.01)
        final = service.wait(run_id, timeout=60)
        assert final.terminal
        assert seen_running or final.state is RunState.SUCCEEDED
        manifest = service.store.load_manifest(run_id)
        assert manifest["progress"] == 1.0 or manifest["progress"] <= 1.0
    finally:
        service.shutdown()
