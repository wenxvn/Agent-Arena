"""V12 重复性汇总：同条件多次运行之间的结局一致性（翻转率）。

用法：
    uv run python scripts/summarize_v12_replicates.py <experiment_id> [<experiment_id> ...]

只读已落盘结果，不重跑、不改账本。

判定口径：
- 分组键为 `(map_id, environment_seed, agent_id)`；
- 只有**同 prompt_hash、同单局预算**的多次运行才计入翻转率；
- 其余分组照常列出，但标 `跨版本`／`跨预算`，并**不计入**翻转率——
  否则"换了提示或预算再跑"会被误读成抽样波动。
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.experiment import ExperimentService  # noqa: E402
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402

VALID_CATEGORIES = {"completed_success", "mechanism_failure", "budget_censored"}


def _group(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (
            f"{record['map_id']}|seed={record['environment_seed']}"
            f"|{record['agent_id']}"
        )
        groups[key].append(record)
    return groups


def _signature(items: list[dict[str, Any]]) -> tuple[set[str], set[tuple[int, int]]]:
    """返回该组的 prompt_hash 集合与单局预算集合，用于判断是否真的可比。"""

    hashes = {str(item.get("prompt_hash") or "unknown") for item in items}
    budgets = {
        (int(item.get("request_cap") or 0), int(item.get("input_token_cap") or 0))
        for item in items
    }
    return hashes, budgets


def _mismatch_label(hashes: set[str], budgets: set[tuple[int, int]]) -> str:
    labels = []
    if len(hashes) > 1:
        labels.append("跨版本")
    if len(budgets) > 1:
        labels.append("跨预算")
    return "／".join(labels)


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "用法: summarize_v12_replicates.py <experiment_id> [...]", file=sys.stderr
        )
        return 2

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    try:
        records: list[dict[str, Any]] = []
        for experiment_id in argv:
            spec = service.spec(experiment_id)
            for record in service.records(experiment_id):
                replay = runs.load_replay(record["run_id"])
                result = replay.get("result") or {}
                manifest = replay.get("manifest") or {}
                prompt_hash = (
                    result.get("prompt_hash")
                    or (manifest.get("hashes") or {}).get("prompt_hash")
                    or ""
                )
                item = dict(record)
                item["experiment_id"] = experiment_id
                item["prompt_hash"] = str(prompt_hash)
                item["request_cap"] = spec.budget.per_run_request_cap
                item["input_token_cap"] = spec.budget.per_run_input_token_cap
                records.append(item)

        groups = _group(records)
        print(
            json.dumps(
                {
                    "experiments": argv,
                    "runs": len(records),
                    "valid": sum(1 for r in records if r["category"] in VALID_CATEGORIES),
                    "successes": sum(
                        1 for r in records if r["category"] == "completed_success"
                    ),
                    "cost_cny": round(
                        sum(float(r["cost_cny"] or 0) for r in records), 8
                    ),
                },
                ensure_ascii=False,
            )
        )
        print()
        print("| 条件 | 次数 | 成功 | 结局序列 | 可比 | 一致 |")
        print("|---|---:|---:|---|---|---|")

        flips = 0
        comparable = 0
        skipped = 0
        for key in sorted(groups):
            items = groups[key]
            if len(items) < 2:
                continue
            outcomes = [item["category"] for item in items]
            successes = sum(1 for item in items if item["category"] == "completed_success")
            hashes, budgets = _signature(items)
            label = _mismatch_label(hashes, budgets)
            consistent = len(set(outcomes)) == 1
            if label:
                skipped += 1
                print(
                    f"| {key} | {len(items)} | {successes} | "
                    f"{' → '.join(outcomes)} | **{label}** | — |"
                )
                continue
            comparable += 1
            if not consistent:
                flips += 1
            print(
                f"| {key} | {len(items)} | {successes} | "
                f"{' → '.join(outcomes)} | 是 | {'是' if consistent else '否'} |"
            )

        print()
        print(
            json.dumps(
                {
                    "comparable_groups": comparable,
                    "groups_with_flip": flips,
                    "flip_rate": round(flips / comparable, 4) if comparable else None,
                    "excluded_not_comparable": skipped,
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
