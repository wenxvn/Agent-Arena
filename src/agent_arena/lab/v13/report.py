"""模板化离线实验报告（P2-4 / V13-10-01 … 10-03、10-07）。

原则：

- **零 LLM**：报告由模板 + 已落盘数字生成；任何"润色"都必须是独立可选项，
  且不得覆盖基础报告；
- **每条结论带锚点**：``experiment:<id>`` / ``run:<run_id>`` / ``decision:<run_id>#<n>``，
  报告里出现的每个数字都能回到原始记录；
- **结论分级**：``SUPPORTED`` / ``TENTATIVE`` / ``INSUFFICIENT`` / ``NOT_TESTED``，
  等级只看证据结构（样本、截尾、可比性），不看结果好坏；
- **负面结果必须保留**：反向、零提升、成本升高都要单独成节；
- 模拟数据必须写 ``SIMULATED``，历史数据必须写 ``HISTORICAL``。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_arena.lab.compare import CATEGORY_LABELS, VALID_DENOMINATOR_CATEGORIES
from agent_arena.lab.contracts import Finding

LEVEL_SUPPORTED = "SUPPORTED"
LEVEL_TENTATIVE = "TENTATIVE"
LEVEL_INSUFFICIENT = "INSUFFICIENT"
LEVEL_NOT_TESTED = "NOT_TESTED"

CONCLUSION_LEVELS = (LEVEL_SUPPORTED, LEVEL_TENTATIVE, LEVEL_INSUFFICIENT, LEVEL_NOT_TESTED)

SOURCE_LIVE = "LIVE"
SOURCE_SIMULATED = "SIMULATED"
SOURCE_HISTORICAL = "HISTORICAL"


def anchor_run(run_id: str) -> str:
    return f"run:{run_id}"


def anchor_decision(run_id: str, step: int) -> str:
    return f"decision:{run_id}#{step}"


def anchor_experiment(experiment_id: str) -> str:
    return f"experiment:{experiment_id}"


def _sampling_claim(sampling: dict[str, Any]) -> str:
    """由采样登记推导对外口径（不在 `public_dict` 里存派生字段）。"""

    support = str(sampling.get("support") or "UNKNOWN")
    seed_requested = sampling.get("seed_requested")
    if support == "SUPPORTED" and seed_requested is not None:
        return "SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED"
    if support == "UNSUPPORTED":
        return "UNSUPPORTED"
    return "UNKNOWN"


@dataclass
class Conclusion:
    level: str
    text: str
    anchors: list[str] = field(default_factory=list)
    scope: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "anchors": list(self.anchors),
            "scope": self.scope,
        }

    def markdown(self) -> str:
        anchors = "、".join(f"`{item}`" for item in self.anchors) or "—"
        scope = f"（范围：{self.scope}）" if self.scope else ""
        return f"- `{self.level}`{scope} {self.text}  \n  锚点：{anchors}"


def _source_label(mode: str) -> tuple[str, str]:
    if mode == "simulated":
        return (
            SOURCE_SIMULATED,
            "**SIMULATED**：确定性脚本 Provider，只验证调用链/预算/诊断，"
            "不代表任何真实模型能力。",
        )
    if mode == "live":
        return SOURCE_LIVE, "**LIVE**：真实模型请求；结论受样本量与 Provider 稳定性限制。"
    return SOURCE_HISTORICAL, "**HISTORICAL**：只读历史记录，不是本轮新跑。"


def _denominator(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, Any] = {
        "all_attempted": len(records),
        "evaluable": 0,
        "uncensored_finished": 0,
        "censored": 0,
        "invalid": 0,
    }
    for record in records:
        category = str(record.get("category") or "")
        if category in VALID_DENOMINATOR_CATEGORIES:
            counts["evaluable"] += 1
        if category in {"completed_success", "mechanism_failure"}:
            counts["uncensored_finished"] += 1
        if category == "budget_censored":
            counts["censored"] += 1
        if category in {
            "invalid_run",
            "provider_error",
            "cancelled",
            "interrupted",
            "pending",
        }:
            counts["invalid"] += 1
    counts["censored_ratio"] = round(
        counts["censored"] / counts["evaluable"], 4
    ) if counts["evaluable"] else 0
    return counts


def _arm_rows(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in comparison.get("arms") or []]


def _negative_results(
    comparison: dict[str, Any], records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """反向/零提升/成本升高 —— 一律保留，不因不好看而删。"""

    rows: list[dict[str, Any]] = []
    arms = _arm_rows(comparison)
    if len(arms) < 2:
        return rows
    baseline = next((arm for arm in arms if str(arm.get("agent_id")) == "basic.v1"), arms[0])
    base_rate = baseline.get("success_rate")
    base_cost = baseline.get("mean_cost_cny")
    for arm in arms:
        if arm is baseline:
            continue
        rate = arm.get("success_rate")
        cost = arm.get("mean_cost_cny")
        reasons: list[str] = []
        if rate is not None and base_rate is not None and rate < base_rate:
            reasons.append(f"成功率低于基线（{rate} < {base_rate}）")
        if rate is not None and base_rate is not None and rate == base_rate:
            reasons.append(f"成功率与基线相同（{rate}），没有可观察提升")
        if (
            cost is not None
            and base_cost is not None
            and cost > base_cost
        ):
            reasons.append(f"平均费用高于基线（{cost:.6f} > {base_cost:.6f}）")
        if arm.get("invalid_actions"):
            reasons.append(f"非法动作 {arm['invalid_actions']} 次")
        if reasons:
            rows.append(
                {
                    "agent_id": arm.get("agent_id"),
                    "reasons": reasons,
                    "success_rate": rate,
                    "mean_cost_cny": cost,
                    "anchors": [
                        anchor_run(str(item.get("run_id")))
                        for item in records
                        if str(item.get("agent_id")) == str(arm.get("agent_id"))
                    ][:3],
                }
            )
    return rows


def _failure_section(
    findings: Iterable[Finding], taxonomy: dict[str, Any] | None
) -> list[str]:
    items = list(findings)
    lines = [
        "## 6. 失败原因（分层归因）",
        "",
    ]
    if taxonomy:
        lines += ["| 层 | 局数 |", "|---|---:|"]
        for layer, count in (taxonomy.get("primary_counts") or {}).items():
            lines.append(f"| `{layer}` | {count} |")
        lines.append("")
    if not items:
        lines.append("- 没有产生证据级诊断。")
        return lines
    lines += ["| 地图 | run_id | 类别 | 证据步 | 摘要 |", "|---|---|---|---|---|"]
    for finding in items[:20]:
        steps = ", ".join(str(step) for step in finding.evidence_steps) or "—"
        lines.append(
            f"| {finding.map_id} | `{finding.run_id}` | `{finding.category}` | {steps} | "
            f"{finding.summary} |"
        )
    lines.append("")
    return lines


def build_report_v13(
    *,
    experiment: dict[str, Any],
    summary: dict[str, Any],
    comparison: dict[str, Any],
    records: list[dict[str, Any]],
    findings: Iterable[Finding] = (),
    stability: dict[str, Any] | None = None,
    validity: dict[str, Any] | None = None,
    capability: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
    protocol: dict[str, Any] | None = None,
    source: str = "",
) -> str:
    """生成 V13 结构化报告（Markdown）。"""

    mode = str(experiment.get("mode") or summary.get("mode") or "")
    source_label, source_note = _source_label(mode)
    if source:
        source_label = source
    denominator = _denominator(records)
    experiment_id = str(summary.get("experiment_id") or "")
    arms = _arm_rows(comparison)
    negatives = _negative_results(comparison, records)
    successes = denominator["evaluable"] and sum(
        1 for item in records if item.get("category") == "completed_success"
    )

    conclusions: list[Conclusion] = []
    if denominator["evaluable"] == 0:
        conclusions.append(
            Conclusion(
                LEVEL_NOT_TESTED,
                "没有可评估的子局（全部未执行/无效），本轮不能回答研究问题。",
                [anchor_experiment(experiment_id)],
            )
        )
    else:
        level = LEVEL_SUPPORTED
        reasons: list[str] = []
        if denominator["evaluable"] < 3:
            level = LEVEL_TENTATIVE
            reasons.append(f"有效分母仅 {denominator['evaluable']}")
        if denominator["censored_ratio"] >= 0.3:
            level = LEVEL_INSUFFICIENT
            reasons.append(f"截尾比例 {denominator['censored_ratio']}")
        if str(comparison.get("verdict")) == "INCOMPARABLE":
            level = LEVEL_INSUFFICIENT
            reasons.append("配对不可比")
        conclusions.append(
            Conclusion(
                level,
                f"有效分母 {denominator['evaluable']} 局，成功 {successes} 局；"
                f"可比性判定 `{comparison.get('verdict')}`。",
                [anchor_experiment(experiment_id)],
                scope="；".join(reasons) or "同版本、同预算、同 seed 配对",
            )
        )
    if stability and stability.get("flip_rate") is not None:
        conclusions.append(
            Conclusion(
                LEVEL_TENTATIVE,
                f"同条件重复的结局翻转率为 {stability['flip_rate']}"
                f"（{stability.get('groups_with_flip')}/{stability.get('comparable_groups')} 组）；"
                "单次观测不足以下架构结论。",
                [anchor_experiment(experiment_id)],
                scope="重复不是新的环境 seed",
            )
        )
    if negatives:
        conclusions.append(
            Conclusion(
                LEVEL_TENTATIVE,
                f"{len(negatives)} 个实验臂出现反向、零提升或成本升高，已如实保留。",
                [anchor_experiment(experiment_id)],
            )
        )

    lines: list[str] = [
        f"# V13 实验报告：{experiment.get('name') or summary.get('name')}",
        "",
        f"- `experiment_id`：`{experiment_id}`",
        f"- 数据来源：`{source_label}` — {source_note}",
        f"- 状态：`{summary.get('state')}`；执行通道：`{mode}`",
        f"- 模型 / Provider：`{summary.get('model')}` / `{summary.get('provider_id')}`",
        f"- 地图：{', '.join(summary.get('maps') or [])}",
        f"- 环境 seed：{summary.get('seeds')}；重复次数：{experiment.get('replicates', 1)}",
        f"- 实验臂：{', '.join(str(arm.get('agent_id')) for arm in arms)}",
        f"- 运行时版本：`{summary.get('runtime_version') or 'unknown'}`",
        "",
        "## 0. 结论摘要（分级 + 锚点）",
        "",
        *[item.markdown() for item in conclusions],
        "",
        "## 1. 研究问题与预注册",
        "",
    ]
    if protocol:
        lines += [
            f"- 协议：`{protocol.get('protocol_id')}`（v{protocol.get('version')}）",
            f"- 问题：{protocol.get('question')}",
            f"- 主指标：`{protocol.get('primary_metric')}`",
            f"- 次要指标：{', '.join(protocol.get('secondary_metrics') or []) or '—'}",
            f"- 停止规则：{'；'.join(protocol.get('stop_rules') or []) or '—'}",
            f"- 来源：`{protocol.get('source')}`；"
            f"冻结指纹 `{protocol.get('fingerprint', '')[:12]}`",
        ]
    else:
        lines.append(
            "- **未预注册协议**：本报告属于 `ad_hoc` 分析，结论强度上限为 `TENTATIVE`。"
        )
    sampling = experiment.get("sampling") or {}
    sampling_claim = _sampling_claim(sampling)
    lines += [
        "",
        "## 2. 设置与可比较性",
        "",
        f"- 配对判定：`{comparison.get('verdict')}`",
        *[f"  - 不可比原因：{reason}" for reason in comparison.get("reasons") or []],
        f"- 采样参数登记：support=`{sampling.get('support', 'UNKNOWN')}`，"
        f"对外口径 `{sampling_claim}`"
        "（环境 seed 固定 ≠ 模型输出可复现）",
        "- 有效分母只含：完成且成功 / 机制失败 / 预算截尾；Provider 错误、取消、"
        "中断、策略异常**不计入**。",
        "",
        "## 3. 分母与结果",
        "",
        "| 口径 | 值 |",
        "|---|---:|",
        f"| all_attempted | {denominator['all_attempted']} |",
        f"| evaluable | {denominator['evaluable']} |",
        f"| uncensored_finished | {denominator['uncensored_finished']} |",
        f"| censored | {denominator['censored']} |",
        f"| invalid | {denominator['invalid']} |",
        f"| censored_ratio | {denominator['censored_ratio']} |",
        "",
        "| 实验臂 | 版本 | 局数 | 有效 | 成功 | 成功率 | 平均请求 | 平均费用 CNY |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        lines.append(
            f"| `{arm.get('agent_id')}` | {arm.get('agent_version') or '—'} | "
            f"{arm.get('runs')} | {arm.get('valid_denominator')} | {arm.get('successes')} | "
            f"{arm.get('success_rate')} | {arm.get('mean_requests')} | "
            f"{arm.get('mean_cost_cny')} |"
        )
    lines += ["", "### 单局类别分布", "", "| 类别 | 局数 |", "|---|---:|"]
    for category, count in (summary.get("categories") or {}).items():
        lines.append(f"| {CATEGORY_LABELS.get(category, category)}（`{category}`） | {count} |")
    lines += [
        "",
        "### 逐局锚点（每个数字都可回到原始 run）",
        "",
        "| run_id | 地图 | seed | 实验臂 | 类别 | 锚点 |",
        "|---|---|---:|---|---|---|",
    ]
    for record in records[:40]:
        lines.append(
            f"| `{record.get('run_id')}` | {record.get('map_id')} | "
            f"{record.get('environment_seed')} | `{record.get('agent_id')}` | "
            f"`{record.get('category')}` | `{anchor_run(str(record.get('run_id')))}` |"
        )
    if len(records) > 40:
        lines.append(f"| … | 其余 {len(records) - 40} 局见 runs.csv | — | — | — | — |")
    lines += ["", "## 4. 负面结果（如实保留）", ""]
    if negatives:
        lines += ["| 实验臂 | 原因 | 锚点 |", "|---|---|---|"]
        for row in negatives:
            lines.append(
                f"| `{row['agent_id']}` | {'；'.join(row['reasons'])} | "
                f"{'、'.join(f'`{a}`' for a in row['anchors']) or '—'} |"
            )
    else:
        lines.append("- 没有可判定的负面结果（或只有一个实验臂）。")
    budget = summary.get("budget") or {}
    lines += [
        "",
        "## 5. 成本",
        "",
        f"- 已结算：CNY {budget.get('cost_settled_cny', '0')}",
        f"- 未知消费：{'是' if budget.get('cost_unknown') else '否'}",
        f"- 请求数：{budget.get('requests_used', 0)}",
    ]
    if ledger:
        lines.append(
            f"- 本地账本审计：`{ledger.get('status', ledger.get('external_reconciliation'))}`"
        )
    lines += [""]
    lines += _failure_section(findings, taxonomy)
    if stability:
        lines += [
            "## 7. 重复稳定性",
            "",
            f"- 可比分组：{stability.get('comparable_groups')}；"
            f"翻转分组：{stability.get('groups_with_flip')}；"
            f"翻转率：{stability.get('flip_rate')}",
            f"- 统计单位：{stability.get('units', {}).get('warning', '—')}",
            "",
        ]
    if validity:
        lines += ["## 8. 地图效度（构念层）", "", "| 地图 | 标签 | 理由 |", "|---|---|---|"]
        for row in validity.get("maps") or []:
            lines.append(
                f"| {row['map_id']} | `{row['composite']}` | "
                f"{'；'.join(row.get('reasons') or [])[:160]} |"
            )
        lines.append("")
    if capability:
        lines += [
            "## 9. 机制级能力画像",
            "",
            "| 维度 | 可测局 | 成功率 | 证据等级 |",
            "|---|---:|---:|---|",
        ]
        for item in capability.get("dimensions") or []:
            lines.append(
                f"| {item['label']} | {item['measurable_runs']} | "
                f"{item['success_rate'] if item['success_rate'] is not None else '—'} | "
                f"`{item['evidence_level']}` |"
            )
        lines += ["", f"> 标注状态：`{capability.get('label_status')}`（不是 human_approved）", ""]
    lines += [
        "## 10. 统计与解释限制",
        "",
        "- 每个配对键通常只有 1 局；重复次数增加不改变「同一环境 seed」这一事实。",
        "- 结论等级由证据结构决定，不由成功率高低决定。",
        "- 模拟数据不能用于声称模型能力；历史数据不能冒充本轮新结果。",
        "- 接口/测量层的问题不算能力差异（见分层归因）。",
        "",
        "## 11. 下一轮可验证假设",
        "",
        "- 在同一 `(map, seed, replicate_index)` 上只改一个开关，重复 ≥3 次，"
        "观察首次差异步是否前移。",
        "- 若某条件翻转率仍 > 20%，先扩大重复次数，再讨论架构优劣。",
        "- 预算截尾的图先做预算阶梯，不要用低预算的 0 成功当作能力结论。",
        "",
        "## 12. 复现",
        "",
        "```bash",
        "uv run python scripts/verify_v13.py          # 离线一键验收",
        "uv run python scripts/demo_v13.py            # 零 Key 演示（SIMULATED）",
        "```",
        "",
        f"实验目录：`runs/lab/{experiment_id}/`；子局仍在 `runs/web/<run_id>/`。",
        "",
    ]
    return "\n".join(lines)


def report_payload(
    *,
    experiment: dict[str, Any],
    summary: dict[str, Any],
    comparison: dict[str, Any],
    records: list[dict[str, Any]],
    stability: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
    validity: dict[str, Any] | None = None,
    capability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """机器可读版报告（CSV/JSON 导出用）。"""

    return {
        "schema": "v13-report-1",
        "experiment_id": summary.get("experiment_id"),
        "mode": summary.get("mode"),
        "state": summary.get("state"),
        "denominator": _denominator(records),
        "arms": _arm_rows(comparison),
        "verdict": comparison.get("verdict"),
        "reasons": list(comparison.get("reasons") or []),
        "categories": dict(summary.get("categories") or {}),
        "budget": dict(summary.get("budget") or {}),
        "negative_results": _negative_results(comparison, records),
        "stability": {
            "flip_rate": (stability or {}).get("flip_rate"),
            "comparable_groups": (stability or {}).get("comparable_groups"),
            "groups_with_flip": (stability or {}).get("groups_with_flip"),
        }
        if stability
        else None,
        "taxonomy": (taxonomy or {}).get("primary_counts"),
        "validity": [row.get("composite") for row in (validity or {}).get("maps") or []],
        "capability": [
            {
                "dimension": item.get("dimension"),
                "evidence_level": item.get("evidence_level"),
                "measurable_runs": item.get("measurable_runs"),
            }
            for item in (capability or {}).get("dimensions") or []
        ],
        "read_only_source": True,
    }


def write_report(
    directory: Path, markdown: str, payload: dict[str, Any]
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    md_path = directory / "report_v13.md"
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    json_path = directory / "report_v13.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {md_path.name: md_path, json_path.name: json_path}


__all__ = [
    "CONCLUSION_LEVELS",
    "LEVEL_INSUFFICIENT",
    "LEVEL_NOT_TESTED",
    "LEVEL_SUPPORTED",
    "LEVEL_TENTATIVE",
    "SOURCE_HISTORICAL",
    "SOURCE_LIVE",
    "SOURCE_SIMULATED",
    "Conclusion",
    "anchor_decision",
    "anchor_experiment",
    "anchor_run",
    "build_report_v13",
    "report_payload",
    "write_report",
]
