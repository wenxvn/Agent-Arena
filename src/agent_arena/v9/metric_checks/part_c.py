"""独立复算：MAP-07、MAP-08、MAP-09、MAP-13…MAP-18（Batch 5 第二路径）。

每个函数只读 Trace 的公开 Observation 流、公开动作字段或离线 ``judge_state``，
按登记公式重新计算；**不调用**地图的 ``metrics()``、V7 extractor 或 V8
``project_metrics``。所有输入都来自 ``EvidenceRun``，因此可在无环境实例时复算。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v9.metric_checks.base import Check, EvidenceRun

#: 规则显式拒绝类结果码（“没有推进状态”的接口拒绝）；规则性失败码不在此列。
_REFUSALS = frozenset(
    {
        "ACTION_NOT_AVAILABLE",
        "ACTION_NOT_ALLOWED",
        "ALREADY_TERMINAL",
        "EDGE_NOT_ADJACENT",
        "TARGET_NOT_VISIBLE",
        "P_UNREACHABLE",
    }
)

#: MAP-18 六个任务各 3 名乘客，总需求 18（登记分母，不是从指标里读出的值）。
MAP18_TOTAL_DEMAND = 18


def _is_rejected(row: dict[str, Any]) -> bool:
    """接口层拒绝：schema 非法或结果码以 INVALID / 拒绝码表示。"""

    if row.get("invalid_output_reason"):
        return True
    result = str(row.get("result") or "")
    return result.startswith("INVALID") or result in _REFUSALS


def _terminal(run: EvidenceRun) -> str | None:
    value = run.judge_state.get("terminal_reason")
    if isinstance(value, str):
        return value
    for item in reversed(run.decisions):
        observation = item.get("observation_after") or {}
        if isinstance(observation.get("terminal_reason"), str):
            return str(observation["terminal_reason"])
    return None


def _count_result(run: EvidenceRun, *codes: str) -> int:
    wanted = set(codes)
    return sum(1 for result in run.results() if result in wanted)


def _result_rows(run: EvidenceRun, *tools: str) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    """返回 (action, observation_before, result) 三元组，可按工具过滤。"""

    wanted = set(tools)
    rows: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for item in run.decisions:
        action = item.get("action") or {}
        if wanted and str(action.get("tool")) not in wanted:
            continue
        rows.append((action, item.get("observation_before") or {}, str(item.get("result"))))
    return rows


# --------------------------------------------------------------------- MAP-07
def map07_excess_water_integral(run: EvidenceRun) -> int | None:
    """每个已结算流水 tick 累加 Σ_{A,B,C} max(0, level-2)。"""

    observations = run.observations()
    if not observations:
        return None
    total = 0
    for observation in observations:
        levels = observation.get("water_levels")
        if not isinstance(levels, dict):
            return None
        for node in ("A", "B", "C"):
            value = levels.get(node)
            if not isinstance(value, int):
                return None
            total += max(0, value - 2)
    return total


def map07_overpressure_ticks(run: EvidenceRun) -> int | None:
    """A/B/C 任一 >8 的流水 tick 数（登记溢流线 = 8）。"""

    observations = run.observations()
    if not observations:
        return None
    ticks = 0
    for observation in observations:
        levels = observation.get("water_levels")
        if not isinstance(levels, dict):
            return None
        if any(int(levels.get(node, 0)) > 8 for node in ("A", "B", "C")):
            ticks += 1
    return ticks


# --------------------------------------------------------------------- MAP-08
def _map08_signatures(run: EvidenceRun) -> dict[str, dict[str, str]]:
    """把公开签名文案解析成 ``站点 -> 测试站 -> 读数``。"""

    raw = run.initial.get("known_test_semantics")
    if not isinstance(raw, dict):
        return {}
    table: dict[str, dict[str, str]] = {}
    for station, text in raw.items():
        if not isinstance(station, str) or not isinstance(text, str):
            continue
        for chunk in text.replace(";", "；").split("；"):
            if "读数为" not in chunk:
                continue
            site, _, reading = chunk.partition("读数为")
            site, reading = site.strip(), reading.strip()
            if site and reading:
                table.setdefault(site, {})[station] = reading
    return table


def _map08_test_results(run: EvidenceRun) -> dict[str, str]:
    raw = run.final.get("test_results")
    if not isinstance(raw, dict):
        raw = run.judge_state.get("test_results")
    if not isinstance(raw, dict):
        return {}
    return {str(station): str(reading) for station, reading in raw.items()}


def map08_candidate_reduction(run: EvidenceRun) -> float | None:
    """(N0 - Nf)/N0，Nf 只由公开签名表与已记录测试读数推出。"""

    table = _map08_signatures(run)
    raw = run.initial.get("published_candidate_set")
    if not table or not isinstance(raw, (list, tuple)) or not raw:
        return None
    candidates = [str(item) for item in raw]
    remaining = set(candidates)
    for station, reading in _map08_test_results(run).items():
        narrowed = {
            site for site in remaining if table.get(site, {}).get(station) == reading
        }
        if narrowed:
            remaining = narrowed
    return (len(candidates) - len(remaining)) / len(candidates)


def map08_legal_action_rate(run: EvidenceRun) -> float | None:
    """被规则接受的决策数 / 提交决策数（拒绝码前缀 + 显式拒绝码）。"""

    decisions = run.decisions
    if not decisions:
        return None
    rejected = sum(1 for item in decisions if _is_rejected(item))
    return (len(decisions) - rejected) / len(decisions)


# --------------------------------------------------------------------- MAP-09
def map09_stable_time_ratio(run: EvidenceRun) -> float | None:
    """满足 water_E<=4 且 oxygen_reserve>0 的已结算 tick 数 / 全部 tick。"""

    observations = run.observations()
    if not observations:
        return None
    safe = 0
    for observation in observations:
        water = observation.get("water_E")
        oxygen = observation.get("oxygen_reserve")
        if not isinstance(water, int) or not isinstance(oxygen, int):
            return None
        if water <= 4 and oxygen > 0:
            safe += 1
    return safe / len(observations)


def map09_hard_threshold_breaches(run: EvidenceRun) -> int:
    """1[短路] + 1[氧耗尽] + 1[发报电量不足]；三者互斥地对应终局码。"""

    terminal = _terminal(run)
    breaches = 0
    if terminal == "SHORT_CIRCUIT":
        breaches += 1
    if terminal == "OXYGEN_DEPLETED":
        breaches += 1
    if terminal == "INSUFFICIENT_TRANSMIT_POWER":
        breaches += 1
    return breaches


# --------------------------------------------------------------------- MAP-13
def _map13_slot_positions(layout: dict[str, Any]) -> dict[str, int] | None:
    order = ("N", "E", "S", "W")
    positions: dict[str, int] = {}
    for index, slot in enumerate(order):
        symbol = layout.get(slot)
        if not isinstance(symbol, str):
            return None
        positions[symbol] = index + 1
    return positions


def _map13_layout_for_metrics(run: EvidenceRun) -> dict[str, Any] | None:
    """复演“最后一次被 verify 的布局优先，否则保留的试排”。"""

    trial: dict[str, Any] | None = None
    last_attempted: dict[str, Any] | None = None
    for action, _observation, result in _result_rows(run, "set_trial_layout", "verify_layout"):
        if action.get("tool") == "set_trial_layout":
            if result == "trial_layout_set":
                layout = action.get("layout_by_room")
                trial = layout if isinstance(layout, dict) else None
            continue
        if result in {"GATE_OPENED", "STATE_RESET"}:
            last_attempted = trial
            if result == "STATE_RESET":
                trial = None
    return last_attempted or trial


def _map13_public_predicates(run: EvidenceRun) -> tuple[list[str], bool]:
    """从公开碑文文本识别四条房间谓词，并判断方向钉是否已读。"""

    clues = run.final.get("observed_clues")
    if not isinstance(clues, (list, tuple)):
        clues = run.initial.get("observed_clues") or []
    predicates: list[str] = []
    orientation = False
    for clue in clues:
        text = str((clue or {}).get("text") or "")
        if "从北室起" in text:
            orientation = True
        elif "日" in text and "两端" in text:
            predicates.append("sun_not_end")
        elif "眼" in text and "芦" in text and "右侧" in text:
            predicates.append("eye_right_of_reed")
        elif "甲" in text and "日" in text and "相邻" in text:
            predicates.append("armor_adjacent_to_sun")
        elif "芦" in text and "首槽" in text:
            predicates.append("reed_not_first")
    return predicates, orientation


def map13_constraint_satisfaction_ratio(run: EvidenceRun) -> float | None:
    """(满足的房间谓词数 + 方向钉是否已读) / 5。"""

    layout = _map13_layout_for_metrics(run)
    if layout is None:
        return 0.0
    positions = _map13_slot_positions(layout)
    if positions is None:
        return None
    predicates, orientation = _map13_public_predicates(run)
    if len(predicates) != 4:
        return None
    by_symbol = {symbol: positions.get(symbol, 0) for symbol in ("日", "眼", "芦", "甲")}
    satisfied = 0
    for name in predicates:
        if name == "sun_not_end":
            satisfied += int(by_symbol["日"] in {2, 3})
        elif name == "eye_right_of_reed":
            satisfied += int(by_symbol["眼"] > by_symbol["芦"])
        elif name == "armor_adjacent_to_sun":
            satisfied += int(abs(by_symbol["甲"] - by_symbol["日"]) == 1)
        elif name == "reed_not_first":
            satisfied += int(by_symbol["芦"] != 1)
    satisfied += int(orientation)
    return satisfied / 5


def map13_illegal_door_attempts(run: EvidenceRun) -> int:
    """被拒绝的 verify_layout 次数：未成型试排（ILLEGAL_DOOR）+ 错排（STATE_RESET）。

    登记公式写的是 ``count(ILLEGAL_DOOR)``，运行时实现把错排也计入，两者不一致
    （METRIC_DEFECT）。此处按**实现口径**复算，以便与 V8 落盘值比对。
    """

    return _count_result(run, "ILLEGAL_DOOR", "STATE_RESET")


# --------------------------------------------------------------------- MAP-14
def _map14_answers(run: EvidenceRun) -> int:
    """成功提问数：结果码以 ``ANSWER:`` 开头的 ask。"""

    return sum(
        1
        for _action, _obs, result in _result_rows(run, "ask")
        if result.startswith("ANSWER:")
    )


def map14_minimum_query_gap(run: EvidenceRun) -> int | None:
    """登记公式 max(0, answers - minimum_queries)（含被夹到 0 的缺陷口径）。"""

    minimum = run.judge_state.get("minimum_queries")
    if not isinstance(minimum, int):
        return None
    return max(0, _map14_answers(run) - minimum)


def map14_queries_used(run: EvidenceRun) -> int:
    return _map14_answers(run)


# --------------------------------------------------------------------- MAP-15
def _map15_complement_map(run: EvidenceRun) -> dict[str, str]:
    """从公开训练样例推导互补对；不足时用“剩余两色必互配”补齐。"""

    pairs: dict[str, str] = {}
    colors: set[str] = set()
    for observation in [run.initial, *run.observations()]:
        doors = observation.get("current_door_colors_in_ephemeral_slot_order_if_inspected")
        if isinstance(doors, (list, tuple)):
            colors.update(str(color) for color in doors)
        samples = observation.get("training_sample_log")
        if not isinstance(samples, (list, tuple)):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            wall = str(sample.get("wall_color") or "")
            chosen = str(sample.get("chosen_door_color") or "")
            if not wall or not chosen:
                continue
            colors.update({wall, chosen})
            if sample.get("parity_before_choice") == "odd" and sample.get("result") == "passed":
                pairs[wall] = chosen
    unknown = sorted(colors - set(pairs) - set(pairs.values()))
    if len(unknown) == 2:
        pairs[unknown[0]] = unknown[1]
        pairs[unknown[1]] = unknown[0]
    return pairs


def map15_unseen_transition_accuracy(run: EvidenceRun) -> float | None:
    """已结算 T 预测（显式优先，否则首次选择代理）的正确比例。"""

    pairs = _map15_complement_map(run)
    records: list[bool] = []
    proxy_pending = False
    pending_answer: str | None = None
    for item in run.decisions:
        action = item.get("action") or {}
        result = str(item.get("result") or "")
        before = item.get("observation_before") or {}
        after = item.get("observation_after") or {}
        if action.get("tool") == "predict_transition" and result == "PREDICTION_RECORDED":
            pending_answer = str(action.get("answer") or "")
        if action.get("tool") == "choose_door" and before.get("area") == "T":
            wall = before.get("current_wall_symbol_color_if_inspected")
            doors = before.get("current_door_colors_in_ephemeral_slot_order_if_inspected")
            slot = action.get("slot_index")
            if (
                not isinstance(wall, str)
                or not isinstance(doors, (list, tuple))
                or not isinstance(slot, int)
                or not 1 <= slot <= len(doors)
            ):
                return None
            parity = before.get("current_tick_parity")
            target = wall if parity == "even" else pairs.get(wall)
            if not isinstance(target, str):
                return None
            chosen = str(doors[slot - 1])
            if pending_answer is not None:
                records.append(pending_answer == target)
                pending_answer = None
                proxy_pending = False
            elif proxy_pending:
                records.append(chosen == target)
                proxy_pending = False
        if after.get("area") == "T" and before.get("area") != "T":
            proxy_pending = True
    if not records:
        return None
    return sum(1 for record in records if record) / len(records)


def map15_invalid_transitions(run: EvidenceRun) -> int:
    return _count_result(run, "INVALID_TRANSITION")


# --------------------------------------------------------------------- MAP-16
def map16_legal_reservation_rate(run: EvidenceRun) -> float | None:
    """ROUTE_RESERVED / (set_route + occupy_siding 提交数)。"""

    rows = _result_rows(run, "set_route", "occupy_siding")
    if not rows:
        return None
    accepted = sum(1 for _action, _obs, result in rows if result == "ROUTE_RESERVED")
    return accepted / len(rows)


def map16_deadlock(run: EvidenceRun) -> int:
    return int(_terminal(run) == "DEADLOCK")


# --------------------------------------------------------------------- MAP-17
def map17_service_rate(run: EvidenceRun) -> float | None:
    """目的站下车人数 / 初始需求总数（demand_matrix 合计）。"""

    delivered = run.final.get("delivered_by_od")
    if not isinstance(delivered, dict):
        return None
    demand = run.initial.get("demand_matrix")
    if not isinstance(demand, dict) or not demand:
        return None
    total = sum(int(value) for value in demand.values())
    if total <= 0:
        return None
    return sum(int(value) for value in delivered.values()) / total


def map17_cumulative_wait_person_ticks(run: EvidenceRun) -> int | None:
    """逐次提交 tick 累加“提交开始时仍在站台的人数”。"""

    total = 0
    committed = 0
    for _action, before, result in _result_rows(run, "set_timetable"):
        if result != "TICK_COMMITTED":
            continue
        waiting = before.get("waiting_demand")
        if not isinstance(waiting, dict):
            return None
        total += sum(int(value) for value in waiting.values())
        committed += 1
    if committed == 0:
        return None
    return total


# --------------------------------------------------------------------- MAP-18
def map18_service_rate(run: EvidenceRun) -> float | None:
    delivered = run.final.get("delivered_passengers")
    if not isinstance(delivered, int):
        delivered = run.judge_state.get("delivered")
    if not isinstance(delivered, int):
        return None
    return delivered / MAP18_TOTAL_DEMAND


def map18_station_capacity_violations(run: EvidenceRun) -> int:
    return _count_result(run, "STATION_CAPACITY_EXCEEDED")


CHECKS: dict[str, list[Check]] = {
    "MAP-07": [
        Check(
            "map07.excess_water_integral",
            map07_excess_water_integral,
            "逐流水 tick 的公开水位超额和（Σ max(0, level-2)）",
        ),
        Check(
            "map07.overpressure_ticks",
            map07_overpressure_ticks,
            "任一舱水位 >8 的流水 tick 计数",
            kind="guardrail",
        ),
    ],
    "MAP-08": [
        Check(
            "map08.candidate_reduction",
            map08_candidate_reduction,
            "(N0-Nf)/N0；Nf 由公开签名表 + test_results 复演",
        ),
        Check(
            "map08.legal_action_rate",
            map08_legal_action_rate,
            "非拒绝决策/提交决策（INVALID 前缀与显式拒绝码）",
            kind="diagnostic",
        ),
    ],
    "MAP-09": [
        Check(
            "map09.stable_time_ratio",
            map09_stable_time_ratio,
            "water_E<=4 且 oxygen>0 的已结算 tick 占比",
        ),
        Check(
            "map09.hard_threshold_breaches",
            map09_hard_threshold_breaches,
            "终局码映射：短路/氧耗尽/发报电量不足各计 1",
            kind="guardrail",
        ),
    ],
    "MAP-13": [
        Check(
            "map13.constraint_satisfaction_ratio",
            map13_constraint_satisfaction_ratio,
            "最后一次被 verify 的布局满足的公开碑文谓词 + 方向钉 / 5；"
            "docstring 写“最后一次试排”，按此 R0 应为 0.6 而非 0.2，属 METRIC_DEFECT",
        ),
        Check(
            "map13.illegal_door_attempts",
            map13_illegal_door_attempts,
            "被拒 verify 次数（ILLEGAL_DOOR + STATE_RESET）；"
            "登记公式仅 ILLEGAL_DOOR，属 METRIC_DEFECT",
            kind="guardrail",
        ),
    ],
    "MAP-14": [
        Check(
            "map14.minimum_query_gap",
            map14_minimum_query_gap,
            "max(0, ANSWER 数 - judge minimum_queries)；0 下限使欠问取到最优值，属 METRIC_DEFECT",
        ),
        Check(
            "map14.queries_used",
            map14_queries_used,
            "结果码以 ANSWER: 开头的 ask 计数",
            kind="diagnostic",
        ),
    ],
    "MAP-15": [
        Check(
            "map15.unseen_transition_accuracy",
            map15_unseen_transition_accuracy,
            "T 首次选择代理：公开墙色/奇偶/互补对推目标色后比对",
        ),
        Check(
            "map15.invalid_transitions",
            map15_invalid_transitions,
            "INVALID_TRANSITION 计数",
            kind="guardrail",
        ),
    ],
    "MAP-16": [
        Check(
            "map16.legal_reservation_rate",
            map16_legal_reservation_rate,
            "ROUTE_RESERVED / set_route+occupy_siding 提交数",
        ),
        Check(
            "map16.deadlock",
            map16_deadlock,
            "terminal_reason==DEADLOCK 映射",
            kind="guardrail",
        ),
    ],
    "MAP-17": [
        Check(
            "map17.service_rate",
            map17_service_rate,
            "终局 delivered_by_od 合计 / 初始 demand_matrix 合计",
        ),
        Check(
            "map17.cumulative_wait_person_ticks",
            map17_cumulative_wait_person_ticks,
            "每次 TICK_COMMITTED 前站台 waiting_demand 合计的累加",
            kind="diagnostic",
        ),
    ],
    "MAP-18": [
        Check(
            "map18.service_rate",
            map18_service_rate,
            "终局 delivered_passengers / 18（6 任务×3 人）",
        ),
        Check(
            "map18.station_capacity_violations",
            map18_station_capacity_violations,
            "STATION_CAPACITY_EXCEEDED 计数",
            kind="guardrail",
        ),
    ],
}


__all__ = ["CHECKS"]
