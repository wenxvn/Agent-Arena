"""V14 LIVE 方案预注册（方案 A，零请求）。

**本模块不提交任何实验、不发任何请求。** 它只做三件事：

1. 用 V14 的**钉住配置**（而不是 V13 的"只覆盖被测开关"）构造两个独立父实验；
2. 按 V12 实测单价重算费用区间，并给出批准上限建议；
3. 生成一份可审阅的预注册清单（模型、矩阵、seed、重复、预算、停止条件、门禁）。

为什么不能直接复用 V13 的 `memory.route_log` 模板：V13 模板只覆盖
``{"route_log": True/False}``，其余配置取注册表默认值，而 `memory.v2` 的默认
``route_mode`` 是 ``env_write``。于是 V13 的 E1-a 实际上把"写入机制"也带进了对照，
与"只变 route_log"不符（V14-02 要求钉住 ``context_only``）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from agent_arena.lab.contracts import (
    AgentArm,
    ComparisonPolicy,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.v13.comparability import single_switch_check
from agent_arena.lab.v14.agent_studies import memory_ablation_plan, memory_arm_configs
from agent_arena.lab.v14.conditions import validate_seed
from agent_arena.lab.v14.planning_study import (
    planning_ablation_plan,
    planning_arm_configs,
)
from agent_arena.lab.v14.reflection_study import (
    reflection_ablation_plan,
    reflection_arm_configs,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER

STATUS_PLANNED = "PLANNED_ONLY"
LIVE_PENDING = "LIVE_PENDING"

#: 方案 A 使用的三组（每组两臂）。
PLAN_A_GROUPS: tuple[str, ...] = ("E1-a", "E2-a", "E3")

#: 默认的批准上限建议（与 ``docs/v13/live-budget-proposal.md`` 修正版一致）。
RECOMMENDED_CAP_CNY = Decimal("5.00")

#: 单局硬上限（fail-closed 护栏，不是期望值）。
PER_RUN_LIMITS: dict[str, Any] = {
    "per_run_request_cap": 90,
    "per_run_decision_cap": 90,
    "per_run_input_token_cap": 200_000,
    "per_run_cost_cap_cny": Decimal("0.50"),
}

STOP_RULES: tuple[str, ...] = (
    "任一局 unknown_spend → 立即停止整个批次并封账，不自动重试",
    "累计结算达批准上限的 90% → 停止未开始的子局",
    "Provider 连续 3 次错误 → 停止",
    "发现契约/接口缺陷 → 停止，先写 DCR，修复后用新版本实验，不污染原计划",
    "实际平均单局费用超过预估 2 倍 → 停止并重新申请",
    "reflection_on 臂全部 0 触发 → 停止并记 NO_TREATMENT_EXPOSURE（改阈值须另立版本）",
)

def _arms_for_group(group: str) -> list[dict[str, Any]]:
    for factory in (memory_arm_configs, planning_arm_configs, reflection_arm_configs):
        arms = [arm for arm in factory() if arm["group"] == group]
        if arms:
            return arms
    raise KeyError(f"未注册的消融组：{group}")

def plan_a_arms() -> dict[str, list[dict[str, Any]]]:
    """方案 A 的三组臂（每组两臂：control / treatment）。"""

    selected: dict[str, list[dict[str, Any]]] = {}
    for group in PLAN_A_GROUPS:
        arms = _arms_for_group(group)
        if group == "E3":
            # 三臂设计里取 disabled 与 reflection_on（两臂子集 = 18 局）
            keep = {"E3-control", "E3-treatment"}
            arms = [arm for arm in arms if arm["arm_id"] in keep]
        if len(arms) != 2:
            raise ValueError(f"组 {group} 应有 2 臂，实际 {len(arms)}")
        selected[group] = arms
    return selected

def plan_a_single_factor_checks() -> list[dict[str, Any]]:
    checks = []
    for group, arms in plan_a_arms().items():
        check = single_switch_check(arms[0], arms[1])
        checks.append(
            {
                "group": group,
                "control": arms[0]["arm_id"],
                "treatment": arms[1]["arm_id"],
                "agent_id": arms[0]["agent_id"],
                "ok": check.ok,
                "manipulated_variable": check.manipulated_variable,
                "changed_keys": list(check.changed_keys),
                "reasons": list(check.reasons),
            }
        )
    return checks

def _budget(runs: int) -> ExperimentBudget:
    return ExperimentBudget(
        per_run_request_cap=PER_RUN_LIMITS["per_run_request_cap"],
        per_run_decision_cap=PER_RUN_LIMITS["per_run_decision_cap"],
        per_run_input_token_cap=PER_RUN_LIMITS["per_run_input_token_cap"],
        per_run_cost_cap_cny=PER_RUN_LIMITS["per_run_cost_cap_cny"],
        experiment_request_cap=PER_RUN_LIMITS["per_run_request_cap"] * runs,
        experiment_cost_cap_cny=RECOMMENDED_CAP_CNY,
    )

def plan_a_specs(
    *,
    maps: dict[str, list[str]] | None = None,
    seeds: list[int] | None = None,
    replicates: int = 3,
    mode: ExperimentMode = ExperimentMode.SIMULATED,
    provider_id: str = SIMULATED_PROVIDER,
    model: str = SIMULATED_MODEL,
) -> list[dict[str, Any]]:
    """构造方案 A 的 6 个父实验规格（**只构造，不执行**）。

    默认 ``mode=SIMULATED``：这样即使有人误跑，也不会产生真实请求。
    """

    map_by_group = maps or {"E1-a": ["MAP-22"], "E2-a": ["MAP-16"], "E3": ["MAP-22"]}
    seed_list = seeds or [0, 1, 2]
    specs: list[dict[str, Any]] = []
    for group, arms in plan_a_arms().items():
        runs = len(arms) * len(map_by_group[group]) * len(seed_list) * replicates
        for arm in arms:
            spec = ExperimentSpec(
                name=f"v14-{group} · {arm['arm_id']}",
                notes=(
                    f"V14 方案 A 预注册（{STATUS_PLANNED}）。"
                    f"组 {group}，臂 {arm['arm_id']}，被操纵变量见组定义；"
                    "本规格不构成执行授权。"
                ),
                maps=list(map_by_group[group]),
                environment_seeds=list(seed_list),
                agent_arms=[
                    AgentArm(
                        agent_id=arm["agent_id"],
                        config=dict(arm["config"]),
                        label=arm["arm_id"],
                    )
                ],
                provider_id=provider_id,
                model=model,
                mode=mode,
                budget=_budget(runs),
                comparison=ComparisonPolicy(min_paired_samples=replicates),
                replicates=replicates,
                experiment_kind="ablation",
            )
            specs.append(
                {
                    "group": group,
                    "arm_id": arm["arm_id"],
                    "agent_id": arm["agent_id"],
                    "maps": list(map_by_group[group]),
                    "seeds": list(seed_list),
                    "replicates": replicates,
                    "runs": runs // len(arms),
                    "config_hash": spec.agent_arms[0].config_hash,
                    "spec": spec,
                }
            )
    return specs

def plan_a_seed_audit() -> list[dict[str, Any]]:
    """逐组检查 seed 是否都在白名单内（绝不编造 seed）。"""

    rows = []
    for group in plan_a_arms():
        maps = {"E1-a": ["MAP-22"], "E2-a": ["MAP-16"], "E3": ["MAP-22"]}[group]
        for map_id in maps:
            for seed in (0, 1, 2):
                check = validate_seed(map_id, seed)
                rows.append(
                    {
                        "group": group,
                        "map_id": map_id,
                        "seed": seed,
                        "valid": check["valid"],
                        "allowed": check["allowed"],
                    }
                )
    return rows

def plan_a_cost_estimate(
    unit_costs: dict[str, dict[str, float]], *, margin: float = 1.5
) -> dict[str, Any]:
    """按 V12 实测单价估算费用（含 1.5 倍余量），并给出上界。"""

    per_run = {map_id: float(item["cost_cny"]) for map_id, item in unit_costs.items()}
    groups = []
    total_runs = 0
    total_estimate = 0.0
    total_upper = 0.0
    for group, arms in plan_a_arms().items():
        map_id = {"E1-a": "MAP-22", "E2-a": "MAP-16", "E3": "MAP-22"}[group]
        runs = len(arms) * 3 * 3
        unit = per_run.get(map_id)
        estimate = None if unit is None else round(runs * unit * margin, 2)
        upper = round(runs * float(PER_RUN_LIMITS["per_run_cost_cap_cny"]), 2)
        groups.append(
            {
                "group": group,
                "map_id": map_id,
                "runs": runs,
                "unit_cost_cny": None if unit is None else round(unit, 8),
                "estimate_cny": estimate,
                "upper_cny": upper,
            }
        )
        total_runs += runs
        total_estimate += estimate or 0.0
        total_upper += upper
    return {
        "groups": groups,
        "runs": total_runs,
        "estimate_cny": round(total_estimate, 2),
        "upper_cny": round(total_upper, 2),
        "recommended_cap_cny": float(RECOMMENDED_CAP_CNY),
        "margin": margin,
        "note": (
            "预估 = 子局数 × V12 实测均价 × 1.5；上界 = 子局数 × 单局硬上限。"
            "上界远高于预估是 fail-closed 护栏，不是期望花费。"
        ),
    }

def plan_a_preflight(
    unit_costs: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """方案 A 的零请求预注册总表。"""

    arms = plan_a_arms()
    checks = plan_a_single_factor_checks()
    seeds = plan_a_seed_audit()
    cost = plan_a_cost_estimate(unit_costs or {})
    sub_plans = {
        "memory": memory_ablation_plan(),
        "planning": planning_ablation_plan(),
        "reflection": reflection_ablation_plan(),
    }
    return {
        "schema": "v14-live-plan-a-1",
        "status": STATUS_PLANNED,
        "live_status": LIVE_PENDING,
        "groups": list(arms),
        "arms": {group: [arm["arm_id"] for arm in items] for group, items in arms.items()},
        "checks": checks,
        "all_single_factor": all(item["ok"] for item in checks),
        "combination_contrasts": [
            {
                "group": "E3",
                "kind": "COMBINATION_CONTRAST",
                "note": (
                    "E3 的 disabled→reflection_on 同时改「触发判定 + 是否请求 + 是否注入」，"
                    "只能作为机制级组合对照；单因子结论需另跑 "
                    "E3-trigger-only → E3-treatment（同样 18 局）。"
                ),
            }
        ],
        "seeds": seeds,
        "all_seeds_valid": all(item["valid"] for item in seeds),
        "cost": cost,
        "limits": {
            **{key: str(value) for key, value in PER_RUN_LIMITS.items()},
        },
        "stop_rules": list(STOP_RULES),
        "sub_plans": {
            name: {
                "runs": plan["runs"],
                "status": plan["status"],
                "live_status": plan["live_status"],
            }
            for name, plan in sub_plans.items()
        },
        "approval_required": (
            "需用户明确批准：模型名、实验矩阵、总费用上限、每局请求/token/费用阈值、"
            "未知 usage 处理与停止条件。未获批不得提交任何 LIVE 请求。"
        ),
        "no_go_note": (
            "V12 的 ¥6 历史授权已结束，剩余额度不延续；V14 不沿用旧 LiveApproval。"
        ),
    }

def plan_a_markdown(plan: dict[str, Any]) -> str:
    cost = plan["cost"]
    lines = [
        "# V14 LIVE 方案 A 预注册（`PLANNED_ONLY`）",
        "",
        "> **本文件不构成执行授权。** V14 新增真实付费请求：**0**。",
        "> V12 的 ¥6 授权已结束，剩余额度不延续；本方案需要用户对"
        "「模型 / 矩阵 / 总费用上限」逐项批准。",
        "",
        "## 1. 矩阵（54 局）",
        "",
        "| 组 | 地图 | 臂 | 单臂子局 | 组子局 | 被操纵变量 | 单开关 |",
        "|---|---|---|---:|---:|---|---|",
    ]
    checks = {item["group"]: item for item in plan["checks"]}
    for row in cost["groups"]:
        check = checks[row["group"]]
        lines.append(
            f"| {row['group']} | {row['map_id']} | "
            f"{' / '.join(plan['arms'][row['group']])} | {row['runs'] // 2} | "
            f"{row['runs']} | `{check['manipulated_variable']}` | "
            f"{'是' if check['ok'] else '**否**'} |"
        )
    lines += [
        f"| **合计** | | | | **{cost['runs']}** | | "
        f"{'配置层单开关' if plan['all_single_factor'] else '**存在多开关**'} |",
        "",
        "seed：0 / 1 / 2（每组），重复：3 次独立观测。",
        "",
        "> **E3 的读法**：`disabled → reflection_on` 只差 `enabled` 一个配置键，"
        "但它同时开启「触发判定 + 反思请求 + 建议注入」，所以是**机制级组合对照**；"
        "要回答「反思请求本身有没有用」，需改跑 `trigger_only → reflection_on`（同样 18 局）。",
        "",
        f"seed 白名单校验：{'全部合法' if plan['all_seeds_valid'] else '**存在非法 seed**'}。",
        "",
        "## 2. 费用",
        "",
        "| 组 | 子局 | V12 实测均价 CNY/局 | 预估 CNY（×1.5） | 上界 CNY |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in cost["groups"]:
        lines.append(
            f"| {row['group']} | {row['runs']} | {row['unit_cost_cny']} | "
            f"{row['estimate_cny']} | {row['upper_cny']} |"
        )
    lines += [
        f"| **合计** | **{cost['runs']}** | — | **{cost['estimate_cny']}** | "
        f"**{cost['upper_cny']}** |",
        "",
        f"- 建议批准上限：**¥{cost['recommended_cap_cny']}**（高于预估，低于上界）。",
        f"- {cost['note']}",
        "",
        "## 3. 单局硬上限",
        "",
        "| 项 | 值 |",
        "|---|---|",
    ]
    for key, value in plan["limits"].items():
        lines.append(f"| `{key}` | {value} |")
    lines += [
        "",
        "## 4. 停止条件",
        "",
    ]
    lines += [f"{index}. {rule}" for index, rule in enumerate(plan["stop_rules"], 1)]
    lines += [
        "",
        "## 5. 子计划状态",
        "",
        "| 子计划 | 子局 | 状态 | 真实收益 |",
        "|---|---:|---|---|",
    ]
    for name, sub in plan["sub_plans"].items():
        lines.append(
            f"| {name} | {sub['runs']} | `{sub['status']}` | `{sub['live_status']}` |"
        )
    lines += [
        "",
        "## 6. 批准要求",
        "",
        f"- {plan['approval_required']}",
        f"- {plan['no_go_note']}",
        "",
        "## 7. 零请求预检命令",
        "",
        "```bash",
        "# 只构造规格并打印，不提交（默认即预检模式）",
        "uv run python scripts/plan_v14_live.py --check",
        "",
        "# 单因子消融的 V13 预检入口（同样默认不提交）",
        "uv run python scripts/run_v12_matrix.py --ablation memory.route_log \\",
        "    --maps MAP-22 --seeds 0 1 2 --replicates 3 \\",
        "    --provider simulated_scripted --decisions 90 --requests 90",
        "```",
        "",
        "> V14 的三组臂使用**钉住配置**（例如 E1-a 固定 `route_mode=context_only`），"
        "与 V13 模板的默认值不同；因此正式提交时必须用 V14 规格，不能直接复用 V13 模板。",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "LIVE_PENDING",
    "PER_RUN_LIMITS",
    "PLAN_A_GROUPS",
    "RECOMMENDED_CAP_CNY",
    "STATUS_PLANNED",
    "STOP_RULES",
    "plan_a_arms",
    "plan_a_cost_estimate",
    "plan_a_markdown",
    "plan_a_preflight",
    "plan_a_seed_audit",
    "plan_a_single_factor_checks",
    "plan_a_specs",
]
