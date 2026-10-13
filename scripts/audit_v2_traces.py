"""Build a reproducible, public-field-only census of local episode traces.

The audit intentionally emits aggregate metrics and step numbers, never raw
decision text or runtime feedback. It deduplicates copied trace files by
episode_id, but keeps separate episodes as separate attempts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

TRACE_SUFFIX = ".json"
SETTING_FIELDS = (
    "step_limit",
    "runtime_feedback_enabled",
    "public_action_hints_enabled",
    "recent_history_enabled",
    "recent_history_window",
    "structured_milestones_enabled",
    "public_action_guard_enabled",
    "stuck_recovery_enabled",
    "concrete_action_candidates_enabled",
    "public_phase_context_enabled",
    "candidate_selection_enabled",
    "memory_schema_version",
    "planning_enabled",
)
CSV_FIELDS = (
    "episode_id",
    "source",
    "source_path",
    "experiment_bucket",
    "created_at",
    "world_version",
    "world_definition_id",
    "world_definition_hash",
    "seed_role",
    "effective_instance_signature",
    "configuration_signature",
    "recorded_attempt_index",
    "seed",
    "agent",
    "provider",
    "model",
    "prompt_version",
    "prompt_hash",
    "memory_renderer_version",
    "step_limit",
    "recent_history_window",
    "stuck_recovery_enabled",
    "public_phase_context_enabled",
    "public_action_guard_enabled",
    "memory_schema_version",
    "outcome",
    "recorded_action_count",
    "observed_action_steps",
    "input_tokens",
    "output_tokens",
    "planner_input_tokens",
    "planner_output_tokens",
    "planner_calls",
    "planner_latency_ms",
    "latency_ms",
    "memory_statistics_present",
    "memory_insertions",
    "memory_updates",
    "memory_invalidations",
    "memory_compactions",
    "memory_rendered_chars",
    "memory_estimated_tokens",
    "first_panel_opened_step",
    "first_power_restored_step",
    "first_code_read_step",
    "first_escape_step",
    "progress_observed_steps",
    "no_progress_actions",
    "state_progress_actions",
    "epistemic_progress_actions",
    "wrong_terminal_target_reads",
    "code_reads",
    "repeated_code_reads",
    "post_code_navigation_actions",
    "repeated_failed_action_attempts",
    "repeated_look_actions",
    "navigation_two_cycle_count",
    "first_wrong_terminal_step",
    "first_repeated_code_step",
    "first_failed_action_repeat_step",
    "first_navigation_cycle_end_step",
    "rejected_actions",
    "rejection_reason_counts",
    "rejection_reason_by_tool_counts",
)


def _sum_numeric(steps: list[dict[str, Any]], field: str) -> int | None:
    values = [step[field] for step in steps if isinstance(step.get(field), int)]
    return sum(values) if values else None


def _action_key(action: dict[str, Any], reason: str) -> str:
    encoded = json.dumps(action, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{encoded}|{reason}"


def audit_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Extract counts from an episode using only allowlisted public trace fields."""
    steps = [step for step in trace.get("steps", []) if isinstance(step, dict)]
    action_steps = [step for step in steps if isinstance(step.get("action"), dict)]
    code_read_steps: list[int] = []
    wrong_terminal_steps: list[int] = []
    post_code_navigation_steps: list[int] = []
    failed_action_counts: Counter[str] = Counter()
    rejection_reason_counts: Counter[str] = Counter()
    rejection_reason_by_tool_counts: Counter[str] = Counter()
    rejected_actions = 0
    failed_action_repeat_steps: list[int] = []
    look_rooms: Counter[str] = Counter()
    repeated_look_steps: list[int] = []
    progress_steps = 0
    no_progress = 0
    state_progress = 0
    epistemic_progress = 0
    room_path: list[str] = []
    navigation_cycle_end_steps: list[int] = []
    public_event_steps: dict[str, int] = {}
    memory_stats: list[dict[str, Any]] = []
    saw_code = False

    for index, step in enumerate(steps, start=1):
        step_memory_stats = step.get("memory_statistics")
        if isinstance(step_memory_stats, dict):
            memory_stats.append(step_memory_stats)
        action = step.get("action")
        if not isinstance(action, dict):
            continue
        result = step.get("result")
        result = result if isinstance(result, dict) else {}
        reason = result.get("reason")
        tool = action.get("tool")
        observation = step.get("observation")
        observation = observation if isinstance(observation, dict) else {}
        room = observation.get("current_room")
        if reason in {"panel_opened", "power_restored", "code_read", "escaped"}:
            public_event_steps.setdefault(str(reason), index)

        progress = step.get("progress")
        if isinstance(progress, dict):
            progress_steps += 1
            no_progress += progress.get("progress") is False
            state_progress += progress.get("state_progress") is True
            epistemic_progress += progress.get("epistemic_progress") is True

        if tool == "read_terminal" and reason == "wrong_target":
            wrong_terminal_steps.append(index)
        if tool == "read_terminal" and reason == "code_read":
            code_read_steps.append(index)
            saw_code = True
        elif saw_code and tool in {"move", "look"}:
            post_code_navigation_steps.append(index)

        if result.get("status") == "rejected":
            rejected_actions += 1
            rejection_reason_counts[str(reason)] += 1
            rejection_reason_by_tool_counts[f"{tool or 'unknown'}:{reason}"] += 1
            key = _action_key(action, str(reason))
            if failed_action_counts[key]:
                failed_action_repeat_steps.append(index)
            failed_action_counts[key] += 1

        if tool == "look" and isinstance(room, str):
            if look_rooms[room] and progress is not None and isinstance(progress, dict):
                if progress.get("progress") is False:
                    repeated_look_steps.append(index)
            look_rooms[room] += 1

        if tool == "move" and isinstance(room, str):
            destination = action.get("destination")
            if isinstance(destination, str):
                if not room_path:
                    room_path.append(room)
                elif room_path[-1] != room:
                    room_path.append(room)
                room_path.append(destination)
                if len(room_path) >= 4:
                    a, b, c, d = room_path[-4:]
                    if a == c and b == d and a != b:
                        navigation_cycle_end_steps.append(index)

    header = trace.get("provenance")
    provenance = header if isinstance(header, dict) else {}
    code_reads = len(code_read_steps)
    recorded_actions = trace.get("executed_action_count")
    if not isinstance(recorded_actions, int):
        recorded_actions = len(action_steps)
    final_memory_stats = memory_stats[-1] if memory_stats else {}

    return {
        "episode_id": str(trace.get("episode_id") or ""),
        "created_at": str(trace.get("created_at") or ""),
        "world_version": trace.get("world_version", "unavailable"),
        "world_definition_id": provenance.get("world_definition_id", "unavailable"),
        "world_definition_hash": provenance.get("world_definition_hash", "unavailable"),
        "seed": trace.get("seed", "unavailable"),
        "seed_role": (
            "seeded_instance"
            if "seeded" in str(trace.get("world_version", ""))
            else "replicate_id"
        ),
        "effective_instance_signature": "",
        "agent": trace.get("agent", "unavailable"),
        "provider": trace.get("provider", "unavailable"),
        "model": provenance.get("model_name", "unavailable"),
        "prompt_version": trace.get("prompt_version", "unavailable"),
        "prompt_hash": provenance.get("base_prompt_hash", "unavailable"),
        "memory_renderer_version": provenance.get("memory_renderer_version"),
        **{field: provenance.get(field) for field in SETTING_FIELDS},
        "settings": {field: provenance.get(field) for field in SETTING_FIELDS},
        "outcome": trace.get("outcome", "unavailable"),
        "recorded_action_count": recorded_actions,
        "observed_action_steps": len(action_steps),
        "input_tokens": _sum_numeric(steps, "input_tokens"),
        "output_tokens": _sum_numeric(steps, "output_tokens"),
        "planner_input_tokens": _sum_numeric(steps, "planner_input_tokens"),
        "planner_output_tokens": _sum_numeric(steps, "planner_output_tokens"),
        "planner_calls": sum(step.get("planner_called") is True for step in steps),
        "planner_latency_ms": _sum_numeric(steps, "planner_latency_ms"),
        "latency_ms": trace.get("latency_ms"),
        "memory_statistics_present": bool(memory_stats),
        "memory_insertions": final_memory_stats.get("insertions"),
        "memory_updates": final_memory_stats.get("updates"),
        "memory_invalidations": final_memory_stats.get("invalidations"),
        "memory_compactions": final_memory_stats.get("compactions"),
        "memory_rendered_chars": max(
            (
                value["rendered_chars"]
                for value in memory_stats
                if isinstance(value.get("rendered_chars"), int)
            ),
            default=None,
        ),
        "memory_estimated_tokens": max(
            (
                value["estimated_tokens"]
                for value in memory_stats
                if isinstance(value.get("estimated_tokens"), int)
            ),
            default=None,
        ),
        "first_panel_opened_step": public_event_steps.get("panel_opened", ""),
        "first_power_restored_step": public_event_steps.get("power_restored", ""),
        "first_code_read_step": public_event_steps.get("code_read", ""),
        "first_escape_step": public_event_steps.get("escaped", ""),
        "progress_observed_steps": progress_steps,
        "no_progress_actions": no_progress,
        "state_progress_actions": state_progress,
        "epistemic_progress_actions": epistemic_progress,
        "wrong_terminal_target_reads": len(wrong_terminal_steps),
        "code_reads": code_reads,
        "repeated_code_reads": max(0, code_reads - 1),
        "post_code_navigation_actions": len(post_code_navigation_steps),
        "repeated_failed_action_attempts": len(failed_action_repeat_steps),
        "repeated_look_actions": len(repeated_look_steps),
        "navigation_two_cycle_count": len(navigation_cycle_end_steps),
        "first_wrong_terminal_step": min(wrong_terminal_steps, default=""),
        "first_repeated_code_step": code_read_steps[1] if len(code_read_steps) > 1 else "",
        "first_failed_action_repeat_step": (
            min(failed_action_repeat_steps) if failed_action_repeat_steps else ""
        ),
        "first_navigation_cycle_end_step": (
            min(navigation_cycle_end_steps) if navigation_cycle_end_steps else ""
        ),
        "rejected_actions": rejected_actions,
        "rejection_reason_counts": dict(rejection_reason_counts),
        "rejection_reason_by_tool_counts": dict(rejection_reason_by_tool_counts),
    }


def _source_bucket(root_name: str, relative_path: Path) -> str:
    return relative_path.parts[0] if len(relative_path.parts) > 1 else f"{root_name}-root"


def _configuration_signature(row: dict[str, Any]) -> str:
    data = {
        key: row.get(key)
        for key in (
            "world_version",
            "world_definition_hash",
            "agent",
            "provider",
            "model",
            "prompt_version",
            "prompt_hash",
            "memory_renderer_version",
        )
    }
    data["settings"] = row.get("settings", {})
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def load_attempts(runs_dir: Path, results_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Load traces from both roots and deduplicate copied episodes by episode_id."""
    selected: dict[str, tuple[int, dict[str, Any], str, str]] = {}
    counters = Counter()
    roots = (("runs", runs_dir, 0), ("results", results_dir, 1))
    for source_name, root, priority in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob(f"episode_*{TRACE_SUFFIX}")):
            counters[f"{source_name}_files"] += 1
            try:
                raw = path.read_bytes()
                trace = json.loads(raw)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                counters["unreadable_files"] += 1
                continue
            if not isinstance(trace, dict) or not isinstance(trace.get("steps", []), list):
                counters["invalid_trace_files"] += 1
                continue
            row = audit_trace(trace)
            episode_id = row["episode_id"] or f"missing:{source_name}:{path.relative_to(root)}"
            row["episode_id"] = episode_id
            relative = path.relative_to(root)
            row["source"] = source_name
            row["source_path"] = relative.as_posix()
            row["experiment_bucket"] = _source_bucket(source_name, relative)
            world_version = str(row["world_version"])
            seed = str(row["seed"])
            instance_data = {
                "world_version": world_version,
                "world_definition_hash": row["world_definition_hash"],
                "seed": seed if row["seed_role"] == "seeded_instance" else None,
            }
            row["effective_instance_signature"] = hashlib.sha256(
                json.dumps(instance_data, sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
            row["_digest"] = hashlib.sha256(raw).hexdigest()
            row["configuration_signature"] = _configuration_signature(row)
            row["recorded_attempt_index"] = 0
            if episode_id in selected:
                counters["duplicate_files"] += 1
                previous = selected[episode_id]
                if row["_digest"] != previous[1]["_digest"]:
                    counters["conflicting_duplicate_ids"] += 1
                if priority < previous[0]:
                    selected[episode_id] = (priority, row, source_name, str(path))
            else:
                selected[episode_id] = (priority, row, source_name, str(path))

    rows = [value[1] for value in selected.values()]
    attempts: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["experiment_bucket"], row["configuration_signature"], str(row["seed"]))
        attempts[key].append(row)
    for group in attempts.values():
        group.sort(key=lambda row: (row["created_at"], row["source_path"]))
        for index, row in enumerate(group, start=1):
            row["recorded_attempt_index"] = index
    return sorted(rows, key=lambda row: (row["created_at"], row["source_path"])), dict(counters)


def _distribution(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"n": 0, "p50": None, "p90": None, "max": None}
    ordered = sorted(values)
    p90_index = max(0, int(0.9 * (len(ordered) - 1) + 0.5))
    return {"n": len(values), "p50": median(ordered), "p90": ordered[p90_index], "max": ordered[-1]}


def _success_at_k(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate offline cutoffs; provider errors and earlier step-limit censoring are excluded."""
    result: dict[str, Any] = {}
    for budget in (30, 60, 100, 150, 200):
        eligible = 0
        successes = 0
        provider_censored = 0
        step_limit_censored = 0
        for row in rows:
            outcome = row["outcome"]
            actions = row["recorded_action_count"]
            if outcome == "provider_error":
                provider_censored += 1
                continue
            if outcome == "step_limit":
                limit = row.get("step_limit")
                if isinstance(limit, int) and 0 < limit < budget:
                    step_limit_censored += 1
                    continue
            eligible += 1
            if outcome == "success" and isinstance(actions, int) and actions <= budget:
                successes += 1
        result[str(budget)] = {
            "successes": successes,
            "eligible": eligible,
            "rate": successes / eligible if eligible else None,
            "provider_error_censored": provider_censored,
            "step_limit_censored_before_budget": step_limit_censored,
        }
    return result


def summarize(rows: list[dict[str, Any]], counters: dict[str, int]) -> dict[str, Any]:
    outcomes = Counter(str(row["outcome"]) for row in rows)
    earliest = Counter(
        str(row["outcome"]) for row in rows if row["recorded_attempt_index"] == 1
    )
    success_steps = [
        row["recorded_action_count"]
        for row in rows
        if row["outcome"] == "success" and isinstance(row["recorded_action_count"], int)
    ]
    metric_totals = {
        field: sum(int(row[field] or 0) for row in rows)
        for field in (
            "wrong_terminal_target_reads",
            "code_reads",
            "repeated_code_reads",
            "post_code_navigation_actions",
            "repeated_failed_action_attempts",
            "repeated_look_actions",
            "navigation_two_cycle_count",
            "no_progress_actions",
            "progress_observed_steps",
        )
    }
    rejection_reason_totals: Counter[str] = Counter()
    rejection_reason_by_tool_totals: Counter[str] = Counter()
    for row in rows:
        rejection_reason_totals.update(row["rejection_reason_counts"])
        rejection_reason_by_tool_totals.update(row["rejection_reason_by_tool_counts"])
    bucket_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket_groups[
            (row["experiment_bucket"], str(row["world_version"]), row["configuration_signature"])
        ].append(row)
    grouped = []
    for (bucket, world_version, signature), group in sorted(bucket_groups.items()):
        success_counts = [
            row["recorded_action_count"]
            for row in group
            if row["outcome"] == "success" and isinstance(row["recorded_action_count"], int)
        ]
        grouped.append(
            {
                "experiment_bucket": bucket,
                "world_version": world_version,
                "configuration_signature": signature,
                "attempts": len(group),
                "outcomes": dict(Counter(str(row["outcome"]) for row in group)),
                "memory_statistics_episodes": sum(
                    row["memory_statistics_present"] is True for row in group
                ),
                "offline_success_at_k_all_recorded_attempts": _success_at_k(group),
                "offline_success_at_k_earliest_recorded_per_seed": _success_at_k(
                    [row for row in group if row["recorded_attempt_index"] == 1]
                ),
                "successful_action_counts": _distribution(success_counts),
                "wrong_terminal_target_reads": sum(
                    row["wrong_terminal_target_reads"] for row in group
                ),
                "repeated_code_reads": sum(row["repeated_code_reads"] for row in group),
                "repeated_failed_action_attempts": sum(
                    row["repeated_failed_action_attempts"] for row in group
                ),
                "navigation_two_cycle_count": sum(
                    row["navigation_two_cycle_count"] for row in group
                ),
            }
        )
    return {
        "schema_version": 1,
        "trace_files": counters.get("runs_files", 0) + counters.get("results_files", 0),
        "unique_episode_ids": len(rows),
        "memory_schema_versions": dict(
            Counter(str(row["memory_schema_version"]) for row in rows)
        ),
        "memory_statistics_episodes": sum(
            row["memory_statistics_present"] is True for row in rows
        ),
        "deduplicated_copies": counters.get("duplicate_files", 0),
        "conflicting_duplicate_ids": counters.get("conflicting_duplicate_ids", 0),
        "unreadable_files": counters.get("unreadable_files", 0),
        "invalid_trace_files": counters.get("invalid_trace_files", 0),
        "outcomes_all_attempts": dict(outcomes),
        "earliest_recorded_per_condition_and_seed": dict(earliest),
        "earliest_recorded_is_not_verified_first_attempt": True,
        "successful_action_count_distribution": _distribution(success_steps),
        "public_step_metric_totals": metric_totals,
        "rejection_reason_totals": dict(rejection_reason_totals),
        "rejection_reason_by_tool_totals": dict(rejection_reason_by_tool_totals),
        "condition_groups": grouped,
        "limitations": [
            "episode_id 仅用于去除同一 Trace 的文件副本；不同 episode_id 均保留为单独尝试。",
            (
                "recorded_attempt_index 按实验目录、配置签名和 seed 的 created_at 排序；"
                "缺少 run-attempt ID 时只能称最早记录，不能确认首次调用。"
            ),
            (
                "动作重复、无进展与导航二循环是公开 Trace 上的操作性代理指标，"
                "不自动证明反事实可避免或事实遗忘。"
            ),
            (
                "当前 Trace 契约没有独立 instance_hash；seeded 世界用 world_version、"
                "definition_hash、seed 作为临时实例签名，不能视为环境内容哈希。"
            ),
        ],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            output_row = dict(row)
            output_row["rejection_reason_counts"] = json.dumps(
                row["rejection_reason_counts"], ensure_ascii=False, sort_keys=True
            )
            output_row["rejection_reason_by_tool_counts"] = json.dumps(
                row["rejection_reason_by_tool_counts"], ensure_ascii=False, sort_keys=True
            )
            writer.writerow(output_row)


def main() -> None:
    parser = argparse.ArgumentParser(description="离线审计 runs/ 与 results/ 中的 Trace")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--csv-output", type=Path, default=Path("docs/research/v2/assets/trace-audit.csv")
    )
    parser.add_argument(
        "--summary-output", type=Path, default=Path("docs/research/v2/assets/trace-audit.json")
    )
    args = parser.parse_args()
    rows, counters = load_attempts(args.runs_dir, args.results_dir)
    summary = summarize(rows, counters)
    _write_csv(args.csv_output, rows)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"audited {summary['unique_episode_ids']} unique episodes from "
        f"{summary['trace_files']} files; copied files deduplicated: "
        f"{summary['deduplicated_copies']}"
    )


if __name__ == "__main__":
    main()
