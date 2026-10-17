"""Strict, offline contracts for V7 metrics and normalized episode events.

The V7 layer consumes already-written episode artefacts. It never mutates the
V4/V5/V6 trace writer and it never exposes ``private_state_hash`` or judge
values to an Agent prompt, tool response, or public report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class MetricStatus(StrEnum):
    """Whether a metric value may be interpreted at all."""

    VALID = "valid"
    NOT_APPLICABLE = "not_applicable"
    CENSORED = "censored"
    UNAVAILABLE = "unavailable"
    INVALID_TRACE = "invalid_trace"


class MetricKind(StrEnum):
    """Four non-interchangeable metric families (V7 outline §2.1)."""

    OUTCOME = "outcome"
    PRIMARY = "primary"
    GUARDRAIL = "guardrail"
    DIAGNOSTIC = "diagnostic"


class Direction(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    DESCRIPTIVE = "descriptive"


class TraceFormatError(ValueError):
    """The supplied rows cannot be interpreted as one V7 episode trace."""


def _derived_valid_range(unit: str, formula: str) -> str:
    """Return the pre-registered admissible range for a metric value.

    Most V7 units already imply a range. The few signed or rule-bounded
    quantities are handled explicitly so a missing ``valid_range`` can never be
    misread as an unbounded or fabricated zero-valued metric.
    """

    if unit == "0/1":
        return "0 或 1"
    if unit == "比例 0..1":
        return "0..1"
    if unit == "水位单位":
        return "0..7.5（>7.0 即失败）"
    if unit == "水位·tick":
        return ">= 0（超额水位累计）"
    if unit in {"温度", "温度单位", "温度·tick"}:
        if "max(0" in formula or "exceed" in formula.lower() or "超额" in formula:
            return ">= 0（相对安全上限的超限量）"
        return "由该图规则温度上下限约束；报告原值"
    if unit in {"损失单位", "库存单位"}:
        return "可正可负（损失差 / 安全库存差）"
    if "queries_used - minimum_queries" in formula:
        return ">= 0（不得少于该实例最小问询数）"
    if "committed_ticks - BFS_optimum" in formula:
        return ">= 0（成功局不应短于 BFS 最优）"
    if "movement_steps - BFS_optimal_moves" in formula:
        return ">= 0（成功局不应短于 BFS 最优）"
    if "actual_remaining_cost / shortest_feasible_cost" in formula:
        return ">= 1（改线后剩余成本不得低于最短可行成本）"
    if unit in {"任务/燃料", "资源/人", "能耗/人", "补给/发现"}:
        return ">= 0（分母为 0 时按该指标缺失规则处理）"
    if unit == "个子系统":
        return "0..该图登记子系统数"
    if unit in {"燃料单位", "资源单位 + tick", "风险·tick", "节点·tick"}:
        return ">= 0"
    return ">= 0"


class MetricSpec(BaseModel):
    """One pre-registered per-map metric definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    map_id: str
    kind: MetricKind
    construct_name: str
    unit: str
    direction: Direction
    formula: str
    denominator: str
    window: str
    applicability: str
    valid_range: str = ""
    missing_rule: str
    censor_rule: str
    source_events: tuple[str, ...]
    adversarial_note: str
    implemented: bool
    doc_ref: str

    @model_validator(mode="before")
    @classmethod
    def _fill_valid_range(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("valid_range"):
            data = dict(data)
            data["valid_range"] = _derived_valid_range(
                str(data.get("unit", "")), str(data.get("formula", ""))
            )
        return data


class MetricValue(BaseModel):
    """One computed metric value with an explicit availability status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_id: str
    value: float | int | str | None
    status: MetricStatus
    denominator: int | None = None
    note: str | None = None

    @classmethod
    def unavailable(cls, metric_id: str, note: str) -> MetricValue:
        return cls(metric_id=metric_id, value=None, status=MetricStatus.UNAVAILABLE, note=note)

    @classmethod
    def not_applicable(cls, metric_id: str, note: str) -> MetricValue:
        return cls(metric_id=metric_id, value=None, status=MetricStatus.NOT_APPLICABLE, note=note)

    @classmethod
    def censored(cls, metric_id: str, note: str) -> MetricValue:
        return cls(metric_id=metric_id, value=None, status=MetricStatus.CENSORED, note=note)

    @classmethod
    def invalid_trace(cls, metric_id: str, note: str) -> MetricValue:
        return cls(metric_id=metric_id, value=None, status=MetricStatus.INVALID_TRACE, note=note)


@dataclass(frozen=True)
class TraceEvent:
    """One normalized V4/V6 step.

    ``observation_before``/``observation_after`` are the public observations as
    written by the existing runner. They are sufficient for every V7 metric;
    private state is read only from the optional offline judge artefact.
    """

    seq: int
    event_type: str
    tool: str | None
    action: dict[str, Any] | None
    result: str
    tick_before: int | None
    tick_after: int | None
    observation_before: dict[str, Any]
    observation_after: dict[str, Any]
    decision_index: int | None
    invalid_schema: bool


@dataclass(frozen=True)
class TraceRecord:
    """A parsed episode trace plus its optional offline judge artefact."""

    header: dict[str, Any]
    events: tuple[TraceEvent, ...]
    judge: dict[str, Any] | None
    source: str

    @property
    def map_id(self) -> str:
        value = self.header.get("map_id")
        if not isinstance(value, str):
            raise TraceFormatError("trace_header.map_id is missing.")
        return value

    @property
    def instance_id(self) -> str:
        value = self.header.get("instance_id")
        return value if isinstance(value, str) else ""

    @property
    def condition_id(self) -> str:
        value = self.header.get("condition_id")
        return value if isinstance(value, str) else ""

    @property
    def seed(self) -> int:
        value = self.header.get("seed")
        return value if isinstance(value, int) else 0

    @property
    def scenario_hash(self) -> str:
        value = self.header.get("scenario_hash")
        return value if isinstance(value, str) else ""

    @property
    def final_observation(self) -> dict[str, Any]:
        return self.events[-1].observation_after if self.events else {}

    @property
    def decided_events(self) -> tuple[TraceEvent, ...]:
        return tuple(event for event in self.events if event.event_type == "decision")

    @property
    def tool_events(self) -> tuple[TraceEvent, ...]:
        return tuple(event for event in self.events if event.tool is not None)

    @property
    def terminal_reason(self) -> str | None:
        reason = self.final_observation.get("terminal_reason")
        return reason if isinstance(reason, str) else None

    @property
    def is_terminal(self) -> bool:
        return bool(self.final_observation.get("terminal", False))

    @property
    def judge_metrics(self) -> dict[str, Any]:
        metrics = (self.judge or {}).get("metrics")
        return metrics if isinstance(metrics, dict) else {}


_TICK_KEYS = ("tick", "current_tick", "movement_steps")
_ACCEPTED_EVENT_TYPES = {"decision", "prefix_action"}


def observation_tick(observation: dict[str, Any]) -> int | None:
    """Return the map-specific logical time exposed by a public observation."""

    for key in _TICK_KEYS:
        value = observation.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TraceFormatError(f"{field} must be a JSON object.")
    return value


def parse_trace_rows(
    rows: list[dict[str, Any]],
    *,
    judge: dict[str, Any] | None = None,
    source: str = "<memory>",
) -> TraceRecord:
    """Normalize V6 ``agent_trace.jsonl`` rows into a :class:`TraceRecord`."""

    if not rows:
        raise TraceFormatError("The trace is empty.")
    header = dict(rows[0])
    if header.get("event") != "trace_header":
        raise TraceFormatError("The first row must be a trace_header event.")
    for field in ("map_id", "instance_id", "scenario_hash"):
        if not isinstance(header.get(field), str) or not header[field]:
            raise TraceFormatError(f"trace_header.{field} is missing.")
    if not isinstance(header.get("seed"), int):
        raise TraceFormatError("trace_header.seed is missing.")

    events: list[TraceEvent] = []
    for index, row in enumerate(rows[1:], start=1):
        event_type = row.get("event", "decision")
        if event_type not in _ACCEPTED_EVENT_TYPES:
            raise TraceFormatError(f"row {index} has an unsupported event type: {event_type}")
        result = row.get("result")
        if not isinstance(result, str):
            raise TraceFormatError(f"row {index} has no string result.")
        before = _require_mapping(row.get("observation_before"), f"row {index} observation_before")
        after = _require_mapping(row.get("observation_after"), f"row {index} observation_after")
        action_raw = row.get("action")
        action = dict(action_raw) if isinstance(action_raw, dict) else None
        tool = action.get("tool") if action is not None else None
        if tool is not None and not isinstance(tool, str):
            raise TraceFormatError(f"row {index} action.tool is not a string.")
        decision_index = row.get("decision_index") if event_type == "decision" else None
        if event_type == "decision" and not isinstance(decision_index, int):
            raise TraceFormatError(f"row {index} decision_index is missing.")
        events.append(
            TraceEvent(
                seq=index,
                event_type=str(event_type),
                tool=tool if isinstance(tool, str) else None,
                action=action,
                result=result,
                tick_before=observation_tick(before),
                tick_after=observation_tick(after),
                observation_before=before,
                observation_after=after,
                decision_index=decision_index if isinstance(decision_index, int) else None,
                invalid_schema=row.get("invalid_output_reason") is not None,
            )
        )
    return TraceRecord(
        header=header,
        events=tuple(events),
        judge=judge,
        source=source,
    )


def load_trace(
    trace_path: Path,
    *,
    judge_path: Path | None = None,
) -> TraceRecord:
    """Load one V6 episode trace and, optionally, its offline judge metrics."""

    try:
        rows = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceFormatError(f"Cannot read trace: {trace_path}") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise TraceFormatError("Each trace line must be a JSON object.")
    judge: dict[str, Any] | None = None
    if judge_path is not None:
        try:
            loaded = json.loads(judge_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TraceFormatError(f"Cannot read judge metrics: {judge_path}") from exc
        judge = _require_mapping(loaded, "judge_metrics")
    return parse_trace_rows(rows, judge=judge, source=str(trace_path))


__all__ = [
    "Direction",
    "MetricKind",
    "MetricSpec",
    "MetricStatus",
    "MetricValue",
    "TraceEvent",
    "TraceFormatError",
    "TraceRecord",
    "load_trace",
    "observation_tick",
    "parse_trace_rows",
]
