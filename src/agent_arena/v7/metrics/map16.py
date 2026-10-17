"""V7 metrics for MAP-16, atomic single-track reservations and deadlock."""

from __future__ import annotations

from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    legal_action_rate,
    ratio,
)
from agent_arena.v7.metrics.references import MAP16_OPTIMAL_MAKESPAN
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceRecord,
)

MAP_ID = "MAP-16"
DOC_REF = "docs/v7/maps/MAP-16.md"
_COMMITTED = {"MOVES_COMMITTED", "GATE_OPENED"}


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map16.legal_reservation_rate",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="同步预约在提交时被原子规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="ROUTE_RESERVED / (set_route + occupy_siding submissions)",
        denominator="提交的预约动作数；0 则 N/A",
        window="整局预约事件",
        applicability="所有 MAP-16 实例",
        missing_rule="没有预约动作 → N/A",
        censor_rule="过程量按已提交动作计算，不因截尾删除",
        source_events=("set_route", "occupy_siding", "result ROUTE_RESERVED"),
        adversarial_note="只提交一次合法预约就停手会得到 100%，必须与 makespan_gap 并列解读。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.makespan_gap",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="实际完工 tick 与同实例 BFS 最优 makespan 的差",
        unit="tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="committed_ticks - BFS_optimum(instance)",
        denominator="成功终局的 episode",
        window="终局",
        applicability="有冻结最优值的 4 个 V6 实例",
        missing_rule="实例无冻结最优 → UNAVAILABLE；已失败 → N/A",
        censor_rule="step-limit 截尾 → CENSORED",
        source_events=("move_train", "MOVES_COMMITTED/GATE_OPENED"),
        adversarial_note="失败局不能算 gap=0；必须 N/A。单车 L1 的 gap 不能代表会车能力。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.deadlock",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="不可恢复死锁是否发生",
        unit="0/1",
        direction=Direction.LOWER_IS_BETTER,
        formula="1 if terminal_reason==DEADLOCK else 0",
        denominator="episode",
        window="终局",
        applicability="多车实例",
        missing_rule="无终局 → CENSORED",
        censor_rule="截尾且未进入死锁 → CENSORED",
        source_events=("terminal_reason",),
        adversarial_note="死锁是硬失败，不能被更短 makespan 抵消。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.node_capacity_conflicts",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="节点/站台容量冲突次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==NODE_CAPACITY_CONFLICT)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("move_train result",),
        adversarial_note="与避让站冲突分开计数；两者不可合并成一个“容量错误”。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.head_on_conflicts",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="相向交换/正面冲突次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==HEAD_ON_SWAP)",
        denominator="episode",
        window="整局",
        applicability="所有多车实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("set_route/move_train result",),
        adversarial_note="相向交换与同段容量冲突的因果不同，必须分开。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.section_conflicts",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="同一区段被两列车同时预约的次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==SECTION_RESERVATION_CONFLICT)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("set_route result",),
        adversarial_note="边容量冲突与节点冲突不可互换。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.committed_ticks",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="实际提交的调度 tick 数",
        unit="tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(MOVES_COMMITTED or GATE_OPENED)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 → 合法 0",
        censor_rule="按已提交 tick 计算",
        source_events=("move_train result",),
        adversarial_note="tick 数与完工时间相关但不等价；失败局 tick 少不代表更好。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map16.legal_action_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="提交决策中被规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="accepted decisions / submitted decisions",
        denominator="模型决策数",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次决策 → N/A",
        censor_rule="按已提交决策计算",
        source_events=("decision.result",),
        adversarial_note="接口合法率不能替代调度质量。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _committed_ticks(record: TraceRecord) -> int:
    return sum(1 for event in record.events if event.result in _COMMITTED)


def _optimum(record: TraceRecord, actual: int) -> int | None:
    frozen = MAP16_OPTIMAL_MAKESPAN.get(record.instance_id)
    if frozen is not None:
        return frozen
    gap = record.judge_metrics.get("optimality_gap")
    makespan = record.judge_metrics.get("makespan_ticks")
    if isinstance(gap, int) and isinstance(makespan, int):
        return makespan - gap
    return None


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    reservations = [
        event for event in record.events if event.tool in {"set_route", "occupy_siding"}
    ]
    accepted = sum(1 for event in reservations if event.result == "ROUTE_RESERVED")
    result: dict[str, MetricValue] = {
        "map16.legal_reservation_rate": ratio(
            "map16.legal_reservation_rate", accepted, len(reservations)
        ),
        "map16.deadlock": counted("map16.deadlock", int(record.terminal_reason == "DEADLOCK")),
        "map16.node_capacity_conflicts": counted(
            "map16.node_capacity_conflicts",
            sum(1 for event in record.events if event.result == "NODE_CAPACITY_CONFLICT"),
        ),
        "map16.head_on_conflicts": counted(
            "map16.head_on_conflicts",
            sum(1 for event in record.events if event.result == "HEAD_ON_SWAP"),
        ),
        "map16.section_conflicts": counted(
            "map16.section_conflicts",
            sum(1 for event in record.events if event.result == "SECTION_RESERVATION_CONFLICT"),
        ),
    }
    actual = _committed_ticks(record)
    result["map16.committed_ticks"] = counted("map16.committed_ticks", actual)

    if episode_is_censored(record):
        result["map16.makespan_gap"] = MetricValue.censored(
            "map16.makespan_gap", "episode 在 step-limit 或 provider 边界截尾。"
        )
    elif record.terminal_reason != "GATE_OPENED":
        result["map16.makespan_gap"] = MetricValue.not_applicable(
            "map16.makespan_gap",
            f"未成功终局（{record.terminal_reason}），最优差没有可比定义。",
        )
    else:
        optimum = _optimum(record, actual)
        if optimum is None:
            result["map16.makespan_gap"] = MetricValue.unavailable(
                "map16.makespan_gap", f"实例 {record.instance_id} 没有冻结 BFS 最优值。"
            )
        else:
            result["map16.makespan_gap"] = MetricValue(
                metric_id="map16.makespan_gap",
                value=actual - optimum,
                status=MetricStatus.VALID,
                note=f"BFS 最优 {optimum} tick。",
            )

    result["map16.legal_action_rate"] = legal_action_rate(record, "map16.legal_action_rate")
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
