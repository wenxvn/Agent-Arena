from __future__ import annotations

import json
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RESULT_DIR))
import run_matrix as runner


def load_manifest() -> dict[str, object]:
    return json.loads(runner.MANIFEST_PATH.read_text(encoding="utf-8"))


def active_processes(records: list[dict[str, object]]) -> dict[str, psutil.Process]:
    expected = {
        str(runner.episode_directory(item).resolve()).casefold(): item
        for item in records
        if item["status"] == "running"
    }
    adopted: dict[str, psutil.Process] = {}
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            if not str(process.info.get("name", "")).lower().startswith("python"):
                continue
            args = process.info.get("cmdline") or []
            if "agent_arena.cli" not in " ".join(args) or "--output-dir" not in args:
                continue
            path = str(Path(args[args.index("--output-dir") + 1]).resolve()).casefold()
            item = expected.get(path)
            if item is not None:
                adopted[str(item["attempt_id"])] = process
        except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
            continue
    return adopted


def finalize_existing(item: dict[str, object], process: psutil.Process) -> dict[str, object]:
    try:
        return_code = process.wait()
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        updates = {
            "status": "interrupted",
            "ended_at": runner.now(),
            "interruption_note": f"Pipeline could not monitor the existing process: {type(exc).__name__}.",
        }
        runner.update_episode(str(item["attempt_id"]), **updates)
        return {"attempt_id": item["attempt_id"], **updates}

    out_dir = runner.episode_directory(item)
    traces = sorted(out_dir.glob("episode_*.json"))
    trace_meta: dict[str, object] | None = None
    if len(traces) == 1:
        trace_path = traces[0]
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            identity_ok = (
                trace.get("world_version") == item["world_version"]
                and trace.get("seed") == item["seed"]
                and trace.get("scenario_id") == item["scenario_id"]
            )
            trace_meta = {
                "trace_path": str(trace_path.relative_to(ROOT)),
                "trace_sha256": runner.sha256(trace_path),
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
        updates = {
            **trace_meta,
            "status": status,
            "ended_at": runner.now(),
            "return_code": return_code,
        }
    else:
        updates = {
            "status": "cli_error" if return_code not in (None, 0) else "missing_or_invalid_trace",
            "ended_at": runner.now(),
            "return_code": return_code,
            "trace_count": len(traces),
            **(trace_meta or {}),
        }
    runner.update_episode(str(item["attempt_id"]), **updates)
    return {"attempt_id": item["attempt_id"], **updates}


def append_infrastructure_retries(records: list[dict[str, object]]) -> None:
    existing_ids = {str(item["attempt_id"]) for item in records}
    for item in list(records):
        if item["status"] != "launch_error" or item.get("trace_path"):
            continue
        if item.get("error_type") != "PermissionError":
            continue
        retry_id = str(item["attempt_id"]).removesuffix("attempt-01") + "attempt-02"
        if retry_id in existing_ids:
            continue
        retry = {
            key: value
            for key, value in item.items()
            if key not in {
                "status", "outcome", "error_type", "error_note", "ended_at",
                "started_at", "trace_path", "trace_sha256", "trace_identity_valid",
                "episode_id", "created_at", "executed_action_count", "live_decision_attempt",
                "progress_updated_at", "return_code", "trace_count",
            }
        }
        retry.update({
            "attempt_id": retry_id,
            "status": "planned",
            "outcome": None,
            "retry_of": str(item["attempt_id"]),
            "retry_reason": "Preserve PermissionError attempt and obtain one trace for this seed.",
            "output_subdir": f"seed-{item['seed']}-attempt-02",
        })
        records.append(retry)
        existing_ids.add(retry_id)
        print(f"Queued infrastructure recovery: {retry_id}", flush=True)


def main() -> int:
    manifest = load_manifest()
    runner.manifest = manifest
    records = manifest["episodes"]
    assert isinstance(records, list)

    adopted = active_processes(records)
    adopted_ids = set(adopted)
    for item in records:
        if item["status"] == "running" and str(item["attempt_id"]) not in adopted_ids:
            item["status"] = "interrupted"
            item["ended_at"] = runner.now()
            item["interruption_note"] = "No active episode process existed when the pipeline started."

    append_infrastructure_retries(records)
    design = manifest["design"]
    assert isinstance(design, dict)
    design["planned_episode_attempts"] = len(records)
    design["episode_attempt_policy"] = (
        "Five target seeds per selector; infrastructure failures are preserved and retried as separate attempts."
    )
    design["max_parallel_episodes"] = 21
    manifest["status"] = "in_progress"
    runner.save_manifest()

    queue = iter(item for item in records if item["status"] == "planned")
    futures: dict[Future[dict[str, object]], dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=21) as executor:
        for attempt_id, process in adopted.items():
            item = next(item for item in records if item["attempt_id"] == attempt_id)
            futures[executor.submit(finalize_existing, item, process)] = item
        for _ in range(max(0, 21 - len(futures))):
            item = next(queue, None)
            if item is None:
                break
            futures[executor.submit(runner.run_episode, item)] = item

        initial_count = sum(1 for item in records if item["status"] not in {"planned", "running"})
        print(
            f"Pipeline active: adopted={len(adopted)}, queued={sum(1 for item in records if item['status'] == 'planned')}, "
            f"parallel_limit=21, already_recorded={initial_count}/{len(records)}.",
            flush=True,
        )
        finished = initial_count
        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                item = futures.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    updates = {
                        "status": "launch_error",
                        "ended_at": runner.now(),
                        "error_type": type(exc).__name__,
                        "error_note": str(exc)[:240],
                    }
                    runner.update_episode(str(item["attempt_id"]), **updates)
                    result = {"attempt_id": item["attempt_id"], **updates}
                finished += 1
                print(
                    f"[{finished}/{len(records)}] {result['attempt_id']} "
                    f"outcome={result.get('outcome') or result.get('status')} "
                    f"actions={result.get('executed_action_count', '-')} status={result.get('status')}",
                    flush=True,
                )
                runner.write_summary()
                next_item = next(queue, None)
                if next_item is not None:
                    futures[executor.submit(runner.run_episode, next_item)] = next_item

    summary = runner.write_summary()
    # Completion means every one of the 150 selector/seed pairs has a valid trace.
    valid_cases = {
        (str(item["scenario_id"]), int(item["seed"]))
        for item in records
        if item.get("trace_identity_valid") and item.get("trace_path")
    }
    all_cases = {
        (str(item["scenario_id"]), int(item["seed"]))
        for item in records
        if str(item["attempt_id"]).endswith("attempt-01")
    }
    coverage_complete = len(all_cases) == 150 and all_cases <= valid_cases
    if coverage_complete:
        summary["status"] = "complete"
        summary["unique_selector_seed_cases"] = len(all_cases)
        summary["valid_selector_seed_cases"] = len(all_cases & valid_cases)
        runner.atomic_json(runner.SUMMARY_PATH, summary)
        manifest["status"] = "complete"
        runner.save_manifest()
    print(
        json.dumps({
            "status": summary["status"],
            "finished_attempts": summary["finished_attempts"],
            "traces_written": summary["traces_written"],
            "unique_selector_seed_cases": len(all_cases),
            "valid_selector_seed_cases": len(all_cases & valid_cases),
            "complete_successes": summary["complete_successes"],
            "outcome_counts": summary["outcome_counts"],
            "summary_path": str(runner.SUMMARY_PATH.relative_to(ROOT)),
        }, ensure_ascii=False),
        flush=True,
    )
    return 0 if coverage_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
