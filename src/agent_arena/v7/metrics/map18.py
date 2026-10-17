"""V7 metrics for MAP-18, bounded online recovery dispatch."""

from __future__ import annotations

from typing import Any

from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    is_rejected_result,
    ratio,
)
from agent_arena.v7.metrics.references import (
    MAP18_PASSENGERS,
    MAP18_PLANNED_ARRIVAL,
    MAP18_RED_TASKS,
    MAP18_TOTAL_DEMAND,
)
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceEvent,
    TraceRecord,
)

MAP_ID = "MAP-18"
DOC_REF = "docs/v7/maps/MAP-18.md"


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map18.service_rate",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="在 12 tick horizon 内按乘客权重完成的服务比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="delivered_passengers / 18",
        denominator="总需求 18 人",
        window="horizon 结束或更早的终止",
        applicability="所有 MAP-18 实例",
        missing_rule="无公开 delivered_passengers → UNAVAILABLE",
        censor_rule="未到 horizon 的 step-limit 截尾 → CENSORED（值仍为已交付比例）",
        source_events=("observation.delivered_passengers", "terminal"),
        adversarial_note="服务率 1.0 不等于延误最优；必须与 delay_person_ticks 并列。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.delay_person_ticks",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="乘客实际到达相对计划到达的累计人·tick 延误",
        unit="人·tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="Σ_task passengers × max(arrival_tick - planned_arrival_tick, 0)",
        denominator="已交付任务；未交付不计入（另报 service_rate）",
        window="整局",
        applicability="所有 MAP-18 实例",
        missing_rule="无交付 → 0（合法）",
        censor_rule="未到 horizon 截尾时只累计已观察交付并标 CENSORED",
        source_events=("observation.delivered_tasks", "published_dispatch_windows"),
        adversarial_note="把未交付当作零延误会奖励放弃任务，必须同时看服务率。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.first_reroute_delay",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="封锁公开可见后，首次合法改线动作的延迟",
        unit="tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="tick(first non-closed release/detour committed) - tick(closure first public)",
        denominator="closure 实际发生的 episode",
        window="从首次公开 closed_segments 到之后首个有效 set_timetable",
        applicability="fault_enabled=True 的实例；L1 无故障为 N/A",
        missing_rule="从未观察到封锁，或封锁后没有任何移动型时刻表 → N/A",
        censor_rule="封锁后提交了移动但未成功改线 → CENSORED（延迟无上界）",
        source_events=("observation.closed_segments", "set_timetable", "TICK_COMMITTED"),
        adversarial_note="不能把提前发车规避（从未见到封锁）算成 0 延迟；那属于 N/A。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.recovery_delay",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="封锁公开后红线任务恢复交付的延迟",
        unit="tick",
        direction=Direction.LOWER_IS_BETTER,
        formula="tick(first red-line task delivered after closure) - tick(closure first public)",
        denominator="closure 实际发生的 episode",
        window="从封锁公开到首个 TASK_R2_R3/TASK_R3_R2 交付",
        applicability="fault_enabled=True 且红线任务尚未在封锁前交付的实例",
        missing_rule="无封锁，或红线任务已在封锁前交付 → N/A",
        censor_rule="封锁后红线任务未恢复交付且 episode 截尾 → CENSORED",
        source_events=("observation.delivered_tasks", "observation.closed_segments"),
        adversarial_note="取消服务不是恢复；取消后交付其它任务不能算红线恢复。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.station_capacity_violations",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="站台同时停靠超过 2 列车的次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==STATION_CAPACITY_EXCEEDED)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("set_timetable result",),
        adversarial_note="容量硬失败不能被服务率抵消。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.collision_violations",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="相向碰撞与区段容量冲突次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(HEAD_ON_COLLISION) + count(SEGMENT_CAPACITY)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("set_timetable result",),
        adversarial_note="碰撞与容量冲突分属不同因果，合并值须保留分项 note。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.completed_train_moves",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="完成后仍被移动/改线的列车数（任务不可逆性违例）",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==COMPLETED_TRAIN_MOVED)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("set_timetable result",),
        adversarial_note="已完成任务不可再调度；这是任务语义违例而非路线错误。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map18.legal_action_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="提交的联合时刻表动作被规则接受的比例",
        unit="比例 0..1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="accepted set_timetable / submitted set_timetable",
        denominator="提交的时刻表动作数；0 则 N/A",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次 → N/A",
        censor_rule="按已提交动作计算",
        source_events=("set_timetable result",),
        adversarial_note="TICK_MISMATCH 等接口拒绝率不能与调度策略失败混在一起。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _closure_tick(record: TraceRecord) -> int | None:
    for event in record.events:
        closed = event.observation_after.get("closed_segments")
        if isinstance(closed, (list, tuple)) and closed:
            return event.tick_after
    return None


def _operations(event: TraceEvent) -> dict[str, Any]:
    if not isinstance(event.action, dict):
        return {}
    operations = event.action.get("operations")
    return operations if isinstance(operations, dict) else {}


def _first_reroute(record: TraceRecord, closure_tick: int) -> int | None:
    for event in record.events:
        if event.tool != "set_timetable" or event.tick_after is None:
            continue
        if event.tick_after <= closure_tick:
            continue
        positions = event.observation_before.get("train_positions")
        if not isinstance(positions, dict):
            continue
        closed = event.observation_after.get("closed_segments")
        closed_set = {
            frozenset(str(item).split("_"))
            for item in (closed if isinstance(closed, (list, tuple)) else ())
        }
        for train, operation in _operations(event).items():
            if not isinstance(operation, dict) or operation.get("op") not in {
                "release",
                "detour",
            }:
                continue
            destination = operation.get("to")
            origin = positions.get(train)
            if not isinstance(destination, str) or not isinstance(origin, str):
                continue
            edge = frozenset((origin, destination))
            if edge in closed_set:
                continue
            return event.tick_after
    return None


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    final = record.final_observation
    delivered = final.get("delivered_passengers")
    censored = episode_is_censored(record)
    result: dict[str, MetricValue] = {}

    if isinstance(delivered, int):
        result["map18.service_rate"] = MetricValue(
            metric_id="map18.service_rate",
            value=round(delivered / MAP18_TOTAL_DEMAND, 6),
            status=MetricStatus.CENSORED if censored else MetricStatus.VALID,
            denominator=MAP18_TOTAL_DEMAND,
            note=f"{delivered}/{MAP18_TOTAL_DEMAND} 人。",
        )
    else:
        result["map18.service_rate"] = MetricValue.unavailable(
            "map18.service_rate", "trace 缺少公开 delivered_passengers。"
        )

    delay = 0
    seen: set[str] = set()
    for event in record.events:
        tasks = event.observation_after.get("delivered_tasks")
        if not isinstance(tasks, (list, tuple)) or event.tick_after is None:
            continue
        for task in tasks:
            if not isinstance(task, str) or task in seen:
                continue
            seen.add(task)
            planned = MAP18_PLANNED_ARRIVAL.get(task)
            passengers = MAP18_PASSENGERS.get(task)
            if planned is None or passengers is None:
                continue
            delay += passengers * max(event.tick_after - planned, 0)
    result["map18.delay_person_ticks"] = MetricValue(
        metric_id="map18.delay_person_ticks",
        value=delay,
        status=MetricStatus.CENSORED if censored else MetricStatus.VALID,
        note=None if censored else "仅累计已交付任务。",
    )

    closure = _closure_tick(record)
    if closure is None:
        note = "本局没有公开封锁；无故障实例的改线延迟按 N/A。"
        result["map18.first_reroute_delay"] = MetricValue.not_applicable(
            "map18.first_reroute_delay", note
        )
        result["map18.recovery_delay"] = MetricValue.not_applicable("map18.recovery_delay", note)
    else:
        reroute = _first_reroute(record, closure)
        if reroute is None:
            attempted = any(
                event.tool == "set_timetable"
                and event.tick_after is not None
                and event.tick_after > closure
                and bool(_operations(event))
                for event in record.events
            )
            if attempted:
                result["map18.first_reroute_delay"] = MetricValue.censored(
                    "map18.first_reroute_delay",
                    "封锁公开后提交了时刻表，但没有成功移动到非封闭区段。",
                )
            else:
                result["map18.first_reroute_delay"] = MetricValue.not_applicable(
                    "map18.first_reroute_delay",
                    "封锁公开后没有提交任何有移动的时刻表（任务已完成或已取消）。",
                )
        else:
            result["map18.first_reroute_delay"] = counted(
                "map18.first_reroute_delay", max(reroute - closure, 0)
            )
        red_delivered_before: set[str] = set()
        for event in record.events:
            if event.tick_after is None or event.tick_after >= closure:
                continue
            tasks = event.observation_after.get("delivered_tasks")
            if isinstance(tasks, (list, tuple)):
                red_delivered_before.update(task for task in tasks if task in MAP18_RED_TASKS)
        recovered_at: int | None = None
        for event in record.events:
            if event.tick_after is None or event.tick_after < closure:
                continue
            tasks = event.observation_after.get("delivered_tasks")
            if isinstance(tasks, (list, tuple)) and any(
                task in MAP18_RED_TASKS and task not in red_delivered_before for task in tasks
            ):
                recovered_at = event.tick_after
                break
        if recovered_at is None:
            if red_delivered_before:
                result["map18.recovery_delay"] = MetricValue.not_applicable(
                    "map18.recovery_delay",
                    "红线任务在封锁公开前已交付，封锁没有留下可测的恢复延迟。",
                )
            else:
                result["map18.recovery_delay"] = MetricValue.censored(
                    "map18.recovery_delay", "封锁后红线任务未恢复交付。"
                )
        else:
            result["map18.recovery_delay"] = counted(
                "map18.recovery_delay", max(recovered_at - closure, 0)
            )

    result["map18.station_capacity_violations"] = counted(
        "map18.station_capacity_violations",
        sum(1 for event in record.events if event.result == "STATION_CAPACITY_EXCEEDED"),
    )
    result["map18.collision_violations"] = counted(
        "map18.collision_violations",
        sum(
            1
            for event in record.events
            if event.result in {"HEAD_ON_COLLISION", "SEGMENT_CAPACITY"}
        ),
        note="合并值；HEAD_ON_COLLISION 与 SEGMENT_CAPACITY 分项见 trace。",
    )
    result["map18.completed_train_moves"] = counted(
        "map18.completed_train_moves",
        sum(1 for event in record.events if event.result == "COMPLETED_TRAIN_MOVED"),
    )

    submissions = [event for event in record.events if event.tool == "set_timetable"]
    accepted = sum(
        1
        for event in submissions
        if not event.invalid_schema and not is_rejected_result(event.result)
    )
    result["map18.legal_action_rate"] = ratio("map18.legal_action_rate", accepted, len(submissions))
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
