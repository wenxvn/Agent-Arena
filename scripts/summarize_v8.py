"""从不可覆盖的 episode manifest 与账本重建 V8 注册表与 90 行结果表。

只读 `runs/v8/` 下的运行产物，不调用 Provider、不改写任何 episode。
输出：
- `runs/v8/registry.json`：机器可读的 90 行正式结果 + 所有尝试 + 缺口 + 账本。
- `runs/v8/results_90.csv`：90 行扁平结果。
- `runs/v8/results_90.md`：人类可读表格与逐图汇总。
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v7.metrics.registry import specs_for  # noqa: E402

V8_ROOT = ROOT / "runs" / "v8"
EPISODE_ROOT = V8_ROOT / "experiments" / "episodes"
FREEZE_PATH = V8_ROOT / "freeze_manifest.json"
LEDGER_PATH = V8_ROOT / "ledger.jsonl"
REGISTRY_PATH = V8_ROOT / "registry.json"
CSV_PATH = V8_ROOT / "results_90.csv"
MD_PATH = V8_ROOT / "results_90.md"

FORMAL_STATUSES = {
    "success",
    "failure",
    "censored",
    "decision_budget_reached",
    "episode_timeout",
    "schema_fault_limit",
}
FIELDS = [
    "experiment_id",
    "map_id",
    "world",
    "difficulty",
    "scenario_hash",
    "rule_hash",
    "prompt_hash",
    "metric_schema_hash",
    "commit",
    "model_id",
    "provider",
    "temperature",
    "seed_or_replicate",
    "run_id",
    "condition_id",
    "decision_budget",
    "status",
    "success",
    "termination_reason",
    "agent_trace_path",
    "judge_metrics_path",
    "v8_metrics_path",
    "input_tokens",
    "output_tokens",
    "requests",
    "cost",
    "currency",
    "provider_error",
    "unknown_spend",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ledger_events() -> list[dict[str, Any]]:
    if not LEDGER_PATH.is_file():
        return []
    return [
        json.loads(line)
        for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ledger_snapshot(events: list[dict[str, Any]]) -> dict[str, Any]:
    created = next((e for e in events if e["event"] == "experiment_created"), {})
    reserved = {
        e["request_id"]: Decimal(str(e["reserved_cost"]))
        for e in events
        if e["event"] == "request_reserved"
    }
    for event in events:
        if event["event"] == "request_settled":
            reserved.pop(event.get("request_id"), None)
        elif event["event"] == "request_failed" and not event.get("unknown_spend"):
            reserved.pop(event.get("request_id"), None)
    settled = sum(
        (
            Decimal(str(e.get("actual_cost", "0")))
            for e in events
            if e["event"] == "request_settled"
        ),
        Decimal(0),
    )
    return {
        "experiment_id": created.get("experiment_id"),
        "currency": created.get("currency", "CNY"),
        "max_cost": created.get("max_cost", "10"),
        "settled_cost": str(settled),
        "unknown_spend_reserved": str(sum(reserved.values(), Decimal(0))),
        "request_attempts": sum(1 for e in events if e["event"] == "request_reserved"),
        "settled_requests": sum(1 for e in events if e["event"] == "request_settled"),
        "failed_requests": sum(1 for e in events if e["event"] == "request_failed"),
        "closed": any(e["event"] == "experiment_closed" for e in events),
        "closed_reason": next(
            (e.get("reason") for e in reversed(events) if e["event"] == "experiment_closed"),
            None,
        ),
        "warnings": [e["fraction"] for e in events if e["event"] == "budget_warning"],
    }


def scan_manifests() -> dict[tuple[str, int], list[dict[str, Any]]]:
    attempts: dict[tuple[str, int], list[dict[str, Any]]] = {}
    if not EPISODE_ROOT.is_dir():
        return attempts
    for path in sorted(EPISODE_ROOT.glob("*/episode_manifest.json")):
        manifest = read_json(path)
        key = (str(manifest.get("map_id")), int(manifest.get("replicate_id", 0)))
        attempts.setdefault(key, []).append(manifest)
    return attempts


def formal_manifest(attempts: list[dict[str, Any]]) -> dict[str, Any] | None:
    for manifest in attempts:
        if manifest.get("status") in FORMAL_STATUSES:
            return manifest
    return None


def primary_metrics(map_id: str, manifest: dict[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        return {}
    v8_path = Path(str(manifest.get("v8_metrics_path", "")))
    if not v8_path.is_file():
        return {}
    metrics = read_json(v8_path).get("metrics", {})
    selected: dict[str, Any] = {}
    for spec in specs_for(map_id):
        if spec.kind.value in {"primary", "outcome", "guardrail"}:
            value = metrics.get(spec.metric_id, {})
            selected[spec.metric_id] = {
                "kind": spec.kind.value,
                "status": value.get("status"),
                "value": value.get("value"),
                "denominator": value.get("denominator"),
            }
    return selected


def flatten(manifest: dict[str, Any] | None, map_id: str, replicate: int) -> dict[str, Any]:
    if manifest is None:
        return {
            "experiment_id": None,
            "map_id": map_id,
            "world": None,
            "difficulty": None,
            "scenario_hash": None,
            "rule_hash": None,
            "prompt_hash": None,
            "metric_schema_hash": None,
            "commit": None,
            "model_id": None,
            "provider": None,
            "temperature": None,
            "seed_or_replicate": replicate,
            "run_id": None,
            "condition_id": None,
            "decision_budget": None,
            "status": "missing",
            "success": None,
            "termination_reason": None,
            "agent_trace_path": None,
            "judge_metrics_path": None,
            "v8_metrics_path": None,
            "input_tokens": None,
            "output_tokens": None,
            "requests": None,
            "cost": None,
            "currency": None,
            "provider_error": None,
            "unknown_spend": None,
        }
    usage = manifest.get("usage") or {}
    return {
        "experiment_id": manifest.get("experiment_id"),
        "map_id": manifest.get("map_id"),
        "world": manifest.get("world"),
        "difficulty": manifest.get("difficulty"),
        "scenario_hash": manifest.get("scenario_hash"),
        "rule_hash": manifest.get("rule_hash"),
        "prompt_hash": manifest.get("prompt_hash"),
        "metric_schema_hash": manifest.get("metric_schema_hash"),
        "commit": manifest.get("commit"),
        "model_id": manifest.get("model_id"),
        "provider": manifest.get("provider"),
        "temperature": manifest.get("temperature"),
        "seed_or_replicate": manifest.get("replicate_id", replicate),
        "run_id": manifest.get("run_id"),
        "condition_id": manifest.get("condition_id"),
        "decision_budget": manifest.get("decision_budget"),
        "status": manifest.get("status"),
        "success": manifest.get("success"),
        "termination_reason": manifest.get("termination_reason"),
        "agent_trace_path": manifest.get("agent_trace_path"),
        "judge_metrics_path": manifest.get("judge_metrics_path"),
        "v8_metrics_path": manifest.get("v8_metrics_path"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "requests": usage.get("requests"),
        "cost": usage.get("cost"),
        "currency": usage.get("currency"),
        "provider_error": manifest.get("provider_error"),
        "unknown_spend": manifest.get("unknown_spend"),
    }


def main() -> int:
    freeze = read_json(FREEZE_PATH)
    events = ledger_events()
    snapshot = ledger_snapshot(events)
    attempts = scan_manifests()

    rows: list[dict[str, Any]] = []
    per_map: dict[str, dict[str, Any]] = {}
    gaps: list[dict[str, Any]] = []
    attempt_rows: list[dict[str, Any]] = []
    for map_id in sorted(freeze["maps"]):
        entry = freeze["maps"][map_id]
        per_map[map_id] = {
            "world": entry["world"],
            "difficulty": entry["difficulty"],
            "condition_id": entry["condition_id"],
            "successes": 0,
            "statuses": {},
            "cost": Decimal(0),
            "decisions": {},
            "runs": [],
            "primary": {},
        }
        for replicate in range(3):
            manifests = attempts.get((map_id, replicate), [])
            chosen = formal_manifest(manifests)
            if chosen is None:
                gaps.append(
                    {
                        "map_id": map_id,
                        "replicate_id": replicate,
                        "attempts": len(manifests),
                        "statuses": [item.get("status") for item in manifests],
                    }
                )
            row = flatten(chosen, map_id, replicate)
            rows.append(row)
            summary = per_map[map_id]
            summary["statuses"][row["status"]] = summary["statuses"].get(row["status"], 0) + 1
            if row["success"]:
                summary["successes"] += 1
            if row["cost"] is not None:
                summary["cost"] += Decimal(str(row["cost"]))
            if row["status"] != "missing":
                summary["decisions"][str(replicate)] = chosen.get("decision_count")
                summary["runs"].append(row["run_id"])
                summary["primary"][str(replicate)] = primary_metrics(map_id, chosen)
            for item in manifests:
                attempt_rows.append(
                    {
                        "map_id": map_id,
                        "replicate_id": replicate,
                        "run_id": item.get("run_id"),
                        "status": item.get("status"),
                        "success": item.get("success"),
                        "provider_error": item.get("provider_error"),
                        "unknown_spend": item.get("unknown_spend"),
                        "cost": (item.get("usage") or {}).get("cost"),
                    }
                )

    maps_payload = {
        map_id: {
            **summary,
            "cost": str(summary["cost"]),
            "mean_decisions": (
                sum(summary["decisions"].values()) / len(summary["decisions"])
                if summary["decisions"]
                else 0.0
            ),
            "mean_cost": (
                str(summary["cost"] / len(summary["decisions"]))
                if summary["decisions"]
                else "0"
            ),
        }
        for map_id, summary in per_map.items()
    }
    completed = sum(1 for row in rows if row["status"] != "missing")
    total_cost = sum(
        (Decimal(str(row["cost"])) for row in rows if row["cost"] is not None),
        Decimal(0),
    )
    registry = {
        "schema_version": "v8_registry_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "freeze_hash": freeze["freeze_hash"],
        "runtime_tree_hash": freeze["runtime_tree_hash"],
        "commit": freeze["commit"],
        "model_id": freeze["model_id"],
        "provider": freeze["provider"],
        "currency": "CNY",
        "hard_cap": "10",
        "planned_episodes": 90,
        "formal_episodes_completed": completed,
        "gaps": gaps,
        "ledger": snapshot,
        "formal_cost_of_completed_runs": str(total_cost),
        "rows": rows,
        "attempts": attempt_rows,
        "maps": maps_payload,
    }
    REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with CSV_PATH.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in FIELDS})

    lines = [
        "# V8 90 局结果表",
        "",
        f"- freeze_hash: `{freeze['freeze_hash']}`",
        f"- 模型: `{freeze['model_id']}` / provider `{freeze['provider']}`",
        f"- 完成正式局: {completed}/90；缺口 {len(gaps)}",
        f"- 正式局已结算费用: ¥{total_cost}（硬上限 ¥10）",
        f"- 账本: settled {snapshot['settled_cost']} / attempts {snapshot['request_attempts']}"
        f" / failed {snapshot['failed_requests']} / closed {snapshot['closed']}",
        "",
        "n=3 仅作重复运行描述，不做显著性断言。",
        "",
        "| # | map | world | 难度 | rep | status | success | 主指标 |"
        " 终止原因 | 决策 | cost | run_id |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, 1):
        primary = maps_payload[row["map_id"]]["primary"].get(str(row["seed_or_replicate"]), {})
        primary_text = "; ".join(
            f"{metric_id.split('.')[-1]}={value['value']}"
            for metric_id, value in list(primary.items())[:2]
        )
        lines.append(
            f"| {index} | {row['map_id']} | {row['world']} | {row['difficulty']} |"
            f" {row['seed_or_replicate']} | {row['status']} | {row['success']} |"
            f" {primary_text} | {row['termination_reason']} |"
            f" {maps_payload[row['map_id']]['decisions'].get(str(row['seed_or_replicate']), '')} |"
            f" {row['cost']} | `{row['run_id']}` |"
        )
    lines.extend(["", "## 逐图汇总", ""])
    lines.append("| map | world | 难度 | 成功/3 | statuses | mean decisions | total cost |")
    lines.append("|---|---|---|---|---|---|---|")
    for map_id, summary in maps_payload.items():
        lines.append(
            f"| {map_id} | {summary['world']} | {summary['difficulty']} |"
            f" {summary['successes']}/3 | {summary['statuses']} |"
            f" {summary['mean_decisions']:.1f} | {summary['cost']} |"
        )
    if gaps:
        lines.extend(["", "## 缺口", ""])
        for gap in gaps:
            lines.append(
                f"- {gap['map_id']} R{gap['replicate_id']}: attempts={gap['attempts']}"
                f" statuses={gap['statuses']}"
            )
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "registry": str(REGISTRY_PATH),
                "csv": str(CSV_PATH),
                "markdown": str(MD_PATH),
                "formal_episodes_completed": completed,
                "gaps": len(gaps),
                "formal_cost": str(total_cost),
                "ledger": snapshot,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
