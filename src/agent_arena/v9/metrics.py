"""V9 指标投影修正层（只读重算，不改 V8 文件）。

V7/V8 登记的 censor 规则是“预算/provider 截尾 → CENSORED，并保留原因码”，
但 V8 的 ``metrics._empty_status`` 只把 ``censored``（环境 horizon）当作截尾，
``decision_budget_reached`` 被投影成 ``NOT_APPLICABLE``。V9 在这里按登记规则
重新投影，并对 V8 的 90 局做 post-hoc 重算，旧值原样保留以便对照。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.v7.metrics.registry import specs_for
from agent_arena.v7.metrics.schema import MetricStatus
from agent_arena.v8.metrics import metric_schema_hash
from agent_arena.v9.audit import REPO_ROOT, V9_ROOT, official_rows

_CENSORING_OUTCOMES = {
    "censored",
    "decision_budget_reached",
    "episode_timeout",
    "schema_fault_limit",
    "provider_error",
    "provider_error_limit",
    "budget_closed",
    "unknown_provider_spend",
}


def empty_status(outcome: str) -> MetricStatus:
    return MetricStatus.CENSORED if outcome in _CENSORING_OUTCOMES else MetricStatus.NOT_APPLICABLE


def _from_raw(map_id: str, raw: dict[str, Any], outcome: str) -> dict[str, dict[str, Any]]:
    missing = empty_status(outcome)
    projected: dict[str, dict[str, Any]] = {}
    registered = {spec.metric_id for spec in specs_for(map_id)}
    unknown = set(raw) - registered
    if unknown:
        raise ValueError(f"{map_id} 返回未登记指标：{sorted(unknown)}")
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
            # 与 V8 的唯一差异：预算截尾也记 CENSORED，而不是 N/A。
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
        # V4 适配图已经返回 MetricStatus；只把 N/A 在截尾结局下改写为 CENSORED。
        projected: dict[str, dict[str, Any]] = {}
        for metric_id, value in metric_values().items():
            status = value.status.value
            if status == MetricStatus.NOT_APPLICABLE.value and outcome in _CENSORING_OUTCOMES:
                status = MetricStatus.CENSORED.value
            projected[metric_id] = {
                "status": status,
                "value": value.value,
                "denominator": value.denominator,
                "note": value.note,
            }
        return projected
    return _from_raw(map_id, environment.metrics(), outcome)


def rescore_v8() -> dict[str, Any]:
    rows = official_rows()
    output = V9_ROOT / "rescore"
    output.mkdir(parents=True, exist_ok=True)
    per_map: dict[str, Any] = {}
    changes_by_metric: dict[str, int] = {}
    for row in rows:
        judge = json.loads(Path(row.judge_metrics_path).read_text(encoding="utf-8"))
        old = json.loads(Path(row.v8_metrics_path).read_text(encoding="utf-8"))
        new_metrics = _from_raw(row.map_id, judge.get("metrics") or {}, row.status)
        per_map.setdefault(row.map_id, {"runs": []})["runs"].append(
            {
                "run_id": row.run_id,
                "status": row.status,
                "success": row.success,
                "metric_schema_hash": metric_schema_hash(row.map_id),
                "old": old.get("metrics"),
                "new": new_metrics,
                "changed": {
                    metric_id: {
                        "old": (old.get("metrics") or {}).get(metric_id, {}).get("status"),
                        "new": value["status"],
                    }
                    for metric_id, value in new_metrics.items()
                    if (old.get("metrics") or {}).get(metric_id, {}).get("status")
                    != value["status"]
                },
            }
        )
        for metric_id, value in new_metrics.items():
            old_status = (old.get("metrics") or {}).get(metric_id, {}).get("status")
            if old_status != value["status"]:
                key = f"{metric_id}:{old_status}->{value['status']}"
                changes_by_metric[key] = changes_by_metric.get(key, 0) + 1
    for map_id, payload in per_map.items():
        path = output / f"{map_id}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    summary = {
        "runs": len(rows),
        "maps": len(per_map),
        "changed_status_count": sum(changes_by_metric.values()),
        "changes_by_metric": dict(sorted(changes_by_metric.items())),
        "note": (
            "只把预算/超时截尾下的 None 指标从 not_applicable 改为 censored；"
            "有效值与分母不变。"
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    summary = rescore_v8()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"output={REPO_ROOT / 'runs' / 'v9' / 'rescore'}")


if __name__ == "__main__":
    main()
