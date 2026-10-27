"""V14 Lab 视图增强（P1-5 / P2-3）：纯函数，不依赖 Streamlit。

四个视图 + 一个门禁：

| 函数 | 作用 | 关键约束 |
|---|---|---|
| ``first_divergence_view`` | 双轨迹首次分歧高亮 | 只比较公开动作与公开结果；拒绝/成功分别标注 |
| ``seed_grouped_repeats`` | 重复结果按 seed 分组 | 同 seed 的重复不是新环境样本 |
| ``map22_exploration_view`` | MAP-22 探索摘要 | 被拒移动**绝不**画成走过的边 |
| ``map30_ladder_view`` | MAP-30 预算阶梯 | 截尾 ≠ 能力；瓶颈轴单独展示 |
| ``comparison_gate`` | 不可比时禁用结论 | 页面必须显示原因，而不是给一个"更好"的排名 |

所有函数都是纯函数（输入 dict → 输出 dict），可单测、可 JSON 序列化，
不含任何私有状态或隐藏真值。
"""

from __future__ import annotations

from typing import Any

#: 拒绝类公开结果的前缀（与 V10/V12 的终态码一致）。
REJECTED_PREFIXES: tuple[str, ...] = (
    "BEARING_",
    "NOT_",
    "INVALID",
    "ACTION_NOT",
    "REJECTED",
    "MEMORY_",
)

def _action(step: dict[str, Any]) -> dict[str, Any]:
    value = step.get("action")
    return value if isinstance(value, dict) else {}

def _result_text(step: dict[str, Any]) -> str:
    for key in ("result", "public_result", "last_action_result"):
        value = step.get(key)
        if isinstance(value, str) and value:
            return value
    return ""

def _is_rejected(text: str) -> bool:
    upper = text.upper()
    return any(upper.startswith(prefix) for prefix in REJECTED_PREFIXES)

def _step_index(step: dict[str, Any], fallback: int) -> int:
    for key in ("decision_index", "step", "index"):
        value = step.get(key)
        if isinstance(value, int):
            return value
    return fallback

# ------------------------------------------------------- dual-trace divergence
def first_divergence_view(
    left_steps: list[dict[str, Any]],
    right_steps: list[dict[str, Any]],
    *,
    left_label: str = "A",
    right_label: str = "B",
    left_version: str = "",
    right_version: str = "",
) -> dict[str, Any]:
    """找出两条轨迹的首次公开分歧，并给出可高亮的对照行。

    "分歧"= 同一决策序号上「动作」或「公开结果」不同。只比公开字段，
    不推断内部原因；版本不同时额外提示"这是版本比较，不是单开关消融"。
    """

    rows: list[dict[str, Any]] = []
    divergence: dict[str, Any] | None = None
    total = max(len(left_steps), len(right_steps))
    for index in range(total):
        left = left_steps[index] if index < len(left_steps) else {}
        right = right_steps[index] if index < len(right_steps) else {}
        left_action = _action(left)
        right_action = _action(right)
        left_result = _result_text(left)
        right_result = _result_text(right)
        same_action = left_action == right_action
        same_result = left_result == right_result
        differs = not (same_action and same_result)
        row = {
            "step": _step_index(left or right, index),
            "left_action": left_action,
            "right_action": right_action,
            "left_result": left_result,
            "right_result": right_result,
            "left_rejected": _is_rejected(left_result),
            "right_rejected": _is_rejected(right_result),
            "differs": differs,
            "first_divergence": False,
        }
        if differs and divergence is None:
            divergence = {
                "step": row["step"],
                "kind": (
                    "ACTION"
                    if not same_action
                    else "PUBLIC_RESULT"
                ),
                "left_action": left_action,
                "right_action": right_action,
                "left_result": left_result,
                "right_result": right_result,
                "left_rejected": row["left_rejected"],
                "right_rejected": row["right_rejected"],
                "anchor": f"{left_label}#{row['step']} vs {right_label}#{row['step']}",
            }
            row["first_divergence"] = True
        rows.append(row)
    version_note = ""
    if left_version and right_version and left_version != right_version:
        version_note = (
            f"两侧策略版本不同（{left_version} vs {right_version}）："
            "这是**版本比较**，不能宣称某个开关的因果效果。"
        )
    return {
        "schema": "v14-first-divergence-1",
        "left_label": left_label,
        "right_label": right_label,
        "compared_steps": total,
        "first_divergence": divergence,
        "rows": rows[:40],
        "identical_prefix": (
            divergence["step"] if divergence else None
        ),
        "version_note": version_note,
        "note": (
            "只比较公开动作与公开结果；"
            "高亮的是「首次出现差异的那一步」，不解释差异的内部原因。"
        ),
    }

# -------------------------------------------------------- seed-grouped repeats
def seed_grouped_repeats(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """把重复稳定性行按 ``(map, seed)`` 分组，并显式声明重复不是新样本。

    输入行至少包含 ``map_id`` / ``environment_seed`` / ``n`` / ``evidence_label``；
    其余字段原样透传。
    """

    buckets: dict[tuple[str, int], dict[str, Any]] = {}
    for row in groups:
        map_id = str(row.get("map_id") or row.get("map") or "")
        seed = int(row.get("environment_seed") or row.get("seed") or 0)
        bucket = buckets.setdefault(
            (map_id, seed),
            {
                "map_id": map_id,
                "environment_seed": seed,
                "groups": 0,
                "observations": 0,
                "categories": set(),
                "evidence_labels": set(),
                "comparable": True,
            },
        )
        bucket["groups"] += 1
        bucket["observations"] += int(row.get("n") or row.get("observations") or 0)
        for key in ("categories", "category_counts"):
            value = row.get(key)
            if isinstance(value, list):
                bucket["categories"].update(str(item) for item in value)
            elif isinstance(value, dict):
                bucket["categories"].update(str(item) for item in value)
        if row.get("evidence_label"):
            bucket["evidence_labels"].add(str(row["evidence_label"]))
        if row.get("comparable") is False:
            bucket["comparable"] = False
    rows = []
    for bucket in sorted(
        buckets.values(), key=lambda item: (item["map_id"], item["environment_seed"])
    ):
        categories = sorted(bucket["categories"])
        rows.append(
            {
                "map_id": bucket["map_id"],
                "environment_seed": bucket["environment_seed"],
                "groups": bucket["groups"],
                "observations": bucket["observations"],
                "distinct_categories": categories,
                "flipped": len(categories) > 1,
                "evidence_labels": sorted(bucket["evidence_labels"]),
                "comparable": bucket["comparable"],
            }
        )
    return {
        "schema": "v14-seed-groups-1",
        "rows": rows,
        "seed_count": len({(row["map_id"], row["environment_seed"]) for row in rows}),
        "flipped_seeds": [
            f"{row['map_id']}#{row['environment_seed']}" for row in rows if row["flipped"]
        ],
        "note": (
            "同一 seed 的多次重复只反映模型采样波动，**不构成新的环境样本**；"
            "跨 seed 的差异才能谈泛化，且样本少时仍只作描述。"
        ),
    }

# ------------------------------------------------------- MAP-22 exploration
def map22_exploration_view(model: dict[str, Any]) -> dict[str, Any]:
    """MAP-22 探索摘要：接受边与拒绝移动分列，绝不把拒绝画成路径。"""

    if not model.get("available"):
        return {
            "schema": "v14-map22-1",
            "available": False,
            "reason": model.get("empty_reason") or "没有可绘制的公开数据。",
        }
    edges = list(model.get("edges") or [])
    rejected = list(model.get("rejected_moves") or [])
    nodes = list(model.get("nodes") or [])
    path = [str(edge.get("from")) for edge in edges]
    if edges:
        path.append(str(edges[-1].get("to")))
    return {
        "schema": "v14-map22-1",
        "available": True,
        "accepted_edges": len(edges),
        "rejected_moves": len(rejected),
        "discovered_nodes": len(nodes),
        "walked_path": path,
        "rejected_rows": [
            {
                "step": item.get("step"),
                "bearing": item.get("bearing"),
                "result": item.get("result"),
                "position_unchanged": True,
            }
            for item in rejected
        ],
        "moves_used": model.get("moves_used"),
        "move_budget": model.get("move_budget"),
        "statement": (
            f"已绘制 {len(edges)} 条**被接受**的移动边、{len(nodes)} 个已发现路标；"
            f"{len(rejected)} 次被拒移动**没有改变位置，因此不画成走过的路径**。"
        ),
        "note": "未到达区域不显示（隐藏地图不公开）；被拒移动只作为行为证据单列。",
    }

# ------------------------------------------------------------ MAP-30 ladder
def map30_ladder_view(tiers: list[dict[str, Any]]) -> dict[str, Any]:
    """MAP-30 预算阶梯：逐档展示请求/token/金额与瓶颈轴。"""

    rows = []
    for tier in tiers:
        rows.append(
            {
                "tier": tier.get("tier"),
                "request_cap": tier.get("request_cap"),
                "input_token_cap": tier.get("input_token_cap"),
                "runs": tier.get("runs"),
                "successes": tier.get("successes"),
                "censored": tier.get("censored"),
                "mechanism_failures": tier.get("mechanism_failures"),
                "bottleneck_axis": tier.get("bottleneck_axis") or "UNKNOWN",
                "bottleneck_evidence": tier.get("bottleneck_evidence") or "",
                "supported_decisions": (
                    tier.get("capacity", {}).get("estimated_supported_decisions")
                    if isinstance(tier.get("capacity"), dict)
                    else None
                ),
            }
        )
    censored = sum(int(row["censored"] or 0) for row in rows)
    successes = sum(int(row["successes"] or 0) for row in rows)
    return {
        "schema": "v14-map30-ladder-1",
        "rows": rows,
        "tiers": len(rows),
        "total_runs": sum(int(row["runs"] or 0) for row in rows),
        "total_successes": successes,
        "total_censored": censored,
        "reading": (
            "截尾（没测完）与机制失败必须分开读："
            f"本图 {censored} 局截尾、{successes} 局成功。"
            "低档位的 0 成功不能读作能力不足。"
        ),
        "note": "可达区间来自已观测分布，是估计范围，不承诺能跑通。",
    }

# ------------------------------------------------------------- comparison gate
def comparison_gate(verdict: str, reasons: list[str] | None = None) -> dict[str, Any]:
    """不可比时禁用结论；可比时也禁止"显著/因果"的措辞。"""

    reasons = list(reasons or [])
    normalized = str(verdict or "").upper()
    if normalized == "INCOMPARABLE":
        return {
            "allowed": False,
            "show_ranking": False,
            "verdict": normalized,
            "headline": "不可做因果比较",
            "reason": "；".join(reasons[:4]) or "存在硬不匹配（地图/预算/契约/采样）。",
            "note": "页面只展示并列事实，不给「谁更好」的结论。",
        }
    if normalized in {"DESCRIPTIVE_ONLY", "NOT_COMPARABLE"}:
        return {
            "allowed": True,
            "show_ranking": False,
            "verdict": normalized,
            "headline": "只能描述性对照",
            "reason": "；".join(reasons[:4]) or "版本/采样/预算未登记或策略不同。",
            "note": "可以并列数字，但不能宣称显著改善或因果。",
        }
    return {
        "allowed": True,
        "show_ranking": True,
        "verdict": normalized or "UNKNOWN",
        "headline": "可比对照",
        "reason": "；".join(reasons[:4]) or "条件一致。",
        "note": "即使可比，`SUPPORTED` 也只表示证据形式满足门槛，不等于显著改善。",
    }

__all__ = [
    "REJECTED_PREFIXES",
    "comparison_gate",
    "first_divergence_view",
    "map22_exploration_view",
    "map30_ladder_view",
    "seed_grouped_repeats",
]
