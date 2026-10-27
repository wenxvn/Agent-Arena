"""V14 LIVE 方案 A 预注册（零请求）。

用法：
    uv run python scripts/plan_v14_live.py --check     # 只校验并打印（默认行为）
    uv run python scripts/plan_v14_live.py --write     # 写 docs/v14/live-plan.md

本脚本**不提交任何实验**、不发任何请求。它只构造规格、校验 seed 白名单、
计算费用区间并输出预注册文档。真正的提交需要 `LiveApproval`，且只能由
`scripts/run_v12_matrix.py --submit` 在用户明确批准后执行。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v14.data_audit import map_unit_costs  # noqa: E402
from agent_arena.lab.v14.live_plan import (  # noqa: E402
    plan_a_markdown,
    plan_a_preflight,
    plan_a_specs,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验（默认行为）：打印矩阵、费用与单因子结论，不写文件",
    )
    args = parser.parse_args()

    unit_costs = map_unit_costs(load_v12_history())
    plan = plan_a_preflight(unit_costs)
    specs = plan_a_specs()
    document = plan_a_markdown(plan)

    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "live-plan.md").write_text(document, encoding="utf-8", newline="\n")
        (args.out / "live-plan.json").write_text(
            json.dumps(
                {
                    "plan": {
                        key: value
                        for key, value in plan.items()
                        if key not in {"checks", "seeds"}
                    },
                    "checks": plan["checks"],
                    "specs": [
                        {
                            "group": item["group"],
                            "arm_id": item["arm_id"],
                            "agent_id": item["agent_id"],
                            "runs": item["runs"],
                            "config_hash": item["config_hash"],
                        }
                        for item in specs
                    ],
                },
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    summary = {
        "status": plan["status"],
        "live_status": plan["live_status"],
        "runs": plan["cost"]["runs"],
        "estimate_cny": plan["cost"]["estimate_cny"],
        "upper_cny": plan["cost"]["upper_cny"],
        "recommended_cap_cny": plan["cost"]["recommended_cap_cny"],
        "all_single_factor": plan["all_single_factor"],
        "all_seeds_valid": plan["all_seeds_valid"],
        "specs": len(specs),
        "external_requests": 0,
        "written": str(args.out / "live-plan.md") if args.write else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
