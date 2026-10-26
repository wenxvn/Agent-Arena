"""V12 提纲 §4.3 附加对照：Memory / Planning / Reflection 的开关消融（真实 API）。

提纲要求的三条附加对照（同策略版本、同基线 prompt、同历史窗口，只切换开关）：

1. Memory 关闭/开启
2. Planning 关闭/开启
3. Reflection 触发/关闭

`condition_key` 不含 config hash，所以同一实验内不能放"同 agent 不同 config"的两个臂。
因此每个开关各建一个独立实验，配对时按 (map, seed) 跨实验对齐——
这些实验的版本指纹完全相同，唯一差异就是被消融的那个开关。

用法：
    uv run python scripts/run_v12_ablations.py              # 只预检并打印矩阵
    uv run python scripts/run_v12_ablations.py --submit     # 真跑（12 局）
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
from agent_arena.lab.experiment import ExperimentService, preflight  # noqa: E402
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402

ABLATIONS: tuple[dict[str, object], ...] = (
    {
        "name": "v12-ablation-memory-on",
        "maps": ["MAP-18"],
        "agent": "memory.v1",
        "config": {"enabled": True},
        "notes": (
            "§4.3-1 Memory 消融（开启）：MAP-18 seed 0/1，"
            "与 v12-ablation-memory-off 按 (map, seed) 配对。"
        ),
    },
    {
        "name": "v12-ablation-memory-off",
        "maps": ["MAP-18"],
        "agent": "memory.v1",
        "config": {"enabled": False},
        "notes": "§4.3-1 Memory 消融（关闭）：唯一变量是 enabled=false。",
    },
    {
        "name": "v12-ablation-planning-on",
        "maps": ["MAP-16"],
        "agent": "planning.v1",
        "config": {"enabled": True},
        "notes": "§4.3-2 Planning 消融（开启）：MAP-16 seed 0/1，Planner 额外请求全部计费。",
    },
    {
        "name": "v12-ablation-planning-off",
        "maps": ["MAP-16"],
        "agent": "planning.v1",
        "config": {"enabled": False},
        "notes": "§4.3-2 Planning 消融（关闭）：唯一变量是 enabled=false。",
    },
    {
        "name": "v12-ablation-reflection-on",
        "maps": ["MAP-16"],
        "agent": "reflection.v1",
        "config": {"enabled": True},
        "notes": "§4.3-3 Reflection 消融（开启）：MAP-16 seed 0/1，触发只能用公开规则。",
    },
    {
        "name": "v12-ablation-reflection-off",
        "maps": ["MAP-16"],
        "agent": "reflection.v1",
        "config": {"enabled": False},
        "notes": "§4.3-3 Reflection 消融（关闭）：唯一变量是 enabled=false。",
    },
)

SEEDS = (0, 1)
PER_RUN_REQUESTS = 90
PER_RUN_COST = Decimal("0.20")
EXPERIMENT_COST = Decimal("0.30")


def _spec(item: dict[str, object]) -> ExperimentSpec:
    maps = list(item["maps"])  # type: ignore[arg-type]
    cells = len(maps) * len(SEEDS)
    return ExperimentSpec(
        name=str(item["name"]),
        notes=str(item["notes"]),
        maps=maps,
        agent_arms=[
            AgentArm(agent_id=str(item["agent"]), config=dict(item["config"]))  # type: ignore[arg-type]
        ],
        environment_seeds=list(SEEDS),
        provider_id="openai_compatible",
        model="mimo-v2.6-flash",
        mode=ExperimentMode.LIVE,
        budget=ExperimentBudget(
            per_run_request_cap=PER_RUN_REQUESTS,
            per_run_decision_cap=PER_RUN_REQUESTS,
            per_run_cost_cap_cny=PER_RUN_COST,
            experiment_request_cap=PER_RUN_REQUESTS * cells,
            experiment_cost_cap_cny=EXPERIMENT_COST,
        ),
        preflight_only=False,
        approval=LiveApproval(
            approved=True,
            approved_by="user",
            max_cost_cny=EXPERIMENT_COST,
            note="沿用用户已批准的 ¥6.00 总预算；本消融预计 ≤ ¥0.35。",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    specs: list[ExperimentSpec] = []
    try:
        for item in ABLATIONS:
            spec = _spec(item)
            result = preflight(spec)
            print(
                json.dumps(
                    {
                        "name": spec.name,
                        "cells": result.cells,
                        "max_cost_cny": str(result.max_cost_cny),
                        "ok": result.ok,
                        "blockers": list(result.blockers),
                    },
                    ensure_ascii=False,
                )
            )
            if not result.ok:
                return 1
            specs.append(spec)
        if not args.submit:
            # 预检不落盘：dry-run 不创建实验目录，避免 runs/lab 里堆 CREATED 空壳。
            print("（未提交；加 --submit 才会创建实验并调用 Provider）")
            return 0
        for spec in specs:
            experiment_id = service.create_experiment(
                spec, idempotency_key=f"ablation:{spec.name}"
            )
            service.submit(experiment_id, resume=True)
            manifest = service.wait(experiment_id, timeout=3_600)
            print(
                json.dumps(
                    {
                        "experiment_id": experiment_id,
                        "name": manifest.name,
                        "state": manifest.state.value,
                        "counts": manifest.counts,
                        "budget": manifest.budget,
                    },
                    ensure_ascii=False,
                )
            )
        return 0
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
