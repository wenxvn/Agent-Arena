"""V8 metric projection over the 154 pre-registered V7 MetricSpec entries.

The 24 new runtimes compute their registered metrics directly from judge state;
the six V4 adapter maps reuse the frozen V7 extractors. This module only
normalises both sources into the five-state V8 artefact and never invents a
value where the map returned ``None``.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from agent_arena.v7.metrics.registry import specs_for
from agent_arena.v7.metrics.schema import MetricStatus, MetricValue


def metric_schema(map_id: str) -> list[dict[str, Any]]:
    return [
        {
            "metric_id": spec.metric_id,
            "kind": spec.kind.value,
            "unit": spec.unit,
            "direction": spec.direction.value,
            "formula": spec.formula,
            "denominator": spec.denominator,
            "valid_range": spec.valid_range,
            "missing_rule": spec.missing_rule,
            "censor_rule": spec.censor_rule,
            "implemented": spec.implemented,
        }
        for spec in specs_for(map_id)
    ]


def metric_schema_hash(map_id: str) -> str:
    payload = json.dumps(metric_schema(map_id), ensure_ascii=False, sort_keys=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def _empty_status(outcome: str) -> MetricStatus:
    return MetricStatus.CENSORED if outcome == "censored" else MetricStatus.NOT_APPLICABLE


def _from_metric_values(
    values: dict[str, MetricValue], outcome: str
) -> dict[str, dict[str, Any]]:
    projected: dict[str, dict[str, Any]] = {}
    for metric_id, value in values.items():
        projected[metric_id] = {
            "status": value.status.value,
            "value": value.value,
            "denominator": value.denominator,
            "note": value.note,
        }
    return projected


def _from_raw(
    map_id: str, raw: dict[str, Any], outcome: str
) -> dict[str, dict[str, Any]]:
    missing = _empty_status(outcome)
    projected: dict[str, dict[str, Any]] = {}
    registered = {spec.metric_id for spec in specs_for(map_id)}
    unknown = set(raw) - registered
    if unknown:  # pragma: no cover - guarded by check_v8_map.py
        raise ValueError(f"{map_id} returned unregistered metrics: {sorted(unknown)}")
    for metric_id in sorted(registered):
        value = raw.get(metric_id)
        if isinstance(value, dict):
            numerator = value.get("numerator")
            denominator = value.get("denominator")
            if (
                not isinstance(numerator, (int, float))
                or not isinstance(denominator, int)
                or isinstance(numerator, bool)
            ):
                projected[metric_id] = {
                    "status": MetricStatus.INVALID_TRACE.value,
                    "value": None,
                    "denominator": None,
                    "note": "比例指标形状非法。",
                }
            elif denominator <= 0:
                projected[metric_id] = {
                    "status": MetricStatus.NOT_APPLICABLE.value,
                    "value": None,
                    "denominator": 0,
                    "note": "分母为 0，按预登记规则记为 N/A。",
                }
            else:
                projected[metric_id] = {
                    "status": MetricStatus.VALID.value,
                    "value": round(float(numerator) / denominator, 6),
                    "denominator": denominator,
                    "note": None,
                }
        elif value is None:
            projected[metric_id] = {
                "status": missing.value,
                "value": None,
                "denominator": None,
                "note": "地图未给出该局可计算值。",
            }
        elif isinstance(value, bool):
            projected[metric_id] = {
                "status": MetricStatus.VALID.value,
                "value": int(value),
                "denominator": None,
                "note": None,
            }
        elif isinstance(value, (int, float, str)):
            projected[metric_id] = {
                "status": MetricStatus.VALID.value,
                "value": value,
                "denominator": None,
                "note": None,
            }
        else:
            projected[metric_id] = {
                "status": MetricStatus.INVALID_TRACE.value,
                "value": None,
                "denominator": None,
                "note": f"指标类型非法：{type(value).__name__}",
            }
    return projected


def project_metrics(environment: Any, outcome: str) -> dict[str, dict[str, Any]]:
    map_id = str(environment.map_id)
    metric_values = getattr(environment, "metric_values", None)
    if callable(metric_values):
        return _from_metric_values(metric_values(), outcome)
    return _from_raw(map_id, environment.metrics(), outcome)


def summarize(projected: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {status.value: 0 for status in MetricStatus}
    for value in projected.values():
        counts[value["status"]] = counts.get(value["status"], 0) + 1
    return counts


__all__ = [
    "metric_schema",
    "metric_schema_hash",
    "project_metrics",
    "summarize",
]
