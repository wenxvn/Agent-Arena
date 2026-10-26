"""V12 种子覆盖扩展：把 MAP-16 / MAP-18 的登记 seed 用满。

背景：主矩阵按"六图共同 seed"取 0/1/2。MAP-16 的 `SEED_SPACE` 是 0–3，
MAP-18 是 0–4，因此还有 3 个**已登记但未测**的实例。它们不是新地图、
不是新规则，只是同一张图的不同 seed——补上它们能扩大梯度图的样本量。

用法：
    uv run python scripts/extend_v12_seeds.py            # 只打印计划
    uv run python scripts/extend_v12_seeds.py --submit   # 真跑
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.contracts import (  # noqa: E402
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
    LiveApproval,
)
from agent_arena.lab.experiment import (  # noqa: E402
    ExperimentService,
    preflight,
)
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402

#: 主矩阵已覆盖的 seed。
COVERED = {"MAP-16": (0, 1, 2), "MAP-18": (0, 1, 2)}

EXPERIMENTS = (
    {
        "name": "v12-map16-seed3",
        "maps": ["MAP-16"],
        "seeds": [3],
        "notes": "种子覆盖扩展：MAP-16 的第 4 个登记实例（seed 3），主矩阵只测了 0/1/2。",
    },
    {
        "name": "v12-map18-seed3-4",
        "maps": ["MAP-18"],
        "seeds": [3, 4],
        "notes": "种子覆盖扩展：MAP-18 的第 4/5 个登记实例（seed 3、4），主矩阵只测了 0/1/2。",
    },
)


def _spec(item: dict[str, object]) -> ExperimentSpec:
    return ExperimentSpec(
        name=str(item["name"]),
        notes=str(item["notes"]),
        maps=list(item["maps"]),  # type: ignore[arg-type]
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        environment_seeds=list(item["seeds"]),  # type: ignore[arg-type]
        provider_id="openai_compatible",
        model="mimo-v2.6-flash",
        mode=ExperimentMode.LIVE,
        budget=ExperimentBudget(
            per_run_request_cap=90,
            per_run_decision_cap=90,
            per_run_cost_cap_cny=Decimal("0.20"),
            experiment_request_cap=90 * 3 * 6,
            experiment_cost_cap_cny=Decimal("0.80"),
        ),
        preflight_only=False,
        approval=LiveApproval(
            approved=True,
            approved_by="user",
            max_cost_cny=Decimal("0.80"),
            note="用户已授权 API；本扩展沿用同一总预算（¥6.00）。",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    ids: list[str] = []
    try:
        for item in EXPERIMENTS:
            spec = _spec(item)
            result = preflight(spec)
            print(
                json.dumps(
                    {
                        "name": spec.name,
                        "cells": result.cells,
                        "seeds": list(result.seeds),
                        "max_cost_cny": result.max_cost_cny,
                        "ok": result.ok,
                        "blockers": list(result.blockers),
                    },
                    ensure_ascii=False,
                )
            )
            if not result.ok:
                continue
            experiment_id = service.create_experiment(
                spec, idempotency_key=f"seed-ext:{spec.name}"
            )
            ids.append(experiment_id)
            print("  created:", experiment_id)
        if not args.submit:
            print("（未提交；加 --submit 才会入队）")
            return 0
        # 单 worker 串行：一个实验跑完再提交下一个，否则会被 ExperimentBusy 拒绝。
        for experiment_id in ids:
            service.submit(experiment_id, resume=True)
            manifest = service.wait(experiment_id, timeout=3_600)
            summary = service.summary(experiment_id)
            print(
                json.dumps(
                    {
                        "experiment_id": experiment_id,
                        "state": manifest.state.value,
                        "counts": manifest.counts,
                        "budget": manifest.budget,
                        "executed": summary["executed"],
                        "categories": summary["categories"],
                    },
                    ensure_ascii=False,
                )
            )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps({"experiments": ids}, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
        return 0
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
