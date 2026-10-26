"""V13 数据与费用审计：本地账本只读核验 + 可选后台账单对账。

用法：
    # 只做本地审计（默认，零网络）
    uv run python scripts/audit_v13_ledger.py --write

    # 提供脱敏账单 CSV 时才对账（文件只在本地读取）
    uv run python scripts/audit_v13_ledger.py --bill path/to/bill.csv --write

输出：``docs/v13/data-and-cost-audit.md`` 与同名 ``.json``。
**不修改**任何账本条目；发现差异只记录。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.lab.v13.ledger import (  # noqa: E402
    audit_ledger,
    ledger_markdown,
    read_ledger,
    reconcile_bill,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=WEB_RUNS / "_ledger" / "web_ledger.jsonl")
    parser.add_argument("--lab-dir", type=Path, default=LAB_RUNS)
    parser.add_argument("--web-dir", type=Path, default=WEB_RUNS)
    parser.add_argument("--bill", type=Path, default=None, help="脱敏后台账单 CSV")
    parser.add_argument("--currency", default="CNY")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v13")
    parser.add_argument("--write", action="store_true", help="写出 Markdown/JSON 报告")
    args = parser.parse_args()

    audit = audit_ledger(
        ledger_path=args.ledger, lab_dir=args.lab_dir, web_dir=args.web_dir
    )
    rows = read_ledger(args.ledger)
    reconciliation = reconcile_bill(
        audit, args.bill, ledger_rows=rows, currency=args.currency
    )
    payload = {**audit.as_dict(), "reconciliation": reconciliation}
    markdown = ledger_markdown(audit, reconciliation)
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "data-and-cost-audit.md").write_text(
            markdown, encoding="utf-8", newline="\n"
        )
        (args.out / "data-and-cost-audit.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "entries": audit.entries,
                "started": audit.started,
                "settled": audit.settled,
                "requests": audit.requests,
                "cost_settled_cny": audit.cost_settled_cny,
                "unknown_spend_runs": len(audit.unknown_spend_runs),
                "orphan_runs": len(audit.orphan_runs),
                "duplicate_settlements": len(audit.duplicate_settlements),
                "parents": audit.parents,
                "child_links": audit.child_links,
                "issues": audit.issues,
                "reconciliation": reconciliation.get("status"),
                "written": str(args.out) if args.write else None,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
