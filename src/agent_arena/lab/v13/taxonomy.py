"""分层失败归因（P1-3 / V13-08-01 … 08-03）。

V12 的 ``lab/diagnostics.py`` 已经能给出证据级 Finding。V13 在它之上加**分层**，
因为"失败"至少有七种完全不同的性质，混在一起就会把接口缺陷写成能力不足：

| 层 | 含义 | 典型证据 |
|---|---|---|
| `INTERFACE_CONTRACT` | 公开契约/字段形状问题 | 非法动作占比、`INVALID_MEMORY_PAYLOAD` |
| `MEASUREMENT_COVERAGE` | 指标读不到但行为正确 | 键名不在指标口径内 |
| `BUDGET_CENSORED` | 请求/token/费用/动作上限 | `BUDGET_REACHED` + termination |
| `ENVIRONMENT_MECHANISM` | 环境机制被真实触发但未满足条件 | `ACCUSATION_REJECTED`、`DEADLOCK` |
| `POLICY_BEHAVIOUR` | 策略侧可观察行为问题 | 重复动作环、盲换、无进展 |
| `PROVIDER` | Provider/网络/未知消费 | `PROVIDER_ERROR`、`unknown_spend` |
| `UNKNOWN` | 证据不足 | `NOT_ENOUGH_EVIDENCE` |

规则：

- 每条结论必须能回溯到具体 ``decision``/事件（``evidence_steps``）；
- 一个 run 可以有**一个主层**与若干次层，但**不得**把接口问题算进能力分母；
- 证据不足时输出 ``UNKNOWN``，不猜。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from agent_arena.lab.contracts import Finding

INTERFACE = "INTERFACE_CONTRACT"
MEASUREMENT = "MEASUREMENT_COVERAGE"
BUDGET = "BUDGET_CENSORED"
MECHANISM = "ENVIRONMENT_MECHANISM"
POLICY = "POLICY_BEHAVIOUR"
PROVIDER = "PROVIDER"
UNKNOWN = "UNKNOWN"

LAYERS: tuple[str, ...] = (
    INTERFACE,
    MEASUREMENT,
    BUDGET,
    MECHANISM,
    POLICY,
    PROVIDER,
    UNKNOWN,
)

LAYER_LABELS: dict[str, str] = {
    INTERFACE: "接口/契约问题（不是能力）",
    MEASUREMENT: "测量覆盖问题（不是能力）",
    BUDGET: "预算截尾（没测完）",
    MECHANISM: "环境机制真实触发但未达成",
    POLICY: "策略可观察行为",
    PROVIDER: "Provider/基础设施",
    UNKNOWN: "证据不足",
}

#: Finding 类别 → 层。未列出的类别由关键词兜底。
CATEGORY_LAYERS: dict[str, str] = {
    "contract_artifact": INTERFACE,
    "memory_payload_rejected": INTERFACE,
    "memory_key_not_in_metric": MEASUREMENT,
    "memory_sequence_short": POLICY,
    "memory_not_used": POLICY,
    "provider_error": PROVIDER,
    "budget_censored": BUDGET,
    "cancelled": UNKNOWN,
    "interrupted": UNKNOWN,
    "repeated_action_loop": POLICY,
    "repeated_rejected_action": POLICY,
    "no_progress_window": POLICY,
    "key_action_never_attempted": POLICY,
    "key_action_attempted_rejected": MECHANISM,
    "key_action_used_no_trigger": MECHANISM,
    "unused_public_tests": POLICY,
    "premature_commit": POLICY,
    "frame_mismatch": POLICY,
    "window_violation": POLICY,
    "blind_swap": POLICY,
    "unsupported_accusation": MECHANISM,
    "not_enough_evidence": UNKNOWN,
    "NOT_ENOUGH_EVIDENCE": UNKNOWN,
}

#: 接口层的关键词（用于未登记类别的兜底判定）。
_INTERFACE_HINTS = ("contract", "payload", "schema", "invalid_output", "契约")
_MEASUREMENT_HINTS = ("metric", "coverage", "key_not", "指标")
_BUDGET_HINTS = ("budget", "limit_exceeded", "censored", "截尾")
_PROVIDER_HINTS = ("provider", "network", "timeout", "unknown_spend")
_MECHANISM_HINTS = ("accusation", "deadlock", "collision", "mechanism", "机制")


def classify_category(category: str) -> str:
    """把 Finding 类别映射到层；未知类别按关键词兜底，最后落到 ``UNKNOWN``。"""

    if category in CATEGORY_LAYERS:
        return CATEGORY_LAYERS[category]
    lowered = category.lower()
    for hints, layer in (
        (_INTERFACE_HINTS, INTERFACE),
        (_MEASUREMENT_HINTS, MEASUREMENT),
        (_BUDGET_HINTS, BUDGET),
        (_PROVIDER_HINTS, PROVIDER),
        (_MECHANISM_HINTS, MECHANISM),
    ):
        if any(hint in lowered for hint in hints):
            return layer
    return UNKNOWN


@dataclass
class RunAttribution:
    """一局的归因结果：主层 + 次层 + 证据锚。"""

    run_id: str
    map_id: str
    agent_id: str = ""
    primary_layer: str = UNKNOWN
    layers: dict[str, int] = field(default_factory=dict)
    anchors: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "map_id": self.map_id,
            "agent_id": self.agent_id,
            "primary_layer": self.primary_layer,
            "primary_label": LAYER_LABELS.get(self.primary_layer, self.primary_layer),
            "layers": dict(sorted(self.layers.items())),
            "anchors": list(self.anchors),
            "summary": self.summary,
        }


#: 主层的优先级：越靠前越"不怪 Agent"。
_PRIORITY: tuple[str, ...] = (PROVIDER, INTERFACE, MEASUREMENT, BUDGET, MECHANISM, POLICY, UNKNOWN)


def attribute_run(
    record: dict[str, Any], findings: Iterable[Finding]
) -> RunAttribution:
    """把一局的 Finding 聚合成分层归因（主层按"最不怪 Agent"优先）。"""

    items = [item for item in findings if item.run_id == record.get("run_id")]
    attribution = RunAttribution(
        run_id=str(record.get("run_id") or ""),
        map_id=str(record.get("map_id") or ""),
        agent_id=str(record.get("agent_id") or ""),
    )
    for finding in items:
        layer = classify_category(finding.category)
        attribution.layers[layer] = attribution.layers.get(layer, 0) + 1
        attribution.anchors.append(
            {
                "layer": layer,
                "category": finding.category,
                "severity": finding.severity,
                "decision_steps": list(finding.evidence_steps),
                "event_ids": list(finding.evidence_event_ids),
                "summary": finding.summary,
                "scope": finding.confidence_scope,
            }
        )
    if attribution.layers:
        for layer in _PRIORITY:
            if layer in attribution.layers:
                attribution.primary_layer = layer
                break
        attribution.summary = (
            f"主层 {LAYER_LABELS[attribution.primary_layer]}；"
            f"共 {len(items)} 条证据级诊断。"
        )
    else:
        category = str(record.get("category") or "")
        if category == "budget_censored":
            attribution.primary_layer = BUDGET
            attribution.layers = {BUDGET: 1}
            attribution.summary = "预算/动作上限截尾（没有诊断规则命中）。"
        elif category == "provider_error":
            attribution.primary_layer = PROVIDER
            attribution.layers = {PROVIDER: 1}
            attribution.summary = "Provider 错误（不是策略失败）。"
        elif category == "completed_success":
            attribution.primary_layer = ""
            attribution.summary = "成功局，无需失败归因。"
        else:
            attribution.summary = "没有命中任何确定性规则；证据不足。"
    return attribution


def taxonomy_report(
    records: list[dict[str, Any]], findings: Iterable[Finding]
) -> dict[str, Any]:
    """整体分层统计 + 逐局归因 + 未归因计数（不补零）。"""

    by_run = {str(item.get("run_id")): item for item in records}
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.run_id, []).append(finding)
    attributions = [
        attribute_run(record, grouped.get(str(record.get("run_id")), []))
        for record in records
    ]
    layer_counts: dict[str, int] = {}
    for attribution in attributions:
        for layer, count in attribution.layers.items():
            layer_counts[layer] = layer_counts.get(layer, 0) + count
    primary_counts: dict[str, int] = {}
    for attribution in attributions:
        if attribution.primary_layer:
            primary_counts[attribution.primary_layer] = (
                primary_counts.get(attribution.primary_layer, 0) + 1
            )
    unclassified = [
        attribution.run_id
        for attribution in attributions
        if attribution.primary_layer == UNKNOWN
        and by_run.get(attribution.run_id, {}).get("category") != "completed_success"
    ]
    return {
        "schema": "v13-diagnosis-taxonomy-1",
        "runs": len(records),
        "findings": sum(len(items) for items in grouped.values()),
        "layer_counts": dict(sorted(layer_counts.items())),
        "primary_counts": dict(sorted(primary_counts.items())),
        "layer_labels": dict(LAYER_LABELS),
        "attributions": [item.as_dict() for item in attributions],
        "unclassified_runs": unclassified,
        "rule": (
            "主层按 PROVIDER > INTERFACE > MEASUREMENT > BUDGET > MECHANISM > POLICY 优先；"
            "接口与测量问题永远不算进能力分母。"
        ),
    }


def taxonomy_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 失败归因分层",
        "",
        f"- 局数：{report.get('runs')}；诊断条目：{report.get('findings')}",
        f"- 规则：{report.get('rule')}",
        "",
        "## 主层分布",
        "",
        "| 层 | 含义 | 局数 |",
        "|---|---|---:|",
    ]
    for layer in LAYERS:
        count = (report.get("primary_counts") or {}).get(layer, 0)
        lines.append(f"| `{layer}` | {LAYER_LABELS[layer]} | {count} |")
    lines += [
        "",
        "## 逐局归因（带证据锚）",
        "",
        "| run_id | 地图 | 实验臂 | 主层 | 证据步 | 摘要 |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.get("attributions") or []:
        if not item.get("primary_layer"):
            continue
        steps = sorted(
            {
                step
                for anchor in item.get("anchors") or []
                for step in anchor.get("decision_steps") or []
            }
        )
        lines.append(
            f"| `{item['run_id']}` | {item['map_id']} | `{item['agent_id']}` | "
            f"`{item['primary_layer']}` | "
            f"{', '.join(str(step) for step in steps[:8]) or '—'} | {item['summary']} |"
        )
    if report.get("unclassified_runs"):
        lines += [
            "",
            "## 未归因局（证据不足，不猜）",
            "",
            *[f"- `{run_id}`" for run_id in report["unclassified_runs"]],
        ]
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------- fixtures
#: 离线正反例（V13-08-03）：每项都声明"应当归到哪一层"以及一个反例。
FIXTURES: dict[str, dict[str, Any]] = {
    "memory_route_short": {
        "question": "记忆写了路线但过短 → 策略层，不是接口层",
        "positive": {
            "finding_category": "memory_sequence_short",
            "expect_layer": POLICY,
            "evidence_steps": [3, 5],
        },
        "negative": {
            "finding_category": "memory_payload_rejected",
            "expect_layer": INTERFACE,
            "why": "同样是记忆问题，但载荷结构不合规属于接口。",
        },
    },
    "planning_conflict": {
        "question": "先 move 后 set_route 的整帧语义错误 → 策略层",
        "positive": {
            "finding_category": "frame_mismatch",
            "expect_layer": POLICY,
            "evidence_steps": [4],
        },
        "negative": {
            "finding_category": "key_action_attempted_rejected",
            "expect_layer": MECHANISM,
            "why": "机制动作被拒是环境机制层，不是策略层。",
        },
    },
    "reflection_not_activated": {
        "question": "反思从未触发 → 不是失败归因，而是无处理暴露",
        "positive": {
            "finding_category": "not_enough_evidence",
            "expect_layer": UNKNOWN,
            "note": "零触发时策略层不应被指控；报告用 NO_TREATMENT_EXPOSURE。",
        },
        "negative": {
            "finding_category": "no_progress_window",
            "expect_layer": POLICY,
            "why": "真的有连续无进展时才归策略层。",
        },
    },
    "map30_censored": {
        "question": "MAP-30 撞 token 上限 → 预算层",
        "positive": {
            "finding_category": "budget_censored",
            "expect_layer": BUDGET,
            "termination": "input_token_limit_exceeded",
        },
        "negative": {
            "finding_category": "unsupported_accusation",
            "expect_layer": MECHANISM,
            "termination": "ACCUSATION_REJECTED",
            "why": "走到法庭被拒是真实机制失败。",
        },
    },
}


def check_fixtures() -> dict[str, Any]:
    """验证 fixtures 的分类结果与声明一致（供 verify_v13 调用）。"""

    checked = 0
    failures: list[str] = []
    for name, fixture in FIXTURES.items():
        for side in ("positive", "negative"):
            case = fixture[side]
            layer = classify_category(str(case["finding_category"]))
            checked += 1
            if layer != case["expect_layer"]:
                failures.append(
                    f"{name}.{side}: {case['finding_category']} → {layer}，"
                    f"期望 {case['expect_layer']}"
                )
    return {"checked": checked, "failures": failures, "ok": not failures}


__all__ = [
    "BUDGET",
    "CATEGORY_LAYERS",
    "FIXTURES",
    "INTERFACE",
    "LAYERS",
    "LAYER_LABELS",
    "MECHANISM",
    "MEASUREMENT",
    "POLICY",
    "PROVIDER",
    "UNKNOWN",
    "RunAttribution",
    "attribute_run",
    "check_fixtures",
    "classify_category",
    "taxonomy_markdown",
    "taxonomy_report",
]
