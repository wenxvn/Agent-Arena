"""V9 MiMo 单局 smoke：真实 API、独立 smoke 账本、1 个 episode。

用法：python scripts/v9_smoke.py [MAP-21]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v9_mimo as base  # noqa: E402

from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.v9.budget import V9BudgetLedger  # noqa: E402
from agent_arena.v9.runner import V9EpisodeSpec, V9Runner  # noqa: E402


def main() -> int:
    map_id = sys.argv[1] if len(sys.argv) > 1 else "MAP-21"
    root = ROOT / "runs" / "v9" / "smoke"
    ledger_path = root / "ledger.jsonl"
    if ledger_path.exists():
        raise SystemExit("smoke 账本已存在；请换目录或先人工归档。")
    settings = base.settings_for_run()
    ledger = V9BudgetLedger(
        ledger_path,
        currency="CNY",
        model=base.MODEL_NAME,
        source_hashes=base.ledger_source_hashes(),
    )
    runner = V9Runner(
        provider=OpenAIDecisionProvider(settings),
        settings=settings,
        ledger=ledger,
        output_dir=root / "experiments",
        commit="smoke",
        progress=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True),
    )
    result = runner.run(
        V9EpisodeSpec(map_id, 0, 46, arm="v9_fixed", hypothesis="smoke")
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "success": result["success"],
                "termination_reason": result["termination_reason"],
                "decision_count": result["decision_count"],
                "cost": result["usage"]["cost"],
                "ledger": ledger.snapshot(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
