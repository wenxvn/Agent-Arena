# ruff: noqa: E501
"""V10 指标治理：154 项枚举、五态优先级、缺陷处理表与五态核对。

- ``enumerate_specs()``：V7/V8 的 154 条注册指标 + V10 各图 ``METRIC_SPECS``；
- ``schema_hash()``：把两部分规格一起哈希，作为 ``metric_schema_version=v10`` 的身份；
- ``DEFECT_RESOLUTIONS``：V9 failure-taxonomy 中标为 ``METRIC_DEFECT`` 的 20 张图的逐条结论；
- ``audit_states()``：**规格驱动的五态核对**——不信任各图内部计算，只校验“状态与取值”
  是否符合声明（VALID ⇒ 非空且在 valid_range 内；其余态 ⇒ 必须为空）。
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from agent_arena.v7.metrics.registry import all_specs
from agent_arena.v10.metrics.schema import (
    METRIC_SCHEMA_VERSION,
    MetricSpec,
    MState,
    MValue,
    check_range,
    specs_hash,
)
from agent_arena.v10.runtime.catalog import MAP_IDS, V10_MAPS, v10_class

FIVE_STATE_PRIORITY = (
    MState.INVALID_TRACE,
    MState.UNAVAILABLE,
    MState.NOT_APPLICABLE,
    MState.CENSORED,
    MState.VALID,
)

#: V9 failure-taxonomy 中带 ``METRIC_DEFECT`` 标签的全部地图（实测 20 张；
#: 提纲提到的“13 项”是其中被逐条复核的子集，本表按实测清单逐图给出结论）。
DEFECT_RESOLUTIONS: dict[str, tuple[str, str, str]] = {
    "MAP-02": ("response_latency 恒 1", "改用 adaptive_response_within_2；latency 降为 diagnostic", "DCR-09 / V8 只读"),
    "MAP-03": ("long_delay_recall_accuracy 与成功共线", "拆成 code_recall_correct + memory_gap_actions", "DCR-V10-01 §7"),
    "MAP-04": ("earliest_safe_crossing_delay 未走 S_G 时为空；area 无分母", "主指标改 time_margin；零分母 → N/A", "DCR-V10-08 §7"),
    "MAP-05": ("missed_windows 与 effective_signals 口径重叠", "effective_signals 保留 secondary；missed_windows 降 diagnostic", "V9 metric-check §3"),
    "MAP-06": ("info_value_of_observation 恒 None", "改用 risk_time_utility + utility_regret", "DCR-V10-03 §7"),
    "MAP-12": ("survival_days 与 fuel_consumed 口径混用", "改用 research_completion + min_food", "DCR-V10-22 §7"),
    "MAP-13": ("illegal_door_attempts 混合未成型与错排；ratio 未试排给 0", "拆两计数；未试排 → N/A", "DCR-V10-15 §7"),
    "MAP-14": ("minimum_query_gap 欠问截 0；queries_used 反向", "改用 deduction_success + consistent_hypothesis_rate", "DCR-V10-09 §7"),
    "MAP-15": ("unseen_transition_accuracy 与成功共线", "改用 test_gate_first_try_accuracy + rule_generalization", "DCR-V10-04 §7"),
    "MAP-17": ("overcapacity_events 计入口径错", "按“被拒绝的预约”重算并单列 guardrail", "V9 metric-check §3"),
    "MAP-18": ("replanning 指标在截断预算下误标 valid", "按声明 censored 口径处理；预算与时钟分离", "DCR-V10-02 §7"),
    "MAP-19": ("area 无分母；forecast 误差无出口；coolant_exhausted 恒 0", "area 带分母；新增 mean_forecast_error；删不可达指标", "DCR-V10-10 §7"),
    "MAP-20": ("旁路损耗参数与产能线性冲突", "产能与热量解耦；新增 bypass_used_ticks", "DCR-V10-11 §7"),
    "MAP-21": ("terminal_score 未登记；risk_exposure 奖励直达", "拆分 safety/science/overall；risk_exposure 降 guardrail", "DCR-V10-05 §7"),
    "MAP-22": ("journal 不参与任何指标", "route_recall 直接读 agent_notes", "DCR-V10-12 §7"),
    "MAP-23": ("cost_per_discovery 分母 0；覆盖率计被拒", "clue_utilization 带分母；unjustified 单列", "DCR-V10-13 §7"),
    "MAP-24": ("replanning_latency 对任何非桥边置位；ratio 分母歧义", "改 replan_success + latency(观察后)；ratio 仅最短>0", "DCR-V10-14 §7"),
    "MAP-25": ("覆盖率计入被拒诊断", "按“被接受的诊断”重算", "V9 metric-check §3"),
    "MAP-26": ("tests_run 计入被拒；no_diagnosis 也成功", "改为 spares_used/wrong_swaps/diagnosis_precision", "DCR-V10-17 §7"),
    "MAP-30": ("accusation_claim_precision 统计未进法庭的指控；q4_recall 不要求入卷", "只统计被接受指控；q4 要求条目已记录", "DCR-V10-07 §4"),
}


def enumerate_specs() -> dict[str, Any]:
    v7 = tuple(all_specs())
    v10: list[MetricSpec] = []
    for map_id in sorted(V10_MAPS):
        v10.extend(v10_class(map_id).METRIC_SPECS)
    return {
        "v7_specs": v7,
        "v10_specs": tuple(v10),
        "v7_count": len(v7),
        "v10_count": len(v10),
        "all_ids": [spec.metric_id for spec in v7] + [spec.metric_id for spec in v10],
    }


def schema_hash() -> str:
    payload = enumerate_specs()
    combined = json.dumps(
        {
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "v7": sorted(spec.metric_id for spec in payload["v7_specs"]),
            "v10": specs_hash(payload["v10_specs"]),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(combined.encode("utf-8")).hexdigest()


def primary_policy() -> dict[str, list[str]]:
    """每图的主指标（1–2 条）；跨图只比较语义同构量，不做简单加总。"""

    policy: dict[str, list[str]] = {}
    for map_id in MAP_IDS:
        if map_id not in V10_MAPS:
            continue
        policy[map_id] = [
            spec.metric_id for spec in v10_class(map_id).METRIC_SPECS if spec.role == "primary"
        ]
    return policy


def truncation_censored(map_id: str, metrics: dict[str, Any], *, truncated: bool) -> dict[str, Any]:
    """按各图**声明的**截尾口径，把被预算截断的局统一为 `CENSORED`（DCR-V10-26）。

    背景：各图的 `v10_metrics()` 只检查环境的 `step_limit_reached`，而 V10 runner 的截断
    来自**决策预算**（环境停在 `running`），于是 MAP-10/19/20/22/23 在被截断时仍报 `VALID`、
    MAP-28 报 `NOT_APPLICABLE`，与其 `METRIC_SPECS` 声明的「截尾 → CENSORED」冲突。

    规则（只用规格里已有的文本，不改任何指标定义）：

    - 局被截断 **且** 指标规格的 `censored_rule` 含 `截尾 → CENSORED` **且** 未含
      「部分进度保持 VALID」「仍 VALID」 → `VALID` 改判 `CENSORED`；
    - 局被截断 **且** 规格的 `zero_denominator` 含 `截尾 → CENSORED` → `NOT_APPLICABLE`
      改判 `CENSORED`。
    """

    if not truncated:
        return metrics
    if map_id not in V10_MAPS:
        return metrics
    specs = {spec.metric_id: spec for spec in v10_class(map_id).METRIC_SPECS}
    output: dict[str, Any] = {}
    for metric_id, item in metrics.items():
        spec = specs.get(metric_id)
        if spec is None or not isinstance(item, dict):
            output[metric_id] = item
            continue
        rule = spec.censored_rule
        partial_ok = "部分进度保持 VALID" in rule or "仍 VALID" in rule
        valid_to_censored = "截尾 → CENSORED" in rule and not partial_ok
        na_to_censored = "截尾 → CENSORED" in spec.zero_denominator
        state = item.get("state")
        if (state == "VALID" and valid_to_censored) or (
            state == "NOT_APPLICABLE" and na_to_censored
        ):
            output[metric_id] = {"state": "CENSORED", "value": None, "note": "预算截尾"}
        else:
            output[metric_id] = item
    return output


def audit_states(map_id: str, seed: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """规格驱动的五态核对（独立于各图内部计算）。"""

    from agent_arena.v10.baselines.runner import run_actions

    run = run_actions(map_id, actions, environment_seed=seed)
    specs = {spec.metric_id: spec for spec in v10_class(map_id).METRIC_SPECS}
    violations: list[str] = []
    checked = 0
    for metric_id, value in run.metrics.items():
        spec = specs.get(metric_id)
        if spec is None:
            violations.append(f"{metric_id}: 投影指标没有注册规格")
            continue
        checked += 1
        state = value.get("state")
        raw = value.get("value")
        if state == "VALID":
            mvalue = MValue(MState(state), raw)
            if raw is None or not check_range(spec, mvalue):
                violations.append(f"{metric_id}: VALID 但取值缺失或越界 ({raw})")
        elif state in {"NOT_APPLICABLE", "CENSORED", "UNAVAILABLE", "INVALID_TRACE"}:
            if raw is not None:
                violations.append(f"{metric_id}: {state} 但取值非空 ({raw})")
        else:
            violations.append(f"{metric_id}: 未知状态 {state}")
    return {
        "map_id": map_id,
        "seed": seed,
        "checked": checked,
        "violations": violations,
        "success": run.success,
        "status": run.status,
    }


__all__ = [
    "DEFECT_RESOLUTIONS",
    "FIVE_STATE_PRIORITY",
    "audit_states",
    "enumerate_specs",
    "primary_policy",
    "schema_hash",
    "truncation_censored",
]
