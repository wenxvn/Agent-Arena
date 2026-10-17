"""调试单个地图的公开启发式策略。

用法：
    python scripts/v9_try_policy.py MAP-07
    python scripts/v9_try_policy.py MAP-07 --ablation no_memory

只打印公开 Observation 与动作结果；不读取 judge_state。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v9.baseline_run import decision_budget  # noqa: E402
from agent_arena.v9.baselines import run_policy  # noqa: E402
from agent_arena.v9.policies import ablations, heuristics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("map_id")
    parser.add_argument("--ablation", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.ablation:
        factory = ablations().get(args.map_id, {}).get(args.ablation)
    else:
        factory = heuristics().get(args.map_id)
    if factory is None:
        print(f"no policy for {args.map_id} (ablation={args.ablation})")
        return 2
    run = run_policy(
        args.map_id,
        factory(),
        seed=args.seed,
        decision_budget=args.budget or decision_budget(args.map_id),
    )
    print(
        f"{run.map_id} policy={run.policy} status={run.status} success={run.success} "
        f"terminal={run.terminal_reason} decisions={run.decisions} "
        f"invalid={run.invalid_actions} rejected={run.rejected_actions}"
    )
    print("metrics:", json.dumps(run.metrics, ensure_ascii=False))
    if not args.quiet:
        for item in run.actions:
            action = json.dumps(item["action"], ensure_ascii=False)
            print(f"  {item['decision']:>2} {action} -> {item['result']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
