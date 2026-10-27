"""V14 失败归因与能力画像审计（只读；零外部请求）。

用法：
    uv run python scripts/audit_v14_failures.py            # 打印摘要
    uv run python scripts/audit_v14_failures.py --write     # 写 docs/v14/failure-and-capability.*
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v14.failure_capability import (  # noqa: E402
    failure_capability_markdown,
    failure_capability_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = failure_capability_report(load_v12_history())
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "failure-and-capability.md").write_text(
            failure_capability_markdown(report), encoding="utf-8", newline="\n"
        )
        (args.out / "failure-and-capability.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    summary = {
        "fixtures": [item["fixture"] for item in report["fixtures"]["fixtures"]],
        "capability_status": {
            row["dimension"]: row["status"] for row in report["capability"]["dimensions"]
        },
        "unavailable": report["capability"]["unavailable"],
        "conclusion": report["conclusion"],
        "written": str(args.out / "failure-and-capability.md") if args.write else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
