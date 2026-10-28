from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ID = RESULT_ROOT.name
RUN_ROOT = ROOT / "runs" / EXPERIMENT_ID
MANIFEST_PATH = RESULT_ROOT / "manifest.json"
SUMMARY_PATH = RESULT_ROOT / "matrix_summary.json"
PROMPT_PATH = ROOT / "prompts" / "react_scenario_v3.txt"
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings
from agent_arena.worlds.scenario.catalog import SCENARIO_REGISTRY, create_scenario_environment


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for attempt in range(12):
        temp.write_text(serialized, encoding="utf-8")
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(0.025 * (attempt + 1))


def build_manifest() -> dict[str, object]:
    os.environ["AGENT_ARENA_STEP_LIMIT"] = "0"
    settings = RuntimeSettings.load()
    if settings.provider != "openai" or settings.agent != "react":
        raise RuntimeError("Effective provider or agent does not match the frozen experiment.")
    episodes: list[dict[str, object]] = []
    for (world, world_version), _factory in SCENARIO_REGISTRY.items():
        env = create_scenario_environment(world, world_version, seed=0)
        difficulty = world_version.split("-world-v3-", 1)[1].removesuffix("-zh")
        for seed in range(5):
            episodes.append({
                "attempt_id": f"{env.scenario_id}-seed-{seed}-attempt-01",
                "scenario_id": env.scenario_id,
                "world": world,
                "world_version": world_version,
                "difficulty": difficulty,
                "world_definition_sha256": env.identity[3],
                "seed": seed,
                "status": "planned",
                "outcome": None,
            })
    if len(episodes) != 150 or len({item["scenario_id"] for item in episodes}) != 30:
        raise RuntimeError("The frozen V3 selector matrix is not 30 x 5.")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    endpoint_host = urlsplit(settings.base_url).hostname if settings.base_url else None
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "in_progress",
        "created_at": now(),
        "source_commit": revision,
        "provider_probe": "passed; separate from the 150 episodes",
        "design": {
            "provider": settings.provider,
            "requested_model": settings.model_name,
            "endpoint_host": endpoint_host,
            "agent": "react",
            "prompt_version": "react_scenario_v3",
            "prompt_sha256": sha256(PROMPT_PATH),
            "world_families": 10,
            "difficulties": ["easy", "medium", "hard"],
            "selectors": 30,
            "seeds": [0, 1, 2, 3, 4],
            "planned_episode_attempts": 150,
            "episode_attempt_policy": "one attempt per selector and seed; no whole-episode reruns",
            "step_limit": 0,
            "step_limit_source": "AGENT_ARENA_STEP_LIMIT=0; CLI step-limit omitted",
            "runner_mode": "autonomous flag retained from superseded attempt: disables runtime feedback and stuck recovery",
            "episode_termination": "natural scenario terminal or provider/runner error; no action or wall-clock episode limit",
            "temperature": 0,
            "reasoning_effort": settings.reasoning_effort,
            "response_format": settings.response_format,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "provider_retry_count": settings.retry_count,
            "provider_max_output_tokens": settings.max_provider_output_tokens,
            "max_parallel_episodes": 21,
            "provider_session_id": "not recorded; kept in local configuration",
        },
        "episodes": episodes,
        "updated_at": now(),
    }


lock = threading.RLock()
manifest: dict[str, object]


def save_manifest() -> None:
    with lock:
        manifest["updated_at"] = now()
        atomic_json(MANIFEST_PATH, manifest)


def update_episode(attempt_id: str, **updates: object) -> None:
    with lock:
        records = manifest["episodes"]
        assert isinstance(records, list)
        for item in records:
            if item["attempt_id"] == attempt_id:
                item.update(updates)
                break
        else:
            raise KeyError(attempt_id)
        save_manifest()


def episode_directory(item: dict[str, object]) -> Path:
    subdirectory = item.get("output_subdir") or f"seed-{item['seed']}"
    return RUN_ROOT / str(item["scenario_id"]) / str(subdirectory)


def run_episode(item: dict[str, object]) -> dict[str, object]:
    out_dir = episode_directory(item)
    out_dir.mkdir(parents=True, exist_ok=True)
    update_episode(str(item["attempt_id"]), status="running", started_at=now())
    bootstrap = """
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
    command = [
        sys.executable, "-c", bootstrap, "run",
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
    env["OPENAI_MODEL"] = str(manifest["design"]["requested_model"])
    try:
        command[1:1] = ["-u"]
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True, encoding="utf-8", errors="replace",
        )
        last_progress_saved = 0
        provider_diagnostics: list[dict[str, object]] = []
        assert process.stdout is not None
        for line in process.stdout:
            match = re.search(r"正在请求第 (\d+)/不限 步", line)
            if match:
                decision_attempt = int(match.group(1))
                if decision_attempt - last_progress_saved >= 10:
                    update_episode(
                        str(item["attempt_id"]),
                        live_decision_attempt=decision_attempt,
                        progress_updated_at=now(),
                    )
                    last_progress_saved = decision_attempt
            if "SAFE_PROVIDER_DIAG:" in line:
                try:
                    diagnostic = json.loads(line.split("SAFE_PROVIDER_DIAG:", 1)[1].strip())
                    if isinstance(diagnostic, dict):
                        provider_diagnostics.append(diagnostic)
                except json.JSONDecodeError:
                    pass
        return_code = process.wait()
    except Exception as exc:
        details = {
            "status": "launch_error",
            "ended_at": now(),
            "error_type": type(exc).__name__,
            "error_note": str(exc)[:240],
        }
        update_episode(str(item["attempt_id"]), **details)
        return {"attempt_id": item["attempt_id"], **details}

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
                "trace_path": str(path.relative_to(ROOT)),
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
        updates = {**trace_meta, "status": status, "ended_at": now()}
        if provider_diagnostics:
            updates["provider_error_diagnostics"] = provider_diagnostics
        update_episode(str(item["attempt_id"]), **updates)
        return {"attempt_id": item["attempt_id"], **updates, "return_code": return_code}
    status = "cli_error" if return_code != 0 else "missing_or_invalid_trace"
    updates = {
        "status": status,
        "ended_at": now(),
        "return_code": return_code,
        "trace_count": len(trace_paths),
    }
    if provider_diagnostics:
        updates["provider_error_diagnostics"] = provider_diagnostics
    update_episode(str(item["attempt_id"]), **updates)
    return {"attempt_id": item["attempt_id"], **updates}


def write_summary() -> dict[str, object]:
    records = manifest["episodes"]
    assert isinstance(records, list)
    by_scenario: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_scenario[str(record["scenario_id"])].append(record)
    scenarios = []
    all_outcomes: Counter[str] = Counter()
    traces = 0
    successful = 0
    for scenario_id, items in sorted(by_scenario.items()):
        outcomes = Counter(
            str(item.get("outcome")) for item in items if item.get("outcome") is not None
        )
        all_outcomes.update(outcomes)
        traces += sum(1 for item in items if item.get("trace_path"))
        successes = outcomes.get("scenario_success", 0) + outcomes.get("success", 0)
        successful += successes
        terminal_outcomes = {"scenario_success", "success", "partial_success", "scenario_failure", "failure"}
        natural_terminal_steps = [
            int(item["executed_action_count"]) for item in items
            if item.get("outcome") in terminal_outcomes and isinstance(item.get("executed_action_count"), int)
        ]
        complete_success_steps = [
            int(item["executed_action_count"]) for item in items
            if item.get("outcome") in {"scenario_success", "success"}
            and isinstance(item.get("executed_action_count"), int)
        ]
        scenarios.append({
            "scenario_id": scenario_id,
            "world": items[0]["world"],
            "world_version": items[0]["world_version"],
            "attempts_planned": len(items),
            "traces_written": sum(1 for item in items if item.get("trace_path")),
            "complete_successes": successes,
            "mean_steps_to_natural_terminal": (sum(natural_terminal_steps) / len(natural_terminal_steps)) if natural_terminal_steps else None,
            "natural_terminal_episodes": len(natural_terminal_steps),
            "mean_steps_among_complete_successes": (sum(complete_success_steps) / len(complete_success_steps)) if complete_success_steps else None,
            "complete_success_step_counts": complete_success_steps,
            "outcomes": dict(sorted(outcomes.items())),
            "attempt_statuses": dict(sorted(Counter(str(item["status"]) for item in items).items())),
            "episode_ids": [item.get("episode_id") for item in items if item.get("episode_id")],
            "trace_paths": [item.get("trace_path") for item in items if item.get("trace_path")],
        })
    finished_attempts = sum(1 for item in records if item["status"] not in {"planned", "running"})
    is_complete = finished_attempts == len(records) and traces == len(records)
    natural_terminal_outcomes = {"scenario_success", "success", "partial_success", "scenario_failure", "failure"}
    natural_terminal_steps = [
        int(item["executed_action_count"]) for item in records
        if item.get("outcome") in natural_terminal_outcomes and isinstance(item.get("executed_action_count"), int)
    ]
    complete_success_steps = [
        int(item["executed_action_count"]) for item in records
        if item.get("outcome") in {"scenario_success", "success"}
        and isinstance(item.get("executed_action_count"), int)
    ]
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "status": "complete" if is_complete else "incomplete",
        "updated_at": now(),
        "planned_episode_attempts": len(records),
        "finished_attempts": finished_attempts,
        "traces_written": traces,
        "episode_step_limit": None,
        "natural_terminal_outcomes": sorted(natural_terminal_outcomes),
        "complete_successes": successful,
        "natural_terminal_episodes": len(natural_terminal_steps),
        "mean_steps_to_natural_terminal": (sum(natural_terminal_steps) / len(natural_terminal_steps)) if natural_terminal_steps else None,
        "complete_success_episodes_with_step_count": len(complete_success_steps),
        "mean_steps_among_complete_successes": (sum(complete_success_steps) / len(complete_success_steps)) if complete_success_steps else None,
        "median_steps_among_complete_successes": (sorted(complete_success_steps)[len(complete_success_steps) // 2] if len(complete_success_steps) % 2 else (sorted(complete_success_steps)[len(complete_success_steps) // 2 - 1] + sorted(complete_success_steps)[len(complete_success_steps) // 2]) / 2) if complete_success_steps else None,
        "complete_success_step_counts": complete_success_steps,
        "success_rate_over_all_planned_attempts": successful / len(records) if records else 0.0,
        "outcome_counts": dict(sorted(all_outcomes.items())),
        "attempt_status_counts": dict(sorted(Counter(str(item["status"]) for item in records).items())),
        "scenarios": scenarios,
    }
    atomic_json(SUMMARY_PATH, summary)
    manifest["status"] = summary["status"]
    save_manifest()
    return summary


def chunks(records: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [records[i:i + size] for i in range(0, len(records), size)]


def main() -> int:
    global manifest
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        records = manifest["episodes"]
        assert isinstance(records, list)
        for item in records:
            if item["status"] == "running":
                item["status"] = "interrupted"
                item["ended_at"] = now()
                item["interruption_note"] = "Process ended before an attempt result was recorded."
        manifest["status"] = "in_progress"
        save_manifest()
    else:
        manifest = build_manifest()
        save_manifest()

    records = manifest["episodes"]
    assert isinstance(records, list)
    if args.smoke_only:
        smoke = next(
            item for item in records
            if item["scenario_id"] == "SP-E" and item["seed"] == 0
        )
        if smoke["status"] == "planned":
            result = run_episode(smoke)
            write_summary()
            print(
                f"Smoke {smoke['scenario_id']} seed={smoke['seed']}: "
                f"status={result.get('status')} outcome={result.get('outcome')} "
                f"trace={result.get('trace_path')}",
                flush=True,
            )
        else:
            result = smoke
            print(
                f"Smoke already recorded: status={result.get('status')} "
                f"outcome={result.get('outcome')} trace={result.get('trace_path')}",
                flush=True,
            )
        return 0 if result.get("trace_identity_valid") and result.get("outcome") != "provider_error" else 2

    planned = [item for item in records if item["status"] == "planned"]
    completed_before = sum(1 for item in records if item["status"] not in {"planned", "running"})
    print(
        f"Starting {len(planned)} remaining episodes; "
        f"parallel limit=21; recorded attempts={completed_before}/150.",
        flush=True,
    )
    completed = completed_before
    queue = iter(planned)
    futures = {}
    with ThreadPoolExecutor(max_workers=21) as executor:
        for _ in range(min(21, len(planned))):
            item = next(queue, None)
            if item is not None:
                futures[executor.submit(run_episode, item)] = item
        while futures:
            future = next(as_completed(futures))
            item = futures.pop(future)
            result = future.result()
            completed += 1
            outcome = result.get("outcome") or result.get("status")
            print(
                f"[{completed}/150] {result['attempt_id']} outcome={outcome} "
                f"actions={result.get('executed_action_count', '-')} "
                f"status={result.get('status')}",
                flush=True,
            )
            write_summary()
            next_item = next(queue, None)
            if next_item is not None:
                futures[executor.submit(run_episode, next_item)] = next_item
    summary = write_summary()
    print(json.dumps({
        "status": summary["status"],
        "finished_attempts": summary["finished_attempts"],
        "traces_written": summary["traces_written"],
        "complete_successes": summary["complete_successes"],
        "outcome_counts": summary["outcome_counts"],
        "summary_path": str(SUMMARY_PATH.relative_to(ROOT)),
    }, ensure_ascii=False), flush=True)
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
