"""V7 metrics for MAP-22, local signposts and Agent-owned return memory."""

from __future__ import annotations

from typing import Any

from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    legal_action_rate,
    ratio,
)
from agent_arena.v7.metrics.references import MAP22_OPTIMAL_MOVES
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceRecord,
)

MAP_ID = "MAP-22"
DOC_REF = "docs/v7/maps/MAP-22.md"


SPECS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="map22.return_success",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="访问遗迹后是否在移动预算内回到营地",
        unit="0/1",
        direction=Direction.HIGHER_IS_BETTER,
        formula="1 if terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD else 0",
        denominator="episode",
        window="终局",
        applicability="所有 MAP-22 实例",
        missing_rule="无终局 → CENSORED",
        censor_rule="step-limit 截尾时值仍为 0，但状态标 CENSORED",
        source_events=("terminal_reason",),
        adversarial_note="到达遗迹本身不算成功；必须回营。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.path_gap",
        map_id=MAP_ID,
        kind=MetricKind.PRIMARY,
        construct_name="成功返程相对同实例最短合法往返的移动差",
        unit="moves",
        direction=Direction.LOWER_IS_BETTER,
        formula="movement_steps - BFS_optimal_moves(instance)",
        denominator="成功返程的 episode",
        window="终局",
        applicability="有冻结最优的 4 个 V6 实例",
        missing_rule="无冻结最优 → UNAVAILABLE；未成功 → N/A",
        censor_rule="截尾 → CENSORED",
        source_events=("move", "observation.movement_steps"),
        adversarial_note="最优值必须按实例取，不能沿用 V4 默认 8；否则短图会被误判为负差。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.repeated_public_edge_rate",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="按公开位置签名检测到的同向重复走边比例",
        unit="比例 0..1",
        direction=Direction.LOWER_IS_BETTER,
        formula="directed edges traversed more than once / resolved directed moves",
        denominator="两端的公开位置签名都可解析的移动数",
        window="整局",
        applicability="所有实例；位置签名用 sign_id 或 silhouette+exits",
        missing_rule="可解析移动为 0 → N/A",
        censor_rule="按已发生移动计算",
        source_events=("move", "observation.current_coarse_silhouette", "visible_exit_bearings"),
        adversarial_note=(
            "必须按有向边计：合法往返会各走一次相反方向，不能被误判为重复；"
            "该指标是过程诊断，不单独支撑记忆能力结论。"
        ),
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.memory_grounding_violations",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="写入未观察/未经过事实的次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==MEMORY_FACT_NOT_OBSERVED)",
        denominator="episode",
        window="整局",
        applicability="启用记忆的实例",
        missing_rule="0 次为合法 0；未启用记忆时无该结果",
        censor_rule="按已发生事件计数",
        source_events=("write_memory result",),
        adversarial_note="不能用全图预装记忆；合法来源必须是当前观察或刚经过边。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.illegal_bearing_actions",
        map_id=MAP_ID,
        kind=MetricKind.GUARDRAIL,
        construct_name="不存在的方位动作次数",
        unit="次",
        direction=Direction.LOWER_IS_BETTER,
        formula="count(result==INVALID_BEARING)",
        denominator="episode",
        window="整局",
        applicability="所有实例",
        missing_rule="0 次为合法 0",
        censor_rule="按已发生事件计数",
        source_events=("move result",),
        adversarial_note="方位试探是合法探索的一部分，只有不存在于公开出口的方位才计违例。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.memory_facts_written",
        map_id=MAP_ID,
        kind=MetricKind.DIAGNOSTIC,
        construct_name="Agent 合法写入的记忆事实数量（成本，不是收益）",
        unit="条",
        direction=Direction.DESCRIPTIVE,
        formula="len(final agent_authored_memory_journal)",
        denominator="episode",
        window="终局",
        applicability="记忆条件",
        missing_rule="无 journal 字段 → UNAVAILABLE",
        censor_rule="按最终公开 journal 计算",
        source_events=("observation.agent_authored_memory_journal",),
        adversarial_note="写得多不等于记得好；必须与返程成功和 path_gap 并列。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
    MetricSpec(
        metric_id="map22.legal_action_rate",
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
        adversarial_note="不能把接口熟悉度当成空间记忆。",
        implemented=True,
        doc_ref=DOC_REF,
    ),
)


def _position_key(observation: dict[str, Any]) -> str | None:
    detail = observation.get("inspected_current_sign_detail")
    if isinstance(detail, dict) and isinstance(detail.get("sign_id"), str):
        return f"sign:{detail['sign_id']}"
    silhouette = observation.get("current_coarse_silhouette")
    exits = observation.get("visible_exit_bearings")
    if isinstance(silhouette, str) and isinstance(exits, (list, tuple)):
        return f"shape:{silhouette}|{','.join(str(item) for item in exits)}"
    return None


def _repeated_edges(record: TraceRecord) -> tuple[int, int]:
    seen: set[tuple[str, str]] = set()
    resolved = 0
    repeated = 0
    for event in record.events:
        if event.tool != "move":
            continue
        before = _position_key(event.observation_before)
        after = _position_key(event.observation_after)
        if before is None or after is None or before == after:
            continue
        resolved += 1
        edge = (before, after)
        if edge in seen:
            repeated += 1
        else:
            seen.add(edge)
    return repeated, resolved


def compute(record: TraceRecord) -> dict[str, MetricValue]:
    censored = episode_is_censored(record)
    success = record.terminal_reason == "RETURNED_TO_CAMP_WITH_RUIN_RECORD"
    result: dict[str, MetricValue] = {
        "map22.return_success": MetricValue(
            metric_id="map22.return_success",
            value=int(success),
            status=MetricStatus.CENSORED if censored else MetricStatus.VALID,
            note=None if record.is_terminal else "episode 未终局。",
        )
    }

    moves_value = record.final_observation.get("movement_steps")
    moves = (
        moves_value
        if isinstance(moves_value, int)
        else sum(1 for event in record.events if event.tool == "move")
    )
    if censored:
        result["map22.path_gap"] = MetricValue.censored(
            "map22.path_gap", "episode 在移动预算或 provider 边界截尾。"
        )
    elif not success:
        result["map22.path_gap"] = MetricValue.not_applicable(
            "map22.path_gap", f"未成功返程（{record.terminal_reason}），最优差没有可比定义。"
        )
    else:
        optimum = MAP22_OPTIMAL_MOVES.get(record.instance_id)
        if optimum is None:
            gap = record.judge_metrics.get("shortest_route_gap")
            if isinstance(gap, int):
                optimum = moves - gap
        if optimum is None:
            result["map22.path_gap"] = MetricValue.unavailable(
                "map22.path_gap", f"实例 {record.instance_id} 没有冻结最短往返值。"
            )
        else:
            result["map22.path_gap"] = MetricValue(
                metric_id="map22.path_gap",
                value=moves - optimum,
                status=MetricStatus.VALID,
                note=f"BFS 最优 {optimum} moves。",
            )

    repeated, resolved = _repeated_edges(record)
    result["map22.repeated_public_edge_rate"] = ratio(
        "map22.repeated_public_edge_rate", repeated, resolved
    )
    result["map22.memory_grounding_violations"] = counted(
        "map22.memory_grounding_violations",
        sum(1 for event in record.events if event.result == "MEMORY_FACT_NOT_OBSERVED"),
    )
    result["map22.illegal_bearing_actions"] = counted(
        "map22.illegal_bearing_actions",
        sum(1 for event in record.events if event.result == "INVALID_BEARING"),
    )

    journal = record.final_observation.get("agent_authored_memory_journal")
    if isinstance(journal, (list, tuple)):
        result["map22.memory_facts_written"] = counted(
            "map22.memory_facts_written", len(journal), note="成本量，不是能力收益。"
        )
    else:
        result["map22.memory_facts_written"] = MetricValue.unavailable(
            "map22.memory_facts_written", "trace 缺少公开记忆 journal。"
        )

    result["map22.legal_action_rate"] = legal_action_rate(record, "map22.legal_action_rate")
    return result


__all__ = ["DOC_REF", "MAP_ID", "SPECS", "compute"]
