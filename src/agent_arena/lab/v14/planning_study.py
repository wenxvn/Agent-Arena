"""V14 Planning 机制研究（P0-5）：触发链、成本归因与三组独立单因子。

本模块零模型请求：用确定性脚本驱动 ``planning.v2``，把每次决策的
"触发 → 是否被 TTL/预算/上限挡下 → 是否真的发出 Planner 请求 → 子目标是否变化
→ 该步动作 → 公开结果"记录成**可复算的链**。

成本口径（关键）：

- Planner 请求与动作请求同属一次决策的 ``requests``，**Planner 不免单**；
- Planner 的输入/输出 token 单独累加，便于算"每成功局费用"；
- 比较的是**同一总预算**下的结果，不允许"Planner 免费多请求"这种口径。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import AgentContext, PublicObservation
from agent_arena.lab.policies import planning_v2
from agent_arena.lab.v13.comparability import single_switch_check
from agent_arena.lab.v14.agent_studies import (
    _episode,
    _observation,
    _result,
    _ScriptedGateway,
)

#: 钉住的公共配置：三个消融组除被测开关外完全一致。
PLANNING_PINNED_BASE: dict[str, Any] = {
    "enabled": True,
    "planner_mode": planning_v2.MODE_ADAPTIVE,
    "min_steps_between_plans": 4,
    "stall_threshold": 4,
    "reject_threshold": 2,
    "max_plans": 6,
    "budget_aware": True,
    "history_window": 5,
}

#: V14 Planning 消融臂：三组独立单因子。
PLANNING_ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm_id": "E2-a-control",
        "group": "E2-a",
        "label": "规划关（enabled=False）",
        "overrides": {"enabled": False},
    },
    {
        "arm_id": "E2-a-treatment",
        "group": "E2-a",
        "label": "规划开（adaptive）",
        "overrides": {"enabled": True},
    },
    {
        "arm_id": "E2-b-control",
        "group": "E2-b",
        "label": "重规划开（adaptive）",
        "overrides": {"planner_mode": planning_v2.MODE_ADAPTIVE},
    },
    {
        "arm_id": "E2-b-treatment",
        "group": "E2-b",
        "label": "重规划关（initial_only）",
        "overrides": {"planner_mode": planning_v2.MODE_INITIAL_ONLY},
    },
    {
        "arm_id": "E2-c-control",
        "group": "E2-c",
        "label": "Planner 高频（每 4 步）",
        "overrides": {
            "planner_mode": planning_v2.MODE_PERIODIC,
            "min_steps_between_plans": 4,
        },
    },
    {
        "arm_id": "E2-c-treatment",
        "group": "E2-c",
        "label": "Planner 低频（每 12 步）",
        "overrides": {
            "planner_mode": planning_v2.MODE_PERIODIC,
            "min_steps_between_plans": 12,
        },
    },
)

#: 脚本：3 步有公开进度 → 2 次被拒 → 4 步无进度 → 3 步恢复。
PLANNING_SCRIPT: tuple[dict[str, Any], ...] = (
    {"moves_used": 1, "result": "MOVED", "rejected": False},
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True},
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 2, "result": "MOVED", "rejected": False},
    {"moves_used": 3, "result": "MOVED", "rejected": False},
    {"moves_used": 4, "result": "MOVED", "rejected": False},
    {"moves_used": 5, "result": "MOVED", "rejected": False},
)

#: 预算守卫专用脚本：12 步全部无公开进度（用来触发 TTL/预算两条挡下路径）。
PLANNING_STALL_SCRIPT: tuple[dict[str, Any], ...] = tuple(
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False} for _ in range(12)
)

#: 每个 Planner 请求的固定 token（与 ``_ScriptedGateway.ask_json`` 一致）。
PLANNER_INPUT_TOKENS = 120
PLANNER_OUTPUT_TOKENS = 30

def planning_offline_probe(
    config: dict[str, Any] | None = None,
    *,
    script: tuple[dict[str, Any], ...] = PLANNING_SCRIPT,
    decision_budget: int = 24,
    map_id: str = "MAP-16",
) -> dict[str, Any]:
    """确定性脚本驱动 ``planning.v2``，输出逐决策触发链与成本归因。"""

    policy = planning_v2.PlanningV2Policy(config)
    policy.reset(_episode(map_id=map_id, decisions=decision_budget))
    gateway = _ScriptedGateway()
    chain: list[dict[str, Any]] = []
    decisions = 0
    total_requests = 0
    planner_requests = 0
    planner_tokens_in = 0
    previous_subgoal: str | None = None

    for index, step in enumerate(script):
        gateway.current = {"tool": "move", "bearing": "north"}
        context = AgentContext(
            decision_index=index,
            remaining_decisions=max(1, decision_budget - index),
            history=(),
            gateway=gateway,
        )
        observation: PublicObservation = _observation(
            moves_used=step["moves_used"], step=index
        )
        decision = policy.decide(observation, context)
        decisions += 1
        total_requests += int(decision.requests or 0)
        event = decision.plan_event
        event_name = "" if event is None else str(event.event)
        trigger = ""
        blocked = ""
        subgoal = None
        if event is not None:
            trigger = str((event.payload or {}).get("trigger") or "")
            if event_name == "planner_skipped_budget":
                blocked = "budget"
            elif event_name == "planner_deferred_ttl":
                blocked = "ttl"
            elif event_name == "plan_budget_exhausted":
                blocked = "max_plans"
            elif event_name in {"plan_created", "plan_replanned"}:
                subgoal = str((event.payload or {}).get("subgoal") or "")
        if event_name in {"plan_created", "plan_replanned"}:
            planner_requests += 1
            planner_tokens_in += PLANNER_INPUT_TOKENS
        snapshot = policy.snapshot()
        chain.append(
            {
                "decision_index": index,
                "trigger": trigger,
                "event": event_name,
                "blocked_by": blocked,
                "planner_request": 1
                if event_name in {"plan_created", "plan_replanned"}
                else 0,
                "subgoal": subgoal,
                "subgoal_changed": bool(subgoal) and subgoal != previous_subgoal,
                "action": decision.action,
                "public_result": step["result"],
                "rejected": bool(step["rejected"]),
                "requests": int(decision.requests or 0),
                "plan_count": int(snapshot["plan_count"]),
            }
        )
        if subgoal:
            previous_subgoal = subgoal
        policy.observe_result(
            _result(
                action=decision.action,
                result=str(step["result"]),
                rejected=bool(step["rejected"]),
                decision_index=index,
            )
        )

    snapshot = policy.snapshot()
    return {
        "config": {
            "enabled": policy.enabled,
            "planner_mode": policy.planner_mode,
            "min_steps_between_plans": policy.min_steps_between_plans,
            "budget_aware": policy.budget_aware,
            "max_plans": policy.max_plans,
        },
        "decisions": decisions,
        "total_requests": total_requests,
        "action_requests": total_requests - planner_requests,
        "planner_requests": planner_requests,
        "planner_tokens_in": planner_tokens_in,
        "planner_tokens_out": PLANNER_OUTPUT_TOKENS * planner_requests,
        "planner_request_share": (
            round(planner_requests / total_requests, 4) if total_requests else None
        ),
        "plan_count": snapshot["plan_count"],
        "skipped_ttl": snapshot["skipped_ttl"],
        "skipped_budget": snapshot["skipped_budget"],
        "triggers": [item["trigger"] for item in snapshot["plan_requests"]],
        "chain": chain,
        "note": (
            "Planner 请求与动作请求同属一次决策的 ``requests``；"
            "成本按 requests + input/output token 分别记账，Planner 不免单。"
        ),
    }

def planning_arm_configs() -> list[dict[str, Any]]:
    return [
        {
            "arm_id": spec["arm_id"],
            "group": spec["group"],
            "label": spec["label"],
            "agent_id": "planning.v2",
            "config": {**PLANNING_PINNED_BASE, **spec["overrides"]},
        }
        for spec in PLANNING_ARMS
    ]

def planning_single_factor_audit() -> dict[str, Any]:
    arms = planning_arm_configs()
    groups: dict[str, list[dict[str, Any]]] = {}
    for arm in arms:
        groups.setdefault(arm["group"], []).append(arm)
    checks = []
    for group, items in sorted(groups.items()):
        check = single_switch_check(items[0], items[1])
        checks.append(
            {
                "group": group,
                "control": items[0]["arm_id"],
                "treatment": items[1]["arm_id"],
                "ok": check.ok,
                "manipulated_variable": check.manipulated_variable,
                "changed_keys": list(check.changed_keys),
                "reasons": list(check.reasons),
            }
        )
    return {
        "schema": "v14-planning-arms-1",
        "arms": arms,
        "checks": checks,
        "all_single_factor": all(item["ok"] for item in checks),
        "note": (
            "E2-a 改 ``enabled``；E2-b 改 ``planner_mode``（adaptive→initial_only）；"
            "E2-c 改 ``min_steps_between_plans``（4→12，两臂都钉 ``periodic``）。"
            "三组互不混用；MAP-18 只作负向对照。"
        ),
    }

def planning_ablation_plan() -> dict[str, Any]:
    """MAP-16 三组主消融 + MAP-18 负向对照；零请求预检登记。"""

    seeds = [0, 1, 2]
    replicates = 3
    main_runs = 3 * 2 * len(seeds) * replicates
    negative_runs = 1 * 2 * len(seeds) * replicates
    return {
        "schema": "v14-planning-plan-1",
        "status": "PLANNED_ONLY",
        "live_status": "LIVE_PENDING",
        "main_map": "MAP-16",
        "negative_control_map": "MAP-18",
        "seeds": seeds,
        "replicates": replicates,
        "runs": main_runs + negative_runs,
        "main_runs": main_runs,
        "negative_control_runs": negative_runs,
        "budget": {
            "per_run_request_cap": 90,
            "per_run_input_token_cap": 200_000,
            "per_run_cost_cap_cny": 0.50,
            "experiment_cost_cap_cny": 5.00,
        },
        "primary_metrics": [
            "completed_success",
            "plan_count",
            "planner_requests",
            "planner_tokens_in",
            "skipped_ttl",
            "skipped_budget",
        ],
        "cost_metrics": [
            "requests",
            "input_tokens",
            "output_tokens",
            "decisions",
            "cost_cny",
            "cost_per_success_cny",
        ],
        "stop_rules": [
            "任一局 unknown_spend → 立即停止并封账",
            "累计结算达批准上限 90% → 停止未开始子局",
            "Provider 连续 3 次错误 → 停止",
            "发现契约/接口缺陷 → 停止并写 DCR",
            "平均单局费用超过预估 2 倍 → 停止并重新申请",
        ],
        "comparison_rule": (
            "同一**总预算**下比较：Planner 请求不免费，必须计入同一 requests/token/费用上限；"
            "若节流省钱但成功率下降，如实保留，不为追涨点放松预算。"
        ),
        "negative_control_note": (
            "MAP-18 在 V12/V13 从未显示 planning 正梯度，保留为负向对照；"
            "若该图也出现「规划更好」，先怀疑测量与噪声，不当作收益证据。"
        ),
        "no_go_note": (
            "V14 未获用户对模型/矩阵/总额的批准，本计划不得执行；"
            "``scripts/run_v12_matrix.py --ablation`` 只允许默认预检模式。"
        ),
    }

def planning_study_report() -> dict[str, Any]:
    probes = {
        "adaptive": planning_offline_probe({"planner_mode": planning_v2.MODE_ADAPTIVE}),
        "initial_only": planning_offline_probe(
            {"planner_mode": planning_v2.MODE_INITIAL_ONLY}
        ),
        "periodic_4": planning_offline_probe(
            {"planner_mode": planning_v2.MODE_PERIODIC, "min_steps_between_plans": 4}
        ),
        "periodic_12": planning_offline_probe(
            {"planner_mode": planning_v2.MODE_PERIODIC, "min_steps_between_plans": 12}
        ),
        "disabled": planning_offline_probe({"enabled": False}),
        "budget_guard": planning_offline_probe(
            {"stall_threshold": 2},
            script=PLANNING_STALL_SCRIPT,
            decision_budget=12,
        ),
        "max_plans": planning_offline_probe(
            {"stall_threshold": 2, "max_plans": 2},
            script=PLANNING_STALL_SCRIPT,
            decision_budget=24,
        ),
    }
    return {
        "schema": "v14-planning-study-1",
        "probes": probes,
        "arms": planning_single_factor_audit(),
        "plan": planning_ablation_plan(),
        "note": "全部为 SIMULATED 机制证据，零模型请求；真实收益 LIVE_PENDING。",
    }

def planning_markdown(report: dict[str, Any]) -> str:
    probes = report["probes"]
    arms = report["arms"]
    plan = report["plan"]
    lines = [
        "## 2. Planning（P0-5）",
        "",
        "### 2.1 离线触发链（SIMULATED，零模型请求）",
        "",
        "脚本：1 步有进度 → 2 次被拒 → 5 步无进度 → 4 步恢复；共 12 次决策。",
        "",
        "| 臂 | 决策 | 总请求 | Planner 请求 | Planner token(in) | 计划数 | TTL 跳过 | 预算跳过 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, probe in probes.items():
        lines.append(
            f"| `{name}` | {probe['decisions']} | {probe['total_requests']} | "
            f"{probe['planner_requests']} | {probe['planner_tokens_in']} | "
            f"{probe['plan_count']} | {probe['skipped_ttl']} | "
            f"{probe['skipped_budget']} |"
        )
    lines += [
        "",
        "逐决策链（`adaptive`）：",
        "",
        "| 步 | 触发 | 事件 | 被挡 | Planner 请求 | 子目标 | 公开结果 | 请求 |",
        "|---:|---|---|---|---:|---|---|---:|",
    ]
    for node in probes["adaptive"]["chain"]:
        lines.append(
            f"| {node['decision_index']} | `{node['trigger'] or '—'}` | "
            f"`{node['event'] or '—'}` | `{node['blocked_by'] or '—'}` | "
            f"{node['planner_request']} | {node['subgoal'] or '—'} | "
            f"`{node['public_result']}` | {node['requests']} |"
        )
    lines += [
        "",
        f"> {probes['adaptive']['note']}",
        "",
        "被挡下的两条路径（`stall_threshold=2` + 12 步无进度）：",
        "",
        "| 臂 | 决策数 | 计划数 | TTL 跳过 | 预算跳过 | Planner 请求 | 总请求 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("budget_guard", "max_plans"):
        probe = probes[name]
        lines.append(
            f"| `{name}` | {probe['decisions']} | {probe['plan_count']} | "
            f"{probe['skipped_ttl']} | {probe['skipped_budget']} | "
            f"{probe['planner_requests']} | {probe['total_requests']} |"
        )
    lines += [
        "",
        "### 2.2 三组独立单因子",
        "",
        "| 组 | 对照 | 处理 | 唯一变化键 | 单开关 |",
        "|---|---|---|---|---|",
    ]
    for check in arms["checks"]:
        lines.append(
            f"| {check['group']} | `{check['control']}` | `{check['treatment']}` | "
            f"`{check['manipulated_variable']}` | {'是' if check['ok'] else '**否**'} |"
        )
    lines += [
        "",
        f"- 全部单因子：{'是' if arms['all_single_factor'] else '**否**'}",
        f"- {arms['note']}",
        "",
        "### 2.3 预检登记（`PLANNED_ONLY`，零请求）",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 主测地图 | {plan['main_map']} |",
        f"| 负向对照 | {plan['negative_control_map']} |",
        f"| 子局 | {plan['runs']}（主测 {plan['main_runs']} + 对照 "
        f"{plan['negative_control_runs']}） |",
        f"| 状态 | `{plan['status']}` / `{plan['live_status']}` |",
        "",
        f"- 比较口径：{plan['comparison_rule']}",
        f"- 负向对照：{plan['negative_control_note']}",
        f"- {plan['no_go_note']}",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "PLANNER_INPUT_TOKENS",
    "PLANNER_OUTPUT_TOKENS",
    "PLANNING_ARMS",
    "PLANNING_PINNED_BASE",
    "PLANNING_SCRIPT",
    "PLANNING_STALL_SCRIPT",
    "planning_ablation_plan",
    "planning_arm_configs",
    "planning_markdown",
    "planning_offline_probe",
    "planning_single_factor_audit",
    "planning_study_report",
]
