"""V7 metrics for MAP-26, diagnosis, feedback correction, and spare budget."""

from __future__ import annotations

from typing import Any

from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    legal_action_rate,
    ratio,
)
from agent_arena.v7.metrics.references import MAP26_FAULT_PART, MAP26_INITIAL_SPARES
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceEvent,
    TraceRecord,
)

MAP_ID = "MAP-26"
DOC_REF = "docs/v7/maps/MAP-26.md"
_FEEDBACK_PREFIXES = (
    "POWER_SELF_TEST_OK",
    "ANTENNA_SELF_TEST_OK",
    "SOFTWARE_SELF_TEST_OK",
    "REPLACEMENT_FEEDBACK_HIDDEN",
)


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map26.repair_success",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="通信是否在备件预算内真正恢复",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if final communication_restored else 0",
        denominator="episode",
        window="终局",
        applicability="所有 MAP-26 实例",
        missing_rule="无公开 communication_restored → UNAVAILABLE",
        censor_rule="step-limit 截尾 → CENSORED",
        source_events=("observation.communication_restored", "terminal"),
        adversarial_note="restart 成功但备件为 0 仍是失败；不能只看通信灯。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.recovery_latency",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="首次错误替换反馈后到首次有效策略调整的 tick 延迟",
        unit="tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="tick(first rollback/test/different-part replace) - tick(first wrong feedback)",
        denominator="至少发生一次错误替换的 episode",
        window="从首个错误反馈到之后首个有效调整",
        applicability="free_diagnosis 与三种 recovery 条件",
        missing_rule="没有错误替换 → N/A",
        censor_rule="至终局仍无有效调整 → CENSORED",
        source_events=("replace result", "rollback", "test"),
        adversarial_note="把同一错误部件再装一次不算调整；必须改变策略。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.repeat_error_rate",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="错误部件被重复安装的比例（未吸收反馈）",
        unit="比例 0..1",
        direction=Direction.LOWER_IS_BETTER,
        formula="replaces of an already-failed part / total wrong replacements",
        denominator="错误替换尝试数；0 则 N/A",
        window="整局",
        applicability="所有实例",
        missing_rule="无错误替换 → N/A",
        censor_rule="按已发生替换计算",
        source_events=("replace result",),
        adversarial_note="不能靠增加备件把重复错误稀释；分母固定为错误替换数。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.spares_remaining",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="终局仍可用的备件数（预算安全裕量）",
        unit="件",
        direction=Direction.HIGHER_IS_BETTER,
        formula="spare_units_at_B + len(carried_spare_units)",
        denominator="episode",
        window="终局",
        applicability="所有实例",
        missing_rule="公开字段与 judge 均缺失 → UNAVAILABLE",
        censor_rule="按已观察库存计算",
        source_events=("observation.spare_units_at_B", "observation.carried_spare_units"),
        adversarial_note="备件多不等于能力强；spare_rich 实例不能与标准预算直接比较成功率。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.diagnosis_accuracy",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="最终安装/替换的部件是否命中隐藏故障件",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if last replaced part == frozen fault_part else 0",
        denominator="提交过 replace 的 episode",
        window="终局",
        applicability="所有实例（离线裁判真值）",
        missing_rule="无 replace → N/A；无冻结真值 → UNAVAILABLE",
        censor_rule="截尾且未完成诊断 → CENSORED",
        source_events=("replace action", "judge_state.fault_part"),
        adversarial_note="诊断正确不等于修复成功（可能未 restart）；两者分报。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.tests_run",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="诊断测试次数（信息成本）",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(test)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="无 → 0",
        censor_rule="按已发生测试计算",
        source_events=("test",),
        adversarial_note="测试多可能更准，不能单独作为能力；必须与诊断准确率并列。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map26.legal_action_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="提交动作中被规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="accepted decisions / submitted decisions",
        denominator="模型决策数",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次决策 → N/A",
        censor_rule="按已提交决策计算",
        source_events=("decision.result",),
        adversarial_note="接口合法率不能替代纠错能力。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _feedback_part(result: str, action: dict[str, Any] | None) -> str | None:
    if not (result.startswith(_FEEDBACK_PREFIXES) or result.startswith("{")):
        return None
    return str(action.get("part_id")) if isinstance(action, dict) else None


def _is_adjustment(event: TraceEvent, failed_part: str) -> bool:
    if event.tool in {"rollback", "test"}:
        return True
    if event.tool == "replace" and isinstance(event.action, dict):
        return event.action.get("part_id") != failed_part
    return False


def _fault_part(record: TraceRecord) -> str | None:
    judge_state = (record.judge or {}).get("judge_state")
    if isinstance(judge_state, dict):
        value = judge_state.get("fault_part")
        if isinstance(value, str):
            return value
    return MAP26_FAULT_PART.get(record.instance_id)


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    censored = episode_is_censored(record)
    final = record.final_observation
    result: dict[str, MetricValue] = {}

    restored = final.get("communication_restored")
    if isinstance(restored, bool):
        result["map26.repair_success"] = MetricValue(
            metric_id="map26.repair_success",
            value=int(restored),
            status=MetricStatus.CENSORED if censored else MetricStatus.VALID,
        )
    else:
        result["map26.repair_success"] = MetricValue.unavailable(
            "map26.repair_success", "trace 缺少公开 communication_restored。"
        )

    first_feedback: TraceEvent | None = None
    failed_part: str | None = None
    for event in record.events:
        if event.tool != "replace":
            continue
        part = _feedback_part(event.result, event.action)
        if part is not None:
            first_feedback = event
            failed_part = part
            break

    if first_feedback is None or failed_part is None:
        result["map26.recovery_latency"] = MetricValue.not_applicable(
            "map26.recovery_latency", "本局没有发生错误替换反馈。"
        )
    else:
        adjusted: TraceEvent | None = None
        seen_feedback = False
        for event in record.events:
            if event is first_feedback:
                seen_feedback = True
                continue
            if not seen_feedback:
                continue
            if _is_adjustment(event, failed_part):
                adjusted = event
                break
        if adjusted is None or first_feedback.tick_after is None or adjusted.tick_after is None:
            result["map26.recovery_latency"] = MetricValue.censored(
                "map26.recovery_latency", "错误反馈后到终局都没有有效策略调整。"
            )
        else:
            result["map26.recovery_latency"] = counted(
                "map26.recovery_latency",
                max(adjusted.tick_after - first_feedback.tick_after, 0),
            )

    failed: set[str] = set()
    wrong = 0
    repeated = 0
    replaces: list[TraceEvent] = []
    for event in record.events:
        if event.tool != "replace" or not isinstance(event.action, dict):
            continue
        part = event.action.get("part_id")
        if not isinstance(part, str):
            continue
        replaces.append(event)
        if _feedback_part(event.result, event.action) is not None:
            wrong += 1
            if part in failed:
                repeated += 1
            failed.add(part)
    judge_state = (record.judge or {}).get("judge_state")
    if isinstance(judge_state, dict) and isinstance(judge_state.get("failed_by_part"), dict):
        counts = [
            int(value) for value in judge_state["failed_by_part"].values() if isinstance(value, int)
        ]
        if sum(counts) > 0:
            wrong = sum(counts)
            repeated = sum(max(count - 1, 0) for count in counts)
    result["map26.repeat_error_rate"] = ratio("map26.repeat_error_rate", repeated, wrong)

    spares = final.get("spare_units_at_B")
    carried = final.get("carried_spare_units")
    if isinstance(spares, int) and isinstance(carried, (list, tuple)):
        result["map26.spares_remaining"] = counted("map26.spares_remaining", spares + len(carried))
    elif isinstance(record.judge_metrics.get("spare_units_remaining"), int):
        result["map26.spares_remaining"] = counted(
            "map26.spares_remaining",
            int(record.judge_metrics["spare_units_remaining"]),
            note="来自离线 judge_metrics。",
        )
    else:
        result["map26.spares_remaining"] = MetricValue.unavailable(
            "map26.spares_remaining", "公开库存字段缺失。"
        )

    fault = _fault_part(record)
    if not replaces:
        if censored:
            result["map26.diagnosis_accuracy"] = MetricValue.censored(
                "map26.diagnosis_accuracy", "截尾且没有发生替换。"
            )
        else:
            result["map26.diagnosis_accuracy"] = MetricValue.not_applicable(
                "map26.diagnosis_accuracy", "本局没有提交 replace。"
            )
    elif fault is None:
        result["map26.diagnosis_accuracy"] = MetricValue.unavailable(
            "map26.diagnosis_accuracy", "缺少离线故障件真值。"
        )
    else:
        last = replaces[-1]
        part = last.action.get("part_id") if isinstance(last.action, dict) else None
        result["map26.diagnosis_accuracy"] = counted("map26.diagnosis_accuracy", int(part == fault))

    result["map26.tests_run"] = counted(
        "map26.tests_run", sum(1 for event in record.events if event.tool == "test")
    )
    result["map26.legal_action_rate"] = legal_action_rate(record, "map26.legal_action_rate")
    if record.instance_id in MAP26_INITIAL_SPARES:
        result["map26.spares_remaining"] = result["map26.spares_remaining"].model_copy(
            update={"note": f"实例初始备件 {MAP26_INITIAL_SPARES[record.instance_id]}。"}
        )
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
