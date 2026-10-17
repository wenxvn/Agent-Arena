"""V9 主指标独立复算框架。

约束：
- 只能读取 Trace 行、公开 Observation 与 judge_state（离线核对可用 judge 真值）；
- **不得调用** ``environment.metrics()``、V7 extractor 或 V8 ``project_metrics``；
- 每张图至少 2 条 Trace（R0 + 首条非 R0），每条至少 1 个主指标 + 1 个安全/护栏指标；
- 结果写入 ``runs/v9/metric_checks/``，并汇总到 ``docs/v9/metric-independent-check.md``。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_arena.v9.audit import V9_ROOT, official_rows

CheckFn = Callable[["EvidenceRun"], Any]


@dataclass
class EvidenceRun:
    map_id: str
    run_id: str
    replicate_id: int
    status: str
    success: bool
    trace: list[dict[str, Any]]
    judge_state: dict[str, Any]
    reported: dict[str, Any]

    @property
    def decisions(self) -> list[dict[str, Any]]:
        return [row for row in self.trace if row.get("event") == "decision"]

    @property
    def initial(self) -> dict[str, Any]:
        decisions = self.decisions
        return decisions[0]["observation_before"] if decisions else {}

    @property
    def final(self) -> dict[str, Any]:
        decisions = self.decisions
        return decisions[-1]["observation_after"] if decisions else {}

    def results(self) -> list[str]:
        return [str(row.get("result")) for row in self.decisions]

    def observations(self) -> list[dict[str, Any]]:
        return [row.get("observation_after") or {} for row in self.decisions]


@dataclass
class Check:
    metric_id: str
    fn: CheckFn
    note: str
    tolerance: float = 1e-6
    kind: str = "primary"


@dataclass
class CheckOutcome:
    map_id: str
    run_id: str
    metric_id: str
    kind: str
    reported_status: str
    reported_value: Any
    recomputed: Any
    match: bool | None
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "run_id": self.run_id,
            "metric_id": self.metric_id,
            "kind": self.kind,
            "reported_status": self.reported_status,
            "reported_value": self.reported_value,
            "recomputed": self.recomputed,
            "match": self.match,
            "note": self.note,
        }


@dataclass
class CheckReport:
    outcomes: list[CheckOutcome] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        total = len(self.outcomes)
        matched = sum(1 for item in self.outcomes if item.match is True)
        mismatched = [item.as_dict() for item in self.outcomes if item.match is False]
        not_computable = [item.as_dict() for item in self.outcomes if item.match is None]
        return {
            "checks": total,
            "matched": matched,
            "mismatched": len(mismatched),
            "not_computable": len(not_computable),
            "mismatch_detail": mismatched,
            "not_computable_detail": not_computable,
            "maps": len({item.map_id for item in self.outcomes}),
            "runs": len({item.run_id for item in self.outcomes}),
        }


def evidence_runs(map_id: str) -> list[EvidenceRun]:
    runs: list[EvidenceRun] = []
    rows = [row for row in official_rows() if row.map_id == map_id]
    selected = [row for row in rows if row.replicate_id == 0]
    others = [row for row in rows if row.replicate_id != 0]
    others.sort(key=lambda row: (not row.success, row.replicate_id))
    selected.extend(others[:1])
    for row in selected:
        trace = [
            json.loads(line)
            for line in Path(row.agent_trace_path)
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        judge = json.loads(Path(row.judge_metrics_path).read_text(encoding="utf-8"))
        metrics = json.loads(Path(row.v8_metrics_path).read_text(encoding="utf-8"))
        runs.append(
            EvidenceRun(
                map_id=map_id,
                run_id=row.run_id,
                replicate_id=row.replicate_id,
                status=row.status,
                success=row.success,
                trace=trace,
                judge_state=judge.get("judge_state") or {},
                reported={
                    metric_id: value
                    for metric_id, value in (metrics.get("metrics") or {}).items()
                },
            )
        )
    return runs


def _matches(expected: Any, actual: Any, tolerance: float) -> bool | None:
    if expected is None or actual is None:
        return None
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) <= tolerance
    return bool(expected == actual)


def run_map_checks(map_id: str, checks: list[Check]) -> list[CheckOutcome]:
    outcomes: list[CheckOutcome] = []
    for run in evidence_runs(map_id):
        for check in checks:
            reported = run.reported.get(check.metric_id) or {}
            status = reported.get("status", "missing")
            value = reported.get("value")
            try:
                recomputed = check.fn(run)
            except Exception as exc:  # noqa: BLE001 - recorded as not computable
                outcomes.append(
                    CheckOutcome(
                        map_id=map_id,
                        run_id=run.run_id,
                        metric_id=check.metric_id,
                        kind=check.kind,
                        reported_status=status,
                        reported_value=value,
                        recomputed=None,
                        match=None,
                        note=f"{check.note} | 复算异常：{type(exc).__name__}: {exc}",
                    )
                )
                continue
            match: bool | None
            if status in {"not_applicable", "censored", "unavailable"} and recomputed is None:
                match = True
            else:
                match = _matches(value, recomputed, check.tolerance)
            outcomes.append(
                CheckOutcome(
                    map_id=map_id,
                    run_id=run.run_id,
                    metric_id=check.metric_id,
                    kind=check.kind,
                    reported_status=status,
                    reported_value=value,
                    recomputed=recomputed,
                    match=match,
                    note=check.note,
                )
            )
    return outcomes


def run_all() -> dict[str, Any]:
    from agent_arena.v9.metric_checks import registry

    report = CheckReport()
    per_map: dict[str, Any] = {}
    for map_id, checks in registry().items():
        outcomes = run_map_checks(map_id, checks)
        report.outcomes.extend(outcomes)
        per_map[map_id] = {
            "checks": [item.as_dict() for item in outcomes],
        }
    output = V9_ROOT / "metric_checks"
    output.mkdir(parents=True, exist_ok=True)
    for map_id, payload in per_map.items():
        (output / f"{map_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    summary = report.summary()
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


__all__ = [
    "Check",
    "CheckOutcome",
    "CheckReport",
    "EvidenceRun",
    "evidence_runs",
    "run_all",
    "run_map_checks",
]
