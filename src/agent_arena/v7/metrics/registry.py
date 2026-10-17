"""V7 metric registry: 30 declared maps, 6 trace-computable extractors.

Design-only maps are registered with ``implemented=False``. Calling
``compute_metrics`` on them raises ``NotImplementedError`` rather than returning
a fabricated zero or a generic score.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import Any, Final

from agent_arena.v7.metrics import map08, map16, map18, map22, map26, map30
from agent_arena.v7.metrics.schema import (
    Direction,
    MetricKind,
    MetricSpec,
    MetricStatus,
    MetricValue,
    TraceFormatError,
    TraceRecord,
)

_RUNTIME_MODULES: Final[dict[str, ModuleType]] = {
    "MAP-08": map08,
    "MAP-16": map16,
    "MAP-18": map18,
    "MAP-22": map22,
    "MAP-26": map26,
    "MAP-30": map30,
}

DesignRow = tuple[str, MetricKind, str, str, Direction, str, str, tuple[str, ...]]

_GENERIC_ADVERSARIAL = (
    "反例、边界和机制差异见同名设计卡的“手算样例 / 反例 / 边界”小节；"
    "不得用通关率或动作数替代该指标。"
)


def _design_specs(map_id: str, rows: Sequence[DesignRow]) -> tuple[MetricSpec, ...]:
    specs: list[MetricSpec] = []
    for metric_id, kind, construct, unit, direction, formula, denominator, sources in rows:
        specs.append(
            MetricSpec(
                metric_id=metric_id,
                map_id=map_id,
                kind=kind,
                construct_name=construct,
                unit=unit,
                direction=direction,
                formula=formula,
                denominator=denominator,
                window="设计态：整局；运行时接入后按设计卡窗口复算",
                applicability="该图全部预登记实例",
                missing_rule="运行时缺少来源事件 → UNAVAILABLE；不得默认为 0",
                censor_rule="预算/provider 截尾 → CENSORED，并保留原因码",
                source_events=sources,
                adversarial_note=_GENERIC_ADVERSARIAL,
                implemented=False,
                doc_ref=f"docs/v7/maps/{map_id}.md",
            )
        )
    return tuple(specs)


_DESIGN_SPECS: Final[tuple[MetricSpec, ...]] = (
    *_design_specs(
        "MAP-01",
        (
            (
                "map01.dependency_satisfaction_rate",
                MetricKind.PRIMARY,
                "按合法先后完成的必需依赖边比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_required_edges / required_edges",
                "必需边数",
                ("interact", "dependency_events"),
            ),
            (
                "map01.longest_oxygen_outage_ticks",
                MetricKind.PRIMARY,
                "供氧中断的最长连续 tick",
                "tick",
                Direction.LOWER_IS_BETTER,
                "max consecutive ticks with oxygen_output=False",
                "episode",
                ("oxygen_output", "tick"),
            ),
            (
                "map01.oxygen_guardrail_violations",
                MetricKind.GUARDRAIL,
                "氧气归零或连续断供超过 3 tick 的硬违例数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(OXYGEN_RESERVE_EXHAUSTED) + count(OXYGEN_SUPPLY_INTERRUPTION_LIMIT)",
                "episode",
                ("terminal_reason", "oxygen_off_ticks"),
            ),
            (
                "map01.dependency_violations",
                MetricKind.DIAGNOSTIC,
                "违反前置顺序的动作次数（失败归因）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(ILLEGAL_PREREQUISITE_ORDER)",
                "episode",
                ("interact result",),
            ),
            (
                "map01.completion_ticks",
                MetricKind.DIAGNOSTIC,
                "成功终局的完成 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "terminal_tick if success else N/A",
                "成功局",
                ("terminal_tick", "terminal_reason"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-02",
        (
            (
                "map02.event_response_latency",
                MetricKind.PRIMARY,
                "泄漏首次公开到首个改变计划的有效动作的延迟",
                "tick",
                Direction.LOWER_IS_BETTER,
                "tick(first plan-changing action after leak) - tick(leak public)",
                "观察到泄漏的 episode",
                ("scheduled_event", "interact"),
            ),
            (
                "map02.dual_objective_completion",
                MetricKind.PRIMARY,
                "救人与导航核封存两个加权目标的明细完成度",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "(w_rescue * rescue_done + w_nav * nav_secured) / (w_rescue + w_nav)",
                "两目标权重和",
                ("milestone_events",),
            ),
            (
                "map02.crew_decompression",
                MetricKind.GUARDRAIL,
                "船员失压事件数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(CREW_DECOMPRESSION)",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map02.stale_plan_actions_after_leak",
                MetricKind.DIAGNOSTIC,
                "泄漏后仍推进旧目标且无收益的动作数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(stale_goal_actions after leak)",
                "泄漏后动作数",
                ("decision.action", "milestone_events"),
            ),
            (
                "map02.completion_ticks",
                MetricKind.DIAGNOSTIC,
                "成功终局的完成 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "terminal_tick if success else N/A",
                "成功局",
                ("terminal_tick", "terminal_reason"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-03",
        (
            (
                "map03.phase_completion_coverage",
                MetricKind.PRIMARY,
                "五个合法里程碑的完成覆盖率",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_milestones / 5",
                "5",
                ("milestone_events",),
            ),
            (
                "map03.long_delay_recall_accuracy",
                MetricKind.PRIMARY,
                "末阶段提交的早期事实（K7/校准码）正确率",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "correct_early_facts / required_early_facts",
                "需提交事实数",
                ("submit", "early_observation"),
            ),
            (
                "map03.phase_order_violations",
                MetricKind.GUARDRAIL,
                "阶段逆序或重复阶段动作数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(PHASE_OUT_OF_ORDER)",
                "episode",
                ("interact result",),
            ),
            (
                "map03.lost_sample",
                MetricKind.DIAGNOSTIC,
                "样本丢失导致的失败（与忘记区分）",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if terminal_reason==SAMPLE_LOST else 0",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map03.completion_ticks",
                MetricKind.DIAGNOSTIC,
                "成功终局的完成 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "terminal_tick if success else N/A",
                "成功局",
                ("terminal_tick", "terminal_reason"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-04",
        (
            (
                "map04.window_hit_rate",
                MetricKind.PRIMARY,
                "可通行窗口内尝试穿越的比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "in_window_crossings / crossing_attempts",
                "穿越尝试数",
                ("move", "tide_phase"),
            ),
            (
                "map04.earliest_safe_crossing_delay",
                MetricKind.PRIMARY,
                "相对最早可行通过 tick 的延迟",
                "tick",
                Direction.LOWER_IS_BETTER,
                "actual_cross_tick - earliest_feasible_tick",
                "成功穿越的 episode",
                ("move", "tide_phase"),
            ),
            (
                "map04.high_tide_entries",
                MetricKind.GUARDRAIL,
                "高水位闯入密道次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(HIGH_TIDE_ENTRY)",
                "episode",
                ("move result",),
            ),
            (
                "map04.stranded_ticks",
                MetricKind.DIAGNOSTIC,
                "被困或被迫回退的 tick 损失",
                "tick",
                Direction.LOWER_IS_BETTER,
                "Σ stranded_ticks + rollback_cost",
                "episode",
                ("move", "wait"),
            ),
            (
                "map04.wait_ticks",
                MetricKind.DIAGNOSTIC,
                "等待相位消耗的 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "count(wait) + ticks waiting for tide window",
                "episode",
                ("wait", "tick"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-05",
        (
            (
                "map05.effective_signals",
                MetricKind.PRIMARY,
                "三束信号中完成校准并有效发射的数量",
                "束",
                Direction.HIGHER_IS_BETTER,
                "count(valid_signal emissions)",
                "3",
                ("interact", "signal_events"),
            ),
            (
                "map05.window_utilization",
                MetricKind.PRIMARY,
                "可完成窗口任务中实际完成的比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_window_tasks / feasible_window_tasks",
                "可完成窗口任务数",
                ("scheduled_windows", "interact"),
            ),
            (
                "map05.power_overcommit",
                MetricKind.GUARDRAIL,
                "共享电力超配次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(POWER_LIMIT_EXCEEDED)",
                "episode",
                ("switch_power result",),
            ),
            (
                "map05.missed_windows",
                MetricKind.DIAGNOSTIC,
                "错过发射窗口数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(window_end without emission)",
                "episode",
                ("scheduled_windows",),
            ),
            (
                "map05.idle_ticks",
                MetricKind.DIAGNOSTIC,
                "已接电塔上无进展的等待 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "idle_ticks_on_powered_tower",
                "episode",
                ("power_state", "tick"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-06",
        (
            (
                "map06.task_success_rate",
                MetricKind.PRIMARY,
                "风险约束下的任务达成率（与暴露风险分开报告）",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_tasks / required_tasks",
                "必需任务数",
                ("milestone_events",),
            ),
            (
                "map06.value_of_information",
                MetricKind.PRIMARY,
                "同天气轨迹下可观测与不可观测的预登记损失差",
                "损失单位",
                Direction.HIGHER_IS_BETTER,
                "loss(no_observation) - loss(with_observation)",
                "配对 episode 对",
                ("weather_observation", "decision"),
            ),
            (
                "map06.high_risk_exposure_ticks",
                MetricKind.GUARDRAIL,
                "风暴临界区暴露 tick",
                "tick",
                Direction.LOWER_IS_BETTER,
                "Σ ticks in high-risk window",
                "episode",
                ("weather_state", "move"),
            ),
            (
                "map06.resource_exhausted",
                MetricKind.DIAGNOSTIC,
                "资源耗尽导致的终止",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if terminal_reason==RESOURCE_EXHAUSTED else 0",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map06.observation_cost",
                MetricKind.DIAGNOSTIC,
                "查询天气观测消耗的 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "query_count * 2",
                "episode",
                ("observe_weather", "tick"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-07",
        (
            (
                "map07.excess_water_integral",
                MetricKind.PRIMARY,
                "三舱水位高于目标带上限 2 的超额水量积分",
                "水位·tick",
                Direction.LOWER_IS_BETTER,
                "Σ_t Σ_c max(0, level_c,t - 2)",
                "有效流水 tick",
                ("water_level", "tick"),
            ),
            (
                "map07.correct_direction_rate",
                MetricKind.PRIMARY,
                "导致目标压力朝期望方向变化的干预比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "correct_direction_interventions / decidable interventions",
                "可判定干预数",
                ("interact", "pressure_state"),
            ),
            (
                "map07.overpressure_ticks",
                MetricKind.GUARDRAIL,
                "超压 tick 数",
                "tick",
                Direction.LOWER_IS_BETTER,
                "count(pressure > safe_limit)",
                "episode",
                ("pressure_state",),
            ),
            (
                "map07.illegal_valve_combo",
                MetricKind.DIAGNOSTIC,
                "非法阀门组合次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(INVALID_VALVE_COMBINATION)",
                "episode",
                ("interact result",),
            ),
            (
                "map07.interventions",
                MetricKind.DIAGNOSTIC,
                "阀门开闭与泵启停的动作数（成本指标）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(valve open/close) + count(pump start/stop)",
                "episode",
                ("interact", "pump_control"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-09",
        (
            (
                "map09.stable_time_ratio",
                MetricKind.PRIMARY,
                "关键系统变量处于安全域的 tick 占比",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "safe_system_ticks / valid_ticks",
                "有效 tick 数",
                ("system_state",),
            ),
            (
                "map09.fault_propagation_scale",
                MetricKind.PRIMARY,
                "受故障传播影响的子系统数",
                "个子系统",
                Direction.LOWER_IS_BETTER,
                "count(subsystems entering unsafe state after first fault)",
                "子系统总数",
                ("system_state", "fault_events"),
            ),
            (
                "map09.hard_threshold_breaches",
                MetricKind.GUARDRAIL,
                "水位/氧气硬阈值突破次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(WATER_HARD_LIMIT) + count(OXYGEN_HARD_LIMIT)",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map09.repair_dependency_violations",
                MetricKind.DIAGNOSTIC,
                "修复依赖违例（失败归因）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(REPAIR_DEPENDENCY_VIOLATION)",
                "episode",
                ("interact result",),
            ),
            (
                "map09.repair_actions",
                MetricKind.DIAGNOSTIC,
                "修线、开氧、补氧、抽水、封舱动作数（成本指标）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(repair/power/oxygen/pump/seal actions)",
                "episode",
                ("interact", "repair_events"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-10",
        (
            (
                "map10.key_task_fuel_efficiency",
                MetricKind.PRIMARY,
                "每单位燃料完成的必需任务数",
                "任务/燃料",
                Direction.HIGHER_IS_BETTER,
                "completed_required_tasks / fuel_consumed",
                "燃料消耗；0 耗则 N/A",
                ("task_events", "fuel_ledger"),
            ),
            (
                "map10.minimum_task_guarantee",
                MetricKind.PRIMARY,
                "最低保障任务达成数",
                "个",
                Direction.HIGHER_IS_BETTER,
                "count(guaranteed_tasks completed)",
                "必需保障任务数",
                ("task_events",),
            ),
            (
                "map10.minimum_base_temperature",
                MetricKind.GUARDRAIL,
                "基地最低温度（安全裕量）",
                "温度",
                Direction.HIGHER_IS_BETTER,
                "min_t base_temperature_t",
                "episode",
                ("base_temperature", "tick"),
            ),
            (
                "map10.base_frozen",
                MetricKind.GUARDRAIL,
                "基地是否冻结（硬失败）",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if terminal_reason==BASE_FROZEN else 0",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map10.fuel_consumed",
                MetricKind.DIAGNOSTIC,
                "整局燃料净消耗（成本指标）",
                "燃料单位",
                Direction.LOWER_IS_BETTER,
                "12 - (fuel_depot + carried_fuel)",
                "episode",
                ("fuel_depot", "carried_fuel"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-11",
        (
            (
                "map11.rescue_count",
                MetricKind.PRIMARY,
                "成功救回的人数",
                "人",
                Direction.HIGHER_IS_BETTER,
                "count(rescued survivors)",
                "失联人数",
                ("rescue", "survivor_state"),
            ),
            (
                "map11.resource_cost_per_rescue",
                MetricKind.PRIMARY,
                "每名获救者的燃料与热量成本",
                "资源/人",
                Direction.LOWER_IS_BETTER,
                "resource_spent / rescued_count",
                "获救人数；0 则 N/A",
                ("fuel_ledger", "heat_ledger"),
            ),
            (
                "map11.rescuer_hypothermia",
                MetricKind.GUARDRAIL,
                "搜救员失温事件数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(RESCUER_HYPOTHERMIA)",
                "episode",
                ("terminal_reason",),
            ),
            (
                "map11.abandoned_reachable_targets",
                MetricKind.DIAGNOSTIC,
                "仍可救援却被放弃的目标数",
                "人",
                Direction.LOWER_IS_BETTER,
                "count(reachable but abandoned survivors)",
                "初始可救援人数",
                ("survivor_state", "rescue"),
            ),
            (
                "map11.first_clue_delay",
                MetricKind.DIAGNOSTIC,
                "首次侦察结果出现的 tick（成本/延迟指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "tick(first scout result); no scout -> N/A",
                "episode",
                ("scout", "tick"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-12",
        (
            (
                "map12.survival_days",
                MetricKind.PRIMARY,
                "满足供热与补给约束的生存天数",
                "天",
                Direction.HIGHER_IS_BETTER,
                "days_with_all_survival_constraints / 30",
                "30",
                ("day_settlement",),
            ),
            (
                "map12.minimum_safety_margin",
                MetricKind.PRIMARY,
                "全周期最小安全库存裕量",
                "库存单位",
                Direction.HIGHER_IS_BETTER,
                "min_t(inventory_t - safety_stock_t)",
                "各日结算点",
                ("inventory_ledger",),
            ),
            (
                "map12.heating_outage_days",
                MetricKind.GUARDRAIL,
                "供热中断天数",
                "天",
                Direction.LOWER_IS_BETTER,
                "count(heating outage days)",
                "30",
                ("day_settlement",),
            ),
            (
                "map12.plan_breach_days",
                MetricKind.DIAGNOSTIC,
                "计划违约天数（失败归因）",
                "天",
                Direction.LOWER_IS_BETTER,
                "count(days with missed planned action)",
                "30",
                ("day_settlement",),
            ),
            (
                "map12.fuel_consumed",
                MetricKind.DIAGNOSTIC,
                "整局燃料净消耗（成本指标）",
                "燃料单位",
                Direction.LOWER_IS_BETTER,
                "40 - fuel_E_30",
                "episode",
                ("fuel_ledger",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-13",
        (
            (
                "map13.constraint_satisfaction_ratio",
                MetricKind.PRIMARY,
                "最终满足的独立符号约束比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "satisfied_constraints / total_constraints",
                "总约束数",
                ("constraint_state",),
            ),
            (
                "map13.correct_sequence",
                MetricKind.PRIMARY,
                "四门进入顺序是否与唯一推导一致",
                "0/1",
                Direction.HIGHER_IS_BETTER,
                "1 if door_order == derived_unique_order else 0",
                "episode",
                ("door_events",),
            ),
            (
                "map13.illegal_door_attempts",
                MetricKind.GUARDRAIL,
                "非法开门尝试次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(ILLEGAL_DOOR)",
                "episode",
                ("interact result",),
            ),
            (
                "map13.state_resets",
                MetricKind.DIAGNOSTIC,
                "错误开启导致的状态重置次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(STATE_RESET)",
                "episode",
                ("state_reset",),
            ),
            (
                "map13.completion_ticks",
                MetricKind.DIAGNOSTIC,
                "成功终局的完成 tick（成本指标）",
                "tick",
                Direction.LOWER_IS_BETTER,
                "terminal_tick if success else N/A",
                "成功局",
                ("terminal_tick", "terminal_reason"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-14",
        (
            (
                "map14.globally_consistent_hypothesis_rate",
                MetricKind.PRIMARY,
                "提交的假设中与全部已公开陈述一致的比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "consistent_hypotheses / submitted_hypotheses",
                "提交假设数",
                ("submit_configuration", "testimony"),
            ),
            (
                "map14.minimum_query_gap",
                MetricKind.PRIMARY,
                "相对同实例最少问询数的差距",
                "次",
                Direction.LOWER_IS_BETTER,
                "queries_used - minimum_queries(instance)",
                "实例最少问询数",
                ("ask", "reference_solution"),
            ),
            (
                "map14.query_budget_overruns",
                MetricKind.GUARDRAIL,
                "问询预算超支次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(QUERY_BUDGET_EXCEEDED)",
                "episode",
                ("ask result",),
            ),
            (
                "map14.contradiction_missed",
                MetricKind.DIAGNOSTIC,
                "未识别矛盾导致的错误提交",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if submit contains known contradiction else 0",
                "episode",
                ("submit_configuration",),
            ),
            (
                "map14.queries_used",
                MetricKind.DIAGNOSTIC,
                "实际问询数（成本指标）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(ask)",
                "episode",
                ("ask",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-15",
        (
            (
                "map15.unseen_transition_accuracy",
                MetricKind.PRIMARY,
                "对未试过状态转换的预测正确率",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "correct_unseen_predictions / evaluable_unseen_predictions",
                "可评估未见预测数",
                ("choose_door", "prediction"),
            ),
            (
                "map15.probes_to_target",
                MetricKind.PRIMARY,
                "到达目标所需试探动作数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(probe actions before target)",
                "episode",
                ("choose_door",),
            ),
            (
                "map15.invalid_transitions",
                MetricKind.GUARDRAIL,
                "无效状态转换次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(INVALID_TRANSITION)",
                "episode",
                ("choose_door result",),
            ),
            (
                "map15.loop_states",
                MetricKind.DIAGNOSTIC,
                "循环状态重复次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(visited state re-entered)",
                "episode",
                ("state_events",),
            ),
            (
                "map15.reset_losses",
                MetricKind.DIAGNOSTIC,
                "错误消耗的资源与额外 tick（成本指标）",
                "资源单位 + tick",
                Direction.LOWER_IS_BETTER,
                "resource_units_lost + extra_ticks",
                "episode",
                ("choose_door result", "tick"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-17",
        (
            (
                "map17.service_rate",
                MetricKind.PRIMARY,
                "按乘客需求权重完成的服务比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "delivered_weight / total_demand_weight",
                "总需求",
                ("passenger_ledger",),
            ),
            (
                "map17.cumulative_wait_person_ticks",
                MetricKind.PRIMARY,
                "累计乘客等待人·tick",
                "人·tick",
                Direction.LOWER_IS_BETTER,
                "Σ passengers × wait_ticks",
                "已服务乘客",
                ("passenger_ledger",),
            ),
            (
                "map17.energy_per_passenger",
                MetricKind.DIAGNOSTIC,
                "每名乘客能耗（Pareto 轴，不与等待隐式加权）",
                "能耗/人",
                Direction.LOWER_IS_BETTER,
                "energy_used / delivered_passengers",
                "已服务乘客；0 则 N/A",
                ("energy_ledger",),
            ),
            (
                "map17.overcapacity_events",
                MetricKind.GUARDRAIL,
                "站台超容量或碰撞事件数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(STATION_CAPACITY) + count(COLLISION)",
                "episode",
                ("terminal_reason",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-19",
        (
            (
                "map19.temperature_exceedance_area",
                MetricKind.PRIMARY,
                "温度超过安全阈值的面积",
                "温度·tick",
                Direction.LOWER_IS_BETTER,
                "Σ max(0, T_t - T_safe) × Δt",
                "有效 tick 数",
                ("read_temperature",),
            ),
            (
                "map19.oscillation_count",
                MetricKind.PRIMARY,
                "阀门/温度控制振荡次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(sign changes of dT/dt within band)",
                "episode",
                ("temperature_trace",),
            ),
            (
                "map19.critical_overheat_ticks",
                MetricKind.GUARDRAIL,
                "临界超温 tick 数",
                "tick",
                Direction.LOWER_IS_BETTER,
                "count(T > critical_limit)",
                "episode",
                ("temperature_trace",),
            ),
            (
                "map19.coolant_exhausted",
                MetricKind.DIAGNOSTIC,
                "冷却剂耗尽终止",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if terminal_reason==COOLANT_EXHAUSTED else 0",
                "episode",
                ("terminal_reason",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-20",
        (
            (
                "map20.max_node_exceedance",
                MetricKind.PRIMARY,
                "最热关键节点的温度越限量",
                "温度单位",
                Direction.LOWER_IS_BETTER,
                "max_node max_t max(0, T_node_t - T_safe)",
                "关键节点数",
                ("read_temperature",),
            ),
            (
                "map20.safe_node_ticks",
                MetricKind.PRIMARY,
                "所有关键节点同时安全的节点·tick",
                "节点·tick",
                Direction.HIGHER_IS_BETTER,
                "Σ_nodes Σ_t [T_node_t <= T_safe]",
                "节点数×有效 tick",
                ("read_temperature",),
            ),
            (
                "map20.flow_conservation_violations",
                MetricKind.GUARDRAIL,
                "流量守恒违例次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(FLOW_CONSERVATION_VIOLATION)",
                "episode",
                ("set_flow result",),
            ),
            (
                "map20.key_node_runaway",
                MetricKind.DIAGNOSTIC,
                "任一关键节点失控的失败归因",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if any key node exceeds hard limit else 0",
                "episode",
                ("terminal_reason",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-21",
        (
            (
                "map21.risk_exposure_integral",
                MetricKind.PRIMARY,
                "喷发风险下的暴露积分",
                "风险·tick",
                Direction.LOWER_IS_BETTER,
                "Σ_t risk_t × people_at_risk_t",
                "有效 tick",
                ("measure", "risk_state"),
            ),
            (
                "map21.evacuation_coverage",
                MetricKind.PRIMARY,
                "成功撤离的人员/资产覆盖比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "evacuated_units / total_units",
                "总撤离单位",
                ("evacuation_events",),
            ),
            (
                "map21.false_safety_claims",
                MetricKind.GUARDRAIL,
                "虚假安全承诺次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(FALSE_SAFETY_CLAIM)",
                "episode",
                ("submit result",),
            ),
            (
                "map21.late_evacuation",
                MetricKind.DIAGNOSTIC,
                "喷发前未完成撤离的失败归因",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if eruption_tick < last_evacuation_tick else 0",
                "发生喷发的 episode",
                ("eruption_event", "evacuation_events"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-23",
        (
            (
                "map23.clue_utilization",
                MetricKind.PRIMARY,
                "依据已证实线索缩减的候选区域比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "reduced_candidate_regions / reducible_candidate_regions",
                "可缩减候选区域数",
                ("investigate", "clue_state"),
            ),
            (
                "map23.cost_per_discovery",
                MetricKind.PRIMARY,
                "单位发现成本",
                "补给/发现",
                Direction.LOWER_IS_BETTER,
                "supplies_spent / discoveries",
                "发现数；0 则 N/A",
                ("supply_ledger", "discovery_events"),
            ),
            (
                "map23.repeated_invalid_exploration",
                MetricKind.GUARDRAIL,
                "重复无效探索次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(region re-searched after exclusion)",
                "episode",
                ("scout", "candidate_state"),
            ),
            (
                "map23.ignored_counterevidence",
                MetricKind.DIAGNOSTIC,
                "忽略明确反证的行为数（失败归因）",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(action contradicting confirmed clue)",
                "episode",
                ("investigate", "clue_state"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-24",
        (
            (
                "map24.replanning_latency",
                MetricKind.PRIMARY,
                "地形突变公开后到首次改路的延迟",
                "tick",
                Direction.LOWER_IS_BETTER,
                "tick(first replanned move) - tick(collapse public)",
                "坍塌实际发生的 episode",
                ("collapse_event", "move"),
            ),
            (
                "map24.route_cost_ratio",
                MetricKind.PRIMARY,
                "坍塌后剩余路程与最短可行路程之比",
                "比值 ≥1",
                Direction.LOWER_IS_BETTER,
                "actual_remaining_cost / shortest_feasible_cost_after_collapse",
                "坍塌后最短可行成本",
                ("move", "collapse_event"),
            ),
            (
                "map24.collapsed_edge_attempts",
                MetricKind.GUARDRAIL,
                "继续尝试已坍塌边的次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(move onto collapsed edge)",
                "episode",
                ("move result",),
            ),
            (
                "map24.rescue_failure",
                MetricKind.DIAGNOSTIC,
                "救援未完成的失败归因",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if rescue target not reached by deadline else 0",
                "episode",
                ("terminal_reason",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-25",
        (
            (
                "map25.required_check_coverage",
                MetricKind.PRIMARY,
                "EVA 前必需安全检查的覆盖率",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_required_checks / required_checks",
                "必需检查项数",
                ("inspect", "equip"),
            ),
            (
                "map25.dependency_order_correctness",
                MetricKind.PRIMARY,
                "依赖顺序正确的检查/工具步骤比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "correct_order_steps / evaluated_steps",
                "可评估步骤数",
                ("tool_steps",),
            ),
            (
                "map25.unsafe_eva_attempts",
                MetricKind.GUARDRAIL,
                "未完成气密/氧气检查即出舱的次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(EVA_BEFORE_SAFE)",
                "episode",
                ("eva_exit result",),
            ),
            (
                "map25.oxygen_shortfall",
                MetricKind.DIAGNOSTIC,
                "氧气不足导致的返舱失败",
                "0/1",
                Direction.LOWER_IS_BETTER,
                "1 if terminal_reason==OXYGEN_SHORTFALL else 0",
                "episode",
                ("terminal_reason",),
            ),
        ),
    ),
    *_design_specs(
        "MAP-27",
        (
            (
                "map27.joint_task_completion_rate",
                MetricKind.PRIMARY,
                "中继/采样/救援协同任务完成率",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "completed_joint_tasks / required_joint_tasks",
                "必需协同任务数",
                ("task_events",),
            ),
            (
                "map27.critical_path_delay",
                MetricKind.PRIMARY,
                "关键路径相对参考计划的延误",
                "tick",
                Direction.LOWER_IS_BETTER,
                "actual_critical_path_ticks - reference_critical_path_ticks",
                "参考关键路径",
                ("task_events", "reference_plan"),
            ),
            (
                "map27.communication_blackout_ticks",
                MetricKind.GUARDRAIL,
                "通信失联 tick 数",
                "tick",
                Direction.LOWER_IS_BETTER,
                "count(communication == down)",
                "episode",
                ("relay_state",),
            ),
            (
                "map27.resource_conflicts",
                MetricKind.DIAGNOSTIC,
                "共享电力/货位冲突次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(RESOURCE_CONFLICT)",
                "episode",
                ("load", "charge", "drive result"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-28",
        (
            (
                "map28.timeline_constraint_satisfaction",
                MetricKind.PRIMARY,
                "最终时间线满足的约束比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "satisfied_timeline_constraints / total_timeline_constraints",
                "时间线约束数",
                ("submit", "evidence_timeline"),
            ),
            (
                "map28.key_evidence_coverage",
                MetricKind.PRIMARY,
                "已证实关键证据的覆盖比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "verified_key_evidence / required_key_evidence",
                "必需关键证据数",
                ("investigate", "record"),
            ),
            (
                "map28.unsupported_accusations",
                MetricKind.GUARDRAIL,
                "无证据指控次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(accusation without two sources)",
                "episode",
                ("submit result",),
            ),
            (
                "map28.time_contradictions",
                MetricKind.DIAGNOSTIC,
                "时间矛盾未被排除的失败归因",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(submitted timeline contradiction)",
                "episode",
                ("submit", "timeline_check"),
            ),
        ),
    ),
    *_design_specs(
        "MAP-29",
        (
            (
                "map29.contradiction_detection_rate",
                MetricKind.PRIMARY,
                "证人矛盾被识别并正确记录的比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "detected_contradictions / planted_contradictions",
                "植入矛盾数",
                ("compare_testimony", "testimony_state"),
            ),
            (
                "map29.evidence_supported_testimony_ratio",
                MetricKind.PRIMARY,
                "最终采信的证词中有物证支持的比例",
                "比例 0..1",
                Direction.HIGHER_IS_BETTER,
                "supported_adopted_testimony / adopted_testimony",
                "采信证词数",
                ("submit", "evidence_state"),
            ),
            (
                "map29.query_budget_overruns",
                MetricKind.GUARDRAIL,
                "问询预算超支次数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(QUERY_BUDGET_EXCEEDED)",
                "episode",
                ("ask result",),
            ),
            (
                "map29.single_witness_trust",
                MetricKind.DIAGNOSTIC,
                "未交叉验证即采信单一证人的行为数",
                "次",
                Direction.LOWER_IS_BETTER,
                "count(adopt testimony with <2 independent sources)",
                "episode",
                ("submit", "evidence_state"),
            ),
        ),
    ),
)


def _runtime_specs() -> tuple[MetricSpec, ...]:
    specs: list[MetricSpec] = []
    for module in _RUNTIME_MODULES.values():
        specs.extend(module.SPECS)
    return tuple(specs)


ALL_SPECS: Final[tuple[MetricSpec, ...]] = tuple(
    sorted((*_runtime_specs(), *_DESIGN_SPECS), key=lambda spec: spec.metric_id)
)


def all_specs() -> tuple[MetricSpec, ...]:
    return ALL_SPECS


def specs_for(map_id: str) -> tuple[MetricSpec, ...]:
    return tuple(spec for spec in ALL_SPECS if spec.map_id == map_id)


def spec_for(metric_id: str) -> MetricSpec:
    for spec in ALL_SPECS:
        if spec.metric_id == metric_id:
            return spec
    raise KeyError(f"Unknown V7 metric: {metric_id}")


def implemented_map_ids() -> tuple[str, ...]:
    return tuple(sorted(_RUNTIME_MODULES))


def compute_metrics(record: TraceRecord) -> dict[str, MetricValue]:
    """Compute every registered metric for one runtime-backed episode trace."""

    module = _RUNTIME_MODULES.get(record.map_id)
    if module is None:
        raise NotImplementedError(
            f"{record.map_id} 目前只有设计态指标卡，没有 V7 运行时可复算实现。"
        )
    declared = {spec.metric_id for spec in module.SPECS}
    if record.map_id != module.MAP_ID:  # pragma: no cover - defensive
        return {
            metric_id: MetricValue.invalid_trace(
                metric_id, f"trace map_id {record.map_id} 与 extractor 不匹配。"
            )
            for metric_id in declared
        }
    try:
        computed: dict[str, MetricValue] = module.compute(record)
    except TraceFormatError as exc:
        return {metric_id: MetricValue.invalid_trace(metric_id, str(exc)) for metric_id in declared}
    missing = declared - set(computed)
    if missing:  # pragma: no cover - developer error guard
        raise AssertionError(f"{record.map_id} extractor omitted metrics: {sorted(missing)}")
    for metric_id, value in computed.items():
        if value.metric_id != metric_id:  # pragma: no cover - developer error guard
            raise AssertionError(f"{record.map_id} metric key/id mismatch: {metric_id}")
        if value.status is MetricStatus.VALID and value.value is None:
            raise AssertionError(f"{record.map_id} returned VALID without a value: {metric_id}")
    return computed


def registry_document() -> dict[str, Any]:
    """A JSON-serializable view used by the validation script and reports."""

    maps: dict[str, Any] = {}
    for spec in ALL_SPECS:
        entry = maps.setdefault(
            spec.map_id,
            {"implemented": spec.implemented, "metrics": []},
        )
        entry["metrics"].append(spec.model_dump(mode="json"))
    return {"maps": maps, "implemented_map_ids": list(implemented_map_ids())}


__all__ = [
    "ALL_SPECS",
    "all_specs",
    "compute_metrics",
    "implemented_map_ids",
    "registry_document",
    "spec_for",
    "specs_for",
]
