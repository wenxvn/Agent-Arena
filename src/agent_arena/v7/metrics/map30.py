"""V7 metrics for MAP-30, bounded courtroom investigation with long gaps."""

from __future__ import annotations

from typing import Any

from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    legal_action_rate,
    ratio,
)
from agent_arena.v7.metrics.references import MAP30_CASES, Map30CaseReference
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricValue,
    TraceRecord,
)

MAP_ID = "MAP-30"
DOC_REF = "docs/v7/maps/MAP-30.md"


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map30.q4_recall_accuracy",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="长间隔后是否正确引用早期编码并指向真凶（纯召回变体的主指标）",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if person==culprit and code_entry cited in formal_accuse else 0",
        denominator="提交过 formal_accuse 的 episode",
        window="终局",
        applicability="全部实例；召回变体与完整调查必须分报",
        missing_rule="无最终指控 → N/A；无冻结案情 → UNAVAILABLE",
        censor_rule="因 deadline/step-limit 未提交 → CENSORED",
        source_events=("formal_accuse.person_id", "formal_accuse.cited_entry_ids"),
        adversarial_note="不能用私有真凶判断“是否看到证据”；只认最终公开提交。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.evidence_chain_coverage",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="四段证据链中满足全部必需证据的条目比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="entries with required_evidence ⊆ recorded / len(entry_order)",
        denominator="该案卷条目总数（3 或 4）",
        window="终局 casebook",
        applicability="全部实例",
        missing_rule="casebook 字段缺失 → UNAVAILABLE",
        censor_rule="过程量按已记录条目计算",
        source_events=("observation.casebook",),
        adversarial_note="记录条目但缺一条证据不算覆盖；不能按 record 次数计。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.accusation_claim_precision",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="最终指控中时间/地点/值勤码与冻结事实的一致率",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="max(0, matched_expected - extra) / expected_claim_count",
        denominator="冻结案情的应提交事件数",
        window="终局 formal_accuse",
        applicability="提交过指控的 episode",
        missing_rule="无指控 → N/A；无冻结案情 → UNAVAILABLE",
        censor_rule="无指控且截尾 → CENSORED",
        source_events=("formal_accuse.event_claims",),
        adversarial_note="少提交事件不能自动得满分；分母固定为应提交数。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.chain_reconciled",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="是否成功执行 compare_records 并得到 CHAIN_COHERENT",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if any result==CHAIN_COHERENT else 0",
        denominator="episode",
        window="整局",
        applicability="全部实例",
        missing_rule="无 compare_records → 0（合法）",
        censor_rule="按已发生事件计算",
        source_events=("compare_records result",),
        adversarial_note="对齐成功不等于指控正确；必须与召回和事实精确率并列。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.investigation_progress",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="已记录案卷条目占应记录条目的比例（区别于证据完整性）",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="len(recorded entries) / len(entry_order)",
        denominator="案卷条目总数",
        window="终局 casebook",
        applicability="完整调查实例；召回变体只作描述",
        missing_rule="casebook 缺失 → UNAVAILABLE",
        censor_rule="按已记录条目计算",
        source_events=("observation.casebook",),
        adversarial_note="记录条目只是流程进度，不能替代证据覆盖或召回正确率。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.unsupported_accusations",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="证据不足的正式指控次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="final unsupported_formal_accusations",
        denominator="episode",
        window="终局",
        applicability="全部实例",
        missing_rule="字段缺失 → UNAVAILABLE",
        censor_rule="按已发生指控计数",
        source_events=("observation.unsupported_formal_accusations",),
        adversarial_note="第二次无据指控即失败；不能用最终猜中抵消。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map30.legal_action_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="提交动作中被规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="accepted decisions / submitted decisions",
        denominator="模型决策数",
        window="整局",
        applicability="全部实例",
        missing_rule="0 次决策 → N/A",
        censor_rule="按已提交决策计算",
        source_events=("decision.result",),
        adversarial_note="导航/接口失败率不能冒充调查或记忆能力。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _case(record: TraceRecord) -> Map30CaseReference | None:
    return MAP30_CASES.get(record.instance_id)


def _casebook_exposed(record: TraceRecord) -> bool:
    """Whether this trace's conditioning actually exposed the casebook.

    The MAP-30 environment always serializes ``casebook``, but the memory
    conditions without the structured casebook emit an empty tuple. An empty
    tuple is therefore ambiguous: "exposed but unused" (legal 0) versus
    "not exposed" (must be UNAVAILABLE, never 0). Prefer an explicit judge
    flag, then the condition id; default to exposed when neither is available.
    """

    judge_state = (record.judge or {}).get("judge_state")
    if isinstance(judge_state, dict):
        visible = judge_state.get("casebook_visible")
        if isinstance(visible, bool):
            return visible
    condition = record.condition_id
    if condition and "casebook" not in condition:
        return False
    return True


def _casebook(record: TraceRecord) -> dict[str, set[str]] | None:
    if not _casebook_exposed(record):
        return None
    raw = record.final_observation.get("casebook")
    if not isinstance(raw, (list, tuple)):
        return None
    recorded: dict[str, set[str]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("entry_id")
        evidence_ids = entry.get("evidence_ids")
        if isinstance(entry_id, str) and isinstance(evidence_ids, (list, tuple)):
            recorded[entry_id] = {str(item) for item in evidence_ids}
    return recorded


def _final_accusation(record: TraceRecord) -> dict[str, Any] | None:
    for event in reversed(record.events):
        if event.tool == "formal_accuse" and isinstance(event.action, dict):
            return event.action
    return None


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    case = _case(record)
    censored = episode_is_censored(record)
    result: dict[str, MetricValue] = {}

    casebook = _casebook(record)
    if case is None or casebook is None:
        note = "缺少冻结案情或公开 casebook，无法复算证据链。"
        for metric_id in (
            "map30.evidence_chain_coverage",
            "map30.investigation_progress",
        ):
            result[metric_id] = MetricValue.unavailable(metric_id, note)
    else:
        total = len(case.entry_order)
        complete = sum(
            1
            for entry_id in case.entry_order
            if entry_id in casebook and case.entry_required[entry_id].issubset(casebook[entry_id])
        )
        result["map30.evidence_chain_coverage"] = ratio(
            "map30.evidence_chain_coverage", complete, total
        )
        result["map30.investigation_progress"] = ratio(
            "map30.investigation_progress", len(casebook), total
        )

    accusation = _final_accusation(record)
    if accusation is None:
        note = "本局没有提交 formal_accuse。"
        for metric_id in (
            "map30.q4_recall_accuracy",
            "map30.accusation_claim_precision",
        ):
            result[metric_id] = (
                MetricValue.censored(metric_id, note)
                if censored
                else MetricValue.not_applicable(metric_id, note)
            )
    elif case is None:
        for metric_id in (
            "map30.q4_recall_accuracy",
            "map30.accusation_claim_precision",
        ):
            result[metric_id] = MetricValue.unavailable(metric_id, "缺少冻结案情参考。")
    else:
        cited = accusation.get("cited_entry_ids")
        cited_ids = {str(item) for item in cited} if isinstance(cited, (list, tuple)) else set()
        person = accusation.get("person_id")
        result["map30.q4_recall_accuracy"] = counted(
            "map30.q4_recall_accuracy",
            int(person == case.culprit and case.code_entry in cited_ids),
        )

        expected = {claim[0]: claim[1:] for claim in case.claims}
        raw_claims = accusation.get("event_claims")
        submitted: list[tuple[str, str, str, str]] = []
        if isinstance(raw_claims, (list, tuple)):
            for claim in raw_claims:
                if not isinstance(claim, dict):
                    continue
                submitted.append(
                    (
                        str(claim.get("event_id", "")),
                        str(claim.get("time", "")),
                        str(claim.get("location", "")),
                        str(claim.get("duty_code", "")),
                    )
                )
        matched = sum(
            1 for claim in submitted if claim[0] in expected and claim[1:] == expected[claim[0]]
        )
        extra = max(len(submitted) - matched, 0)
        numerator = max(matched - extra, 0)
        result["map30.accusation_claim_precision"] = ratio(
            "map30.accusation_claim_precision", numerator, case.claim_count
        )

    result["map30.chain_reconciled"] = counted(
        "map30.chain_reconciled",
        int(any(event.result == "CHAIN_COHERENT" for event in record.events)),
    )
    unsupported = record.final_observation.get("unsupported_formal_accusations")
    if isinstance(unsupported, int):
        result["map30.unsupported_accusations"] = counted(
            "map30.unsupported_accusations", unsupported
        )
    else:
        result["map30.unsupported_accusations"] = MetricValue.unavailable(
            "map30.unsupported_accusations", "trace 缺少公开指控计数。"
        )
    result["map30.legal_action_rate"] = legal_action_rate(record, "map30.legal_action_rate")
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
