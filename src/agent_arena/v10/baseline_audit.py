"""V10 Batch 0：在不写入 runs/v8、runs/v9 的前提下复算 V8/V9 证据。

- V8 90 局：注册表、Trace/judge/metrics 文件可达性、hash 头与冻结一致性、账本；
- V9 29 条：episode manifest、账本（主账本 + 2 个补充账本）与 provider 中断；
- V9 基线：Oracle、20 个 legal_random、公开启发式、消融重跑，与 runs/v9/baselines 逐图比较；
- V9 独立复算：120 条检查重跑，与 runs/v9/metric_checks/summary.json 比较。

全部输出写到 ``runs/v10/baseline_audit/``。
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from agent_arena.v10.paths import REPO_ROOT, V9_RUNS, V10_RUNS

OUTPUT = V10_RUNS / "baseline_audit"


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------- V8
def audit_v8() -> dict[str, Any]:
    from agent_arena.v9 import audit as v9_audit

    rows = v9_audit.official_rows()
    frozen = v9_audit.freeze_manifest()
    registry = v9_audit.audit_registry(rows)
    episodes = v9_audit.audit_episodes(rows, frozen)
    ledger = v9_audit.audit_ledger(rows)
    runtime = v9_audit.audit_runtime_hashes(frozen)
    aggregates = v9_audit.recompute_aggregates(rows, episodes)
    present = {
        label: sum(1 for entry in episodes["per_run"] if entry.get(f"{label}_present"))
        for label in ("trace", "judge", "metrics")
    }
    return {
        "rows": len(rows),
        "files_present": present,
        "registry": registry,
        "episode_problems": episodes["problems"],
        "header_mismatch_count": len(episodes["header_mismatches"]),
        "header_mismatch_fields": dict(
            Counter(item["field"] for item in episodes["header_mismatches"])
        ),
        "ledger": {
            key: ledger[key]
            for key in (
                "settled_cost",
                "official_episode_cost",
                "official_episode_cost_coverage",
                "csv_cost",
                "settled_requests",
                "failed_requests",
                "unknown_spend_failure_count",
                "input_tokens",
                "output_tokens",
            )
        },
        "ledger_names": sorted(ledger["ledgers"]),
        "runtime_hash_mismatches": runtime["mismatch_count"],
        "total_success": aggregates["total_success"],
        "strata": aggregates["strata"],
        "per_map_success": {
            map_id: item["successes"] for map_id, item in aggregates["per_map"].items()
        },
    }


# ---------------------------------------------------------------------- V9
def audit_v9_mimo() -> dict[str, Any]:
    episodes_root = V9_RUNS / "experiments" / "episodes"
    records: list[dict[str, Any]] = []
    for directory in sorted(path for path in episodes_root.iterdir() if path.is_dir()):
        manifest = _read_json(directory / "episode_manifest.json")
        files = {
            name: (directory / name).is_file()
            for name in (
                "agent_trace.jsonl",
                "judge_metrics.json",
                "v9_metrics.json",
                "episode_manifest.json",
            )
        }
        records.append(
            {
                "run_id": manifest["run_id"],
                "map_id": manifest["map_id"],
                "arm": manifest.get("arm"),
                "seed": manifest.get("seed"),
                "replicate_id": manifest.get("replicate_id"),
                "status": manifest.get("status"),
                "success": manifest.get("success"),
                "termination_reason": manifest.get("termination_reason"),
                "unknown_spend": manifest.get("unknown_spend"),
                "provider_error": manifest.get("provider_error"),
                "decision_count": manifest.get("decision_count"),
                "cost": (manifest.get("usage") or {}).get("cost"),
                "files": files,
            }
        )
    ledgers: dict[str, Any] = {}
    total_settled = Decimal(0)
    for name, path in (
        ("main", V9_RUNS / "ledger.jsonl"),
        ("supplement_001", V9_RUNS / "supplement_001" / "ledger.jsonl"),
        ("supplement_002", V9_RUNS / "supplement_002" / "ledger.jsonl"),
    ):
        events = _jsonl(path)
        settled = sum(
            (
                Decimal(str(event.get("actual_cost", "0")))
                for event in events
                if event["event"] == "request_settled"
            ),
            Decimal(0),
        )
        total_settled += settled
        closed = [event for event in events if event["event"] == "experiment_closed"]
        ledgers[name] = {
            "settled_cost": str(settled),
            "settled_requests": sum(1 for e in events if e["event"] == "request_settled"),
            "failed_requests": sum(1 for e in events if e["event"] == "request_failed"),
            "unknown_spend": sum(
                1 for e in events if e["event"] == "request_failed" and e.get("unknown_spend")
            ),
            "closed_reason": closed[-1].get("reason") if closed else None,
        }
    interrupted = [item for item in records if item["unknown_spend"]]
    valid = [item for item in records if not item["unknown_spend"]]
    return {
        "records": len(records),
        "valid": len(valid),
        "provider_interrupted": len(interrupted),
        "interrupted_run_ids": [item["run_id"] for item in interrupted],
        "successes": sum(1 for item in valid if item["success"]),
        "all_files_present": all(all(item["files"].values()) for item in records),
        "seeds_used": dict(Counter(str(item["seed"]) for item in records)),
        "ledgers": ledgers,
        "settled_cost_total": str(total_settled),
        "per_run": records,
    }


def _strip_volatile(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _strip_volatile(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_strip_volatile(item) for item in payload]
    return payload


def rerun_v9_baselines() -> dict[str, Any]:
    from agent_arena.v9 import baseline_run
    from agent_arena.worlds.scenario_v8.catalog import CONDITIONS, LEVEL_OF, MAP_IDS, WORLD_OF

    per_map: dict[str, Any] = {}
    for map_id in MAP_IDS:
        current: dict[str, Any] = {
            "map_id": map_id,
            "world": WORLD_OF[map_id],
            "difficulty": LEVEL_OF[map_id],
            "condition_id": CONDITIONS.get(map_id, "default"),
            "decision_budget": baseline_run.decision_budget(map_id),
            "oracle": baseline_run.oracle_records(map_id),
            "legal_random": baseline_run.random_records(map_id),
            "public_heuristic": baseline_run.heuristic_records(map_id),
            "ablations": baseline_run.ablation_records(map_id),
        }
        stored_path = V9_RUNS / "baselines" / f"{map_id}.json"
        stored = _read_json(stored_path) if stored_path.is_file() else None
        identical = (
            stored is not None
            and json.loads(json.dumps(current, ensure_ascii=False, sort_keys=True)) == stored
        )
        per_map[map_id] = {
            "identical_to_v9": identical,
            "oracle_ok": sum(1 for item in current["oracle"] if item["ok"]),
            "oracle_cases": len(current["oracle"]),
            "oracle_seeds": sorted(
                {int(case.get("seed", 0)) for case in baseline_run.oracle_cases(map_id)}
            ),
            "random_success": sum(1 for item in current["legal_random"] if item["success"]),
            "random_runs": len(current["legal_random"]),
            "heuristic_success": bool(
                current["public_heuristic"] and current["public_heuristic"].get("success")
            ),
            "ablations": {
                name: bool(record.get("success")) for name, record in current["ablations"].items()
            },
        }
    return {
        "maps": per_map,
        "identical_maps": sum(1 for item in per_map.values() if item["identical_to_v9"]),
        "oracle_ok": sum(item["oracle_ok"] for item in per_map.values()),
        "oracle_cases": sum(item["oracle_cases"] for item in per_map.values()),
        "random_runs": sum(item["random_runs"] for item in per_map.values()),
        "random_success": sum(item["random_success"] for item in per_map.values()),
    }


def rerun_v9_metric_checks() -> dict[str, Any]:
    from agent_arena.v9.metric_checks import registry
    from agent_arena.v9.metric_checks.base import CheckReport, run_map_checks

    report = CheckReport()
    for map_id, checks in registry().items():
        report.outcomes.extend(run_map_checks(map_id, checks))
    summary = report.summary()
    stored = _read_json(V9_RUNS / "metric_checks" / "summary.json")
    keys = ("checks", "matched", "mismatched", "not_computable", "maps", "runs")
    return {
        "current": {key: summary[key] for key in keys},
        "stored_v9": {key: stored[key] for key in keys},
        "identical": all(summary[key] == stored[key] for key in keys),
    }


def build() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "python": sys.version.split()[0],
        "v8": audit_v8(),
        "v9_mimo": audit_v9_mimo(),
        "v9_baselines": rerun_v9_baselines(),
        "v9_metric_checks": rerun_v9_metric_checks(),
    }
    (OUTPUT / "baseline_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    report = build()
    brief = {
        "head": report["head"],
        "v8_rows": report["v8"]["rows"],
        "v8_files_present": report["v8"]["files_present"],
        "v8_problems": len(report["v8"]["episode_problems"]),
        "v8_header_mismatch": report["v8"]["header_mismatch_count"],
        "v8_runtime_mismatch": report["v8"]["runtime_hash_mismatches"],
        "v8_success": report["v8"]["total_success"],
        "v8_ledger": report["v8"]["ledger"],
        "v9_records": report["v9_mimo"]["records"],
        "v9_valid": report["v9_mimo"]["valid"],
        "v9_interrupted": report["v9_mimo"]["provider_interrupted"],
        "v9_success": report["v9_mimo"]["successes"],
        "v9_settled": report["v9_mimo"]["settled_cost_total"],
        "v9_ledgers": report["v9_mimo"]["ledgers"],
        "v9_baselines_identical": report["v9_baselines"]["identical_maps"],
        "v9_oracle": f"{report['v9_baselines']['oracle_ok']}/"
        f"{report['v9_baselines']['oracle_cases']}",
        "v9_random": f"{report['v9_baselines']['random_success']}/"
        f"{report['v9_baselines']['random_runs']}",
        "v9_metric_checks": report["v9_metric_checks"],
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
