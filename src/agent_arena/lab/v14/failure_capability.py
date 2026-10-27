"""V14 诊断锚点、能力画像缺口与结论强度（P1-3 / P1-4 / P1-6）。

三件事：

1. **归因锚点校验**：每条 Finding 必须能定位到
   ``(run_id, decision_index, action, public_result)``。没有锚点的结论一律降级为
   ``UNANCHORED``，不允许用"Agent 大概不理解……"这类未经证实的解释。
2. **正反 fixture**：把两种容易被混为一谈的失败分开——
   - **拒绝导致无进展**（`POLICY_BEHAVIOUR` / 接口层）：动作被环境拒绝，位置没变；
   - **有公开进展但预算失败**（`BUDGET_CENSORED`）：位置在推进，但预算用尽。
3. **结论强度三字段**：`evidence_level`（证据形式）、`mechanism_exposure`
   （干预是否真的发生）、`effect_direction`（描述性方向）三者独立，
   `SUPPORTED` 永不等价于"显著改善"或"因果证实"。

本模块只读：不修改 V13 的 taxonomy / capability 输出，只在之上补充字段。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.contracts import Finding
from agent_arena.lab.v13.capability import DIMENSIONS, capability_profile
from agent_arena.lab.v13.taxonomy import (
    BUDGET,
    INTERFACE,
    LAYERS,
    MEASUREMENT,
    MECHANISM,
    POLICY,
    PROVIDER,
    UNKNOWN,
)

#: 锚点完整性状态。
ANCHOR_COMPLETE = "ANCHORED"
ANCHOR_PARTIAL = "PARTIALLY_ANCHORED"
ANCHOR_MISSING = "UNANCHORED"

#: 结论强度三字段的取值域。
EVIDENCE_LEVELS: tuple[str, ...] = (
    "SUPPORTED",
    "TENTATIVE",
    "INSUFFICIENT",
    "NOT_TESTED",
)
MECHANISM_EXPOSURE: tuple[str, ...] = (
    "EXPOSED",
    "NO_TREATMENT_EXPOSURE",
    "NOT_APPLICABLE",
    "UNKNOWN",
)
EFFECT_DIRECTIONS: tuple[str, ...] = (
    "IMPROVED",
    "WORSE",
    "NO_DIFFERENCE",
    "MIXED",
    "NOT_MEASURABLE",
)

#: 层 → 是否可用于"能力"结论。接口/测量/Provider 三层**不得**算进能力分母。
CAPABILITY_ELIGIBLE_LAYERS: tuple[str, ...] = (MECHANISM, POLICY, BUDGET)
NON_CAPABILITY_LAYERS: tuple[str, ...] = (INTERFACE, MEASUREMENT, PROVIDER, UNKNOWN)

#: 本模块的 fixture 类别。
FIXTURE_REJECTED_NO_PROGRESS = "REJECTED_NO_PROGRESS"
FIXTURE_PROGRESS_THEN_BUDGET = "PROGRESS_THEN_BUDGET_CENSORED"

# --------------------------------------------------------------- anchor check
def finding_anchor(finding: Finding | dict[str, Any]) -> dict[str, Any]:
    """抽取并校验一条 Finding 的证据锚点。"""

    payload = finding.as_dict() if isinstance(finding, Finding) else dict(finding)
    run_id = str(payload.get("run_id") or "")
    steps = tuple(int(item) for item in payload.get("evidence_steps") or ())
    events = tuple(str(item) for item in payload.get("evidence_event_ids") or ())
    action = payload.get("action")
    public_result = payload.get("public_result")
    has_step = bool(steps) or bool(events)
    if run_id and has_step and action is not None and public_result is not None:
        status = ANCHOR_COMPLETE
    elif run_id and has_step:
        status = ANCHOR_PARTIAL
    else:
        status = ANCHOR_MISSING
    return {
        "category": payload.get("category"),
        "run_id": run_id,
        "decision_index": steps[0] if steps else None,
        "evidence_steps": list(steps),
        "evidence_event_ids": list(events),
        "action": action,
        "public_result": public_result,
        "status": status,
        "anchor": (
            f"{run_id}#{steps[0]}" if run_id and steps else ""
        ),
        "note": (
            "锚点完整：可定位到具体决策与公开结果。"
            if status == ANCHOR_COMPLETE
            else (
                "锚点部分：有 run 与决策序号，但缺少动作或公开结果，"
                "只能作线索，不能作结论。"
                if status == ANCHOR_PARTIAL
                else "无锚点：不得据此断言 Agent 的内部原因。"
            )
        ),
    }

def audit_findings(findings: list[Finding | dict[str, Any]]) -> dict[str, Any]:
    """批量校验锚点，并统计各层可用性。"""

    rows = [finding_anchor(item) for item in findings]
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {
        "schema": "v14-finding-anchors-1",
        "findings": len(rows),
        "by_status": by_status,
        "anchored": by_status.get(ANCHOR_COMPLETE, 0),
        "partial": by_status.get(ANCHOR_PARTIAL, 0),
        "unanchored": by_status.get(ANCHOR_MISSING, 0),
        "rows": rows,
        "rule": (
            "没有 (run_id, decision_index, action, public_result) 的结论只能标 "
            "`UNANCHORED`，不得写成「Agent 不理解……」。"
        ),
    }

# ------------------------------------------------------------- positive/negative fixtures
def _trace_event(
    decision_index: int, action: dict[str, Any], public_result: str
) -> dict[str, Any]:
    return {
        "decision_index": decision_index,
        "action": action,
        "public_result": public_result,
    }

def rejected_no_progress_fixture() -> dict[str, Any]:
    """正例：动作被拒 → 位置不变 → 无公开进展（策略/接口层）。"""

    trace = [
        _trace_event(0, {"tool": "move", "bearing": "north"}, "MOVED"),
        _trace_event(1, {"tool": "move", "bearing": "north"}, "BEARING_NOT_AVAILABLE"),
        _trace_event(2, {"tool": "move", "bearing": "north"}, "BEARING_NOT_AVAILABLE"),
        _trace_event(3, {"tool": "move", "bearing": "north"}, "BEARING_NOT_AVAILABLE"),
    ]
    rejected = [item for item in trace if "NOT_AVAILABLE" in item["public_result"]]
    progressed = [
        item for item in trace[1:] if item["public_result"] == "MOVED"
    ]
    finding = Finding(
        category="repeated_rejected_action",
        severity="warning",
        map_id="MAP-22",
        run_id="fixture-rejected",
        evidence_steps=(1, 2, 3),
        summary="连续 3 次同一方位被拒，位置没有变化。",
        detail="公开结果为 BEARING_NOT_AVAILABLE，属于可观察行为问题。",
        suggested_check="检查是否在写入方位前先读取公开地图。",
    )
    anchor = finding_anchor(
        {
            **finding.as_dict(),
            "action": {"tool": "move", "bearing": "north"},
            "public_result": "BEARING_NOT_AVAILABLE",
        }
    )
    return {
        "fixture": FIXTURE_REJECTED_NO_PROGRESS,
        "expected_layer": POLICY,
        "expected_capability_eligible": True,
        "rejected_steps": len(rejected),
        "progress_steps": len(progressed),
        "public_progress_after_step_0": bool(progressed),
        "anchor": anchor,
        "trace": trace,
        "reading": (
            "被拒且没有公开进展 → 归因到策略/接口层，可以进能力分母；"
            "但若被拒是契约形状导致，则应改判 INTERFACE_CONTRACT（见反例）。"
        ),
    }

def progress_then_budget_fixture() -> dict[str, Any]:
    """反例：位置在推进，但预算耗尽（截尾，不是能力）。"""

    trace = [
        _trace_event(0, {"tool": "move", "bearing": "north"}, "MOVED"),
        _trace_event(1, {"tool": "move", "bearing": "east"}, "MOVED"),
        _trace_event(2, {"tool": "read_map"}, "MAP_READ"),
        _trace_event(3, {"tool": "move", "bearing": "south"}, "MOVED"),
    ]
    finding = Finding(
        category="budget_censored",
        severity="info",
        map_id="MAP-22",
        run_id="fixture-budget",
        evidence_steps=(3,),
        summary="最后一步之后预算用尽，机制尚未闭合。",
        detail="公开轨迹显示位置持续变化，没有出现拒绝或非法动作。",
        suggested_check="提高单局预算后重测，或改用更省步数的策略。",
    )
    anchor = finding_anchor(
        {
            **finding.as_dict(),
            "action": {"tool": "move", "bearing": "south"},
            "public_result": "MOVED",
        }
    )
    return {
        "fixture": FIXTURE_PROGRESS_THEN_BUDGET,
        "expected_layer": BUDGET,
        "expected_capability_eligible": False,
        "rejected_steps": 0,
        "progress_steps": len([item for item in trace if item["public_result"] == "MOVED"]),
        "public_progress_after_step_0": True,
        "anchor": anchor,
        "trace": trace,
        "reading": (
            "有公开进展但预算耗尽 → 归因到 BUDGET_CENSORED，"
            "**不得**算进能力分母，也不得写成「推理能力极弱」。"
        ),
    }

def interface_artifact_fixture() -> dict[str, Any]:
    """接口假象：被拒原因是契约形状（不是策略选择）。"""

    bad_action = {"tool": "write_memory", "facts": {"key": "path_state"}}
    trace = [
        _trace_event(0, bad_action, "INVALID_MEMORY_PAYLOAD"),
        _trace_event(1, bad_action, "INVALID_MEMORY_PAYLOAD"),
    ]
    finding = Finding(
        category="memory_payload_rejected",
        severity="critical",
        map_id="MAP-22",
        run_id="fixture-interface",
        evidence_steps=(0, 1),
        summary="记忆写入全部被拒：公开契约没有说明 facts 需要内部字段名。",
        detail="两次写入都返回 INVALID_MEMORY_PAYLOAD，属于契约形状问题。",
        suggested_check="检查公开动作契约是否列出了嵌套字段名。",
    )
    anchor = finding_anchor(
        {
            **finding.as_dict(),
            "action": bad_action,
            "public_result": "INVALID_MEMORY_PAYLOAD",
        }
    )
    return {
        "fixture": "INTERFACE_ARTEFACT",
        "expected_layer": INTERFACE,
        "expected_capability_eligible": False,
        "rejected_steps": len(trace),
        "progress_steps": 0,
        "public_progress_after_step_0": False,
        "anchor": anchor,
        "trace": trace,
        "reading": (
            "同样「被拒且无进展」，但原因是契约形状 → INTERFACE_CONTRACT，"
            "**不得**进能力分母。这就是正反 fixture 必须成对存在的原因。"
        ),
    }

def failure_fixtures() -> dict[str, Any]:
    return {
        "schema": "v14-failure-fixtures-1",
        "fixtures": [
            rejected_no_progress_fixture(),
            progress_then_budget_fixture(),
            interface_artifact_fixture(),
        ],
        "layer_eligibility": {
            layer: layer in CAPABILITY_ELIGIBLE_LAYERS for layer in LAYERS
        },
        "note": (
            "「被拒无进展」与「有进展但预算耗尽」必须分开；"
            "「契约形状导致被拒」必须再单独一层。三者混算会同时高估接口缺陷与低估能力。"
        ),
    }

# ----------------------------------------------------------- capability gaps
def capability_with_gaps(
    records: list[dict[str, Any]], *, min_runs: int = 3
) -> dict[str, Any]:
    """在 V13 六维画像之上补：适用样本、独立 seed、重复数、缺口字段。"""

    profile = capability_profile(records, min_runs=min_runs)
    rows = []
    for item in profile["dimensions"]:
        dimension = item["dimension"]
        from agent_arena.lab.v13.capability import MAP_TAGS

        maps = [map_id for map_id, tags in MAP_TAGS.items() if dimension in tags]
        selected = [rec for rec in records if str(rec.get("map_id")) in set(maps)]
        seeds = sorted({int(rec.get("environment_seed") or 0) for rec in selected})
        replicates = sorted(
            {int(rec.get("replicate_index") or 0) for rec in selected}
        )
        measured = item["measurable_runs"]
        gaps: list[str] = []
        if measured == 0:
            gaps.append("UNAVAILABLE")
        if len(seeds) < min_runs:
            gaps.append("FEW_INDEPENDENT_SEEDS")
        if len(replicates) < 2:
            gaps.append("NO_REPLICATES")
        if item["budget_censored"]:
            gaps.append("HAS_CENSORED_RUNS")
        if item["missing_maps"]:
            gaps.append("MISSING_MAPS")
        rows.append(
            {
                "dimension": dimension,
                "label": item["label"],
                "status": "UNAVAILABLE" if measured == 0 else "AVAILABLE",
                "applicable_maps": len(maps),
                "observed_maps": item["observed_map_count"],
                "measurable_runs": measured,
                "runs": item["runs"],
                "independent_seeds": seeds,
                "independent_seed_count": len(seeds),
                "replicate_indices": replicates,
                "successes": item["successes"],
                "mechanism_failures": item["mechanism_failures"],
                "budget_censored": item["budget_censored"],
                "success_rate": item["success_rate"],
                "evidence_level": item["evidence_level"],
                "gaps": gaps,
                "note": (
                    "`UNAVAILABLE` 表示没有可测样本，**不是能力为 0**；"
                    "样本/seed/重复数必须与成功率并列展示。"
                ),
            }
        )
    return {
        "schema": "v14-capability-1",
        "dimensions": rows,
        "dimension_count": len(rows),
        "unavailable": [row["dimension"] for row in rows if row["status"] == "UNAVAILABLE"],
        "label_status": profile["label_status"],
        "label_note": profile["label_note"],
        "aggregation_rule": (
            "按机制维度聚合，不对异质指标求总分；每个维度都带适用样本、独立 seed、"
            "重复数与观察缺口。"
        ),
    }

def capability_markdown_v14(profile: dict[str, Any]) -> str:
    lines = [
        "## 2. 六维能力画像（P1-4）",
        "",
        f"- 标注状态：`{profile['label_status']}`",
        f"- 聚合规则：{profile['aggregation_rule']}",
        "",
        "| 维度 | 状态 | 适用图 | 已观测图 | 可测局 | 独立 seed "
        "| 重复编号 | 成功 | 机制失败 | 截尾 | 成功率 | 缺口 |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in profile["dimensions"]:
        rate = row["success_rate"]
        lines.append(
            f"| {row['label']} | `{row['status']}` | {row['applicable_maps']} | "
            f"{row['observed_maps']} | {row['measurable_runs']} | "
            f"{row['independent_seed_count']} | {row['replicate_indices']} | "
            f"{row['successes']} | {row['mechanism_failures']} | "
            f"{row['budget_censored']} | {'—' if rate is None else rate} | "
            f"{', '.join(row['gaps']) or '无'} |"
        )
    lines += [
        "",
        "> `UNAVAILABLE` 是「没有可测样本」，不是「能力为 0」；"
        "所有成功率必须与样本数、独立 seed 数、重复数一起读。",
        "",
    ]
    return "\n".join(lines)

# ------------------------------------------------------- conclusion strength
def conclusion_strength(
    *,
    evidence_level: str,
    mechanism_exposure: str,
    effect_direction: str,
    reasons: tuple[str, ...] = (),
) -> dict[str, Any]:
    """把"结论等级"拆成三个独立字段，并给出禁止的读法。"""

    if evidence_level not in EVIDENCE_LEVELS:
        raise ValueError(f"未知 evidence_level：{evidence_level}")
    if mechanism_exposure not in MECHANISM_EXPOSURE:
        raise ValueError(f"未知 mechanism_exposure：{mechanism_exposure}")
    if effect_direction not in EFFECT_DIRECTIONS:
        raise ValueError(f"未知 effect_direction：{effect_direction}")

    forbidden: list[str] = []
    if evidence_level != "SUPPORTED":
        forbidden.append("不得写成「已证实」")
    if mechanism_exposure == "NO_TREATMENT_EXPOSURE":
        forbidden.append("不得写成「策略无效」（干预从未发生）")
    if effect_direction in {"NOT_MEASURABLE", "MIXED"}:
        forbidden.append("不得写成「有效」或「显著提升」")
    forbidden.append("`SUPPORTED` 不等于显著改善，也不等于因果证实")

    return {
        "evidence_level": evidence_level,
        "mechanism_exposure": mechanism_exposure,
        "effect_direction": effect_direction,
        "reasons": list(reasons),
        "forbidden_claims": forbidden,
        "reading": (
            "三个字段独立：证据形式（能不能算）、干预暴露（有没有发生）、"
            "效果方向（描述性差异）。任一为否定时都不能给出「策略有效」的结论。"
        ),
    }

def conclusion_strength_markdown(item: dict[str, Any]) -> str:
    lines = [
        "## 3. 结论强度（P1-6）",
        "",
        "| 字段 | 取值 | 含义 |",
        "|---|---|---|",
        f"| `evidence_level` | `{item['evidence_level']}` | 证据形式是否满足门槛 |",
        f"| `mechanism_exposure` | `{item['mechanism_exposure']}` | 干预是否真的发生 |",
        f"| `effect_direction` | `{item['effect_direction']}` | 描述性方向，不是因果 |",
        "",
        "禁止的读法：",
        "",
    ]
    lines += [f"- {text}" for text in item["forbidden_claims"]]
    if item["reasons"]:
        lines += ["", "理由："] + [f"- {reason}" for reason in item["reasons"]]
    lines += ["", f"> {item['reading']}", ""]
    return "\n".join(lines)

def failure_capability_report(
    records: list[dict[str, Any]],
    *,
    findings: list[Finding | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """一次性产出 P1-3 / P1-4 / P1-6 三部分。"""

    anchors = audit_findings(findings or [])
    return {
        "schema": "v14-failure-capability-1",
        "anchors": anchors,
        "fixtures": failure_fixtures(),
        "capability": capability_with_gaps(records),
        "conclusion": conclusion_strength(
            evidence_level="INSUFFICIENT",
            mechanism_exposure="NO_TREATMENT_EXPOSURE",
            effect_direction="NOT_MEASURABLE",
            reasons=(
                "V14 未获真实模型试验批准：没有 LIVE 样本。",
                "历史 V12 CSV 缺 mechanism_triggered 字段，机制暴露未知。",
            ),
        ),
        "dimensions": list(DIMENSIONS),
    }

def failure_capability_markdown(report: dict[str, Any]) -> str:
    fixtures = report["fixtures"]
    anchors = report["anchors"]
    lines = [
        "# V14 失败归因与能力画像（P1-3 / P1-4 / P1-6）",
        "",
        "> 只读分析：不修改 V13 的 taxonomy / capability 输出，只在之上补充字段。",
        "",
        "## 1. 七层归因与正反 fixture（P1-3）",
        "",
        "| 层 | 是否可进能力分母 | 含义 |",
        "|---|---|---|",
    ]
    labels = {
        INTERFACE: "接口/契约问题（不是能力）",
        MEASUREMENT: "测量覆盖问题（不是能力）",
        BUDGET: "预算截尾（没测完）",
        MECHANISM: "环境机制真实触发但未达成",
        POLICY: "策略可观察行为",
        PROVIDER: "Provider/基础设施",
        UNKNOWN: "证据不足",
    }
    for layer in LAYERS:
        eligible = fixtures["layer_eligibility"][layer]
        lines.append(
            f"| `{layer}` | {'是' if eligible else '**否**'} | {labels[layer]} |"
        )
    lines += [
        "",
        "### 1.1 三个 fixture",
        "",
        "| fixture | 期望层 | 可进能力分母 | 被拒步 | 有公开进展 | 读法 |",
        "|---|---|---|---:|---|---|",
    ]
    for item in fixtures["fixtures"]:
        lines.append(
            f"| `{item['fixture']}` | `{item['expected_layer']}` | "
            f"{'是' if item['expected_capability_eligible'] else '**否**'} | "
            f"{item['rejected_steps']} | "
            f"{'是' if item['public_progress_after_step_0'] else '否'} | "
            f"{item['reading']} |"
        )
    lines += ["", f"> {fixtures['note']}", "", "### 1.2 锚点校验", ""]
    if anchors["findings"]:
        lines += [
            f"- 共 {anchors['findings']} 条 Finding："
            f"`{ANCHOR_COMPLETE}` {anchors['anchored']} / "
            f"`{ANCHOR_PARTIAL}` {anchors['partial']} / "
            f"`{ANCHOR_MISSING}` {anchors['unanchored']}",
            f"- 规则：{anchors['rule']}",
            "",
        ]
        lines += [
            "| 类别 | 锚点 | 状态 | 动作 | 公开结果 |",
            "|---|---|---|---|---|",
        ]
        for row in anchors["rows"][:20]:
            lines.append(
                f"| `{row['category']}` | `{row['anchor'] or '—'}` | `{row['status']}` | "
                f"{row['action'] or '—'} | {row['public_result'] or '—'} |"
            )
        lines.append("")
    else:
        lines += [
            "- 本批没有逐局 Finding 输入（历史 CSV 不含 Finding 明细）；"
            "锚点校验逻辑由 3 个 fixture 与单测覆盖。",
            f"- 规则：{anchors['rule']}",
            "",
        ]
    lines.append(capability_markdown_v14(report["capability"]))
    lines.append(conclusion_strength_markdown(report["conclusion"]))
    return "\n".join(lines)

__all__ = [
    "ANCHOR_COMPLETE",
    "ANCHOR_MISSING",
    "ANCHOR_PARTIAL",
    "CAPABILITY_ELIGIBLE_LAYERS",
    "EFFECT_DIRECTIONS",
    "EVIDENCE_LEVELS",
    "FIXTURE_PROGRESS_THEN_BUDGET",
    "FIXTURE_REJECTED_NO_PROGRESS",
    "MECHANISM_EXPOSURE",
    "NON_CAPABILITY_LAYERS",
    "audit_findings",
    "capability_markdown_v14",
    "capability_with_gaps",
    "conclusion_strength",
    "conclusion_strength_markdown",
    "failure_capability_markdown",
    "failure_capability_report",
    "failure_fixtures",
    "finding_anchor",
    "interface_artifact_fixture",
    "progress_then_budget_fixture",
    "rejected_no_progress_fixture",
]
