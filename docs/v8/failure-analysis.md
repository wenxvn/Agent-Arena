# V8 失败分析

基于 42 局正式结果；n=3，不做显著性断言。

## 1. 状态分布

| status | count |
|---|---|
| decision_budget_reached | 13 |
| failure | 23 |
| missing | 48 |
| success | 6 |

## 2. 失败码频次

同一局可有多个失败码（如 `INVALID_ACTION` + 机制码）。

| failure_code | count |
|---|---|
| `CENSORED` | 13 |
| `NAV_CORE_FLOODED` | 3 |
| `SIGNAL_WINDOW_MISSED` | 3 |
| `LAMP_RESTORED` | 3 |
| `SHORT_CIRCUIT` | 3 |
| `GENERATOR_FUEL_SHORTAGE` | 3 |
| `SUPPLY_SHORTAGE` | 3 |
| `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` | 2 |
| `EVA_OXYGEN_EXHAUSTED` | 2 |
| `RESCUE_SIGNAL_WINDOW_EXPIRED` | 2 |
| `GATE_OPENED` | 2 |
| `BUS_RESET_WITH_HULL_OPEN` | 1 |
| `SAMPLE_COLD_WINDOW_EXPIRED` | 1 |
| `SIGNAL_LIT` | 1 |

## 3. 地板与天花板

- 3/3 成功（天花板）：MAP-06
- 0/3 成功（地板）：MAP-01, MAP-02, MAP-03, MAP-05, MAP-07, MAP-08, MAP-09, MAP-10, MAP-11, MAP-12, MAP-14

地板不自动等于“能力为零”：可能是接口、预算、机制陷阱或模型策略失败；逐图原因见 `maps/MAP-XX-final.md` 与 judge metrics。

## 4. 同世界分面

不同地图的原始指标不可直接横比；下表只列各世界三难度的成功数与平均决策数。

| world | 简单 | 中等 | 困难 | 平均决策（按图） |
|---|---|---|---|---|
| spaceship | 0/3 | 0/3 | 0/3 | MAP-01:12.3, MAP-02:6.0, MAP-03:25.3 |
| lighthouse | 1/3 | 0/3 | 3/3 | MAP-04:15.3, MAP-05:19.3, MAP-06:2.7 |
| abyss | 0/3 | 0/3 | 0/3 | MAP-07:30.0, MAP-08:38.0, MAP-09:2.0 |
| polar | 0/3 | 0/3 | 0/3 | MAP-10:3.0, MAP-11:2.0, MAP-12:46.0 |
| pyramid | 2/3 | 0/3 | 0/3 | MAP-13:25.3, MAP-14:38.0, MAP-15:0.0 |
| subway | 0/3 | 0/3 | 0/3 | MAP-16:0.0, MAP-17:0.0, MAP-18:0.0 |
| volcano | 0/3 | 0/3 | 0/3 | MAP-19:0.0, MAP-20:0.0, MAP-21:0.0 |
| jungle | 0/3 | 0/3 | 0/3 | MAP-22:0.0, MAP-23:0.0, MAP-24:0.0 |
| lunar | 0/3 | 0/3 | 0/3 | MAP-25:0.0, MAP-26:0.0, MAP-27:0.0 |
| castle | 0/3 | 0/3 | 0/3 | MAP-28:0.0, MAP-29:0.0, MAP-30:0.0 |

## 5. 资源与费用

- 总费用 ¥0.45363316；单局均值 ¥0.010801。
- 输入 token 583499，输出 token 39245。
- 请求 796，平均每局 19.0。
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
- **MAP-12**：R0: heating_outage_days=0, minimum_safety_margin=6, survival_days=0.766667；R1: heating_outage_days=0, minimum_safety_margin=6, survival_days=0.766667；R2: heating_outage_days=0, minimum_safety_margin=6, survival_days=0.766667
- **MAP-13**：R0: constraint_satisfaction_ratio=0.2, correct_sequence=0, illegal_door_attempts=3；R1: constraint_satisfaction_ratio=0.8, correct_sequence=1, illegal_door_attempts=0；R2: constraint_satisfaction_ratio=0.8, correct_sequence=1, illegal_door_attempts=0
- **MAP-14**：R0: minimum_query_gap=0, query_budget_overruns=0；R1: minimum_query_gap=0, query_budget_overruns=0；R2: minimum_query_gap=0, query_budget_overruns=0

## 8. 解释边界

- 0/3 只说明这三次重复未成功，不说明地图不可解；每图都有真实 Oracle 回放。
- 3/3 也不说明能力普遍化；样本只有三次同图重复。
- 失败码来自机制状态机，不等同于模型内部原因；需要结合 trace 中的动作序列阅读。
