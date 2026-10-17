"""V7 Pilot-001: twelve paid episodes on the six runtime-backed maps.

The pilot is pre-registered in ``docs/v7/pilot-001-registration.md``. It reuses
the frozen V6 six-map runtime and the read-only V7 metric layer, but keeps its
own ``runs/v7`` ledger, registry, manifest and budget guard. It never touches
the closed V2/V5/V6 ledgers or the V6 pilot registry.

Usage:
    .venv\\Scripts\\python.exe scripts\\run_v7_pilot.py --preflight
    .venv\\Scripts\\python.exe scripts\\run_v7_pilot.py --execute-paid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.v6.budget import (  # noqa: E402
    MAX_DECISIONS_PER_EPISODE,
    MAX_REQUESTS_GLOBAL,
    PRICE_SHEETS,
    PilotBudgetClosed,
    V6BudgetLedger,
)
from agent_arena.v6.budget import MAX_EPISODES as V6_MAX_EPISODES  # noqa: E402
from agent_arena.v6.offline_gate import GATE_PATH, load_and_validate_gate  # noqa: E402
from agent_arena.v6.runner import V6EpisodeSpec, V6PilotRunner, registered_v6_matrix  # noqa: E402

V7_RUN_ROOT = ROOT / "runs" / "v7"
V7_EXPERIMENT_ROOT = V7_RUN_ROOT / "experiments"
V7_LEDGER_ROOT = V7_RUN_ROOT / "ledgers"
V7_REGISTRY_PATH = V7_RUN_ROOT / "pilot_registry.json"
REGISTRATION_PATH = ROOT / "docs" / "v7" / "pilot-001-registration.md"
EXPERIMENT_LABEL = "v7_pilot_001"
MAX_EPISODES = 12
OPERATIONAL_COST_CAP = Decimal("2.00")
STOP_BEFORE_NEXT_EPISODE = Decimal("1.80")
CURRENCY = "CNY"
MODEL_NAME = "mimo-v2.6-flash"
ALLOWED_ENDPOINT = ("https", "api.xiaomimimo.com", "/v1")

SELECTED: tuple[tuple[str, str, int], ...] = (
    ("map08_l1_two_candidate", "no_hypothesis_table", 0),
    ("map08_l3_original", "hypothesis_table", 0),
    ("map16_l1_single_train", "react", 0),
    ("map16_l3_original", "constraint_table", 0),
    ("map18_l2_alt_segment_r2b2", "alert_off", 0),
    ("map18_l3_original", "alert_on", 0),
    ("map22_l1_short_return", "history5", 0),
    ("map22_l3_original", "history5_graph_memory", 0),
    ("map26_l3_software_fault", "free_diagnosis", 0),
    ("map26_recovery_power", "recovery_full", 0),
    ("map30_l3_original", "history5_casebook", 0),
    ("map30_recall_original", "history5_casebook", 0),
)

INCOMPLETE_OUTCOMES = {
    "provider_error",
    "provider_error_limit",
    "unknown_provider_spend",
    "input_context_limit",
    "episode_timeout",
    "global_provider_timeout",
    "incomplete",
    "invalid_action_schema_limit",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".v7-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _read_registry() -> dict[str, Any] | None:
    if not V7_REGISTRY_PATH.is_file():
        return None
    try:
        payload = json.loads(V7_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("V7 pilot registry is malformed; no paid run is allowed.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "v7_pilot_registry_v1":
        raise RuntimeError("V7 pilot registry is invalid; no paid run is allowed.")
    return payload


def _claim_registry(payload: dict[str, Any]) -> None:
    V7_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with V7_REGISTRY_PATH.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError("A V7 pilot is already registered; refusing to create another.") from exc


def _update_registry(payload: dict[str, Any]) -> None:
    prior = _read_registry()
    identity = ("experiment_id", "run_dir", "ledger_path", "offline_gate_hash")
    if prior is None or any(prior.get(field) != payload.get(field) for field in identity):
        raise RuntimeError("V7 pilot registry identity changed; refusing further execution.")
    _atomic_write(V7_REGISTRY_PATH, payload)


def _settings_for_paid_run() -> RuntimeSettings:
    configured = RuntimeSettings.load(env_file=ROOT / ".env")
    if configured.provider != "openai" or configured.model_name != MODEL_NAME:
        raise ValueError("Local provider/model settings do not match the registered MiMo pilot.")
    settings = RuntimeSettings.load(
        {
            "provider": "openai",
            "world": "scenario_v4",
            "world_version": "V4",
            "agent": "react",
            "seed": 0,
            "runs_dir": V7_RUN_ROOT,
            "results_dir": ROOT / "results" / "v7",
            "step_limit": 100,
            "request_timeout_seconds": 30,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "reasoning_effort": "none",
            "response_format": "json_object",
            "model_name": MODEL_NAME,
        },
        env_file=ROOT / ".env",
    )
    if settings.provider != "openai" or settings.model_name != MODEL_NAME:
        raise ValueError("Local provider configuration does not match the registered MiMo model.")
    if not settings.openai_api_key:
        raise ValueError("The local MiMo API credential is not configured.")
    if not settings.base_url:
        raise ValueError("The local MiMo API endpoint is not configured.")
    endpoint = urlparse(settings.base_url)
    if (
        endpoint.scheme != ALLOWED_ENDPOINT[0]
        or endpoint.hostname != ALLOWED_ENDPOINT[1]
        or endpoint.path.rstrip("/") != ALLOWED_ENDPOINT[2]
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("The endpoint does not match the Xiaomi MiMo Responses API.")
    return settings


def _selected_specs() -> list[V6EpisodeSpec]:
    matrix = {item.episode_id: item for item in registered_v6_matrix()}
    specs: list[V6EpisodeSpec] = []
    for instance_id, condition_id, seed in SELECTED:
        spec = V6EpisodeSpec(instance_id, condition_id, seed)
        if spec.episode_id not in matrix:
            raise ValueError(f"Selected episode is not in the V6 matrix: {spec.episode_id}")
        specs.append(spec)
    if len(specs) != MAX_EPISODES or len({item.episode_id for item in specs}) != MAX_EPISODES:
        raise AssertionError("V7 pilot selection must contain exactly 12 unique episodes.")
    return specs


def _preflight_payload(gate: dict[str, Any]) -> dict[str, Any]:
    specs = _selected_specs()
    return {
        "experiment_label": EXPERIMENT_LABEL,
        "episodes": len(specs),
        "maps": sorted({spec.map_id for spec in specs}),
        "selected": [
            {
                "episode_id": spec.episode_id,
                "map_id": spec.map_id,
                "instance_id": spec.instance_id,
                "condition_id": spec.condition_id,
                "seed": spec.seed,
            }
            for spec in specs
        ],
        "gate_hash": gate["frozen_gate_hash"],
        "runtime_commit": gate["runtime_commit"],
        "runtime_tree_hash": gate["runtime_tree_hash"],
        "currency": CURRENCY,
        "operational_cost_cap": str(OPERATIONAL_COST_CAP),
        "ledger_hard_cap": str(PRICE_SHEETS[CURRENCY].max_cost),
        "max_episodes": MAX_EPISODES,
        "max_decisions_per_episode": MAX_DECISIONS_PER_EPISODE,
        "max_requests_global": MAX_REQUESTS_GLOBAL,
        "v6_ledger_episode_hard_cap": V6_MAX_EPISODES,
        "registration_sha256": sha256_file(REGISTRATION_PATH),
        "script_sha256": sha256_file(Path(__file__)),
        "paid_api_calls": 0,
    }


def _write_manifest(
    path: Path,
    *,
    ledger: V6BudgetLedger,
    run_dir: Path,
    gate: dict[str, Any],
    status: str,
    stage: str,
    started_at: str,
    completed: list[str],
    error: str | None = None,
) -> None:
    payload = {
        "schema_version": "v7_pilot_manifest_v1",
        "experiment_label": EXPERIMENT_LABEL,
        "experiment_id": ledger.experiment_id,
        "status": status,
        "stage": stage,
        "started_at": started_at,
        "updated_at": utc_now(),
        "finished_at": utc_now() if status in {"completed", "stopped", "aborted"} else None,
        "provider": "openai",
        "model": MODEL_NAME,
        "temperature": 0,
        "billing_currency": CURRENCY,
        "price_source": "https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash",
        "offline_gate_hash": gate["frozen_gate_hash"],
        "runtime_commit": gate["runtime_commit"],
        "runtime_tree_hash": gate["runtime_tree_hash"],
        "run_dir": str(run_dir.relative_to(ROOT)),
        "ledger_path": str(ledger.path.relative_to(ROOT)),
        "registered_episodes": [
            {
                "instance_id": spec.instance_id,
                "condition_id": spec.condition_id,
                "seed": spec.seed,
                "episode_id": spec.episode_id,
            }
            for spec in _selected_specs()
        ],
        "completed_episode_ids": completed,
        "operational_cost_cap": str(OPERATIONAL_COST_CAP),
        "ledger_hard_cap": str(PRICE_SHEETS[CURRENCY].max_cost),
        "ledger_snapshot": ledger.snapshot(),
        "error": error,
    }
    _atomic_write(path, payload)
    _update_registry(
        {
            "schema_version": "v7_pilot_registry_v1",
            "experiment_label": EXPERIMENT_LABEL,
            "experiment_id": ledger.experiment_id,
            "status": status,
            "stage": stage,
            "updated_at": payload["updated_at"],
            "run_dir": str(run_dir.relative_to(ROOT)),
            "ledger_path": str(ledger.path.relative_to(ROOT)),
            "offline_gate_hash": gate["frozen_gate_hash"],
            "runtime_commit": gate["runtime_commit"],
            "billing_currency": CURRENCY,
            "completed_episode_count": len(completed),
            "ledger_snapshot": ledger.snapshot(),
        }
    )


def _cost_guard(ledger: V6BudgetLedger) -> None:
    snapshot = ledger.snapshot()
    reserved = Decimal(str(snapshot["reserved_cost"]))
    actual = Decimal(str(snapshot["actual_cost_from_reported_usage"]))
    if reserved > OPERATIONAL_COST_CAP or actual > OPERATIONAL_COST_CAP:
        ledger.close(
            "V7_OPERATIONAL_COST_LIMIT",
            reserved_cost=str(reserved),
            actual_cost=str(actual),
            cap=str(OPERATIONAL_COST_CAP),
        )
        raise PilotBudgetClosed("V7 operational cost cap reached.")
    if reserved > STOP_BEFORE_NEXT_EPISODE or actual > STOP_BEFORE_NEXT_EPISODE:
        ledger.close(
            "V7_PRE_EPISODE_COST_GUARD",
            reserved_cost=str(reserved),
            actual_cost=str(actual),
            stop_threshold=str(STOP_BEFORE_NEXT_EPISODE),
        )
        raise PilotBudgetClosed(
            "V7 pilot stopped before the next episode to preserve the cost cap."
        )


def _progress(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def execute_paid() -> int:
    gate = load_and_validate_gate(ROOT / GATE_PATH)
    settings = _settings_for_paid_run()
    specs = _selected_specs()
    existing = _read_registry()
    if existing is not None:
        raise RuntimeError(
            "A V7 pilot registry already exists; archive it explicitly before a new run."
        )
    token = uuid4().hex
    label = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = V7_EXPERIMENT_ROOT / f"{EXPERIMENT_LABEL}_{label}_{token}"
    ledger_path = V7_LEDGER_ROOT / f"{EXPERIMENT_LABEL}_{label}_{token}.jsonl"
    source_hashes = {
        "__offline_gate__": gate["frozen_gate_hash"],
        "__runtime_tree__": gate["runtime_tree_hash"],
        "__v7_registration__": sha256_file(REGISTRATION_PATH),
        "__v7_script__": sha256_file(Path(__file__)),
        "__v7_selection__": canonical_hash(SELECTED),
    }
    ledger = V6BudgetLedger(
        ledger_path,
        currency=CURRENCY,
        model=MODEL_NAME,
        source_hashes=source_hashes,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    manifest_path = run_dir / "run_manifest.json"
    completed: list[str] = []
    _claim_registry(
        {
            "schema_version": "v7_pilot_registry_v1",
            "experiment_label": EXPERIMENT_LABEL,
            "experiment_id": ledger.experiment_id,
            "status": "running",
            "stage": "preflight",
            "updated_at": utc_now(),
            "run_dir": str(run_dir.relative_to(ROOT)),
            "ledger_path": str(ledger.path.relative_to(ROOT)),
            "offline_gate_hash": gate["frozen_gate_hash"],
            "runtime_commit": gate["runtime_commit"],
            "billing_currency": CURRENCY,
            "completed_episode_count": 0,
            "ledger_snapshot": ledger.snapshot(),
        }
    )
    _write_manifest(
        manifest_path,
        ledger=ledger,
        run_dir=run_dir,
        gate=gate,
        status="running",
        stage="preflight",
        started_at=started_at,
        completed=completed,
    )
    provider = OpenAIDecisionProvider(settings)
    runner = V6PilotRunner(
        provider=provider,
        settings=settings,
        ledger=ledger,
        output_dir=run_dir,
        progress=_progress,
        offline_gate_hash=gate["frozen_gate_hash"],
        runtime_commit=gate["runtime_commit"],
        runtime_tree_hash=gate["runtime_tree_hash"],
    )
    try:
        for index, spec in enumerate(specs, 1):
            if ledger.closed:
                break
            _cost_guard(ledger)
            _progress(
                {
                    "event": "v7_episode_queued",
                    "index": index,
                    "total": len(specs),
                    "episode_id": spec.episode_id,
                    "ledger_snapshot": ledger.snapshot(),
                }
            )
            result = runner.run(spec)
            if result.get("outcome") in INCOMPLETE_OUTCOMES:
                if not ledger.closed:
                    ledger.close(
                        "V7_INCOMPLETE_EPISODE",
                        episode_id=spec.episode_id,
                        outcome=result.get("outcome"),
                    )
                _write_manifest(
                    manifest_path,
                    ledger=ledger,
                    run_dir=run_dir,
                    gate=gate,
                    status="stopped",
                    stage="matrix",
                    started_at=started_at,
                    completed=completed,
                    error=f"incomplete episode: {result.get('outcome')}",
                )
                return 2
            completed = sorted(ledger.completed_episode_ids())
            _write_manifest(
                manifest_path,
                ledger=ledger,
                run_dir=run_dir,
                gate=gate,
                status="running",
                stage="matrix",
                started_at=started_at,
                completed=completed,
            )
    except Exception as exc:  # noqa: BLE001
        if not ledger.closed:
            ledger.close("V7_DRIVER_ABORTED", error_type=type(exc).__name__)
        error_text = f"{type(exc).__name__}: {exc}"
        (run_dir / "driver_error.txt").write_text(
            error_text + "\n\n" + traceback.format_exc(),
            encoding="utf-8",
            newline="\n",
        )
        _write_manifest(
            manifest_path,
            ledger=ledger,
            run_dir=run_dir,
            gate=gate,
            status="aborted",
            stage="matrix",
            started_at=started_at,
            completed=completed,
            error=error_text[:1_000],
        )
        _progress({"event": "v7_pilot_aborted", "error": error_text[:500]})
        return 2
    completed = sorted(ledger.completed_episode_ids())
    complete = len(completed) == MAX_EPISODES and not ledger.closed
    if complete:
        ledger.record(
            "pilot_completed",
            episode_count=MAX_EPISODES,
            snapshot=ledger.snapshot(),
        )
    _write_manifest(
        manifest_path,
        ledger=ledger,
        run_dir=run_dir,
        gate=gate,
        status="completed" if complete else "stopped",
        stage="complete" if complete else "matrix",
        started_at=started_at,
        completed=completed,
        error=None if complete else "pilot did not complete all registered episodes",
    )
    _progress(
        {
            "event": "v7_pilot_finished",
            "status": "completed" if complete else "stopped",
            "experiment_id": ledger.experiment_id,
            "completed_episodes": len(completed),
            "registered_episodes": MAX_EPISODES,
            "run_dir": str(run_dir.relative_to(ROOT)),
            "ledger_snapshot": ledger.snapshot(),
        }
    )
    return 0 if complete else 2


def preflight() -> int:
    gate = load_and_validate_gate(ROOT / GATE_PATH)
    _settings_for_paid_run()
    payload = _preflight_payload(gate)
    existing = _read_registry()
    payload["existing_registry"] = existing
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V7 six-map 12-episode paid pilot.")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute-paid", action="store_true")
    args = parser.parse_args()
    if args.preflight == args.execute_paid:
        parser.error("choose exactly one of --preflight or --execute-paid")
    return args


def main() -> int:
    args = parse_args()
    try:
        return execute_paid() if args.execute_paid else preflight()
    except (PilotBudgetClosed, RuntimeError, ValueError, OSError) as exc:
        print(f"V7 pilot refused or stopped ({type(exc).__name__}).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
