"""V11 RunService：提交、排队、执行、取消、恢复与查询的唯一入口。

UI 只调用本服务，不直接创建环境或 Provider。默认单 worker 串行，避免多个付费
任务同时发出请求；状态一律以 ``runs/web/<run_id>/manifest.json`` 为准。
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from queue import Queue
from typing import Any
from uuid import uuid4

from agent_arena.llm.protocol import DecisionProvider
from agent_arena.web.catalog import DISPLAY_TITLES
from agent_arena.web.clock import new_attempt_id, new_run_id, utc_now
from agent_arena.web.execution import ExecutionOutcome, execute_live, execute_offline
from agent_arena.web.lock import SingleInstanceLock
from agent_arena.web.providers import build_live_provider
from agent_arena.web.safety import classify_exception, error_hint
from agent_arena.web.schemas import (
    ALLOWED_TRANSITIONS,
    LEGACY_LIVE_AGENT,
    SCHEMA_VERSION,
    TERMINAL_STATES,
    RunConfig,
    RunMode,
    RunState,
    RunStatus,
    RunSummary,
)
from agent_arena.web.store import RunNotFoundError, RunStore
from agent_arena.worlds.scenario_v8.catalog import WORLD_OF

TOTAL_BUDGET_ENV = "AGENT_ARENA_WEB_TOTAL_BUDGET_CNY"

Runner = Callable[..., ExecutionOutcome]
ProviderFactory = Callable[[RunConfig], DecisionProvider]

_ACTIVE_OWNERS: set[str] = set()


def _default_lab_runner(*args: Any, **kwargs: Any) -> Any:
    """延迟导入 Lab runner：V11 单局路径不因 V12 模块缺失而不可用。"""

    from agent_arena.lab.runner import run_lab_episode

    return run_lab_episode(*args, **kwargs)


def _default_simulated_provider(config: RunConfig) -> DecisionProvider:
    from agent_arena.lab.simulated import build_simulated_provider

    return build_simulated_provider(config)


class RunServiceError(RuntimeError):
    """服务层可预期的拒绝。"""


class ConcurrentLiveRunError(RunServiceError):
    """已有付费任务在运行或排队。"""


class InvalidTransitionError(RunServiceError):
    """非法的状态迁移。"""


class RunService:
    def __init__(
        self,
        base_dir: Any,
        *,
        recover: bool = True,
        owner_id: str | None = None,
        offline_runner: Runner = execute_offline,
        live_runner: Runner = execute_live,
        provider_factory: ProviderFactory = build_live_provider,
        lab_runner: Runner = _default_lab_runner,
        simulated_provider_factory: ProviderFactory = _default_simulated_provider,
    ) -> None:
        self.store = RunStore(base_dir)
        self._owner = owner_id or f"{os.getpid()}-{uuid4().hex[:8]}"
        self._lock = threading.RLock()
        self._cancel: dict[str, threading.Event] = {}
        self._queue: Queue[str | None] = Queue()
        self._active: str | None = None
        self._worker: threading.Thread | None = None
        self._shutdown = False
        self._offline_runner = offline_runner
        self._live_runner = live_runner
        self._provider_factory = provider_factory
        self._lab_runner = lab_runner
        self._simulated_provider_factory = simulated_provider_factory
        self._instance_lock = SingleInstanceLock(self.store.base / ".service.lock")
        self._instance_lock.acquire()
        _ACTIVE_OWNERS.add(self._owner)
        try:
            self.recovery = self.recover() if recover else {"recovered": [], "broken": []}
        except Exception:
            _ACTIVE_OWNERS.discard(self._owner)
            self._instance_lock.release()
            raise

    # ---------------------------------------------------------------- lifecycle
    def recover(self) -> dict[str, list[str]]:
        """把上一个进程遗留的非终态运行标成 INTERRUPTED，并保留可读部分。"""

        recovered: list[str] = []
        broken: list[str] = []
        manifests, broken_ids = self.store.discover()
        broken.extend(broken_ids)
        for manifest in manifests:
            state = RunState(str(manifest.get("state", RunState.CREATED.value)))
            if state in TERMINAL_STATES:
                continue
            if str(manifest.get("owner_id", "")) in _ACTIVE_OWNERS:
                continue
            run_id = str(manifest["run_id"])
            result = self.store.load_result(run_id)
            result_state = str((result or {}).get("state", ""))
            if result is not None and result_state in {item.value for item in TERMINAL_STATES}:
                manifest["state"] = result_state
                self.store.save_manifest(manifest)
                self.store.append_event(
                    run_id,
                    {"event": "recovered_from_result", "state": result_state},
                )
                recovered.append(run_id)
                continue
            partial = self._partial_result(
                manifest,
                state=RunState.INTERRUPTED,
                outcome="interrupted",
                termination="interrupted_on_restart",
                message="进程在运行中终止；已保留中断前的公开动作记录。",
            )
            self.store.save_result(run_id, partial)
            manifest["state"] = RunState.INTERRUPTED.value
            manifest["outcome"] = "interrupted"
            manifest["termination"] = "interrupted_on_restart"
            manifest["message"] = partial["message"]
            manifest["finished_at"] = utc_now()
            manifest["success"] = False
            self.store.save_manifest(manifest)
            self.store.append_event(
                run_id, {"event": "interrupted", "reason": "process_restart"}
            )
            recovered.append(run_id)
        return {"recovered": recovered, "broken": broken}

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
            for event in self._cancel.values():
                event.set()
            self._queue.put(None)
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=5)
        _ACTIVE_OWNERS.discard(self._owner)
        self._instance_lock.release()

    # ------------------------------------------------------------------- create
    def create_run(self, config: RunConfig, *, idempotency_key: str | None = None) -> str:
        with self._lock:
            if self._shutdown:
                raise RunServiceError("服务已关闭。")
            key = idempotency_key or config.idempotency_key
            if key:
                existing = self.store.find_by_idempotency(key)
                if existing:
                    return existing
            if config.mode is RunMode.LIVE:
                self._guard_live_start(config)
            run_id = self._unique_run_id()
            attempt_id = new_attempt_id()
            manifest: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "attempt_id": attempt_id,
                "owner_id": self._owner,
                "owner_pid": os.getpid(),
                "state": RunState.CREATED.value,
                "created_at": config.created_at,
                "updated_at": utc_now(),
                "started_at": None,
                "finished_at": None,
                "config": config.public_dict(),
                "map_id": config.map_id,
                "world": WORLD_OF[config.map_id],
                "title": DISPLAY_TITLES[config.map_id],
                "mode": config.mode.value,
                "provider_id": config.provider_id,
                "model": config.model,
                "environment_seed": config.environment_seed,
                "decision_budget": config.max_decisions,
                "decisions": 0,
                "progress": 0.0,
                "outcome": None,
                "termination": None,
                "message": None,
                "success": False,
                "budget": {},
                "hashes": {},
                "idempotency_key": key,
            }
            self.store.save_manifest(manifest)
            self.store.append_event(
                run_id,
                {
                    "event": "run_created",
                    "map_id": config.map_id,
                    "mode": config.mode.value,
                    "provider_id": config.provider_id,
                    "model": config.model,
                    "environment_seed": config.environment_seed,
                },
            )
            self._set_state(manifest, RunState.QUEUED)
            self._cancel[run_id] = threading.Event()
            if config.mode is RunMode.LIVE:
                self._ledger_start(run_id, config)
            self._queue.put(run_id)
            self._ensure_worker()
            return run_id

    def _guard_live_start(self, config: RunConfig) -> None:
        manifests, _ = self.store.discover()
        for manifest in manifests:
            if manifest.get("mode") != RunMode.LIVE.value:
                continue
            if RunState(str(manifest.get("state"))) in {RunState.QUEUED, RunState.RUNNING}:
                raise ConcurrentLiveRunError(
                    f"已有付费任务 {manifest.get('run_id')} 在运行或排队；其余付费任务已拒绝。"
                )
        cap = self._total_budget_cap()
        if cap is None:
            return
        settled, pending, unknown = self._global_spend()
        projected = settled + pending + unknown
        if projected + config.max_cost_cny > cap:
            raise RunServiceError(
                f"平台总预算上限 CNY {cap} 不足：已占用 {projected}，本局最多 "
                f"{config.max_cost_cny}。"
            )

    # ----------------------------------------------------------------- execute
    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._worker_loop, name="agent-arena-web", daemon=True
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            run_id = self._queue.get()
            try:
                if run_id is None:
                    return
                self._execute(run_id)
            finally:
                self._queue.task_done()

    def _execute(self, run_id: str) -> None:
        with self._lock:
            try:
                manifest = self.store.load_manifest(run_id)
            except RunNotFoundError:
                return
            if RunState(str(manifest["state"])) is not RunState.QUEUED:
                return
            self._active = run_id
            self._set_state(manifest, RunState.RUNNING)
            config = RunConfig.model_validate(manifest["config"])
            cancel_event = self._cancel.setdefault(run_id, threading.Event())

        def on_event(event: dict[str, Any]) -> None:
            with self._lock:
                self.store.append_event(run_id, event)
                current = self.store.load_manifest(run_id)
                if event.get("event") == "decision":
                    current["decisions"] = max(
                        int(current.get("decisions") or 0),
                        int(event.get("decision_index") or 0),
                    )
                    budget_size = max(1, int(current.get("decision_budget") or 1))
                    current["progress"] = round(
                        min(1.0, int(current["decisions"]) / budget_size), 4
                    )
                if isinstance(event.get("budget"), dict):
                    current["budget"] = event["budget"]
                self.store.save_manifest(current)

        try:
            if config.mode is RunMode.OFFLINE:
                outcome = self._offline_runner(
                    config,
                    on_event=on_event,
                    should_stop=cancel_event.is_set,
                )
            elif config.mode is RunMode.SIMULATED:
                provider = self._simulated_provider_factory(config)
                outcome = self._lab_runner(
                    config,
                    provider=provider,
                    on_event=on_event,
                    should_stop=cancel_event.is_set,
                    run_id=run_id,
                )
            elif config.agent != LEGACY_LIVE_AGENT:
                provider = self._provider_factory(config)
                outcome = self._lab_runner(
                    config,
                    provider=provider,
                    on_event=on_event,
                    should_stop=cancel_event.is_set,
                    run_id=run_id,
                )
            else:
                provider = self._provider_factory(config)
                outcome = self._live_runner(
                    config,
                    provider=provider,
                    on_event=on_event,
                    should_stop=cancel_event.is_set,
                )
        except ValueError as exc:
            category = str(exc)
            if category not in {"missing_api_key", "missing_base_url"}:
                category = classify_exception(exc)
            self._finish(
                run_id,
                state=RunState.PROVIDER_ERROR,
                outcome="provider_config_error",
                termination=category,
                message=error_hint(category),
                success=False,
                budget={},
            )
            self._clear_run(run_id)
            return
        except Exception as exc:  # noqa: BLE001 - service boundary
            self._finish(
                run_id,
                state=RunState.FAILED,
                outcome="internal_error",
                termination=classify_exception(exc),
                message="运行内部错误；已停止，未自动重试。",
                success=False,
                budget={},
            )
            self._clear_run(run_id)
            return

        self._finish(
            run_id,
            state=outcome.state,
            outcome=outcome.outcome,
            termination=outcome.termination,
            message=str(outcome.result.get("message") or "") or None,
            success=outcome.success,
            budget=dict(outcome.result.get("usage") or {}),
            result=outcome.result,
        )
        self._clear_run(run_id)

    def _finish(
        self,
        run_id: str,
        *,
        state: RunState,
        outcome: str,
        termination: str,
        message: str | None,
        success: bool,
        budget: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            manifest = self.store.load_manifest(run_id)
            payload: dict[str, Any]
            if result is None:
                payload = self._partial_result(
                    manifest,
                    state=state,
                    outcome=outcome,
                    termination=termination,
                    message=message,
                    budget=budget,
                )
            else:
                payload = result
            payload["run_id"] = run_id
            payload["attempt_id"] = manifest.get("attempt_id")
            payload["config"] = manifest.get("config", {})
            payload["success"] = bool(payload.get("success") or success)
            self.store.save_result(run_id, payload)
            manifest["state"] = state.value
            manifest["outcome"] = outcome
            manifest["termination"] = termination
            manifest["message"] = message
            manifest["success"] = bool(payload.get("success"))
            manifest["budget"] = budget or manifest.get("budget", {})
            manifest["hashes"] = {
                "scenario_hash": payload.get("scenario_hash"),
                "rule_hash": payload.get("rule_hash"),
                "metric_hash": payload.get("metric_hash"),
                "metric_schema_hash": payload.get("metric_schema_hash"),
                "prompt_hash": payload.get("prompt_hash"),
            }
            manifest["finished_at"] = utc_now()
            manifest["updated_at"] = utc_now()
            self.store.save_manifest(manifest)
            self.store.append_event(
                run_id,
                {
                    "event": "run_finished",
                    "state": state.value,
                    "outcome": outcome,
                    "success": bool(payload.get("success")),
                    "termination": termination,
                },
            )
            if manifest.get("mode") == RunMode.LIVE.value:
                self._ledger_finish(run_id, payload, state)

    def _clear_run(self, run_id: str) -> None:
        with self._lock:
            self._cancel.pop(run_id, None)
            if self._active == run_id:
                self._active = None

    # ------------------------------------------------------------------- cancel
    def cancel_run(self, run_id: str) -> bool:
        with self._lock:
            manifest = self.store.load_manifest(run_id)
            state = RunState(str(manifest["state"]))
            if state in TERMINAL_STATES:
                return False
            event = self._cancel.setdefault(run_id, threading.Event())
            event.set()
            self.store.append_event(run_id, {"event": "cancel_requested"})
            if state in {RunState.CREATED, RunState.QUEUED}:
                partial = self._partial_result(
                    manifest,
                    state=RunState.CANCELLED,
                    outcome="cancelled",
                    termination="cancelled_before_start",
                    message="运行在开始前被取消。",
                )
                self.store.save_result(run_id, partial)
                manifest["state"] = RunState.CANCELLED.value
                manifest["outcome"] = "cancelled"
                manifest["termination"] = "cancelled_before_start"
                manifest["message"] = partial["message"]
                manifest["finished_at"] = utc_now()
                manifest["success"] = False
                self.store.save_manifest(manifest)
                self.store.append_event(
                    run_id, {"event": "run_finished", "state": RunState.CANCELLED.value}
                )
                if manifest.get("mode") == RunMode.LIVE.value:
                    self._ledger_abort(run_id)
                return True
            manifest["message"] = "停止请求已收到；将在当前请求或步骤结束后生效。"
            self.store.save_manifest(manifest)
            return True

    # ------------------------------------------------------------------ queries
    def get_run(self, run_id: str) -> RunStatus:
        return RunStatus.from_manifest(self.store.load_manifest(run_id))

    def list_runs(
        self,
        *,
        map_id: str | None = None,
        state: str | None = None,
        mode: str | None = None,
        provider_id: str | None = None,
        model: str | None = None,
        since: str | None = None,
        limit: int | None = None,
    ) -> list[RunSummary]:
        manifests, _ = self.store.discover()
        rows: list[RunSummary] = []
        for manifest in manifests:
            if map_id and manifest.get("map_id") != map_id:
                continue
            if state and manifest.get("state") != state:
                continue
            if mode and manifest.get("mode") != mode:
                continue
            if provider_id and manifest.get("provider_id") != provider_id:
                continue
            if model and manifest.get("model") != model:
                continue
            created = str(manifest.get("created_at") or "")
            if since and created[:10] < since[:10]:
                continue
            rows.append(self._summary(manifest))
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[:limit] if limit else rows

    def _summary(self, manifest: dict[str, Any]) -> RunSummary:
        raw_budget = manifest.get("budget")
        raw_hashes = manifest.get("hashes")
        budget: dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
        hashes: dict[str, Any] = raw_hashes if isinstance(raw_hashes, dict) else {}
        cost = budget.get("cost_settled_cny")
        try:
            cost_value = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            cost_value = None
        return RunSummary(
            run_id=str(manifest.get("run_id", "")),
            map_id=str(manifest.get("map_id", "")),
            world=str(manifest.get("world", "")),
            mode=str(manifest.get("mode", "")),
            provider_id=str(manifest.get("provider_id", "")),
            model=str(manifest.get("model", "")),
            environment_seed=int(manifest.get("environment_seed") or 0),
            state=str(manifest.get("state", "")),
            outcome=manifest.get("outcome"),
            success=bool(manifest.get("success")),
            decisions=int(manifest.get("decisions") or 0),
            decision_budget=int(manifest.get("decision_budget") or 0),
            created_at=str(manifest.get("created_at", "")),
            finished_at=manifest.get("finished_at"),
            cost_settled_cny=cost_value,
            cost_unknown=bool(budget.get("cost_unknown")),
            rule_hash=hashes.get("rule_hash"),
            metric_hash=hashes.get("metric_hash"),
            metric_schema_hash=hashes.get("metric_schema_hash"),
            display_title=DISPLAY_TITLES.get(str(manifest.get("map_id", "")), ""),
        )

    def load_replay(self, run_id: str) -> dict[str, Any]:
        manifest = self.store.load_manifest(run_id)
        events, skipped = self.store.read_events_with_diagnostics(run_id)
        steps = [event for event in events if event.get("event") == "decision"]
        return {
            "run_id": run_id,
            "manifest": manifest,
            "status": RunStatus.from_manifest(manifest),
            "result": self.store.load_result(run_id),
            "steps": steps,
            "events": events,
            "events_skipped": skipped,
        }

    def diagnostics(self) -> dict[str, Any]:
        manifests, broken = self.store.discover()
        return {
            "runs": len(manifests),
            "broken": broken,
            "base_dir": str(self.store.base),
            "active": self._active,
            "total_spend": [str(value) for value in self._global_spend()],
        }

    def wait(self, run_id: str, *, timeout: float = 30.0, interval: float = 0.05) -> RunStatus:
        deadline = time.monotonic() + timeout
        while True:
            status = self.get_run(run_id)
            if status.terminal or time.monotonic() >= deadline:
                return status
            time.sleep(interval)

    # ------------------------------------------------------------------ private
    def _set_state(self, manifest: dict[str, Any], state: RunState, **extra: Any) -> None:
        current = RunState(str(manifest["state"]))
        if current is state:
            return
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if state not in allowed:
            raise InvalidTransitionError(f"{current.value} -> {state.value} 非法。")
        manifest["state"] = state.value
        manifest.update(extra)
        now = utc_now()
        if state is RunState.RUNNING:
            manifest["started_at"] = manifest.get("started_at") or now
        if state in TERMINAL_STATES:
            manifest["finished_at"] = now
        self.store.save_manifest(manifest)
        self.store.append_event(
            manifest["run_id"],
            {"event": "state_changed", "from": current.value, "to": state.value},
        )

    def _partial_result(
        self,
        manifest: dict[str, Any],
        *,
        state: RunState,
        outcome: str,
        termination: str,
        message: str | None,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "v11-web-result-1",
            "run_id": manifest.get("run_id"),
            "attempt_id": manifest.get("attempt_id"),
            "map_id": manifest.get("map_id"),
            "world": manifest.get("world"),
            "title": manifest.get("title") or DISPLAY_TITLES.get(str(manifest.get("map_id"))),
            "environment_seed": manifest.get("environment_seed"),
            "mode": manifest.get("mode"),
            "provider_id": manifest.get("provider_id"),
            "model": manifest.get("model"),
            "agent": (manifest.get("config") or {}).get("agent"),
            "state": state.value,
            "outcome": outcome,
            "success": False,
            "termination": termination,
            "message": message,
            "partial": True,
            "decision_count": int(manifest.get("decisions") or 0),
            "config": manifest.get("config", {}),
            "usage": budget or manifest.get("budget", {}),
            "started_at": manifest.get("started_at"),
            "finished_at": utc_now(),
        }

    def _unique_run_id(self) -> str:
        self.store.ensure_base()
        for _ in range(20):
            candidate = new_run_id()
            if not (self.store.base / candidate).exists():
                return candidate
        raise RunServiceError("无法生成唯一 run_id。")

    # -------------------------------------------------------------- global spend
    def _total_budget_cap(self) -> Decimal | None:
        raw = os.environ.get(TOTAL_BUDGET_ENV)
        if not raw:
            return None
        try:
            cap = Decimal(raw)
        except InvalidOperation as exc:
            raise RunServiceError(f"{TOTAL_BUDGET_ENV} 不是合法金额。") from exc
        if cap <= 0:
            raise RunServiceError(f"{TOTAL_BUDGET_ENV} 必须大于 0。")
        return cap

    def _global_spend(self) -> tuple[Decimal, Decimal, Decimal]:
        events = self.store.read_global_ledger()
        started: dict[str, Decimal] = {}
        settled_ids: set[str] = set()
        aborted: set[str] = set()
        settled = Decimal(0)
        unknown = Decimal(0)
        for event in events:
            kind = event.get("event")
            run_id = str(event.get("run_id", ""))
            if kind == "run_started":
                try:
                    started[run_id] = Decimal(str(event.get("reserved_cny", "0")))
                except InvalidOperation:
                    started[run_id] = Decimal(0)
            elif kind == "run_settled":
                settled_ids.add(run_id)
                try:
                    settled += Decimal(str(event.get("cost_settled_cny", "0")))
                except InvalidOperation:
                    pass
                if event.get("cost_unknown"):
                    try:
                        unknown += Decimal(str(event.get("reserved_cny", "0")))
                    except InvalidOperation:
                        pass
            elif kind == "run_aborted":
                aborted.add(run_id)
            elif kind == "unknown_spend_adjustment":
                try:
                    unknown += Decimal(str(event.get("reserved_cny", "0")))
                except InvalidOperation:
                    pass
        pending = sum(
            (
                value
                for key, value in started.items()
                if key not in settled_ids and key not in aborted
            ),
            Decimal(0),
        )
        return settled, pending, unknown

    def _ledger_start(self, run_id: str, config: RunConfig) -> None:
        self.store.append_global_ledger(
            {
                "event": "run_started",
                "run_id": run_id,
                "map_id": config.map_id,
                "provider_id": config.provider_id,
                "model": config.model,
                "reserved_cny": str(config.max_cost_cny),
                "cost_enforced": "mimo" in config.model.lower(),
            }
        )

    def _ledger_finish(self, run_id: str, result: dict[str, Any], state: RunState) -> None:
        raw_usage = result.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        self.store.append_global_ledger(
            {
                "event": "run_settled",
                "run_id": run_id,
                "state": state.value,
                "cost_settled_cny": str(usage.get("cost_settled_cny", "0")),
                "cost_unknown": bool(usage.get("cost_unknown")),
                "reserved_cny": str(usage.get("max_cost_cny", "0")),
                "requests": usage.get("requests", 0),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
        )

    def _ledger_abort(self, run_id: str) -> None:
        self.store.append_global_ledger({"event": "run_aborted", "run_id": run_id})


__all__ = [
    "ConcurrentLiveRunError",
    "InvalidTransitionError",
    "RunService",
    "RunServiceError",
    "TOTAL_BUDGET_ENV",
]
