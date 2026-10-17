"""V9 Batch 0：从原始文件复算 V8 基线，不信任既有摘要。

输入只读：``runs/v8/results_90.csv``、``runs/v8/freeze_manifest.json``、
``runs/v8/ledger.jsonl`` 与 90 个 episode 目录。
输出写到 ``runs/v9/baseline/``，供 ``docs/v9/baseline-audit.md`` 引用。
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from agent_arena.v8.metrics import metric_schema_hash
from agent_arena.v8.prompts import system_prompt
from agent_arena.worlds.scenario_v8.catalog import (
    CONDITIONS,
    LEVEL_OF,
    MAP_IDS,
    WORLD_OF,
    create_environment,
    rule_hash,
    scenario_hash,
    source_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
V8_ROOT = REPO_ROOT / "runs" / "v8"
V9_ROOT = REPO_ROOT / "runs" / "v9"


@dataclass(frozen=True)
class Row:
    map_id: str
    replicate_id: int
    run_id: str
    status: str
    success: bool
    termination_reason: str | None
    decision_budget: int
    cost: Decimal
    commit: str
    agent_trace_path: str
    judge_metrics_path: str
    v8_metrics_path: str
    condition_id: str


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def official_rows() -> list[Row]:
    rows: list[Row] = []
    for raw in _read_csv_rows(V8_ROOT / "results_90.csv"):
        rows.append(
            Row(
                map_id=raw["map_id"],
                replicate_id=int(raw["seed_or_replicate"]),
                run_id=raw["run_id"],
                status=raw["status"],
                success=raw["success"] == "True",
                termination_reason=raw["termination_reason"] or None,
                decision_budget=int(raw["decision_budget"]),
                cost=Decimal(raw["cost"]),
                commit=raw["commit"],
                agent_trace_path=raw["agent_trace_path"],
                judge_metrics_path=raw["judge_metrics_path"],
                v8_metrics_path=raw["v8_metrics_path"],
                condition_id=raw["condition_id"],
            )
        )
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _trace_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def freeze_manifest() -> dict[str, Any]:
    return _read_json(V8_ROOT / "freeze_manifest.json")


def audit_registry(rows: list[Row]) -> dict[str, Any]:
    keys = Counter((row.map_id, row.replicate_id) for row in rows)
    duplicates = [f"{map_id}-R{rep}" for (map_id, rep), count in keys.items() if count > 1]
    expected = {(map_id, rep) for map_id in MAP_IDS for rep in range(3)}
    present = set(keys)
    unknown = sorted(present - expected)
    return {
        "rows": len(rows),
        "expected_rows": len(expected),
        "missing": sorted(f"{map_id}-R{rep}" for map_id, rep in expected - present),
        "unknown": [f"{map_id}-R{rep}" for map_id, rep in unknown],
        "duplicates": duplicates,
        "unique_run_ids": len({row.run_id for row in rows}) == len(rows),
        "commit_distribution": dict(Counter(row.commit for row in rows)),
        "condition_distribution": dict(Counter(row.condition_id for row in rows)),
    }


def audit_episodes(rows: list[Row], frozen: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    per_run: list[dict[str, Any]] = []
    header_mismatch: list[dict[str, Any]] = []
    for row in rows:
        trace_path = Path(row.agent_trace_path)
        judge_path = Path(row.judge_metrics_path)
        metrics_path = Path(row.v8_metrics_path)
        entry: dict[str, Any] = {
            "map_id": row.map_id,
            "replicate_id": row.replicate_id,
            "run_id": row.run_id,
            "status": row.status,
            "success": row.success,
            "termination_reason": row.termination_reason,
            "cost": str(row.cost),
            "commit": row.commit,
            "condition_id": row.condition_id,
        }
        for label, path in (
            ("trace", trace_path),
            ("judge", judge_path),
            ("metrics", metrics_path),
        ):
            if not path.is_file():
                problems.append(f"{row.run_id}: missing {label} {path}")
                entry[f"{label}_present"] = False
            else:
                entry[f"{label}_present"] = True
        if not trace_path.is_file():
            entry["trace_sha256"] = None
            per_run.append(entry)
            continue
        trace = _trace_rows(trace_path)
        entry["trace_sha256"] = _sha256_file(trace_path)
        header = trace[0] if trace else {}
        decisions = [item for item in trace[1:] if item.get("event") == "decision"]
        entry["decision_rows"] = len(decisions)
        entry["invalid_action_rows"] = sum(
            1 for item in decisions if item.get("invalid_output_reason")
        )
        entry["header"] = {
            key: header.get(key)
            for key in (
                "scenario_hash",
                "rule_hash",
                "source_hash",
                "prompt_hash",
                "metric_schema_hash",
                "commit",
                "condition_id",
                "decision_budget",
                "model_id",
                "provider",
            )
        }
        if judge_path.is_file():
            judge = _read_json(judge_path)
            entry["judge_decision_count"] = judge.get("decision_count")
            entry["judge_success"] = judge.get("success")
            entry["judge_termination_reason"] = judge.get("termination_reason")
            entry["failure_codes"] = judge.get("failure_codes")
            entry["usage_cost"] = (judge.get("usage") or {}).get("cost")
            entry["usage_requests"] = (judge.get("usage") or {}).get("requests")
            if judge.get("decision_count") != len(decisions):
                problems.append(f"{row.run_id}: decision_count != trace decisions")
            if judge.get("success") != row.success:
                problems.append(f"{row.run_id}: judge success != registry success")
            if (judge.get("termination_reason") or None) != row.termination_reason:
                problems.append(f"{row.run_id}: judge terminal_reason mismatch")
        if metrics_path.is_file():
            metrics = _read_json(metrics_path)
            entry["metric_status_counts"] = metrics.get("status_counts")
            entry["metric_values"] = {
                metric_id: value.get("value")
                for metric_id, value in (metrics.get("metrics") or {}).items()
            }
            entry["metric_statuses"] = {
                metric_id: value.get("status")
                for metric_id, value in (metrics.get("metrics") or {}).items()
            }
        frozen_map = frozen["maps"].get(row.map_id, {})
        for key in (
            "scenario_hash",
            "rule_hash",
            "source_hash",
            "prompt_hash",
            "metric_schema_hash",
        ):
            if header.get(key) != frozen_map.get(key):
                header_mismatch.append(
                    {
                        "run_id": row.run_id,
                        "field": key,
                        "header": header.get(key),
                        "frozen": frozen_map.get(key),
                    }
                )
        if header.get("decision_budget") != frozen_map.get("decision_budget"):
            problems.append(f"{row.run_id}: decision budget differs from freeze")
        per_run.append(entry)
    return {
        "problems": problems,
        "header_mismatches": header_mismatch,
        "per_run": per_run,
    }


def ledger_paths() -> dict[str, Path]:
    """Every V8 ledger, including aborted pre-runs and isolated supplements."""

    paths = {"main": V8_ROOT / "ledger.jsonl"}
    for supplement in sorted(V8_ROOT.glob("supplement_*")):
        candidate = supplement / "ledger.jsonl"
        if candidate.is_file():
            paths[supplement.name] = candidate
    for aborted in sorted((V8_ROOT / "aborted").glob("*/ledger.jsonl")):
        paths[f"aborted/{aborted.parent.name}"] = aborted
    return paths


def audit_ledger(rows: list[Row]) -> dict[str, Any]:
    official_ids = {row.run_id for row in rows}
    ledgers: dict[str, Any] = {}
    official_cost = Decimal(0)
    all_settled_cost = Decimal(0)
    all_settled = 0
    all_failed = 0
    official_by_episode: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for name, path in ledger_paths().items():
        events = _trace_rows(path)
        settled = [event for event in events if event["event"] == "request_settled"]
        failed = [event for event in events if event["event"] == "request_failed"]
        created = [event for event in events if event["event"] == "experiment_created"]
        closed = [event for event in events if event["event"] == "experiment_closed"]
        settled_cost = sum(
            (Decimal(str(event.get("actual_cost", "0"))) for event in settled), Decimal(0)
        )
        by_episode: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for event in settled:
            by_episode[str(event.get("episode_id"))] += Decimal(
                str(event.get("actual_cost", "0"))
            )
        official_here = {
            episode: cost for episode, cost in by_episode.items() if episode in official_ids
        }
        for episode, cost in official_here.items():
            official_by_episode[episode] += cost
        superseeded = sorted(set(by_episode) - official_ids)
        ledgers[name] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "experiment_created": created,
            "closed": closed,
            "settled_cost": str(settled_cost),
            "settled_requests": len(settled),
            "failed_requests": len(failed),
            "episodes_started": len(
                {event.get("episode_id") for event in events if event["event"] == "episode_started"}
            ),
            "episodes_completed": len(
                {
                    event.get("episode_id")
                    for event in events
                    if event["event"] == "episode_completed"
                }
            ),
            "official_episode_count": len(official_here),
            "official_cost": str(sum(official_here.values(), Decimal(0))),
            "superseded_episodes": superseeded,
            "superseded_cost": str(
                sum((by_episode[key] for key in superseeded), Decimal(0))
            ),
            "unknown_spend_failures": [
                {key: event.get(key) for key in ("episode_id", "error_category", "at")}
                for event in failed
                if event.get("unknown_spend")
            ],
        }
        all_settled_cost += settled_cost
        all_settled += len(settled)
        all_failed += len(failed)
    official_cost = sum(official_by_episode.values(), Decimal(0))
    return {
        "ledgers": ledgers,
        "settled_cost": str(all_settled_cost),
        "official_episode_cost": str(official_cost),
        "official_episode_cost_coverage": len(official_by_episode),
        "csv_cost": str(sum((row.cost for row in rows), Decimal(0))),
        "settled_requests": all_settled,
        "failed_requests": all_failed,
        "unknown_spend_failure_count": sum(
            len(item["unknown_spend_failures"]) for item in ledgers.values()
        ),
        "input_tokens": sum(
            int(event.get("input_tokens", 0))
            for name, path in ledger_paths().items()
            for event in _trace_rows(path)
            if event["event"] == "request_settled"
        ),
        "output_tokens": sum(
            int(event.get("output_tokens", 0))
            for name, path in ledger_paths().items()
            for event in _trace_rows(path)
            if event["event"] == "request_settled"
        ),
    }


def audit_runtime_hashes(frozen: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    per_map: dict[str, Any] = {}
    for map_id in MAP_IDS:
        environment = create_environment(map_id)
        level = LEVEL_OF[map_id]
        # MAP-12 has a registered budget exception (60, not the level default 46).
        budget = int(frozen["maps"][map_id]["decision_budget"])
        current = {
            "rule_hash": rule_hash(map_id),
            "scenario_hash": scenario_hash(map_id),
            "source_hash": source_hash(map_id),
            "metric_schema_hash": metric_schema_hash(map_id),
            "prompt_hash": sha256(
                system_prompt(environment, decision_budget=budget).encode("utf-8")
            ).hexdigest(),
            "condition_id": CONDITIONS.get(map_id, "default"),
            "world": WORLD_OF[map_id],
            "difficulty": level,
            "decision_budget": budget,
        }
        expected = frozen["maps"].get(map_id, {})
        drift = [key for key, value in current.items() if expected.get(key) != value]
        if drift:
            mismatches.append({"map_id": map_id, "drift": drift})
        per_map[map_id] = {"current": current, "matches_freeze": not drift, "drift": drift}
    return {"mismatch_count": len(mismatches), "mismatches": mismatches, "maps": per_map}


def recompute_aggregates(rows: list[Row], episodes: dict[str, Any]) -> dict[str, Any]:
    per_map: dict[str, Any] = {}
    by_run = {entry["run_id"]: entry for entry in episodes["per_run"]}
    for map_id in MAP_IDS:
        map_rows = [row for row in rows if row.map_id == map_id]
        statuses = Counter(row.status for row in map_rows)
        successes = sum(1 for row in map_rows if row.success)
        decisions = [by_run[row.run_id].get("decision_rows", 0) for row in map_rows]
        per_map[map_id] = {
            "world": WORLD_OF[map_id],
            "difficulty": LEVEL_OF[map_id],
            "condition_id": CONDITIONS.get(map_id, "default"),
            "successes": successes,
            "n": len(map_rows),
            "statuses": dict(statuses),
            "terminal_reasons": [
                row.termination_reason for row in map_rows
            ],
            "decisions": decisions,
            "mean_decisions": round(sum(decisions) / len(decisions), 2) if decisions else None,
            "cost": str(sum((row.cost for row in map_rows), Decimal(0))),
            "invalid_actions": sum(
                by_run[row.run_id].get("invalid_action_rows", 0) for row in map_rows
            ),
        }
    strata: dict[str, dict[str, int]] = defaultdict(lambda: {"successes": 0, "n": 0})
    for item in per_map.values():
        level = item["difficulty"]
        strata[level]["successes"] += item["successes"]
        strata[level]["n"] += item["n"]
    total_success = sum(item["successes"] for item in per_map.values())
    return {
        "per_map": per_map,
        "strata": dict(strata),
        "total_success": total_success,
        "total_rows": len(rows),
        "status_totals": dict(Counter(row.status for row in rows)),
    }


def build() -> dict[str, Any]:
    rows = official_rows()
    frozen = freeze_manifest()
    registry = audit_registry(rows)
    episodes = audit_episodes(rows, frozen)
    ledger = audit_ledger(rows)
    runtime = audit_runtime_hashes(frozen)
    aggregates = recompute_aggregates(rows, episodes)
    report = {
        "head_commit": _git_head(),
        "registry": registry,
        "episodes": {key: value for key, value in episodes.items() if key != "per_run"},
        "episode_index": episodes["per_run"],
        "ledger": ledger,
        "runtime_hashes": runtime,
        "aggregates": aggregates,
    }
    output = V9_ROOT / "baseline"
    output.mkdir(parents=True, exist_ok=True)
    (output / "baseline.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_run_index(output / "run-index.csv", episodes["per_run"])
    return report


def _git_head() -> str:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _write_run_index(path: Path, per_run: list[dict[str, Any]]) -> None:
    fields = [
        "map_id",
        "replicate_id",
        "run_id",
        "status",
        "success",
        "termination_reason",
        "decision_rows",
        "invalid_action_rows",
        "cost",
        "commit",
        "condition_id",
        "trace_sha256",
        "judge_decision_count",
        "failure_codes",
        "metric_status_counts",
        "usage_cost",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entry in per_run:
            writer.writerow(
                {
                    **{field: entry.get(field) for field in fields},
                    "failure_codes": "|".join(entry.get("failure_codes") or []),
                    "metric_status_counts": json.dumps(
                        entry.get("metric_status_counts"), sort_keys=True
                    ),
                }
            )


def main() -> None:
    report = build()
    print(
        json.dumps(
            {
                "registry": report["registry"],
                "episode_problems": report["episodes"]["problems"],
                "header_mismatches": len(report["episodes"]["header_mismatches"]),
                "ledger": {
                    key: report["ledger"][key]
                    for key in (
                        "settled_cost",
                        "official_episode_cost",
                        "official_episode_cost_coverage",
                        "csv_cost",
                        "settled_requests",
                        "failed_requests",
                        "unknown_spend_failure_count",
                    )
                },
                "runtime_mismatches": report["runtime_hashes"]["mismatch_count"],
                "total_success": report["aggregates"]["total_success"],
                "strata": report["aggregates"]["strata"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
