"""V12 一键离线验收：契约、30 图、父子实验、预算、可视化、导出复算与脱敏。

用法：
    uv run python scripts/verify_v12.py
    uv run python scripts/verify_v12.py --report runs/v12/selfcheck.json

退出码 0 表示全部通过；1 表示至少一项失败。脚本不会发送任何 Provider 请求。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.selfcheck import run_checks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report", type=Path, default=ROOT / "runs" / "v12" / "selfcheck.json"
    )
    args = parser.parse_args()
    report = run_checks(report_path=args.report)
    report_path = (
        str(args.report.relative_to(ROOT))
        if args.report.is_relative_to(ROOT)
        else str(args.report)
    )
    summary = {
        "ok": report["ok"],
        "failed": report["failed"],
        "head": report["head"],
        "report": report_path,
        "checks": [
            {
                "name": item["name"],
                "ok": item["ok"],
                "seconds": item["seconds"],
                "detail": item["detail"] if not item["ok"] else "ok",
            }
            for item in report["checks"]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
