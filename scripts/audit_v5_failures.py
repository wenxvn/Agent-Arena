"""Offline audit of the committed V5 six-map pilot artifacts.

This script is read-only. It never creates a provider and never mutates a ledger.
It reads whatever local `runs/v5` artifacts are present and, when the raw traces
are absent, reports `trace_unavailable` instead of inventing replacement values.

Usage:
    python scripts/audit_v5_failures.py                 # audit the newest experiment
    python scripts/audit_v5_failures.py --out docs/v6/v5-failure-audit.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "runs" / "v5" / "experiments"

# Action results that indicate the model issued a legal tool the environment did
# not service (interface mismatch), as opposed to a schema rejection.
_INTERFACE_RESULTS = {"ACTION_NOT_AVAILABLE", "ACTION_DISABLED"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _latest_experiment(runs_dir: Path) -> Path | None:
    if not runs_dir.is_dir():
        return None
    candidates = [
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and (path / "episodes").is_dir()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "episodes").stat().st_mtime)


def _censor_bucket(episode: dict[str, Any]) -> str:
    status = episode.get("status")
    v4_status = episode.get("v4_status")
    if status == "success":
        return "success"
    if v4_status == "step_limit_reached":
        return "censored_step_limit"
    if status in {"decision_limit", "censored"}:
        return "censored_decision_limit"
    if status in {"episode_timeout", "global_provider_timeout"}:
        return "censored_wall_clock"
    if status in {"provider_error", "provider_error_limit", "unknown_provider_spend"}:
        return "provider_error"
    if status == "input_context_limit":
        return "input_context_limit"
    if v4_status == "scenario_failure":
        return "rule_outcome_failure"
    return "incomplete"


def _episode_summary(episode_dir: Path) -> dict[str, Any]:
    judge = json.loads((episode_dir / "judge_metrics.json").read_text(encoding="utf-8"))
    trace_path = episode_dir / "agent_trace.jsonl"
    interface_counts: Counter[str] = Counter()
    invalid_reason_counts: Counter[str] = Counter()
    if trace_path.is_file():
        for row in _read_jsonl(trace_path):
            if row.get("event") != "decision":
                continue
            result = row.get("result")
            if isinstance(result, str) and result in _INTERFACE_RESULTS:
                interface_counts[result] += 1
            reason = row.get("invalid_output_reason")
            if reason:
                invalid_reason_counts[str(reason)] += 1
    return {
        "episode_id": judge.get("episode_id"),
        "map_id": judge.get("map_id"),
        "condition_id": judge.get("condition_id"),
        "seed": judge.get("seed"),
        "status": judge.get("status"),
        "v4_status": judge.get("v4_status"),
        "censor_bucket": _censor_bucket(judge),
        "decision_count": judge.get("decision_count"),
        "failure_codes": [item["code"] for item in judge.get("failure_classifications", [])],
        "interface_result_counts": dict(interface_counts),
        "invalid_output_reason_counts": dict(invalid_reason_counts),
        "metrics": judge.get("metrics", {}),
        "trace_available": trace_path.is_file(),
    }


def _aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for episode in episodes:
        key = f"{episode['map_id']}::{episode['condition_id']}"
        grouped.setdefault(key, []).append(episode)
    summary: dict[str, Any] = {}
    for key, group in sorted(grouped.items()):
        buckets = Counter(episode["censor_bucket"] for episode in group)
        codes = Counter(code for episode in group for code in episode["failure_codes"])
        interface = Counter(
            name
            for episode in group
            for name, count in episode["interface_result_counts"].items()
            for _ in range(count)
        )
        summary[key] = {
            "episodes": len(group),
            "success": buckets.get("success", 0),
            "censor_buckets": dict(buckets),
            "failure_codes": dict(codes),
            "interface_result_counts": dict(interface),
        }
    return summary


def _flag_interface_anomalies(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for episode in episodes:
        interface_total = sum(episode["interface_result_counts"].values())
        if interface_total and interface_total >= max(3, (episode["decision_count"] or 0) // 3):
            flags.append(
                {
                    "episode_id": episode["episode_id"],
                    "map_id": episode["map_id"],
                    "condition_id": episode["condition_id"],
                    "interface_result_counts": episode["interface_result_counts"],
                    "decision_count": episode["decision_count"],
                    "censor_bucket": episode["censor_bucket"],
                    "interpretation": (
                        "A large share of decisions returned an interface code rather than a "
                        "rule outcome; this episode cannot support a capability claim."
                    ),
                }
            )
    return flags


def audit(runs_dir: Path) -> dict[str, Any]:
    experiment = _latest_experiment(runs_dir)
    if experiment is None:
        return {
            "trace_unavailable": True,
            "reason": "No local V5 experiment directory with episodes was found.",
            "runs_dir": str(runs_dir),
        }
    episode_dirs = sorted(
        path
        for path in (experiment / "episodes").iterdir()
        if (path / "judge_metrics.json").is_file()
    )
    if not episode_dirs:
        return {
            "trace_unavailable": True,
            "reason": "The newest V5 experiment contains no judge_metrics.json files.",
            "experiment": experiment.name,
        }
    episodes = [_episode_summary(path) for path in episode_dirs]
    return {
        "trace_unavailable": False,
        "experiment": experiment.name,
        "episode_count": len(episodes),
        "aggregate": _aggregate(episodes),
        "interface_anomalies": _flag_interface_anomalies(episodes),
        "episodes": episodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--summary", action="store_true", help="Print only the aggregate.")
    args = parser.parse_args()
    result = audit(args.runs_dir)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.summary and not result.get("trace_unavailable"):
        print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
