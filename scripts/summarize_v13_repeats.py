"""V13 重复稳定性汇总：翻转率、逐条件明细与 Wilson 描述区间。

用法：
    # 只读 V12 历史（默认，零请求）
    uv run python scripts/summarize_v13_repeats.py --history --out docs/v13

    # 指定本机实验（同一实验内可含 replicates）
    uv run python scripts/summarize_v13_repeats.py lab-2026... lab-2026...

只读：不重跑、不改账本、不改历史文件。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.experiment import ExperimentService  # noqa: E402
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v13.stability import (  # noqa: E402
    flip_interval,
    replicate_variability,
    write_variability,
)
from agent_arena.web.service import RunService  # noqa: E402

THREE_OBS = [
    "main-54-runs.csv",
    "replicate-16-18-runs.csv",
    "replicate-16-18-b-runs.csv",
]


def _records_from_experiments(ids: list[str]) -> list[dict]:
    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    records: list[dict] = []
    try:
        for experiment_id in ids:
            for record in service.records(experiment_id):
                item = dict(record)
                item["experiment_id"] = experiment_id
                item["source"] = "RUNTIME"
                records.append(item)
    finally:
        runs.shutdown()
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", nargs="*", help="本机实验 id（留空则用 --history）")
    parser.add_argument("--history", action="store_true", help="使用 V12 历史 CSV（只读）")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v13")
    parser.add_argument("--min-obs", type=int, default=2)
    parser.add_argument("--write", action="store_true", help="写出 CSV/JSON/Markdown 报告")
    args = parser.parse_args()

    if args.experiments:
        records = _records_from_experiments(args.experiments)
        source = "RUNTIME"
        stem = "repeat_variability"
    else:
        records = load_v12_history(names=THREE_OBS)
        source = "HISTORICAL"
        stem = "repeat_variability"
    report = replicate_variability(records, min_obs=args.min_obs, source=source)
    written = write_variability(report, args.out, stem=stem)
    payload = {
        "records": report["records"],
        "groups": report["groups"],
        "comparable_groups": report["comparable_groups"],
        "groups_with_flip": report["groups_with_flip"],
        "flip_rate": report["flip_rate"],
        "excluded_not_comparable": report["excluded_not_comparable"],
        "wilson_95": flip_interval(report)["wilson_95"],
        "always_success_conditions": report["always_success_conditions"],
        "written": {name: str(path) for name, path in written.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
