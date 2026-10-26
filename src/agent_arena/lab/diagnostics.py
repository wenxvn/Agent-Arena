"""证据驱动的失败诊断与两条轨迹的事件序列对照。

原则：

- 每条 ``Finding`` 都指向具体 ``decision`` 事件；不写“模型心里怎么想”；
- 触发规则是可复核的确定性规则（公开动作 + 公开结果 + 公开观察）；
- 信息不足时明确输出 ``NOT_ENOUGH_EVIDENCE``，而不是编造原因；
- Provider 错误、预算截尾、用户取消不伪装成策略失败；
- 核心诊断不需要任何 API；可选的 LLM 解说默认关闭且另行计费（本模块不实现）。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.lab.contracts import Finding, PairwiseDiff
from agent_arena.v10.attribution import MECHANISM_TOOLS
from agent_arena.v10.baselines.runner import REJECT_MARKERS

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

#: 诊断类别（供 UI 与报告分组）。
CATEGORY_LABELS: dict[str, str] = {
    "contract_artifact": "接口假象（非法动作占比过高）",
    "provider_error": "Provider 错误（不是策略失败）",
    "budget_censored": "预算截尾（能力未测完）",
    "cancelled": "运行被取消",
    "interrupted": "运行被中断",
    "repeated_action_loop": "重复动作循环",
    "repeated_rejected_action": "重复被拒动作",
    "no_progress_window": "连续无公开进展",
    "key_action_never_attempted": "核心机制动作从未尝试",
    "key_action_attempted_rejected": "核心机制动作全部被拒",
    "key_action_used_no_trigger": "机制动作被接受但未触发",
    "unused_public_tests": "未使用公开测试就动手",
    "premature_commit": "前置条件未满足就提交",
    "frame_mismatch": "整帧调度语义错误",
    "window_violation": "错失公开窗口",
    "memory_not_used": "未使用公开记忆通道",
    "memory_payload_rejected": "记忆载荷结构不合规（接口问题）",
    "memory_key_not_in_metric": "记忆键名不在指标口径内（口径问题）",
    "memory_sequence_short": "记忆里的路线序列过短（策略问题）",
    "blind_swap": "未诊断就换件",
    "unsupported_accusation": "证据链不完整就指控",
    "not_enough_evidence": "证据不足",
}

NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


def _is_rejected(result: str) -> bool:
    """V10 冻结口径（与 runner 的 ``rejected_actions`` 计数一致）。"""

    return str(result).startswith(REJECT_MARKERS)


#: 诊断层额外承认的“负面结果”前缀/后缀。
#: 这些结果确实表示动作未被环境接受，但不在 V10 冻结的 ``REJECT_MARKERS`` 里
#: （例如 MAP-22 的 ``BEARING_NOT_AVAILABLE``）。诊断只用于解释，不改变任何
#: 已落盘计数口径。
NEGATIVE_PREFIXES: tuple[str, ...] = (
    "NOT_AT_",
    "NOT_",
    "RUIN_NOT_",
    "EVIDENCE_",
    "CLAIM_",
    "CASE_",
    "ACCUSATION_",
    "COMPLETED_",
)
NEGATIVE_SUFFIXES: tuple[str, ...] = (
    "_NOT_AVAILABLE",
    "_NOT_RECORDED",
    "_MISSING",
    "_VIOLATION",
)


def _negative(result: str) -> bool:
    text = str(result)
    if _is_rejected(text):
        return True
    if text.startswith(NEGATIVE_PREFIXES):
        return True
    return text.endswith(NEGATIVE_SUFFIXES)


def _step_id(index: int) -> str:
    return f"step-{index}"


def _tool(step: dict[str, Any]) -> str:
    action = step.get("action")
    if isinstance(action, dict):
        if "invalid_output" in action:
            return "<invalid>"
        tool = action.get("tool")
        if isinstance(tool, str):
            return tool
    return "<none>"


def _signature(step: dict[str, Any]) -> tuple[str, str, str]:
    action = step.get("action")
    payload = json.dumps(action, ensure_ascii=False, sort_keys=True, default=str)
    result = str(step.get("result") or "")
    if "<invalid>" == _tool(step):
        kind = "invalid"
    elif _negative(result):
        kind = "rejected"
    else:
        kind = "ok"
    return (_tool(step), kind, payload)


def _progress_signature(step: dict[str, Any]) -> str:
    observation = step.get("observation_after")
    if not isinstance(observation, dict):
        return ""
    keys = (
        "tick",
        "moves_used",
        "delivered_passengers",
        "candidate_sites",
        "candidate_faults",
        "test_results",
        "installed_part",
        "wear",
        "casebook",
        "ruin_recorded",
        "chain_reconciled",
        "task_status",
        "recent_action_window",
    )
    payload = {key: observation.get(key) for key in keys if key in observation}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _finding(
    *,
    category: str,
    severity: str,
    map_id: str,
    run_id: str,
    summary: str,
    steps: list[int],
    detail: str = "",
    suggested_check: str = "",
    confidence_scope: str = "behavior_observed_not_internal_cause",
) -> Finding:
    return Finding(
        category=category,
        severity=severity,  # type: ignore[arg-type]
        map_id=map_id,
        run_id=run_id,
        evidence_event_ids=tuple(_step_id(index) for index in steps),
        evidence_steps=tuple(steps),
        summary=summary,
        detail=detail,
        suggested_check=suggested_check,
        confidence_scope=confidence_scope,
    )


# ------------------------------------------------------------------ base rules
def _terminal_findings(
    map_id: str, run_id: str, result: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    state = str(result.get("state") or "")
    termination = str(result.get("termination") or "")
    if state == "PROVIDER_ERROR":
        findings.append(
            _finding(
                category="provider_error",
                severity="critical",
                map_id=map_id,
                run_id=run_id,
                summary="Provider 错误导致运行提前结束；本局不能用于能力结论。",
                steps=[],
                detail=f"termination={termination}",
                suggested_check="检查 Provider 连通性/额度后重跑；不要与策略失败混算。",
                confidence_scope="infrastructure_not_behavior",
            )
        )
    elif state == "BUDGET_REACHED":
        findings.append(
            _finding(
                category="budget_censored",
                severity="info",
                map_id=map_id,
                run_id=run_id,
                summary="预算/动作上限耗尽，指标按 CENSORED 处理。",
                steps=[],
                detail=f"termination={termination}",
                suggested_check="提高决策预算或换更短路径的实例后重测，不把截尾当作失败。",
            )
        )
    elif state == "CANCELLED":
        findings.append(
            _finding(
                category="cancelled",
                severity="info",
                map_id=map_id,
                run_id=run_id,
                summary="用户取消；没有终局判定。",
                steps=[],
            )
        )
    elif state == "INTERRUPTED":
        findings.append(
            _finding(
                category="interrupted",
                severity="info",
                map_id=map_id,
                run_id=run_id,
                summary="进程中断；只保留中断前的公开记录。",
                steps=[],
            )
        )
    return findings


def _behavior_findings(
    map_id: str, run_id: str, steps: list[dict[str, Any]]
) -> list[Finding]:
    findings: list[Finding] = []
    if not steps:
        return findings
    decisions = len(steps)

    # 1. 契约假象：非法动作超过一半，结论不可用。
    invalid = [step for step in steps if _tool(step) == "<invalid>"]
    if decisions and len(invalid) / decisions > 0.5:
        findings.append(
            _finding(
                category="contract_artifact",
                severity="critical",
                map_id=map_id,
                run_id=run_id,
                summary=(
                    f"{len(invalid)}/{decisions} 步未通过公开动作契约；"
                    "这是接口假象，不能当作能力差异。"
                ),
                steps=[int(step.get("decision_index") or 0) for step in invalid[:8]],
                detail="非法输出比例 > 50%。",
                suggested_check="先修接口（契约字段/类型）再重跑，勿据此比较架构。",
                confidence_scope="interface_not_behavior",
            )
        )

    # 2. 连续重复动作 / 重复被拒动作。
    signatures = [_signature(step) for step in steps]
    run_start = 0
    for index in range(1, len(signatures) + 1):
        if index < len(signatures) and signatures[index][:2] == signatures[run_start][:2]:
            continue
        length = index - run_start
        if length >= 3:
            window = steps[run_start:index]
            rejected = signatures[run_start][1] == "rejected"
            category = "repeated_rejected_action" if rejected else "repeated_action_loop"
            findings.append(
                _finding(
                    category=category,
                    severity="warning",
                    map_id=map_id,
                    run_id=run_id,
                    summary=(
                        f"连续 {length} 步重复同一动作"
                        + ("且被环境拒绝" if rejected else "，期间没有新的动作选择")
                        + f"：{_tool(window[0])}。"
                    ),
                    steps=[int(step.get("decision_index") or 0) for step in window],
                    detail=f"结果示例：{window[0].get('result')}",
                    suggested_check="对照启用记忆/反思臂后重复是否减少。",
                )
            )
        run_start = index

    # 3. 连续无公开进展。
    progress = [_progress_signature(step) for step in steps]
    start = 0
    for index in range(1, len(progress) + 1):
        if index < len(progress) and progress[index] == progress[start]:
            continue
        length = index - start
        if length >= 4 and progress[start]:
            window = steps[start:index]
            findings.append(
                _finding(
                    category="no_progress_window",
                    severity="warning",
                    map_id=map_id,
                    run_id=run_id,
                    summary=f"连续 {length} 步公开进度没有变化。",
                    steps=[int(step.get("decision_index") or 0) for step in window],
                    suggested_check="检查是否在等待错误的前置条件或陷入无效探索。",
                )
            )
        start = index
    return findings


def _mechanism_findings(
    map_id: str, run_id: str, steps: list[dict[str, Any]], result: dict[str, Any]
) -> list[Finding]:
    tools = set(MECHANISM_TOOLS.get(map_id, ()))
    if not tools:
        return []
    attempts = [step for step in steps if _tool(step) in tools]
    rejected = [step for step in attempts if _negative(str(step.get("result") or ""))]
    accepted = [step for step in attempts if step not in rejected]
    triggered = bool(result.get("mechanism_triggered"))
    if triggered:
        return []
    if not attempts:
        return [
            _finding(
                category="key_action_never_attempted",
                severity="warning",
                map_id=map_id,
                run_id=run_id,
                summary=f"核心机制动作 {sorted(tools)} 一次都没有调用。",
                steps=[],
                suggested_check="先确认模型是否读懂了公开目标与动作契约。",
            )
        ]
    if not accepted:
        return [
            _finding(
                category="key_action_attempted_rejected",
                severity="warning",
                map_id=map_id,
                run_id=run_id,
                summary="机制动作被尝试过，但全部被环境拒绝（前置条件未满足）。",
                steps=[int(step.get("decision_index") or 0) for step in rejected[:8]],
                detail=f"被拒结果示例：{rejected[0].get('result')}",
                suggested_check="对照公开前置条件，检查是否缺少必要的准备动作。",
            )
        ]
    return [
        _finding(
            category="key_action_used_no_trigger",
            severity="warning",
            map_id=map_id,
            run_id=run_id,
            summary="机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。",
            steps=[int(step.get("decision_index") or 0) for step in accepted[:8]],
            suggested_check="检查机制阈值与顺序，而不是只看是否调用了工具。",
        )
    ]


# ------------------------------------------------------- map-specific evidence
def _map08(steps: list[dict[str, Any]], run_id: str) -> list[Finding]:
    findings: list[Finding] = []
    used_tests: list[str] = []
    repaired: list[int] = []
    for step in steps:
        tool = _tool(step)
        action = step.get("action") or {}
        if tool == "run_test":
            used_tests.append(str(action.get("test_id")))
        elif tool == "repair":
            repaired.append(int(step.get("decision_index") or 0))
        elif tool == "seal_diagnosis" and _negative(str(step.get("result") or "")):
            findings.append(
                _finding(
                    category="premature_commit",
                    severity="warning",
                    map_id="MAP-08",
                    run_id=run_id,
                    summary="候选集尚未缩成唯一站点就封存诊断，被环境拒绝。",
                    steps=[int(step.get("decision_index") or 0)],
                    detail=f"结果：{step.get('result')}",
                    suggested_check="先跑公开测试把 candidate_sites 缩到 1 个再封存。",
                )
            )
    if repaired and not used_tests:
        findings.append(
            _finding(
                category="unused_public_tests",
                severity="warning",
                map_id="MAP-08",
                run_id=run_id,
                summary="没有使用任何公开测试就直接维修。",
                steps=repaired[:5],
                suggested_check="对照使用测试的臂，看错修与备件消耗是否下降。",
            )
        )
    if used_tests and len(set(used_tests)) < len(used_tests):
        findings.append(
            _finding(
                category="repeated_rejected_action",
                severity="info",
                map_id="MAP-08",
                run_id=run_id,
                summary="重复使用了同一个公开测试（每测试只能读一次）。",
                steps=[],
                detail=f"测试序列：{used_tests}",
            )
        )
    return findings


def _map16(steps: list[dict[str, Any]], run_id: str) -> list[Finding]:
    findings: list[Finding] = []
    pending_route = False
    for step in steps:
        tool = _tool(step)
        result = str(step.get("result") or "")
        if tool in {"set_route", "occupy_siding"}:
            pending_route = True
        elif tool == "move_train":
            if not pending_route:
                findings.append(
                    _finding(
                        category="frame_mismatch",
                        severity="warning",
                        map_id="MAP-16",
                        run_id=run_id,
                        summary="没有先登记路由就 move_train（整帧提交缺少内容）。",
                        steps=[int(step.get("decision_index") or 0)],
                        detail=f"结果：{result}",
                        suggested_check=(
                            "set_route/occupy_siding 登记下一跳后，再用 move_train 整帧提交。"
                        ),
                    )
                )
            pending_route = False
        elif tool == "release_section":
            findings.append(
                _finding(
                    category="frame_mismatch",
                    severity="info",
                    map_id="MAP-16",
                    run_id=run_id,
                    summary=(
                        "使用了 release_section；"
                        "该图整帧调度应以 set_route + move_train 为主。"
                    ),
                    steps=[int(step.get("decision_index") or 0)],
                )
            )
    return findings


def _map18(steps: list[dict[str, Any]], run_id: str) -> list[Finding]:
    findings: list[Finding] = []
    for step in steps:
        result = str(step.get("result") or "")
        if "DISPATCH_WINDOW" in result:
            findings.append(
                _finding(
                    category="window_violation",
                    severity="warning",
                    map_id="MAP-18",
                    run_id=run_id,
                    summary="在公开发车窗口之前让列车离开起点，整行被拒。",
                    steps=[int(step.get("decision_index") or 0)],
                    detail=f"结果：{result}",
                    suggested_check="对照 published_dispatch_windows 的 release_tick 再提交。",
                )
            )
        elif "TRACK_CLOSED" in result:
            findings.append(
                _finding(
                    category="window_violation",
                    severity="info",
                    map_id="MAP-18",
                    run_id=run_id,
                    summary="进入临时封闭区段，列车原地等待（公开信息）。",
                    steps=[int(step.get("decision_index") or 0)],
                )
            )
    return findings


def _map22(steps: list[dict[str, Any]], run_id: str, result: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    writes = [step for step in steps if _tool(step) == "write_memory"]
    accepted_writes = [
        step for step in writes if not _negative(str(step.get("result") or ""))
    ]
    moves = [
        step
        for step in steps
        if _tool(step) == "move" and not _negative(str(step.get("result") or ""))
    ]
    route_length = len(moves)
    metric_keys = 0
    rejected_payload = 0
    for step in writes:
        result_text = str(step.get("result") or "")
        if result_text == "INVALID_MEMORY_PAYLOAD":
            rejected_payload += 1
        action = step.get("action") or {}
        for fact in action.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            key = fact.get("key")
            if key in {"bearing", "path_state"}:
                metric_keys += 1
                # `path_state` 一条可含多个方位（逗号分隔），按方位数计。
                value = fact.get("value")
                if isinstance(value, str):
                    metric_keys += sum(
                        1 for item in value.split(",") if item.strip()
                    ) - 1
    if rejected_payload:
        findings.append(
            _finding(
                category="memory_payload_rejected",
                severity="critical" if rejected_payload >= max(3, len(writes) // 2) else "warning",
                map_id="MAP-22",
                run_id=run_id,
                summary=(
                    f"{rejected_payload}/{len(writes)} 次 write_memory 因 facts 结构不合规被拒"
                    "（接口问题，不是记忆能力）。"
                ),
                steps=[
                    int(step.get("decision_index") or 0)
                    for step in writes
                    if str(step.get("result") or "") == "INVALID_MEMORY_PAYLOAD"
                ][:8],
                detail="环境要求每条 fact 恰好是 {\"key\": str, \"value\": str}。",
                suggested_check=(
                    "核对公开契约是否把嵌套字段名写清楚（DCR-V12-01）；"
                    "修好后应另立实验，不与旧版本配对。"
                ),
                confidence_scope="interface_not_behavior",
            )
        )
    if not accepted_writes:
        if not rejected_payload:
            findings.append(
                _finding(
                    category="memory_not_used",
                    severity="warning",
                    map_id="MAP-22",
                    run_id=run_id,
                    summary="整局没有写入任何公开记忆；返程只能依赖 5 步历史窗口。",
                    steps=[],
                    suggested_check="对照启用记忆的臂，看 wasted_moves 与返程成功率。",
                )
            )
    elif metric_keys == 0:
        findings.append(
            _finding(
                category="memory_key_not_in_metric",
                severity="warning",
                map_id="MAP-22",
                run_id=run_id,
                summary=(
                    "记忆写入成功，但没有使用指标口径内的键（bearing / path_state），"
                    "因此 route_recall 为 NOT_APPLICABLE。"
                ),
                steps=[int(step.get("decision_index") or 0) for step in accepted_writes[:5]],
                detail=(
                    "公开规则只要求 {key,value}，未说明哪个键会被指标读取；"
                    "这是口径问题，不代表没有记忆（DCR-V12-02）。"
                ),
                suggested_check=(
                    "若要指标可读，写入 key=bearing（单个方位）或 key=path_state"
                    "（逗号分隔的方位序列）。"
                ),
                confidence_scope="metric_coverage_not_behavior",
            )
        )
    elif route_length and metric_keys < max(3, route_length // 2):
        # 键名合规，但写入的方位数量远少于真实移动数 → "记了但太短"（DCR-V12-03）。
        findings.append(
            _finding(
                category="memory_sequence_short",
                severity="warning",
                map_id="MAP-22",
                run_id=run_id,
                summary=(
                    f"记忆里只有 {metric_keys} 个方位，而本局走了 {route_length} 步；"
                    "路线日志不完整，返程无法只靠记忆复现。"
                ),
                steps=[int(step.get("decision_index") or 0) for step in accepted_writes[:5]],
                detail=(
                    "键名已在指标口径内（bearing / path_state），因此这是策略侧的"
                    "跨阶段状态维护问题，不是接口问题（DCR-V12-03）。"
                ),
                suggested_check=(
                    "对照按步追加 bearing 的记忆策略，看 route_recall 与 wasted_moves 是否改善。"
                ),
            )
        )
    if _tool(steps[0]) == "return_to_camp" and not result.get("success"):
        findings.append(
            _finding(
                category="premature_commit",
                severity="warning",
                map_id="MAP-22",
                run_id=run_id,
                summary="一开始就尝试返程，但尚未完成遗迹打卡。",
                steps=[int(steps[0].get("decision_index") or 0)],
                detail=f"结果：{steps[0].get('result')}",
            )
        )
    return findings


def _map26(steps: list[dict[str, Any]], run_id: str) -> list[Finding]:
    findings: list[Finding] = []
    tested = False
    swaps = 0
    rollbacks = 0
    for step in steps:
        tool = _tool(step)
        if tool == "run_test" and not _negative(str(step.get("result") or "")):
            tested = True
        elif tool == "replace":
            swaps += 1
            if not tested:
                findings.append(
                    _finding(
                        category="blind_swap",
                        severity="warning",
                        map_id="MAP-26",
                        run_id=run_id,
                        summary="没有跑任何公开测试就换件（盲换，会消耗备件与磨损）。",
                        steps=[int(step.get("decision_index") or 0)],
                        suggested_check="对照先测试的臂，比较 spares_used 与 wrong_swaps。",
                    )
                )
        elif tool == "rollback":
            rollbacks += 1
    if swaps >= 3:
        findings.append(
            _finding(
                category="blind_swap",
                severity="warning",
                map_id="MAP-26",
                run_id=run_id,
                summary=f"共换件 {swaps} 次、回滚 {rollbacks} 次；备件消耗明显偏高。",
                steps=[],
                suggested_check="先诊断再换件，减少 wrong_swaps。",
            )
        )
    return findings


def _map30(steps: list[dict[str, Any]], run_id: str) -> list[Finding]:
    findings: list[Finding] = []
    recorded: list[str] = []
    for step in steps:
        tool = _tool(step)
        result = str(step.get("result") or "")
        if tool == "record" and not _negative(result):
            action = step.get("action") or {}
            recorded.append(str(action.get("entry_id")))
        elif tool == "formal_accuse":
            if _negative(result):
                findings.append(
                    _finding(
                        category="unsupported_accusation",
                        severity="critical",
                        map_id="MAP-30",
                        run_id=run_id,
                        summary="指控被拒：证据链不完整或引用了未记录的条目。",
                        steps=[int(step.get("decision_index") or 0)],
                        detail=f"结果：{result}",
                        suggested_check="先补齐四个条目与交叉索引，再在法庭节点提交。",
                    )
                )
            elif len(set(recorded)) < 4:
                findings.append(
                    _finding(
                        category="unsupported_accusation",
                        severity="warning",
                        map_id="MAP-30",
                        run_id=run_id,
                        summary=f"提交指控时只记录了 {len(set(recorded))}/4 个条目。",
                        steps=[int(step.get("decision_index") or 0)],
                    )
                )
    return findings


_MAP_RULES = {
    "MAP-08": _map08,
    "MAP-16": _map16,
    "MAP-18": _map18,
    "MAP-26": _map26,
    "MAP-30": _map30,
}


def diagnose_run(
    *,
    map_id: str,
    run_id: str,
    steps: list[dict[str, Any]],
    result: dict[str, Any],
) -> list[Finding]:
    """一局的全部诊断结论（确定性、可复核、按严重度排序）。"""

    findings: list[Finding] = []
    findings.extend(_terminal_findings(map_id, run_id, result))
    if steps:
        findings.extend(_behavior_findings(map_id, run_id, steps))
        findings.extend(_mechanism_findings(map_id, run_id, steps, result))
        rule = _MAP_RULES.get(map_id)
        if rule is not None:
            findings.extend(rule(steps, run_id))
        if map_id == "MAP-22":
            findings.extend(_map22(steps, run_id, result))
    if not findings:
        state = str(result.get("state") or "")
        if state in {"SUCCEEDED", "FAILED"} and steps:
            findings.append(
                _finding(
                    category=NOT_ENOUGH_EVIDENCE,
                    severity="info",
                    map_id=map_id,
                    run_id=run_id,
                    summary="没有命中任何确定性诊断规则；当前证据不足以解释差异。",
                    steps=[],
                    suggested_check="补充更多公开证据或扩大样本，不要据此推断内部原因。",
                )
            )
    findings.sort(key=lambda item: SEVERITY_ORDER.get(item.severity, 9))
    return findings


# ------------------------------------------------------------------- trace diff
def _anchor(step: dict[str, Any]) -> str:
    observation = step.get("observation_after") or {}
    parts = []
    for key in ("tick", "location", "current_sign", "node"):
        if key in observation:
            parts.append(f"{key}={observation[key]}")
    return ",".join(parts)


def pairwise_diff(
    *,
    pairing_key: str,
    left_run_id: str,
    right_run_id: str,
    left_agent: str,
    right_agent: str,
    left_steps: list[dict[str, Any]],
    right_steps: list[dict[str, Any]],
    left_result: dict[str, Any] | None = None,
    right_result: dict[str, Any] | None = None,
    verdict: str = "COMPARABLE",
    reasons: tuple[str, ...] = (),
) -> PairwiseDiff:
    """事件序列对照；步数不一致时用阶段/锚点，而不是硬减第 n 步。"""

    left_signatures = [_signature(step) for step in left_steps]
    right_signatures = [_signature(step) for step in right_steps]
    limit = min(len(left_signatures), len(right_signatures))
    divergence: int | None = None
    for index in range(limit):
        if left_signatures[index][:2] != right_signatures[index][:2]:
            divergence = index
            break
    anchor = ""
    summary = ""
    if divergence is not None:
        left_step = left_steps[divergence]
        right_step = right_steps[divergence]
        anchor = _anchor(left_step) or _anchor(right_step)
        summary = (
            f"第 {divergence + 1} 步首次出现不同行为："
            f"{left_agent} {_tool(left_step)}（{left_step.get('result')}） vs "
            f"{right_agent} {_tool(right_step)}（{right_step.get('result')}）"
        )
    elif len(left_signatures) != len(right_signatures):
        divergence = limit
        anchor = "长度差异"
        summary = (
            f"前 {limit} 步动作一致，但步数不同：{left_agent} {len(left_signatures)} 步 vs "
            f"{right_agent} {len(right_signatures)} 步"
        )
    else:
        summary = "两条轨迹的动作序列完全一致。"

    stage_deltas: list[dict[str, Any]] = []
    left_result = left_result or {}
    right_result = right_result or {}
    for metric_id in sorted(
        set(left_result.get("metrics") or {}) | set(right_result.get("metrics") or {})
    ):
        left_metric = (left_result.get("metrics") or {}).get(metric_id) or {}
        right_metric = (right_result.get("metrics") or {}).get(metric_id) or {}
        if left_metric == right_metric:
            continue
        stage_deltas.append(
            {
                "metric_id": metric_id,
                "left_state": left_metric.get("state"),
                "left_value": left_metric.get("value"),
                "right_state": right_metric.get("state"),
                "right_value": right_metric.get("value"),
            }
        )
    return PairwiseDiff(
        pairing_key=pairing_key,
        left_run_id=left_run_id,
        right_run_id=right_run_id,
        left_agent=left_agent,
        right_agent=right_agent,
        verdict=verdict,
        reasons=tuple(reasons),
        first_divergence_step=None if divergence is None else divergence + 1,
        first_divergence_anchor=anchor,
        first_divergence_summary=summary,
        left_decisions=len(left_steps),
        right_decisions=len(right_steps),
        left_success=bool(left_result.get("success")),
        right_success=bool(right_result.get("success")),
        stage_deltas=tuple(stage_deltas),
    )


def diff_hypotheses(diff: PairwiseDiff) -> list[dict[str, str]]:
    """把 diff 转成“已有证据 / 不足证据 / 下一次可验证假设”。"""

    rows: list[dict[str, str]] = []
    if diff.first_divergence_step is None:
        rows.append(
            {
                "kind": "evidence",
                "text": "两条轨迹动作序列一致；差异只可能来自指标计算或终局判定。",
            }
        )
    else:
        rows.append(
            {
                "kind": "evidence",
                "text": f"首次有意义差异出现在第 {diff.first_divergence_step} 步"
                + (
                    f"（锚点 {diff.first_divergence_anchor}）"
                    if diff.first_divergence_anchor
                    else ""
                )
                + "。",
            }
        )
    if not diff.stage_deltas:
        rows.append({"kind": "gap", "text": "指标层面没有可比较的差异记录。"})
    else:
        for item in diff.stage_deltas[:5]:
            rows.append(
                {
                    "kind": "evidence",
                    "text": (
                        f"{item['metric_id']}：{item['left_state']}={item['left_value']} vs "
                        f"{item['right_state']}={item['right_value']}。"
                    ),
                }
            )
    rows.append(
        {
            "kind": "hypothesis",
            "text": "下一步可验证假设：在该配对 seed 上只改变一个架构开关，"
            "重复同一预算，观察首次差异步是否前移。",
        }
    )
    return rows


def summarize_findings(findings: list[Finding]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
    return {
        "total": len(findings),
        "by_category": dict(sorted(counts.items())),
        "by_severity": {
            severity: sum(1 for item in findings if item.severity == severity)
            for severity in ("critical", "warning", "info")
        },
        "critical": [item.as_dict() for item in findings if item.severity == "critical"],
    }


__all__ = [
    "CATEGORY_LABELS",
    "NOT_ENOUGH_EVIDENCE",
    "SEVERITY_ORDER",
    "diff_hypotheses",
    "diagnose_run",
    "pairwise_diff",
    "summarize_findings",
]
