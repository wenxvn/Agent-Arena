"""打印一张图的 V9 证据包摘要，供逐图审计引用。

用法：`python scripts/v9_show_map.py MAP-07 [--full]`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _short(value: object, limit: int = 300) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("map_id")
    parser.add_argument("--full", action="store_true", help="打印完整 delta")
    args = parser.parse_args()
    path = ROOT / "runs" / "v9" / "evidence" / f"{args.map_id}.json"
    pack = json.loads(path.read_text(encoding="utf-8"))
    print(f"# {pack['map_id']} {pack['title']} [{pack['world']}/{pack['difficulty']}] "
          f"condition={pack['condition_id']}")
    print(pack["docstring"])
    print("metrics:", ", ".join(spec["metric_id"] for spec in pack["metric_specs"]))
    for run in pack["runs"]:
        print()
        print(f"== R{run['replicate_id']} {run['run_id']} status={run['status']} "
              f"success={run['success']} terminal={run['termination_reason']} "
              f"decisions={run['decision_rows']}/{run['decision_budget']}")
        print("failure_codes:", run["failure_codes"])
        print("judge_metrics:", _short(run["judge_metrics"]))
        print("projected:", _short(run["projected_metrics"]))
        print("initial:", _short(run["initial_observation"], 1200))
        for step in run["steps"]:
            delta = step["delta"] if args.full else _short(step["delta"], 400)
            print(
                f"  {step['i']:>2} {_short(step['action'], 220)} -> {step['result']} | {delta}"
            )
        print("final:", _short(run["final_observation"], 800))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
