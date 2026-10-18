"""V10 多 seed 基线套件：Oracle、legal_random（每 seed 20 policy seed）、启发式与消融。

用法：
    python -m agent_arena.v10.baselines.suite MAP-03 MAP-18   # 指定 V10 地图
    python -m agent_arena.v10.baselines.suite                 # 全部已有 V10 运行时的地图

输出 ``runs/v10/baselines/MAP-XX.json``（逐局摘要，不含动作明细）与 ``summary.json``；
Oracle 动作明细另存 ``runs/v10/oracle/MAP-XX-seedN.json``。
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from typing import Any

from agent_arena.v10.baselines.runner import (
    LegalRandomPolicy,
    run_actions,
    run_policy,
)
from agent_arena.v10.paths import V10_RUNS
from agent_arena.v10.runtime.catalog import (
    LEVEL_OF,
    V10_MAPS,
    create_environment,
    scenario_record,
    seed_space,
)

BUDGETS = {"简单": 30, "中等": 38, "困难": 46}
#: 每 tick 需要多条控制指令的地图使用更大的决策预算。
BUDGET_OVERRIDES = {"MAP-12": 60, "MAP-19": 60}
RANDOM_POLICY_SEEDS = tuple(range(20))


def decision_budget(map_id: str) -> int:
    return BUDGET_OVERRIDES.get(map_id, BUDGETS[LEVEL_OF[map_id]])


def baseline_module(map_id: str) -> Any:
    return importlib.import_module(f"agent_arena.v10.baselines.map{map_id[-2:]}")


def _make(factory: type, policy_seed: int) -> Any:
    parameters = inspect.signature(factory).parameters
    return factory(seed=policy_seed) if "seed" in parameters else factory()


def run_map(map_id: str, *, seeds: tuple[int, ...] | None = None) -> dict[str, Any]:
    module = baseline_module(map_id)
    budget = decision_budget(map_id)
    seeds = seeds or seed_space(map_id)
    payload: dict[str, Any] = {
        "map_id": map_id,
        "decision_budget": budget,
        "environment_seeds": list(seeds),
        "scenarios": {},
        "oracle": [],
        "public_heuristic": [],
        "ablations": {},
        "legal_random": [],
    }
    oracle_dir = V10_RUNS / "oracle"
    oracle_dir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        payload["scenarios"][str(seed)] = scenario_record(map_id, seed)
        actions = module.oracle_actions(seed)
        oracle = run_actions(map_id, actions, environment_seed=seed)
        (oracle_dir / f"{map_id}-seed{seed}.json").write_text(
            oracle.to_json() + "\n", encoding="utf-8"
        )
        summary = oracle.summary()
        summary["within_budget"] = len(actions) <= budget
        payload["oracle"].append(summary)
        payload["public_heuristic"].append(
            run_policy(
                map_id,
                module.HEURISTIC(),
                environment_seed=seed,
                decision_budget=budget,
                keep_actions=False,
            ).summary()
        )
        for name, factory in module.ABLATIONS.items():
            payload["ablations"].setdefault(name, []).append(
                run_policy(
                    map_id,
                    _make(factory, 0),
                    environment_seed=seed,
                    decision_budget=budget,
                    keep_actions=False,
                ).summary()
            )
        shapes = create_environment(map_id, environment_seed=seed).SHAPES
        for policy_seed in RANDOM_POLICY_SEEDS:
            payload["legal_random"].append(
                run_policy(
                    map_id,
                    LegalRandomPolicy(shapes, policy_seed),
                    environment_seed=seed,
                    policy_seed=policy_seed,
                    decision_budget=budget,
                    keep_actions=False,
                ).summary()
            )
    return payload


def condense(payload: dict[str, Any]) -> dict[str, Any]:
    def rate(rows: list[dict[str, Any]]) -> str:
        return f"{sum(1 for row in rows if row['success'])}/{len(rows)}"

    def mean_primary(rows: list[dict[str, Any]]) -> float | None:
        values = [
            float(row["primary_value"])
            for row in rows
            if row["primary_state"] == "VALID" and row["primary_value"] is not None
        ]
        return round(sum(values) / len(values), 4) if values else None

    return {
        "environment_seeds": payload["environment_seeds"],
        "oracle": rate(payload["oracle"]),
        "oracle_within_budget": all(row["within_budget"] for row in payload["oracle"]),
        "oracle_mechanism_triggered": rate(
            [{"success": bool(row["mechanism_triggered"])} for row in payload["oracle"]]
        ),
        "public_heuristic": rate(payload["public_heuristic"]),
        "ablations": {name: rate(rows) for name, rows in payload["ablations"].items()},
        "ablation_primary_mean": {
            name: mean_primary(rows) for name, rows in payload["ablations"].items()
        },
        "heuristic_primary_mean": mean_primary(payload["public_heuristic"]),
        "legal_random": rate(payload["legal_random"]),
        "legal_random_primary_mean": mean_primary(payload["legal_random"]),
        "unique_scenario_hashes": len(
            {item["scenario_hash"] for item in payload["scenarios"].values()}
        ),
    }


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    map_ids = [item for item in args if item in V10_MAPS] or sorted(V10_MAPS)
    output = V10_RUNS / "baselines"
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "summary.json"
    summary: dict[str, Any] = (
        json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    )
    for map_id in map_ids:
        payload = run_map(map_id)
        (output / f"{map_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
        )
        summary[map_id] = condense(payload)
        print(map_id, json.dumps(summary[map_id], ensure_ascii=False), flush=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
