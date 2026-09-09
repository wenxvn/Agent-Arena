"""Local benchmark aggregation derived only from persisted episode traces."""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from agent_arena.arena import ToolReason, ToolStatus
from agent_arena.evaluation.loop import public_state_key
from agent_arena.evaluation.trace import EpisodeOutcome, EpisodeTrace


@dataclass(frozen=True)
class BenchmarkRow:
    benchmark_id: str
    episode_id: str
    episode_index: int
    world_version: str
    seed: int
    agent: str
    provider: str
    outcome: str
    steps: int
    invalid_output_count: int
    rejected_action_count: int
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    condition_id: str
    condition_json: str
    repeated_action_ratio: float
    max_consecutive_look: int
    unique_public_states: int
    tools_collected: bool
    panel_opened: bool
    power_restored: bool
    code_read: bool
    escaped: bool
    guidance_comparable_count: int
    guidance_deviation_count: int
    guidance_deviation_rate: float | None
    planner_call_count: int
    replan_count: int
    generated_subgoal_count: int
    completed_subgoal_count: int
    subgoal_completion_rate: float | None
    mean_actions_per_subgoal: float | None
    no_progress_action_count: int
    repeated_failure_count: int
    planner_latency_ms: int
    executor_latency_ms: int
    planner_input_tokens: int | None
    planner_output_tokens: int | None
    executor_input_tokens: int | None
    executor_output_tokens: int | None
    planner_tokens: int | None
    executor_tokens: int | None
    total_tokens: int | None


def row_from_trace(trace: EpisodeTrace, benchmark_id: str, episode_index: int) -> BenchmarkRow:
    executed = [step for step in trace.steps if step.action is not None and step.result is not None]
    action_keys = [step.action.model_dump_json() for step in executed if step.action is not None]
    repeated = len(action_keys) - len(set(action_keys))
    consecutive = maximum = 0
    states: set[str] = set()
    reasons: set[ToolReason] = set()
    tools_collected = False
    for step in trace.steps:
        for observation in (step.observation, step.next_observation):
            if observation is not None:
                states.add(public_state_key(observation))
                tools_collected |= {"screwdriver", "replacement_fuse"} <= set(observation.inventory)
        if step.result is not None and step.result.status is ToolStatus.SUCCESS:
            reasons.add(step.result.reason)
        if step.action is not None and step.result is not None:
            consecutive = consecutive + 1 if step.action.tool == "look" else 0
            maximum = max(maximum, consecutive)
    comparable = [
        step
        for step in trace.steps
        if step.suggested_action is not None and step.action is not None
    ]
    deviations = sum(step.action != step.suggested_action for step in comparable)
    planner_calls = sum(step.planner_called for step in executed)
    completed_subgoals = sum(step.subgoal_completed for step in executed)
    planner_latency = sum(step.planner_latency_ms or 0 for step in executed)
    executor_latency = sum(step.executor_latency_ms or 0 for step in executed)
    planner_input_tokens = sum(
        step.planner_input_tokens or 0
        for step in executed
        if step.planner_input_tokens is not None
    )
    planner_output_tokens = sum(
        step.planner_output_tokens or 0
        for step in executed
        if step.planner_output_tokens is not None
    )
    executor_input_tokens = sum(
        step.executor_input_tokens or 0
        for step in executed
        if step.executor_input_tokens is not None
    )
    executor_output_tokens = sum(
        step.executor_output_tokens or 0
        for step in executed
        if step.executor_output_tokens is not None
    )
    total_input_tokens = sum(item.input_tokens or 0 for item in trace.steps)
    total_output_tokens = sum(item.output_tokens or 0 for item in trace.steps)
    condition = {
        "world_version": trace.world_version,
        "agent": trace.agent,
        "prompt_version": trace.prompt_version,
        "provider": trace.provider,
        "provenance": trace.provenance.model_dump(mode="json"),
    }
    # Legacy traces do not prove actual world/config identity; do not pool them.
    if trace.provenance.trace_contract_version == "legacy":
        condition["legacy_episode_id"] = str(trace.episode_id)
    condition_json = json.dumps(condition, ensure_ascii=False, sort_keys=True)
    return BenchmarkRow(
        benchmark_id=benchmark_id,
        episode_id=str(trace.episode_id),
        episode_index=episode_index,
        world_version=trace.world_version,
        seed=trace.seed,
        agent=trace.agent,
        provider=trace.provider,
        outcome=trace.outcome.value,
        steps=trace.executed_action_count,
        invalid_output_count=trace.invalid_output_count,
        rejected_action_count=trace.rejected_action_count,
        latency_ms=trace.latency_ms,
        input_tokens=total_input_tokens or None,
        output_tokens=total_output_tokens or None,
        condition_id=sha256(condition_json.encode("utf-8")).hexdigest(),
        condition_json=condition_json,
        repeated_action_ratio=repeated / len(executed) if executed else 0.0,
        max_consecutive_look=maximum,
        unique_public_states=len(states),
        tools_collected=tools_collected,
        panel_opened=ToolReason.PANEL_OPENED in reasons,
        power_restored=ToolReason.POWER_RESTORED in reasons,
        code_read=ToolReason.CODE_READ in reasons,
        escaped=ToolReason.ESCAPED in reasons,
        guidance_comparable_count=len(comparable),
        guidance_deviation_count=deviations,
        guidance_deviation_rate=deviations / len(comparable) if comparable else None,
        planner_call_count=planner_calls,
        replan_count=max(0, planner_calls - 1),
        generated_subgoal_count=planner_calls,
        completed_subgoal_count=completed_subgoals,
        subgoal_completion_rate=completed_subgoals / planner_calls if planner_calls else None,
        mean_actions_per_subgoal=(
            trace.executed_action_count / planner_calls if planner_calls else None
        ),
        no_progress_action_count=sum(step.plan_signal == "no_progress" for step in executed),
        repeated_failure_count=sum(step.plan_signal == "repeated_failure" for step in executed),
        planner_latency_ms=planner_latency,
        executor_latency_ms=executor_latency,
        planner_input_tokens=planner_input_tokens or None,
        planner_output_tokens=planner_output_tokens or None,
        executor_input_tokens=executor_input_tokens or None,
        executor_output_tokens=executor_output_tokens or None,
        planner_tokens=(
            planner_input_tokens + planner_output_tokens
            if planner_input_tokens or planner_output_tokens
            else None
        ),
        executor_tokens=(
            executor_input_tokens + executor_output_tokens
            if executor_input_tokens or executor_output_tokens
            else None
        ),
        total_tokens=(total_input_tokens + total_output_tokens)
        if total_input_tokens or total_output_tokens
        else None,
    )


def write_benchmark(rows: list[BenchmarkRow], output_dir: Path) -> tuple[Path, Path]:
    benchmark_id = rows[0].benchmark_id if rows else str(uuid4())
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    agents = "-".join(dict.fromkeys(row.agent for row in rows)) or "none"
    seed_count = len({row.seed for row in rows})
    short_id = benchmark_id.split("-", maxsplit=1)[0]
    stem = f"benchmark_{timestamp}_{agents}_{seed_count}-seeds_{len(rows)}-episodes_{short_id}"
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    groups: dict[str, list[BenchmarkRow]] = {}
    for row in rows:
        groups.setdefault(row.condition_id, []).append(row)
    payload = {
        "schema_version": "benchmark_v3",
        "benchmark_id": benchmark_id,
        "rows": [row.__dict__ for row in rows],
        "totals": {"attempted": len(rows)},
        "conditions": {
            key: {
                "configuration": json.loads(group[0].condition_json),
                "aggregates": _aggregate(group),
            }
            for key, group in groups.items()
        },
        # A mixed experiment has no meaningful single success rate.
        "aggregates": _aggregate(rows) if len(groups) == 1 else None,
    }
    _atomic_write(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_csv(csv_path, rows)
    return json_path, csv_path


def _aggregate(rows: list[BenchmarkRow]) -> dict[str, object]:
    attempted = len(rows)
    succeeded = sum(row.outcome == EpisodeOutcome.SUCCESS.value for row in rows)
    comparable = sum(row.guidance_comparable_count for row in rows)
    deviations = sum(row.guidance_deviation_count for row in rows)
    deviating_episodes = [row for row in rows if row.guidance_deviation_count > 0]
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "success_rate": succeeded / attempted,
        "mean_steps": sum(row.steps for row in rows) / attempted,
        "mean_latency_ms": sum(row.latency_ms for row in rows) / attempted,
        "mean_invalid_output_count": sum(row.invalid_output_count for row in rows) / attempted,
        "mean_repeated_action_ratio": sum(row.repeated_action_ratio for row in rows) / attempted,
        "mean_max_consecutive_look": sum(row.max_consecutive_look for row in rows) / attempted,
        "mean_unique_public_states": sum(row.unique_public_states for row in rows) / attempted,
        "mean_planner_call_count": sum(row.planner_call_count for row in rows) / attempted,
        "mean_replan_count": sum(row.replan_count for row in rows) / attempted,
        "mean_subgoal_completion_rate": _mean_optional(
            row.subgoal_completion_rate for row in rows
        ),
        "mean_actions_per_subgoal": _mean_optional(row.mean_actions_per_subgoal for row in rows),
        "mean_no_progress_action_count": sum(row.no_progress_action_count for row in rows)
        / attempted,
        "mean_repeated_failure_count": sum(row.repeated_failure_count for row in rows) / attempted,
        "mean_planner_latency_ms": sum(row.planner_latency_ms for row in rows) / attempted,
        "mean_executor_latency_ms": sum(row.executor_latency_ms for row in rows) / attempted,
        "total_planner_latency_ms": sum(row.planner_latency_ms for row in rows),
        "total_executor_latency_ms": sum(row.executor_latency_ms for row in rows),
        "planner_input_tokens": _sum_optional(row.planner_input_tokens for row in rows),
        "planner_output_tokens": _sum_optional(row.planner_output_tokens for row in rows),
        "executor_input_tokens": _sum_optional(row.executor_input_tokens for row in rows),
        "executor_output_tokens": _sum_optional(row.executor_output_tokens for row in rows),
        "planner_tokens": _sum_optional(row.planner_tokens for row in rows),
        "executor_tokens": _sum_optional(row.executor_tokens for row in rows),
        "total_tokens": _sum_optional(row.total_tokens for row in rows),
        "stage_completion_rates": {
            stage: sum(bool(getattr(row, stage)) for row in rows) / attempted
            for stage in (
                "tools_collected",
                "panel_opened",
                "power_restored",
                "code_read",
                "escaped",
            )
        },
        "guidance_comparable_count": comparable,
        "guidance_deviation_count": deviations,
        "guidance_deviation_rate": deviations / comparable if comparable else None,
        "deviating_episode_count": len(deviating_episodes),
        "success_rate_after_guidance_deviation": (
            sum(row.outcome == EpisodeOutcome.SUCCESS.value for row in deviating_episodes)
            / len(deviating_episodes)
            if deviating_episodes
            else None
        ),
    }


def _mean_optional(values: Iterable[object]) -> float | None:
    numbers = [value for value in values if isinstance(value, (int, float))]
    return sum(numbers) / len(numbers) if numbers else None


def _sum_optional(values: Iterable[object]) -> int | None:
    numbers = [value for value in values if isinstance(value, int)]
    return sum(numbers) if numbers else None


def _atomic_write(destination: Path, contents: str) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(contents)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise


def _atomic_write_csv(destination: Path, rows: list[BenchmarkRow]) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(temporary_file, fieldnames=list(BenchmarkRow.__annotations__))
            writer.writeheader()
            writer.writerows(row.__dict__ for row in rows)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise
