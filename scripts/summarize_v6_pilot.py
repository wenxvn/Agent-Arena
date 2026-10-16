"""Summarise the newest V6 paid experiment into per-instance descriptive counts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "runs" / "v6" / "experiments"


def _latest(runs_dir: Path) -> Path | None:
    if not runs_dir.is_dir():
        return None
    candidates = [
        path for path in runs_dir.iterdir() if path.is_dir() and (path / "episodes").is_dir()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "episodes").stat().st_mtime)


def summarise(experiment: Path) -> dict[str, Any]:
    judge_files = sorted((experiment / "episodes").glob("*/judge_metrics.json"))
    rows: list[dict[str, Any]] = []
    for path in judge_files:
        judge = json.loads(path.read_text(encoding="utf-8"))
        usage = judge.get("usage", {})
        rows.append(
            {
                "episode_id": judge["episode_id"],
                "instance_id": judge.get("instance_id"),
                "map_id": judge["map_id"],
                "level": None,
                "condition_id": judge["condition_id"],
                "status": judge["status"],
                "v4_status": judge.get("v4_status"),
                "decision_count": judge.get("decision_count"),
                "failure_codes": [
                    item["code"] for item in judge.get("failure_classifications", [])
                ],
                "metrics": judge.get("metrics", {}),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "settled_requests": usage.get("settled_requests"),
                "reported_usage_cost": usage.get("reported_usage_cost"),
            }
        )
    total_cost = sum(
        (Decimal(str(row["reported_usage_cost"])) for row in rows if row["reported_usage_cost"]),
        Decimal(0),
    )
    by_instance: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_instance.setdefault(f"{row['instance_id']}::{row['condition_id']}", []).append(row)
    grouped: dict[str, Any] = {}
    for key, group in sorted(by_instance.items()):
        statuses = Counter(row["status"] for row in group)
        codes = Counter(code for row in group for code in row["failure_codes"])
        grouped[key] = {
            "runs": len(group),
            "statuses": dict(statuses),
            "failure_codes": dict(codes),
            "decisions": [row["decision_count"] for row in group],
            "metrics": [row["metrics"] for row in group],
        }
    manifest_path = experiment / "run_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    return {
        "experiment": experiment.name,
        "status": manifest.get("status"),
        "stage": manifest.get("stage"),
        "billing_currency": manifest.get("billing_currency"),
        "offline_gate_hash": manifest.get("offline_gate_hash"),
        "episodes": len(rows),
        "success": sum(row["status"] == "success" for row in rows),
        "total_reported_cost": str(total_cost),
        "ledger_snapshot": manifest.get("ledger_snapshot"),
        "grouped": grouped,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    experiment = _latest(args.runs_dir)
    if experiment is None:
        raise SystemExit("No V6 experiment with episodes was found.")
    result = summarise(experiment)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
