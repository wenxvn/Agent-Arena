"""V14 地图适用性审计（只读历史 + 只读规则；零外部请求）。

用法：
    uv run python scripts/audit_v14_maps.py            # 打印摘要
    uv run python scripts/audit_v14_maps.py --write     # 写 docs/v14/map-audit.md/.json

不改 V10 规则、不新增 seed、不修改历史 trace。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v14.map_audit import (  # noqa: E402
    map_audit_markdown,
    map_audit_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = map_audit_report(load_v12_history())
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "map-audit.md").write_text(
            map_audit_markdown(report), encoding="utf-8", newline="\n"
        )
        (args.out / "map-audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    summary = {
        "six_map_labels": {
            row["map_id"]: row["composite"] for row in report["six_map"]["maps"]
        },
        "six_map_status": {
            row["map_id"]: row["status"] for row in report["six_map"]["maps"]
        },
        "map30_axes": {
            tier["tier"]: tier["bottleneck_axis"] for tier in report["map30"]["tiers"]
        },
        "map30_intervals": {
            item["tier"]: item.get("supported_decisions")
            for item in report["map30_interval"]["intervals"]
        },
        "candidates": {
            item["map_id"]: {
                "runs": item.get("historical_runs"),
                "reflection_candidate": item.get("reflection_candidate"),
            }
            for item in report["candidates"]
        },
        "written": str(args.out / "map-audit.md") if args.write else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
