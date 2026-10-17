"""独立复算：MAP-19…MAP-24、MAP-26…MAP-30。

每个函数只读 Trace 的公开 Observation 流、decision result 或 ``judge_state``，
按指标登记公式重新计算；不调用地图的 ``metrics()``、V7 extractor 或 V8 投影。

少数几处需要“冻结常量”才能复算，它们都是判分侧的登记口径，不是运行时状态：

- MAP-19 的 ``EXCEEDANCE_BASELINE=8`` / ``SAFE_TEMPERATURE=10``；
- MAP-23 的 ``SUPPLY_INITIAL=14``；
- MAP-28 的 4 条 ``KEY_EVIDENCE`` 与 4 个 claim 字段；
- MAP-29 的不可靠 NPC 集合 ``{A, B}``；
- MAP-30 的 ``map30_l3_original`` 案卷条目与必需证据（V6 冻结案情）；
- MAP-22/26/30 的 ``legal_action_rate`` 拒绝词表（登记口径）。

Trace 逐行保存了这些动作与结果，因此上述常量只用于公式，不构成对环境的二次调用。
"""

from __future__ import annotations

from agent_arena.v9.metric_checks.base import Check, EvidenceRun

# 登记口径：显式拒绝（不是规则后果）。见 V7 ``common.REJECTED_RESULTS``。
_REJECTED_RESULTS = frozenset(
    {
        "ACTION_NOT_AVAILABLE",
        "ALREADY_TERMINAL",
        "CASEBOOK_ENTRY_NOT_FOUND",
        "CASEBOOK_FULL",
        "COURTROOM_REQUIRED",
        "EVIDENCE_NOT_AVAILABLE",
        "MEMORY_CAPACITY_EXCEEDED",
        "MEMORY_DISABLED",
        "MEMORY_FACT_NOT_OBSERVED",
        "NO_PENDING_ROUTE",
        "NO_SEALANT",
        "NO_SPARE_AVAILABLE",
        "NPC_NOT_HERE",
        "TICK_MISMATCH",
        "TRAIN_LOCKED",
        "UNKNOWN_TRAIN",
    }
)


def _terminal(run: EvidenceRun) -> str | None:
    value = run.judge_state.get("terminal_reason")
    if isinstance(value, str):
        return value
    for item in reversed(run.decisions):
        observation = item.get("observation_after") or {}
        if isinstance(observation.get("terminal_reason"), str):
            return str(observation["terminal_reason"])
    return None


def _status(run: EvidenceRun) -> str:
    value = run.judge_state.get("status")
    return str(value) if isinstance(value, str) else ""


def _is_success(run: EvidenceRun) -> bool:
    return _status(run) == "scenario_success" or bool(run.success)


def _count_result_prefix(run: EvidenceRun, *prefixes: str) -> int:
    return sum(1 for result in run.results() if result.startswith(prefixes))


def _count_result(run: EvidenceRun, *codes: str) -> int:
    wanted = set(codes)
    return sum(1 for result in run.results() if result in wanted)


def _legal_action_rate(run: EvidenceRun) -> float | None:
    decisions = run.decisions
    if not decisions:
        return None
    rejected = 0
    for item in decisions:
        result = str(item.get("result", ""))
        if item.get("invalid_output_reason") is not None:
            rejected += 1
        elif result.startswith("INVALID") or result in _REJECTED_RESULTS:
            rejected += 1
    return round((len(decisions) - rejected) / len(decisions), 6)


# --------------------------------------------------------------------- MAP-19
EXCEEDANCE_BASELINE = 8
SAFE_TEMPERATURE = 10


def map19_exceedance_area(run: EvidenceRun) -> int | None:
    states = run.judge_state.get("settled_states")
    if not isinstance(states, list):
        return None
    return sum(
        max(0, int(temperature) - EXCEEDANCE_BASELINE)
        for state in states
        for temperature in state.values()
    )


def map19_critical_overheat_ticks(run: EvidenceRun) -> int | None:
    states = run.judge_state.get("settled_states")
    if not isinstance(states, list):
        return None
    return sum(
        1
        for state in states
        for temperature in state.values()
        if int(temperature) > SAFE_TEMPERATURE
    )


# --------------------------------------------------------------------- MAP-20
def _map20_states(run: EvidenceRun) -> list[dict[str, int]] | None:
    states = run.judge_state.get("settled_states_tenths")
    if not isinstance(states, list):
        return None
    return [state for state in states if isinstance(state, dict)]


def map20_max_exceedance(run: EvidenceRun) -> int | None:
    states = _map20_states(run)
    if states is None:
        return None
    return max(
        (max(0, int(temperature) - 100) for state in states for temperature in state.values()),
        default=0,
    )


def map20_safe_node_ticks(run: EvidenceRun) -> int | None:
    states = _map20_states(run)
    if states is None:
        return None
    return sum(
        1 for state in states for temperature in state.values() if int(temperature) <= 100
    )


# --------------------------------------------------------------------- MAP-21
def map21_evacuation_coverage(run: EvidenceRun) -> float | None:
    """invested = 1(人员) + 已测量 + 已采样品；成功时 evacuated == invested。"""

    measured = 1 if _count_result_prefix(run, "MEASURED:") else 0
    sampled = 1 if _count_result_prefix(run, "SAMPLE_COLLECTED:") else 0
    invested = 1 + measured + sampled
    evacuated = invested if _is_success(run) else 0
    return round(evacuated / invested, 6)


def map21_late_evacuation(run: EvidenceRun) -> int | None:
    status = _status(run)
    if status in {"running", ""}:
        return None
    return int(_terminal(run) == "FATAL_ERUPTION")


# --------------------------------------------------------------------- MAP-22
def map22_return_success(run: EvidenceRun) -> int:
    return int(_terminal(run) == "RETURNED_TO_CAMP_WITH_RUIN_RECORD")


def map22_legal_action_rate(run: EvidenceRun) -> float | None:
    return _legal_action_rate(run)


# --------------------------------------------------------------------- MAP-23
SUPPLY_INITIAL = 14


def map23_clue_utilization(run: EvidenceRun) -> float:
    clues = run.final.get("clues_received") or []
    reductions = [
        3 - len(clue.get("supports") or [])
        for clue in clues
        if isinstance(clue, dict) and isinstance(clue.get("supports"), list)
    ]
    return round(max(reductions, default=0) / 2, 6)


def map23_cost_per_discovery(run: EvidenceRun) -> float | None:
    if not _is_success(run):
        return None
    supply = run.judge_state.get("supply")
    if not isinstance(supply, int):
        return None
    return round((SUPPLY_INITIAL - supply) / 1, 6)


# --------------------------------------------------------------------- MAP-24
_BRIDGE_EDGES = (frozenset({"A", "B"}), frozenset({"B", "C"}))


def map24_rescue_failure(run: EvidenceRun) -> int:
    return int(_terminal(run) != "ALL_ITEMS_DELIVERED")


def map24_collapsed_edge_attempts(run: EvidenceRun) -> int:
    """坍塌后对已移除桥边的 move 尝试：结果为 MOVE_FAILED_EDGE_CLOSED 的桥边动作。"""

    attempts = 0
    for item in run.decisions:
        if str(item.get("result", "")) != "MOVE_FAILED_EDGE_CLOSED":
            continue
        action = item.get("action") or {}
        origin = (item.get("observation_before") or {}).get("location")
        target = action.get("to")
        if origin is None or target is None:
            continue
        if frozenset({str(origin), str(target)}) in _BRIDGE_EDGES:
            attempts += 1
    return attempts


# --------------------------------------------------------------------- MAP-26
def map26_spares_remaining(run: EvidenceRun) -> int | None:
    at_b = run.judge_state.get("spares_at_B")
    carried = run.judge_state.get("carried")
    if not isinstance(at_b, int) or not isinstance(carried, list):
        return None
    return at_b + len(carried)


def map26_legal_action_rate(run: EvidenceRun) -> float | None:
    return _legal_action_rate(run)


# --------------------------------------------------------------------- MAP-27
def map27_joint_completion_rate(run: EvidenceRun) -> float | None:
    judge = run.judge_state
    if not isinstance(judge.get("objectives"), dict):
        return None
    completed = (
        int(judge.get("relay_state") == "ONLINE")
        + int(judge.get("survivor_state") == "RESCUED")
        + int(judge.get("sample_state") == "SEALED")
    )
    return round(completed / 3, 6)


def map27_resource_conflicts(run: EvidenceRun) -> int | None:
    judge = run.judge_state
    cargo_errors = judge.get("cargo_errors")
    conflict_errors = judge.get("resource_conflict_errors")
    if not isinstance(cargo_errors, int) or not isinstance(conflict_errors, int):
        return None
    return cargo_errors + conflict_errors


# --------------------------------------------------------------------- MAP-28
_KEY_EVIDENCE = (
    "KEY_REGISTER_K3_CELINE",
    "LOCK_ENTRY_K3_2106",
    "PRINT_C7_ROUTE_SV",
    "WITNESS_BASIL_S_WINDOW",
)
_CLAIM_FIELDS = 4


def map28_key_evidence_coverage(run: EvidenceRun) -> float | None:
    recorded = run.judge_state.get("recorded_evidence_ids")
    if not isinstance(recorded, list):
        return None
    covered = sum(1 for evidence_id in _KEY_EVIDENCE if evidence_id in set(recorded))
    return round(covered / len(_KEY_EVIDENCE), 6)


def map28_timeline_constraint_satisfaction(run: EvidenceRun) -> float | None:
    satisfied = run.judge_state.get("satisfied_fields")
    if not isinstance(satisfied, int):
        return None
    return round(satisfied / _CLAIM_FIELDS, 6)


# --------------------------------------------------------------------- MAP-29
_UNRELIABLE_NPCS = frozenset({"A", "B"})


def map29_contradiction_detection_rate(run: EvidenceRun) -> float | None:
    proven = run.judge_state.get("unreliable_proven")
    if not isinstance(proven, list):
        return None
    detected = sum(1 for npc in proven if npc in _UNRELIABLE_NPCS)
    return round(detected / len(_UNRELIABLE_NPCS), 6)


def map29_query_budget_overruns(run: EvidenceRun) -> int | None:
    overruns = run.judge_state.get("overruns")
    if isinstance(overruns, int):
        return overruns
    # 退回 Trace：预算用尽后仍继续提问的拒绝码。
    return _count_result_prefix(run, "QUESTION_BUDGET", "NO_QUESTIONS_REMAINING")


# --------------------------------------------------------------------- MAP-30
#: ``map30_l3_original`` 的冻结案卷定义（4 条条目与各自必需证据）。
_MAP30_ENTRY_ORDER = (
    "Q4_CODEBOOK",
    "EVENT_1_HANDOFF",
    "EVENT_2_WAX",
    "EVENT_3_SIGNAL",
)
_MAP30_ENTRY_REQUIRED = {
    "Q4_CODEBOOK": frozenset({"Q4_CODE_INDEX"}),
    "EVENT_1_HANDOFF": frozenset({"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"}),
    "EVENT_2_WAX": frozenset({"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"}),
    "EVENT_3_SIGNAL": frozenset({"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"}),
}


def map30_evidence_chain_coverage(run: EvidenceRun) -> float | None:
    casebook = run.judge_state.get("casebook")
    if not isinstance(casebook, dict):
        return None
    complete = 0
    for entry_id in _MAP30_ENTRY_ORDER:
        recorded = casebook.get(entry_id)
        if isinstance(recorded, (list, tuple)) and _MAP30_ENTRY_REQUIRED[entry_id].issubset(
            {str(item) for item in recorded}
        ):
            complete += 1
    return round(complete / len(_MAP30_ENTRY_ORDER), 6)


def map30_legal_action_rate(run: EvidenceRun) -> float | None:
    return _legal_action_rate(run)


CHECKS: dict[str, list[Check]] = {
    "MAP-19": [
        Check(
            "map19.temperature_exceedance_area",
            map19_exceedance_area,
            "Σ 已结算区·tick 的 max(0, T−8)（未归一化，与登记分母“有效 tick 数”不一致）",
        ),
        Check(
            "map19.critical_overheat_ticks",
            map19_critical_overheat_ticks,
            "已结算状态中 T>10 的区·tick 计数",
            kind="guardrail",
        ),
    ],
    "MAP-20": [
        Check(
            "map20.max_node_exceedance",
            map20_max_exceedance,
            "所有已结算节点的 max(0, T−100) 最大值（十分之一度）",
        ),
        Check(
            "map20.safe_node_ticks",
            map20_safe_node_ticks,
            "Σ 每 tick 每节点 T<=100 的计数（满值 3×10=30）",
            kind="diagnostic",
        ),
    ],
    "MAP-21": [
        Check(
            "map21.evacuation_coverage",
            map21_evacuation_coverage,
            "invested=1+已测量+已采样品；成功时 evacuated=invested（成功路径恒 1.0）",
        ),
        Check(
            "map21.late_evacuation",
            map21_late_evacuation,
            "终止码映射：FATAL_ERUPTION→1，其余终局→0，运行中→无值",
            kind="diagnostic",
        ),
    ],
    "MAP-22": [
        Check(
            "map22.return_success",
            map22_return_success,
            "terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD",
        ),
        Check(
            "map22.legal_action_rate",
            map22_legal_action_rate,
            "(决策数−被拒数)/决策数；被拒=INVALID* 前缀或登记拒绝词表",
            kind="guardrail",
        ),
    ],
    "MAP-23": [
        Check(
            "map23.clue_utilization",
            map23_clue_utilization,
            "公开 clues_received 中最强支持集 max(3−len(supports))/2",
        ),
        Check(
            "map23.cost_per_discovery",
            map23_cost_per_discovery,
            "(14−终局 supply)/成功发现数；未成功→无值（补满 6 点会低估支出）",
            kind="diagnostic",
        ),
    ],
    "MAP-24": [
        Check(
            "map24.rescue_failure",
            map24_rescue_failure,
            "终局码不是 ALL_ITEMS_DELIVERED 即 1",
        ),
        Check(
            "map24.collapsed_edge_attempts",
            map24_collapsed_edge_attempts,
            "结果为 MOVE_FAILED_EDGE_CLOSED 且边属于 A-B/B-C 桥的计数",
            kind="guardrail",
        ),
    ],
    "MAP-26": [
        Check(
            "map26.spares_remaining",
            map26_spares_remaining,
            "spares_at_B + len(carried)",
        ),
        Check(
            "map26.legal_action_rate",
            map26_legal_action_rate,
            "(决策数−被拒数)/决策数；被拒=INVALID* 前缀或登记拒绝词表",
            kind="guardrail",
        ),
    ],
    "MAP-27": [
        Check(
            "map27.joint_task_completion_rate",
            map27_joint_completion_rate,
            "(中继 ONLINE + 伤员 RESCUED + 样品 SEALED)/3",
        ),
        Check(
            "map27.resource_conflicts",
            map27_resource_conflicts,
            "cargo_errors + resource_conflict_errors",
            kind="guardrail",
        ),
    ],
    "MAP-28": [
        Check(
            "map28.key_evidence_coverage",
            map28_key_evidence_coverage,
            "4 条关键证据中已记录的条数/4",
        ),
        Check(
            "map28.timeline_constraint_satisfaction",
            map28_timeline_constraint_satisfaction,
            "satisfied_fields/4 个 claim 字段",
            kind="diagnostic",
        ),
    ],
    "MAP-29": [
        Check(
            "map29.contradiction_detection_rate",
            map29_contradiction_detection_rate,
            "unreliable_proven ∩ {A,B} 的计数/2",
        ),
        Check(
            "map29.query_budget_overruns",
            map29_query_budget_overruns,
            "judge_state.overruns（缺字段时退回预算拒绝码计数）",
            kind="guardrail",
        ),
    ],
    "MAP-30": [
        Check(
            "map30.evidence_chain_coverage",
            map30_evidence_chain_coverage,
            "冻结案卷 4 条中“必需证据集 ⊆ 已记录”的条目比例",
        ),
        Check(
            "map30.legal_action_rate",
            map30_legal_action_rate,
            "(决策数−被拒数)/决策数；被拒=INVALID* 前缀或登记拒绝词表",
            kind="guardrail",
        ),
    ],
}


__all__ = ["CHECKS"]
