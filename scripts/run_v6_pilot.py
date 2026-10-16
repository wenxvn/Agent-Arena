"""V6 six-map measurement-validity pilot; defaults to a fake dry-run.

Paid execution is opt-in via ``--execute-paid`` and requires the exact local
MiMo endpoint, a passing frozen V6 offline gate, a fresh V6 ledger, and a
CNY/USD hard cap. It never opens or mutates the V2/V5 ledgers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse  # noqa: E402
from agent_arena.v6.budget import (  # noqa: E402
    MAX_DECISIONS_PER_EPISODE,
    MAX_EPISODES,
    MAX_PROVIDER_SECONDS_GLOBAL,
    MAX_REQUESTS_GLOBAL,
    MAX_RESERVED_TOKENS_GLOBAL,
    PRICE_SHEETS,
    PRICE_URL,
    PilotBudgetClosed,
    V6BudgetLedger,
)
from agent_arena.v6.offline_gate import GATE_PATH, load_and_validate_gate  # noqa: E402
from agent_arena.v6.runner import (  # noqa: E402
    V6PilotRunner,
    registered_v6_matrix,
    smoke_specs,
)

PILOT_REGISTRY_PATH = ROOT / "runs" / "v6" / "pilot_registry.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def read_pilot_registry(path: Path = PILOT_REGISTRY_PATH) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "The V6 pilot registry is malformed; no new paid run is allowed."
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "v6_pilot_registry_v1":
        raise RuntimeError("The V6 pilot registry is invalid; no new paid run is allowed.")
    return payload


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".v6-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def claim_pilot_registry(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RuntimeError(
            "A V6 paid pilot is already registered; do not create another ledger."
        ) from exc


def update_pilot_registry(path: Path, payload: dict[str, Any]) -> None:
    prior = read_pilot_registry(path)
    identity_fields = ("experiment_id", "run_dir", "ledger_path", "offline_gate_hash")
    if prior is None or any(prior.get(field) != payload.get(field) for field in identity_fields):
        raise RuntimeError("V6 pilot registry identity changed; refusing further paid execution.")
    atomic_write(path, payload)


class _OfflineFakeProvider:
    def decide(self, request: DecisionRequest) -> ProviderResponse:
        observation = request.observation
        map_id = getattr(observation, "map_id", None)
        actions: dict[str, dict[str, Any]] = {
            "MAP-08": {"tool": "wait", "turns": 1},
            "MAP-16": {"tool": "inspect_network"},
            "MAP-18": {
                "tool": "set_timetable",
                "tick": int(getattr(observation, "tick", 0)),
                "operations": {},
            },
            "MAP-22": {"tool": "observe_signpost"},
            "MAP-26": {"tool": "move", "to": "D"},
            "MAP-30": {
                "tool": "move",
                "to": next(iter(getattr(observation, "local_neighbors", ())), "J"),
            },
        }
        if map_id not in actions:
            raise AssertionError("Offline fake received an unregistered map.")
        return ProviderResponse(
            candidate={
                "decision_reason": "离线协议冒烟。",
                "action": actions[map_id],
                "agent_hypothesis_table": None,
            },
            input_tokens=80,
            output_tokens=30,
            cached_input_tokens=0,
        )


def run_fake_dry_run() -> dict[str, Any]:
    """Run one fake decision on each V6 smoke condition without reading .env."""
    with tempfile.TemporaryDirectory(prefix="agent-arena-v6-dryrun-") as temporary:
        root = Path(temporary)
        settings = RuntimeSettings.load(
            {
                "provider": "fake",
                "world": "scenario_v4",
                "world_version": "V4",
                "agent": "react",
                "seed": 0,
                "runs_dir": root / "runs",
                "results_dir": root / "results",
                "step_limit": 100,
                "request_timeout_seconds": 30,
                "retry_count": 0,
                "retry_backoff_seconds": [],
                "enable_thinking": False,
                "reasoning_effort": "none",
                "response_format": "json_object",
                "model_name": "offline-fake-v6",
            },
            env_file=None,
        )
        ledger = V6BudgetLedger(
            root / "ledger.jsonl",
            currency="CNY",
            model="offline-fake-v6",
            source_hashes={"__fake__": "offline"},
        )
        runner = V6PilotRunner(
            provider=_OfflineFakeProvider(),
            settings=settings,
            ledger=ledger,
            output_dir=root / "experiment",
            decision_limit=1,
        )
        summaries = [runner.run(spec) for spec in smoke_specs()]
        if len(summaries) != 6 or ledger.snapshot()["request_attempts"] != 6:
            raise RuntimeError("Fake V6 dry run did not complete exactly six decisions.")
        for summary in summaries:
            episode_dir = root / "experiment" / "episodes" / summary["episode_id"]
            required = (
                episode_dir / "agent_trace.jsonl",
                episode_dir / "judge_metrics.json",
                episode_dir / "episode_manifest.json",
            )
            if any(not path.is_file() for path in required):
                raise RuntimeError("Fake V6 dry run did not write all trace layers.")
        return {
            "episodes": len(summaries),
            "fake_requests": ledger.snapshot()["request_attempts"],
            "paid_api_calls": 0,
            "persistent_output": False,
        }


def print_preflight() -> None:
    cny = PRICE_SHEETS["CNY"].reserve_per_request()
    usd = PRICE_SHEETS["USD"].reserve_per_request()
    print(
        json.dumps(
            {
                "mode": "dry-run",
                "registered_episodes": MAX_EPISODES,
                "smoke_episodes": 6,
                "decision_cap_per_episode": MAX_DECISIONS_PER_EPISODE,
                "global_request_attempt_cap": MAX_REQUESTS_GLOBAL,
                "global_reserved_token_cap": MAX_RESERVED_TOKENS_GLOBAL,
                "global_provider_wall_seconds_cap": MAX_PROVIDER_SECONDS_GLOBAL,
                "CNY": {
                    "per_request_reserve": str(cny),
                    "global_reserve": str(cny * MAX_REQUESTS_GLOBAL),
                    "hard_cap": str(PRICE_SHEETS["CNY"].max_cost),
                },
                "USD": {
                    "per_request_reserve": str(usd),
                    "global_reserve": str(usd * MAX_REQUESTS_GLOBAL),
                    "hard_cap": str(PRICE_SHEETS["USD"].max_cost),
                },
                "price_source": PRICE_URL,
                "message": "dry-run uses only a fake provider and temporary local files",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    print(json.dumps(run_fake_dry_run(), ensure_ascii=False, sort_keys=True))


def _path_under_v6_runs(raw: str) -> Path:
    path = Path(raw)
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    required_root = (ROOT / "runs" / "v6").resolve()
    try:
        resolved.relative_to(required_root)
    except ValueError as exc:
        raise ValueError("Run and ledger paths must stay under runs/v6.") from exc
    return resolved


def _settings_for_paid_run() -> RuntimeSettings:
    configured = RuntimeSettings.load(env_file=ROOT / ".env")
    if configured.provider != "openai" or configured.model_name != "mimo-v2.6-flash":
        raise ValueError("Local provider/model settings do not match the registered MiMo pilot.")
    settings = RuntimeSettings.load(
        {
            "provider": "openai",
            "world": "scenario_v4",
            "world_version": "V4",
            "agent": "react",
            "seed": 0,
            "runs_dir": ROOT / "runs" / "v6",
            "results_dir": ROOT / "results" / "v6",
            "step_limit": 100,
            "request_timeout_seconds": 30,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "reasoning_effort": "none",
            "response_format": "json_object",
            "model_name": "mimo-v2.6-flash",
        },
        env_file=ROOT / ".env",
    )
    if settings.provider != "openai" or settings.model_name != "mimo-v2.6-flash":
        raise ValueError("Local provider configuration does not match the registered MiMo model.")
    if not settings.openai_api_key:
        raise ValueError("The local MiMo API credential is not configured.")
    if not settings.base_url:
        raise ValueError("The local MiMo API endpoint is not configured.")
    endpoint = urlparse(settings.base_url)
    if (
        endpoint.scheme != "https"
        or endpoint.hostname != "api.xiaomimimo.com"
        or endpoint.path.rstrip("/") != "/v1"
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("The endpoint does not match the Xiaomi MiMo Responses API.")
    return settings


def _verify_smoke(ledger: V6BudgetLedger, run_dir: Path, gate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for spec in smoke_specs():
        episode_dir = run_dir / "episodes" / spec.episode_id
        trace_path = episode_dir / "agent_trace.jsonl"
        judge_path = episode_dir / "judge_metrics.json"
        manifest_path = episode_dir / "episode_manifest.json"
        if not all(path.is_file() for path in (trace_path, judge_path, manifest_path)):
            raise RuntimeError(f"Smoke artifacts are incomplete for {spec.episode_id}.")
        trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        judge = json.loads(judge_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not trace or trace[0].get("event") != "trace_header":
            raise RuntimeError(f"Smoke trace header is missing for {spec.episode_id}.")
        if any(
            field in json.dumps(trace, ensure_ascii=False)
            for field in ("true_leak", "oracle_trace", "answer_table", "future_events")
        ):
            raise RuntimeError(f"Private data appeared in smoke trace: {spec.episode_id}.")
        usage = judge.get("usage", {})
        if (
            judge.get("episode_id") != spec.episode_id
            or judge.get("offline_gate_hash") != gate["frozen_gate_hash"]
            or judge.get("runtime_commit") != gate["runtime_commit"]
            or judge.get("provider") != "openai"
            or judge.get("model") != "mimo-v2.6-flash"
            or judge.get("status")
            not in {"success", "failure", "decision_limit", "censored"}
            or not isinstance(usage.get("input_tokens"), int)
            or usage.get("settled_requests", 0) < 1
            or usage.get("unknown_spend_failures", 0) != 0
        ):
            raise RuntimeError(f"Incomplete smoke usage or metrics: {spec.episode_id}.")
        if manifest.get("offline_gate_hash") != gate["frozen_gate_hash"]:
            raise RuntimeError(f"Smoke manifest provenance failed for {spec.episode_id}.")
        checks.append(
            {
                "episode_id": spec.episode_id,
                "status": judge["status"],
                "decisions": judge["decision_count"],
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "reported_usage_cost": usage["reported_usage_cost"],
            }
        )
    return {
        "verified_at": utc_now(),
        "episode_count": len(checks),
        "checks": checks,
        "ledger_snapshot": ledger.snapshot(),
    }


def _write_run_manifest(
    path: Path,
    *,
    ledger: V6BudgetLedger,
    run_dir: Path,
    gate: dict[str, Any],
    currency: str,
    stage: str,
    status: str,
    smoke_report: dict[str, Any] | None,
    started_at: str,
) -> None:
    matrix = registered_v6_matrix()
    payload = {
        "schema_version": "v6_run_manifest_v1",
        "experiment_id": ledger.experiment_id,
        "status": status,
        "stage": stage,
        "started_at": started_at,
        "updated_at": utc_now(),
        "finished_at": utc_now() if status in {"completed", "stopped", "aborted"} else None,
        "provider": "openai",
        "model": "mimo-v2.6-flash",
        "temperature": 0,
        "billing_currency": currency,
        "price_source": PRICE_URL,
        "price_checked_on": "2026-10-16",
        "offline_gate_hash": gate["frozen_gate_hash"],
        "runtime_commit": gate["runtime_commit"],
        "runtime_tree_hash": gate["runtime_tree_hash"],
        "run_dir": str(run_dir.relative_to(ROOT)),
        "ledger_path": str(ledger.path.relative_to(ROOT)),
        "max_episodes": MAX_EPISODES,
        "max_requests_global": MAX_REQUESTS_GLOBAL,
        "max_reserved_tokens_global": MAX_RESERVED_TOKENS_GLOBAL,
        "currency_hard_cap": str(PRICE_SHEETS[currency].max_cost),
        "registered_matrix": [
            {
                "episode_id": item.episode_id,
                "instance_id": item.instance_id,
                "condition_id": item.condition_id,
                "seed": item.seed,
            }
            for item in matrix
        ],
        "smoke_report": smoke_report,
        "ledger_snapshot": ledger.snapshot(),
    }
    atomic_write(path, payload)
    update_pilot_registry(
        PILOT_REGISTRY_PATH,
        {
            "schema_version": "v6_pilot_registry_v1",
            "experiment_id": ledger.experiment_id,
            "status": status,
            "stage": stage,
            "updated_at": payload["updated_at"],
            "run_dir": str(run_dir.relative_to(ROOT)),
            "ledger_path": str(ledger.path.relative_to(ROOT)),
            "offline_gate_hash": gate["frozen_gate_hash"],
            "runtime_commit": gate["runtime_commit"],
            "billing_currency": currency,
            "completed_episode_count": len(ledger.completed_episode_ids()),
            "ledger_snapshot": ledger.snapshot(),
        },
    )


_INCOMPLETE = {
    "provider_error",
    "provider_error_limit",
    "unknown_provider_spend",
    "input_context_limit",
    "episode_timeout",
    "global_provider_timeout",
    "incomplete",
    "invalid_action_schema_limit",
}


def execute_paid(args: argparse.Namespace) -> int:
    if not args.billing_currency:
        raise ValueError("--billing-currency CNY|USD is required for every paid run.")
    currency = args.billing_currency
    gate_path = Path(args.offline_gate)
    gate_path = (ROOT / gate_path).resolve() if not gate_path.is_absolute() else gate_path.resolve()
    gate = load_and_validate_gate(gate_path)
    settings = _settings_for_paid_run()
    provider = OpenAIDecisionProvider(settings)
    run_dir = _path_under_v6_runs(args.run_dir) if args.run_dir else None
    ledger_path = _path_under_v6_runs(args.ledger) if args.ledger else None
    if args.resume:
        if run_dir is None or ledger_path is None:
            raise ValueError("--resume requires the exact --run-dir and --ledger paths.")
        prior = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        registry = read_pilot_registry()
        if (
            registry is None
            or registry.get("experiment_id") != prior.get("experiment_id")
            or registry.get("offline_gate_hash") != gate["frozen_gate_hash"]
            or prior.get("offline_gate_hash") != gate["frozen_gate_hash"]
            or prior.get("billing_currency") != currency
        ):
            raise ValueError("Resume settings differ from the registered V6 run.")
        started_at = prior["started_at"]
    else:
        if read_pilot_registry() is not None:
            raise ValueError("A V6 paid pilot is already registered; do not create another ledger.")
        if run_dir is not None or ledger_path is not None:
            raise ValueError("Custom --run-dir/--ledger paths are reserved for --resume only.")
        token = uuid4().hex
        label = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = ROOT / "runs" / "v6" / "experiments" / f"pilot_{label}_{token}"
        ledger_path = ROOT / "runs" / "v6" / "ledgers" / f"pilot_{label}_{token}.jsonl"
        started_at = utc_now()
    assert run_dir is not None and ledger_path is not None
    source_hashes = {
        "__offline_gate__": gate["frozen_gate_hash"],
        "__runtime_tree__": gate["runtime_tree_hash"],
    }
    ledger = V6BudgetLedger(
        ledger_path,
        currency=currency,
        model=settings.model_name,
        source_hashes=source_hashes,
        resume=args.resume,
    )
    if not args.resume:
        claim_pilot_registry(
            PILOT_REGISTRY_PATH,
            {
                "schema_version": "v6_pilot_registry_v1",
                "experiment_id": ledger.experiment_id,
                "status": "running",
                "stage": "smoke",
                "updated_at": utc_now(),
                "run_dir": str(run_dir.relative_to(ROOT)),
                "ledger_path": str(ledger.path.relative_to(ROOT)),
                "offline_gate_hash": gate["frozen_gate_hash"],
                "runtime_commit": gate["runtime_commit"],
                "billing_currency": currency,
                "completed_episode_count": 0,
                "ledger_snapshot": ledger.snapshot(),
            },
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest.json"
    if not args.resume:
        _write_run_manifest(
            manifest_path,
            ledger=ledger,
            run_dir=run_dir,
            gate=gate,
            currency=currency,
            stage="smoke",
            status="running",
            smoke_report=None,
            started_at=started_at,
        )
    runner = V6PilotRunner(
        provider=provider,
        settings=settings,
        ledger=ledger,
        output_dir=run_dir,
        progress=lambda payload: print(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        offline_gate_hash=gate["frozen_gate_hash"],
        runtime_commit=gate["runtime_commit"],
        runtime_tree_hash=gate["runtime_tree_hash"],
    )
    all_specs = registered_v6_matrix()
    smoke_ids = {item.episode_id for item in smoke_specs()}
    existing_stage_gate = next(
        (event for event in ledger.read_events() if event["event"] == "stage_gate_completed"),
        None,
    )
    smoke_report: dict[str, Any] | None = None
    if existing_stage_gate is None:
        for spec in smoke_specs():
            if spec.episode_id in ledger.completed_episode_ids():
                continue
            try:
                result = runner.run(spec)
            except Exception as exc:  # noqa: BLE001
                if not ledger.closed:
                    ledger.close(
                        "SMOKE_RUNNER_ABORTED",
                        episode_id=spec.episode_id,
                        error_type=type(exc).__name__,
                    )
                _write_run_manifest(
                    manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
                    currency=currency, stage="smoke", status="aborted",
                    smoke_report=None, started_at=started_at,
                )
                print(f"Paid V6 pilot aborted safely in smoke ({type(exc).__name__}).")
                return 2
            if result["outcome"] in _INCOMPLETE:
                if not ledger.closed:
                    ledger.close("SMOKE_INCOMPLETE", episode_id=spec.episode_id)
                _write_run_manifest(
                    manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
                    currency=currency, stage="smoke", status="stopped",
                    smoke_report=None, started_at=started_at,
                )
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                print("Paid V6 pilot stopped during smoke; no matrix episodes were started.")
                return 2
            _write_run_manifest(
                manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
                currency=currency, stage="smoke", status="running",
                smoke_report=None, started_at=started_at,
            )
        try:
            smoke_report = _verify_smoke(ledger, run_dir, gate)
        except Exception as exc:  # noqa: BLE001
            if not ledger.closed:
                ledger.close("SMOKE_VALIDATION_FAILED", error_type=type(exc).__name__)
            _write_run_manifest(
                manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
                currency=currency, stage="smoke", status="stopped",
                smoke_report=None, started_at=started_at,
            )
            print(f"Paid V6 pilot stopped: smoke evidence failed ({type(exc).__name__}).")
            return 2
        ledger.record("stage_gate_completed", stage="smoke", smoke_report=smoke_report)
    else:
        smoke_report = existing_stage_gate.get("smoke_report")
        if not isinstance(smoke_report, dict):
            smoke_report = _verify_smoke(ledger, run_dir, gate)
    _write_run_manifest(
        manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
        currency=currency, stage="matrix", status="running",
        smoke_report=smoke_report, started_at=started_at,
    )
    for spec in all_specs:
        if spec.episode_id in smoke_ids or spec.episode_id in ledger.completed_episode_ids():
            continue
        if ledger.closed:
            break
        try:
            result = runner.run(spec)
        except Exception as exc:  # noqa: BLE001
            if not ledger.closed:
                ledger.close("MATRIX_RUNNER_ABORTED", episode_id=spec.episode_id,
                             error_type=type(exc).__name__)
            _write_run_manifest(
                manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
                currency=currency, stage="matrix", status="aborted",
                smoke_report=smoke_report, started_at=started_at,
            )
            print(f"Paid V6 pilot aborted safely in matrix ({type(exc).__name__}).")
            return 2
        if result["outcome"] in _INCOMPLETE:
            if not ledger.closed:
                ledger.close("MATRIX_EPISODE_INCOMPLETE", episode_id=spec.episode_id)
            break
        _write_run_manifest(
            manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
            currency=currency, stage="matrix", status="running",
            smoke_report=smoke_report, started_at=started_at,
        )
    complete = len(ledger.completed_episode_ids()) == MAX_EPISODES and not ledger.closed
    status = "completed" if complete else "stopped"
    if complete and not any(event["event"] == "pilot_completed" for event in ledger.read_events()):
        ledger.record("pilot_completed", episode_count=MAX_EPISODES, snapshot=ledger.snapshot())
    _write_run_manifest(
        manifest_path, ledger=ledger, run_dir=run_dir, gate=gate,
        currency=currency, stage="complete" if complete else "matrix", status=status,
        smoke_report=smoke_report, started_at=started_at,
    )
    print(
        json.dumps(
            {
                "status": status,
                "experiment_id": ledger.experiment_id,
                "completed_episodes": len(ledger.completed_episode_ids()),
                "total_episodes": MAX_EPISODES,
                "ledger_snapshot": ledger.snapshot(),
                "run_manifest": str(manifest_path.relative_to(ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if complete else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V6 six-map pilot; defaults to fake dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-paid", action="store_true")
    parser.add_argument("--billing-currency", choices=("CNY", "USD"))
    parser.add_argument("--offline-gate", default=str(GATE_PATH))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-dir")
    parser.add_argument("--ledger")
    args = parser.parse_args()
    if args.dry_run and args.execute_paid:
        parser.error("--dry-run and --execute-paid cannot be combined.")
    if args.resume and not args.execute_paid:
        parser.error("--resume is only valid with --execute-paid.")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.execute_paid:
            return execute_paid(args)
        print_preflight()
        return 0
    except (PilotBudgetClosed, RuntimeError, ValueError, OSError) as exc:
        print(f"V6 pilot refused or stopped ({type(exc).__name__}).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
