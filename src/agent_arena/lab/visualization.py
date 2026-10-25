"""地图专属可视化 view-model（只读公开 trace）。

硬约束：

- 只接收已公开的 ``decision`` 事件、``agent_event`` 与结果里的公开字段；
- **不在页面里重新执行环境**，不读取 ``judge_state`` / ``sealed_truth``；
- MAP-22 只画 Agent **实际发现**的路标与走过的边，绝不绘制隐藏地图；
- MAP-30 不提前揭示未发现的物证；
- 数据不足时给出可解释空态（``available=False`` + ``empty_reason``），不编造。

所有 view-model 都是可 JSON 序列化的纯 dict，UI 只做渲染。
"""

from __future__ import annotations

from typing import Any

VIEW_MODEL_SCHEMA = "v12-lab-view-1"

#: 六张重点地图的专属视图。
FOCUS_MAPS: tuple[str, ...] = (
    "MAP-08",
    "MAP-16",
    "MAP-18",
    "MAP-22",
    "MAP-26",
    "MAP-30",
)

KIND_BY_MAP: dict[str, str] = {
    "MAP-08": "diagnosis_funnel",
    "MAP-16": "occupancy_timeline",
    "MAP-18": "recovery_gantt",
    "MAP-22": "exploration_graph",
    "MAP-26": "maintenance_chain",
    "MAP-30": "evidence_chain",
}

TITLE_BY_KIND: dict[str, str] = {
    "diagnosis_funnel": "诊断漏斗：候选集合收缩与测试",
    "occupancy_timeline": "节点/区段占用时间线",
    "recovery_gantt": "故障与恢复调度时间线",
    "exploration_graph": "已发现区域探索图（仅公开路标）",
    "maintenance_chain": "测试 → 诊断 → 更换 → 回滚事件链",
    "evidence_chain": "证据卡片与法庭窗口",
    "generic_progress": "通用资源/进度与动作分布",
}


def _action(step: dict[str, Any]) -> dict[str, Any]:
    action = step.get("action")
    return dict(action) if isinstance(action, dict) else {}


def _tool(step: dict[str, Any]) -> str:
    return str(_action(step).get("tool") or "")


def _observation(step: dict[str, Any]) -> dict[str, Any]:
    payload = step.get("observation_after")
    return dict(payload) if isinstance(payload, dict) else {}


def _base(
    map_id: str,
    kind: str,
    *,
    steps: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": VIEW_MODEL_SCHEMA,
        "map_id": map_id,
        "kind": kind,
        "title": TITLE_BY_KIND.get(kind, kind),
        "source": "public_trace",
        "available": True,
        "empty_reason": "",
        "steps": len(steps),
        "mode": result.get("mode"),
        "agent": result.get("agent"),
        "state": result.get("state"),
        "success": bool(result.get("success")),
        "metrics": result.get("metrics") or {},
        "metric_specs": result.get("metric_specs") or [],
        "notes": [],
    }


def _empty(map_id: str, kind: str, reason: str, result: dict[str, Any]) -> dict[str, Any]:
    payload = _base(map_id, kind, steps=[], result=result)
    payload["available"] = False
    payload["empty_reason"] = reason
    return payload


# --------------------------------------------------------------------- MAP-08
def _map08(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-08", "diagnosis_funnel", "本局没有动作记录。", result)
    payload = _base("MAP-08", "diagnosis_funnel", steps=steps, result=result)
    starting = result.get("starting_observation") or {}
    previous = list(starting.get("candidate_sites") or [])
    funnel: list[dict[str, Any]] = [
        {
            "step": 0,
            "candidate_sites": previous,
            "candidate_count": len(previous),
            "event": "initial",
            "tick": starting.get("tick"),
        }
    ]
    tests: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    for step in steps:
        action = _action(step)
        observation = _observation(step)
        tool = _tool(step)
        candidates = list(observation.get("candidate_sites") or previous)
        entry = {
            "step": int(step.get("decision_index") or 0),
            "tool": tool,
            "result": str(step.get("result") or ""),
            "candidate_sites": candidates,
            "candidate_count": len(candidates),
            "tick": observation.get("tick"),
            "event": "action",
        }
        if tool == "run_test":
            tests.append(
                {
                    "step": entry["step"],
                    "test_id": action.get("test_id"),
                    "result": entry["result"],
                    "candidate_count_after": len(candidates),
                    "partition": (observation.get("test_partitions") or {}).get(
                        str(action.get("test_id"))
                    ),
                }
            )
            entry["event"] = "test"
        elif tool == "seal_diagnosis":
            entry["event"] = "seal"
            entry["sealed_diagnosis"] = observation.get("sealed_diagnosis")
        elif tool == "repair":
            repairs.append(
                {
                    "step": entry["step"],
                    "target_id": action.get("target_id"),
                    "result": entry["result"],
                    "wrong_repairs": observation.get("wrong_repairs"),
                }
            )
            entry["event"] = "repair"
        funnel.append(entry)
        previous = candidates
    payload.update(
        {
            "funnel": funnel,
            "tests": tests,
            "repairs": repairs,
            "deadline_tick": (result.get("starting_observation") or {}).get("deadline_tick"),
            "sealed_diagnosis": funnel[-1].get("sealed_diagnosis")
            if funnel[-1].get("sealed_diagnosis") is not None
            else None,
            "final_candidates": previous,
        }
    )
    payload["notes"].append(
        "候选集合只来自公开 candidate_sites；测试分区来自公开 test_partitions。"
    )
    return payload


# --------------------------------------------------------------------- MAP-16
def _map16(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-16", "occupancy_timeline", "本局没有动作记录。", result)
    payload = _base("MAP-16", "occupancy_timeline", steps=steps, result=result)
    rows: list[dict[str, Any]] = []
    conflicts = 0
    for step in steps:
        observation = _observation(step)
        result_text = str(step.get("result") or "")
        if "CONFLICT" in result_text or "DEADLOCK" in result_text:
            conflicts += 1
        rows.append(
            {
                "step": int(step.get("decision_index") or 0),
                "tick": observation.get("tick"),
                "tool": _tool(step),
                "result": result_text,
                "train_positions": observation.get("train_positions") or {},
                "occupied_nodes": observation.get("occupied_nodes") or [],
                "pending_reservations": observation.get("pending_route_reservations") or {},
                "conflict": "CONFLICT" in result_text or "DEADLOCK" in result_text,
            }
        )
    starting = result.get("starting_observation") or {}
    payload.update(
        {
            "topology": starting.get("topology") or {},
            "siding_nodes": starting.get("siding_nodes") or [],
            "train_goals": starting.get("train_goals") or {},
            "timeline": rows,
            "conflict_events": conflicts,
        }
    )
    if not rows:
        payload["notes"].append("没有可绘制的时间线数据。")
    return payload


# --------------------------------------------------------------------- MAP-18
def _map18(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-18", "recovery_gantt", "本局没有动作记录。", result)
    payload = _base("MAP-18", "recovery_gantt", steps=steps, result=result)
    gantt: list[dict[str, Any]] = []
    closed_ticks: list[dict[str, Any]] = []
    for step in steps:
        observation = _observation(step)
        result_text = str(step.get("result") or "")
        closed = observation.get("closed_segments") or []
        if closed:
            closed_ticks.append(
                {
                    "step": int(step.get("decision_index") or 0),
                    "tick": observation.get("tick"),
                    "segments": closed,
                }
            )
        gantt.append(
            {
                "step": int(step.get("decision_index") or 0),
                "tick": observation.get("tick"),
                "tool": _tool(step),
                "result": result_text,
                "positions": observation.get("train_positions") or {},
                "delivered": observation.get("delivered_passengers"),
                "canceled": observation.get("canceled_passengers"),
                "task_status": observation.get("task_status") or {},
                "closed_segments": closed,
                "recovery_status": observation.get("recovery_status"),
                "window_violation": "DISPATCH_WINDOW" in result_text,
            }
        )
    starting = result.get("starting_observation") or {}
    payload.update(
        {
            "timeline": gantt,
            "closed_ticks": closed_ticks,
            "task_routes": starting.get("task_routes") or {},
            "dispatch_windows": starting.get("published_dispatch_windows") or {},
            "horizon": starting.get("horizon"),
            "success_threshold": starting.get("success_threshold_passengers"),
            "delivered_final": (gantt[-1].get("delivered") if gantt else None),
        }
    )
    return payload


# --------------------------------------------------------------------- MAP-22
def _map22(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-22", "exploration_graph", "本局没有动作记录。", result)
    payload = _base("MAP-22", "exploration_graph", steps=steps, result=result)
    starting = result.get("starting_observation") or {}
    current = str(starting.get("current_sign") or "")
    nodes: dict[str, dict[str, Any]] = {}
    if current:
        nodes[current] = {"sign": current, "first_seen_step": 0, "visits": 1}
    edges: list[dict[str, Any]] = []
    route: list[dict[str, Any]] = []
    rejected_moves: list[dict[str, Any]] = []
    for step in steps:
        action = _action(step)
        observation = _observation(step)
        tool = _tool(step)
        after = str(observation.get("current_sign") or "")
        if tool == "move" and after:
            bearing = str(action.get("bearing") or "")
            result_text = str(step.get("result") or "")
            rejected = result_text.startswith(
                ("BEARING_", "NOT_", "INVALID", "ACTION_NOT")
            ) or after == current
            if rejected:
                # 被环境拒绝的移动没有改变位置：不能画成一条“走过的边”。
                rejected_moves.append(
                    {
                        "step": int(step.get("decision_index") or 0),
                        "bearing": bearing,
                        "result": result_text,
                        "sign": after,
                    }
                )
            else:
                edges.append(
                    {
                        "from": current,
                        "bearing": bearing,
                        "to": after,
                        "step": int(step.get("decision_index") or 0),
                        "accepted": True,
                    }
                )
                route.append(
                    {
                        "step": int(step.get("decision_index") or 0),
                        "bearing": bearing,
                        "to": after,
                        "moves_used": observation.get("moves_used"),
                    }
                )
                current = after
        if after:
            node = nodes.setdefault(
                after,
                {
                    "sign": after,
                    "first_seen_step": int(step.get("decision_index") or 0),
                    "visits": 0,
                },
            )
            node["visits"] = int(node["visits"]) + 1
    notes = list(result.get("agent_notes") or [])
    if not notes:
        notes = list((steps[-1].get("observation_after") or {}).get("agent_notes") or [])
    payload.update(
        {
            "nodes": sorted(nodes.values(), key=lambda item: int(item["first_seen_step"])),
            "edges": edges,
            "route": route,
            "discovered_node_count": len(nodes),
            "rejected_moves": rejected_moves,
            "moves_used": (steps[-1].get("observation_after") or {}).get("moves_used"),
            "move_budget": starting.get("move_budget"),
            "ruin_recorded": (steps[-1].get("observation_after") or {}).get("ruin_recorded"),
            "agent_notes": notes,
        }
    )
    payload["notes"].append(
        "只绘制 Agent 实际到达过的路标与走过的边；未到达区域不显示（隐藏地图不公开）。"
    )
    return payload


# --------------------------------------------------------------------- MAP-26
def _map26(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-26", "maintenance_chain", "本局没有动作记录。", result)
    payload = _base("MAP-26", "maintenance_chain", steps=steps, result=result)
    chain: list[dict[str, Any]] = []
    for step in steps:
        action = _action(step)
        observation = _observation(step)
        tool = _tool(step)
        node = {
            "step": int(step.get("decision_index") or 0),
            "tool": tool,
            "result": str(step.get("result") or ""),
            "spares": observation.get("spares") or {},
            "wear": observation.get("wear"),
            "installed_part": observation.get("installed_part"),
            "rollbacks_used": observation.get("rollbacks_used"),
        }
        if tool == "run_test":
            node["node_type"] = "test"
            node["test_id"] = action.get("test_id")
        elif tool == "read_log":
            node["node_type"] = "log"
            node["log_id"] = action.get("log_id")
        elif tool == "replace":
            node["node_type"] = "replace"
            node["part_id"] = action.get("part_id")
        elif tool == "rollback":
            node["node_type"] = "rollback"
        elif tool == "restart":
            node["node_type"] = "restart"
        else:
            node["node_type"] = "other"
        chain.append(node)
    payload.update(
        {
            "chain": chain,
            "spares_start": (result.get("starting_observation") or {}).get("spares"),
            "deadline_tick": (result.get("starting_observation") or {}).get("deadline_tick"),
            "max_wear": (result.get("starting_observation") or {}).get("max_wear"),
            "final_wear": (steps[-1].get("observation_after") or {}).get("wear"),
        }
    )
    return payload


# --------------------------------------------------------------------- MAP-30
def _map30(steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty("MAP-30", "evidence_chain", "本局没有动作记录。", result)
    payload = _base("MAP-30", "evidence_chain", steps=steps, result=result)
    starting = result.get("starting_observation") or {}
    recorded: dict[str, dict[str, Any]] = {}
    interviews: list[dict[str, Any]] = []
    accusations: list[dict[str, Any]] = []
    for step in steps:
        action = _action(step)
        observation = _observation(step)
        tool = _tool(step)
        casebook = observation.get("casebook") or {}
        if tool == "record":
            entry_id = str(action.get("entry_id") or "")
            recorded[entry_id] = {
                "entry_id": entry_id,
                "step": int(step.get("decision_index") or 0),
                "result": str(step.get("result") or ""),
                "evidence_ids": action.get("evidence_ids") or [],
                "in_casebook": entry_id in casebook,
            }
        elif tool == "interview":
            interviews.append(
                {
                    "step": int(step.get("decision_index") or 0),
                    "npc_id": action.get("npc_id"),
                    "topic_id": action.get("topic_id"),
                    "shown_evidence_ids": action.get("shown_evidence_ids") or [],
                    "result": str(step.get("result") or ""),
                }
            )
        elif tool == "formal_accuse":
            accusations.append(
                {
                    "step": int(step.get("decision_index") or 0),
                    "person_id": action.get("person_id"),
                    "claims": action.get("event_claims") or [],
                    "result": str(step.get("result") or ""),
                    "rejected": str(step.get("result") or "").startswith(
                        ("EVIDENCE", "CLAIM", "CASE", "ACCUSATION")
                    ),
                }
            )
    requirements = starting.get("entry_requirements") or {}
    cards: list[dict[str, Any]] = []
    for entry_id, needed in requirements.items():
        card = recorded.get(entry_id)
        cards.append(
            {
                "entry_id": entry_id,
                "required_evidence": list(needed),
                "recorded": card is not None,
                "recorded_evidence": (card or {}).get("evidence_ids") or [],
                "in_casebook": bool((card or {}).get("in_casebook")),
            }
        )
    recent = (steps[-1].get("observation_after") or {}).get("recent_action_window") or []
    payload.update(
        {
            "evidence_cards": cards,
            "recorded_count": sum(1 for card in cards if card["recorded"]),
            "required_count": len(cards),
            "interviews": interviews,
            "accusations": accusations,
            "recent_window": recent,
            "chain_reconciled": (steps[-1].get("observation_after") or {}).get("chain_reconciled"),
            "courtroom_node": starting.get("courtroom_node"),
            "location": (steps[-1].get("observation_after") or {}).get("location"),
        }
    )
    payload["notes"].append("只显示已公开的条目与已出示的证据；未发现的物证不出现。")
    return payload


# -------------------------------------------------------------------- generic
GENERIC_SERIES_KEYS: tuple[str, ...] = (
    "tick",
    "moves_used",
    "delivered_passengers",
    "fuel",
    "oxygen",
    "power",
    "water",
    "spares",
    "wear",
    "candidate_sites",
    "candidate_faults",
)


def _generic(map_id: str, steps: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    if not steps:
        return _empty(map_id, "generic_progress", "本局没有动作记录。", result)
    payload = _base(map_id, "generic_progress", steps=steps, result=result)
    histogram: dict[str, int] = {}
    series: dict[str, list[dict[str, Any]]] = {}
    for step in steps:
        tool = _tool(step) or "<invalid>"
        histogram[tool] = histogram.get(tool, 0) + 1
        observation = _observation(step)
        for key in GENERIC_SERIES_KEYS:
            value = observation.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                series.setdefault(key, []).append(
                    {"step": int(step.get("decision_index") or 0), "value": value}
                )
    payload.update(
        {
            "tool_histogram": dict(sorted(histogram.items(), key=lambda item: -item[1])),
            "series": series,
            "timeline": [
                {
                    "step": int(step.get("decision_index") or 0),
                    "tool": _tool(step),
                    "result": str(step.get("result") or ""),
                    "status": step.get("status"),
                }
                for step in steps
            ],
        }
    )
    if not series:
        payload["notes"].append("该图没有可提取的数值型公开进度字段；只显示动作序列。")
    return payload


_BUILDERS = {
    "MAP-08": _map08,
    "MAP-16": _map16,
    "MAP-18": _map18,
    "MAP-22": _map22,
    "MAP-26": _map26,
    "MAP-30": _map30,
}


def build_view_model(
    map_id: str,
    steps: list[dict[str, Any]],
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """按地图返回专属 view-model；其余 24 图回退到通用视图。"""

    payload = result or {}
    builder = _BUILDERS.get(map_id)
    if builder is None:
        return _generic(map_id, steps, payload)
    return builder(steps, payload)


def available_kinds() -> dict[str, str]:
    return {map_id: KIND_BY_MAP[map_id] for map_id in FOCUS_MAPS}


__all__ = [
    "FOCUS_MAPS",
    "GENERIC_SERIES_KEYS",
    "KIND_BY_MAP",
    "TITLE_BY_KIND",
    "VIEW_MODEL_SCHEMA",
    "available_kinds",
    "build_view_model",
]
