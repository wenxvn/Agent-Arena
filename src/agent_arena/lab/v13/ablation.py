"""开关消融与核心证据包（P0-4 / P0-6，V13-05-01 … 05-07）。

三条硬规则：

1. **单因子消融必须同版本、只改一个开关**。``memory.v1`` vs ``memory.v2`` 是
   **版本比较**，不是"关掉一个开关"；报告措辞必须不同（V13-05-03）。
2. on/off 默认建立**两个独立父实验**，通过 ``(map, seed, replicate_index)``
   配对；不把不同配置塞进同一个 ``condition_key``。
3. 反向、零提升、成本升高都是结果，必须保留（V13-05-07）。

本模块只做**计划与判定**：构造两臂规格、检查单变量、给出证据等级。
它不提交任何实验，也不发任何请求。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from agent_arena.lab.contracts import (
    AgentArm,
    ComparisonPolicy,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.v13.comparability import (
    SwitchCheck,
    single_switch_check,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER

KIND_SINGLE_SWITCH = "SINGLE_SWITCH_ABLATION"
KIND_VERSION_COMPARE = "VERSION_COMPARISON"
KIND_MULTI_SWITCH = "MULTI_SWITCH_COMBINATION"
KIND_NO_INTERVENTION = "NO_INTERVENTION"

LEVEL_SUPPORTED = "SUPPORTED"
LEVEL_TENTATIVE = "TENTATIVE"
LEVEL_INSUFFICIENT = "INSUFFICIENT"
LEVEL_NOT_TESTED = "NOT_TESTED"


@dataclass(frozen=True)
class AblationTemplate:
    """一个标准消融模板：两臂配置 + 说明 + 期望的机制证据。"""

    template_id: str
    agent_id: str
    label: str
    treatment: dict[str, Any]
    control: dict[str, Any]
    manipulated_variable: str
    expectation: str
    mechanism_metrics: tuple[str, ...] = ()

    def arms(self) -> tuple[AgentArm, AgentArm]:
        return (
            AgentArm(agent_id=self.agent_id, config=dict(self.control), label="control"),
            AgentArm(agent_id=self.agent_id, config=dict(self.treatment), label="treatment"),
        )

    def check(self) -> SwitchCheck:
        return single_switch_check(
            {"agent_id": self.agent_id, "config": dict(self.control)},
            {"agent_id": self.agent_id, "config": dict(self.treatment)},
        )

    def as_dict(self) -> dict[str, Any]:
        check = self.check()
        return {
            "template_id": self.template_id,
            "agent_id": self.agent_id,
            "label": self.label,
            "treatment": dict(self.treatment),
            "control": dict(self.control),
            "manipulated_variable": self.manipulated_variable,
            "expectation": self.expectation,
            "mechanism_metrics": list(self.mechanism_metrics),
            "single_switch_ok": check.ok,
            "kind": KIND_SINGLE_SWITCH if check.ok else KIND_MULTI_SWITCH,
            "reasons": list(check.reasons),
        }


#: 内置模板：全部是**同版本**的单开关。
ABLATION_TEMPLATES: dict[str, AblationTemplate] = {
    "memory.on_off": AblationTemplate(
        template_id="memory.on_off",
        agent_id="memory.v2",
        label="Memory 开关（同版本 memory.v2）",
        control={"enabled": False},
        treatment={"enabled": True},
        manipulated_variable="enabled",
        expectation="记忆开启后应减少重复被拒/无效动作；若无变化或成本上升，如实保留。",
        mechanism_metrics=("route_length", "block_chars", "render_count"),
    ),
    "memory.route_log": AblationTemplate(
        template_id="memory.route_log",
        agent_id="memory.v2",
        label="Memory 路线日志开关（同版本 memory.v2）",
        control={"route_log": False},
        treatment={"route_log": True},
        manipulated_variable="route_log",
        expectation="路线日志应提高 route_recall、降低 wasted_moves，代价是占用决策预算。",
        mechanism_metrics=("route_length", "route_recall", "wasted_moves"),
    ),
    "planning.on_off": AblationTemplate(
        template_id="planning.on_off",
        agent_id="planning.v2",
        label="Planning 开关（同版本 planning.v2）",
        control={"enabled": False},
        treatment={"enabled": True},
        manipulated_variable="enabled",
        expectation="规划开启应提高有梯度地图的成功率，代价是额外 Planner 请求与 token。",
        mechanism_metrics=("plan_count", "planner_requests", "planner_tokens_in"),
    ),
    "planning.replan_off": AblationTemplate(
        template_id="planning.replan_off",
        agent_id="planning.v2",
        label="重规划开关（同版本，规划仍开）",
        control={"planner_mode": "adaptive"},
        treatment={"planner_mode": "initial_only"},
        manipulated_variable="planner_mode",
        expectation="关闭重规划后 Planner 请求数应降到 1；成功率的代价才是「重规划的价值」。",
        mechanism_metrics=("plan_count", "planner_requests", "skipped_ttl"),
    ),
    "planning.low_frequency": AblationTemplate(
        template_id="planning.low_frequency",
        agent_id="planning.v2",
        label="低频 Planner（同版本）",
        control={"min_steps_between_plans": 4},
        treatment={"min_steps_between_plans": 12},
        manipulated_variable="min_steps_between_plans",
        expectation="降低规划频率应显著减少 Planner 请求；若成功率不降，说明原频率过高。",
        mechanism_metrics=("plan_count", "planner_requests", "skipped_ttl"),
    ),
    "reflection.on_off": AblationTemplate(
        template_id="reflection.on_off",
        agent_id="reflection.v2",
        label="Reflection 开关（同版本 reflection.v2）",
        control={"enabled": False},
        treatment={"enabled": True},
        manipulated_variable="enabled",
        expectation=(
            "只有 triggered>0 时才有资格谈效果；triggered=0 必须报 "
            "NO_TREATMENT_EXPOSURE（V13-06-05）。"
        ),
        mechanism_metrics=("eligible", "triggered", "recoveries"),
    ),
    "reflection.trigger_only": AblationTemplate(
        template_id="reflection.trigger_only",
        agent_id="reflection.v2",
        label="Reflection trigger-only 对照",
        control={"trigger_only": False},
        treatment={"trigger_only": True},
        manipulated_variable="trigger_only",
        expectation=(
            "trigger-only 不请求模型、不注入建议；若两者结果相同，说明反思内容没有起作用，"
            "差异只来自触发判定本身。"
        ),
        mechanism_metrics=("triggered", "activation_rate"),
    ),
}

#: 版本比较（**不是**消融）：跨 agent_id，必须单独标注。
VERSION_COMPARISONS: tuple[dict[str, str], ...] = (
    {
        "left": "memory.v1",
        "right": "memory.v2",
        "why": "默认 route_log 与容量/渲染上限都变了，属于版本比较。",
    },
    {
        "left": "planning.v1",
        "right": "planning.v2",
        "why": "重规划触发与节流语义不同，属于版本比较。",
    },
    {
        "left": "reflection.v1",
        "right": "reflection.v2",
        "why": "新增 trigger-only、恢复窗口与激活率口径，属于版本比较。",
    },
)


def classify_pair(
    left_agent: str, left_config: dict[str, Any], right_agent: str, right_config: dict[str, Any]
) -> str:
    """判定一对实验臂属于哪类对照。"""

    if left_agent != right_agent:
        return KIND_VERSION_COMPARE
    check = single_switch_check(
        {"agent_id": left_agent, "config": left_config},
        {"agent_id": right_agent, "config": right_config},
    )
    if check.kind == "no_intervention":
        return KIND_NO_INTERVENTION
    return KIND_SINGLE_SWITCH if check.ok else KIND_MULTI_SWITCH


def build_ablation_specs(
    template: AblationTemplate,
    *,
    maps: list[str],
    seeds: list[int],
    replicates: int = 3,
    mode: ExperimentMode = ExperimentMode.SIMULATED,
    provider_id: str = SIMULATED_PROVIDER,
    model: str = SIMULATED_MODEL,
    budget: ExperimentBudget | None = None,
    name_prefix: str = "",
) -> tuple[ExperimentSpec, ExperimentSpec]:
    """构造 on/off 两个**独立父实验**（同版本、只差一个开关）。"""

    check = template.check()
    if not check.ok:
        raise ValueError(
            f"模板 {template.template_id} 不是单开关消融：" + "；".join(check.reasons)
        )
    budget = budget or ExperimentBudget(
        per_run_request_cap=90,
        per_run_decision_cap=90,
        experiment_request_cap=2_000,
        experiment_cost_cap_cny=Decimal("2.00"),
    )
    prefix = name_prefix or template.template_id
    common: dict[str, Any] = {
        "maps": list(maps),
        "environment_seeds": list(seeds),
        "provider_id": provider_id,
        "model": model,
        "mode": mode,
        "budget": budget,
        "comparison": ComparisonPolicy(min_paired_samples=replicates),
        "replicates": replicates,
        "experiment_kind": "ablation",
    }
    control_spec = ExperimentSpec(
        name=f"{prefix} · control",
        notes=(
            f"消融对照（control）：{template.label}；被操纵变量 "
            f"`{template.manipulated_variable}` = {template.control}。"
        ),
        agent_arms=[
            AgentArm(
                agent_id=template.agent_id,
                config=dict(template.control),
                label="control",
            )
        ],
        **common,
    )
    treatment_spec = ExperimentSpec(
        name=f"{prefix} · treatment",
        notes=(
            f"消融处理（treatment）：{template.label}；被操纵变量 "
            f"`{template.manipulated_variable}` = {template.treatment}。"
        ),
        agent_arms=[
            AgentArm(agent_id=template.agent_id, config=dict(template.treatment), label="treatment")
        ],
        **common,
    )
    return control_spec, treatment_spec


@dataclass
class EvidencePack:
    """一张地图的核心证据包（V13-05-04）：原始 run 引用 + 分母 + 反例 + 截尾 + 费用。"""

    map_id: str
    question: str
    source: str
    runs: int = 0
    valid_denominator: int = 0
    successes: int = 0
    mechanism_failures: int = 0
    budget_censored: int = 0
    invalid_runs: int = 0
    cost_cny: float = 0.0
    cost_unknown_runs: int = 0
    by_arm: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_refs: list[dict[str, Any]] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def censored_ratio(self) -> float | None:
        return round(self.budget_censored / self.runs, 4) if self.runs else None

    def conclusion_level(self) -> str:
        """证据等级：只看样本与截尾，不看成功率高低。"""

        if self.runs == 0:
            return LEVEL_NOT_TESTED
        if self.valid_denominator == 0:
            return LEVEL_INSUFFICIENT
        if self.budget_censored and self.censored_ratio and self.censored_ratio >= 0.3:
            return LEVEL_INSUFFICIENT
        if self.valid_denominator < 3:
            return LEVEL_TENTATIVE
        return LEVEL_SUPPORTED

    def as_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "question": self.question,
            "source": self.source,
            "runs": self.runs,
            "valid_denominator": self.valid_denominator,
            "successes": self.successes,
            "mechanism_failures": self.mechanism_failures,
            "budget_censored": self.budget_censored,
            "invalid_runs": self.invalid_runs,
            "censored_ratio": self.censored_ratio,
            "cost_cny": round(self.cost_cny, 8),
            "cost_unknown_runs": self.cost_unknown_runs,
            "by_arm": self.by_arm,
            "counterexamples": self.counterexamples,
            "conclusion_level": self.conclusion_level(),
            "notes": self.notes,
            "run_refs": self.run_refs,
        }

    def markdown(self) -> str:
        lines = [
            f"# 证据包 · {self.map_id}",
            "",
            f"- 研究问题：{self.question}",
            f"- 数据来源：`{self.source}`（历史只读，不是本轮新跑）",
            f"- 结论等级：`{self.conclusion_level()}`",
            "",
            "## 分母（先看这一节）",
            "",
            "| 指标 | 值 |",
            "|---|---:|",
            f"| 总局数 | {self.runs} |",
            f"| 有效分母 | {self.valid_denominator} |",
            f"| 成功 | {self.successes} |",
            f"| 机制失败 | {self.mechanism_failures} |",
            f"| 预算截尾 | {self.budget_censored} |",
            f"| 无效/中断/取消 | {self.invalid_runs} |",
            f"| 截尾比例 | {self.censored_ratio if self.censored_ratio is not None else '—'} |",
            f"| 已结算费用 CNY | {round(self.cost_cny, 8)} |",
            f"| 费用未知局数 | {self.cost_unknown_runs} |",
            "",
            "## 逐实验臂",
            "",
            "| 实验臂 | 版本 | 局数 | 有效 | 成功 | 截尾 | 平均请求 | 平均费用 |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for arm_id, bucket in sorted(self.by_arm.items()):
            lines.append(
                f"| `{arm_id}` | {bucket.get('version') or '—'} | {bucket.get('runs')} | "
                f"{bucket.get('valid')} | {bucket.get('successes')} | "
                f"{bucket.get('censored')} | {bucket.get('mean_requests')} | "
                f"{bucket.get('mean_cost_cny')} |"
            )
        if self.counterexamples:
            lines += ["", "## 反例（同一实验臂内的失败/截尾局）", ""]
            for item in self.counterexamples[:12]:
                lines.append(
                    f"- `{item.get('run_id')}` · `{item.get('agent_id')}` · "
                    f"`{item.get('category')}` · 终止 `{item.get('termination')}`"
                )
        if self.notes:
            lines += ["", "## 限制与说明", ""]
            lines.extend(f"- {note}" for note in self.notes)
        lines += [
            "",
            "## 原始引用",
            "",
            f"- 逐局明细见 `{self.source}` 对应 CSV；本证据包只做只读聚合。",
            "",
        ]
        return "\n".join(lines)


def build_evidence_pack(
    map_id: str,
    records: list[dict[str, Any]],
    *,
    question: str,
    source: str,
) -> EvidencePack:
    """从逐局记录构造证据包（只读、不补零）。"""

    selected = [item for item in records if str(item.get("map_id")) == map_id]
    pack = EvidencePack(map_id=map_id, question=question, source=source, runs=len(selected))
    arms: dict[str, dict[str, Any]] = {}
    for record in selected:
        category = str(record.get("category") or "")
        valid = category in {"completed_success", "mechanism_failure", "budget_censored"}
        if valid:
            pack.valid_denominator += 1
        if category == "completed_success":
            pack.successes += 1
        elif category == "mechanism_failure":
            pack.mechanism_failures += 1
        elif category == "budget_censored":
            pack.budget_censored += 1
        else:
            pack.invalid_runs += 1
        if record.get("cost_known") and record.get("cost_cny") is not None:
            pack.cost_cny += float(record["cost_cny"])
        else:
            pack.cost_unknown_runs += 1
        agent = str(record.get("agent_id") or "")
        config_hash = str(record.get("agent_config_hash") or "")
        # 同 agent 不同配置必须分开统计（否则"版本比较"会被当成"消融"）。
        arm_key = f"{agent}@{config_hash[:8]}" if config_hash else agent
        bucket = arms.setdefault(
            arm_key,
            {
                "agent_id": agent,
                "config_hash": config_hash[:12],
                "version": record.get("agent_version") or "",
                "runs": 0,
                "valid": 0,
                "successes": 0,
                "censored": 0,
                "requests": 0,
                "costs": [],
            },
        )
        bucket["runs"] += 1
        bucket["valid"] += 1 if valid else 0
        bucket["successes"] += 1 if category == "completed_success" else 0
        bucket["censored"] += 1 if category == "budget_censored" else 0
        bucket["requests"] += int(record.get("requests") or 0)
        if record.get("cost_known") and record.get("cost_cny") is not None:
            bucket["costs"].append(float(record["cost_cny"]))
        if category in {"mechanism_failure", "budget_censored"}:
            pack.counterexamples.append(
                {
                    "run_id": record.get("run_id"),
                    "agent_id": agent,
                    "category": category,
                    "termination": record.get("termination"),
                    "decisions": record.get("decisions"),
                }
            )
        pack.run_refs.append(
            {
                "run_id": record.get("run_id"),
                "agent_id": agent,
                "environment_seed": record.get("environment_seed"),
                "category": category,
                "success": bool(record.get("success")),
                "cost_cny": record.get("cost_cny"),
                "requests": record.get("requests"),
            }
        )
    for bucket in arms.values():
        runs = bucket["runs"] or 1
        costs = bucket.pop("costs")
        bucket["mean_requests"] = round(bucket.pop("requests") / runs, 4)
        bucket["mean_cost_cny"] = round(sum(costs) / len(costs), 8) if costs else None
    pack.by_arm = arms
    if pack.cost_unknown_runs:
        pack.notes.append(
            f"{pack.cost_unknown_runs} 局费用未知；费用汇总不含这些局，也不补零。"
        )
    if pack.budget_censored:
        pack.notes.append(
            f"{pack.budget_censored} 局因预算/动作上限截尾：它们只说明「没测完」，"
            "不说明「做不到」。"
        )
    return pack


def template_table() -> list[dict[str, Any]]:
    """模板清单（UI 与文档共用）。"""

    return [template.as_dict() for template in ABLATION_TEMPLATES.values()]


__all__ = [
    "ABLATION_TEMPLATES",
    "KIND_MULTI_SWITCH",
    "KIND_NO_INTERVENTION",
    "KIND_SINGLE_SWITCH",
    "KIND_VERSION_COMPARE",
    "LEVEL_INSUFFICIENT",
    "LEVEL_NOT_TESTED",
    "LEVEL_SUPPORTED",
    "LEVEL_TENTATIVE",
    "VERSION_COMPARISONS",
    "AblationTemplate",
    "EvidencePack",
    "build_ablation_specs",
    "build_evidence_pack",
    "classify_pair",
    "template_table",
]
