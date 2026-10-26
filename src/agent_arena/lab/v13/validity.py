"""地图效度与 MAP-30 深度分析（P1-2 / P1-6，V13-07-01 … 07-07）。

两个必须分开的概念：

- **工程 Gate**（V10 的 8 个 Gate）说明"这张图能跑、指标能算、回放确定"；
- **构念效度**说明"这张图的成功/失败真的在测量我们想测的能力"。

本模块只产出构念效度标签，不改任何 V10 规则、不新增 seed：

| 标签 | 含义 |
|---|---|
| `SUITABLE` | 有梯度、机制被真实触发、指标可用 |
| `CEILING` | 所有实验臂都成功（测不出差异） |
| `FLOOR` | 所有实验臂都失败且**不是**预算截尾 |
| `CENSORED` | 失败主要是预算/动作上限截尾（没测完） |
| `INTERFACE_ARTEFACT` | 非法动作/契约问题占比过高（接口假象） |
| `NEEDS_EVIDENCE` | 样本不足或机制从未触发 |

标签可**复合**（例如 `FLOOR + CENSORED`），并必须带证据来源与适用限制。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.attribution import MECHANISM_TOOLS

LABEL_SUITABLE = "SUITABLE"
LABEL_CEILING = "CEILING"
LABEL_FLOOR = "FLOOR"
LABEL_CENSORED = "CENSORED"
LABEL_INTERFACE = "INTERFACE_ARTEFACT"
LABEL_NEEDS_EVIDENCE = "NEEDS_EVIDENCE"

VALIDITY_LABELS = (
    LABEL_SUITABLE,
    LABEL_CEILING,
    LABEL_FLOOR,
    LABEL_CENSORED,
    LABEL_INTERFACE,
    LABEL_NEEDS_EVIDENCE,
)

#: 六图重点集合（与 V12 一致）。
FOCUS_MAPS: tuple[str, ...] = (
    "MAP-08",
    "MAP-16",
    "MAP-18",
    "MAP-22",
    "MAP-26",
    "MAP-30",
)

#: 长观测地图：预检必须给预算分解。
LONG_HORIZON_MAPS: tuple[str, ...] = ("MAP-30", "MAP-19", "MAP-20", "MAP-14")

VALID_CATEGORIES = {"completed_success", "mechanism_failure", "budget_censored"}


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def budget_capacity(
    records: list[dict[str, Any]],
    *,
    input_token_cap: int,
    request_cap: int,
) -> dict[str, Any]:
    """从**已观测**的 token/决策分布估算某预算能支撑多少回合（V13-07-02）。

    绝不编造耗时；只给区间，并写明"来自观测分布，不是承诺"。
    """

    per_decision: list[float] = []
    per_request: list[float] = []
    for record in records:
        decisions = int(record.get("decisions") or 0)
        tokens = int(record.get("input_tokens") or 0)
        requests = int(record.get("requests") or 0)
        if decisions > 0 and tokens > 0:
            per_decision.append(tokens / decisions)
        if requests > 0 and decisions > 0:
            per_request.append(decisions / requests)
    if not per_decision:
        return {
            "available": False,
            "reason": "没有可用的 token/决策观测，无法估算回合数（不编造）。",
            "observations": 0,
        }
    low = _percentile(per_decision, 0.9) or 0.0  # 贵的局 → 保守下限
    mid = _percentile(per_decision, 0.5) or 0.0
    high = _percentile(per_decision, 0.1) or 0.0  # 便宜的局 → 乐观上限
    supported_low = int(input_token_cap / low) if low else 0
    supported_high = int(input_token_cap / high) if high else 0
    return {
        "available": True,
        "observations": len(per_decision),
        "tokens_per_decision": {
            "p10": round(high, 2),
            "p50": round(mid, 2),
            "p90": round(low, 2),
        },
        "decisions_per_request": (
            round(sum(per_request) / len(per_request), 4) if per_request else None
        ),
        "input_token_cap": input_token_cap,
        "request_cap": request_cap,
        "estimated_supported_decisions": [supported_low, supported_high],
        "note": (
            "区间来自已观测的 token/决策分布；下限按最贵观测、上限按最便宜观测。"
            "这不是对真实模型的承诺，也不含墙钟耗时。"
        ),
    }


def map30_failure_class(record: dict[str, Any]) -> str:
    """MAP-30 的四类失败（外加成功），全部绑定公开终局码。"""

    category = str(record.get("category") or "")
    termination = str(record.get("termination") or "")
    if category == "completed_success":
        return "SUCCESS"
    if category == "budget_censored":
        return "BUDGET_CENSORED"
    if "ACCUSATION_REJECTED" in termination:
        return "ACCUSATION_REJECTED"
    if "INSUFFICIENT" in termination or "EVIDENCE" in termination:
        return "EVIDENCE_INSUFFICIENT"
    return "REASONING_CHAIN_MIDWAY"


def map30_ladder(records: list[dict[str, Any]]) -> dict[str, Any]:
    """按预算档位重分析 MAP-30 的"地板"到底是能力还是预算（V13-07-01）。"""

    selected = [item for item in records if str(item.get("map_id")) == "MAP-30"]
    tiers: dict[str, dict[str, Any]] = {}
    for record in selected:
        tier = (
            f"req={record.get('request_cap') or 'unknown'}"
            f"|tok={record.get('input_token_cap') or 'unknown'}"
        )
        bucket = tiers.setdefault(
            tier,
            {
                "tier": tier,
                "request_cap": record.get("request_cap"),
                "input_token_cap": record.get("input_token_cap"),
                "runs": 0,
                "successes": 0,
                "censored": 0,
                "mechanism_failures": 0,
                "accusation_rejected": 0,
                "midway": 0,
                "max_decisions": 0,
                "max_input_tokens": 0,
                "cost_cny": 0.0,
            },
        )
        bucket["runs"] += 1
        category = str(record.get("category") or "")
        bucket["successes"] += 1 if category == "completed_success" else 0
        bucket["censored"] += 1 if category == "budget_censored" else 0
        bucket["mechanism_failures"] += 1 if category == "mechanism_failure" else 0
        klass = map30_failure_class(record)
        if klass == "ACCUSATION_REJECTED":
            bucket["accusation_rejected"] += 1
        elif klass in {"EVIDENCE_INSUFFICIENT", "REASONING_CHAIN_MIDWAY"}:
            bucket["midway"] += 1
        bucket["max_decisions"] = max(
            bucket["max_decisions"], int(record.get("decisions") or 0)
        )
        bucket["max_input_tokens"] = max(
            bucket["max_input_tokens"], int(record.get("input_tokens") or 0)
        )
        if record.get("cost_known") and record.get("cost_cny") is not None:
            bucket["cost_cny"] += float(record["cost_cny"])
    ordered = sorted(
        tiers.values(),
        key=lambda item: (item["request_cap"] or 0, item["input_token_cap"] or 0),
    )
    for bucket in ordered:
        bucket["cost_cny"] = round(bucket["cost_cny"], 8)
        bucket["censored_ratio"] = _ratio(bucket["censored"], bucket["runs"])
        bucket["reached_court"] = bucket["accusation_rejected"] > 0
    return {
        "map_id": "MAP-30",
        "runs": len(selected),
        "tiers": ordered,
        "reading": (
            "同一张图在不同预算档位下出现不同瓶颈：先撞请求数，再撞输入 token，"
            "最后撞单局费用。低档位的 0 成功只能读作「没测完」，不是能力结论。"
            if ordered
            else "没有 MAP-30 观测，无法重分析预算阶梯。"
        ),
        "next_candidate_tiers": [
            {"request_cap": 180, "input_token_cap": 600_000, "per_run_cost_cny": 0.25},
            {"request_cap": 240, "input_token_cap": 900_000, "per_run_cost_cny": 0.40},
        ],
        "candidate_note": (
            "以上是**需批准的候选档**，不是默认预算；不得自动启用（V13-07-03）。"
        ),
    }


def map_validity(
    map_id: str, records: list[dict[str, Any]], *, min_runs: int = 3
) -> dict[str, Any]:
    """一张图的构念效度标签（可复合）+ 证据。"""

    selected = [item for item in records if str(item.get("map_id")) == map_id]
    labels: list[str] = []
    reasons: list[str] = []
    valid = [item for item in selected if str(item.get("category")) in VALID_CATEGORIES]
    successes = sum(1 for item in valid if item.get("category") == "completed_success")
    censored = sum(1 for item in valid if item.get("category") == "budget_censored")
    mechanism = sum(1 for item in valid if item.get("category") == "mechanism_failure")
    invalid_actions = sum(int(item.get("invalid_actions") or 0) for item in selected)
    decisions = sum(int(item.get("decisions") or 0) for item in selected)
    arms = sorted({str(item.get("agent_id")) for item in selected})
    triggered = sum(1 for item in selected if item.get("mechanism_triggered"))

    if len(selected) < min_runs:
        labels.append(LABEL_NEEDS_EVIDENCE)
        reasons.append(f"观测仅 {len(selected)} 局（< {min_runs}）。")
    if decisions and invalid_actions / max(1, decisions) > 0.5:
        labels.append(LABEL_INTERFACE)
        reasons.append(
            f"非法动作 {invalid_actions}/{decisions} 超过一半：结论是接口假象。"
        )
    if valid and successes == len(valid) and len(valid) >= min_runs:
        labels.append(LABEL_CEILING)
        reasons.append(f"{successes}/{len(valid)} 全部成功：测不出架构差异。")
    if valid and successes == 0:
        if censored and censored >= max(1, len(valid) // 2):
            labels.append(LABEL_CENSORED)
            reasons.append(
                f"{censored}/{len(valid)} 局预算截尾：0 成功不能读作能力不足。"
            )
        else:
            labels.append(LABEL_FLOOR)
            reasons.append(
                f"{len(valid)} 局全部失败且截尾只占 {censored}：地板更像机制/策略原因。"
            )
    if valid and 0 < successes < len(valid):
        labels.append(LABEL_SUITABLE)
        reasons.append(f"{successes}/{len(valid)} 有梯度：可区分不同实验臂。")
    if not triggered and len(selected) >= min_runs and LABEL_SUITABLE in labels:
        # 只有"字段存在且确实为 0"才算机制未触发；历史 CSV 没有该列时不能据此下结论。
        present = any(item.get("mechanism_triggered") is not None for item in selected)
        if present:
            labels.append(LABEL_NEEDS_EVIDENCE)
            reasons.append("核心机制从未被触发（mechanism_triggered 全为 0）。")
        else:
            reasons.append(
                "历史记录没有 mechanism_triggered 字段：机制触发情况未知，"
                "需在 V13 运行时重新采集，不能用 0 冒充。"
            )
    if not labels:
        labels.append(LABEL_NEEDS_EVIDENCE)
        reasons.append("证据不足，无法给出效度标签。")

    return {
        "map_id": map_id,
        "labels": sorted(set(labels)),
        "composite": "+".join(sorted(set(labels))),
        "runs": len(selected),
        "valid_denominator": len(valid),
        "successes": successes,
        "mechanism_failures": mechanism,
        "budget_censored": censored,
        "censored_ratio": _ratio(censored, len(valid)),
        "success_rate": _ratio(successes, len(valid)),
        "arms": arms,
        "mechanism_tools": list(MECHANISM_TOOLS.get(map_id, ())),
        "mechanism_triggered_runs": triggered,
        "mechanism_triggered_available": any(
            item.get("mechanism_triggered") is not None for item in selected
        ),
        "invalid_actions": invalid_actions,
        "decisions": decisions,
        "reasons": reasons,
        "source": (
            "HISTORICAL"
            if any(item.get("source") == "HISTORICAL" for item in selected)
            else "RUNTIME"
        ),
        "restriction": (
            "工程 Gate 通过 ≠ 构念效度充分；标签只描述「能否区分能力」，"
            "不评价地图设计质量。"
        ),
    }


def six_map_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    """六图效度审计（V13-07-05 / 07-06）。"""

    rows = [map_validity(map_id, records) for map_id in FOCUS_MAPS]
    ceiling = [row["map_id"] for row in rows if LABEL_CEILING in row["labels"]]
    floor = [
        row["map_id"]
        for row in rows
        if LABEL_FLOOR in row["labels"] or LABEL_CENSORED in row["labels"]
    ]
    suitable = [row["map_id"] for row in rows if LABEL_SUITABLE in row["labels"]]
    recommendations: list[dict[str, str]] = []
    for row in rows:
        map_id = row["map_id"]
        if LABEL_CEILING in row["labels"]:
            recommendations.append(
                {
                    "map_id": map_id,
                    "recommendation": "保留为回归/冒烟能力案例，暂不作为区分度排名样本",
                    "why": "所有实验臂都成功，无法区分架构；用它排名只会放大噪声。",
                }
            )
        elif LABEL_CENSORED in row["labels"]:
            recommendations.append(
                {
                    "map_id": map_id,
                    "recommendation": "预算扩展后再评估；先不参与能力比较",
                    "why": "0 成功主要来自截尾，抬高预算可能改变结论（DCR-V12-04）。",
                }
            )
        elif LABEL_SUITABLE in row["labels"]:
            recommendations.append(
                {
                    "map_id": map_id,
                    "recommendation": "可作为区分度样本，但需 ≥3 次重复与同版本配对",
                    "why": "存在真实梯度；单次观测的翻转率仍可能有 20% 以上。",
                }
            )
        else:
            recommendations.append(
                {
                    "map_id": map_id,
                    "recommendation": "补充公开信息或证据后再判断，不自动改规则",
                    "why": "证据不足；V13 不修改 V10 规则、不凭空构造新 seed。",
                }
            )
    return {
        "schema": "v13-map-validity-1",
        "maps": rows,
        "ceiling_maps": ceiling,
        "floor_or_censored_maps": floor,
        "suitable_maps": suitable,
        "recommendations": recommendations,
        "note": (
            "工程 Gate VALIDATED（30/30 可运行）不等于构念效度可信；"
            "本审计只给构念标签，不改任何地图规则。"
        ),
    }


def validity_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# 六图效度审计（构念层）",
        "",
        "> 工程可运行 ≠ 能区分能力。本表只回答「这张图能不能测出架构差异」。",
        "",
        "| 地图 | 标签 | 有效分母 | 成功 | 机制失败 | 截尾 | 成功率 | 机制触发局 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audit.get("maps") or []:
        lines.append(
            f"| {row['map_id']} | `{row['composite']}` | {row['valid_denominator']} | "
            f"{row['successes']} | {row['mechanism_failures']} | {row['budget_censored']} | "
            f"{row['success_rate'] if row['success_rate'] is not None else '—'} | "
            f"{row['mechanism_triggered_runs']}/{row['runs']} |"
        )
    lines += ["", "## 逐图理由", ""]
    for row in audit.get("maps") or []:
        lines.append(f"### {row['map_id']} · `{row['composite']}`")
        for reason in row.get("reasons") or []:
            lines.append(f"- {reason}")
        lines.append(f"- 适用限制：{row.get('restriction')}")
        lines.append("")
    lines += ["## 选图建议", "", "| 地图 | 建议 | 理由 |", "|---|---|---|"]
    for item in audit.get("recommendations") or []:
        lines.append(
            f"| {item['map_id']} | {item['recommendation']} | {item['why']} |"
        )
    lines += ["", f"> {audit.get('note')}", ""]
    return "\n".join(lines)


def map30_markdown(ladder: dict[str, Any]) -> str:
    lines = [
        "# MAP-30 预算阶梯与失败分型",
        "",
        f"- 观测局数：{ladder.get('runs')}",
        f"- 读法：{ladder.get('reading')}",
        "",
        "| 预算档位 | 局数 | 成功 | 截尾 | 机制失败 | 到法庭被拒 | 中途失败 "
        "| 最大决策 | 最大输入 token | 费用 CNY |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tier in ladder.get("tiers") or []:
        lines.append(
            f"| `{tier['tier']}` | {tier['runs']} | {tier['successes']} | "
            f"{tier['censored']} | {tier['mechanism_failures']} | "
            f"{tier['accusation_rejected']} | {tier['midway']} | "
            f"{tier['max_decisions']} | {tier['max_input_tokens']} | {tier['cost_cny']} |"
        )
    lines += [
        "",
        "## 失败分型（互斥）",
        "",
        "- `BUDGET_CENSORED`：撞到请求/token/费用上限，**没测完**；",
        "- `EVIDENCE_INSUFFICIENT`：证据链未集齐（公开终局码含 EVIDENCE/INSUFFICIENT）；",
        "- `ACCUSATION_REJECTED`：真的走到法庭但指控被拒（真实机制失败）；",
        "- `REASONING_CHAIN_MIDWAY`：推理链中途终止，既非截尾也非法庭拒绝；",
        "- `SUCCESS`：完成。",
        "",
        "## 候选预算档（**需批准，不自动启用**）",
        "",
        "| 请求上限 | 输入 token 上限 | 单局费用上限 CNY |",
        "|---:|---:|---:|",
    ]
    for tier in ladder.get("next_candidate_tiers") or []:
        lines.append(
            f"| {tier['request_cap']} | {tier['input_token_cap']} | {tier['per_run_cost_cny']} |"
        )
    lines += ["", f"> {ladder.get('candidate_note')}", ""]
    return "\n".join(lines)


__all__ = [
    "FOCUS_MAPS",
    "LABEL_CEILING",
    "LABEL_CENSORED",
    "LABEL_FLOOR",
    "LABEL_INTERFACE",
    "LABEL_NEEDS_EVIDENCE",
    "LABEL_SUITABLE",
    "LONG_HORIZON_MAPS",
    "VALIDITY_LABELS",
    "budget_capacity",
    "map30_failure_class",
    "map30_ladder",
    "map30_markdown",
    "map_validity",
    "six_map_audit",
    "validity_markdown",
]
