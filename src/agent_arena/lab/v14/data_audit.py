"""V14 只读数据审计层（P0-2 / P0-3）。

三件事，全部只读、可复算、零外部请求：

1. **未知 vs 零**：机制触发、成功、截尾的分子分母必须分开"未观测"与"观测为假"，
   全未知一律输出 ``UNKNOWN (0 observed)``。
2. **版本/协议隔离**：历史 CSV 缺少 ``contract_version`` / ``prompt_hash``，
   跨契约（MAP-22 contract-1 → contract-2）、跨预算、跨实验类型的数据**不得**
   静默求均值。本模块按"实验登记文件 + 实验类型 + 规则/指标指纹"分组，
   多组并存时显式标 ``POOLED_ACROSS_PROTOCOLS``。
3. **文档算术自检**：``docs/v13/live-budget-proposal.md`` 的逐行数字与它自己声明的
   合计/方案不一致（V14 发现）。本模块从 Markdown 解析逐行数字并重算，
   用真实 V12 单价按文档声明的 1.5 倍余量公式复核。

所有函数只接受内存中的 record 列表，不写文件、不访问网络、不修改历史数据。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.history import load_v12_history
from agent_arena.lab.v13.validity import (
    FOCUS_MAPS,
    VALID_CATEGORIES,
    mechanism_triggered_summary,
    six_map_audit,
)

#: 文档声明的预估余量（``live-budget-proposal.md`` 第 2 节）。
ESTIMATE_MARGIN = 1.5

PROTOCOL_POOLED = "POOLED_ACROSS_PROTOCOLS"
PROTOCOL_SINGLE = "SINGLE_PROTOCOL"
PROTOCOL_UNKNOWN = "UNKNOWN_PROTOCOL"

#: V13 已发布的六图结论（``docs/v13/map-validity.md``，2026-10-26 生成）。
#: 只作为"被审计对象"保留；V14 不修改它，只生成差异表。
V13_RECORDED_VALIDITY: dict[str, dict[str, Any]] = {
    "MAP-08": {"label": "CEILING", "valid_denominator": 9, "successes": 9, "censored": 0,
               "trigger_display": "0/9"},
    "MAP-16": {"label": "SUITABLE", "valid_denominator": 35, "successes": 9, "censored": 1,
               "trigger_display": "0/35"},
    "MAP-18": {"label": "SUITABLE", "valid_denominator": 37, "successes": 8, "censored": 0,
               "trigger_display": "0/37"},
    "MAP-22": {"label": "SUITABLE", "valid_denominator": 20, "successes": 3, "censored": 2,
               "trigger_display": "0/21"},
    "MAP-26": {"label": "CEILING", "valid_denominator": 9, "successes": 9, "censored": 0,
               "trigger_display": "0/9"},
    "MAP-30": {"label": "CENSORED", "valid_denominator": 27, "successes": 0, "censored": 20,
               "trigger_display": "0/27"},
}

# --------------------------------------------------------------- 协议隔离
def protocol_group(record: dict[str, Any]) -> dict[str, Any]:
    """一条历史记录的协议分组（不是"契约版本"——CSV 没有那个字段）。

    分组键：
    - ``experiment_kind``：``matrix`` / ``replicate`` / ``ablation`` / ``version_rerun`` / …
    - ``source_file``：实验登记文件，是跨契约/跨预算隔离的唯一可靠线索；
    - ``fingerprint``：``rule_hash + metric_hash + metric_schema_hash + agent_version
      + prompt_hash + contract_version`` 的短哈希（缺失项写 ``UNKNOWN``）。

    **局限（DCR-V14-01）**：V12 的逐局 CSV 没有 ``prompt_hash`` / ``contract_version``，
    因此 MAP-22 的 contract-1 与 contract-2 只能靠"是否来自 ``map22-contract2-runs.csv``"
    区分，无法在数据层证明两者契约一致。V14 之后的新 trace 必须落这两个字段。
    """

    from agent_arena.lab.contracts import config_hash

    payload = {
        "rule_hash": record.get("rule_hash") or "UNKNOWN",
        "metric_hash": record.get("metric_hash") or "UNKNOWN",
        "metric_schema_hash": record.get("metric_schema_hash") or "UNKNOWN",
        "agent_version": record.get("agent_version") or "UNKNOWN",
        "prompt_hash": record.get("prompt_hash") or "UNKNOWN",
        "contract_version": record.get("agent_contract_version")
        or record.get("action_contract_version")
        or "UNKNOWN",
    }
    return {
        "kind": str(record.get("experiment_kind") or "ad_hoc"),
        "file": str(record.get("source_file") or "unknown"),
        "experiment_id": str(record.get("experiment_id") or ""),
        "fingerprint": config_hash(payload)[:12],
        "contract_version": payload["contract_version"],
        "prompt_hash_recorded": payload["prompt_hash"] != "UNKNOWN",
    }

def version_isolation(
    records: list[dict[str, Any]], map_id: str
) -> dict[str, Any]:
    """一张图按协议分组的逐组计数，多组并存时禁止合并求均值。"""

    selected = [item for item in records if str(item.get("map_id")) == map_id]
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in selected:
        group = protocol_group(record)
        key = (group["kind"], group["file"], group["fingerprint"])
        bucket = groups.setdefault(
            key,
            {
                "kind": group["kind"],
                "file": group["file"],
                "fingerprint": group["fingerprint"],
                "contract_version": group["contract_version"],
                "prompt_hash_recorded": group["prompt_hash_recorded"],
                "runs": 0,
                "valid": 0,
                "successes": 0,
                "censored": 0,
                "mechanism_failures": 0,
                "invalid": 0,
                "cost_cny": 0.0,
            },
        )
        bucket["runs"] += 1
        category = str(record.get("category") or "")
        if category in VALID_CATEGORIES:
            bucket["valid"] += 1
        if category == "completed_success":
            bucket["successes"] += 1
        elif category == "budget_censored":
            bucket["censored"] += 1
        elif category == "mechanism_failure":
            bucket["mechanism_failures"] += 1
        else:
            bucket["invalid"] += 1
        if record.get("cost_known") and record.get("cost_cny") is not None:
            bucket["cost_cny"] += float(record["cost_cny"])
    rows = []
    for bucket in sorted(groups.values(), key=lambda item: (item["kind"], item["file"])):
        bucket["cost_cny"] = round(bucket["cost_cny"], 8)
        bucket["success_rate"] = (
            round(bucket["successes"] / bucket["valid"], 4) if bucket["valid"] else None
        )
        rows.append(bucket)
    pooled = len(rows) > 1
    return {
        "map_id": map_id,
        "protocol_groups": len(rows),
        "status": PROTOCOL_POOLED if pooled else PROTOCOL_SINGLE,
        "runs": len(selected),
        "groups": rows,
        "pooling_allowed": not pooled,
        "note": (
            "存在多个协议分组：任何成功率/均值都不得跨组合并；"
            "只能逐组报告或按组排除（P0-2 / P0-3）。"
            if pooled
            else "只有一个协议分组，可在组内聚合。"
        ),
    }

def six_map_protocol_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    """六图逐图协议隔离 + 未知机制触发比例。"""

    maps = []
    for map_id in FOCUS_MAPS:
        isolation = version_isolation(records, map_id)
        selected = [item for item in records if str(item.get("map_id")) == map_id]
        trigger = mechanism_triggered_summary(selected)
        maps.append({**isolation, "trigger": trigger})
    pooled_maps = [item["map_id"] for item in maps if not item["pooling_allowed"]]
    unknown_maps = [
        item["map_id"] for item in maps if not item["trigger"]["available"]
    ]
    return {
        "schema": "v14-data-validity-1",
        "maps": maps,
        "pooled_maps": pooled_maps,
        "trigger_unknown_maps": unknown_maps,
        "note": (
            "``POOLED_ACROSS_PROTOCOLS`` 的图不允许给出单一成功率；"
            "机制触发全未知的图必须显示 UNKNOWN，不能显示 0/n。"
        ),
    }

# ------------------------------------------------------- V13 标签差异复算
def validity_diff(records: list[dict[str, Any]]) -> dict[str, Any]:
    """重算六图标签，并与 V13 已发布表格逐项比对。"""

    audit = six_map_audit(records)
    recomputed = {row["map_id"]: row for row in audit["maps"]}
    rows = []
    for map_id in FOCUS_MAPS:
        recorded = V13_RECORDED_VALIDITY.get(map_id, {})
        row = recomputed.get(map_id, {})
        changes: list[str] = []
        if recorded.get("label") and recorded["label"] != row.get("composite"):
            changes.append(f"标签 {recorded['label']} → {row.get('composite')}")
        if recorded.get("valid_denominator") != row.get("valid_denominator"):
            changes.append(
                f"有效分母 {recorded.get('valid_denominator')} → {row.get('valid_denominator')}"
            )
        if recorded.get("successes") != row.get("successes"):
            changes.append(f"成功 {recorded.get('successes')} → {row.get('successes')}")
        if recorded.get("censored") != row.get("budget_censored"):
            changes.append(
                f"截尾 {recorded.get('censored')} → {row.get('budget_censored')}"
            )
        if recorded.get("trigger_display") != row.get("mechanism_triggered_display"):
            changes.append(
                f"机制触发 {recorded.get('trigger_display')} → "
                f"{row.get('mechanism_triggered_display')}"
            )
        rows.append(
            {
                "map_id": map_id,
                "v13_label": recorded.get("label"),
                "v14_label": row.get("composite"),
                "v13_valid_denominator": recorded.get("valid_denominator"),
                "v14_valid_denominator": row.get("valid_denominator"),
                "v13_trigger": recorded.get("trigger_display"),
                "v14_trigger": row.get("mechanism_triggered_display"),
                "v14_trigger_status": row.get("mechanism_triggered_status"),
                "changes": changes,
                "changed": bool(changes),
            }
        )
    return {
        "schema": "v14-validity-diff-1",
        "rows": rows,
        "changed_maps": [row["map_id"] for row in rows if row["changed"]],
        "note": (
            "差异只来自**展示口径**修正（未知不再算 0）与有效分母重算；"
            "原始历史数据未被修改。"
        ),
    }

def validity_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# V13 → V14 六图口径差异表",
        "",
        "> 被审计对象：`docs/v13/map-validity.md`（2026-10-26 生成）。"
        "本表由 `scripts/audit_v14_data.py --write` 从只读历史 CSV 复算得到。",
        "",
        "| 地图 | V13 标签 | V14 标签 | V13 有效分母 | V14 有效分母 "
        "| V13 机制触发 | V14 机制触发 | 变化 |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for row in diff.get("rows") or []:
        lines.append(
            f"| {row['map_id']} | `{row['v13_label']}` | `{row['v14_label']}` | "
            f"{row['v13_valid_denominator']} | {row['v14_valid_denominator']} | "
            f"{row['v13_trigger']} | {row['v14_trigger']} | "
            f"{'；'.join(row['changes']) if row['changes'] else '无'} |"
        )
    lines += ["", f"> {diff.get('note')}", ""]
    return "\n".join(lines)

# ------------------------------------------------- 预算申请文档算术自检
_ROW_RE = re.compile(
    r"^\|\s*(E\d[-\w]*)\s*\|(?P<body>.+)\|\s*$"
)

def parse_budget_rows(text: str) -> list[dict[str, Any]]:
    """解析 ``live-budget-proposal.md`` 第 2 节的逐行预算表。"""

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = _ROW_RE.match(line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group("body").split("|")]
        # 期望 6 列：内容 / 地图·seed / 条件×重复 / 子局 / 单局硬上限 / 上界 / 预估
        if len(cells) != 7:
            continue
        try:
            runs = int(cells[3])
            upper = float(cells[5])
            estimate = float(cells[6])
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "group": match.group(1),
                "content": cells[0],
                "maps": cells[1],
                "design": cells[2],
                "runs": runs,
                "per_run_cap": cells[4],
                "upper_cny": upper,
                "estimate_cny": estimate,
            }
        )
    return rows

def map_unit_costs(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """从 V12 真实逐局记录算每图平均费用/请求/输入 token（只读）。"""

    buckets: dict[str, dict[str, float]] = {}
    for record in records:
        if not (record.get("cost_known") and record.get("cost_cny") is not None):
            continue
        map_id = str(record.get("map_id") or "")
        bucket = buckets.setdefault(
            map_id, {"runs": 0.0, "cost": 0.0, "requests": 0.0, "tokens": 0.0}
        )
        bucket["runs"] += 1
        bucket["cost"] += float(record["cost_cny"])
        bucket["requests"] += float(record.get("requests") or 0)
        bucket["tokens"] += float(record.get("input_tokens") or 0)
    output: dict[str, dict[str, float]] = {}
    for map_id, bucket in buckets.items():
        runs = bucket["runs"] or 1.0
        output[map_id] = {
            "runs": int(bucket["runs"]),
            "cost_cny": round(bucket["cost"] / runs, 8),
            "requests": round(bucket["requests"] / runs, 4),
            "input_tokens": round(bucket["tokens"] / runs, 2),
        }
    return output

def _row_maps(label: str) -> list[str]:
    found = re.findall(r"MAP-\d\d", label)
    return found

def budget_proposal_check(
    text: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    """重算预算申请：逐行合计、方案 A/B/C 与"预估"公式一致性。"""

    rows = parse_budget_rows(text)
    costs = map_unit_costs(records)
    for row in rows:
        maps = _row_maps(row["maps"])
        if not maps:
            row["recomputed_estimate"] = None
            continue
        values = [
            costs[map_id]["cost_cny"] for map_id in maps if map_id in costs
        ]
        unit = sum(values) / len(values) if values else None
        row["unit_cost_cny"] = None if unit is None else round(unit, 8)
        row["recomputed_estimate"] = (
            None
            if unit is None
            else round(row["runs"] * unit * ESTIMATE_MARGIN, 2)
        )
        row["estimate_matches_formula"] = (
            None
            if row["recomputed_estimate"] is None
            else abs(row["recomputed_estimate"] - row["estimate_cny"]) <= 0.011
        )
    totals = {
        "runs": sum(row["runs"] for row in rows),
        "upper_cny": round(sum(row["upper_cny"] for row in rows), 2),
        "estimate_cny": round(sum(row["estimate_cny"] for row in rows), 2),
        "recomputed_estimate_cny": round(
            sum(
                row["recomputed_estimate"]
                for row in rows
                if row.get("recomputed_estimate") is not None
            ),
            2,
        ),
    }
    declared = re.search(r"\*\*合计\*\*：\*\*(\d+)\s*局\*\*", text)
    declared_runs = int(declared.group(1)) if declared else None
    groups = {row["group"] for row in rows}
    def subset(prefixes: tuple[str, ...]) -> dict[str, Any]:
        chosen = [row for row in rows if row["group"].startswith(prefixes)]
        return {
            "groups": [row["group"] for row in chosen],
            "runs": sum(row["runs"] for row in chosen),
            "upper_cny": round(sum(row["upper_cny"] for row in chosen), 2),
            "estimate_cny": round(sum(row["estimate_cny"] for row in chosen), 2),
            "recomputed_estimate_cny": round(
                sum(
                    row["recomputed_estimate"]
                    for row in chosen
                    if row.get("recomputed_estimate") is not None
                ),
                2,
            ),
        }
    plans = {
        "A": subset(("E1-a", "E2-a", "E3-a")),
        "B": subset(("E0", "E1", "E2", "E3")),
        "C": subset(tuple(groups)),
    }
    return {
        "schema": "v14-budget-audit-1",
        "rows": rows,
        "row_count": len(rows),
        "totals": totals,
        "declared_total_runs": declared_runs,
        "declared_total_matches": declared_runs == totals["runs"],
        "plans": plans,
        "unit_costs": costs,
        "margin": ESTIMATE_MARGIN,
        "note": (
            "``recomputed_estimate_cny`` 按文档自己声明的"
            f" {ESTIMATE_MARGIN} 倍余量公式（子局数 × V12 实测均价 × 余量）重算；"
            "与 ``estimate_cny`` 不一致的行说明原表未统一使用该公式。"
        ),
    }

def budget_proposal_markdown(check: dict[str, Any]) -> str:
    lines = [
        "# V14 预算申请算术复核（`docs/v13/live-budget-proposal.md`）",
        "",
        "> 只读复核，不构成执行授权。**V14 未获新批准，外部付费请求 0。**",
        "",
        "## 1. 逐行复核",
        "",
        "| 组 | 子局 | 上界 CNY | 原预估 | 按 1.5 倍公式重算 | 一致 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in check.get("rows") or []:
        lines.append(
            f"| {row['group']} | {row['runs']} | {row['upper_cny']:.2f} | "
            f"{row['estimate_cny']:.2f} | "
            f"{row['recomputed_estimate'] if row['recomputed_estimate'] is not None else '—'} | "
            f"{'是' if row.get('estimate_matches_formula') else '**否**'} |"
        )
    totals = check.get("totals") or {}
    lines += [
        "",
        "## 2. 合计",
        "",
        f"- 逐行子局合计：**{totals.get('runs')}** 局"
        f"（文件声明：{check.get('declared_total_runs')} 局，"
        f"{'一致' if check.get('declared_total_matches') else '**不一致**'}）",
        f"- 逐行上界合计：**¥{totals.get('upper_cny')}**",
        f"- 逐行原预估合计：**¥{totals.get('estimate_cny')}**",
        f"- 按 1.5 倍公式重算合计：**¥{totals.get('recomputed_estimate_cny')}**",
        "",
        "## 3. 方案重算",
        "",
        "| 方案 | 包含组 | 子局 | 上界 CNY | 原预估 | 重算预估 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, plan in (check.get("plans") or {}).items():
        lines.append(
            f"| {name} | {', '.join(plan['groups'])} | {plan['runs']} | "
            f"{plan['upper_cny']:.2f} | {plan['estimate_cny']:.2f} | "
            f"{plan['recomputed_estimate_cny']:.2f} |"
        )
    lines += ["", f"> {check.get('note')}", ""]
    return "\n".join(lines)

# -------------------------------------------------------------- 顶层装配
def data_validity_report(
    records: list[dict[str, Any]] | None = None,
    *,
    proposal_path: Path | None = None,
) -> dict[str, Any]:
    """一次性产出 V14 数据口径审计的三个部分。"""

    selected = load_v12_history() if records is None else records
    path = proposal_path or (REPO_ROOT / "docs" / "v13" / "live-budget-proposal.md")
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {
        "schema": "v14-data-validity-1",
        "records": len(selected),
        "protocol": six_map_protocol_audit(selected),
        "validity_diff": validity_diff(selected),
        "budget": budget_proposal_check(text, selected) if text else None,
    }

def data_validity_markdown(report: dict[str, Any]) -> str:
    protocol = report.get("protocol") or {}
    lines = [
        "# V14 数据口径与构念效度修正",
        "",
        "- 来源：`docs/v12/real-runs/*.csv`（只读，未修改）",
        f"- 历史局数：{report.get('records')}",
        "- 真实付费请求：**0**",
        "",
        "## 1. `UNKNOWN` 与 `0` 分开（P0-2）",
        "",
        "V13 的 `validity_markdown()` 用 `mechanism_triggered_runs / runs` 渲染机制触发列。",
        "历史 CSV 根本没有 `mechanism_triggered` 列，于是**缺失**被打印成 `0/N`，",
        "等价于把\"没测过\"写成\"测过且为假\"。V14 改为三档计数：",
        "`observed_true` / `observed_false` / `unknown`，只有观测子集才进分母。",
        "",
        "| 地图 | 协议分组 | 分组状态 | 局数 | 机制触发（V14 口径） | 状态 |",
        "|---|---:|---|---:|---|---|",
    ]
    for item in protocol.get("maps") or []:
        trigger = item.get("trigger") or {}
        lines.append(
            f"| {item['map_id']} | {item['protocol_groups']} | `{item['status']}` | "
            f"{item['runs']} | {trigger.get('observed_true')}/{trigger.get('observed')} "
            f"observed，{trigger.get('unknown')} unknown | `{trigger.get('status')}` |"
        )
    lines += [
        "",
        "## 2. 版本 / 协议隔离（P0-2 / P0-3）",
        "",
        f"- 多协议并存、禁止合并求均值的图：{', '.join(protocol.get('pooled_maps') or []) or '无'}",
        f"- 机制触发全未知的图：{', '.join(protocol.get('trigger_unknown_maps') or []) or '无'}",
        "",
        "### 2.1 MAP-22 的分组明细",
        "",
        "| 实验类型 | 文件 | 指纹 | 局数 | 有效 | 成功 | 截尾 | 成功率 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in protocol.get("maps") or []:
        if item["map_id"] != "MAP-22":
            continue
        for group in item["groups"]:
            lines.append(
                f"| {group['kind']} | `{group['file']}` | `{group['fingerprint']}` | "
                f"{group['runs']} | {group['valid']} | {group['successes']} | "
                f"{group['censored']} | "
                f"{group['success_rate'] if group['success_rate'] is not None else '—'} |"
            )
    lines += ["", f"> {protocol.get('note')}", ""]
    diff = report.get("validity_diff")
    if diff:
        lines += [
            "## 3. 六图标签差异（V13 → V14）",
            "",
            "| 地图 | V13 标签 | V14 标签 | V13 有效分母 | V14 有效分母 | 变化 |",
            "|---|---|---|---:|---:|---|",
        ]
        for row in diff["rows"]:
            lines.append(
                f"| {row['map_id']} | `{row['v13_label']}` | `{row['v14_label']}` | "
                f"{row['v13_valid_denominator']} | {row['v14_valid_denominator']} | "
                f"{'；'.join(row['changes']) if row['changes'] else '无'} |"
            )
        lines += ["", f"> {diff['note']}", ""]
    budget = report.get("budget")
    if budget:
        totals = budget["totals"]
        lines += [
            "## 4. LIVE 预算表算术复核",
            "",
            f"- 逐行子局合计：**{totals['runs']}**（文件声明 {budget['declared_total_runs']}，"
            f"{'一致' if budget['declared_total_matches'] else '**不一致**'}）",
            f"- 逐行原预估合计：¥{totals['estimate_cny']}",
            f"- 按 1.5 倍公式重算：¥{totals['recomputed_estimate_cny']}",
            "",
            "| 方案 | 子局 | 上界 CNY | 原预估 | 重算预估 |",
            "|---|---:|---:|---:|---:|",
        ]
        for name, plan in budget["plans"].items():
            lines.append(
                f"| {name} | {plan['runs']} | {plan['upper_cny']:.2f} | "
                f"{plan['estimate_cny']:.2f} | {plan['recomputed_estimate_cny']:.2f} |"
            )
        lines += ["", f"> {budget['note']}", ""]
    lines += [
        "## 5. 适用限制",
        "",
        "- `SUITABLE` 只表示**现有样本里出现了成功率梯度**，不构成构念效度充分或因果证据；",
        "- `CEILING` / `CENSORED` 只描述样本形态，不评价地图设计质量；",
        "- 历史 CSV 缺 `prompt_hash` / `contract_version`（DCR-V14-01），",
        "  跨契约隔离只能按实验登记文件进行，不能声称数据层已证明契约一致。",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "ESTIMATE_MARGIN",
    "PROTOCOL_POOLED",
    "PROTOCOL_SINGLE",
    "PROTOCOL_UNKNOWN",
    "V13_RECORDED_VALIDITY",
    "budget_proposal_check",
    "budget_proposal_markdown",
    "data_validity_markdown",
    "data_validity_report",
    "map_unit_costs",
    "parse_budget_rows",
    "protocol_group",
    "six_map_protocol_audit",
    "validity_diff",
    "validity_diff_markdown",
    "version_isolation",
]
