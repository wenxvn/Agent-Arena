"""V12 重复性汇总：同条件多次运行之间的成功率与结局一致性。

用法：
    uv run python scripts/summarize_v12_replicates.py <experiment_id> [<experiment_id> ...]

只读已落盘 result.json，不重跑、不改账本。输出：
- 每个 (map, seed, agent) 的多次结局；
- 整体翻转率（同条件不同结局的比例）；
- 只对"可比"的集合做统计（同 prompt_hash、同预算）。
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


def _failure_summary(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if field == "pairing":
            key = f"{record['map_id']}|seed={record['environment_seed']}|{record['agent_id']}"
        else:
            key = f"{record['map_id']}|seed={record['environment_seed']}"
        groups[key].append(record)
    return groups


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: summarize_v12_replicates.py <experiment_id> [...]", file=sys.stderr)
        return 2
    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    try:
        records: list[dict[str, Any]] = []
        for experiment_id in argv:
            manifest = service.status(experiment_id)
            for record in service.records(experiment_id):
                record = dict(record)
                record["experiment_id"] = experiment_id
                record["experiment_name"] = manifest.name
                records.append(record)

        groups = _failure_summary(records, "pairing")
        print(
            json.dumps(
                {
                    "experiments": argv,
                    "runs": len(records),
                    "cost_cny": round(sum(r["cost_cny"] or 0 for r in records), 8),
                    "valid": sum(
                        1
                        for r in records
                        if r["category"]
                        in {"completed_success", "mechanism_failure", "budget_censored"}
                    ),
                    "successes": sum(1 for r in records if r["category"] == "completed_success"),
                },
                ensure_ascii=False,
            )
        )
        print()
        print("| 条件（图|seed） | 运行次数 | 成功 | 结局序列 | 一致 |")
        print("|---|---:|---:|---|---|")
        flips = 0
        comparable_groups = 0
        for key in sorted(groups):
            items = groups[key]
            if len(items) < 2:
                continue
            comparable_groups += 1
            outcomes = [item["category"] for item in items]
            successes = sum(1 for item in items if item["category"] == "completed_success")
            consistent = len(set(outcomes)) == 1
            if not consistent:
                flips += 1
            print(
                f"| {key} | {len(items)} | {successes} | "
                f"{' → '.join(outcomes)} | {'是' if consistent else '否'} |"
            )
        print()
        print(
            json.dumps(
                {
                    "comparable_groups": comparable_groups,
                    "groups_with_flip": flips,
                    "flip_rate": round(flips / comparable_groups, 4)
                    if comparable_groups
                    else None,
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
