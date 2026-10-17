# V8 失败分析

基于 90 局正式结果；n=3，不做显著性断言。

## 1. 状态分布

| status | count |
|---|---|
| censored | 2 |
| decision_budget_reached | 32 |
| failure | 39 |
| success | 17 |

## 2. 失败码频次

同一局可有多个失败码（如 `INVALID_ACTION` + 机制码）。

| failure_code | count |
|---|---|
| `CENSORED` | 34 |
| `NAV_CORE_FLOODED` | 3 |
| `SIGNAL_WINDOW_MISSED` | 3 |
| `SHORT_CIRCUIT` | 3 |
| `GENERATOR_FUEL_SHORTAGE` | 3 |
| `SUPPLY_SHORTAGE` | 3 |
| `RESEARCH_TARGET_MISSED` | 3 |
| `VEHICLE_STRANDED` | 3 |
| `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` | 2 |
| `EVA_OXYGEN_EXHAUSTED` | 2 |
| `RESCUE_SIGNAL_WINDOW_EXPIRED` | 2 |
| `NODE_CAPACITY_CONFLICT` | 2 |
| `ACTION_LIMIT_REACHED` | 2 |
| `SUPPLY_DEPLETED` | 2 |
| `BUS_RESET_WITH_HULL_OPEN` | 1 |
| `SAMPLE_COLD_WINDOW_EXPIRED` | 1 |
| `DEADLOCK` | 1 |
| `INVALID_ACTION` | 1 |
| `STATION_CAPACITY_EXCEEDED` | 1 |
| `THERMAL_RUNAWAY` | 1 |
| `THERMAL_OVERHEAT` | 1 |
| `STRANDED_ON_BRIDGE` | 1 |
| `OXYGEN_DEPLETED` | 1 |

`CENSORED` 汇总“决策预算耗尽”与地图自身 horizon 截尾，不是机制失败码；其余码为地图私有失败码或 `INVALID_ACTION`。

## 3. 地板与天花板

- 3/3 成功（天花板）：MAP-06, MAP-15, MAP-21
- 0/3 成功（地板）：MAP-01, MAP-02, MAP-03, MAP-05, MAP-07, MAP-08, MAP-09, MAP-10, MAP-11, MAP-12, MAP-14, MAP-16, MAP-17, MAP-18, MAP-19, MAP-22, MAP-25, MAP-26, MAP-27, MAP-28, MAP-29, MAP-30

地板不自动等于“能力为零”：可能是接口、预算、机制陷阱或模型策略失败；逐图原因见 `maps/MAP-XX-final.md` 与 judge metrics。

## 4. 同世界分面

不同地图的原始指标不可直接横比；下表只列各世界三难度的成功数与平均决策数。

| world | 简单 | 中等 | 困难 | 平均决策（按图） |
|---|---|---|---|---|
| spaceship | 0/3 | 0/3 | 0/3 | MAP-01:12.3, MAP-02:6.0, MAP-03:25.3 |
| lighthouse | 1/3 | 0/3 | 3/3 | MAP-04:15.3, MAP-05:19.3, MAP-06:2.7 |
| abyss | 0/3 | 0/3 | 0/3 | MAP-07:30.0, MAP-08:38.0, MAP-09:2.0 |
| polar | 0/3 | 0/3 | 0/3 | MAP-10:3.0, MAP-11:2.0, MAP-12:60.0 |
| pyramid | 2/3 | 0/3 | 3/3 | MAP-13:25.3, MAP-14:38.0, MAP-15:12.3 |
| subway | 0/3 | 0/3 | 0/3 | MAP-16:15.0, MAP-17:38.0, MAP-18:9.0 |
| volcano | 0/3 | 2/3 | 3/3 | MAP-19:27.7, MAP-20:19.3, MAP-21:1.7 |
| jungle | 0/3 | 1/3 | 2/3 | MAP-22:30.0, MAP-23:16.0, MAP-24:10.0 |
| lunar | 0/3 | 0/3 | 0/3 | MAP-25:29.7, MAP-26:38.0, MAP-27:8.0 |
| castle | 0/3 | 0/3 | 0/3 | MAP-28:30.0, MAP-29:38.0, MAP-30:46.0 |

## 5. 资源与费用

- 总费用 ¥1.27464628；单局均值 ¥0.014163。
- 输入 token 1599077，输出 token 105944。
- 请求 1944，平均每局 21.6。
- 费用按供应商 usage 结算；未知消费会立即封账，不用估算值替代。

## 6. Provider / schema 异常

- provider_error：0 局；unknown_spend：0 局。

## 7. 部分能力差异示例

同样未通关的局在部分指标上仍可能不同。以下按图列出未成功局的主指标/护栏值，用于说明“失败”不是单一能力标签：

- **MAP-01**：R0: dependency_satisfaction_rate=0.666667, longest_oxygen_outage_ticks=4, oxygen_guardrail_violations=1；R1: dependency_satisfaction_rate=0.166667, longest_oxygen_outage_ticks=3, oxygen_guardrail_violations=0；R2: dependency_satisfaction_rate=0.0, longest_oxygen_outage_ticks=4, oxygen_guardrail_violations=1
- **MAP-02**：R0: crew_decompression=0, dual_objective_completion=0.0, event_response_latency=1；R1: crew_decompression=0, dual_objective_completion=0.0, event_response_latency=1；R2: crew_decompression=0, dual_objective_completion=0.0, event_response_latency=1
- **MAP-03**：R0: long_delay_recall_accuracy=0.0, phase_completion_coverage=0.2, phase_order_violations=2；R1: long_delay_recall_accuracy=0.0, phase_completion_coverage=0.2, phase_order_violations=1；R2: long_delay_recall_accuracy=0.0, phase_completion_coverage=0.2, phase_order_violations=2
- **MAP-04**：R0: high_tide_entries=0；R1: earliest_safe_crossing_delay=0, high_tide_entries=1, window_hit_rate=0.5；R2: earliest_safe_crossing_delay=0, high_tide_entries=1, window_hit_rate=0.5
- **MAP-05**：R0: effective_signals=0.0, power_overcommit=0, window_utilization=0.0；R1: effective_signals=0.333333, power_overcommit=0, window_utilization=0.333333；R2: effective_signals=0.333333, power_overcommit=0, window_utilization=0.333333
- **MAP-07**：R0: excess_water_integral=180, overpressure_ticks=0；R1: excess_water_integral=180, overpressure_ticks=0；R2: excess_water_integral=180, overpressure_ticks=0
- **MAP-08**：R0: candidate_reduction=0.0, peak_core_water=3.0；R1: candidate_reduction=0.0, peak_core_water=4.0；R2: candidate_reduction=0.0, peak_core_water=4.0
- **MAP-09**：R0: fault_propagation_scale=1, hard_threshold_breaches=1, stable_time_ratio=0.5；R1: fault_propagation_scale=1, hard_threshold_breaches=1, stable_time_ratio=0.5；R2: fault_propagation_scale=1, hard_threshold_breaches=1, stable_time_ratio=0.5
- **MAP-10**：R0: base_frozen=0, key_task_fuel_efficiency=0.0, minimum_base_temperature=5；R1: base_frozen=0, key_task_fuel_efficiency=0.0, minimum_base_temperature=5；R2: base_frozen=0, key_task_fuel_efficiency=0.0, minimum_base_temperature=5
- **MAP-11**：R0: rescue_count=0, rescuer_hypothermia=0；R1: rescue_count=0, rescuer_hypothermia=0；R2: rescue_count=0, rescuer_hypothermia=0
- **MAP-12**：R0: heating_outage_days=0, minimum_safety_margin=-1, survival_days=1.0；R1: heating_outage_days=0, minimum_safety_margin=-1, survival_days=1.0；R2: heating_outage_days=0, minimum_safety_margin=-1, survival_days=1.0
- **MAP-13**：R0: constraint_satisfaction_ratio=0.2, correct_sequence=0, illegal_door_attempts=3；R1: constraint_satisfaction_ratio=0.8, correct_sequence=1, illegal_door_attempts=0；R2: constraint_satisfaction_ratio=0.8, correct_sequence=1, illegal_door_attempts=0
- **MAP-14**：R0: minimum_query_gap=0, query_budget_overruns=0；R1: minimum_query_gap=0, query_budget_overruns=0；R2: minimum_query_gap=0, query_budget_overruns=0
- **MAP-16**：R0: deadlock=1, head_on_conflicts=0, legal_reservation_rate=1.0；R1: deadlock=0, head_on_conflicts=0, legal_reservation_rate=0.4；R2: deadlock=0, head_on_conflicts=0, legal_reservation_rate=1.0
- **MAP-17**：R0: cumulative_wait_person_ticks=18, overcapacity_events=0, service_rate=0.4；R1: cumulative_wait_person_ticks=22, overcapacity_events=1, service_rate=0.2；R2: cumulative_wait_person_ticks=24, overcapacity_events=0, service_rate=0.4
- **MAP-18**：R0: collision_violations=0, completed_train_moves=0, first_reroute_delay=1；R1: collision_violations=0, completed_train_moves=0, delay_person_ticks=0；R2: collision_violations=0, completed_train_moves=3, station_capacity_violations=0
- **MAP-19**：R0: critical_overheat_ticks=0, oscillation_count=2, temperature_exceedance_area=3；R1: critical_overheat_ticks=1, oscillation_count=0, temperature_exceedance_area=15；R2: critical_overheat_ticks=0, oscillation_count=0, temperature_exceedance_area=3
- **MAP-20**：R0: flow_conservation_violations=0, max_node_exceedance=20, safe_node_ticks=29；R1: flow_conservation_violations=0, max_node_exceedance=0, safe_node_ticks=30；R2: flow_conservation_violations=1, max_node_exceedance=0, safe_node_ticks=30
- **MAP-22**：R0: illegal_bearing_actions=1, memory_grounding_violations=1, return_success=0；R1: illegal_bearing_actions=0, memory_grounding_violations=0, return_success=0；R2: illegal_bearing_actions=0, memory_grounding_violations=0, return_success=0
- **MAP-23**：R0: clue_utilization=1.0, repeated_invalid_exploration=0；R1: clue_utilization=1.0, repeated_invalid_exploration=0；R2: clue_utilization=1.0, cost_per_discovery=9.0, repeated_invalid_exploration=0
- **MAP-24**：R0: collapsed_edge_attempts=0；R1: collapsed_edge_attempts=0；R2: collapsed_edge_attempts=0, replanning_latency=1, route_cost_ratio=1.0
- **MAP-25**：R0: dependency_order_correctness=0.454545, required_check_coverage=0.428571, unsafe_eva_attempts=0；R1: dependency_order_correctness=0.555556, required_check_coverage=0.428571, unsafe_eva_attempts=0；R2: dependency_order_correctness=0.692308, required_check_coverage=1.0, unsafe_eva_attempts=0
- **MAP-26**：R0: repair_success=0, spares_remaining=2；R1: repair_success=0, spares_remaining=2；R2: repair_success=0, spares_remaining=2
- **MAP-27**：R0: communication_blackout_ticks=13, joint_task_completion_rate=0.0；R1: communication_blackout_ticks=12, joint_task_completion_rate=0.0；R2: communication_blackout_ticks=14, joint_task_completion_rate=0.0
- **MAP-28**：R0: key_evidence_coverage=0.25, timeline_constraint_satisfaction=0.0, unsupported_accusations=0；R1: key_evidence_coverage=0.75, timeline_constraint_satisfaction=0.0, unsupported_accusations=0；R2: key_evidence_coverage=0.25, timeline_constraint_satisfaction=0.0, unsupported_accusations=0
- **MAP-29**：R0: contradiction_detection_rate=0.0, query_budget_overruns=0；R1: contradiction_detection_rate=0.0, query_budget_overruns=0；R2: contradiction_detection_rate=0.0, query_budget_overruns=0
- **MAP-30**：R0: evidence_chain_coverage=0.0, unsupported_accusations=0；R1: evidence_chain_coverage=0.0, unsupported_accusations=0；R2: accusation_claim_precision=0.666667, evidence_chain_coverage=0.0, q4_recall_accuracy=0

## 8. 解释边界

- 0/3 只说明这三次重复未成功，不说明地图不可解；每图都有真实 Oracle 回放。
- 3/3 也不说明能力普遍化；样本只有三次同图重复。
- 失败码来自机制状态机，不等同于模型内部原因；需要结合 trace 中的动作序列阅读。
