"""V14 LIVE 结果汇总（只读；零请求）。

用法：
    uv run python scripts/summarize_v14_live.py            # 打印摘要
    uv run python scripts/summarize_v14_live.py --write     # 写 docs/v14/live-results.md/.json

数据来源：``runs/v14/live/{lab,web}``（V14 独立账本，本机生成物）。
只读聚合，不重跑、不改写任何 trace 或账本。
"""

from __future__ import annotations

import argparse
import decimal
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v14.conditions import (  # noqa: E402
    build_pairs,
    descriptive_only_preconditions,
    summarize_pairing,
)

LIVE_DIR = ROOT / "runs" / "v14" / "live"
LEDGER = LIVE_DIR / "web" / "_ledger" / "web_ledger.jsonl"

VALID = {"completed_success", "mechanism_failure", "budget_censored"}

#: 基础设施中断：不计入效果分母，也**不**算作场景机制失败。
INTERRUPTED = {"provider_error", "cancelled"}

def classify_state(*, success: bool, state: str | None) -> str:
    """把一局的 `state` 映射成聚合口径的分类。

    - `completed_success` / `mechanism_failure` / `budget_censored` 计入 `valid` 分母；
    - `provider_error` / `cancelled` 属于**基础设施中断**，单独计数、不进分母。

    修正前 Provider 5xx 会被归成 `mechanism_failure`，既污染分母又把
    "模型没答完" 写成 "场景机制失败"（V14.1 修复，见 DCR-V14-11）。
    """
    if success:
        return "completed_success"
    normalized = (state or "").upper()
    if normalized == "BUDGET_REACHED":
        return "budget_censored"
    if normalized == "PROVIDER_ERROR":
        return "provider_error"
    if normalized == "CANCELLED":
        return "cancelled"
    return "mechanism_failure"

def _ledger() -> dict[str, Any]:
    if not LEDGER.is_file():
        return {"available": False}
    rows = [
        json.loads(line)
        for line in LEDGER.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]
    settled = [row for row in rows if row.get("event") == "run_settled"]
    started = {row.get("run_id") for row in rows if row.get("event") == "run_started"}
    settled_ids = [row.get("run_id") for row in settled]
    total = sum(
        (decimal.Decimal(str(row.get("cost_settled_cny") or "0")) for row in settled),
        decimal.Decimal("0"),
    )
    return {
        "available": True,
        "entries": len(rows),
        "started": len(started),
        "settled": len(settled_ids),
        "requests": sum(int(row.get("requests") or 0) for row in settled),
        "settled_cost_cny": f"{total:.8f}",
        "unknown_cost_runs": sum(1 for row in settled if row.get("cost_unknown")),
        "duplicates": len(settled_ids) - len(set(settled_ids)),
        "orphans": len(set(settled_ids) - started),
    }

def _experiments() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for directory in sorted((LIVE_DIR / "lab").glob("lab-*")):
        children_file = directory / "children.json"
        spec_file = directory / "experiment.json"
        if not children_file.is_file() or not spec_file.is_file():
            continue
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        children = json.loads(children_file.read_text(encoding="utf-8"))["children"]
        arm = (spec.get("agent_arms") or [{}])[0]
        config = dict(arm.get("config") or {})
        found.append(
            {
                "experiment_id": directory.name,
                "agent_id": arm.get("agent_id"),
                "config": config,
                "maps": spec.get("maps"),
                "seeds": spec.get("environment_seeds"),
                "replicates": spec.get("replicates"),
                "experiment_kind": spec.get("experiment_kind"),
                "children": children,
            }
        )
    return found

def _group_of(agent_id: str, config: dict[str, Any]) -> tuple[str, str]:
    if agent_id == "memory.v2":
        if not config.get("route_log"):
            return "E1-a", "E1-a/off"
        every = int(config.get("route_write_every") or 2)
        # route_write_every 是 V14 的第二组单因子（记录频率）；默认值 2 记为 "on"。
        return "E1-a", ("E1-a/on" if every == 2 else f"E1-a/on-we{every}")
    if agent_id == "planning.v2":
        arm = "on" if config.get("enabled") else "off"
        return "E2-a", f"E2-a/{arm}"
    if agent_id == "reflection.v2":
        arm = "off" if not config.get("enabled") else (
            "trigger_only" if config.get("trigger_only") else "on"
        )
        return "E3", f"E3/{arm}"
    return "OTHER", f"OTHER/{agent_id}"

def _event_name(item: dict[str, Any]) -> str:
    return str(item.get("agent_event") or item.get("event") or "")

def _record(child: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any] | None:
    run_id = child.get("run_id")
    path = LIVE_DIR / "web" / str(run_id) / "result.json"
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    usage = result.get("usage") or {}
    metrics = result.get("metrics") or {}
    events = result.get("agent_events") or []
    group, arm = _group_of(str(experiment["agent_id"]), experiment["config"])
    return {
        "run_id": run_id,
        "experiment_id": experiment.get("experiment_id"),
        "group": group,
        "arm": arm,
        "experiment_kind": experiment.get("experiment_kind"),
        "agent_id": experiment["agent_id"],
        "config": experiment["config"],
        "map_id": result.get("map_id"),
        "environment_seed": int(result.get("environment_seed") or 0),
        "replicate_index": int(result.get("replicate_index") or 0),
        "category": classify_state(
            success=bool(result.get("success")), state=result.get("state")
        ),
        "success": bool(result.get("success")),
        "state": result.get("state"),
        "termination": result.get("termination"),
        "decisions": int(result.get("decision_count") or 0),
        "requests": int(usage.get("requests") or 0),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "cost_cny": float(usage.get("cost_settled_cny") or 0),
        "cost_known": not bool(usage.get("cost_unknown")),
        "agent_config_hash": result.get("agent_config_hash"),
        "agent_contract_version": result.get("agent_contract_version"),
        "prompt_hash": result.get("prompt_hash"),
        "base_prompt_hash": result.get("base_prompt_hash"),
        "request_cap": int(usage.get("max_requests") or 0) or None,
        "input_token_cap": int(usage.get("max_input_tokens") or 0) or None,
        "mode": result.get("mode"),
        "model": result.get("model"),
        "provider_id": result.get("provider_id"),
        "rule_hash": result.get("rule_hash"),
        "metric_hash": result.get("metric_hash"),
        "metric_schema_hash": result.get("metric_schema_hash"),
        "metrics": {key: value.get("value") for key, value in metrics.items()},
        "metric_states": {key: value.get("state") for key, value in metrics.items()},
        "events": events,
        "reflection_triggered": sum(
            1
            for item in events
            if item.get("kind") == "reflection"
            and _event_name(item) in {"reflection_triggered", "reflection_empty"}
        ),
        "plan_count": sum(
            1
            for item in events
            if item.get("kind") == "plan"
            and _event_name(item) in {"plan_created", "plan_replanned"}
        ),
        "memory_writes": sum(
            1
            for item in events
            if item.get("kind") == "memory" and _event_name(item) == "route_logged"
        ),
        "invalid_actions": int(result.get("invalid_actions") or 0),
        "rejected_actions": int(result.get("rejected_actions") or 0),
    }

def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None

def _arm_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [item for item in records if item["category"] in VALID]
    successes = [item for item in valid if item["category"] == "completed_success"]
    censored = [item for item in valid if item["category"] == "budget_censored"]
    return {
        "runs": len(records),
        "valid": len(valid),
        "successes": len(successes),
        "success_rate": round(len(successes) / len(valid), 4) if valid else None,
        "mechanism_failures": sum(
            1 for item in valid if item["category"] == "mechanism_failure"
        ),
        "censored": len(censored),
        "provider_errors": sum(
            1 for item in records if item["category"] == "provider_error"
        ),
        "cancelled": sum(1 for item in records if item["category"] == "cancelled"),
        "mean_requests": _mean([float(item["requests"]) for item in records]),
        "mean_input_tokens": _mean([float(item["input_tokens"]) for item in records]),
        "mean_decisions": _mean([float(item["decisions"]) for item in records]),
        "total_cost_cny": round(sum(item["cost_cny"] for item in records), 8),
        "mean_cost_cny": _mean([item["cost_cny"] for item in records]),
        "unknown_cost_runs": sum(1 for item in records if not item["cost_known"]),
        "invalid_actions": sum(item["invalid_actions"] for item in records),
        "rejected_actions": sum(item["rejected_actions"] for item in records),
        "seeds": sorted({item["environment_seed"] for item in records}),
        "replicates": sorted({item["replicate_index"] for item in records}),
    }

def _mechanism(records: list[dict[str, Any]], group: str) -> dict[str, Any]:
    if group == "E1-a":
        recall = [
            item["metrics"].get("map22.v10.route_recall")
            for item in records
            if item["metrics"].get("map22.v10.route_recall") is not None
        ]
        return {
            "route_recall_mean": _mean([float(value) for value in recall]),
            "route_recall_values": [round(float(value), 4) for value in recall],
            "memory_writes": sum(item["memory_writes"] for item in records),
            "wasted_moves_mean": _mean(
                [
                    float(item["metrics"].get("map22.v10.wasted_moves") or 0)
                    for item in records
                ]
            ),
        }
    if group == "E2-a":
        return {
            "plan_count_mean": _mean([float(item["plan_count"]) for item in records]),
            "planner_events": sum(item["plan_count"] for item in records),
            "requests_mean": _mean([float(item["requests"]) for item in records]),
        }
    if group == "E3":
        triggered = sum(item["reflection_triggered"] for item in records)
        return {
            "reflection_triggered": triggered,
            "exposure": "TREATMENT_TRIGGERED" if triggered else "NO_TREATMENT_EXPOSURE",
        }
    return {}

def _pairs(records: list[dict[str, Any]], group: str) -> dict[str, Any]:
    arms = sorted({item["arm"] for item in records})
    if len(arms) != 2:
        return {"available": False, "reason": f"组 {group} 的臂数不是 2：{arms}"}
    left = [item for item in records if item["arm"] == arms[0]]
    right = [item for item in records if item["arm"] == arms[1]]
    pairs = build_pairs(left, right)
    summary = summarize_pairing(pairs)
    return {
        "available": True,
        "left_arm": arms[0],
        "right_arm": arms[1],
        "summary": summary,
        "preconditions": descriptive_only_preconditions(pairs),
        "pairs": [
            {
                "pair_key": pair["pair_key"],
                "verdict": pair["verdict"],
                "reason": pair["reason"],
                "left_category": pair["left_category"],
                "right_category": pair["right_category"],
                "left_cost": pair["left_cost_cny"],
                "right_cost": pair["right_cost_cny"],
            }
            for pair in pairs
        ],
    }

def _collect_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    experiments = _experiments()
    records: list[dict[str, Any]] = []
    for experiment in experiments:
        for child in experiment["children"]:
            record = _record(child, experiment)
            if record is not None:
                records.append(record)
    return records, experiments

def collect() -> dict[str, Any]:
    records, experiments = _collect_records()
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = f"{record['group']}|req={record['request_cap']}"
        groups.setdefault(key, []).append(record)
    report = {
        "schema": "v14-live-results-2",
        "ledger": _ledger(),
        "experiments": len(experiments),
        "records": len(records),
        "groups": {},
        "by_kind": {},
    }
    kinds: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        kinds.setdefault(
            f"{record['group']}|{record.get('experiment_kind')}|{record.get('model')}", []
        ).append(record)
    for key, items in sorted(kinds.items()):
        arms: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            arms.setdefault(item["arm"], []).append(item)
        report["by_kind"][key] = {
            name: _arm_summary(rows) for name, rows in sorted(arms.items())
        }
    pooled: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        pooled.setdefault(
            f"{record['group']}|{record['map_id']}|req={record['request_cap']}"
            f"|{record['model']}",
            [],
        ).append(record)
    report["by_seed"] = {}
    for key, items in sorted(pooled.items()):
        table: dict[str, dict[str, dict[str, int]]] = {}
        for item in items:
            arm = table.setdefault(item["arm"], {})
            bucket = arm.setdefault(
                str(item["environment_seed"]),
                {"runs": 0, "successes": 0, "censored": 0, "provider_errors": 0},
            )
            bucket["runs"] += 1
            if item["success"]:
                bucket["successes"] += 1
            if item["category"] == "budget_censored":
                bucket["censored"] += 1
            if item["category"] in INTERRUPTED:
                bucket["provider_errors"] += 1
        report["by_seed"][key] = table
    for group, items in sorted(groups.items()):
        arms: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            arms.setdefault(item["arm"], []).append(item)
        report["groups"][group] = {
            "arms": {name: _arm_summary(rows) for name, rows in sorted(arms.items())},
            "pairs": _pairs(items, group),
            "mechanism": _mechanism(items, group),
            "mechanism_by_arm": {
                name: _mechanism(rows, group) for name, rows in sorted(arms.items())
            },
            "seed_detail": {
                name: sorted(
                    {
                        (int(item["environment_seed"]), int(item["replicate_index"]),
                         "OK" if item["success"] else item["category"])
                        for item in rows
                    }
                )
                for name, rows in sorted(arms.items())
            },
        }
    return report

def _dir(summary: dict[str, Any], key: str) -> Any:
    rows = summary.get("by_seed") or []
    return rows[0].get(key) if rows else "—"

def markdown(report: dict[str, Any]) -> str:
    ledger = report["ledger"]
    lines = [
        "# V14 LIVE 结果（方案 A 子集，真实 MiMo）",
        "",
        "- 模型：`mimo-v2.6-flash`（OpenAI-compatible 网关，本机 `.env`）",
        f"- 实验数：{report['experiments']}；局数：{report['records']}",
        "- 独立账本：`runs/v14/live/web/_ledger/web_ledger.jsonl`（与 V12/V13 分离）",
        "",
        "## 1. 账本",
        "",
        "| 项 | 值 |",
        "|---|---:|",
        f"| started / settled | {ledger.get('started')} / {ledger.get('settled')} |",
        f"| 请求数 | {ledger.get('requests')} |",
        f"| 结算 CNY | {ledger.get('settled_cost_cny')} |",
        f"| 费用未知局 | {ledger.get('unknown_cost_runs')} |",
        f"| 重复结算 / 孤儿 | {ledger.get('duplicates')} / {ledger.get('orphans')} |",
        "",
        "## 2. 逐组结果",
        "",
    ]
    for group, payload in report["groups"].items():
        lines += [
            f"### {group}",
            "",
            "| 臂 | 局数 | 有效 | 成功 | 机制失败 | 截尾 | 中断 | 成功率 "
            "| 平均请求 | 平均决策 | 平均费用 CNY |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, arm in payload["arms"].items():
            lines.append(
                f"| `{name}` | {arm['runs']} | {arm['valid']} | {arm['successes']} | "
                f"{arm['mechanism_failures']} | {arm['censored']} | "
                f"{arm['provider_errors'] + arm['cancelled']} | "
                f"{arm['success_rate'] if arm['success_rate'] is not None else '—'} | "
                f"{arm['mean_requests']} | {arm['mean_decisions']} | {arm['mean_cost_cny']} |"
            )
        pairs = payload["pairs"]
        lines += ["", "配对：", ""]
        if pairs.get("available"):
            summary = pairs["summary"]
            pre = pairs["preconditions"]
            lines += [
                f"- 配对键 `(map, seed, replicate_index)`：{summary['pairs']} 对；"
                f"可比 {summary['comparable_pairs']}、描述性 {summary['descriptive_pairs']}、"
                f"不可比 {summary['incomparable_pairs']}",
                "- 方向（仅可比对）："
                f"right_only {_dir(summary, 'right_only')}、"
                f"left_only {_dir(summary, 'left_only')}、"
                f"both_success {_dir(summary, 'both_success')}、"
                f"neither {_dir(summary, 'neither')}",
                "- 描述性原因：" + ("；".join(pre["reasons"]) or "无"),
                f"- 独立 seed：{pre['independent_seed_count']}",
            ]
        else:
            lines.append(f"- {pairs.get('reason')}")
        mechanism = payload["mechanism"]
        if mechanism:
            lines += ["", f"机制：`{json.dumps(mechanism, ensure_ascii=False)}`"]
        lines.append("")
    lines += [
        "## 3. 口径",
        "",
        "- `局数` = 账本里已结算的全部局；`有效` = 局数 − `中断`（Provider 错误/取消）。",
        "- `成功率` = `成功 / 有效`；`截尾`（`BUDGET_REACHED`）保留在分母里，不当作失败机制。",
        "- `中断` 单独计数：Provider 5xx 不是场景机制失败，也不进分母。",
        "",
        "## 4. 读法（不许夸大）",
        "",
        "- 每组只有 3 个环境 seed × 3 次重复；重复是**模型采样波动**，不是新环境样本。",
        "- 两臂差异必须同时看成功率与成本；0 成功的条件下不得写“某策略更好”。",
        "- `E3` 在 Pilot 中 `triggered = 0` → `NO_TREATMENT_EXPOSURE`，**不评价反思有效性**。",
        "- 全部为 `LIVE` 单模型（MiMo）结果，不构成跨模型结论。",
        "",
    ]
    return "\n".join(lines)

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

def build_manifest() -> dict[str, Any]:
    """逐局证据索引（可提交）：只包含 run_id、条件、结局、请求、费用与文件 sha256。

    原始 `result.json` / `events.jsonl` / 账本体积大且含本机绝对路径，
    仍留在本机 `runs/v14/live/`（gitignore）；本文件是它们与 `docs/` 里
    那些聚合数字之间的可核对索引。
    """
    records, experiments = _collect_records()
    runs: list[dict[str, Any]] = []
    for record in sorted(
        records, key=lambda item: (str(item["experiment_id"]), str(item["run_id"]))
    ):
        run_id = str(record["run_id"])
        directory = LIVE_DIR / "web" / run_id
        events_path = directory / "events.jsonl"
        runs.append(
            {
                "run_id": run_id,
                "experiment_id": record["experiment_id"],
                "group": record["group"],
                "arm": record["arm"],
                "agent": record["agent_id"],
                "map_id": record["map_id"],
                "environment_seed": record["environment_seed"],
                "replicate_index": record["replicate_index"],
                "model": record["model"],
                "request_cap": record["request_cap"],
                "state": record["state"],
                "termination": record["termination"],
                "category": record["category"],
                "success": record["success"],
                "requests": record["requests"],
                "cost_cny": round(float(record["cost_cny"]), 8),
                "cost_known": record["cost_known"],
                "result_sha256": _sha256(directory / "result.json"),
                "events_sha256": _sha256(events_path) if events_path.is_file() else None,
            }
        )
    valid = [item for item in runs if item["category"] in VALID]
    ledger = _ledger()
    if LEDGER.is_file():
        ledger["sha256"] = _sha256(LEDGER)
    return {
        "schema": "v14-live-manifest-1",
        "note": (
            "逐局证据索引。原始 result.json / events.jsonl / 账本留在本机 "
            "runs/v14/live（gitignore，约 29 MB）；本文件只提交索引与 sha256。"
            "校验：`uv run python scripts/summarize_v14_live.py --check-manifest "
            "docs/v14/live-manifest.json`"
        ),
        "ledger": ledger,
        "totals": {
            "experiments": len(experiments),
            "runs": len(runs),
            "valid": len(valid),
            "successes": sum(1 for item in valid if item["success"]),
            "censored": sum(1 for item in valid if item["category"] == "budget_censored"),
            "provider_errors": sum(
                1 for item in runs if item["category"] in INTERRUPTED
            ),
            "requests": sum(int(item["requests"]) for item in runs),
            "cost_cny": round(sum(float(item["cost_cny"]) for item in runs), 8),
        },
        "experiments": [
            {
                "experiment_id": experiment["experiment_id"],
                "agent_id": experiment["agent_id"],
                "experiment_kind": experiment["experiment_kind"],
                "maps": experiment["maps"],
                "environment_seeds": experiment["seeds"],
                "replicates": experiment["replicates"],
                "runs": sum(
                    1
                    for record in records
                    if record["experiment_id"] == experiment["experiment_id"]
                ),
            }
            for experiment in experiments
        ],
        "runs": runs,
    }

def _compare_manifest(path: Path) -> dict[str, Any]:
    if not LIVE_DIR.is_dir():
        return {"available": False, "reason": "本机没有 runs/v14/live，跳过"}
    if not path.is_file():
        return {"available": True, "match": False, "reason": f"缺少 {path}"}
    expected = json.loads(path.read_text(encoding="utf-8"))
    actual = build_manifest()
    if expected == actual:
        return {"available": True, "match": True, "runs": len(actual["runs"])}
    mismatches: list[str] = []
    for key in ("ledger", "totals", "experiments"):
        if expected.get(key) != actual.get(key):
            mismatches.append(key)
    old_runs = {item["run_id"]: item for item in expected.get("runs") or []}
    new_runs = {item["run_id"]: item for item in actual["runs"]}
    for run_id in sorted(set(old_runs) | set(new_runs)):
        if old_runs.get(run_id) != new_runs.get(run_id):
            mismatches.append(f"run:{run_id}")
    return {"available": True, "match": False, "mismatches": mismatches[:20]}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--manifest", type=Path, default=None, help="写逐局证据索引 JSON")
    parser.add_argument(
        "--check-manifest", type=Path, default=None, help="把本机原始数据与已提交的索引对账"
    )
    args = parser.parse_args()

    if args.check_manifest is not None:
        result = _compare_manifest(args.check_manifest)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0 if result.get("match") or not result.get("available") else 1

    report = collect()
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "live-results.md").write_text(markdown(report), encoding="utf-8", newline="\n")
        (args.out / "live-results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(build_manifest(), ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps({"ledger": report["ledger"], "records": report["records"],
                      "groups": sorted(report["groups"])}, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())