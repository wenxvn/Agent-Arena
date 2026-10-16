"""V6 condition prompts with corrected public action contracts.

The MAP-22 non-memory conditions no longer advertise ``write_memory`` and both
MAP-22 conditions explain that ``return_to_camp`` only sets the goal while
movement requires ``move``. This directly addresses the interface defect found
in the V5 audit (DCR-001).
"""

from __future__ import annotations

import json
from typing import Any

_MAP_TASKS = {
    "MAP-08": (
        "在公开候选点中识别唯一漏点并修复。只能使用一份密封剂；"
        "核心水量不得超过上限；压力测试会消耗更多 tick。修复错误地点会失败。"
    ),
    "MAP-16": (
        "把每列车从当前位置送到它的目标节点。每 tick 先预约路线，再调用 move_train "
        "同时移动；区段和站点容量有限，可用避让站安全让行。避免对向冲突和死锁。"
    ),
    "MAP-18": (
        "在限定 tick 内安全交付达到阈值的乘客。按当前公开时刻表逐 tick 联合提交；"
        "只依据当前公开 Observation 的线路状态和已出现告警调整计划，不得推断未公开未来故障。"
    ),
    "MAP-22": (
        "在移动预算内找到目标路标并回到出发营地。只能使用当前位置的局部出口和已观察路标；"
        "return_to_camp 只把出发营地设为当前目标，不会自动移动；真正移动必须使用 "
        "move{bearing:string}，bearing 取自当前 Observation 的 visible_exit_bearings。"
    ),
    "MAP-26": (
        "设备从 T 出发，公开通道为 T-D-A-B；恢复通信并保留至少一个未消耗备件。"
        "日志和诊断测试只能在 D 读取，备件在 B 领取，部件在 A 更换，正确部件更换后在 A restart。"
    ),
    "MAP-30": (
        "限时调查公开证据与证词，按 entry_order 顺序完整记录案卷，"
        "在 J 提交正式指控；证词依赖已公开回执/案卷条目。"
    ),
}

_ACTION_CONTRACTS = {
    "MAP-08": (
        'action 只可为 move{edge_id}、inspect{target_id:"ordinary_sensor"}、'
        'interact{target_id,operation:"pressure_test_<站>"|"repair_leak"}、wait{turns:1}。'
    ),
    "MAP-16": (
        'action 只可为 inspect_network{}、set_route{train_id,next_node}、'
        'occupy_siding{train_id,next_node}、release_section{train_id,section_id}、move_train{}。'
    ),
    "MAP-18": (
        'action 只可为 set_timetable{tick,operations}；operations 值为 '
        'release{op,to}、detour{op,to}、temporary_stop{op}、'
        'turnback{op,reverse_toward,duration_ticks}、cancel_service{op,task_id}。'
    ),
    "MAP-22": (
        'action 只可为 observe_signpost{}、move{bearing}、check_goal{}、return_to_camp{}'
        '（记忆条件额外允许 write_memory{facts}）。'
    ),
    "MAP-26": (
        'action 只可为 move{to}、read_log{log_id}、test{test_id}、take_spare{part_id}、'
        'replace{part_id}、rollback{}、restart{}。'
    ),
    "MAP-30": (
        'action 只可为 move{to}、inspect{evidence_id}、'
        'interview{npc_id,topic_id,shown_evidence_ids,shown_casebook_entry_ids}、'
        'record{entry_id,evidence_ids}、submit_intermediate_hypothesis{...}、'
        'compare_records{entry_ids}、formal_accuse{person_id,event_claims,cited_entry_ids}。'
    ),
}

_CONDITIONS = {
    "no_hypothesis_table": "本条件不提供跨步假设表；agent_hypothesis_table 必须为 null。",
    "hypothesis_table": (
        "本条件启用 Agent-owned 结构化假设表，只能记录已公开证据；不得写入未观察的测试结果。"
    ),
    "react": "使用 Observation 直接逐步 ReAct。",
    "constraint_table": "额外约束表由当前公开 Observation 派生；按表规划但仍以实际预约结果为准。",
    "alert_off": "告警通道关闭；不得推断 Observation 未提供的预告信息。",
    "alert_on": "若 Observation 出现告警，应把它当作不确定信息而非确定的路段事实。",
    "history5": "只把最近五条公开轨迹和当前 Observation 当作可见记忆。",
    "history5_graph_memory": (
        "使用最近五条公开轨迹和 Observation 内 Agent-owned 图记忆；记忆只能依据已观察路标和已走边，"
        "不得臆造未观察的图事实。"
    ),
    "free_diagnosis": "从初始状态自主诊断；所有测试和维修动作按当前 Observation 选择。",
    "recovery_full": "这是合法错误替换后的恢复状态；可见完整公开错误反馈。",
    "recovery_hidden": "这是合法错误替换后的恢复状态；替换反馈已隐藏。",
    "recovery_structured": "这是合法错误替换后的恢复状态；错误反馈以结构化公开摘要给出。",
    "history_full": "使用从调查开始至今的完整公开动作/结果历史及其中已公开的证据与证词细节。",
    "history5_casebook": "使用最近五条公开轨迹与结构化案卷；笔记只引用已公开证据。",}

# Conditions in which MAP-22 grants the Agent-owned memory journal.
_MAP22_MEMORY_CONDITIONS = frozenset({"history5_graph_memory"})


def v6_action_contract(map_id: str, condition_id: str) -> str:
    contract = _ACTION_CONTRACTS[map_id]
    if map_id == "MAP-22" and condition_id not in _MAP22_MEMORY_CONDITIONS:
        # The non-memory condition must not advertise an unavailable action.
        contract = (
            'action 只可为 observe_signpost{}、move{bearing}、check_goal{}、return_to_camp{}。'
            "本条件不提供 write_memory。"
        )
    return contract


def v6_system_prompt(map_id: str, condition_id: str) -> str:
    condition = _CONDITIONS.get(condition_id)
    if condition is None:
        raise ValueError(f"Unregistered V6 condition: {map_id}/{condition_id}")
    if map_id == "MAP-22" and condition_id not in _MAP22_MEMORY_CONDITIONS:
        condition = condition + " 本条件禁用 write_memory；不要尝试写入图记忆。"
    return "\n".join(
        [
            f"你正在运行 Agent Arena V6 {map_id}。",
            _MAP_TASKS[map_id],
            v6_action_contract(map_id, condition_id),
            '"action" 须含 "tool"（动作名）；参数严格按动作契约。',
            condition,
            "只输出合法 JSON 对象，顶层只含 decision_reason、action、agent_hypothesis_table。",
            "Observation 是唯一环境状态来源；不得假设未提供的裁判真值。",
        ]
    )


def v6_condition_memory(
    map_id: str,
    condition_id: str,
    observation: Any,
    hypothesis_table: dict[str, Any] | None,
) -> str | None:
    """Return only registered, Agent-owned or public-derived context."""

    if map_id == "MAP-08" and condition_id == "hypothesis_table":
        return "当前 Agent-owned 假设表：" + json.dumps(
            hypothesis_table,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    if map_id == "MAP-16" and condition_id == "constraint_table":
        table = {
            "train_route_directions": observation.train_route_directions,
            "segment_capacities": observation.segment_capacities,
            "node_capacities": observation.node_capacities,
            "pending_route_reservations": observation.pending_route_reservations,
            "goals": observation.train_goals,
        }
        return "公开约束表：" + json.dumps(
            table,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: list(value) if isinstance(value, tuple) else str(value),
        )
    return None


def v6_public_history(rows: list[dict[str, Any]], *, limit: int | None = 5) -> str | None:
    if not rows:
        return None
    selected = rows if limit is None else rows[-limit:]
    label = "完整公开轨迹：" if limit is None else "最近公开轨迹："
    return label + json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def v6_initial_map08_hypothesis_table(candidate_sites: tuple[str, ...]) -> dict[str, Any]:
    sites = tuple(candidate_sites)
    table: dict[str, Any] = {}
    for site in sites:
        table[f"belief_{site}"] = 1.0 / len(sites)
    table["test_X_result"] = None
    table["test_Y_result"] = None
    table["next_test"] = "X"
    return table

