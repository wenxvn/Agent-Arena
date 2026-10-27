"""V14 数据口径审计（只读历史 CSV，零外部请求）。

用法：
    uv run python scripts/audit_v14_data.py            # 只打印摘要
    uv run python scripts/audit_v14_data.py --write    # 写 docs/v14/ 并修正 V13 效度表

输出：
- ``docs/v14/data-validity.md``：UNKNOWN/0 分离、协议隔离、六图差异、预算表算术复核；
- ``docs/v14/data-validity.json``：同上机读版；
- ``docs/v13/map-validity.md``：**口径修正版**（原表把未知字段渲染成 0/N）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v13.validity import (  # noqa: E402
    map30_ladder,
    map30_markdown,
    six_map_audit,
    validity_markdown,
)
from agent_arena.lab.v14.data_audit import (  # noqa: E402
    budget_proposal_markdown,
    data_validity_markdown,
    data_validity_report,
    validity_diff_markdown,
)

CORRECTION_NOTE = (
    "> **V14 口径修正（2026-10-27）**：本表的\"机制触发局\"列在 V13 生成时直接用\n"
    "> `mechanism_triggered_runs / runs` 渲染，而 V12 历史 CSV **没有** "
    "`mechanism_triggered` 列，\n"
    "> 于是\"未观测\"被打印成 `0/N`。V14 已改为"
    "`observed_true / observed`，全未知显示\n"
    "> `UNKNOWN (0 observed)`。原始历史数据未修改；差异表见 "
    "`docs/v14/data-validity.md`。\n"
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    records = load_v12_history()
    report = data_validity_report(records)
    audit = six_map_audit(records)
    ladder = map30_ladder(records)

    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "data-validity.md").write_text(
            data_validity_markdown(report), encoding="utf-8", newline="\n"
        )
        (args.out / "data-validity.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (args.out / "validity-diff.md").write_text(
            validity_diff_markdown(report["validity_diff"]),
            encoding="utf-8",
            newline="\n",
        )
        budget = report.get("budget")
        if budget:
            (args.out / "budget-audit.md").write_text(
                budget_proposal_markdown(budget), encoding="utf-8", newline="\n"
            )
        corrected = validity_markdown(audit).replace(
            "# 六图效度审计（构念层）\n",
            "# 六图效度审计（构念层）\n\n" + CORRECTION_NOTE,
            1,
        )
        (ROOT / "docs" / "v13" / "map-validity.md").write_text(
            corrected, encoding="utf-8", newline="\n"
        )
        (ROOT / "docs" / "v13" / "map30-budget-ladder.md").write_text(
            map30_markdown(ladder), encoding="utf-8", newline="\n"
        )

    summary = {
        "records": len(records),
        "pooled_maps": report["protocol"]["pooled_maps"],
        "trigger_unknown_maps": report["protocol"]["trigger_unknown_maps"],
        "validity_changed_maps": report["validity_diff"]["changed_maps"],
        "budget_totals": (report.get("budget") or {}).get("totals"),
        "declared_total_runs": (report.get("budget") or {}).get("declared_total_runs"),
        "plans": {
            name: {"runs": plan["runs"], "estimate": plan["estimate_cny"]}
            for name, plan in ((report.get("budget") or {}).get("plans") or {}).items()
        },
        "written": str(args.out) if args.write else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
