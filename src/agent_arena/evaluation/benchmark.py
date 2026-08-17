"""Local benchmark aggregation derived only from persisted episode traces."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

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


def row_from_trace(trace: EpisodeTrace, benchmark_id: str, episode_index: int) -> BenchmarkRow:
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
        input_tokens=sum(item.input_tokens or 0 for item in trace.steps) or None,
        output_tokens=sum(item.output_tokens or 0 for item in trace.steps) or None,
    )


def write_benchmark(rows: list[BenchmarkRow], output_dir: Path) -> tuple[Path, Path]:
    benchmark_id = rows[0].benchmark_id if rows else str(uuid4())
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{benchmark_id}.json"
    csv_path = output_dir / f"{benchmark_id}.csv"
    attempted = len(rows)
    succeeded = sum(row.outcome == EpisodeOutcome.SUCCESS.value for row in rows)
    payload = {
        "benchmark_id": benchmark_id,
        "rows": [row.__dict__ for row in rows],
        "aggregates": {
            "attempted": attempted,
            "succeeded": succeeded,
            "success_rate": succeeded / attempted if attempted else 0.0,
            "mean_steps": sum(row.steps for row in rows) / attempted if attempted else 0.0,
            "mean_latency_ms": sum(row.latency_ms for row in rows) / attempted
            if attempted
            else 0.0,
            "mean_invalid_output_count": (
                sum(row.invalid_output_count for row in rows) / attempted if attempted else 0.0
            ),
        },
    }
    _atomic_write(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_csv(csv_path, rows)
    return json_path, csv_path


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
