"""V13 地图效度与 MAP-30 深度分析（只读历史 + 可选本机实验）。

用法：
    uv run python scripts/audit_v13_maps.py --write

输出（``docs/v13/``）：
- ``map-validity.md``：六图构念效度标签与选图建议；
- ``map30-budget-ladder.md``：预算阶梯与失败分型；
- ``capability-profile.md``：机制维度画像（不含 human_approved）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v13.capability import (  # noqa: E402
    capability_markdown,
    capability_profile,
)
from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v13.taxonomy import (  # noqa: E402
    taxonomy_markdown,
    taxonomy_report,
)
from agent_arena.lab.v13.validity import (  # noqa: E402
    map30_ladder,
    map30_markdown,
    six_map_audit,
    validity_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v13")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    records = load_v12_history()
    audit = six_map_audit(records)
    ladder = map30_ladder(records)
    profile = capability_profile(records)
    # 历史 CSV 没有 Finding 明细，因此分层归因只按终态与终局码归类；
    # 报告里必须声明"这是终态级归因，不是证据步级"。
    taxonomy = taxonomy_report(records, findings=[])
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "map-validity.md").write_text(
            validity_markdown(audit), encoding="utf-8", newline="\n"
        )
        (args.out / "map30-budget-ladder.md").write_text(
            map30_markdown(ladder), encoding="utf-8", newline="\n"
        )
        (args.out / "capability-profile.md").write_text(
            capability_markdown(profile), encoding="utf-8", newline="\n"
        )
        (args.out / "diagnosis-taxonomy.md").write_text(
            taxonomy_markdown(taxonomy), encoding="utf-8", newline="\n"
        )
    print(
        json.dumps(
            {
                "records": len(records),
                "labels": {row["map_id"]: row["composite"] for row in audit["maps"]},
                "map30_tiers": [tier["tier"] for tier in ladder["tiers"]],
                "capability": {
                    item["dimension"]: item["evidence_level"]
                    for item in profile["dimensions"]
                },
                "taxonomy_primary": taxonomy["primary_counts"],
                "written": str(args.out) if args.write else None,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
