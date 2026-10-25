"""父实验：矩阵生成、预检、串行队列、父子状态、实验级预算与幂等。

设计要点：

- **父 Experiment + 子 Run**：子局仍走 V11 ``RunService``（排队、单 worker、取消、
  恢复、幂等、跨进程锁），父实验只负责矩阵、顺序、预算汇总与汇总产物；
- 预检**零请求**：只做配置与版本检查、调用数上界与费用上界估算；
- 真实付费必须显式批准（``LiveApproval``），未批准时 ``submit`` 直接拒绝；
- 断点续跑以子局为单位：已执行/已中断/未知消费的子局不自动重跑。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_arena.lab.clock import compact_utc_now, utc_now
from agent_arena.lab.compare import (
    CATEGORY_PENDING,
    build_comparison,
    run_record,
)
from agent_arena.lab.contracts import (
    EXPERIMENT_TERMINAL_STATES,
    MAX_EXPERIMENT_RUNS,
    ExperimentManifest,
    ExperimentMode,
    ExperimentSpec,
    ExperimentState,
    MatrixCell,
)
from agent_arena.lab.paths import EXPERIMENT_ID_PATTERN, LAB_RUNS
from agent_arena.lab.registry import all_agents, get_agent
from agent_arena.web.budget import price_for_model
from agent_arena.web.safety import sanitize_text
from agent_arena.web.schemas import (
    TERMINAL_STATES,
    RunConfig,
    RunMode,
    RunState,
)

EXPERIMENT_JSON = "experiment.json"
MANIFEST_JSON = "manifest.json"
EVENTS_JSONL = "events.jsonl"
SUMMARY_JSON = "summary.json"
COMPARISON_JSON = "comparison.json"
CHILDREN_JSON = "children.json"
REPORT_MD = "report.md"
EXPORTS_DIR = "exports"

TERMINAL_CHILD_STATES = {state.value for state in TERMINAL_STATES}


class ExperimentError(RuntimeError):
    """父实验可预期的拒绝。"""


class ExperimentNotFound(ExperimentError):
    pass


class LiveApprovalRequired(ExperimentError):
    """未获批准的付费实验。"""


class ExperimentBusy(ExperimentError):
    """已有实验在运行。"""


# --------------------------------------------------------------------- preflight
@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    cells: int
    seeds: tuple[int, ...]
    runs_by_map: dict[str, int]
    max_requests: int
    max_cost_cny: str
    cost_enforced: bool
    provider_ready: bool
    approval_required: bool
    approved: bool
    mode: str
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "cells": self.cells,
            "seeds": list(self.seeds),
            "runs_by_map": dict(self.runs_by_map),
            "max_requests": self.max_requests,
            "max_cost_cny": self.max_cost_cny,
            "cost_enforced": self.cost_enforced,
            "provider_ready": self.provider_ready,
            "approval_required": self.approval_required,
            "approved": self.approved,
            "mode": self.mode,
            "notes": list(self.notes),
        }


def _provider_ready(spec: ExperimentSpec) -> tuple[bool, list[str], list[str]]:
    """零网络检查 Provider 配置是否齐全。"""

    blockers: list[str] = []
    warnings: list[str] = []
    if spec.mode is ExperimentMode.SIMULATED:
        warnings.append("模拟执行：不联网、不产生费用，成绩不得当作模型能力。")
        return True, blockers, warnings
    from agent_arena.web.providers import provider_statuses

    statuses = {item.provider_id: item for item in provider_statuses()}
    status = statuses.get(spec.provider_id)
    if status is None:
        blockers.append(f"未知 Provider：{spec.provider_id}")
        return False, blockers, warnings
    if spec.provider_id == "openai_compatible" and not status.configured:
        blockers.append("未配置 OPENAI_API_KEY / OPENAI_BASE_URL（本机 .env）。")
    return not blockers, blockers, warnings


def preflight(spec: ExperimentSpec) -> PreflightResult:
    """预检：零请求，只报告矩阵规模、预算上界与阻塞项。"""

    cells = spec.matrix()
    seeds = spec.resolved_seeds()
    ready, blockers, warnings = _provider_ready(spec)
    price = price_for_model(spec.model)
    max_requests = len(cells) * spec.budget.per_run_request_cap
    max_cost = Decimal(len(cells)) * spec.budget.per_run_cost_cap_cny
    if price is None:
        warnings.append(
            "该模型没有登记公开价目：费用只按单局上限估算，运行中不启用金额硬门禁。"
        )
    if max_requests > spec.budget.experiment_request_cap:
        blockers.append(
            f"请求上界 {max_requests} 超过实验请求上限 {spec.budget.experiment_request_cap}。"
        )
    if max_cost > spec.budget.experiment_cost_cap_cny:
        warnings.append(
            f"费用上界 CNY {max_cost} 超过实验费用上限 "
            f"{spec.budget.experiment_cost_cap_cny}；实际会在上限处停止。"
        )
    if len(cells) > MAX_EXPERIMENT_RUNS:
        blockers.append(f"子局数 {len(cells)} 超过硬上限 {MAX_EXPERIMENT_RUNS}。")
    for cell in cells:
        try:
            get_agent(cell.agent_id)
        except KeyError:
            blockers.append(f"未注册的策略：{cell.agent_id}")
    approval_required = spec.mode is ExperimentMode.LIVE
    approved = bool(spec.approval.approved)
    if approval_required and not approved:
        blockers.append("真实付费实验需要显式预算批准（LiveApproval.approved=false）。")
    if spec.preflight_only and approval_required:
        warnings.append("preflight_only=true：即使批准也只做预检，不提交真实请求。")
    runs_by_map: dict[str, int] = {}
    for cell in cells:
        runs_by_map[cell.map_id] = runs_by_map.get(cell.map_id, 0) + 1
    notes = [
        f"矩阵 {len(cells)} 局 = {len(spec.maps)} 图 × {len(seeds)} seed × "
        f"{len(spec.agent_arms)} 实验臂。",
        f"seed 取值 {list(seeds)}"
        f"（{'显式指定' if spec.environment_seeds else '自动取共同可用前 3 个'}）。",
        "执行方式：单 worker 串行，避免并发付费请求。",
    ]
    return PreflightResult(
        ok=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        cells=len(cells),
        seeds=seeds,
        runs_by_map=runs_by_map,
        max_requests=max_requests,
        max_cost_cny=str(max_cost),
        cost_enforced=price is not None,
        provider_ready=ready,
        approval_required=approval_required,
        approved=approved,
        mode=spec.mode.value,
        notes=tuple(notes),
    )


# ------------------------------------------------------------------------ store
class ExperimentStore:
    """``runs/lab/<experiment_id>/`` 的唯一读写入口。"""

    def __init__(self, base: Path) -> None:
        self.base = base.resolve()

    def ensure(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)

    def experiment_dir(self, experiment_id: str, *, create: bool = False) -> Path:
        import re

        if not re.fullmatch(EXPERIMENT_ID_PATTERN, experiment_id):
            raise ExperimentNotFound(f"非法的 experiment_id：{experiment_id}")
        path = (self.base / experiment_id).resolve()
        if path.parent != self.base:
            raise ExperimentNotFound("实验目录越界。")
        if create:
            path.mkdir(parents=True, exist_ok=True)
        elif not path.is_dir():
            raise ExperimentNotFound(f"找不到实验：{experiment_id}")
        return path

    def list_ids(self) -> list[str]:
        import re

        if not self.base.is_dir():
            return []
        return sorted(
            path.name
            for path in self.base.iterdir()
            if path.is_dir() and re.fullmatch(EXPERIMENT_ID_PATTERN, path.name)
        )

    def _json(self, experiment_id: str, name: str) -> dict[str, Any] | None:
        """读 JSON；Windows 上原子替换瞬间可能短暂不可读，做有限重试。"""

        import json
        import time

        path = self.experiment_dir(experiment_id) / name
        text: str | None = None
        for attempt in range(20):
            if not path.is_file():
                if attempt < 19:
                    time.sleep(0.01 * (attempt + 1))
                    continue
                return None
            try:
                text = path.read_text(encoding="utf-8")
                break
            except PermissionError:
                time.sleep(0.01 * (attempt + 1))
            except (OSError, UnicodeError):
                return None
        if text is None:
            return None
        try:
            payload = json.loads(text)
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def write_json(self, experiment_id: str, name: str, payload: dict[str, Any]) -> None:
        from agent_arena.web.store import atomic_write_json

        atomic_write_json(self.experiment_dir(experiment_id, create=True) / name, payload)

    def load_spec(self, experiment_id: str) -> dict[str, Any]:
        payload = self._json(experiment_id, EXPERIMENT_JSON)
        if payload is None:
            raise ExperimentNotFound(f"实验缺少 {EXPERIMENT_JSON}：{experiment_id}")
        return payload

    def load_manifest(self, experiment_id: str) -> ExperimentManifest:
        payload = self._json(experiment_id, MANIFEST_JSON)
        if payload is None:
            raise ExperimentNotFound(f"实验缺少 {MANIFEST_JSON}：{experiment_id}")
        return ExperimentManifest.model_validate(payload)

    def save_manifest(self, manifest: ExperimentManifest) -> None:
        manifest.updated_at = utc_now()
        self.write_json(manifest.experiment_id, MANIFEST_JSON, manifest.as_dict())

    def append_event(self, experiment_id: str, payload: dict[str, Any]) -> None:
        from agent_arena.web.store import append_jsonl

        row = {"at": utc_now(), **payload}
        append_jsonl(self.experiment_dir(experiment_id, create=True) / EVENTS_JSONL, row)

    def read_events(self, experiment_id: str) -> list[dict[str, Any]]:
        import json

        path = self.experiment_dir(experiment_id) / EVENTS_JSONL
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows


# ---------------------------------------------------------------------- service
class ExperimentService:
    """父实验服务；子局通过注入的 ``RunService`` 执行。"""

    def __init__(
        self,
        lab_base: Path,
        *,
        run_service: Any,
        recover: bool = True,
    ) -> None:
        self.store = ExperimentStore(lab_base)
        self.store.ensure()
        self.run_service = run_service
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._stop_flags: dict[str, threading.Event] = {}
        self._records: dict[str, dict[str, Any]] = {}
        self._active: str | None = None
        self.recovery = self._recover() if recover else {"interrupted": []}

    # ------------------------------------------------------------------ recovery
    def _recover(self) -> dict[str, list[str]]:
        interrupted: list[str] = []
        for experiment_id in self.store.list_ids():
            try:
                manifest = self.store.load_manifest(experiment_id)
            except ExperimentError:
                continue
            if manifest.state in EXPERIMENT_TERMINAL_STATES:
                continue
            manifest.state = ExperimentState.PARTIAL
            manifest.message = (
                "进程在实验进行中退出；已完成的子局保留，未开始的子局需显式续跑。"
            )
            manifest.finished_at = utc_now()
            self._reconcile_children(manifest)
            self.store.save_manifest(manifest)
            self.store.append_event(
                experiment_id, {"event": "experiment_interrupted", "reason": "process_restart"}
            )
            interrupted.append(experiment_id)
        return {"interrupted": interrupted}

    def _reconcile_children(self, manifest: ExperimentManifest) -> list[str]:
        """用**真实 run 状态**刷新父实验的子局链接，返回被修正的 matrix_index。

        背景：父实验的 `children` 是写入时的快照。如果进程在子局执行中途退出，
        子局可能已经被 `RunService` 收尾（例如被取消/中断），但父实验来不及回写，
        链接会停在 `QUEUED`。此时以磁盘上的 run manifest 为准，避免把"已结束"
        误当成"还在跑"。
        """

        fixed: list[str] = []
        for child in manifest.children:
            run_id = str(child.get("run_id") or "")
            if not run_id:
                continue
            try:
                status = self.run_service.get_run(run_id)
            except Exception:  # noqa: BLE001 - 子局被删时保留原样
                continue
            actual = status.state.value
            if str(child.get("state")) == actual:
                continue
            child["state"] = actual
            child["outcome"] = status.outcome
            child["success"] = actual == RunState.SUCCEEDED.value
            budget = status.budget if isinstance(status.budget, dict) else {}
            requests = budget.get("requests")
            if isinstance(requests, int):
                child["requests"] = max(int(child.get("requests") or 0), requests)
            cost = budget.get("cost_settled_cny")
            if cost is not None and child.get("cost_settled_cny") is None:
                child["cost_settled_cny"] = str(cost)
            if budget.get("cost_unknown"):
                child["cost_unknown"] = True
            fixed.append(str(child.get("matrix_index")))
        if fixed:
            manifest.counts = self._counts(manifest)
            self._refresh_budget(manifest)
            self.store.append_event(
                manifest.experiment_id,
                {"event": "children_reconciled", "matrix_indexes": fixed},
            )
        return fixed

    # -------------------------------------------------------------------- create
    def create_experiment(
        self,
        spec: ExperimentSpec,
        *,
        idempotency_key: str | None = None,
    ) -> str:
        with self._lock:
            if idempotency_key:
                existing = self._find_by_idempotency(idempotency_key)
                if existing:
                    return existing
            versions: dict[tuple[str, str], str] = {}
            for registration in all_agents():
                for arm in spec.agent_arms:
                    if arm.agent_id == registration.agent_id:
                        versions[(arm.agent_id, arm.config_hash)] = registration.identity.version
            matrix = spec.with_agent_versions(versions)
            experiment_id = spec.experiment_id or self._new_id()
            if spec.experiment_id:
                try:
                    self.store.experiment_dir(experiment_id)
                except ExperimentNotFound:
                    pass
                else:
                    raise ExperimentError(f"实验已存在：{experiment_id}")
            spec_payload = {
                **spec.public_dict(),
                "experiment_id": experiment_id,
                "matrix": [cell.as_dict() for cell in matrix],
                "matrix_size": len(matrix),
                "agent_versions": {
                    f"{agent_id}:{config_hash}": version
                    for (agent_id, config_hash), version in versions.items()
                },
            }
            self.store.write_json(experiment_id, EXPERIMENT_JSON, spec_payload)
            manifest = ExperimentManifest(
                experiment_id=experiment_id,
                name=spec.name,
                state=ExperimentState.CREATED,
                mode=spec.mode.value,
                spec={
                    "maps": list(spec.maps),
                    "seeds": list(spec.resolved_seeds()),
                    "arms": [arm.as_dict() for arm in spec.agent_arms],
                    "provider_id": spec.provider_id,
                    "model": spec.model,
                    "preflight_only": spec.preflight_only,
                },
                matrix=[cell.as_dict() for cell in matrix],
                children=[],
                counts={"total": len(matrix), "pending": len(matrix)},
                budget={
                    "experiment_request_cap": spec.budget.experiment_request_cap,
                    "experiment_cost_cap_cny": str(spec.budget.experiment_cost_cap_cny),
                    "per_run_request_cap": spec.budget.per_run_request_cap,
                    "per_run_cost_cap_cny": str(spec.budget.per_run_cost_cap_cny),
                    "requests_used": 0,
                    "cost_settled_cny": "0",
                    "cost_unknown": False,
                },
                approval=spec.approval.as_dict(),
                fingerprint=spec.fingerprint(),
                idempotency_key=idempotency_key,
            )
            self.store.save_manifest(manifest)
            self.store.append_event(
                experiment_id,
                {
                    "event": "experiment_created",
                    "mode": spec.mode.value,
                    "cells": len(matrix),
                    "fingerprint": spec.fingerprint(),
                    "preflight_only": spec.preflight_only,
                },
            )
            return experiment_id

    def _find_by_idempotency(self, key: str) -> str | None:
        for experiment_id in self.store.list_ids():
            try:
                manifest = self.store.load_manifest(experiment_id)
            except ExperimentError:
                continue
            if manifest.idempotency_key == key:
                return experiment_id
        return None

    def _new_id(self) -> str:
        for _ in range(20):
            candidate = f"lab-{compact_utc_now()}-{uuid4().hex[:8]}"
            if not (self.store.base / candidate).exists():
                return candidate
        raise ExperimentError("无法生成唯一 experiment_id。")

    # -------------------------------------------------------------------- submit
    def submit(self, experiment_id: str, *, resume: bool = False) -> ExperimentManifest:
        with self._lock:
            manifest = self.store.load_manifest(experiment_id)
            spec = self._spec(experiment_id)
            if manifest.state in EXPERIMENT_TERMINAL_STATES and not resume:
                return manifest
            if spec.preflight_only and spec.mode is ExperimentMode.LIVE:
                raise ExperimentError(
                    "该实验标记 preflight_only=true：只允许预检，不提交真实请求。"
                )
            if spec.mode is ExperimentMode.LIVE and not spec.approval.approved:
                raise LiveApprovalRequired(
                    "真实付费实验未获批准；请先记录 LiveApproval 再提交。"
                )
            thread = self._threads.get(experiment_id)
            if thread is not None and thread.is_alive():
                return manifest
            if self._active is not None and self._active != experiment_id:
                raise ExperimentBusy(f"已有实验在运行：{self._active}")
            if resume:
                self.store.append_event(experiment_id, {"event": "experiment_resumed"})
            manifest.state = ExperimentState.QUEUED
            manifest.message = None
            manifest.finished_at = None
            self.store.save_manifest(manifest)
            self.store.append_event(experiment_id, {"event": "experiment_queued"})
            self._stop_flags[experiment_id] = threading.Event()
            thread = threading.Thread(
                target=self._run,
                args=(experiment_id,),
                name=f"agent-arena-lab-{experiment_id[-8:]}",
                daemon=True,
            )
            self._threads[experiment_id] = thread
            self._active = experiment_id
            thread.start()
            return manifest

    def wait(self, experiment_id: str, *, timeout: float = 600.0) -> ExperimentManifest:
        deadline = time.monotonic() + timeout
        while True:
            manifest = self.store.load_manifest(experiment_id)
            thread = self._threads.get(experiment_id)
            running = thread is not None and thread.is_alive()
            if manifest.terminal and not running:
                return manifest
            if time.monotonic() >= deadline:
                return manifest
            time.sleep(0.05)

    def stop(self, experiment_id: str) -> ExperimentManifest:
        with self._lock:
            manifest = self.store.load_manifest(experiment_id)
            if manifest.terminal:
                return manifest
            flag = self._stop_flags.setdefault(experiment_id, threading.Event())
            flag.set()
            active = self._active_child(experiment_id)
            if active:
                self.run_service.cancel_run(active)
            thread = self._threads.get(experiment_id)
            if thread is None or not thread.is_alive():
                # 没有正在执行的线程（未提交或已结束）：直接落到明确终态。
                self.store.append_event(
                    experiment_id, {"event": "experiment_stopping", "reason": "no_active_thread"}
                )
                self._finalize(
                    experiment_id,
                    stop_reason="cancelled_by_user",
                    spec=self._spec(experiment_id),
                )
                return self.store.load_manifest(experiment_id)
            manifest.state = ExperimentState.STOPPING
            manifest.message = "停止请求已收到；未开始的子局不再执行。"
            self.store.save_manifest(manifest)
            self.store.append_event(experiment_id, {"event": "experiment_stopping"})
            return manifest

    # ------------------------------------------------------------------- execute
    def _run(self, experiment_id: str) -> None:
        flag = self._stop_flags.get(experiment_id) or threading.Event()
        manifest = self.store.load_manifest(experiment_id)
        spec = self._spec(experiment_id)
        matrix = [MatrixCell.from_dict(item) for item in manifest.matrix]
        manifest.state = ExperimentState.RUNNING
        manifest.started_at = manifest.started_at or utc_now()
        self.store.save_manifest(manifest)
        self.store.append_event(experiment_id, {"event": "experiment_running"})
        started = time.monotonic()
        stop_reason = ""

        try:
            for cell in matrix:
                if flag.is_set():
                    stop_reason = "cancelled_by_user"
                    break
                existing = self._child_for(manifest, cell.matrix_index)
                if existing and str(existing.get("state")) in TERMINAL_CHILD_STATES:
                    continue
                blocked = self._budget_block(spec, manifest, cell)
                if blocked:
                    stop_reason = blocked
                    break
                if (
                    time.monotonic() - started
                    > spec.budget.wall_clock_cap_seconds
                ):
                    stop_reason = "wall_clock_cap"
                    break
                self._run_child(experiment_id, manifest, spec, cell, flag)
                if flag.is_set():
                    stop_reason = "cancelled_by_user"
                    break
        except Exception as exc:  # noqa: BLE001 - 父实验必须落到明确终态
            stop_reason = f"internal_error:{type(exc).__name__}"
            self.store.append_event(
                experiment_id,
                {"event": "experiment_error", "reason": sanitize_text(exc, limit=200)},
            )
        finally:
            self._finalize(experiment_id, stop_reason=stop_reason, spec=spec)
            with self._lock:
                if self._active == experiment_id:
                    self._active = None

    def _run_child(
        self,
        experiment_id: str,
        manifest: ExperimentManifest,
        spec: ExperimentSpec,
        cell: MatrixCell,
        flag: threading.Event,
    ) -> None:
        config = self._run_config(experiment_id, spec, cell)
        key = f"{experiment_id}:{cell.matrix_index}"
        run_id = self.run_service.create_run(config, idempotency_key=key)
        self._link_child(manifest, cell, run_id, state=RunState.QUEUED.value)
        self.store.save_manifest(manifest)
        self.store.append_event(
            experiment_id,
            {
                "event": "child_started",
                "matrix_index": cell.matrix_index,
                "run_id": run_id,
                "map_id": cell.map_id,
                "environment_seed": cell.environment_seed,
                "agent_id": cell.agent_id,
            },
        )
        deadline = time.monotonic() + spec.budget.wall_clock_cap_seconds
        while True:
            status = self.run_service.get_run(run_id)
            if status.terminal:
                break
            if flag.is_set():
                self.run_service.cancel_run(run_id)
            if time.monotonic() > deadline:
                self.run_service.cancel_run(run_id)
                break
            time.sleep(0.05)
        replay = self.run_service.load_replay(run_id)
        result = replay.get("result") or {}
        record = run_record(
            run_id=run_id,
            matrix_index=cell.matrix_index,
            manifest=replay.get("manifest") or {},
            result=result,
        )
        self._records[run_id] = record
        self._link_child(
            manifest,
            cell,
            run_id,
            state=record["state"],
            outcome=record["outcome"],
            success=record["success"],
            requests=record["requests"],
            cost_settled_cny=(
                None if record["cost_cny"] is None else str(record["cost_cny"])
            ),
            cost_unknown=not record["cost_known"],
        )
        self._refresh_budget(manifest)
        self.store.save_manifest(manifest)
        self.store.append_event(
            experiment_id,
            {
                "event": "child_finished",
                "matrix_index": cell.matrix_index,
                "run_id": run_id,
                "state": record["state"],
                "category": record["category"],
                "requests": record["requests"],
                "cost_cny": record["cost_cny"],
                "cost_known": record["cost_known"],
            },
        )

    def _budget_block(
        self, spec: ExperimentSpec, manifest: ExperimentManifest, cell: MatrixCell
    ) -> str:
        requests_used = int(manifest.budget.get("requests_used") or 0)
        settled = Decimal(str(manifest.budget.get("cost_settled_cny") or "0"))
        if manifest.budget.get("cost_unknown"):
            return "unknown_spend_closed"
        if requests_used >= spec.budget.experiment_request_cap:
            return "experiment_request_cap"
        if settled + spec.budget.per_run_cost_cap_cny > spec.budget.experiment_cost_cap_cny:
            return "experiment_cost_cap"
        del cell
        return ""

    def _refresh_budget(self, manifest: ExperimentManifest) -> None:
        requests = 0
        settled = Decimal(0)
        unknown = False
        for child in manifest.children:
            requests += int(child.get("requests") or 0)
            value = child.get("cost_settled_cny")
            if value is not None:
                try:
                    settled += Decimal(str(value))
                except Exception:  # noqa: BLE001 - 脏数据不参与求和
                    pass
            unknown = unknown or bool(child.get("cost_unknown"))
        manifest.budget = {
            **manifest.budget,
            "requests_used": requests,
            "cost_settled_cny": str(settled),
            "cost_unknown": unknown,
        }

    def _link_child(
        self,
        manifest: ExperimentManifest,
        cell: MatrixCell,
        run_id: str,
        *,
        state: str,
        outcome: str | None = None,
        success: bool = False,
        requests: int = 0,
        cost_settled_cny: str | None = None,
        cost_unknown: bool = False,
    ) -> None:
        entry = {
            "matrix_index": cell.matrix_index,
            "run_id": run_id,
            "map_id": cell.map_id,
            "environment_seed": cell.environment_seed,
            "agent_id": cell.agent_id,
            "state": state,
            "outcome": outcome,
            "success": success,
            "requests": requests,
            "cost_settled_cny": cost_settled_cny,
            "cost_unknown": cost_unknown,
        }
        children = [
            item
            for item in manifest.children
            if int(item.get("matrix_index", -1)) != cell.matrix_index
        ]
        children.append(entry)
        children.sort(key=lambda item: int(item.get("matrix_index", 0)))
        manifest.children = children
        manifest.counts = self._counts(manifest)

    def _counts(self, manifest: ExperimentManifest) -> dict[str, int]:
        total = len(manifest.matrix)
        done = sum(
            1
            for item in manifest.children
            if str(item.get("state")) in TERMINAL_CHILD_STATES
        )
        succeeded = sum(1 for item in manifest.children if item.get("success"))
        return {
            "total": total,
            "done": done,
            "pending": max(0, total - done),
            "succeeded": succeeded,
            "failed": sum(
                1
                for item in manifest.children
                if str(item.get("state")) == RunState.FAILED.value
            ),
            "budget_reached": sum(
                1
                for item in manifest.children
                if str(item.get("state")) == RunState.BUDGET_REACHED.value
            ),
            "cancelled": sum(
                1
                for item in manifest.children
                if str(item.get("state")) == RunState.CANCELLED.value
            ),
            "provider_error": sum(
                1
                for item in manifest.children
                if str(item.get("state")) == RunState.PROVIDER_ERROR.value
            ),
            "interrupted": sum(
                1
                for item in manifest.children
                if str(item.get("state")) == RunState.INTERRUPTED.value
            ),
        }

    def _finalize(
        self, experiment_id: str, *, stop_reason: str, spec: ExperimentSpec
    ) -> None:
        manifest = self.store.load_manifest(experiment_id)
        manifest.counts = self._counts(manifest)
        self._refresh_budget(manifest)
        done = manifest.counts.get("done", 0)
        total = manifest.counts.get("total", 0)
        if stop_reason == "cancelled_by_user":
            state = ExperimentState.CANCELLED if done == 0 else ExperimentState.PARTIAL
        elif stop_reason:
            state = ExperimentState.PARTIAL if done else ExperimentState.FAILED
        elif done >= total:
            state = ExperimentState.COMPLETED
        else:
            state = ExperimentState.PARTIAL
        manifest.state = state
        manifest.finished_at = utc_now()
        if stop_reason:
            manifest.message = f"实验提前结束：{stop_reason}"
        elif done < total:
            manifest.message = "仍有未执行的子局。"
        self.store.save_manifest(manifest)
        self.store.append_event(
            experiment_id,
            {
                "event": "experiment_finished",
                "state": state.value,
                "stop_reason": stop_reason or None,
                "done": done,
                "total": total,
                "budget": manifest.budget,
            },
        )
        self.store.write_json(
            experiment_id,
            CHILDREN_JSON,
            {"experiment_id": experiment_id, "children": manifest.children},
        )
        self.write_summary(experiment_id)
        del spec

    # ------------------------------------------------------------------- queries
    def _spec(self, experiment_id: str) -> ExperimentSpec:
        payload = self.store.load_spec(experiment_id)
        derived = {
            "seeds",
            "seed_source",
            "arms",
            "fingerprint",
            "matrix",
            "matrix_size",
            "agent_versions",
        }
        payload = {key: value for key, value in payload.items() if key not in derived}
        payload["experiment_id"] = experiment_id
        return ExperimentSpec.model_validate(payload)

    def _run_config(
        self, experiment_id: str, spec: ExperimentSpec, cell: MatrixCell
    ) -> RunConfig:
        from agent_arena.v10.baselines.suite import decision_budget

        mode = RunMode.SIMULATED if spec.mode is ExperimentMode.SIMULATED else RunMode.LIVE
        return RunConfig(
            map_id=cell.map_id,
            environment_seed=cell.environment_seed,
            mode=mode,
            provider_id=spec.provider_id,
            model=spec.model,
            agent=cell.agent_id,
            agent_config=dict(cell.agent_config),
            experiment_id=experiment_id,
            matrix_index=cell.matrix_index,
            max_decisions=spec.budget.per_run_decision_cap
            or decision_budget(cell.map_id),
            max_requests=spec.budget.per_run_request_cap,
            max_input_tokens=spec.budget.per_run_input_token_cap,
            max_output_tokens=spec.budget.per_run_output_token_cap,
            max_cost_cny=spec.budget.per_run_cost_cap_cny,
        )

    def _child_for(
        self, manifest: ExperimentManifest, matrix_index: int
    ) -> dict[str, Any] | None:
        for item in manifest.children:
            if int(item.get("matrix_index", -1)) == matrix_index:
                return item
        return None

    def _active_child(self, experiment_id: str) -> str | None:
        try:
            manifest = self.store.load_manifest(experiment_id)
        except ExperimentError:
            return None
        for item in manifest.children:
            if str(item.get("state")) in {"QUEUED", "RUNNING"}:
                return str(item.get("run_id") or "") or None
        return None

    def status(self, experiment_id: str) -> ExperimentManifest:
        return self.store.load_manifest(experiment_id)

    def records(self, experiment_id: str) -> list[dict[str, Any]]:
        manifest = self.store.load_manifest(experiment_id)
        if self._reconcile_children(manifest):
            self.store.save_manifest(manifest)
        records: list[dict[str, Any]] = []
        for child in manifest.children:
            run_id = str(child.get("run_id") or "")
            if not run_id:
                continue
            cached = self._records.get(run_id)
            if cached is not None:
                records.append(cached)
                continue
            try:
                replay = self.run_service.load_replay(run_id)
            except Exception:  # noqa: BLE001 - 子局被删/损坏时跳过并标注
                continue
            record = run_record(
                run_id=run_id,
                matrix_index=int(child.get("matrix_index") or 0),
                manifest=replay.get("manifest") or {},
                result=replay.get("result") or {},
            )
            self._records[run_id] = record
            records.append(record)
        records.sort(key=lambda item: int(item["matrix_index"] or 0))
        return records

    def summary(self, experiment_id: str) -> dict[str, Any]:
        manifest = self.store.load_manifest(experiment_id)
        spec = self._spec(experiment_id)
        records = self.records(experiment_id)
        counts: dict[str, int] = {}
        for record in records:
            counts[record["category"]] = counts.get(record["category"], 0) + 1
        total = len(manifest.matrix)
        executed = len(records)
        valid = sum(
            counts.get(item, 0)
            for item in ("completed_success", "mechanism_failure", "budget_censored")
        )
        return {
            "schema_version": "v12-lab-summary-1",
            "experiment_id": experiment_id,
            "name": manifest.name,
            "state": manifest.state.value,
            "mode": manifest.mode,
            "provider_id": spec.provider_id,
            "model": spec.model,
            "maps": list(spec.maps),
            "seeds": list(spec.resolved_seeds()),
            "arms": [arm.as_dict() for arm in spec.agent_arms],
            "total_cells": total,
            "executed": executed,
            "pending": max(0, total - executed),
            "categories": dict(sorted(counts.items())),
            "valid_denominator": valid,
            "successes": counts.get("completed_success", 0),
            "success_rate": (
                round(counts.get("completed_success", 0) / valid, 6) if valid else None
            ),
            "budget": dict(manifest.budget),
            "approval": dict(manifest.approval),
            "counts": dict(manifest.counts),
            "generated_at": utc_now(),
            "pending_category": CATEGORY_PENDING,
            "only_conditions": list(spec.only_conditions),
            "supplement_of": spec.supplement_of,
            "supplement_reason": spec.supplement_reason,
        }

    def comparison(self, experiment_id: str) -> dict[str, Any]:
        manifest = self.store.load_manifest(experiment_id)
        spec = self._spec(experiment_id)
        records = self.records(experiment_id)
        result = build_comparison(
            experiment_id=experiment_id,
            records=records,
            policy=spec.comparison,
        )
        payload = result.as_dict()
        payload["experiment_state"] = manifest.state.value
        payload["mode"] = spec.mode.value
        return payload

    def write_summary(self, experiment_id: str) -> dict[str, Any]:
        summary = self.summary(experiment_id)
        self.store.write_json(experiment_id, SUMMARY_JSON, summary)
        self.store.write_json(
            experiment_id, COMPARISON_JSON, self.comparison(experiment_id)
        )
        return summary

    # ------------------------------------------------------------------ analysis
    def _steps(self, run_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        replay = self.run_service.load_replay(run_id)
        steps = [
            event for event in replay.get("events") or [] if event.get("event") == "decision"
        ]
        return steps, replay.get("result") or {}

    def findings(self, experiment_id: str) -> list[Any]:
        """逐局确定性诊断；每条都指向具体 decision 事件。"""

        from agent_arena.lab.diagnostics import diagnose_run

        output: list[Any] = []
        for record in self.records(experiment_id):
            try:
                steps, result = self._steps(str(record["run_id"]))
            except Exception:  # noqa: BLE001 - 子局缺失时跳过
                continue
            output.extend(
                diagnose_run(
                    map_id=str(record["map_id"]),
                    run_id=str(record["run_id"]),
                    steps=steps,
                    result=result,
                )
            )
        return output

    def view_model(self, run_id: str) -> dict[str, Any]:
        """地图专属可视化 view-model（只读公开 trace）。"""

        from agent_arena.lab.visualization import build_view_model

        steps, result = self._steps(run_id)
        map_id = str(result.get("map_id") or "")
        return build_view_model(map_id, steps, result)

    def pairwise(
        self, experiment_id: str, left_run_id: str, right_run_id: str
    ) -> dict[str, Any]:
        """两条配对轨迹的事件序列对照 + 可验证假设。"""

        from agent_arena.lab.diagnostics import diff_hypotheses, pairwise_diff

        records = {str(item["run_id"]): item for item in self.records(experiment_id)}
        left = records.get(left_run_id)
        right = records.get(right_run_id)
        if left is None or right is None:
            raise ExperimentError("配对轨迹不属于该实验。")
        comparison = self.comparison(experiment_id)
        verdict = "COMPARABLE"
        reasons: tuple[str, ...] = ()
        for pair in comparison.get("pairs") or []:
            if {pair.get("left_run_id"), pair.get("right_run_id")} == {left_run_id, right_run_id}:
                verdict = str(pair.get("verdict") or "COMPARABLE")
                reasons = tuple(str(item) for item in pair.get("reasons") or [])
                break
        left_steps, left_result = self._steps(left_run_id)
        right_steps, right_result = self._steps(right_run_id)
        diff = pairwise_diff(
            pairing_key=f"{left['map_id']}|seed={left['environment_seed']}",
            left_run_id=left_run_id,
            right_run_id=right_run_id,
            left_agent=str(left["agent_id"]),
            right_agent=str(right["agent_id"]),
            left_steps=left_steps,
            right_steps=right_steps,
            left_result=left_result,
            right_result=right_result,
            verdict=verdict,
            reasons=reasons,
        )
        return {
            "diff": diff.as_dict(),
            "hypotheses": diff_hypotheses(diff),
            "verdict": verdict,
            "reasons": list(reasons),
        }

    def report(self, experiment_id: str) -> str:
        from agent_arena.lab.report import build_report

        experiment = self.store.load_spec(experiment_id)
        return build_report(
            experiment=experiment,
            summary=self.summary(experiment_id),
            comparison=self.comparison(experiment_id),
            records=self.records(experiment_id),
            findings=self.findings(experiment_id),
        )

    def export(self, experiment_id: str) -> dict[str, str]:
        """写出 runs.csv / metrics.csv / paired_comparison.csv / report.md 等。"""

        from agent_arena.lab.report import write_exports

        experiment = self.store.load_spec(experiment_id)
        written = write_exports(
            experiment_dir=self.store.experiment_dir(experiment_id),
            experiment=experiment,
            summary=self.summary(experiment_id),
            comparison=self.comparison(experiment_id),
            records=self.records(experiment_id),
            findings=self.findings(experiment_id),
        )
        self.store.append_event(
            experiment_id,
            {"event": "experiment_exported", "files": sorted(written)},
        )
        return {name: str(path) for name, path in written.items()}

    def diagnostics(self) -> dict[str, Any]:
        return {
            "base_dir": str(self.store.base),
            "experiments": len(self.store.list_ids()),
            "active": self._active,
        }

    # -------------------------------------------------------------- supplement
    def supplement_candidates(self, experiment_id: str) -> dict[str, Any]:
        """列出**需要补充**的子局：中断、Provider 错误、未知消费、取消、未执行。

        已完成 / 机制失败 / 预算截尾**不在**候选里：前两者是真实结果，补跑会污染
        分母；预算截尾若要重测应另立提高预算的新实验。

        先与真实 run 状态对账，避免父实验里陈旧链接（例如进程中断后残留的
        `QUEUED`）把"已结束"误当成"待补充"或反之。
        """

        manifest = self.store.load_manifest(experiment_id)
        if self._reconcile_children(manifest):
            self.store.save_manifest(manifest)
        spec = self._spec(experiment_id)
        cells = {cell.matrix_index: cell for cell in spec.matrix()}
        by_index = {
            int(item.get("matrix_index", -1)): item for item in manifest.children
        }
        rows: list[dict[str, Any]] = []
        for index, cell in sorted(cells.items()):
            child = by_index.get(index)
            if child is None:
                reason = "not_executed"
            elif bool(child.get("cost_unknown")):
                reason = "unknown_spend"
            elif str(child.get("state")) == RunState.INTERRUPTED.value:
                reason = "interrupted"
            elif str(child.get("state")) == RunState.PROVIDER_ERROR.value:
                reason = "provider_error"
            elif str(child.get("state")) == RunState.CANCELLED.value:
                # 进程中断/用户取消都没有终局判定，可以补跑（且必须是显式动作）。
                reason = "cancelled"
            elif str(child.get("state")) not in TERMINAL_CHILD_STATES:
                reason = "unfinished"
            else:
                continue
            rows.append(
                {
                    "matrix_index": index,
                    "condition_key": cell.condition_key,
                    "map_id": cell.map_id,
                    "environment_seed": cell.environment_seed,
                    "agent_id": cell.agent_id,
                    "reason": reason,
                    "source_run_id": (child or {}).get("run_id"),
                    "source_state": (child or {}).get("state"),
                }
            )
        return {
            "source_experiment_id": experiment_id,
            "source_state": manifest.state.value,
            "candidates": rows,
            "count": len(rows),
            "excluded_note": (
                "已完成、机制失败、预算截尾均不补跑：它们是真实结果，补跑会污染分母。"
                "预算截尾若需重测，应另立提高单局预算的新实验。"
            ),
        }

    def create_version_rerun(
        self,
        source_experiment_id: str,
        *,
        conditions: list[str],
        reason: str,
        name: str | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """在**新版本**（例如修了公开契约/提示）下重跑指定条件。

        与 `create_supplement` 的区别：

        - 补充实验只跑"失败/未执行"的子局，目的是补齐分母；
        - 版本复跑**允许重跑已完成的子局**，目的是在新版本下重新测量，
          因此它一定是独立实验，且**不与旧版本配对**。

        原始实验一律不动；新实验通过 `supplement_of` / `supplement_reason` 记录来源，
        报告会显式声明"跨版本不配对"。
        """

        source_spec = self._spec(source_experiment_id)
        available = {cell.condition_key for cell in source_spec.matrix()}
        wanted = list(dict.fromkeys(conditions))
        unknown = [item for item in wanted if item not in available]
        if unknown:
            raise ExperimentError(
                "这些条件不属于源实验：" + "、".join(unknown[:5])
            )
        if not wanted:
            raise ExperimentError("版本复跑必须显式给出至少一个条件。")
        new_name = name or f"{source_spec.name} · rerun-v2"
        note = reason or "版本复跑：在新契约/提示版本下重新测量同一批条件。"
        spec = source_spec.model_copy(
            update={
                "experiment_id": "",
                "name": new_name,
                "notes": f"{source_spec.notes}\n{note}".strip(),
                "only_conditions": wanted,
                "supplement_of": source_experiment_id,
                "supplement_reason": note,
                "created_at": utc_now(),
            }
        )
        result = preflight(spec)
        if not result.ok:
            raise ExperimentError("版本复跑预检未通过：" + "；".join(result.blockers))
        key = (
            idempotency_key
            or f"rerun:{source_experiment_id}:{spec.fingerprint()[:12]}"
        )
        return self.create_experiment(spec, idempotency_key=key)

    def create_supplement(
        self,
        source_experiment_id: str,
        *,
        name: str | None = None,
        reason: str = "",
        conditions: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """新建一个**独立**的补充实验，只跑需要补充的子局。

        原始实验、账本与 run 记录一律不动；新实验的 ``supplement_of`` 指向来源，
        报告与汇总都会显示这一关系。补跑产生新的 ``run_id``。
        """

        plan = self.supplement_candidates(source_experiment_id)
        candidates = plan["candidates"]
        if not candidates:
            raise ExperimentError(
                "该实验没有需要补充的子局（无中断/Provider 错误/未知消费/未执行）。"
            )
        if conditions is not None:
            wanted = set(conditions)
            candidates = [item for item in candidates if item["condition_key"] in wanted]
            if not candidates:
                raise ExperimentError("指定的条件都不在补充候选里。")
        source_spec = self._spec(source_experiment_id)
        new_name = name or f"{source_spec.name} · supplement"
        note = reason or (
            "补充实验：只重跑原始实验里中断 / Provider 错误 / 未知消费 / 未执行的子局；"
            f"来源 {source_experiment_id}。"
        )
        spec = source_spec.model_copy(
            update={
                "experiment_id": "",
                "name": new_name,
                "notes": f"{source_spec.notes}\n{note}".strip(),
                "only_conditions": [item["condition_key"] for item in candidates],
                "supplement_of": source_experiment_id,
                "supplement_reason": note,
                "preflight_only": source_spec.preflight_only,
                "created_at": utc_now(),
            }
        )
        # 补充实验必须重新走预检：矩阵变小但仍需预算与版本检查。
        result = preflight(spec)
        if not result.ok:
            raise ExperimentError("补充实验预检未通过：" + "；".join(result.blockers))
        key = idempotency_key or f"supplement:{source_experiment_id}:{spec.fingerprint()[:12]}"
        return self.create_experiment(spec, idempotency_key=key)


def default_experiment_service(
    *, lab_base: Path | None = None, web_base: Path | None = None
) -> ExperimentService:
    """构造默认服务：``runs/lab`` + 复用 ``runs/web`` 的 RunService。"""

    from agent_arena.lab.paths import WEB_RUNS
    from agent_arena.web.service import RunService

    run_service = RunService(web_base or WEB_RUNS)
    return ExperimentService(lab_base or LAB_RUNS, run_service=run_service)


__all__ = [
    "CHILDREN_JSON",
    "COMPARISON_JSON",
    "EVENTS_JSONL",
    "EXPERIMENT_JSON",
    "EXPORTS_DIR",
    "MANIFEST_JSON",
    "REPORT_MD",
    "SUMMARY_JSON",
    "ExperimentBusy",
    "ExperimentError",
    "ExperimentNotFound",
    "ExperimentService",
    "ExperimentStore",
    "LiveApprovalRequired",
    "PreflightResult",
    "default_experiment_service",
    "preflight",
]
