"""V14 Reflection 机制研究（P0-6）：六态计数、三臂设计与选择偏倚防护。

核心教训（DCR-V12-05）：`reflection.v1` 在 MAP-16 上从未触发，两臂
`reflection_triggered` 都是 0，于是"反思无效"的说法毫无根据。V14 因此把
**暴露（exposure）**做成一等公民：

| 状态 | 含义 | 能否用来评价效果 |
|---|---|---|
| `eligible` | 触发条件成立且冷却/额度允许 | 不能（只是候选） |
| `triggered` | 真的发出了反思请求 | 是，但只对触发子集 |
| `blocked_cooldown` | 被冷却挡下 | 不能 |
| `blocked_quota` | 被次数上限挡下 | 不能 |
| `false_triggers` | 触发时其实在推进（`budget_drain` 误判） | 需要单列 |
| `recoveries` | 反思后 `recovery_window` 步内公开进度变化 | 是，但**不是因果** |

两条硬规则：

1. `triggered == 0` → `NO_TREATMENT_EXPOSURE`，**不是**"反思无效"；
   先改选地图；要改阈值必须另立版本（否则等于换实验）。
2. 效果评估必须同时给出"全部已分配局"与"触发子集"两组数字，
   只报触发子集就是**选择偏倚**。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import AgentContext, PublicObservation
from agent_arena.lab.policies import reflection_v2
from agent_arena.lab.v13.comparability import single_switch_check
from agent_arena.lab.v14.agent_studies import (
    _episode,
    _observation,
    _result,
    _ScriptedGateway,
)

#: 钉住的公共配置：三臂除被测开关外完全一致。
REFLECTION_PINNED_BASE: dict[str, Any] = {
    "enabled": True,
    "trigger_only": False,
    "max_reflections": 3,
    "cooldown_steps": 4,
    "stall_threshold": 3,
    "reject_threshold": 2,
    "recovery_window": 3,
    "history_window": 5,
}

#: V14 Reflection 三臂：`disabled` / `trigger_only` / `reflection_on`。
REFLECTION_ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm_id": "E3-control",
        "group": "E3",
        "label": "disabled（完全不反思）",
        "overrides": {"enabled": False},
    },
    {
        "arm_id": "E3-trigger-only",
        "group": "E3",
        "label": "trigger_only（只判定触发，不请求模型）",
        "overrides": {"enabled": True, "trigger_only": True},
    },
    {
        "arm_id": "E3-treatment",
        "group": "E3",
        "label": "reflection_on（真发请求并注入建议）",
        "overrides": {"enabled": True, "trigger_only": False},
    },
)

#: 脚本：1 步有进度 → 3 次被拒 → 3 步无进度 → 1 步恢复 → 4 步再停滞。
REFLECTION_SCRIPT: tuple[dict[str, Any], ...] = (
    {"moves_used": 1, "result": "MOVED", "rejected": False},
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True},
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True},
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 1, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 2, "result": "MOVED", "rejected": False},
    {"moves_used": 2, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 2, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 2, "result": "NO_EFFECT", "rejected": False},
    {"moves_used": 2, "result": "NO_EFFECT", "rejected": False},
)

#: 长失败前缀脚本：12 步全部被拒（用于"暴露率"压测，不改阈值）。
REFLECTION_LONG_FAILURE_SCRIPT: tuple[dict[str, Any], ...] = tuple(
    {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True}
    for _ in range(12)
)

#: 每个反思请求的固定 token（与 ``_ScriptedGateway.ask_json`` 一致）。
REFLECTION_INPUT_TOKENS = 120
REFLECTION_OUTPUT_TOKENS = 30

def reflection_offline_probe(
    config: dict[str, Any] | None = None,
    *,
    script: tuple[dict[str, Any], ...] = REFLECTION_SCRIPT,
    decision_budget: int = 24,
    map_id: str = "MAP-22",
    cycle_actions: bool = False,
    include_tick: bool = True,
) -> dict[str, Any]:
    """确定性脚本驱动 ``reflection.v2``，输出六态计数与逐决策链。"""

    policy = reflection_v2.ReflectionV2Policy(config)
    policy.reset(_episode(map_id=map_id, decisions=decision_budget))
    gateway = _ScriptedGateway()
    chain: list[dict[str, Any]] = []
    decisions = 0
    total_requests = 0
    reflection_requests = 0
    advice_injected = 0

    for index, step in enumerate(script):
        bearing = ("north", "east", "south", "west")[index % 4] if cycle_actions else "north"
        gateway.current = {"tool": "move", "bearing": bearing}
        context = AgentContext(
            decision_index=index,
            remaining_decisions=max(1, decision_budget - index),
            history=(),
            gateway=gateway,
        )
        observation: PublicObservation = _observation(
            moves_used=step["moves_used"], step=index, **({"tick": index} if include_tick else {})
        )
        decision = policy.decide(observation, context)
        decisions += 1
        total_requests += int(decision.requests or 0)
        event = decision.reflection_event
        event_name = "" if event is None else str(event.event)
        trigger = ""
        if event is not None:
            trigger = str((event.payload or {}).get("trigger") or "")
        if event_name in {"reflection_triggered", "reflection_empty"}:
            reflection_requests += 1
        # 反思建议是否真的进入了下一步 prompt
        last_call = gateway.calls[-1] if gateway.calls else {}
        if last_call.get("runtime_feedback"):
            advice_injected += 1
        chain.append(
            {
                "decision_index": index,
                "event": event_name,
                "trigger": trigger,
                "reflection_request": 1
                if event_name in {"reflection_triggered", "reflection_empty"}
                else 0,
                "requests": int(decision.requests or 0),
                "public_result": step["result"],
                "rejected": bool(step["rejected"]),
            }
        )
        policy.observe_result(
            _result(
                action=decision.action,
                result=str(step["result"]),
                rejected=bool(step["rejected"]),
                decision_index=index,
                observation=_observation(
                    moves_used=step["moves_used"],
                    **({"tick": index} if include_tick else {}),
                ),
            )
        )

    snapshot = policy.snapshot()
    return {
        "config": {
            "enabled": policy.enabled,
            "trigger_only": policy.trigger_only,
            "max_reflections": policy.max_reflections,
            "cooldown_steps": policy.cooldown_steps,
            "stall_threshold": policy.stall_threshold,
            "reject_threshold": policy.reject_threshold,
        },
        "decisions": decisions,
        "total_requests": total_requests,
        "reflection_requests": reflection_requests,
        "reflection_tokens_in": REFLECTION_INPUT_TOKENS * reflection_requests,
        "reflection_tokens_out": REFLECTION_OUTPUT_TOKENS * reflection_requests,
        "advice_injected_steps": advice_injected,
        "eligible": snapshot["eligible"],
        "triggered": snapshot["triggered"],
        "blocked_cooldown": snapshot["blocked_cooldown"],
        "blocked_quota": snapshot["blocked_quota"],
        "false_triggers": snapshot["false_triggers"],
        "recoveries": snapshot["recoveries"],
        "activation_rate": snapshot["activation_rate"],
        "recovery_rate": snapshot["recovery_rate"],
        "exposure": snapshot["exposure"],
        "triggers": [item["trigger"] for item in snapshot["trigger_log"]],
        "chain": chain,
        "note": (
            "``eligible`` 只是候选；只有 ``triggered`` 才算真的发生了干预。"
            "``trigger_only`` 臂的 ``triggered`` 计入暴露，但 ``requests`` 不增加。"
        ),
    }

def reflection_arm_configs() -> list[dict[str, Any]]:
    return [
        {
            "arm_id": spec["arm_id"],
            "group": spec["group"],
            "label": spec["label"],
            "agent_id": "reflection.v2",
            "config": {**REFLECTION_PINNED_BASE, **spec["overrides"]},
        }
        for spec in REFLECTION_ARMS
    ]

def reflection_single_factor_audit() -> dict[str, Any]:
    """三臂两两比较：`disabled→trigger_only` 只改 `enabled`；
    `trigger_only→reflection_on` 只改 `trigger_only`。"""

    arms = {arm["arm_id"]: arm for arm in reflection_arm_configs()}
    pairs = (
        ("E3-control", "E3-treatment", "enabled（无反思 → 完整反思）", True),
        ("E3-trigger-only", "E3-treatment", "trigger_only（只判定 → 真请求）", True),
        ("E3-control", "E3-trigger-only", "enabled + trigger_only", False),
    )
    checks = []
    for left, right, label, single in pairs:
        check = single_switch_check(arms[left], arms[right])
        checks.append(
            {
                "left": left,
                "right": right,
                "label": label,
                "ok": check.ok,
                "expected_single_factor": single,
                "manipulated_variable": check.manipulated_variable,
                "changed_keys": list(check.changed_keys),
                "kind": check.kind,
                "reasons": list(check.reasons),
            }
        )
    single_factor = [
        item for item in checks if item["expected_single_factor"]
    ]
    return {
        "schema": "v14-reflection-arms-1",
        "arms": list(arms.values()),
        "checks": checks,
        "single_factor_pairs": [item["label"] for item in single_factor],
        "combination_pairs": [
            item["label"] for item in checks if not item["expected_single_factor"]
        ],
        "all_single_factor": all(item["ok"] for item in single_factor),
        "note": (
            "``disabled→reflection_on`` 是组合对照（含触发判定 + 请求 + 注入），"
            "只能作为机制比较；单因子结论必须用 ``trigger_only→reflection_on``。"
        ),
    }

def exposure_gate(snapshot_or_probe: dict[str, Any]) -> dict[str, Any]:
    """暴露门禁：没有触发就没有干预，不能报"无效"。"""

    triggered = int(snapshot_or_probe.get("triggered") or 0)
    enabled = snapshot_or_probe.get("config", {}).get("enabled", True)
    if not enabled:
        return {
            "status": "DISABLED_ARM",
            "triggered": 0,
            "allowed_conclusion": "该臂不构成干预对照，只能作为无反思基线。",
        }
    if triggered == 0:
        return {
            "status": reflection_v2.EXPOSURE_NONE,
            "triggered": 0,
            "allowed_conclusion": (
                "NO_TREATMENT_EXPOSURE：干预从未发生，不得报告「反思无效」；"
                "先改选有更长失败前缀的地图（改阈值必须另立版本）。"
            ),
        }
    return {
        "status": reflection_v2.EXPOSURE_TRIGGERED,
        "triggered": triggered,
        "allowed_conclusion": (
            "干预确实发生；效果只能在「全部已分配局」与「触发子集」两组同时报告。"
        ),
    }

def evaluate_without_selection_bias(
    *,
    all_assigned: list[dict[str, Any]],
    triggered_subset: list[dict[str, Any]],
) -> dict[str, Any]:
    """同时给出全分配与触发子集的结果，并标注选择偏倚风险。

    调用方必须两边都传；只传子集会被明确标成 ``SELECTION_BIAS``。
    """

    def _rate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        valid = [row for row in rows if row.get("category") in {
            "completed_success",
            "mechanism_failure",
            "budget_censored",
        }]
        successes = sum(1 for row in valid if row.get("category") == "completed_success")
        return {
            "runs": len(rows),
            "valid": len(valid),
            "successes": successes,
            "success_rate": round(successes / len(valid), 4) if valid else None,
        }

    overall = _rate(all_assigned)
    subset = _rate(triggered_subset)
    return {
        "all_assigned": overall,
        "triggered_subset": subset,
        "selection_bias": {
            "present": len(triggered_subset) < len(all_assigned),
            "note": (
                "只报触发子集会把「没触发就失败」的局从分母里删掉，"
                "从而高估效果；两组必须并列。"
            ),
            "dropped_runs": max(0, len(all_assigned) - len(triggered_subset)),
        },
        "interpretation_rule": (
            "若全分配口径没有改善而子集口径改善，只能说明「触发者本来就更接近成功」，"
            "不能说明反思带来了改善。"
        ),
    }

def reflection_ablation_plan() -> dict[str, Any]:
    """MAP-22 三臂 × 3 seed × 3 重复 = 27 局；零请求预检登记。"""

    seeds = [0, 1, 2]
    replicates = 3
    arms = len(REFLECTION_ARMS)
    runs = arms * len(seeds) * replicates
    return {
        "schema": "v14-reflection-plan-1",
        "status": "PLANNED_ONLY",
        "live_status": "LIVE_PENDING",
        "maps": ["MAP-22"],
        "seeds": seeds,
        "replicates": replicates,
        "arms": [arm["arm_id"] for arm in REFLECTION_ARMS],
        "runs": runs,
        "two_arm_subset_runs": 2 * len(seeds) * replicates,
        "budget": {
            "per_run_request_cap": 90,
            "per_run_input_token_cap": 200_000,
            "per_run_cost_cap_cny": 0.50,
            "experiment_cost_cap_cny": 5.00,
        },
        "primary_metrics": [
            "completed_success",
            "eligible",
            "triggered",
            "blocked_cooldown",
            "blocked_quota",
            "false_triggers",
            "recoveries",
        ],
        "cost_metrics": ["requests", "input_tokens", "output_tokens", "cost_cny"],
        "activation_gate": (
            "``reflection_on`` 臂必须至少出现一次真实反思请求（``triggered > 0``）；"
            "否则记录 NO_TREATMENT_EXPOSURE 并改选地图，不得按「反思无效」报告。"
        ),
        "candidate_maps": [
            {"map_id": "MAP-22", "status": "PRIMARY", "why": "V12 已知有较长失败前缀"},
            {"map_id": "MAP-19", "status": "CANDIDATE", "why": "需先做公开动作/触发器离线诊断"},
            {"map_id": "MAP-20", "status": "CANDIDATE", "why": "同上"},
            {"map_id": "MAP-29", "status": "CANDIDATE", "why": "同上"},
        ],
        "stop_rules": [
            "任一局 unknown_spend → 立即停止并封账",
            "累计结算达批准上限 90% → 停止未开始子局",
            "Provider 连续 3 次错误 → 停止",
            "发现契约/接口缺陷 → 停止并写 DCR",
            "``reflection_on`` 臂全部 0 触发 → 停止并按 NO_TREATMENT_EXPOSURE 处理",
        ],
        "no_go_note": (
            "V14 未获用户对模型/矩阵/总额的批准，本计划不得执行；"
            "所有真实效果保持 LIVE_PENDING。"
        ),
    }

def reflection_study_report() -> dict[str, Any]:
    probes = {
        "disabled": reflection_offline_probe({"enabled": False}),
        "trigger_only": reflection_offline_probe({"trigger_only": True}),
        "reflection_on": reflection_offline_probe({"trigger_only": False}),
        "long_failure_on": reflection_offline_probe(
            {"trigger_only": False}, script=REFLECTION_LONG_FAILURE_SCRIPT
        ),
        "no_trigger_on": reflection_offline_probe(
            {"trigger_only": False},
            script=tuple(
                {"moves_used": index + 1, "result": "MOVED", "rejected": False}
                for index in range(6)
            ),
            cycle_actions=True,
            include_tick=False,
        ),
    }
    return {
        "schema": "v14-reflection-study-1",
        "probes": probes,
        "arms": reflection_single_factor_audit(),
        "gates": {name: exposure_gate(probe) for name, probe in probes.items()},
        "plan": reflection_ablation_plan(),
        "note": "全部为 SIMULATED 机制证据，零模型请求；真实收益 LIVE_PENDING。",
    }

def reflection_markdown(report: dict[str, Any]) -> str:
    probes = report["probes"]
    arms = report["arms"]
    plan = report["plan"]
    lines = [
        "## 3. Reflection（P0-6）",
        "",
        "### 3.1 六态计数（SIMULATED，零模型请求）",
        "",
        "| 臂 | 决策 | 总请求 | 反思请求 | eligible | triggered "
        "| 冷却挡 | 额度挡 | 误触发 | 恢复 | 暴露 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, probe in probes.items():
        lines.append(
            f"| `{name}` | {probe['decisions']} | {probe['total_requests']} | "
            f"{probe['reflection_requests']} | {probe['eligible']} | "
            f"{probe['triggered']} | {probe['blocked_cooldown']} | "
            f"{probe['blocked_quota']} | {probe['false_triggers']} | "
            f"{probe['recoveries']} | `{probe['exposure']}` |"
        )
    lines += [
        "",
        "> `eligible` 只是候选；`triggered` 才是真的发生了干预。"
        "`trigger_only` 臂计入暴露但 `requests` 不增加。",
        "",
        "### 3.2 暴露门禁",
        "",
        "| 臂 | 状态 | 允许的结论 |",
        "|---|---|---|",
    ]
    for name, gate in report["gates"].items():
        lines.append(f"| `{name}` | `{gate['status']}` | {gate['allowed_conclusion']} |")
    lines += [
        "",
        "### 3.3 三臂单因子",
        "",
        "| 比较 | 唯一变化键 | 单开关 | 预期 | 说明 |",
        "|---|---|---|---|---|",
    ]
    for check in arms["checks"]:
        lines.append(
            f"| `{check['left']}` → `{check['right']}` | "
            f"`{check['manipulated_variable'] or '、'.join(check['changed_keys'])}` | "
            f"{'是' if check['ok'] else '**否**'} | "
            f"{'单因子' if check['expected_single_factor'] else '组合'} | "
            f"{check['label']} |"
        )
    lines += [
        "",
        f"- {arms['note']}",
        "",
        "### 3.4 选择偏倚防护",
        "",
        "效果评估必须同时给出两组口径（`evaluate_without_selection_bias`）：",
        "",
        "| 口径 | 局数 | 有效 | 成功 | 成功率 |",
        "|---|---:|---:|---:|---:|",
        "| 全部已分配局 | 全部分母 | 同左 | 含未触发局 | 真实可用 |",
        "| 触发子集 | 仅触发的局 | 更小 | 偏高 | **只作机制证据** |",
        "",
        "> 只报触发子集等于把「没触发就失败」的局从分母删掉，会系统性高估效果。",
        "",
        "### 3.5 预检登记（`PLANNED_ONLY`，零请求）",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 地图 | {', '.join(plan['maps'])} |",
        f"| 臂 | {', '.join(plan['arms'])} |",
        f"| 子局 | {plan['runs']}（两臂子集 {plan['two_arm_subset_runs']}） |",
        f"| 状态 | `{plan['status']}` / `{plan['live_status']}` |",
        f"| 激活门禁 | {plan['activation_gate']} |",
        "",
        "- 候选地图（需先做离线公开诊断）："
        + "；".join(
            f"{item['map_id']}（{item['status']}）" for item in plan["candidate_maps"]
        ),
        f"- {plan['no_go_note']}",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "REFLECTION_ARMS",
    "REFLECTION_INPUT_TOKENS",
    "REFLECTION_LONG_FAILURE_SCRIPT",
    "REFLECTION_OUTPUT_TOKENS",
    "REFLECTION_PINNED_BASE",
    "REFLECTION_SCRIPT",
    "evaluate_without_selection_bias",
    "exposure_gate",
    "reflection_ablation_plan",
    "reflection_arm_configs",
    "reflection_markdown",
    "reflection_offline_probe",
    "reflection_single_factor_audit",
    "reflection_study_report",
]
