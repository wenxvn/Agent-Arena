"""聚合、配对比较与版本门禁。

规则：

- 只用**可确认的原始记录**聚合；缺失、截尾、不适用一律不补 0、不算均值；
- 只有同地图、同 seed、同规则/指标 schema、同模型与预算口径的实验臂才可配对；
- 样本不足只给描述性统计，不生成“公平排名”；
- 分母（``valid_denominator``）逐类别显式给出。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from agent_arena.lab.contracts import (
    ArmAggregate,
    ComparisonPolicy,
    ComparisonResult,
)
from agent_arena.v10.metrics.governance import schema_hash
from agent_arena.v10.runtime.catalog import V10_MAPS, v10_class

#: 单局分类（互斥且穷尽）。
CATEGORY_SUCCESS = "completed_success"
CATEGORY_MECHANISM_FAILURE = "mechanism_failure"
CATEGORY_BUDGET_CENSORED = "budget_censored"
CATEGORY_CANCELLED = "cancelled"
CATEGORY_PROVIDER_ERROR = "provider_error"
CATEGORY_INTERRUPTED = "interrupted"
CATEGORY_INVALID = "invalid_run"
CATEGORY_PENDING = "pending"

VALID_DENOMINATOR_CATEGORIES = (
    CATEGORY_SUCCESS,
    CATEGORY_MECHANISM_FAILURE,
    CATEGORY_BUDGET_CENSORED,
)

CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_SUCCESS: "完成且成功",
    CATEGORY_MECHANISM_FAILURE: "机制失败",
    CATEGORY_BUDGET_CENSORED: "预算截尾",
    CATEGORY_CANCELLED: "已取消",
    CATEGORY_PROVIDER_ERROR: "Provider 错误",
    CATEGORY_INTERRUPTED: "已中断",
    CATEGORY_INVALID: "运行/策略异常",
    CATEGORY_PENDING: "未执行",
}

VERDICT_COMPARABLE = "COMPARABLE"
VERDICT_DESCRIPTIVE = "DESCRIPTIVE_ONLY"
VERDICT_INCOMPARABLE = "INCOMPARABLE"


def classify_child(state: str, result: dict[str, Any]) -> str:
    """把运行状态与结果映射成统计类别；Provider 错误不算认知失败。"""

    outcome = str(result.get("outcome") or "")
    if state == "SUCCEEDED":
        return CATEGORY_SUCCESS
    if state == "FAILED":
        if outcome == "scenario_failure":
            return CATEGORY_MECHANISM_FAILURE
        return CATEGORY_INVALID
    if state == "BUDGET_REACHED":
        return CATEGORY_BUDGET_CENSORED
    if state == "CANCELLED":
        return CATEGORY_CANCELLED
    if state == "PROVIDER_ERROR":
        return CATEGORY_PROVIDER_ERROR
    if state == "INTERRUPTED":
        return CATEGORY_INTERRUPTED
    return CATEGORY_PENDING


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def run_record(
    *,
    run_id: str,
    matrix_index: int | None,
    manifest: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """把一局 manifest + result 归一成聚合记录（只含公开字段）。"""

    raw_usage = result.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    state = str(result.get("state") or manifest.get("state") or "")
    raw_config = manifest.get("config")
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    cost = _decimal(usage.get("cost_settled_cny"))
    raw_metrics = result.get("metrics")
    metrics: dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else {}
    raw_hashes = manifest.get("hashes")
    hashes: dict[str, Any] = raw_hashes if isinstance(raw_hashes, dict) else {}
    return {
        "run_id": run_id,
        "matrix_index": matrix_index,
        "map_id": str(result.get("map_id") or manifest.get("map_id") or ""),
        "environment_seed": int(
            result.get("environment_seed") or manifest.get("environment_seed") or 0
        ),
        "agent_id": str(result.get("agent") or config.get("agent") or ""),
        "agent_version": str(result.get("agent_version") or ""),
        "agent_config_hash": str(result.get("agent_config_hash") or ""),
        "state": state,
        "outcome": str(result.get("outcome") or ""),
        "termination": str(result.get("termination") or ""),
        "category": classify_child(state, result),
        "success": bool(result.get("success")),
        "decisions": int(result.get("decision_count") or 0),
        "decision_budget": int(result.get("max_decisions") or 0),
        "requests": int(usage.get("requests") or 0),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "latency_ms": int(usage.get("latency_ms") or 0),
        "cost_cny": None if cost is None else float(cost),
        "cost_known": not bool(usage.get("cost_unknown")) and cost is not None,
        "rejected_actions": int(result.get("rejected_actions") or 0),
        "invalid_actions": int(result.get("invalid_actions") or 0),
        "mechanism_triggered": result.get("mechanism_triggered"),
        "primary_metric": str(result.get("primary_metric") or ""),
        "primary_state": str(result.get("primary_metric_state") or ""),
        "primary_value": result.get("primary_metric_value"),
        "metrics": dict(metrics),
        #: V12 研究投影（当前只有 MAP-22 route_recall）；与 V10 指标分列，不混算。
        "metrics_v12": dict(result.get("metrics_v12") or {}),
        "mode": str(result.get("mode") or manifest.get("mode") or ""),
        "provider_id": str(result.get("provider_id") or manifest.get("provider_id") or ""),
        "model": str(result.get("model") or manifest.get("model") or ""),
        "rule_hash": result.get("rule_hash") or hashes.get("rule_hash"),
        "metric_hash": result.get("metric_hash") or hashes.get("metric_hash"),
        "metric_schema_hash": result.get("metric_schema_hash")
        or hashes.get("metric_schema_hash"),
        "agent_events": len(result.get("agent_events") or []),
        "partial": bool(result.get("partial")),
    }


# --------------------------------------------------------------------- aggregates
def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def aggregate_metrics(map_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """按指标聚合：只有 ``VALID`` 进入均值；其余状态只计频次。"""

    specs = {}
    if map_id in V10_MAPS:
        specs = {spec.metric_id: spec for spec in v10_class(map_id).METRIC_SPECS}
    buckets: dict[str, dict[str, Any]] = {}
    for record in records:
        metrics = record.get("metrics") or {}
        for metric_id, payload in metrics.items():
            if not isinstance(payload, dict):
                continue
            bucket = buckets.setdefault(
                metric_id,
                {
                    "metric_id": metric_id,
                    "states": {},
                    "values": [],
                    "numerator": 0.0,
                    "denominator": 0.0,
                    "has_ratio": True,
                },
            )
            state = str(payload.get("state") or "MISSING")
            bucket["states"][state] = bucket["states"].get(state, 0) + 1
            if state == "VALID":
                value = payload.get("value")
                if isinstance(value, (int, float)):
                    bucket["values"].append(float(value))
                numerator = payload.get("numerator")
                denominator = payload.get("denominator")
                if isinstance(numerator, (int, float)) and isinstance(
                    denominator, (int, float)
                ):
                    bucket["numerator"] += float(numerator)
                    bucket["denominator"] += float(denominator)
                else:
                    bucket["has_ratio"] = False

    output: dict[str, Any] = {}
    for metric_id, bucket in sorted(buckets.items()):
        spec = specs.get(metric_id)
        valid_values: list[float] = bucket["values"]
        pooled = (
            round(bucket["numerator"] / bucket["denominator"], 6)
            if bucket["has_ratio"] and bucket["denominator"] > 0
            else None
        )
        output[metric_id] = {
            "metric_id": metric_id,
            "role": spec.role if spec else "unknown",
            "direction": spec.direction if spec else "unknown",
            "unit": spec.unit if spec else "unknown",
            "states": dict(sorted(bucket["states"].items())),
            "valid_count": len(valid_values),
            "mean": _mean(valid_values),
            "pooled_ratio": pooled,
            "numerator": bucket["numerator"] if bucket["has_ratio"] else None,
            "denominator": bucket["denominator"] if bucket["has_ratio"] else None,
            "not_computed_reason": (
                "没有任何 VALID 取值；不补零"
                if not valid_values and not pooled
                else ""
            ),
        }
    return output


def aggregate_arm(
    agent_id: str, records: list[dict[str, Any]], *, map_id: str = ""
) -> ArmAggregate:
    """一个实验臂的聚合；``valid_denominator`` 只含有效类别。"""

    versions = sorted({record["agent_version"] for record in records if record["agent_version"]})
    categories = {record["category"]: 0 for record in records}
    counts: dict[str, int] = {}
    for record in records:
        counts[record["category"]] = counts.get(record["category"], 0) + 1
    valid = sum(counts.get(item, 0) for item in VALID_DENOMINATOR_CATEGORIES)
    successes = counts.get(CATEGORY_SUCCESS, 0)
    costs = [record["cost_cny"] for record in records if record["cost_known"]]
    latencies = [record["latency_ms"] for record in records if record["latency_ms"]]
    metrics: dict[str, Any] = {}
    if map_id:
        metrics = aggregate_metrics(map_id, records)
    else:
        for item in sorted({record["map_id"] for record in records}):
            metrics[item] = aggregate_metrics(
                item, [record for record in records if record["map_id"] == item]
            )
    del categories
    return ArmAggregate(
        agent_id=agent_id,
        agent_version=versions[0] if len(versions) == 1 else ",".join(versions),
        runs=len(records),
        valid_denominator=valid,
        successes=successes,
        mechanism_failures=counts.get(CATEGORY_MECHANISM_FAILURE, 0),
        budget_censored=counts.get(CATEGORY_BUDGET_CENSORED, 0),
        cancelled=counts.get(CATEGORY_CANCELLED, 0),
        provider_errors=counts.get(CATEGORY_PROVIDER_ERROR, 0),
        interrupted=counts.get(CATEGORY_INTERRUPTED, 0),
        invalid_runs=counts.get(CATEGORY_INVALID, 0),
        success_rate=(round(successes / valid, 6) if valid else None),
        mean_decisions=_mean([float(record["decisions"]) for record in records]),
        mean_requests=_mean([float(record["requests"]) for record in records]),
        mean_cost_cny=_mean([float(value) for value in costs]),
        cost_known_runs=len(costs),
        mean_latency_ms=_mean([float(value) for value in latencies]),
        rejected_actions=sum(record["rejected_actions"] for record in records),
        invalid_actions=sum(record["invalid_actions"] for record in records),
        metrics=metrics,
    )


# ---------------------------------------------------------------------- versions
def version_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    """版本口径：模型、Provider、模式全局一致；规则/指标 hash 按地图一致。"""

    def unique(field: str) -> list[str]:
        return sorted({str(record.get(field) or "") for record in records if record.get(field)})

    per_map: dict[str, dict[str, list[str]]] = {}
    for record in records:
        bucket = per_map.setdefault(
            str(record["map_id"]), {"rule_hash": [], "metric_hash": []}
        )
        for field in ("rule_hash", "metric_hash"):
            value = str(record.get(field) or "")
            if value and value not in bucket[field]:
                bucket[field].append(value)
    return {
        "models": unique("model"),
        "providers": unique("provider_id"),
        "modes": unique("mode"),
        "rule_hashes": unique("rule_hash"),
        "metric_hashes": unique("metric_hash"),
        "metric_schema_hashes": unique("metric_schema_hash"),
        "metric_schema_current": schema_hash(),
        "per_map": {
            map_id: {key: sorted(value) for key, value in bucket.items()}
            for map_id, bucket in per_map.items()
        },
    }


def _mismatch_reasons(records: list[dict[str, Any]]) -> list[str]:
    profile = version_profile(records)
    reasons: list[str] = []
    if len(profile["models"]) > 1:
        reasons.append(f"模型不一致：{', '.join(profile['models'])}")
    if len(profile["providers"]) > 1:
        reasons.append(f"Provider 不一致：{', '.join(profile['providers'])}")
    if len(profile["modes"]) > 1:
        reasons.append(f"执行模式不一致：{', '.join(profile['modes'])}")
    for map_id, bucket in sorted(profile["per_map"].items()):
        if len(bucket["rule_hash"]) > 1:
            reasons.append(f"{map_id} 存在多个 rule_hash")
        if len(bucket["metric_hash"]) > 1:
            reasons.append(f"{map_id} 存在多个 metric_hash")
    current = profile["metric_schema_current"]
    if any(item != current for item in profile["metric_schema_hashes"]):
        reasons.append("指标 schema 与当前版本不一致")
    return reasons


@dataclass(frozen=True)
class PairSlot:
    pairing_key: str
    map_id: str
    environment_seed: int
    left: dict[str, Any]
    right: dict[str, Any]
    verdict: str
    reasons: tuple[str, ...]


def pair_records(
    records: list[dict[str, Any]],
    policy: ComparisonPolicy,
    *,
    left_agent: str,
    right_agent: str,
) -> list[PairSlot]:
    """按 ``(map_id, environment_seed)`` 配对两个实验臂。"""

    index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for record in records:
        key = (record["map_id"], record["environment_seed"], record["agent_id"])
        index[key] = record
    keys = sorted({(item["map_id"], item["environment_seed"]) for item in records})
    slots: list[PairSlot] = []
    for map_id, seed in keys:
        left = index.get((map_id, seed, left_agent))
        right = index.get((map_id, seed, right_agent))
        if left is None or right is None:
            continue
        reasons: list[str] = []
        if left["mode"] != right["mode"]:
            reasons.append("执行模式不同")
        if left["model"] != right["model"]:
            reasons.append("模型不同")
        if left["rule_hash"] != right["rule_hash"]:
            reasons.append("规则版本不同")
        if left["metric_schema_hash"] != right["metric_schema_hash"]:
            reasons.append("指标 schema 不同")
        if left["cost_known"] != right["cost_known"]:
            reasons.append("一局费用未知，成本对比不成立")
        if reasons:
            verdict = VERDICT_INCOMPARABLE
        elif policy.require_same_versions is False:
            verdict = VERDICT_DESCRIPTIVE
        else:
            verdict = VERDICT_COMPARABLE
        slots.append(
            PairSlot(
                pairing_key=f"{map_id}|seed={seed}",
                map_id=map_id,
                environment_seed=seed,
                left=left,
                right=right,
                verdict=verdict,
                reasons=tuple(reasons),
            )
        )
    return slots


def _arm_ids(records: list[dict[str, Any]]) -> list[str]:
    return sorted({record["agent_id"] for record in records})


def aggregate_projection(records: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合 V12 研究投影指标（与 V10 指标分开，不参与 V10 均值）。"""

    buckets: dict[str, dict[str, Any]] = {}
    for record in records:
        for metric_id, payload in (record.get("metrics_v12") or {}).items():
            if not isinstance(payload, dict):
                continue
            bucket = buckets.setdefault(
                metric_id,
                {
                    "metric_id": metric_id,
                    "states": {},
                    "values": [],
                    "numerator": 0.0,
                    "denominator": 0.0,
                    "rule_version": payload.get("rule_version"),
                },
            )
            state = str(payload.get("state") or "MISSING")
            bucket["states"][state] = bucket["states"].get(state, 0) + 1
            if state == "VALID":
                value = payload.get("value")
                if isinstance(value, (int, float)):
                    bucket["values"].append(float(value))
                numerator = payload.get("numerator")
                denominator = payload.get("denominator")
                if isinstance(numerator, (int, float)) and isinstance(
                    denominator, (int, float)
                ):
                    bucket["numerator"] += float(numerator)
                    bucket["denominator"] += float(denominator)
    output: dict[str, Any] = {}
    for metric_id, bucket in sorted(buckets.items()):
        values: list[float] = bucket["values"]
        pooled = (
            round(bucket["numerator"] / bucket["denominator"], 6)
            if bucket["denominator"] > 0
            else None
        )
        output[metric_id] = {
            "metric_id": metric_id,
            "states": dict(sorted(bucket["states"].items())),
            "valid_count": len(values),
            "mean": round(sum(values) / len(values), 6) if values else None,
            "pooled_ratio": pooled,
            "numerator": bucket["numerator"],
            "denominator": bucket["denominator"],
            "rule_version": bucket["rule_version"],
            "namespace": "v12.projection",
            "note": "V12 研究投影，不是 V10 官方指标；不参与 V10 均值。",
        }
    return output


def build_comparison(
    *,
    experiment_id: str,
    records: list[dict[str, Any]],
    policy: ComparisonPolicy,
    notes: list[str] | None = None,
) -> ComparisonResult:
    """生成配对比较；不可比时不生成任何排名或“提升”结论。"""

    notes = list(notes or [])
    arms = _arm_ids(records)
    reasons = _mismatch_reasons(records)
    excluded: list[dict[str, Any]] = []
    for record in records:
        if record["category"] in {CATEGORY_PENDING}:
            excluded.append(
                {"run_id": record["run_id"], "reason": "未执行", "category": record["category"]}
            )

    per_map: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    for map_id in sorted({record["map_id"] for record in records}):
        map_records = [record for record in records if record["map_id"] == map_id]
        row: dict[str, Any] = {
            "map_id": map_id,
            "arms": [
                aggregate_arm(
                    agent,
                    [item for item in map_records if item["agent_id"] == agent],
                    map_id=map_id,
                ).as_dict()
                for agent in arms
                if any(item["agent_id"] == agent for item in map_records)
            ],
            "seeds": sorted({record["environment_seed"] for record in map_records}),
            "pairs": 0,
            "projection": aggregate_projection(map_records),
        }
        for left_index, left_agent in enumerate(arms):
            for right_agent in arms[left_index + 1 :]:
                slots = pair_records(
                    map_records, policy, left_agent=left_agent, right_agent=right_agent
                )
                for slot in slots:
                    pairs.append(
                        {
                            "pairing_key": slot.pairing_key,
                            "map_id": slot.map_id,
                            "environment_seed": slot.environment_seed,
                            "left_agent": left_agent,
                            "right_agent": right_agent,
                            "left_run_id": slot.left["run_id"],
                            "right_run_id": slot.right["run_id"],
                            "verdict": slot.verdict,
                            "reasons": list(slot.reasons),
                            "left_success": slot.left["success"],
                            "right_success": slot.right["success"],
                            "left_decisions": slot.left["decisions"],
                            "right_decisions": slot.right["decisions"],
                            "left_requests": slot.left["requests"],
                            "right_requests": slot.right["requests"],
                            "left_cost_cny": slot.left["cost_cny"],
                            "right_cost_cny": slot.right["cost_cny"],
                            "left_category": slot.left["category"],
                            "right_category": slot.right["category"],
                        }
                    )
                row["pairs"] += len(slots)
        per_map.append(row)

    paired_counts = [row["pairs"] for row in per_map]
    comparable_pairs = [pair for pair in pairs if pair["verdict"] == VERDICT_COMPARABLE]
    if reasons:
        verdict = VERDICT_INCOMPARABLE
    elif len(arms) < 2:
        verdict = VERDICT_INCOMPARABLE
        reasons.append("少于两个实验臂，无法做架构对照")
    elif not pairs:
        verdict = VERDICT_INCOMPARABLE
        reasons.append("没有可配对的条件（地图/seed 未对齐）")
    elif not comparable_pairs:
        verdict = VERDICT_INCOMPARABLE
        reasons.append("所有配对都不可比（费用未知、版本或模式不一致）")
    elif (
        policy.descriptive_only_for_small_samples
        and comparable_pairs
        and min(paired_counts) < policy.min_paired_samples
    ):
        verdict = VERDICT_DESCRIPTIVE
        notes.append(
            f"每对实验臂的有效配对样本最少为 {min(paired_counts)}，"
            f"低于 {policy.min_paired_samples}；只给描述性统计，不作显著性断言。"
        )
    else:
        verdict = VERDICT_COMPARABLE
        if comparable_pairs:
            notes.append(
                f"配对样本为 {min(paired_counts)}（每个配对键一局）；"
                "这是描述性对照，不构成显著性结论。"
            )

    return ComparisonResult(
        experiment_id=experiment_id,
        verdict=verdict,
        reasons=tuple(reasons),
        arms=[
            aggregate_arm(agent, [r for r in records if r["agent_id"] == agent]).as_dict()
            for agent in arms
        ],
        per_map=per_map,
        pairs=pairs,
        excluded_runs=excluded,
        notes=notes,
    )


__all__ = [
    "CATEGORY_BUDGET_CENSORED",
    "CATEGORY_CANCELLED",
    "CATEGORY_INTERRUPTED",
    "CATEGORY_INVALID",
    "CATEGORY_LABELS",
    "CATEGORY_MECHANISM_FAILURE",
    "CATEGORY_PENDING",
    "CATEGORY_PROVIDER_ERROR",
    "CATEGORY_SUCCESS",
    "VALID_DENOMINATOR_CATEGORIES",
    "VERDICT_COMPARABLE",
    "VERDICT_DESCRIPTIVE",
    "VERDICT_INCOMPARABLE",
    "PairSlot",
    "aggregate_arm",
    "aggregate_metrics",
    "aggregate_projection",
    "build_comparison",
    "classify_child",
    "pair_records",
    "run_record",
    "version_profile",
]
