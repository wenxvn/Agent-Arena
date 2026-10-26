"""实验导出与可读报告。

所有数字都来自真实落盘记录（或明确标注的演示/模拟数据）：

- ``experiment.json``：冻结的规格与矩阵；
- ``summary.json`` / ``comparison.json``：汇总与配对口径；
- ``runs.csv`` / ``metrics.csv`` / ``paired_comparison.csv``：机器可读明细；
- ``report.md``：可读报告（含不可比声明、局限与复现方式）。

CSV 使用 UTF-8 BOM，便于本地表格软件直接打开。
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from agent_arena.lab.compare import CATEGORY_LABELS
from agent_arena.lab.contracts import Finding
from agent_arena.lab.paths import LAB_DOCS
from agent_arena.lab.visualization import FOCUS_MAPS

RUNS_CSV = "runs.csv"
METRICS_CSV = "metrics.csv"
PAIRED_CSV = "paired_comparison.csv"
FINDINGS_CSV = "findings.csv"

RUN_FIELDS = (
    "matrix_index",
    "run_id",
    "map_id",
    "environment_seed",
    "agent_id",
    "agent_version",
    "agent_config_hash",
    "state",
    "category",
    "category_label",
    "outcome",
    "termination",
    "success",
    "decisions",
    "requests",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "cost_cny",
    "cost_known",
    "rejected_actions",
    "invalid_actions",
    "agent_events",
    "primary_metric",
    "primary_state",
    "primary_value",
    "rule_hash",
    "metric_hash",
    "metric_schema_hash",
    "mode",
    "provider_id",
    "model",
)

METRIC_FIELDS = (
    "run_id",
    "matrix_index",
    "map_id",
    "environment_seed",
    "agent_id",
    "metric_id",
    "namespace",
    "state",
    "value",
    "numerator",
    "denominator",
    "note",
)

PAIRED_FIELDS = (
    "map_id",
    "environment_seed",
    "left_agent",
    "right_agent",
    "left_run_id",
    "right_run_id",
    "verdict",
    "reasons",
    "left_category",
    "right_category",
    "left_success",
    "right_success",
    "left_decisions",
    "right_decisions",
    "left_requests",
    "right_requests",
    "left_cost_cny",
    "right_cost_cny",
)

FINDING_FIELDS = (
    "run_id",
    "map_id",
    "agent_id",
    "category",
    "severity",
    "evidence_steps",
    "summary",
    "suggested_check",
)


def csv_bytes(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in fields})
    return buffer.getvalue().encode("utf-8-sig")


def runs_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                **{key: record.get(key) for key in RUN_FIELDS},
                "category_label": CATEGORY_LABELS.get(
                    str(record.get("category")), str(record.get("category"))
                ),
            }
        )
    return rows


def metrics_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        metrics = record.get("metrics") or {}
        for metric_id, payload in sorted(metrics.items()):
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "run_id": record.get("run_id"),
                    "matrix_index": record.get("matrix_index"),
                    "map_id": record.get("map_id"),
                    "environment_seed": record.get("environment_seed"),
                    "agent_id": record.get("agent_id"),
                    "metric_id": metric_id,
                    "namespace": "v10",
                    "state": payload.get("state"),
                    "value": payload.get("value"),
                    "numerator": payload.get("numerator"),
                    "denominator": payload.get("denominator"),
                    "note": payload.get("note"),
                }
            )
        # V12 研究投影单独成行，namespace 明确区分，便于下游只取 v10 或只取 v12。
        for metric_id, payload in sorted((record.get("metrics_v12") or {}).items()):
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "run_id": record.get("run_id"),
                    "matrix_index": record.get("matrix_index"),
                    "map_id": record.get("map_id"),
                    "environment_seed": record.get("environment_seed"),
                    "agent_id": record.get("agent_id"),
                    "metric_id": metric_id,
                    "namespace": "v12.projection",
                    "state": payload.get("state"),
                    "value": payload.get("value"),
                    "numerator": payload.get("numerator"),
                    "denominator": payload.get("denominator"),
                    "note": payload.get("note"),
                }
            )
    return rows


def paired_rows(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in comparison.get("pairs") or []:
        row = dict(pair)
        row["reasons"] = "；".join(pair.get("reasons") or [])
        rows.append(row)
    return rows


def findings_rows(findings: list[Finding], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run = {str(record["run_id"]): record for record in records}
    rows: list[dict[str, Any]] = []
    for finding in findings:
        record = by_run.get(finding.run_id) or {}
        rows.append(
            {
                "run_id": finding.run_id,
                "map_id": finding.map_id,
                "agent_id": record.get("agent_id"),
                "category": finding.category,
                "severity": finding.severity,
                "evidence_steps": ",".join(str(item) for item in finding.evidence_steps),
                "summary": finding.summary,
                "suggested_check": finding.suggested_check,
            }
        )
    return rows


# ----------------------------------------------------------------------- report
def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _arm_table(comparison: dict[str, Any]) -> list[str]:
    lines = [
        "| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 "
        "| 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in comparison.get("arms") or []:
        lines.append(
            "| {agent} | {version} | {runs} | {valid} | {successes} | {rate} | {decisions} | "
            "{requests} | {cost} | {cost_known} | {rejected} | {invalid} |".format(
                agent=arm.get("agent_id"),
                version=arm.get("agent_version") or "—",
                runs=arm.get("runs"),
                valid=arm.get("valid_denominator"),
                successes=arm.get("successes"),
                rate=_fmt(arm.get("success_rate")),
                decisions=_fmt(arm.get("mean_decisions")),
                requests=_fmt(arm.get("mean_requests")),
                cost=_fmt(arm.get("mean_cost_cny")),
                cost_known=arm.get("cost_known_runs"),
                rejected=arm.get("rejected_actions"),
                invalid=arm.get("invalid_actions"),
            )
        )
    return lines


def _category_table(summary: dict[str, Any]) -> list[str]:
    lines = ["| 类别 | 局数 |", "|---|---:|"]
    for category, count in (summary.get("categories") or {}).items():
        lines.append(f"| {CATEGORY_LABELS.get(category, category)}（`{category}`） | {count} |")
    if not summary.get("categories"):
        lines.append("| 尚未执行 | 0 |")
    return lines


def _metric_table(comparison: dict[str, Any], map_id: str) -> list[str]:
    lines = [
        "| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |",
        "|---|---|---|---|---|---|",
    ]
    for row in comparison.get("per_map") or []:
        if row.get("map_id") != map_id:
            continue
        for arm in row.get("arms") or []:
            metrics = arm.get("metrics") or {}
            for metric_id, payload in sorted(metrics.items()):
                states = ", ".join(
                    f"{key}×{value}" for key, value in (payload.get("states") or {}).items()
                )
                lines.append(
                    f"| {arm.get('agent_id')} | `{metric_id}` | {payload.get('role')} | "
                    f"{states or '—'} | {_fmt(payload.get('mean'))} | "
                    f"{_fmt(payload.get('pooled_ratio'))} |"
                )
    if len(lines) == 2:
        lines.append("| — | 该图没有可聚合指标 | — | — | — | — |")
    return lines


def _projection_table(comparison: dict[str, Any]) -> list[str]:
    """V12 研究投影指标（与 V10 指标分列，明确标注不是官方值）。"""

    rows: list[tuple[str, str, dict[str, Any]]] = []
    for row in comparison.get("per_map") or []:
        projection = row.get("projection") or {}
        for metric_id, payload in sorted(projection.items()):
            rows.append((str(row.get("map_id")), metric_id, payload))
    if not rows:
        return []
    lines = [
        "### V12 研究投影（不覆盖 V10 指标）",
        "",
        "| 地图 | 指标 | 五态分布 | 有效均值 | 合并比值 | 口径版本 |",
        "|---|---|---|---|---|---|",
    ]
    for map_id, metric_id, payload in rows:
        states = ", ".join(
            f"{key}×{value}" for key, value in (payload.get("states") or {}).items()
        )
        lines.append(
            f"| {map_id} | `{metric_id}` | {states or '—'} | "
            f"{_fmt(payload.get('mean'))} | {_fmt(payload.get('pooled_ratio'))} | "
            f"{payload.get('rule_version') or '—'} |"
        )
    lines += [
        "",
        "> 这些是 V12 为弥补公开信息缺口而新增的**研究投影**（键名宽容），",
        "> 用于回答「记忆是否被用于返程」；它们不参与任何 V10 指标均值，也不写入 V10 账本。",
        "",
    ]
    return lines


def build_report(
    *,
    experiment: dict[str, Any],
    summary: dict[str, Any],
    comparison: dict[str, Any],
    records: list[dict[str, Any]],
    findings: list[Finding] | None = None,
) -> str:
    """生成可读 Markdown 报告；所有数据来自 summary/comparison/records。"""

    findings = list(findings or [])
    mode = str(experiment.get("mode") or summary.get("mode") or "")
    mode_note = (
        "**SIMULATED（离线模拟，不是模型）**：结论只说明调用链、预算与诊断链路可用，"
        "不代表任何真实模型能力。"
        if mode == "simulated"
        else "**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。"
    )
    lines: list[str] = [
        f"# 实验报告：{experiment.get('name') or summary.get('name')}",
        "",
        f"- `experiment_id`：`{summary.get('experiment_id')}`",
        f"- 状态：`{summary.get('state')}`",
        f"- 执行通道：{mode_note}",
        f"- 模型 / Provider：`{summary.get('model')}` / `{summary.get('provider_id')}`",
        f"- 地图：{', '.join(summary.get('maps') or [])}",
        f"- 环境 seed：{summary.get('seeds')}",
        f"- 实验臂：{', '.join(arm.get('agent_id', '') for arm in summary.get('arms') or [])}",
        f"- 运行时版本：`{summary.get('runtime_version') or 'unknown'}`",
        f"- 子局：{summary.get('executed')} / {summary.get('total_cells')}"
        f"（未执行 {summary.get('pending')}）",
        "",
        "## 1. 问题与实验矩阵",
        "",
        "研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，"
        "行为、成功率、成本与失败原因有哪些可验证差异？**",
        "",
        f"- 矩阵 = {len(summary.get('maps') or [])} 图 × {len(summary.get('seeds') or [])} seed × "
        f"{len(summary.get('arms') or [])} 实验臂 = {summary.get('total_cells')} 局。",
        "- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。",
    ]
    supplement_of = summary.get("supplement_of")
    if supplement_of:
        lines += [
            "",
            f"> **补充实验**：来源 `{supplement_of}`；"
            f"只重跑 {summary.get('total_cells')} 个需要补充的条件。",
            f"> 原因：{summary.get('supplement_reason') or '—'}",
            "> 原始实验的记录与账本未被修改；补跑产生新的 run_id，不覆盖历史。",
        ]
    lines += [
        "",
        "## 2. 不可比声明与数据口径",
        "",
        f"- 配对比较判定：`{comparison.get('verdict')}`",
    ]
    for reason in comparison.get("reasons") or []:
        lines.append(f"  - 不可比原因：{reason}")
    for note in comparison.get("notes") or []:
        lines.append(f"  - 说明：{note}")
    lines += [
        "- 有效分母只含：完成且成功、机制失败、预算截尾；Provider 错误、取消、中断、"
        "策略异常**不计入**能力分母。",
        "- 指标五态（VALID/CENSORED/NOT_APPLICABLE/INVALID_TRACE/UNAVAILABLE）原样保留，"
        "缺失不补 0、不跨版本求均值。",
        "- 每对实验臂的配对键是 `(map_id, environment_seed)`；seed 不同不构成配对。",
        "",
        "## 3. 单局类别分布",
        "",
        *_category_table(summary),
        "",
        "## 4. 实验臂汇总",
        "",
        *_arm_table(comparison),
        "",
        "## 5. 逐图指标（五态）",
        "",
    ]
    for map_id in summary.get("maps") or []:
        lines += [f"### {map_id}", "", *_metric_table(comparison, map_id), ""]
    lines += _projection_table(comparison)
    lines += ["", "### 指标命名空间", ""]
    lines += [
        "- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。",
        "- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、",
        "  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。",
        "",
    ]

    lines += ["## 6. 代表性轨迹与证据", ""]
    if findings:
        critical = [item for item in findings if item.severity == "critical"]
        warnings = [item for item in findings if item.severity == "warning"]
        lines.append(
            f"- 共 {len(findings)} 条诊断"
            f"（critical {len(critical)} / warning {len(warnings)}）。"
        )
        for item in (critical + warnings)[:8]:
            evidence = ", ".join(item.evidence_event_ids) or "无单步证据"
            lines.append(
                f"- `{item.map_id}` / `{item.run_id}` · `{item.category}`：{item.summary}"
                f"（证据：{evidence}；建议核查：{item.suggested_check or '—'}）"
            )
    else:
        lines.append("- 本实验没有产生诊断结论（可能尚未执行或全部无异常）。")
    lines += [
        "",
        "## 7. 六图可视化可用性",
        "",
        "| 地图 | 专属视图 |",
        "|---|---|",
    ]
    from agent_arena.lab.visualization import KIND_BY_MAP

    for map_id in FOCUS_MAPS:
        included = map_id in (summary.get("maps") or [])
        label = f"可用（{KIND_BY_MAP[map_id]}）" if included else "本次未纳入"
        lines.append(f"| {map_id} | {label} |")
    lines += [
        "",
        "## 8. 局限",
        "",
        "- 每个配对键通常只有 1 局；这是描述性对照，**不作显著性断言**。",
        "- 架构新增的记忆/计划/反思上下文是唯一被操纵的变量；提示词基线与动作契约保持不变。",
        "- Planner/Reflection 的额外请求已计入请求数、token 与费用；费用未知的局不参与成本对比。",
        "- SIMULATED 模式下策略行为由确定性脚本 Provider 驱动，"
        "**不能**用来声称任何架构能力差异。"
        if mode == "simulated"
        else "- 真实模型输出不可完全复现；只保证环境 seed 配对。",
        "",
        "## 9. 复现方式",
        "",
        "```bash",
        "# 零 API：跑同一矩阵的离线模拟",
        "uv run python scripts/demo_v12.py",
        "# 一键验收（含 Lab 契约、预算、父子状态、导出复算）",
        "uv run python scripts/verify_v12.py",
        "```",
        "",
        f"实验目录：`runs/lab/{summary.get('experiment_id')}/`；"
        "子局仍在 `runs/web/<run_id>/`（V11 结构）。",
        "",
    ]
    return "\n".join(lines)


def write_exports(
    *,
    experiment_dir: Path,
    experiment: dict[str, Any],
    summary: dict[str, Any],
    comparison: dict[str, Any],
    records: list[dict[str, Any]],
    findings: list[Finding] | None = None,
) -> dict[str, Path]:
    """写出机器可读导出与可读报告；返回文件名 → 路径。"""

    exports = experiment_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def _write(name: str, blob: bytes) -> None:
        path = exports / name
        path.write_bytes(blob)
        written[name] = path

    _write(RUNS_CSV, csv_bytes(runs_rows(records), RUN_FIELDS))
    _write(METRICS_CSV, csv_bytes(metrics_rows(records), METRIC_FIELDS))
    _write(PAIRED_CSV, csv_bytes(paired_rows(comparison), PAIRED_FIELDS))
    if findings:
        _write(FINDINGS_CSV, csv_bytes(findings_rows(findings, records), FINDING_FIELDS))

    report = build_report(
        experiment=experiment,
        summary=summary,
        comparison=comparison,
        records=records,
        findings=findings,
    )
    report_path = experiment_dir / "report.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    written["report.md"] = report_path

    for name, payload in (
        ("summary.json", summary),
        ("comparison.json", comparison),
        ("experiment.json", experiment),
    ):
        path = exports / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written[name] = path
    return written


def docs_dir() -> Path:
    return LAB_DOCS


__all__ = [
    "FINDINGS_CSV",
    "FINDING_FIELDS",
    "METRICS_CSV",
    "METRIC_FIELDS",
    "PAIRED_CSV",
    "PAIRED_FIELDS",
    "RUNS_CSV",
    "RUN_FIELDS",
    "build_report",
    "csv_bytes",
    "docs_dir",
    "findings_rows",
    "metrics_rows",
    "paired_rows",
    "runs_rows",
    "write_exports",
]
