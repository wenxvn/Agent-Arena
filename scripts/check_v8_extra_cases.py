"""补充手算失败/边界用例（不改变 V8 冻结运行时）。

这些用例存放在 `docs/v8/extra-fixtures.json`，原因是正式冻结发生在它们之前；
把它们写进地图模块会改变 `rule_hash`。本脚本只做真实 step 回放与期望值核对，
因此计入离线证据，但不属于冻结运行时的一部分。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.worlds.scenario_v8 import create_environment  # noqa: E402
from agent_arena.worlds.scenario_v8.models import V8Action  # noqa: E402
from agent_arena.worlds.scenario_v8.oracle import normalize_action_payload  # noqa: E402

CASES = ROOT / "docs" / "v8" / "extra-fixtures.json"


def main() -> int:
    cases: dict[str, dict[str, Any]] = json.loads(CASES.read_text(encoding="utf-8"))
    problems: list[str] = []
    for map_id, case in sorted(cases.items()):
        environment = create_environment(map_id, seed=case.get("seed", 0))
        for payload in case["actions"]:
            environment.step(
                V8Action.model_validate(normalize_action_payload(payload), strict=True)
            )
        metrics = environment.metrics()
        for metric_id, expected in case["expect"].items():
            value = metrics.get(metric_id)
            if isinstance(value, dict):
                value = (
                    round(value["numerator"] / value["denominator"], 6)
                    if value["denominator"]
                    else None
                )
            if value != expected:
                problems.append(
                    f"{map_id}/{case['name']}: {metric_id} expected {expected}, got {value}"
                )
        print(
            f"{map_id} {case['name']} status={environment.status.value}"
            f" reason={environment.terminal_reason} metrics={len(case['expect'])}"
        )
    if problems:
        print("FAILED:")
        for problem in problems:
            print(" -", problem)
        return 1
    print(f"EXTRA CASES: OK ({len(cases)} maps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
