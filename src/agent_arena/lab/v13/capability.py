"""机制级能力画像（P1-4 / V13-08-04 … 08-06）。

**不**对 326 个异质指标做平均——那会把"读地图""记路线""规划""抗预算"混成一个
无意义的分数。这里按**地图机制标签**组织六个维度：

| 维度 | 含义 | 代表地图 |
|---|---|---|
| `information_gathering` | 主动探测/读公开信息再动手 | MAP-08、MAP-14、MAP-26 |
| `memory_tracking` | 跨阶段保留并复用公开状态 | MAP-22、MAP-03、MAP-11 |
| `planning_replanning` | 子目标、整帧调度、重规划 | MAP-16、MAP-18、MAP-17 |
| `resource_constraints` | 在 tick/预算/备件约束下取舍 | MAP-18、MAP-26、MAP-30 |
| `failure_recovery` | 被拒/失败后换策略 | MAP-05、MAP-19、MAP-20 |
| `evidence_reasoning` | 证据链与结论推理 | MAP-30、MAP-13、MAP-15 |

每个维度必须给出：适用图数、可测样本数、成功/失败/截尾、代表指标、证据等级。
**缺失机制不记为 0**；数据不足时不给分数（``score=None``）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.attribution import MECHANISM_TOOLS
from agent_arena.v10.metrics.governance import schema_hash
from agent_arena.v10.runtime.catalog import V10_MAPS, v10_class

INFORMATION = "information_gathering"
MEMORY = "memory_tracking"
PLANNING = "planning_replanning"
RESOURCE = "resource_constraints"
RECOVERY = "failure_recovery"
EVIDENCE = "evidence_reasoning"

DIMENSIONS: tuple[str, ...] = (
    INFORMATION,
    MEMORY,
    PLANNING,
    RESOURCE,
    RECOVERY,
    EVIDENCE,
)

DIMENSION_LABELS: dict[str, str] = {
    INFORMATION: "信息搜集",
    MEMORY: "记忆 / 状态追踪",
    PLANNING: "规划 / 重规划",
    RESOURCE: "资源约束",
    RECOVERY: "故障恢复",
    EVIDENCE: "证据推理",
}

#: 地图 → 机制标签（多标签；只登记公开可观察的机制，不评价难度）。
MAP_TAGS: dict[str, tuple[str, ...]] = {
    "MAP-01": (INFORMATION, MEMORY),
    "MAP-02": (INFORMATION, RESOURCE),
    "MAP-03": (MEMORY, EVIDENCE),
    "MAP-04": (RESOURCE, RECOVERY),
    "MAP-05": (RECOVERY, PLANNING),
    "MAP-06": (INFORMATION, EVIDENCE),
    "MAP-07": (RESOURCE, RECOVERY),
    "MAP-08": (INFORMATION, EVIDENCE),
    "MAP-09": (RESOURCE, RECOVERY),
    "MAP-10": (RESOURCE, PLANNING),
    "MAP-11": (MEMORY, RECOVERY),
    "MAP-12": (RESOURCE, PLANNING),
    "MAP-13": (EVIDENCE, PLANNING),
    "MAP-14": (EVIDENCE, INFORMATION),
    "MAP-15": (EVIDENCE, INFORMATION),
    "MAP-16": (PLANNING, RESOURCE),
    "MAP-17": (PLANNING, RESOURCE),
    "MAP-18": (PLANNING, RESOURCE),
    "MAP-19": (RECOVERY, RESOURCE),
    "MAP-20": (RECOVERY, RESOURCE),
    "MAP-21": (INFORMATION, RECOVERY),
    "MAP-22": (MEMORY, INFORMATION),
    "MAP-23": (MEMORY, EVIDENCE),
    "MAP-24": (MEMORY, PLANNING),
    "MAP-25": (INFORMATION, PLANNING),
    "MAP-26": (INFORMATION, RESOURCE),
    "MAP-27": (PLANNING, EVIDENCE),
    "MAP-28": (MEMORY, EVIDENCE),
    "MAP-29": (RECOVERY, EVIDENCE),
    "MAP-30": (EVIDENCE, RESOURCE),
}

LEVEL_STRONG = "SUPPORTED"
LEVEL_WEAK = "TENTATIVE"
LEVEL_THIN = "INSUFFICIENT"
LEVEL_UNTESTED = "NOT_TESTED"

VALID_CATEGORIES = {"completed_success", "mechanism_failure", "budget_censored"}


def _metric_ids(map_id: str) -> list[str]:
    if map_id not in V10_MAPS:
        return []
    try:
        return [spec.metric_id for spec in v10_class(map_id).METRIC_SPECS]
    except Exception:  # noqa: BLE001 - 指标不可读时留空，不猜
        return []


def dimension_profile(
    dimension: str,
    records: list[dict[str, Any]],
    *,
    min_runs: int = 3,
) -> dict[str, Any]:
    """一个维度的画像：只统计该维度适用地图上的观测。"""

    maps = sorted(map_id for map_id, tags in MAP_TAGS.items() if dimension in tags)
    selected = [item for item in records if str(item.get("map_id")) in maps]
    valid = [item for item in selected if str(item.get("category")) in VALID_CATEGORIES]
    successes = sum(1 for item in valid if item.get("category") == "completed_success")
    mechanism_failures = sum(
        1 for item in valid if item.get("category") == "mechanism_failure"
    )
    censored = sum(1 for item in valid if item.get("category") == "budget_censored")
    metrics: dict[str, int] = {}
    for record in selected:
        for metric_id in (record.get("metrics") or {}):
            metrics[str(metric_id)] = metrics.get(str(metric_id), 0) + 1
        primary = str(record.get("primary_metric") or "")
        if primary:
            metrics[primary] = metrics.get(primary, 0) + 1
    representative = [
        metric_id
        for metric_id, _ in sorted(metrics.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    ]
    observed_maps = sorted({str(item.get("map_id")) for item in selected})
    if not selected:
        level = LEVEL_UNTESTED
        score = None
        reason = "该维度适用地图在本批数据里一局都没跑过。"
    elif len(valid) < min_runs:
        level = LEVEL_THIN
        score = None
        reason = f"可测局仅 {len(valid)}（< {min_runs}），不足以给分数。"
    elif censored and censored / max(1, len(valid)) >= 0.3:
        level = LEVEL_THIN
        score = None
        reason = (
            f"截尾 {censored}/{len(valid)}（≥30%）：成功率会被截尾压低，"
            "不当作能力分数。"
        )
    elif len(valid) >= 6:
        level = LEVEL_STRONG
        score = round(successes / len(valid), 4)
        reason = f"可测 {len(valid)} 局，截尾比例可控。"
    else:
        level = LEVEL_WEAK
        score = round(successes / len(valid), 4)
        reason = f"可测 {len(valid)} 局（< 6），只作描述性。"
    return {
        "dimension": dimension,
        "label": DIMENSION_LABELS[dimension],
        "applicable_maps": maps,
        "observed_maps": observed_maps,
        "applicable_map_count": len(maps),
        "observed_map_count": len(observed_maps),
        "runs": len(selected),
        "measurable_runs": len(valid),
        "successes": successes,
        "mechanism_failures": mechanism_failures,
        "budget_censored": censored,
        "success_rate": score,
        "evidence_level": level,
        "level_reason": reason,
        "representative_metrics": representative,
        "missing_maps": sorted(set(maps) - set(observed_maps)),
        "note": (
            "缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。"
        ),
    }


def capability_profile(
    records: list[dict[str, Any]], *, min_runs: int = 3
) -> dict[str, Any]:
    """六维机制画像 + 版本适用性 + 标注状态。"""

    dimensions = [
        dimension_profile(dimension, records, min_runs=min_runs)
        for dimension in DIMENSIONS
    ]
    versions = sorted(
        {str(item.get("agent_version") or "") for item in records if item.get("agent_version")}
    )
    configs = sorted(
        {
            str(item.get("agent_config_hash") or "")[:12]
            for item in records
            if item.get("agent_config_hash")
        }
    )
    metric_schema = schema_hash()
    schemas = sorted(
        {
            str(item.get("metric_schema_hash") or "")
            for item in records
            if item.get("metric_schema_hash")
        }
    )
    return {
        "schema": "v13-capability-profile-1",
        "dimensions": dimensions,
        "runs": len(records),
        "agent_versions": versions,
        "agent_configs": configs,
        "metric_schema_current": metric_schema,
        "metric_schema_observed": schemas,
        "version_comparable": len(schemas) <= 1 or (bool(schemas) and schemas == [metric_schema]),
        "label_status": "agent_reviewed",
        "label_note": (
            "本画像由 Agent 生成，状态只能是 `agent_reviewed`；"
            "`human_approved` 必须由真实人工批准，Agent 不得自行盖章。"
        ),
        "aggregation_rule": (
            "按机制维度聚合，不对 326 个异质指标做整体平均；"
            "每个维度只在适用地图内统计，缺失机制不补 0。"
        ),
        "mechanism_tools": {
            map_id: list(tools) for map_id, tools in MECHANISM_TOOLS.items()
        },
        "map_metric_ids": {
            map_id: _metric_ids(map_id) for map_id in sorted(MAP_TAGS) if map_id in V10_MAPS
        },
    }


def capability_markdown(profile: dict[str, Any]) -> str:
    lines = [
        "# 机制级能力画像",
        "",
        f"- 标注状态：`{profile.get('label_status')}` — {profile.get('label_note')}",
        f"- 聚合规则：{profile.get('aggregation_rule')}",
        f"- 版本：{profile.get('agent_versions')}；指标 schema 一致："
        f"{'是' if profile.get('version_comparable') else '否（不可跨版本平均）'}",
        "",
        "| 维度 | 适用图 | 已观测图 | 可测局 | 成功 | 机制失败 | 截尾 | 成功率 | 证据等级 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in profile.get("dimensions") or []:
        rate = item["success_rate"]
        lines.append(
            f"| {item['label']} (`{item['dimension']}`) | {item['applicable_map_count']} | "
            f"{item['observed_map_count']} | {item['measurable_runs']} | {item['successes']} | "
            f"{item['mechanism_failures']} | {item['budget_censored']} | "
            f"{'—' if rate is None else rate} | `{item['evidence_level']}` |"
        )
    lines += ["", "## 代表指标与缺口", ""]
    for item in profile.get("dimensions") or []:
        lines.append(f"### {item['label']}")
        lines.append(
            "- 代表指标：" + (", ".join(f"`{m}`" for m in item["representative_metrics"]) or "—")
        )
        lines.append(
            "- 未观测地图："
            + (", ".join(item["missing_maps"]) if item["missing_maps"] else "无")
        )
        lines.append(f"- 等级理由：{item['level_reason']}")
        lines.append(f"- {item['note']}")
        lines.append("")
    lines += [
        "## 限制",
        "",
        "- 维度标签是**人工登记的公开机制**，不是从指标里反推出来的；",
        "- 同一局可能同时属于多个维度（例如 MAP-30 既在证据推理也在资源约束）；",
        "- 成功率只描述已观测样本，不构成跨地图可比的能力分数。",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "DIMENSIONS",
    "DIMENSION_LABELS",
    "EVIDENCE",
    "INFORMATION",
    "LEVEL_STRONG",
    "LEVEL_THIN",
    "LEVEL_UNTESTED",
    "LEVEL_WEAK",
    "MAP_TAGS",
    "MEMORY",
    "PLANNING",
    "RECOVERY",
    "RESOURCE",
    "capability_markdown",
    "capability_profile",
    "dimension_profile",
]
