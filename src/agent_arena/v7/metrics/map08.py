"""V7 metrics for MAP-08, active leak diagnosis with a single sealant."""

from __future__ import annotations

import re
from typing import Any

from agent_arena.v7.metrics.common import (
    counted,
    entropy_bits,
    episode_is_censored,
    legal_action_rate,
    peak_numeric,
    ratio,
    scalar,
)
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceRecord,
)

MAP_ID = "MAP-08"
DOC_REF = "docs/v7/maps/MAP-08.md"
_READING = re.compile(r"([A-Za-z0-9_]+)\s*读数为\s*([A-Za-z0-9_]+)")


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map08.diagnosis_accuracy",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="密封剂是否用在真实漏点上（唯一、不可重试的结论性证据）",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if repair_leak(target)==true_leak else 0",
        denominator="提交过 repair_leak 的 episode；未提交则 N/A",
        window="整局终局",
        applicability="所有 MAP-08 实例与 seed",
        missing_rule="无 repair 动作 → N/A；无离线真漏 → UNAVAILABLE",
        censor_rule="episode 因 step-limit 截尾 → CENSORED（未观察到结论性修复）",
        source_events=("interact:repair_leak", "terminal LEAK_SEALED/SEALANT_MISUSED"),
        adversarial_note="不能把“修对位置”与“修完之前淹水”混为一谈；只认终局密封结果。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.candidate_reduction",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="公开测试签名把候选漏点集合缩小的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="(N_initial - N_final) / N_initial",
        denominator="初始公开候选数 N_initial",
        window="从首个测试到最终测试；重复测试不改变分母",
        applicability="所有无噪声签名实例",
        missing_rule="known_test_semantics 无法解析 → UNAVAILABLE；无测试 → 0（合法）",
        censor_rule="过程量不因终局失败而删除，只标注同局 outcome",
        source_events=(
            "observation.published_candidate_set",
            "observation.known_test_semantics",
            "test_results",
        ),
        adversarial_note="不能用私有真值直接缩小候选；只能复演公开签名表。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.information_gain_bits",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="每次合法压力测试带来的期望候选熵下降",
        unit="bit",
        direction=Direction.HIGHER_IS_BETTER,
        formula="Σ_t [H_t - H_{t+1}], H=log2|consistent candidates|（本实例等先验）",
        denominator="实际执行的合法测试数",
        window="逐测试事件",
        applicability="签名确定、等先验的 MAP-08 实例",
        missing_rule="签名表不可解析 → UNAVAILABLE；0 次测试 → 0 bit",
        censor_rule="按已发生事件计算，不因截尾删除",
        source_events=("interact:pressure_test_X/Y", "published signatures"),
        adversarial_note="重复测试的信息增益必须为 0；不能把访问次数当信息量。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.peak_core_water",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="诊断期间的核心水位峰值（安全裕量）",
        unit="水位单位",
        direction=Direction.LOWER_IS_BETTER,
        formula="max_t(current_core_water_t)",
        denominator="episode",
        window="整局公开读数",
        applicability="所有 MAP-08 实例（上限 7.0）",
        missing_rule="无任何观测 → UNAVAILABLE",
        censor_rule="截尾时按已观察值计算并标注 CENSORED",
        source_events=("observation.current_core_water",),
        adversarial_note="水位恰为 7.0 合法；不能把 7.0 判成越界。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.wrong_repair",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="错误封堵次数（一次性密封剂被误用）",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="1 if terminal_reason==SEALANT_MISUSED else 0",
        denominator="提交过 repair 的 episode",
        window="终局",
        applicability="所有 sealant_count=1 的实例",
        missing_rule="未提交 repair → N/A",
        censor_rule="截尾且未修复 → CENSORED",
        source_events=("interact:repair_leak result",),
        adversarial_note="错误维修不能通过后续动作追回；不能因最终淹水而改写为 0。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.tests_run",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="单位诊断成本（测试次数）",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(legal pressure_test_X/Y)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="无 → 0",
        censor_rule="按已发生事件计算",
        source_events=("interact:pressure_test_*",),
        adversarial_note="测试次数少不代表诊断更准；必须与 diagnosis_accuracy 并列。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map08.legal_action_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="提交动作中被规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="accepted decisions / submitted decisions",
        denominator="模型提交的 decision 数；prefix 不计",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次决策 → N/A",
        censor_rule="按已提交决策计算",
        source_events=("decision.result",),
        adversarial_note="接口合法率高不等于诊断能力；不能作为能力代理。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _public_signatures(observation: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Parse the public signature prose into ``site -> station -> reading``."""

    raw = observation.get("known_test_semantics")
    if not isinstance(raw, dict):
        return {}
    table: dict[str, dict[str, str]] = {}
    for station, text in raw.items():
        if not isinstance(station, str) or not isinstance(text, str):
            continue
        for site, reading in _READING.findall(text):
            table.setdefault(site, {})[station] = reading
    return table


def _true_leak(record: TraceRecord) -> str | None:
    judge_state = (record.judge or {}).get("judge_state")
    if isinstance(judge_state, dict):
        value = judge_state.get("true_leak")
        if isinstance(value, str):
            return value
    return None


def _initial_observation(record: TraceRecord) -> dict[str, Any]:
    return record.events[0].observation_before if record.events else record.final_observation


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    result: dict[str, MetricValue] = {}
    initial = _initial_observation(record)
    table = _public_signatures(initial)

    def station_readings(station: str) -> set[str]:
        return {row[station] for row in table.values() if isinstance(row.get(station), str)}

    tests = [
        event
        for event in record.events
        if event.tool == "interact"
        and isinstance(event.action, dict)
        and str(event.action.get("operation", "")).startswith("pressure_test_")
        and event.result.startswith("pulse_")
    ]
    repairs = [
        event
        for event in record.events
        if event.tool == "interact"
        and isinstance(event.action, dict)
        and event.action.get("operation") == "repair_leak"
    ]

    result["map08.tests_run"] = counted("map08.tests_run", len(tests))

    candidates_raw = initial.get("published_candidate_set")
    candidates = (
        [str(item) for item in candidates_raw]
        if isinstance(candidates_raw, (list, tuple)) and candidates_raw
        else sorted(table)
    )
    if not table or not candidates:
        result["map08.candidate_reduction"] = MetricValue.unavailable(
            "map08.candidate_reduction", "公开签名表或初始候选集缺失，无法复算候选缩小。"
        )
        result["map08.information_gain_bits"] = MetricValue.unavailable(
            "map08.information_gain_bits", "公开签名表缺失，无法复算信息增益。"
        )
    else:
        remaining = set(candidates)
        gain = 0.0
        for event in tests:
            assert isinstance(event.action, dict)
            operation = str(event.action.get("operation", ""))
            station = operation.removeprefix("pressure_test_")
            if not remaining or event.result not in station_readings(station):
                continue
            before = entropy_bits([1.0] * len(remaining))
            narrowed = {
                site for site in remaining if table.get(site, {}).get(station) == event.result
            }
            if not narrowed:
                continue
            after = entropy_bits([1.0] * len(narrowed))
            gain += before - after
            remaining = narrowed
        result["map08.candidate_reduction"] = ratio(
            "map08.candidate_reduction",
            len(candidates) - len(remaining),
            len(candidates),
        )
        result["map08.information_gain_bits"] = scalar(
            "map08.information_gain_bits", round(gain, 6), unit_note="bit"
        )

    truth = _true_leak(record)
    if repairs:
        repair = repairs[-1]
        target = repair.action.get("target_id") if isinstance(repair.action, dict) else None
        if truth is None:
            result["map08.diagnosis_accuracy"] = MetricValue.unavailable(
                "map08.diagnosis_accuracy", "缺少离线 judge_state.true_leak。"
            )
        else:
            result["map08.diagnosis_accuracy"] = counted(
                "map08.diagnosis_accuracy", int(target == truth)
            )
        result["map08.wrong_repair"] = counted(
            "map08.wrong_repair", int(repair.result == "SEALANT_MISUSED")
        )
    else:
        note = "本局没有提交 repair_leak，诊断结论未被观察到。"
        if episode_is_censored(record):
            result["map08.diagnosis_accuracy"] = MetricValue.censored(
                "map08.diagnosis_accuracy", note
            )
            result["map08.wrong_repair"] = MetricValue.censored("map08.wrong_repair", note)
        else:
            result["map08.diagnosis_accuracy"] = MetricValue.not_applicable(
                "map08.diagnosis_accuracy", note
            )
            result["map08.wrong_repair"] = MetricValue.not_applicable("map08.wrong_repair", note)

    peak = peak_numeric(record, "current_core_water")
    if peak is None:
        result["map08.peak_core_water"] = MetricValue.unavailable(
            "map08.peak_core_water", "trace 中没有公开水位读数。"
        )
    else:
        baseline = float(initial.get("current_core_water") or 1.0)
        status = MetricStatus.CENSORED if episode_is_censored(record) else MetricStatus.VALID
        result["map08.peak_core_water"] = MetricValue(
            metric_id="map08.peak_core_water",
            value=round(max(peak, baseline), 6),
            status=status,
        )

    result["map08.legal_action_rate"] = legal_action_rate(record, "map08.legal_action_rate")
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
