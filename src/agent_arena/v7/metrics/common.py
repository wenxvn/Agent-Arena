"""Map-agnostic derived quantities shared by V7 metric modules.

Everything here is deliberately small and explicit. Sharing arithmetic helpers
is allowed; sharing a single score formula across maps is not.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

from agent_arena.v7.metrics.schema import (
    MetricStatus,
    MetricValue,
    TraceEvent,
    TraceRecord,
)

# Results that mean "the environment refused the submitted action and no rule
# state advanced". Operational rule outcomes (TRACK_CLOSED, ACCUSATION_NOT_
# SUSTAINED, LEAK_SEALED, ...) are *not* rejection: they are legal consequences.
REJECTED_RESULTS = frozenset(
    {
        "ACTION_NOT_AVAILABLE",
        "ALREADY_TERMINAL",
        "CASEBOOK_ENTRY_NOT_FOUND",
        "CASEBOOK_FULL",
        "COURTROOM_REQUIRED",
        "EVIDENCE_NOT_AVAILABLE",
        "MEMORY_CAPACITY_EXCEEDED",
        "MEMORY_DISABLED",
        "MEMORY_FACT_NOT_OBSERVED",
        "NO_PENDING_ROUTE",
        "NO_SEALANT",
        "NO_SPARE_AVAILABLE",
        "NPC_NOT_HERE",
        "TICK_MISMATCH",
        "TRAIN_LOCKED",
        "UNKNOWN_TRAIN",
    }
)

CENSORED_OUTCOMES = frozenset(
    {
        "censored",
        "decision_limit",
        "episode_timeout",
        "global_provider_timeout",
        "input_context_limit",
        "provider_error",
        "provider_error_limit",
        "unknown_provider_spend",
    }
)

CENSORED_REASONS = frozenset({"ACTION_LIMIT_REACHED", "STEP_LIMIT_REACHED"})


def is_rejected_result(result: str) -> bool:
    """True when the result is an explicit action refusal, not a rule outcome."""

    return result.startswith("INVALID") or result in REJECTED_RESULTS


def ratio(
    metric_id: str,
    numerator: float,
    denominator: int,
    *,
    note: str | None = None,
) -> MetricValue:
    """A bounded rate with an explicit zero-denominator rule (N/A, never 0)."""

    if denominator <= 0:
        return MetricValue.not_applicable(metric_id, "分母为 0，按预登记规则记为 N/A。")
    return MetricValue(
        metric_id=metric_id,
        value=round(numerator / denominator, 6),
        status=MetricStatus.VALID,
        denominator=denominator,
        note=note,
    )


def counted(metric_id: str, value: int, *, note: str | None = None) -> MetricValue:
    return MetricValue(metric_id=metric_id, value=value, status=MetricStatus.VALID, note=note)


def scalar(
    metric_id: str,
    value: float | int | str,
    *,
    unit_note: str | None = None,
) -> MetricValue:
    return MetricValue(metric_id=metric_id, value=value, status=MetricStatus.VALID, note=unit_note)


def legal_action_rate(record: TraceRecord, metric_id: str) -> MetricValue:
    """Accepted actions / submitted decisions (prefix actions excluded)."""

    decisions = record.decided_events
    rejected = sum(
        1 for event in decisions if event.invalid_schema or is_rejected_result(event.result)
    )
    return ratio(metric_id, len(decisions) - rejected, len(decisions))


def judge_status(record: TraceRecord) -> str | None:
    value = (record.judge or {}).get("status")
    return value if isinstance(value, str) else None


def episode_is_censored(record: TraceRecord) -> bool:
    """A censored episode was stopped by budget/provider, not by a map predicate."""

    status = judge_status(record)
    if status is not None:
        return status in CENSORED_OUTCOMES
    if not record.is_terminal:
        return True
    return record.terminal_reason in CENSORED_REASONS


def censored(record: TraceRecord, metric_id: str) -> MetricValue | None:
    """Return a CENSORED value when the episode never reached a map terminal."""

    if episode_is_censored(record):
        reason = record.terminal_reason or judge_status(record)
        return MetricValue.censored(
            metric_id,
            f"episode 在预算或 provider 边界结束（{reason}）。",
        )
    return None


def entropy_bits(weights: Sequence[float]) -> float:
    """Shannon entropy in bits; zero-weight candidates are ignored."""

    total = sum(weights)
    if total <= 0:
        return 0.0
    value = 0.0
    for weight in weights:
        probability = weight / total
        if probability > 0:
            value -= probability * math.log2(probability)
    return value


def events_with_tool(record: TraceRecord, *tools: str) -> tuple[TraceEvent, ...]:
    wanted = set(tools)
    return tuple(event for event in record.events if event.tool in wanted)


def count_results(record: TraceRecord, results: Iterable[str]) -> int:
    wanted = set(results)
    return sum(1 for event in record.events if event.result in wanted)


def first_tick_at(record: TraceRecord, predicate: Any) -> int | None:
    """First ``tick_after`` whose public observation satisfies ``predicate``."""

    for event in record.events:
        if predicate(event.observation_after):
            return event.tick_after
    return None


def peak_numeric(record: TraceRecord, field: str) -> float | None:
    values: list[float] = []
    for event in record.events:
        value = event.observation_after.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return max(values) if values else None


def final_numeric(record: TraceRecord, field: str) -> float | None:
    value = record.final_observation.get(field)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def sequence_of(record: TraceRecord, field: str) -> list[Any]:
    value = record.final_observation.get(field)
    return list(value) if isinstance(value, (list, tuple)) else []


__all__ = [
    "CENSORED_OUTCOMES",
    "CENSORED_REASONS",
    "REJECTED_RESULTS",
    "censored",
    "count_results",
    "counted",
    "entropy_bits",
    "episode_is_censored",
    "events_with_tool",
    "final_numeric",
    "first_tick_at",
    "is_rejected_result",
    "judge_status",
    "legal_action_rate",
    "peak_numeric",
    "ratio",
    "scalar",
    "sequence_of",
]
