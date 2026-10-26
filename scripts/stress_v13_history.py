"""V13 历史性能压力测试：1 000 / 5 000 条合成 run 的分页、筛选、聚合与导出。

用法：
    uv run python scripts/stress_v13_history.py --write
    uv run python scripts/stress_v13_history.py --counts 1000 5000 --events 20 --write

安全：压力数据只写临时目录，绝不写入仓库 ``runs/``；不联网、不发请求。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.perf import (  # noqa: E402
    performance_markdown,
    run_stress,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", type=int, nargs="+", default=[1_000, 5_000])
    parser.add_argument("--events", type=int, default=0, help="每局写入的合成事件条数")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v13")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = run_stress(tuple(args.counts), events_per_run=args.events)
    markdown = performance_markdown(report)
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "performance-report.md").write_text(
            markdown, encoding="utf-8", newline="\n"
        )
        (args.out / "performance-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "counts": args.counts,
                "results": [
                    {
                        "runs": item["runs"],
                        "cold_ms": next(
                            (
                                timing["milliseconds"]
                                for timing in item["timings"]
                                if timing["label"] == "index_cold_build"
                            ),
                            None,
                        ),
                        "page_ms": next(
                            (
                                timing["milliseconds"]
                                for timing in item["timings"]
                                if timing["label"] == "page_first_50"
                            ),
                            None,
                        ),
                        "peak_memory_kib": item["peak_memory_kib"],
                    }
                    for item in report["results"]
                ],
                "written": str(args.out) if args.write else None,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
