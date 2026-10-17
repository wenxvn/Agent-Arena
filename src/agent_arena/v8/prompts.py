"""Public-only prompts for the V8 maps.

Every prompt is generated from the map's class metadata, its public action
shapes, the current public Observation and the map module docstring. No judge
state, oracle path, hidden truth or metric value is ever inserted.
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.catalog import CONDITIONS

_FIELD_NOTES = {
    "edge_id": "string，当前 Observation 中 visible_edges/local_neighbors 露出的边标识",
    "to": "string，相邻节点/地点标识",
    "bearing": "string，当前可见出口方位",
    "target": "string，当前地点可见对象",
    "target_id": "string，当前可见目标标识",
    "item_id": "string，物品标识",
    "choice": "string，动作选项",
    "operation": "string，操作名称",
    "turns": "integer，等待回合数",
    "ticks": "integer，等待 tick 数",
    "station": "string，站点标识",
    "day": "integer，日期",
    "slot": "string，时间槽",
    "value": "integer，设定值",
    "answer": "string，回答/预测",
    "from_node": "string，起点",
    "to_node": "string，终点",
    "next_node": "string，下一节点",
    "direction": "string，方向",
    "area": "string，区域",
    "room": "string，房间",
    "name": "string，名称",
    "item": "string，物品",
    "quantity": "integer，数量",
    "slot_index": "integer，槽位序号",
    "sample_id": "string，样本标识",
    "device_id": "string，设备标识",
    "clue_id": "string，线索标识",
    "entrance": "string，入口标识",
    "question_template_id": "string，问询模板标识",
    "layout_by_room": "object，房间到布局的映射",
    "configuration": "integer 数组",
    "configuration_candidate": "integer 数组",
    "claim_id": "string，断言标识",
    "forecast_next": "integer 数组，下一段预测",
    "read_temperature": "string，测温站标识",
    "set_cooling": "integer 数组，冷却设定",
    "adjust_loads": "数组，负载调整",
    "open_bypasses": "object，旁路开关",
    "set_flow_tenths": "integer 数组，流量十分位",
    "reinforced": "boolean",
    "loaded_return": "boolean",
    "rule_id": "string，规则标识",
    "record_id": "string，记录标识",
    "statement_ids": "string 数组",
    "support_ids": "string 数组",
    "against_evidence_ids": "string 数组",
    "unreliability_proof_ids": "string 数组",
    "unreliable_npc_id": "string",
    "event_time": "string",
    "event_location": "string",
    "witness_id": "string",
    "citations_by_claim": "object",
    "tool_ids": "string 数组",
    "diagnosis_code": "string",
    "arguments": "object",
    "truthful_priest_candidate": "string 数组",
    "support_evidence_ids": "string 数组",
    "supporting_sample_ids": "string 数组",
    "commodity": "string",
    "crop": "string",
    "slots": "integer",
    "plan": "string 数组",
    "cost_choice": "fast 或 safe",
    "entries": "string 数组",
    "claims": "对象数组",
    "evidence_ids": "string 数组",
    "entry_ids": "string 数组",
    "shown_evidence_ids": "string 数组",
    "shown_casebook_entry_ids": "string 数组",
    "person_id": "string",
    "candidate_person": "string",
    "confidence": "low 或 tentative",
    "event_ids_known": "string 数组",
    "event_claims": "对象数组，每项 event_id/time/location/duty_code",
    "cited_entry_ids": "string 数组",
    "facts": "对象数组",
    "operations": "object，列车到联合操作的映射",
    "tick": "integer，当前 tick",
    "train_id": "string，列车标识",
    "section_id": "string，区段标识",
    "evidence_id": "string，证据标识",
    "entry_id": "string，案卷条目标识",
}

_CONDITION_NOTES = {
    "hypothesis_table": (
        "本条件启用 Agent 自己的假设表；可用公开测试结果更新，但不得写入未观察事实。"
    ),
    "constraint_table": "本条件启用约束表推理；所有预约仍以实际执行结果为准。",
    "alert_on": "本条件会公开不确定告警；告警不是确定的路段事实。",
    "history5_graph_memory": (
        "本条件允许使用 Observation 中的 Agent-owned 图记忆；只能记录亲历路标与边。"
    ),
    "free_diagnosis": "本条件要求从初始状态自主诊断，测试与维修按当前公开反馈选择。",
    "history5_casebook": "本条件提供结构化案卷；条目只能引用已公开证据。",
}

#: 公开的交互词表。只列“可以被尝试”的字符串，不表示当前位置可执行、
#: 前置条件已满足或顺序正确；这些仍由 Observation 与结果码决定。
_VOCABULARY: dict[str, tuple[str, ...]] = {
    "MAP-01": (
        "inspect(target): power_diagram, scrubber_status, airlock_gauge",
        "pickup(item_id): patch_kit",
        "interact(target, choice): oxygen_relay/start_support, "
        "local_breaker/route_arm, local_breaker/route_support, "
        "hull_panel/apply_patch, main_reactor/reset_bus, "
        "airlock_console/pressure_test, bridge_console/confirm_repair",
        "公开规则：未供氧时每 tick 氧气余量 -1；连续断供超过 3 tick 立即失败；"
        "恢复供氧后断供计数清零。",
        "位置对象：B/H=oxygen_relay；B=bridge_console；H=power_diagram；"
        "O=scrubber_status；P=main_reactor；W=patch_kit, local_breaker, hull_panel；"
        "A=airlock_gauge, airlock_console",
    ),
    "MAP-02": (
        "inspect(target): alarm_panel, core_cradle",
        "pickup(item_id): crew",
        "interact(target, choice): nav_core/brace_in_case, "
        "center_gate/isolate_L1, crew/escort",
        "位置对象：C=alarm_panel, center_gate；R1=core_cradle, nav_core；L2=crew",
    ),
    "MAP-03": (
        "inspect(target): telemetry_panel",
        "interact(target, choice): aux_panel/restore_power, "
        "sample_manifest/read_tag, cryo_case/stabilize_sample, "
        "antenna/repair, telemetry/transmit",
        "submit(target, answer): route_console（answer 使用已读到的航线码）",
        "位置对象：D1=aux_panel；U1=sample_manifest, cryo_case；"
        "U2=route_console；U3=telemetry_panel, telemetry；V=antenna",
    ),
    "MAP-04": (
        "inspect(target): tide_gauge（任意位置可读当前相位）",
        "pickup(item_id): wick",
        "interact(target, choice): lamp/fit_wick, lamp/ignite",
        "位置对象：T=lamp；G=wick",
    ),
    "MAP-05": (
        "inspect(target_id): schedule_chart",
        "switch_power(station): R, B, W",
        "interact(target_id, operation): R|B|W 配合 "
        "calibrate_align, calibrate_phase_lock, send_signal",
        "位置对象：C=schedule_chart、总电源；R/B/W=各信号站",
    ),
    "MAP-06": (
        "inspect(target_id): forecast",
        "interact(target_id, operation): P/repair_lighthouse, G/harden",
        "位置对象：Q=forecast；P=repair_lighthouse；G=harden",
    ),
    "MAP-07": (
        "inspect(target_id): water_levels, pipe_diagram",
        "interact(target_id=console, operation): set_valve 配 "
        'arguments={"valve_id": v1|v2|v3|v4, "open": true|false}；'
        "start_pump, stop_pump；predict_next_levels 配 "
        'arguments={"A":int,"B":int,"C":int,"D":int}',
    ),
    "MAP-08": (
        "inspect(target_id): X, Y",
        "interact(target_id, operation): X|Y/pressure_test_X|pressure_test_Y, "
        "B|D|F/repair_leak",
    ),
    "MAP-09": (
        "inspect(target_id): water_gauges, power_panel, oxygen_panel",
        "interact(target_id, operation): E/bulkhead_E_P 配 "
        'arguments={"mode": preserve|sacrifice}；P/pump_once, '
        "E/restore_power_line, O/restart_oxygen, O/replenish_oxygen, "
        "C/send_distress_packet",
    ),
    "MAP-10": (
        "walk(edge_id) / drive_snowmobile(edge_id[, direction])：使用 visible_edges 中的边",
        "load_fuel(quantity): 1..5；set_heating(choice): on|off；"
        "activate_generator()；transmit()；wait(ticks)",
    ),
    "MAP-11": (
        "move(edge_id[, direction, loaded_return])：使用 visible_edges 中的边；"
        "负重返程需 loaded_return=true",
        "scout()；resupply(quantity)；rest()；rescue()",
    ),
    "MAP-12": (
        "set_heating(choice): on|off；start_greenhouse_power()；plant_batch()；"
        "research()；repair_controller()；wait()",
        "transfer(commodity, from_node, to_node, edge_id, quantity): "
        "commodity ∈ food|parts；quantity 为正整数",
    ),
    "MAP-13": (
        "read_inscription(room): C, N, E, S, W",
        "record_constraint(clue_id): 使用 observed_clues 中已读到的 clue_id",
        'set_trial_layout(layout_by_room): {"N": 符号, "E": 符号, "S": 符号, '
        '"W": 符号}，符号 ∈ 日|眼|芦|甲 且各一次',
        "verify_layout()",
    ),
    "MAP-14": (
        "ask(claim_id): A1, A2, B1, B2, C1, C2",
        "compare_evidence(choice, person_id, support_evidence_ids): "
        "choice ∈ A_sun_wheel|B_crescent|C_star_well；"
        "person_id ∈ A_priest|B_priest|C_priest；support 使用 ANSWER_* / "
        "ARCHIVE_NOT_C 等已公开证据 id",
        "submit_configuration(choice): A_sun_wheel|B_crescent|C_star_well",
    ),
    "MAP-15": (
        "inspect_symbols(area): A, B, C, T",
        "choose_door(slot_index): 从 1 开始，最多 4",
        "record_rule(rule_id, supporting_sample_ids): rule_id 为自定义假设名，"
        "supporting_sample_ids 使用 training_sample_log 中的 id",
        "predict_transition(answer): red|blue|gold|green（只在 T 可用）",
    ),
    "MAP-16": (
        "set_route(train_id, next_node): train_id ∈ a|b；next_node 使用 topology 中的节点",
        "occupy_siding(train_id, next_node)；release_section(train_id, section_id)；"
        "inspect_network()；move_train()",
    ),
    "MAP-17": (
        "set_timetable(tick, operations): tick 为 0..11；operations 形如 "
        '{"T_A": {"op": "release", "to": "B"}}',
        "op ∈ release（配 to）|stop（配 board）|switch_line（配 line, board）|delay；"
        "train_id ∈ T_A|T_C|T_D|T_F；board 是 {OD: 人数}",
    ),
    "MAP-18": (
        "set_timetable(tick, operations): operations 形如 "
        '{"T_R1": {"op": "release", "to": "R2"}}',
        "op ∈ release（配 to）|detour（配 to）|temporary_stop|"
        "turnback（配 reverse_toward, duration_ticks）|cancel_service（配 task_id）；"
        "train_id ∈ T_R1|T_R2|T_R3|T_B|T_G|T_X",
    ),
    "MAP-19": (
        "read_temperature(station): A, B, C",
        "set_cooling(set_cooling): 三个 0..2 的整数（A,B,C）",
        "adjust_loads(adjust_loads): 三个 0..2 的整数（停机/降载/满载）",
        "forecast_next(forecast_next): 三个整数；wait()",
    ),
    "MAP-20": (
        "read_temperature(station): A, B, C",
        "set_flow(set_flow_tenths): 直供流量数组（十分之一单位）",
        "open_bypass(open_bypasses): 形如 "
        '{"AB": {"from": "A", "to": "B", "input_tenths": 5}}，link ∈ AB|BC',
        "adjust_loads(adjust_loads): FULL|REDUCED|IDLE 数组；wait()",
    ),
    "MAP-21": (
        "move(edge_id)：使用 available_edges",
        "measure()（2 tick）；reinforce_sample_case()；"
        "collect_and_carry_sample(sample_id): R_SURFACE_ASH|W_LAYERED_CORE|S_DEEP_ISOTOPE",
    ),
    "MAP-22": (
        "move(bearing)：使用 visible_exit_bearings",
        "observe_signpost()；check_goal()；return_to_camp()；"
        "write_memory(facts)（只写亲历的 node_page / traversed_edge_page）",
    ),
    "MAP-23": (
        "investigate(entrance): X, Y, Z；scout() 在 N|R|H 侦察；"
        "mark(choice): X|Y|Z；resupply() 只在 A",
    ),
    "MAP-24": (
        "move(to)：使用 local_connections；take(item_id): relic_C|supply_case_D；"
        "probe_bridge()；measure_tide()；record_route()；wait()",
    ),
    "MAP-25": (
        "move(to): H, T, A, S；inspect(target): equipment|array",
        "equip(item_id): eva_suit|diagnostic_unit|wrench|safety_tether",
        "diagnose(device_id): diagnostic_unit；"
        "repair(target_id, tool_ids[, diagnosis_code]): "
        "target_id=array_fuse_B，tool_ids 需含 diagnostic_unit 与 wrench；"
        "diagnosis_code 使用 diagnose 后公开的值，也可省略",
        "depressurize()；eva_exit()；return_to_A()；pressurize()",
    ),
    "MAP-26": (
        "move(to): D, A, B；read_log(log_id)；test(test_id)；"
        "take_spare(part_id)；replace(part_id)；rollback()；restart()",
    ),
    "MAP-27": (
        "load(item_id): sample_container|medical_kit|relay_repair_kit；"
        "drive(to)；charge()；repair_relay()；sample(item_id)",
        "rescue(operation[, item_id]): field_stabilize（配 medical_kit）|"
        "remote_evacuation；submit()",
    ),
    "MAP-28": (
        "investigate(target_id): vault_lock_events|footprint_trail；"
        "read_record(record_id): key_registry；interview(witness_id): kitchen_cook；"
        "record(clue_id)：使用已观察的具体证据 id",
        "submit(claims, citations_by_claim): claims 形如 "
        '[{"claim_id": "person_id", "value": "..."}]，四个 claim_id 为 '
        "person_id, entry_path_id, entry_time, exit_time；"
        "citations_by_claim 为 {claim_id: [evidence_id, ...]}",
    ),
    "MAP-29": (
        "ask(npc_id, question_template_id): npc_id ∈ A|B|C|D；template ∈ "
        "OPEN_ACCOUNT|TIME_BASIS|LOCATION_BASIS|ARCHIVE_CROSS_INDEX|SOUND_PATTERN",
        "investigate(target_id): study_clock|courtyard_bell_trace；"
        "compare_testimony(npc_id, statement_ids, against_evidence_ids)",
        "submit(event_time, event_location, unreliable_npc_id, support_ids, "
        "unreliability_proof_ids)",
    ),
    "MAP-30": (
        "inspect(evidence_id)；interview(npc_id, topic_id, shown_evidence_ids, "
        "shown_casebook_entry_ids): npc_id ∈ ARCHIVE_CLERK|BANQUET_CLERK|"
        "KITCHEN_COOK|TOWER_WATCH；topic_id ∈ Q4_CODEBOOK|EVENT_1_HANDOFF|"
        "EVENT_2_WAX|EVENT_3_SIGNAL",
        "record(entry_id, evidence_ids)；compare_records(entry_ids)；"
        "submit_intermediate_hypothesis(candidate_person, confidence, event_ids_known)",
        "formal_accuse(person_id, event_claims, cited_entry_ids)",
    ),
}


def vocabulary(environment: MapEnvironment) -> str:
    items = _VOCABULARY.get(environment.map_id)
    if not items:
        return ""
    lines = "\n".join(f"- {item}" for item in items)
    return (
        "可用动作名（只列公开字符串词表；不表示当前位置可执行或顺序正确，"
        "前置条件仍以 Observation 与结果码为准）：\n" + lines + "\n"
    )


def map_docstring(environment: MapEnvironment) -> str:
    text = (type(environment).__doc__ or "").strip().splitlines()
    return text[0].strip() if text else ""


def action_contract(environment: MapEnvironment) -> str:
    lines: list[str] = []
    for tool in sorted(environment.SHAPES):
        variants: list[str] = []
        for shape in sorted(environment.SHAPES[tool], key=lambda item: sorted(item)):
            fields = sorted(set(shape) - {"tool"})
            rendered = ", ".join(
                f'"{field}": {_FIELD_NOTES.get(field, "按 Observation 类型")}'
                for field in fields
            )
            variants.append(
                "{" + '"tool": "' + tool + '"' + (", " + rendered if rendered else "") + "}"
            )
        lines.append(" | ".join(variants))
    return "\n".join(f"- {line}" for line in lines)


def system_prompt(
    environment: MapEnvironment,
    *,
    decision_budget: int,
) -> str:
    condition = CONDITIONS.get(environment.map_id, "default")
    goal = ""
    observation = environment.observe()
    if isinstance(observation.get("goal"), str):
        goal = observation["goal"]
    if not goal:
        goal = map_docstring(environment)
    condition_note = _CONDITION_NOTES.get(condition, "")
    return (
        f"你是 Agent Arena V8 的具身智能体，正在{environment.world}场景「{environment.title}」"
        f"（{environment.level}）中行动。\n"
        f"本图机制：{goal}\n"
        + (f"条件提示：{condition_note}\n" if condition_note else "")
        + "你只能看到下方公开 Observation。不得假设未出现的隐藏状态、未来事件或裁判真值。\n"
        "每步只输出一个 JSON 对象，格式为 "
        '{"decision_reason":"不超过 200 字的公开理由","action":{"tool":"..."}}。'
        "action 的字段组合必须精确匹配下列契约之一；不得添加未列出的字段，也不得提交 null。\n"
        f"动作契约：\n{action_contract(environment)}\n"
        f"{vocabulary(environment)}"
        f"本局最多 {decision_budget} 个决策；超时、资源耗尽、机制失败都是合法结局。"
    )


def user_prompt(
    environment: MapEnvironment,
    *,
    observation: dict[str, Any],
    history: list[dict[str, Any]],
    decision_index: int,
    decision_budget: int,
    correction: str | None = None,
    repeat_hint: str | None = None,
) -> str:
    import json

    parts = [
        f"第 {decision_index}/{decision_budget} 个决策。",
        "当前公开 Observation："
        + json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ]
    if history:
        parts.append(
            "最近公开动作与结果（最多 5 条）："
            + json.dumps(history[-5:], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    if repeat_hint:
        parts.append(repeat_hint)
    if correction:
        parts.append(correction)
    parts.append("只返回规定的 JSON 结构。")
    return "\n".join(parts)


__all__ = ["action_contract", "map_docstring", "system_prompt", "user_prompt", "vocabulary"]
