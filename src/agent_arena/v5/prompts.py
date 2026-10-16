"""Public, condition-specific instructions for the V5 pilot."""

from __future__ import annotations

import json
from typing import Any

_MAP_TASKS = {
    "MAP-08": (
        "在 B、D、F 三个候选点中识别唯一漏点并修复。只能使用一份密封剂；"
        "每个普通动作推进 1 tick、每次压力测试推进 2 tick。核心水量必须保持不超过 7.0。"
        "可在 X、Y 做压力测试；基线传感器没有区分能力。修复错误地点会耗尽密封剂并失败。"
    ),
    "MAP-16": (
        "把列车 a 从 A 送到 B，把列车 b 从 B 送到 A。每 tick 先预约路线，再调用 move_train"
        "同时移动；单线区段和站点容量均为 1，避让站 D 可用于安全让行。避免对向冲突和死锁。"
    ),
    "MAP-18": (
        "在 12 tick 内安全交付至少 13/18 名乘客。按当前公开时刻表逐 tick 联合提交；"
        "只依据当前公开 Observation 中的线路状态和已出现告警调整计划；不得推断未公开的未来故障。"
        "必要时可取消服务、绕行或折返。"
    ),
    "MAP-22": (
        "在 30 次移动内找到 RUIN_TRIPLE_ARCH 并回到 CAMP_LANTERN_RING。只能使用当前位置的"
        "局部出口和已观察路标；先 observe_signpost 才能写对应 node_page，实际走过边后才能写"
        "traversed_edge_page。地图记忆是 Agent-owned；不可臆造未观察的图事实。"
    ),
    "MAP-26": (
        "设备从 T 出发，公开通道为 T-D-A-B；恢复通信并保留至少一个未消耗备件。"
        "日志和三项诊断测试只能在 D 读取，合法日志为 COMM_LOSS_LAST_TRANSMIT，"
        "合法测试为 bus_load、antenna_loopback、software_checksum；备件在 B 领取，"
        "合法部件为 power_regulator、antenna_coupler、software_image，部件在 A 更换。"
        "测试读数和错误替换反馈只能按实际 Observation 使用；错误候选可 rollback，"
        "正确部件更换后在 A restart。"
    ),
    "MAP-30": (
        "限时调查可见公开证据与证词，在 J 用最多四格 casebook 完整、按序说明三段事件、"
        "人员、时间并提交正式指控；证词依赖已公开回执/案卷。"
    ),
}

_ACTION_CONTRACTS = {
    "MAP-08": (
        'action 只可为 move{edge_id:string}、inspect{target_id:"ordinary_sensor"}、'
        'interact{target_id:string,operation:"pressure_test_X"|"pressure_test_Y"|"repair_leak"}、'
        'wait{turns:1}。interact 测试时 target_id 必须是对应 X/Y；'
        'repair_leak 的 target_id 是 B/D/F。'
    ),
    "MAP-16": (
        'action 只可为 inspect_network{}、set_route{train_id:"a"|"b",next_node:string}、'
        'occupy_siding{train_id:"a"|"b",next_node:"D"}、'
        'release_section{train_id:"a"|"b",section_id:string}、move_train{}。'
        '每个工具对象只能含列出的字段。'
    ),
    "MAP-18": (
        'action 只可为 set_timetable{tick:integer,operations:object}；operations 的键为列车 ID，'
        '值只能是 release{op:"release",to:string}、detour{op:"detour",to:string}、'
        'temporary_stop{op:"temporary_stop"}、turnback{op:"turnback",reverse_toward:string,duration_ticks:1|2}、'
        'cancel_service{op:"cancel_service",task_id:string} 之一。无操作的列车不要放入 operations。'
    ),
    "MAP-22": (
        'action 只可为 observe_signpost{}、move{bearing:string}、'
        'write_memory{facts:array}、check_goal{}、return_to_camp{}。'
        'node_page fact 字段为 fact_type:"node_page",sign_id,exit_bearings；'
        'traversed_edge_page fact 字段为 '
        'fact_type:"traversed_edge_page",from_sign_id,departure_bearing,to_sign_id,arrival_reverse_bearing。'
    ),
    "MAP-26": (
        'action 只可为 move{to:string}、read_log{log_id:string}、test{test_id:string}、'
        'take_spare{part_id:string}、replace{part_id:string}、rollback{}、restart{}。'
    ),
    "MAP-30": (
        'action 只可为 move{to:string}、inspect{evidence_id:string}、'
        'interview{npc_id:string,topic_id:string,shown_evidence_ids:array,shown_casebook_entry_ids:array}、'
        'record{entry_id:string,evidence_ids:array}、'
        'submit_intermediate_hypothesis{candidate_person:string,confidence:"low"|"tentative",event_ids_known:array}、'
        'compare_records{entry_ids:array}、formal_accuse{person_id:string,event_claims:array,cited_entry_ids:array}。'
        'event_claims 每项仅含 event_id,time,location,duty_code。'
    ),
}


def system_prompt(map_id: str, condition_id: str) -> str:
    """Build a bounded task prompt using only registered public instructions."""

    condition = {
        "no_hypothesis_table": "本条件不提供跨步假设表；输出 agent_hypothesis_table 必须为 null。",
        "hypothesis_table": (
            "本条件启用 Agent-owned 结构化假设表。每次完整更新 B/D/F 概率、已观察的 X/Y 测试值"
            "与下一测试/修复选择；不得把未观察的测试结果写入表中。"
        ),
        "react": "使用 Observation 直接逐步 ReAct。",
        "constraint_table": (
            "额外收到的约束表由当前公开 Observation 派生；按表规划，但仍须根据实际预约结果行动。"
        ),
        "alert_off": "告警通道关闭；不得推断 Observation 未提供的预告信息。",
        "alert_on": "若 Observation 出现告警，应把它当作不确定信息而非确定的路段事实。",
        "history5": "只把最近五条公开轨迹和当前 Observation 当作可见记忆。",
        "history5_graph_memory": (
            "使用最近五条公开轨迹和 Observation 中 Agent-owned 图记忆；"
            "记忆只能依据已观察路标和已走边。"
        ),
        "free_diagnosis": "从初始状态自主诊断；所有测试和维修动作均按当前 Observation 选择。",
        "recovery_full": "这是合法错误替换后的恢复状态；可见完整公开错误反馈。",
        "recovery_hidden": "这是合法错误替换后的恢复状态；替换反馈已隐藏。",
        "recovery_structured": "这是合法错误替换后的恢复状态；错误反馈以结构化公开摘要给出。",
        "history5_casebook": (
            "使用最近五条公开轨迹与 Observation 内的四格案卷；调查笔记只能引用已获公开证据。"
        ),
        "history_full": (
            "使用从调查开始至今的完整公开动作/结果历史及其中已公开的证据、证词细节；"
            "不要把完整历史裁剪为最近五步。"
        ),
    }.get(condition_id)
    if condition is None:
        raise ValueError(f"Unregistered V5 condition: {map_id}/{condition_id}")
    hypothesis_contract = (
        '假设表必须恰好含 belief_B/belief_D/belief_F（number，和为 1）、'
        'test_X_result（"pulse_amber"/"pulse_slate"/null）、test_Y_result（"pulse_cobalt"/"pulse_slate"/null）'
        '和 next_test（"X"/"Y"/"repair"）。'
        if map_id == "MAP-08" and condition_id == "hypothesis_table"
        else "其他条件的 agent_hypothesis_table 必须为 null。"
    )
    return "\n".join(
        [
            f"你正在运行 Agent Arena {map_id}。",
            _MAP_TASKS[map_id],
            _ACTION_CONTRACTS[map_id],
            '"action" 须含 "tool"（动作名）；参数严格按动作契约，禁止用 "verb"。',
            condition,
            "只输出合法 JSON 对象，且顶层只含这 3 个键：",
            '"decision_reason"：string，最多 280 字符；'
            '"action"：object，严格符合本图 Action contract；',
            '"agent_hypothesis_table"：object 或 null。' + hypothesis_contract,
            "不要输出 Markdown、代码围栏、占位符、省略号或 JSON 以外的文字。",
            "Observation 是唯一环境状态来源；不得假设未提供的裁判真值。",
            "decision_reason 仅写一句简短状态，不输出详细推理过程。",
        ]
    )


def condition_memory(
    map_id: str,
    condition_id: str,
    observation: Any,
    hypothesis_table: dict[str, Any] | None,
) -> str | None:
    """Return only registered, Agent-owned or public derived context."""

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
            "goal": observation.train_goals,
        }
        return "公开约束表：" + json.dumps(
            table,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: list(value) if isinstance(value, tuple) else str(value),
        )
    return None


def public_history(rows: list[dict[str, Any]], *, limit: int | None = 5) -> str | None:
    if not rows:
        return None
    selected = rows if limit is None else rows[-limit:]
    label = "完整公开轨迹：" if limit is None else "最近公开轨迹："
    return label + json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def initial_map08_hypothesis_table() -> dict[str, Any]:
    return {
        "belief_B": 0.3333333333,
        "belief_D": 0.3333333333,
        "belief_F": 0.3333333334,
        "test_X_result": None,
        "test_Y_result": None,
        "next_test": "X",
    }
