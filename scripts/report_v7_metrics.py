"""Recompute V7 metrics for existing episode traces, fully offline.

Accepts one or more episode directories (containing ``agent_trace.jsonl`` and an
optional ``judge_metrics.json``) or a parent directory to scan recursively. The
script reads traces, runs the registered extractors, and prints one table per
episode. It never starts an environment, calls a provider, or writes a ledger.

Maps whose V7 metrics are design-only are reported as such and skipped: the
script does not fabricate zeros for them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v7.metrics import registry  # noqa: E402
from agent_arena.v7.metrics.schema import (  # noqa: E402
    MetricStatus,
    TraceFormatError,
    load_trace,
)

TRACE_NAME = "agent_trace.jsonl"
JUDGE_NAME = "judge_metrics.json"


def _discover(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(path.rglob(TRACE_NAME)))
        elif path.name == TRACE_NAME:
            found.append(path)
        else:
            raise SystemExit(f"Not an episode directory or trace file: {path}")
    unique: list[Path] = []
    seen: set[Path] = set()
    for item in found:
        resolved = item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(item)
    return unique


def _render_value(value: Any, status: MetricStatus) -> str:
    if status is not MetricStatus.VALID:
        return status.value
    if isinstance(value, float):
        return f"{value:.6g}"
    return "-" if value is None else str(value)


def _episode_payload(trace_path: Path) -> dict[str, Any]:
    judge_path = trace_path.with_name(JUDGE_NAME)
    record = load_trace(trace_path, judge_path=judge_path if judge_path.exists() else None)
    map_id = record.map_id
    if map_id not in registry.implemented_map_ids():
        return {
            "trace": str(trace_path),
            "map_id": map_id,
            "instance_id": record.instance_id,
            "condition_id": record.condition_id,
            "seed": record.seed,
            "status": "design_only",
            "metrics": [],
            "note": "该图的 V7 指标尚未实现 extractor；不生成替代分数。",
        }
    values = registry.compute_metrics(record)
    metrics = []
    for spec in registry.specs_for(map_id):
        value = values[spec.metric_id]
        metrics.append(
            {
                "metric_id": spec.metric_id,
                "kind": spec.kind.value,
                "construct_name": spec.construct_name,
                "unit": spec.unit,
                "direction": spec.direction.value,
                "value": value.value,
                "status": value.status.value,
                "denominator": value.denominator,
                "note": value.note,
            }
        )
    return {
        "trace": str(trace_path),
        "map_id": map_id,
        "instance_id": record.instance_id,
        "condition_id": record.condition_id,
        "seed": record.seed,
        "provider": record.header.get("provider"),
        "model": record.header.get("model"),
        "status": "computed",
        "metrics": metrics,
    }


def _print_episode(payload: dict[str, Any]) -> None:
    header = (
        f"{payload['map_id']} | {payload['instance_id']} | "
        f"{payload['condition_id']} | seed={payload['seed']}"
    )
    print(header)
    if payload["status"] == "design_only":
        print(f"  design_only: {payload['note']}")
        return
    for metric in payload["metrics"]:
        rendered = _render_value(metric["value"], MetricStatus(metric["status"]))
        note = f"  ({metric['note']})" if metric["note"] else ""
        print(f"  {metric['metric_id']:<40} {metric['kind']:<10} {rendered:<14}{note}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="episode dirs or agent_trace.jsonl")
    parser.add_argument("--json", type=Path, default=None, help="write machine-readable results")
    args = parser.parse_args()

    traces = _discover(args.paths)
    if not traces:
        raise SystemExit("No agent_trace.jsonl found.")

    payloads: list[dict[str, Any]] = []
    invalid = 0
    for trace_path in traces:
        try:
            payload = _episode_payload(trace_path)
        except TraceFormatError as exc:
            invalid += 1
            payload = {
                "trace": str(trace_path),
                "map_id": "",
                "instance_id": "",
                "condition_id": "",
                "seed": 0,
                "status": "invalid_trace",
                "metrics": [],
                "note": str(exc),
            }
        payloads.append(payload)
        _print_episode(payload)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"episodes": payloads}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.json}")

    print(
        f"processed {len(payloads)} trace(s): "
        f"{sum(1 for item in payloads if item['status'] == 'computed')} computed, "
        f"{sum(1 for item in payloads if item['status'] == 'design_only')} design_only, "
        f"{invalid} invalid_trace."
    )


if __name__ == "__main__":
    main()
