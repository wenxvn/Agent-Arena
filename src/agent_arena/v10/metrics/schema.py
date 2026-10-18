"""V10 指标 schema：五态取值、指标规格与版本哈希。

``metric_schema_version = "v10"``。V10 指标与 V7/V8 的旧值并列保存，不覆盖、
不跨版本求均值。五态优先级（高→低）：

1. ``INVALID_TRACE``：轨迹本身不可解析或与环境回放不一致；
2. ``UNAVAILABLE``：本该有的事件来源缺失（例如外部 judge 丢失）；
3. ``NOT_APPLICABLE``：真分母为 0，即该指标定义的事件从未发生且不可能发生
   （例如从未提交答案时的召回准确率）；
4. ``CENSORED``：事件在预算截尾时尚未发生，但若继续运行仍可能发生；
5. ``VALID``：可计算。

部分进度类指标（例如阶段完成度）在截尾时仍然 ``VALID``；不得把所有 ``None``
机械地改成 ``CENSORED``。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any

METRIC_SCHEMA_VERSION = "v10"


class MState(StrEnum):
    VALID = "VALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CENSORED = "CENSORED"
    INVALID_TRACE = "INVALID_TRACE"
    UNAVAILABLE = "UNAVAILABLE"


STATE_PRIORITY: tuple[MState, ...] = (
    MState.INVALID_TRACE,
    MState.UNAVAILABLE,
    MState.NOT_APPLICABLE,
    MState.CENSORED,
    MState.VALID,
)


@dataclass(frozen=True)
class MetricSpec:
    """一条 V10 指标的版本化定义。"""

    metric_id: str
    role: str  # primary / secondary / guardrail / diagnostic
    direction: str  # higher / lower / none
    formula: str
    denominator: str
    zero_denominator: str = "NOT_APPLICABLE"
    censored_rule: str = "部分进度保持 VALID；未发生的终点事件为 CENSORED"
    unit: str = "ratio"
    valid_range: tuple[float, float] = (0.0, 1.0)
    event_source: str = "environment judge counters"
    comparable_scope: str = "同一地图、同一 rule_hash"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["valid_range"] = list(self.valid_range)
        return payload


@dataclass(frozen=True)
class MValue:
    state: MState
    value: float | int | None = None
    numerator: float | int | None = None
    denominator: float | int | None = None
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"state": self.state.value, "value": self.value}
        if self.numerator is not None:
            payload["numerator"] = self.numerator
        if self.denominator is not None:
            payload["denominator"] = self.denominator
        if self.note:
            payload["note"] = self.note
        if self.extra:
            payload["extra"] = self.extra
        return payload


def valid(value: float | int, *, note: str = "") -> MValue:
    return MValue(MState.VALID, value, note=note)


def ratio(numerator: float | int, denominator: float | int, *, note: str = "") -> MValue:
    if denominator == 0:
        return MValue(MState.NOT_APPLICABLE, None, numerator, denominator, note or "分母为 0")
    return MValue(
        MState.VALID,
        round(float(numerator) / float(denominator), 6),
        numerator,
        denominator,
        note,
    )


def not_applicable(note: str) -> MValue:
    return MValue(MState.NOT_APPLICABLE, None, note=note)


def censored(note: str) -> MValue:
    return MValue(MState.CENSORED, None, note=note)


def unavailable(note: str) -> MValue:
    return MValue(MState.UNAVAILABLE, None, note=note)


def specs_hash(specs: tuple[MetricSpec, ...]) -> str:
    payload = json.dumps(
        {
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "specs": [spec.as_dict() for spec in sorted(specs, key=lambda item: item.metric_id)],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def check_range(spec: MetricSpec, value: MValue) -> bool:
    if value.state is not MState.VALID or value.value is None:
        return True
    low, high = spec.valid_range
    return low <= float(value.value) <= high


__all__ = [
    "METRIC_SCHEMA_VERSION",
    "MState",
    "MValue",
    "MetricSpec",
    "STATE_PRIORITY",
    "censored",
    "check_range",
    "not_applicable",
    "ratio",
    "specs_hash",
    "unavailable",
    "valid",
]
