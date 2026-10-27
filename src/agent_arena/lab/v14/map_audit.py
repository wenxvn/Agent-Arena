"""V14 地图适用性审计（P1-1 / P1-2）。

三件事，全部只读：

1. **MAP-30 三维预算阶梯**：请求 / 输入 token / 金额分别看瓶颈，并给出
   "保守可达步数区间"（来自已观测分布，不是承诺）。
2. **六图标签复算**：沿用 V13 的构念标签，但把"未知"与"零"分开，
   并标注证据版本、样本数与独立 seed。
3. **候选图公开机制审计**：MAP-19 / MAP-20 / MAP-29 只读检查
   （seed 空间、公开字段、动作形状、规则文本、DCR、历史终态），
   **不改规则、不加 seed、不强行断言"这些图更好"**。

所有结论都必须带证据版本与样本数；不足就写 `NEEDS_MORE_EVIDENCE`。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.validity import (
    FOCUS_MAPS,
    budget_capacity,
    map30_ladder,
    mechanism_triggered_summary,
    six_map_audit,
)
from agent_arena.v10.runtime.catalog import (
    MAP_IDS,
    create_environment,
    is_v10,
    rule_hash,
    seed_space,
    v10_class,
)

#: 候选图（只审计，不参与能力排名）。
CANDIDATE_MAPS: tuple[str, ...] = ("MAP-19", "MAP-20", "MAP-29")

NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"

#: MAP-30 的候选预算档（需批准，不自动启用）。
MAP30_TIERS: tuple[dict[str, Any], ...] = (
    {"request_cap": 90, "input_token_cap": 200_000, "cost_cap_cny": 0.20},
    {"request_cap": 180, "input_token_cap": 200_000, "cost_cap_cny": 0.50},
    {"request_cap": 180, "input_token_cap": 600_000, "cost_cap_cny": 0.20},
)

def map30_three_axis(records: list[dict[str, Any]]) -> dict[str, Any]:
    """MAP-30 的三维阶梯：请求 / token / 金额。

    与 V13 的 ``map30_ladder`` 的差别：本函数额外给出
    **每档的瓶颈轴**（是请求先撞、还是 token 先撞、还是金额先撞），
    以及"按已观测分布能支撑多少决策"的保守区间。
    """

    ladder = map30_ladder(records)
    selected = [item for item in records if str(item.get("map_id")) == "MAP-30"]
    tiers = []
    for tier in ladder["tiers"]:
        request_cap = int(tier.get("request_cap") or 0)
        token_cap = int(tier.get("input_token_cap") or 0)
        in_tier = [
            item
            for item in selected
            if int(item.get("request_cap") or 0) == request_cap
            and int(item.get("input_token_cap") or 0) == token_cap
        ]
        capacity = budget_capacity(
            in_tier, input_token_cap=token_cap, request_cap=request_cap
        )
        censored = int(tier["censored"])
        runs = int(tier["runs"])
        # 瓶颈轴：截尾局里请求是否撞满 / token 是否撞满 / 金额是否撞满
        hit_requests = sum(
            1
            for item in in_tier
            if int(item.get("requests") or 0) >= request_cap > 0
            and str(item.get("category")) == "budget_censored"
        )
        hit_tokens = sum(
            1
            for item in in_tier
            if int(item.get("input_tokens") or 0) >= token_cap > 0
            and str(item.get("category")) == "budget_censored"
        )
        hit_cost = sum(
            1
            for item in in_tier
            if item.get("cost_known")
            and item.get("cost_cny") is not None
            and item.get("cost_cap_cny") is not None
            and float(item["cost_cny"]) >= float(item["cost_cap_cny"])
            and str(item.get("category")) == "budget_censored"
        )
        axis = "UNKNOWN"
        axis_evidence = "没有截尾局，不需要判断瓶颈轴。"
        if censored:
            best = max(hit_requests, hit_tokens, hit_cost)
            if best == 0:
                axis = "UNSPECIFIED"
                axis_evidence = (
                    f"{censored} 局截尾，但公开终态码没有暴露具体撞到哪一维"
                    "（请求/token/费用），不能强行归因。"
                )
            elif hit_requests == best:
                axis = "REQUESTS"
                axis_evidence = f"{hit_requests}/{censored} 局撞满请求上限。"
            elif hit_tokens == best:
                axis = "INPUT_TOKENS"
                axis_evidence = f"{hit_tokens}/{censored} 局撞满输入 token 上限。"
            else:
                axis = "COST_CNY"
                axis_evidence = f"{hit_cost}/{censored} 局撞满单局费用上限。"
        tiers.append(
            {
                "tier": tier["tier"],
                "request_cap": request_cap,
                "input_token_cap": token_cap,
                "runs": runs,
                "successes": int(tier["successes"]),
                "censored": censored,
                "mechanism_failures": int(tier["mechanism_failures"]),
                "accusation_rejected": int(tier["accusation_rejected"]),
                "censored_ratio": tier["censored_ratio"],
                "max_decisions": int(tier["max_decisions"]),
                "max_input_tokens": int(tier["max_input_tokens"]),
                "cost_cny": tier["cost_cny"],
                "bottleneck_axis": axis,
                "bottleneck_evidence": axis_evidence,
                "hit_requests": hit_requests,
                "hit_tokens": hit_tokens,
                "hit_cost": hit_cost,
                "capacity": capacity,
            }
        )
    return {
        "schema": "v14-map30-three-axis-1",
        "map_id": "MAP-30",
        "runs": len(selected),
        "tiers": tiers,
        "candidate_tiers": [dict(item) for item in MAP30_TIERS],
        "reading": (
            "预算阶梯的瓶颈轴必须分开看：请求先撞说明「步数不够」，"
            "token 先撞说明「上下文太长」，金额先撞说明「单价太高」。"
            "三者不能合并成一句「能力不足」。"
        ),
        "caution": (
            "候选档**需批准**，不得自动启用；新 MAP-30 高成本 LIVE 不默认纳入方案 A。"
        ),
    }

def map30_conservative_interval(axis: dict[str, Any]) -> dict[str, Any]:
    """从三维阶梯给出"保守可达决策数"区间（不承诺能跑通）。"""

    intervals = []
    for tier in axis["tiers"]:
        capacity = tier["capacity"]
        if not capacity.get("available"):
            intervals.append(
                {
                    "tier": tier["tier"],
                    "available": False,
                    "reason": capacity.get("reason"),
                }
            )
            continue
        low, high = capacity["estimated_supported_decisions"]
        intervals.append(
            {
                "tier": tier["tier"],
                "available": True,
                "supported_decisions": [int(low), int(high)],
                "observed_max_decisions": tier["max_decisions"],
                "tokens_per_decision": capacity["tokens_per_decision"],
                "bottleneck_axis": tier["bottleneck_axis"],
            }
        )
    return {
        "schema": "v14-map30-interval-1",
        "intervals": intervals,
        "note": (
            "区间来自**已观测** token/决策分布：下限按最贵观测、上限按最便宜观测。"
            "它不是对真实模型的承诺，也不含墙钟时间；预检页只能显示「估计范围」。"
        ),
    }

def six_map_recheck(records: list[dict[str, Any]]) -> dict[str, Any]:
    """六图标签复算，并附证据版本/样本数/独立 seed。"""

    audit = six_map_audit(records)
    rows = []
    for row in audit["maps"]:
        map_id = row["map_id"]
        selected = [item for item in records if str(item.get("map_id")) == map_id]
        seeds = sorted({int(item.get("environment_seed") or 0) for item in selected})
        files = sorted({str(item.get("source_file") or "") for item in selected})
        trigger = mechanism_triggered_summary(selected)
        rows.append(
            {
                "map_id": map_id,
                "labels": row["labels"],
                "composite": row["composite"],
                "runs": row["runs"],
                "valid_denominator": row["valid_denominator"],
                "successes": row["successes"],
                "success_rate": row["success_rate"],
                "censored": row["budget_censored"],
                "independent_seeds": seeds,
                "source_files": files,
                "trigger_status": trigger["status"],
                "trigger_display": row["mechanism_triggered_display"],
                "evidence_version": "V12 real-runs（只读）",
                "sample_note": (
                    f"{row['valid_denominator']} 有效局 / {len(seeds)} 个独立 seed / "
                    f"{len(files)} 个实验文件"
                ),
                "status": (
                    "DESCRIPTIVE_ONLY"
                    if len(seeds) < 3 or not trigger["available"]
                    else "REPORTABLE"
                ),
            }
        )
    return {
        "schema": "v14-six-map-recheck-1",
        "maps": rows,
        "ceiling_maps": audit["ceiling_maps"],
        "floor_or_censored_maps": audit["floor_or_censored_maps"],
        "suitable_maps": audit["suitable_maps"],
        "note": (
            "`SUITABLE` 只表示现有样本里出现成功率梯度；"
            "`CEILING`/`CENSORED` 只描述样本形态；机制触发全未知的图不能写 0/N。"
        ),
    }

V10_STATUS_CSV = (
    REPO_ROOT / "docs" / "v10" / "map-status-matrix.csv"
)

def _v10_status(map_id: str) -> dict[str, Any]:
    """从 V10 状态矩阵读该图的登记事实（只读；缺失返回空字典）。"""

    if not V10_STATUS_CSV.is_file():
        return {}
    import csv

    with V10_STATUS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("map_id") == map_id:
                return {
                    "validity_status": row.get("validity_status", ""),
                    "construct_status": row.get("construct_status", ""),
                    "dcr_id": row.get("dcr_id", ""),
                    "environment_seeds": row.get("environment_seeds", ""),
                    "oracle": row.get("oracle", ""),
                    "mimo": row.get("mimo", ""),
                    "decision": row.get("decision", ""),
                    "source": "docs/v10/map-status-matrix.csv（只读）",
                }
    return {}

def _public_rules(map_id: str, space: tuple[int, ...]) -> tuple[str, ...]:
    """只读读取公开规则文本（构造 seed 空间内的第一个环境实例）。"""

    try:
        environment = create_environment(map_id, environment_seed=space[0])
        rules = getattr(environment, "public_rules", None)
        return tuple(rules()) if callable(rules) else ()
    except Exception:  # pragma: no cover - 规则读取失败不阻断审计
        return ()

def candidate_map_audit(
    map_id: str, records: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """候选图的公开机制审计（只读，不改规则、不加 seed）。"""

    if map_id not in MAP_IDS:
        return {"map_id": map_id, "available": False, "reason": "未注册的地图"}
    if not is_v10(map_id):
        return {
            "map_id": map_id,
            "available": False,
            "reason": "不是 V10 原生图（V8 适配图不在候选范围）",
        }
    factory = v10_class(map_id)
    space = seed_space(map_id)
    public_fields = sorted(getattr(factory, "PUBLIC_FIELDS", frozenset()))
    shapes = getattr(factory, "SHAPES", {})
    actions = sorted(shapes) if isinstance(shapes, dict) else []
    metric_specs = getattr(factory, "METRIC_SPECS", ())
    selected = [
        item for item in (records or []) if str(item.get("map_id")) == map_id
    ]
    status_row = _v10_status(map_id)
    categories: dict[str, int] = {}
    for item in selected:
        key = str(item.get("category") or "unknown")
        categories[key] = categories.get(key, 0) + 1
    max_decisions = max(
        (int(item.get("decisions") or 0) for item in selected), default=0
    )
    max_requests = max((int(item.get("requests") or 0) for item in selected), default=0)
    censored = categories.get("budget_censored", 0)
    # 长失败前缀判据：历史里出现过"用到 60% 以上决策预算但未成功"的局
    long_prefix_runs = sum(
        1
        for item in selected
        if int(item.get("decisions") or 0) >= 0.6 * max(1, int(item.get("decision_cap") or 60))
        and str(item.get("category")) != "completed_success"
    )
    return {
        "map_id": map_id,
        "available": True,
        "title": getattr(factory, "title", ""),
        "world": getattr(factory, "world", ""),
        "level": getattr(factory, "level", ""),
        "rule_hash": rule_hash(map_id),
        "rule_version": getattr(factory, "RULE_VERSION", ""),
        "seed_space": list(space),
        "public_field_count": len(public_fields),
        "public_fields": public_fields,
        "actions": actions,
        "primary_metric": getattr(factory, "PRIMARY_METRIC", ""),
        "metric_spec_count": len(metric_specs),
        "public_rules_count": len(_public_rules(map_id, space)),
        "historical_runs": len(selected),
        "historical_categories": categories,
        "max_decisions": max_decisions,
        "max_requests": max_requests,
        "censored_runs": censored,
        "long_failure_prefix_runs": long_prefix_runs,
        "v10_status": status_row,
        "reflection_candidate": (
            "PLAUSIBLE"
            if long_prefix_runs > 0
            else ("NEEDS_MORE_EVIDENCE" if not selected else "UNLIKELY")
        ),
        "note": (
            "本审计只读公开规则与历史终态；**不修改地图规则、不新增 seed、"
            "不声称这些图一定更适合反思**。"
        ),
    }

def map_audit_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    axis = map30_three_axis(records)
    return {
        "schema": "v14-map-audit-1",
        "focus_maps": list(FOCUS_MAPS),
        "six_map": six_map_recheck(records),
        "map30": axis,
        "map30_interval": map30_conservative_interval(axis),
        "candidates": [
            candidate_map_audit(map_id, records) for map_id in CANDIDATE_MAPS
        ],
    }

def map_audit_markdown(report: dict[str, Any]) -> str:
    six = report["six_map"]
    axis = report["map30"]
    interval = report["map30_interval"]
    lines = [
        "# V14 地图适用性审计（P1-1 / P1-2）",
        "",
        "> 只读审计：不改 V10 规则、不新增 seed、不修改历史 trace。",
        "> 数据来源：`docs/v12/real-runs/*.csv`（`HISTORICAL`）。",
        "",
        "## 1. 六图标签复算",
        "",
        "| 地图 | 标签 | 有效分母 | 成功 | 成功率 | 独立 seed | 机制触发 | 证据版本 | 状态 |",
        "|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in six["maps"]:
        lines.append(
            f"| {row['map_id']} | `{row['composite']}` | {row['valid_denominator']} | "
            f"{row['successes']} | "
            f"{row['success_rate'] if row['success_rate'] is not None else '—'} | "
            f"{row['independent_seeds']} | {row['trigger_display']} | "
            f"{row['evidence_version']} | `{row['status']}` |"
        )
    lines += [
        "",
        f"> {six['note']}",
        "",
        "### 1.1 标签含义与限制",
        "",
        "| 标签 | 含义 | 不能推出的结论 |",
        "|---|---|---|",
        "| `CEILING` | 现有样本全部成功 | 不能推出「该图没有难度」或「任何策略都能过」 |",
        "| `SUITABLE` | 现有样本出现成功率梯度 | 不能推出构念效度充分或策略引起改善 |",
        "| `CENSORED` | 失败主要是预算截尾 | 不能推出「模型能力弱」 |",
        "| `FLOOR` | 全部失败且截尾占比低 | 不能推出「该图无法通过」 |",
        "",
        "## 2. MAP-30 三维预算阶梯",
        "",
        f"- 观测局数：{axis['runs']}",
        "",
        "| 预算档位 | 局数 | 成功 | 截尾 | 机制失败 | 到法庭被拒 "
        "| 瓶颈轴 | 瓶颈证据 | 最大决策 | 最大 token | 费用 CNY |",
        "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    for tier in axis["tiers"]:
        lines.append(
            f"| `{tier['tier']}` | {tier['runs']} | {tier['successes']} | "
            f"{tier['censored']} | {tier['mechanism_failures']} | "
            f"{tier['accusation_rejected']} | `{tier['bottleneck_axis']}` | "
            f"{tier['bottleneck_evidence']} | "
            f"{tier['max_decisions']} | {tier['max_input_tokens']} | {tier['cost_cny']} |"
        )
    lines += ["", f"> {axis['reading']}", "", "### 2.1 保守可达区间", ""]
    lines.append("| 预算档位 | 可达决策区间 | 已观测最大决策 | token/决策 (p10/p50/p90) |")
    lines.append("|---|---|---:|---|")
    for item in interval["intervals"]:
        if not item.get("available"):
            lines.append(f"| `{item['tier']}` | 不可估 | — | {item.get('reason')} |")
            continue
        low, high = item["supported_decisions"]
        tokens = item["tokens_per_decision"]
        lines.append(
            f"| `{item['tier']}` | {low}–{high} | {item['observed_max_decisions']} | "
            f"{tokens['p10']} / {tokens['p50']} / {tokens['p90']} |"
        )
    lines += [
        "",
        f"> {interval['note']}",
        f"> {axis['caution']}",
        "",
        "## 3. 候选图公开机制审计（只读）",
        "",
        "| 地图 | 世界/难度 | seed 空间 | 公开字段 | 动作数 | 历史局 | 长失败前缀局 | 反思候选 |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["candidates"]:
        if not item.get("available"):
            lines.append(f"| {item['map_id']} | — | — | — | — | — | — | {item['reason']} |")
            continue
        lines.append(
            f"| {item['map_id']} | {item['world']} / {item['level']} | "
            f"{item['seed_space']} | {item['public_field_count']} | "
            f"{len(item['actions'])} | {item['historical_runs']} | "
            f"{item['long_failure_prefix_runs']} | `{item['reflection_candidate']}` |"
        )
    lines += [
        "",
        "逐图明细：",
        "",
    ]
    for item in report["candidates"]:
        if not item.get("available"):
            continue
        lines += [
            f"### {item['map_id']} · {item['title']}",
            "",
            f"- 规则版本：`{item['rule_version']}`，`rule_hash = {item['rule_hash'][:12]}`",
            f"- 主指标：`{item['primary_metric']}`（{item['metric_spec_count']} 条指标规格）",
            f"- 公开规则条数：{item['public_rules_count']}",
            f"- 动作：{', '.join(item['actions'])}",
            f"- 历史终态分布（V12 CSV）：{item['historical_categories'] or '无'}",
            f"- V10 登记：{item['v10_status'].get('mimo', '无')}"
            if item.get("v10_status")
            else "- V10 登记：无",
            f"- 最长决策数 / 请求数：{item['max_decisions']} / {item['max_requests']}",
            f"- {item['note']}",
            "",
        ]
    lines += [
        "## 4. 适用范围结论",
        "",
        "- 六图结论**保持** V13 的标签（`CEILING` 08/26、`SUITABLE` 16/18/22、`CENSORED` 30），",
        "  但机制触发一律显示 `UNKNOWN (0 observed)`，不再写 `0/N`；",
        "- MAP-30 的 0 成功必须读作「没测完」，不能读作能力结论；",
        "- 候选图 MAP-19/20/29 的结论最多到 `NEEDS_MORE_EVIDENCE`：",
        "  历史样本不足以支持「更适合反思」的断言，需要离线触发诊断 + 真实 Pilot。",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "CANDIDATE_MAPS",
    "MAP30_TIERS",
    "NEEDS_MORE_EVIDENCE",
    "candidate_map_audit",
    "map30_conservative_interval",
    "map30_three_axis",
    "map_audit_markdown",
    "map_audit_report",
    "six_map_recheck",
]
