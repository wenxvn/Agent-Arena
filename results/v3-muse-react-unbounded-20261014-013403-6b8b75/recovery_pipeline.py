from __future__ import annotations

import hashlib
import json
import os
import psutil
import re
import subprocess
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = Path(__file__).resolve().parent
EXPERIMENT_ID = RESULT_DIR.name
RUN_ROOT = ROOT / "runs" / EXPERIMENT_ID
MANIFEST_PATH = RESULT_DIR / "manifest.json"
STATE_PATH = RESULT_DIR / "recovery_pipeline_state.json"
NATURAL_OUTCOMES = {"scenario_success", "success", "partial_success", "scenario_failure", "failure"}
STATE_LOCK = threading.RLock()
STATE: dict[str, object]


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_state() -> None:
    with STATE_LOCK:
        STATE["updated_at"] = now()
        temp = STATE_PATH.with_suffix(".json.tmp")
        payload = json.dumps(STATE, ensure_ascii=False, indent=2) + "\n"
        for retry in range(12):
            temp.write_text(payload, encoding="utf-8")
            try:
                os.replace(temp, STATE_PATH)
                return
            except PermissionError:
                if retry == 11:
                    raise
                import time
                time.sleep(0.025 * (retry + 1))


def active_episode_process_count() -> int:
    count = 0
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            args = proc.info.get("cmdline") or []
            if (
                str(proc.info.get("name", "")).lower().startswith("python")
                and "agent_arena.cli" in " ".join(args)
                and "--output-dir" in args
                and EXPERIMENT_ID in args[args.index("--output-dir") + 1]
            ):
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            continue
    return count


def build_jobs(manifest: dict[str, object]) -> list[dict[str, object]]:
    records = manifest["episodes"]
    assert isinstance(records, list)
    by_case: dict[tuple[str, int], list[dict[str, object]]] = {}
    for record in records:
        by_case.setdefault((str(record["scenario_id"]), int(record["seed"])), []).append(record)

    jobs: list[dict[str, object]] = []
    for case, attempts in sorted(by_case.items()):
        if any(
            attempt.get("trace_identity_valid")
            and attempt.get("outcome") in NATURAL_OUTCOMES
            and isinstance(attempt.get("executed_action_count"), int)
            for attempt in attempts
        ):
            continue
        if any(attempt.get("status") in {"planned", "running"} for attempt in attempts):
            continue
        base = next((item for item in attempts if str(item["attempt_id"]).endswith("attempt-01")), attempts[0])
        latest = max(
            attempts,
            key=lambda item: int(re.search(r"attempt-(\d+)$", str(item["attempt_id"])).group(1)),
        )
        latest_n = int(re.search(r"attempt-(\d+)$", str(latest["attempt_id"])).group(1))
        next_n = latest_n + 1
        attempt_id = re.sub(r"attempt-\d+$", f"attempt-{next_n:02d}", str(latest["attempt_id"]))
        clean_fields = {
            "status", "outcome", "trace_path", "trace_sha256", "trace_identity_valid", "episode_id",
            "created_at", "executed_action_count", "invalid_output_count", "rejected_action_count",
            "latency_ms", "started_at", "ended_at", "return_code", "trace_count", "error_type",
            "error_note", "live_decision_attempt", "progress_updated_at", "provider_error_diagnostics",
            "actual_output_subdir", "trace_selection_note", "output_subdir", "retry_of", "retry_reason",
            "request_timeout_seconds", "interruption_note",
        }
        item = {key: value for key, value in base.items() if key not in clean_fields}
        item.update({
            "attempt_id": attempt_id,
            "status": "planned",
            "outcome": None,
            "retry_of": str(latest["attempt_id"]),
            "retry_reason": "Resume seed without a valid natural-terminal trace after recorded provider/infrastructure failure.",
            "output_subdir": f"seed-{case[1]}-attempt-{next_n:02d}",
            "request_timeout_seconds": 120,
        })
        jobs.append({
            "attempt": item,
            "status": "planned",
            "live_decision_attempt": None,
            "result": None,
        })
    return jobs


BOOTSTRAP = """
import json, sys
sys.path.insert(0, 'src')
from agent_arena.llm.openai import OpenAIDecisionProvider
_original_decide = OpenAIDecisionProvider.decide
def _diagnostic_decide(self, request):
    try:
        return _original_decide(self, request)
    except Exception as exc:
        chain = []
        current = exc
        while current is not None and len(chain) < 8:
            chain.append(type(current).__name__)
            current = current.__cause__ or current.__context__
        status = None
        current = exc
        while current is not None and status is None:
            status = getattr(current, 'status_code', None)
            current = current.__cause__ or current.__context__
        print('SAFE_PROVIDER_DIAG:' + json.dumps({
            'exception_chain': chain,
            'http_status': status,
        }), file=sys.stderr, flush=True)
        raise
OpenAIDecisionProvider.decide = _diagnostic_decide
from agent_arena.cli import app
app()
"""


def run_episode(job_index: int, model_name: str) -> dict[str, object]:
    job = STATE["jobs"][job_index]
    assert isinstance(job, dict)
    item = job["attempt"]
    assert isinstance(item, dict)
    out_dir = RUN_ROOT / str(item["scenario_id"]) / str(item["output_subdir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-u", "-c", BOOTSTRAP, "run",
        "--provider", "openai",
        "--agent", "react",
        "--seed", str(item["seed"]),
        "--world", str(item["world"]),
        "--world-version", str(item["world_version"]),
        "--output-dir", str(out_dir),
        "--autonomous",
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["AGENT_ARENA_STEP_LIMIT"] = "0"
    env["AGENT_ARENA_REQUEST_TIMEOUT_SECONDS"] = "120"
    env["OPENAI_MODEL"] = model_name
    diagnostics: list[dict[str, object]] = []
    last_progress_saved = 0
    try:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True, encoding="utf-8", errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            match = re.search(r"正在请求第 (\d+)/不限 步", line)
            if match:
                progress = int(match.group(1))
                if progress - last_progress_saved >= 50:
                    with STATE_LOCK:
                        job["live_decision_attempt"] = progress
                        job["progress_updated_at"] = now()
                    save_state()
                    last_progress_saved = progress
            if "SAFE_PROVIDER_DIAG:" in line:
                try:
                    diagnostic = json.loads(line.split("SAFE_PROVIDER_DIAG:", 1)[1].strip())
                    if isinstance(diagnostic, dict):
                        diagnostics.append(diagnostic)
                except json.JSONDecodeError:
                    pass
        return_code = process.wait()
    except Exception as exc:
        result = {
            "attempt_id": item["attempt_id"],
            "status": "launch_error",
            "ended_at": now(),
            "error_type": type(exc).__name__,
            "error_note": str(exc)[:240],
            "provider_error_diagnostics": diagnostics,
        }
        return result

    trace_paths = sorted(out_dir.glob("episode_*.json"))
    trace_meta: dict[str, object] | None = None
    if len(trace_paths) == 1:
        path = trace_paths[0]
        try:
            trace = json.loads(path.read_text(encoding="utf-8"))
            identity_ok = (
                trace.get("world_version") == item["world_version"]
                and trace.get("seed") == item["seed"]
                and trace.get("scenario_id") == item["scenario_id"]
            )
            trace_meta = {
                "trace_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "trace_sha256": sha256(path),
                "trace_identity_valid": identity_ok,
                "episode_id": trace.get("episode_id"),
                "created_at": trace.get("created_at"),
                "prompt_version": trace.get("prompt_version"),
                "provider": trace.get("provider"),
                "outcome": trace.get("outcome"),
                "executed_action_count": trace.get("executed_action_count"),
                "invalid_output_count": trace.get("invalid_output_count"),
                "rejected_action_count": trace.get("rejected_action_count"),
                "latency_ms": trace.get("latency_ms"),
            }
        except Exception as exc:
            trace_meta = {"trace_parse_error": type(exc).__name__}
    if trace_meta and trace_meta.get("trace_identity_valid"):
        status = "completed" if return_code == 0 else "trace_with_cli_error"
        result = {**trace_meta, "status": status, "return_code": return_code, "ended_at": now()}
    else:
        result = {
            "status": "cli_error" if return_code else "missing_or_invalid_trace",
            "return_code": return_code,
            "ended_at": now(),
            "trace_count": len(trace_paths),
            **(trace_meta or {}),
        }
    if diagnostics:
        result["provider_error_diagnostics"] = diagnostics
    return {"attempt_id": item["attempt_id"], **result}


def main() -> int:
    global STATE
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    jobs = build_jobs(manifest)
    running_episode_processes = active_episode_process_count()
    if running_episode_processes > 21:
        raise RuntimeError(f"Existing episode process count already exceeds 21: {running_episode_processes}")
    workers = min(21 - running_episode_processes, len(jobs))
    if workers < 1 and jobs:
        raise RuntimeError("No episode worker slot is available under the 21-process cap.")
    STATE = {
        "experiment_id": EXPERIMENT_ID,
        "status": "in_progress",
        "created_at": now(),
        "base_manifest_sha256": sha256(MANIFEST_PATH),
        "target_cases_missing_natural_terminal_at_start": len(jobs) + (1 if any(
            e.get("status") == "running" and (e.get("scenario_id"), e.get("seed")) == ("CA-M", 0)
            for e in manifest["episodes"]
        ) else 0),
        "request_timeout_seconds": 120,
        "episode_step_limit": 0,
        "max_total_episode_processes": 21,
        "existing_episode_processes_at_start": running_episode_processes,
        "parallel_recovery_workers": workers,
        "jobs": jobs,
        "completed_jobs": 0,
    }
    save_state()
    if not jobs:
        print("No missing natural-terminal seed cases found.", flush=True)
        return 0
    model_name = str(manifest["design"]["requested_model"])
    print(
        f"Recovery pipeline: missing seed jobs={len(jobs)}, active_before={running_episode_processes}, "
        f"workers={workers}, total_process_cap=21, timeout=120s, step_limit=0.",
        flush=True,
    )
    futures: dict[Future[dict[str, object]], int] = {}
    next_index = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while next_index < len(jobs) and len(futures) < workers:
            index = next_index
            next_index += 1
            jobs[index]["status"] = "running"
            jobs[index]["started_at"] = now()
            save_state()
            futures[executor.submit(run_episode, index, model_name)] = index
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                index = futures.pop(future)
                job = jobs[index]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "attempt_id": job["attempt"]["attempt_id"],
                        "status": "worker_error",
                        "error_type": type(exc).__name__,
                        "error_note": str(exc)[:240],
                    }
                job["result"] = result
                job["status"] = str(result.get("status", "unknown"))
                job["ended_at"] = now()
                STATE["completed_jobs"] = int(STATE["completed_jobs"]) + 1
                save_state()
                print(
                    f"[{STATE['completed_jobs']}/{len(jobs)}] {result['attempt_id']} "
                    f"outcome={result.get('outcome') or result.get('status')} "
                    f"actions={result.get('executed_action_count', '-')} status={result.get('status')}",
                    flush=True,
                )
                if next_index < len(jobs):
                    new_index = next_index
                    next_index += 1
                    jobs[new_index]["status"] = "running"
                    jobs[new_index]["started_at"] = now()
                    save_state()
                    futures[executor.submit(run_episode, new_index, model_name)] = new_index
    complete = int(STATE["completed_jobs"]) == len(jobs)
    STATE["status"] = "complete" if complete else "incomplete"
    STATE["ended_at"] = now()
    save_state()
    print(json.dumps({"status": STATE["status"], "completed_jobs": STATE["completed_jobs"], "planned_jobs": len(jobs), "state_path": str(STATE_PATH.relative_to(ROOT))}, ensure_ascii=False), flush=True)
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
