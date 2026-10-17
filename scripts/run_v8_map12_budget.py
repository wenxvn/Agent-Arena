"""MAP-12 预算修复重跑：decision_budget=60（30 天 × 2 劳动槽）。

旧 46 预算的三局无法完成 30 天，已标记 superseded。本脚本在独立账本
`runs/v8/supplement_006/` 中重跑 MAP-12 R0–R2，其余设置不变。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
SUPPLEMENT = V8 / "supplement_006"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v8_90 as base  # noqa: E402

from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.v8.budget import V8BudgetClosed, V8BudgetLedger  # noqa: E402
from agent_arena.v8.runner import V8EpisodeSpec, V8Runner  # noqa: E402


def main() -> int:
    if (SUPPLEMENT / "ledger.jsonl").exists():
        raise SystemExit("supplement_006 ledger already exists; refusing to reuse.")
    freeze = base.read_json(base.FREEZE_PATH)
    base.verify_freeze(freeze)
    settings = base.settings_for_run()
    ledger = V8BudgetLedger(
        SUPPLEMENT / "ledger.jsonl",
        currency="CNY",
        model=base.MODEL_NAME,
        source_hashes=base.ledger_source_hashes(),
    )
    provider = OpenAIDecisionProvider(settings)
    results = []
    for replicate in range(3):
        spec = V8EpisodeSpec("MAP-12", replicate, 60)
        runner = V8Runner(
            provider=provider,
            settings=settings,
            ledger=ledger,
            output_dir=SUPPLEMENT / "experiments",
            commit=freeze["commit"],
            progress=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True),
        )
        print(
            f"RUN MAP-12 R{replicate} budget=60 supplement=True",
            flush=True,
        )
        try:
            episode = runner.run(spec)
        except V8BudgetClosed as exc:
            print(f"STOP: {exc}", flush=True)
            ledger.close("RUNTIME_BUDGET_CLOSED", map_id="MAP-12")
            return 2
        results.append(episode)
        print(
            f"DONE MAP-12 R{replicate} status={episode['status']}"
            f" success={episode['success']} cost={episode['usage']['cost']}",
            flush=True,
        )
        if episode["status"] in base.FATAL_OUTCOMES:
            print(f"STOP: fatal outcome {episode['status']}", flush=True)
            return 2
    (SUPPLEMENT / "experiments").mkdir(parents=True, exist_ok=True)
    (SUPPLEMENT / "experiments" / "run_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "v8_map12_budget_fix_v1",
                "freeze_hash": freeze["freeze_hash"],
                "commit": freeze["commit"],
                "map_id": "MAP-12",
                "decision_budget": 60,
                "episodes": [
                    {
                        "replicate_id": item["replicate_id"],
                        "run_id": item["run_id"],
                        "status": item["status"],
                        "success": item["success"],
                    }
                    for item in results
                ],
                "ledger": ledger.snapshot(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(ledger.snapshot(), ensure_ascii=False))
    return 0 if len(results) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
