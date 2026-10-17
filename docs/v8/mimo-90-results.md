# V8 MiMo 90 局结果

- freeze_hash：`a346ddcdace8758b077bdb563566901980f97c9996b9d20c25f811a048a26bdf`
- 模型：`mimo-v2.6-flash` / provider `openai` / temperature 0
- 正式完成：**42/90**；缺口 48 局
- 正式局已结算费用：**¥0.45363316**（硬上限 ¥10）
- Token：输入 583499 / 输出 39245；请求 796
- 账本：settled `0.46374768` / attempts `814` / failed `2` / closed `True`（UNKNOWN_PROVIDER_SPEND）
- 预警：无

> n=3 只作重复运行描述，不做显著性断言。Oracle 成功率不是 MiMo 能力。

## 1. 90 行结果

| # | map | world | 难度 | rep | status | success | 终止原因 | 决策 | 请求 | cost | 主指标 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MAP-01 | spaceship | 简单 | 0 | failure | False | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 11 | 11 | 0.00758384 | `dependency_satisfaction_rate`=0.666667; `longest_oxygen_outage_ticks`=4 |
| 2 | MAP-01 | spaceship | 简单 | 1 | failure | False | BUS_RESET_WITH_HULL_OPEN | 22 | 22 | 0.00941168 | `dependency_satisfaction_rate`=0.166667; `longest_oxygen_outage_ticks`=3 |
| 3 | MAP-01 | spaceship | 简单 | 2 | failure | False | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 4 | 4 | 0.00158872 | `dependency_satisfaction_rate`=0.0; `longest_oxygen_outage_ticks`=4 |
| 4 | MAP-02 | spaceship | 中等 | 0 | failure | False | NAV_CORE_FLOODED | 6 | 6 | 0.00384868 | `crew_decompression`=0; `dual_objective_completion`=0.0 |
| 5 | MAP-02 | spaceship | 中等 | 1 | failure | False | NAV_CORE_FLOODED | 6 | 6 | 0.00180020 | `crew_decompression`=0; `dual_objective_completion`=0.0 |
| 6 | MAP-02 | spaceship | 中等 | 2 | failure | False | NAV_CORE_FLOODED | 6 | 6 | 0.00147932 | `crew_decompression`=0; `dual_objective_completion`=0.0 |
| 7 | MAP-03 | spaceship | 困难 | 0 | failure | False | EVA_OXYGEN_EXHAUSTED | 28 | 28 | 0.01721744 | `long_delay_recall_accuracy`=0.0; `phase_completion_coverage`=0.2 |
| 8 | MAP-03 | spaceship | 困难 | 1 | failure | False | EVA_OXYGEN_EXHAUSTED | 21 | 21 | 0.01235524 | `long_delay_recall_accuracy`=0.0; `phase_completion_coverage`=0.2 |
| 9 | MAP-03 | spaceship | 困难 | 2 | failure | False | SAMPLE_COLD_WINDOW_EXPIRED | 27 | 27 | 0.01346528 | `long_delay_recall_accuracy`=0.0; `phase_completion_coverage`=0.2 |
| 10 | MAP-04 | lighthouse | 简单 | 0 | success | True | SIGNAL_LIT | 15 | 15 | 0.00831408 | `earliest_safe_crossing_delay`=None; `high_tide_entries`=0 |
| 11 | MAP-04 | lighthouse | 简单 | 1 | failure | False | RESCUE_SIGNAL_WINDOW_EXPIRED | 15 | 15 | 0.00863040 | `earliest_safe_crossing_delay`=0; `high_tide_entries`=1 |
| 12 | MAP-04 | lighthouse | 简单 | 2 | failure | False | RESCUE_SIGNAL_WINDOW_EXPIRED | 16 | 16 | 0.00551948 | `earliest_safe_crossing_delay`=0; `high_tide_entries`=1 |
| 13 | MAP-05 | lighthouse | 中等 | 0 | failure | False | SIGNAL_WINDOW_MISSED | 19 | 19 | 0.01176612 | `effective_signals`=0.0; `power_overcommit`=0 |
| 14 | MAP-05 | lighthouse | 中等 | 1 | failure | False | SIGNAL_WINDOW_MISSED | 20 | 20 | 0.01133772 | `effective_signals`=0.333333; `power_overcommit`=0 |
| 15 | MAP-05 | lighthouse | 中等 | 2 | failure | False | SIGNAL_WINDOW_MISSED | 19 | 19 | 0.01027484 | `effective_signals`=0.333333; `power_overcommit`=0 |
| 16 | MAP-06 | lighthouse | 困难 | 0 | success | True | LAMP_RESTORED | 2 | 2 | 0.0008094 | `high_risk_exposure_ticks`=0; `task_success_rate`=1.0 |
| 17 | MAP-06 | lighthouse | 困难 | 1 | success | True | LAMP_RESTORED | 3 | 3 | 0.00100636 | `high_risk_exposure_ticks`=0; `task_success_rate`=1.0 |
| 18 | MAP-06 | lighthouse | 困难 | 2 | success | True | LAMP_RESTORED | 3 | 3 | 0.00086292 | `high_risk_exposure_ticks`=0; `task_success_rate`=1.0 |
| 19 | MAP-07 | abyss | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.02222448 | `correct_direction_rate`=None; `excess_water_integral`=180 |
| 20 | MAP-07 | abyss | 简单 | 1 | decision_budget_reached | False | None | 30 | 30 | 0.01893456 | `correct_direction_rate`=None; `excess_water_integral`=180 |
| 21 | MAP-07 | abyss | 简单 | 2 | decision_budget_reached | False | None | 30 | 30 | 0.01385244 | `correct_direction_rate`=None; `excess_water_integral`=180 |
| 22 | MAP-08 | abyss | 中等 | 0 | decision_budget_reached | False | None | 38 | 38 | 0.02169032 | `candidate_reduction`=0.0; `diagnosis_accuracy`=None |
| 23 | MAP-08 | abyss | 中等 | 1 | decision_budget_reached | False | None | 38 | 38 | 0.01801644 | `candidate_reduction`=0.0; `diagnosis_accuracy`=None |
| 24 | MAP-08 | abyss | 中等 | 2 | decision_budget_reached | False | None | 38 | 38 | 0.01830844 | `candidate_reduction`=0.0; `diagnosis_accuracy`=None |
| 25 | MAP-09 | abyss | 困难 | 0 | failure | False | SHORT_CIRCUIT | 2 | 2 | 0.001313 | `fault_propagation_scale`=1; `hard_threshold_breaches`=1 |
| 26 | MAP-09 | abyss | 困难 | 1 | failure | False | SHORT_CIRCUIT | 2 | 2 | 0.00024876 | `fault_propagation_scale`=1; `hard_threshold_breaches`=1 |
| 27 | MAP-09 | abyss | 困难 | 2 | failure | False | SHORT_CIRCUIT | 2 | 2 | 0.00079924 | `fault_propagation_scale`=1; `hard_threshold_breaches`=1 |
| 28 | MAP-10 | polar | 简单 | 0 | failure | False | GENERATOR_FUEL_SHORTAGE | 2 | 2 | 0.001246 | `base_frozen`=0; `key_task_fuel_efficiency`=0.0 |
| 29 | MAP-10 | polar | 简单 | 1 | failure | False | GENERATOR_FUEL_SHORTAGE | 5 | 5 | 0.00193544 | `base_frozen`=0; `key_task_fuel_efficiency`=0.0 |
| 30 | MAP-10 | polar | 简单 | 2 | failure | False | GENERATOR_FUEL_SHORTAGE | 2 | 2 | 0.00020976 | `base_frozen`=0; `key_task_fuel_efficiency`=0.0 |
| 31 | MAP-11 | polar | 中等 | 0 | failure | False | SUPPLY_SHORTAGE | 2 | 2 | 0.001328 | `rescue_count`=0; `rescuer_hypothermia`=0 |
| 32 | MAP-11 | polar | 中等 | 1 | failure | False | SUPPLY_SHORTAGE | 2 | 2 | 0.00077152 | `rescue_count`=0; `rescuer_hypothermia`=0 |
| 33 | MAP-11 | polar | 中等 | 2 | failure | False | SUPPLY_SHORTAGE | 2 | 2 | 0.00029976 | `rescue_count`=0; `rescuer_hypothermia`=0 |
| 34 | MAP-12 | polar | 困难 | 0 | decision_budget_reached | False | None | 46 | 46 | 0.03324104 | `heating_outage_days`=0; `minimum_safety_margin`=6 |
| 35 | MAP-12 | polar | 困难 | 1 | decision_budget_reached | False | None | 46 | 46 | 0.03032332 | `heating_outage_days`=0; `minimum_safety_margin`=6 |
| 36 | MAP-12 | polar | 困难 | 2 | decision_budget_reached | False | None | 46 | 46 | 0.03042388 | `heating_outage_days`=0; `minimum_safety_margin`=6 |
| 37 | MAP-13 | pyramid | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.02209248 | `constraint_satisfaction_ratio`=0.2; `correct_sequence`=0 |
| 38 | MAP-13 | pyramid | 简单 | 1 | success | True | GATE_OPENED | 27 | 27 | 0.01553652 | `constraint_satisfaction_ratio`=0.8; `correct_sequence`=1 |
| 39 | MAP-13 | pyramid | 简单 | 2 | success | True | GATE_OPENED | 19 | 19 | 0.00938184 | `constraint_satisfaction_ratio`=0.8; `correct_sequence`=1 |
| 40 | MAP-14 | pyramid | 中等 | 0 | decision_budget_reached | False | None | 38 | 38 | 0.02326660 | `globally_consistent_hypothesis_rate`=None; `minimum_query_gap`=0 |
| 41 | MAP-14 | pyramid | 中等 | 1 | decision_budget_reached | False | None | 38 | 38 | 0.02225512 | `globally_consistent_hypothesis_rate`=None; `minimum_query_gap`=0 |
| 42 | MAP-14 | pyramid | 中等 | 2 | decision_budget_reached | False | None | 38 | 38 | 0.01866248 | `globally_consistent_hypothesis_rate`=None; `minimum_query_gap`=0 |
| 43 | MAP-15 | None | None | 0 | missing | None | None | — | — | None |  |
| 44 | MAP-15 | None | None | 1 | missing | None | None | — | — | None |  |
| 45 | MAP-15 | None | None | 2 | missing | None | None | — | — | None |  |
| 46 | MAP-16 | None | None | 0 | missing | None | None | — | — | None |  |
| 47 | MAP-16 | None | None | 1 | missing | None | None | — | — | None |  |
| 48 | MAP-16 | None | None | 2 | missing | None | None | — | — | None |  |
| 49 | MAP-17 | None | None | 0 | missing | None | None | — | — | None |  |
| 50 | MAP-17 | None | None | 1 | missing | None | None | — | — | None |  |
| 51 | MAP-17 | None | None | 2 | missing | None | None | — | — | None |  |
| 52 | MAP-18 | None | None | 0 | missing | None | None | — | — | None |  |
| 53 | MAP-18 | None | None | 1 | missing | None | None | — | — | None |  |
| 54 | MAP-18 | None | None | 2 | missing | None | None | — | — | None |  |
| 55 | MAP-19 | None | None | 0 | missing | None | None | — | — | None |  |
| 56 | MAP-19 | None | None | 1 | missing | None | None | — | — | None |  |
| 57 | MAP-19 | None | None | 2 | missing | None | None | — | — | None |  |
| 58 | MAP-20 | None | None | 0 | missing | None | None | — | — | None |  |
| 59 | MAP-20 | None | None | 1 | missing | None | None | — | — | None |  |
| 60 | MAP-20 | None | None | 2 | missing | None | None | — | — | None |  |
| 61 | MAP-21 | None | None | 0 | missing | None | None | — | — | None |  |
| 62 | MAP-21 | None | None | 1 | missing | None | None | — | — | None |  |
| 63 | MAP-21 | None | None | 2 | missing | None | None | — | — | None |  |
| 64 | MAP-22 | None | None | 0 | missing | None | None | — | — | None |  |
| 65 | MAP-22 | None | None | 1 | missing | None | None | — | — | None |  |
| 66 | MAP-22 | None | None | 2 | missing | None | None | — | — | None |  |
| 67 | MAP-23 | None | None | 0 | missing | None | None | — | — | None |  |
| 68 | MAP-23 | None | None | 1 | missing | None | None | — | — | None |  |
| 69 | MAP-23 | None | None | 2 | missing | None | None | — | — | None |  |
| 70 | MAP-24 | None | None | 0 | missing | None | None | — | — | None |  |
| 71 | MAP-24 | None | None | 1 | missing | None | None | — | — | None |  |
| 72 | MAP-24 | None | None | 2 | missing | None | None | — | — | None |  |
| 73 | MAP-25 | None | None | 0 | missing | None | None | — | — | None |  |
| 74 | MAP-25 | None | None | 1 | missing | None | None | — | — | None |  |
| 75 | MAP-25 | None | None | 2 | missing | None | None | — | — | None |  |
| 76 | MAP-26 | None | None | 0 | missing | None | None | — | — | None |  |
| 77 | MAP-26 | None | None | 1 | missing | None | None | — | — | None |  |
| 78 | MAP-26 | None | None | 2 | missing | None | None | — | — | None |  |
| 79 | MAP-27 | None | None | 0 | missing | None | None | — | — | None |  |
| 80 | MAP-27 | None | None | 1 | missing | None | None | — | — | None |  |
| 81 | MAP-27 | None | None | 2 | missing | None | None | — | — | None |  |
| 82 | MAP-28 | None | None | 0 | missing | None | None | — | — | None |  |
| 83 | MAP-28 | None | None | 1 | missing | None | None | — | — | None |  |
| 84 | MAP-28 | None | None | 2 | missing | None | None | — | — | None |  |
| 85 | MAP-29 | None | None | 0 | missing | None | None | — | — | None |  |
| 86 | MAP-29 | None | None | 1 | missing | None | None | — | — | None |  |
| 87 | MAP-29 | None | None | 2 | missing | None | None | — | — | None |  |
| 88 | MAP-30 | None | None | 0 | missing | None | None | — | — | None |  |
| 89 | MAP-30 | None | None | 1 | missing | None | None | — | — | None |  |
| 90 | MAP-30 | None | None | 2 | missing | None | None | — | — | None |  |

## 2. 逐图汇总

| map | world | 难度 | 条件 | 成功/3 | statuses | mean decisions | total cost |
|---|---|---|---|---|---|---|---|
| MAP-01 | spaceship | 简单 | default | 0/3 | {'failure': 3} | 12.3 | 0.01858424 |
| MAP-02 | spaceship | 中等 | default | 0/3 | {'failure': 3} | 6.0 | 0.00712820 |
| MAP-03 | spaceship | 困难 | default | 0/3 | {'failure': 3} | 25.3 | 0.04303796 |
| MAP-04 | lighthouse | 简单 | default | 1/3 | {'failure': 2, 'success': 1} | 15.3 | 0.02246396 |
| MAP-05 | lighthouse | 中等 | default | 0/3 | {'failure': 3} | 19.3 | 0.03337868 |
| MAP-06 | lighthouse | 困难 | default | 3/3 | {'success': 3} | 2.7 | 0.00267868 |
| MAP-07 | abyss | 简单 | default | 0/3 | {'decision_budget_reached': 3} | 30.0 | 0.05501148 |
| MAP-08 | abyss | 中等 | hypothesis_table | 0/3 | {'decision_budget_reached': 3} | 38.0 | 0.05801520 |
| MAP-09 | abyss | 困难 | default | 0/3 | {'failure': 3} | 2.0 | 0.00236100 |
| MAP-10 | polar | 简单 | default | 0/3 | {'failure': 3} | 3.0 | 0.00339120 |
| MAP-11 | polar | 中等 | default | 0/3 | {'failure': 3} | 2.0 | 0.00239928 |
| MAP-12 | polar | 困难 | default | 0/3 | {'decision_budget_reached': 3} | 46.0 | 0.09398824 |
| MAP-13 | pyramid | 简单 | default | 2/3 | {'decision_budget_reached': 1, 'success': 2} | 25.3 | 0.04701084 |
| MAP-14 | pyramid | 中等 | default | 0/3 | {'decision_budget_reached': 3} | 38.0 | 0.06418420 |
| MAP-15 | pyramid | 困难 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-16 | subway | 简单 | constraint_table | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-17 | subway | 中等 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-18 | subway | 困难 | alert_on | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-19 | volcano | 简单 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-20 | volcano | 中等 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-21 | volcano | 困难 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-22 | jungle | 简单 | history5_graph_memory | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-23 | jungle | 中等 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-24 | jungle | 困难 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-25 | lunar | 简单 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-26 | lunar | 中等 | free_diagnosis | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-27 | lunar | 困难 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-28 | castle | 简单 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-29 | castle | 中等 | default | 0/3 | {'missing': 3} | 0.0 | 0 |
| MAP-30 | castle | 困难 | history5_casebook | 0/3 | {'missing': 3} | 0.0 | 0 |

## 3. 状态与费用分布

- `decision_budget_reached`：13
- `failure`：23
- `missing`：48
- `success`：6
- 成功：6/90（14.3% of completed）
- 单局平均费用：¥0.010801
- 单局平均请求：19.0

## 4. 补跑与中断

- 尝试记录：44（含补跑与原失败）
- provider_error 的正式局：0
- unknown_spend 的正式局：0
  - MAP-13 R2 `V8-MAP-13-R2-20261017T083750Z-787ade08` status=unknown_provider_spend error=InternalServerError unknown_spend=True
  - MAP-15 R0 `V8-MAP-15-R0-20261017T085151Z-a8381a55` status=unknown_provider_spend error=APIConnectionError unknown_spend=True

## 5. 缺口

- MAP-15 R0：attempts=1 statuses=['unknown_provider_spend']
- MAP-15 R1：attempts=0 statuses=[]
- MAP-15 R2：attempts=0 statuses=[]
- MAP-16 R0：attempts=0 statuses=[]
- MAP-16 R1：attempts=0 statuses=[]
- MAP-16 R2：attempts=0 statuses=[]
- MAP-17 R0：attempts=0 statuses=[]
- MAP-17 R1：attempts=0 statuses=[]
- MAP-17 R2：attempts=0 statuses=[]
- MAP-18 R0：attempts=0 statuses=[]
- MAP-18 R1：attempts=0 statuses=[]
- MAP-18 R2：attempts=0 statuses=[]
- MAP-19 R0：attempts=0 statuses=[]
- MAP-19 R1：attempts=0 statuses=[]
- MAP-19 R2：attempts=0 statuses=[]
- MAP-20 R0：attempts=0 statuses=[]
- MAP-20 R1：attempts=0 statuses=[]
- MAP-20 R2：attempts=0 statuses=[]
- MAP-21 R0：attempts=0 statuses=[]
- MAP-21 R1：attempts=0 statuses=[]
- MAP-21 R2：attempts=0 statuses=[]
- MAP-22 R0：attempts=0 statuses=[]
- MAP-22 R1：attempts=0 statuses=[]
- MAP-22 R2：attempts=0 statuses=[]
- MAP-23 R0：attempts=0 statuses=[]
- MAP-23 R1：attempts=0 statuses=[]
- MAP-23 R2：attempts=0 statuses=[]
- MAP-24 R0：attempts=0 statuses=[]
- MAP-24 R1：attempts=0 statuses=[]
- MAP-24 R2：attempts=0 statuses=[]
- MAP-25 R0：attempts=0 statuses=[]
- MAP-25 R1：attempts=0 statuses=[]
- MAP-25 R2：attempts=0 statuses=[]
- MAP-26 R0：attempts=0 statuses=[]
- MAP-26 R1：attempts=0 statuses=[]
- MAP-26 R2：attempts=0 statuses=[]
- MAP-27 R0：attempts=0 statuses=[]
- MAP-27 R1：attempts=0 statuses=[]
- MAP-27 R2：attempts=0 statuses=[]
- MAP-28 R0：attempts=0 statuses=[]
- MAP-28 R1：attempts=0 statuses=[]
- MAP-28 R2：attempts=0 statuses=[]
- MAP-29 R0：attempts=0 statuses=[]
- MAP-29 R1：attempts=0 statuses=[]
- MAP-29 R2：attempts=0 statuses=[]
- MAP-30 R0：attempts=0 statuses=[]
- MAP-30 R1：attempts=0 statuses=[]
- MAP-30 R2：attempts=0 statuses=[]
