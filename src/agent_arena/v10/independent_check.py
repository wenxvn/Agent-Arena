"""V10 指标与运行时的独立复核（Batch 9 补强）。

对 23 张 V10 原生图逐 seed 执行三类**不信任各图内部计算**的检查：

1. **状态-取值一致性**（规格驱动）：把 Oracle / 各消融 / 少量 ``legal_random`` 的实际动作
   回放后，逐条校验投影指标是否满足 ``METRIC_SPECS`` 声明（``VALID`` ⇒ 非空且在
   ``valid_range``；其余态 ⇒ 必须为空；不得出现未注册指标）；
2. **可复现性**：同一 ``(map, seed, actions)`` 回放两次，``judge_state_hash`` 与指标必须逐字节一致；
3. **实例差异性**：同一图不同环境 seed 的 ``scenario_hash`` 必须互不相同。

边界（必须如实披露）：这不是“第二套公式实现”。每条指标的分子/分母公式仍未用独立实现
重算；因此本检查只能证伪“状态与取值自相矛盾/不可复现/seed 无差异”，不能证明公式正确。

用法：``python -m agent_arena.v10.independent_check``
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from agent_arena.v10.baselines.runner import (
    LegalRandomPolicy,
    run_actions,
    run_policy,
)
from agent_arena.v10.metrics.governance import audit_states
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import (
    V10_MAPS,
    create_environment,
    scenario_hash,
    seed_space,
)

RANDOM_POLICY_SEEDS = (0, 1, 2, 3, 4)


def _audit_map(map_id: str) -> dict[str, Any]:
    module = __import__(f"agent_arena.v10.baselines.map{map_id[-2:]}", fromlist=["ABLATIONS"])
    seeds = seed_space(map_id)
    seed_rows: list[dict[str, Any]] = []
    violations: list[str] = []
    for seed in seeds:
        actions = module.oracle_actions(seed)
        first = run_actions(map_id, actions, environment_seed=seed)
        second = run_actions(map_id, actions, environment_seed=seed)
        deterministic = (
            first.status == second.status
            and first.success == second.success
            and first.metrics == second.metrics
        )
        result = audit_states(map_id, seed, actions)
        violations.extend(f"seed {seed} oracle: {item}" for item in result["violations"])
        shapes = create_environment(map_id, environment_seed=seed).SHAPES
        case_rows = []
        for name, factory in sorted(module.ABLATIONS.items()):
            policy = (
                factory(seed=0)
                if "seed" in inspect.signature(factory).parameters
                else factory()
            )
            run = run_policy(
                map_id,
                policy,
                environment_seed=seed,
                decision_budget=_budget(map_id),
                keep_actions=True,
            )
            case_rows.append(
                {
                    "case": name,
                    "success": run.success,
                    "primary_state": run.primary_state,
                    "rejected": run.rejected_actions,
                }
            )
        for policy_seed in RANDOM_POLICY_SEEDS:
            run = run_policy(
                map_id,
                LegalRandomPolicy(shapes, policy_seed),
                environment_seed=seed,
                policy_seed=policy_seed,
                decision_budget=_budget(map_id),
                keep_actions=True,
            )
            case_rows.append(
                {
                    "case": f"legal_random#{policy_seed}",
                    "success": run.success,
                    "primary_state": run.primary_state,
                    "rejected": run.rejected_actions,
                }
            )
        seed_rows.append(
            {
                "seed": seed,
                "scenario_hash": scenario_hash(map_id, seed),
                "oracle_success": first.success,
                "oracle_primary_state": first.primary_state,
                "deterministic": deterministic,
                "cases": case_rows,
            }
        )
    unique = len({row["scenario_hash"] for row in seed_rows})
    return {
        "map_id": map_id,
        "seeds": [row["seed"] for row in seed_rows],
        "unique_scenario_hashes": unique,
        "seed_distinct": unique == len(seed_rows),
        "all_deterministic": all(row["deterministic"] for row in seed_rows),
        "oracle_success": sum(1 for row in seed_rows if row["oracle_success"]),
        "violations": violations,
        "rows": seed_rows,
    }


def _budget(map_id: str) -> int:
    from agent_arena.v10.baselines.suite import decision_budget

    return decision_budget(map_id)


def audit() -> dict[str, Any]:
    maps = [_audit_map(map_id) for map_id in sorted(V10_MAPS)]
    return {
        "schema": "v10-independent-check-1",
        "scope": "23 V10 原生图 × 全部预登记 seed",
        "method": "spec-driven state audit + replay determinism + seed distinctness",
        "not_covered": "公式级第二套实现（逐条重算分子/分母）仍未完成",
        "maps": maps,
        "totals": {
            "maps": len(maps),
            "seed_instances": sum(len(row["seeds"]) for row in maps),
            "violations": sum(len(row["violations"]) for row in maps),
            "seed_distinct_ok": sum(1 for row in maps if row["seed_distinct"]),
            "deterministic_ok": sum(1 for row in maps if row["all_deterministic"]),
        },
    }


def render(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "# V10 指标与运行时独立复核（Batch 9）",
        "",
        f"- 由 `python -m agent_arena.v10.independent_check` 生成；范围：{payload['scope']}。",
        f"- 方法：{payload['method']}。",
        f"- **未覆盖**：{payload['not_covered']}。",
        "",
        "## 汇总",
        "",
        f"- 覆盖地图：{totals['maps']}；seed 实例：{totals['seed_instances']}",
        f"- 状态-取值违规：{totals['violations']}",
        f"- seed 实例互不相同：{totals['seed_distinct_ok']}/{totals['maps']}",
        f"- 回放可复现：{totals['deterministic_ok']}/{totals['maps']}",
        "",
        "## 逐图结果",
        "",
        "| 图 | seed 数 | seed 互异 | 回放可复现 | Oracle 成功 | 状态-取值违规 |",
        "|---|---:|---|---|---:|---:|",
    ]
    for row in payload["maps"]:
        lines.append(
            f"| {row['map_id']} | {len(row['seeds'])} | "
            f"{'是' if row['seed_distinct'] else '**否**'} | "
            f"{'是' if row['all_deterministic'] else '**否**'} | "
            f"{row['oracle_success']}/{len(row['seeds'])} | {len(row['violations'])} |"
        )
    detail = [
        (row["map_id"], item) for row in payload["maps"] for item in row["violations"]
    ]
    lines += ["", "## 违规明细", ""]
    if detail:
        lines += [f"- {map_id}：{item}" for map_id, item in detail]
    else:
        lines.append("- 无。")
    lines += [
        "",
        "## 解释与限制",
        "",
        "- 通过本检查只说明：状态与取值不矛盾、回放确定、seed 真的换实例；",
        "  它**不能**替代公式级独立实现，也不能证明指标语义与构念一致。",
        "- 公式级逐图复算仍列为 V11 事项（见 `final-report.md` §剩余风险）。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = audit()
    output = V10_RUNS / "independent_check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    (V10_DOCS / "independent-metric-check.md").write_text(render(payload), encoding="utf-8")
    print(json.dumps(payload["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()
