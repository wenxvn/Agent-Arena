# V8 MiMo 90 局结果

- freeze_hash：`4cd8a14131b9ca2022575badd93667d79864efd8d77d77ebc2a9957c9876661b`
- 模型：`mimo-v2.6-flash` / provider `openai` / temperature 0
- 正式完成：**90/90**；缺口 0 局
- 正式局已结算费用：**¥1.25363556**（硬上限 ¥10）
- Token：输入 1566789 / 输出 103774；请求 1902
- 账本：settled `1.27504600` / attempts `1956` / failed `4` / closed `True`（UNKNOWN_PROVIDER_SPEND）
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
| 43 | MAP-15 | pyramid | 困难 | 0 | success | True | GATE_OPENED | 11 | 11 | 0.00648664 | `invalid_transitions`=1; `probes_to_target`=5 |
| 44 | MAP-15 | pyramid | 困难 | 1 | success | True | GATE_OPENED | 12 | 12 | 0.00656380 | `invalid_transitions`=1; `probes_to_target`=5 |
| 45 | MAP-15 | pyramid | 困难 | 2 | success | True | GATE_OPENED | 14 | 14 | 0.00750916 | `invalid_transitions`=3; `probes_to_target`=7 |
| 46 | MAP-16 | subway | 简单 | 0 | failure | False | DEADLOCK | 6 | 6 | 0.0037252 | `deadlock`=1; `head_on_conflicts`=0 |
| 47 | MAP-16 | subway | 简单 | 1 | failure | False | NODE_CAPACITY_CONFLICT | 24 | 24 | 0.01343676 | `deadlock`=0; `head_on_conflicts`=0 |
| 48 | MAP-16 | subway | 简单 | 2 | failure | False | NODE_CAPACITY_CONFLICT | 15 | 15 | 0.00612656 | `deadlock`=0; `head_on_conflicts`=0 |
| 49 | MAP-17 | subway | 中等 | 0 | decision_budget_reached | False | None | 38 | 38 | 0.04320516 | `cumulative_wait_person_ticks`=18; `overcapacity_events`=0 |
| 50 | MAP-17 | subway | 中等 | 1 | decision_budget_reached | False | None | 38 | 38 | 0.04268300 | `cumulative_wait_person_ticks`=22; `overcapacity_events`=1 |
| 51 | MAP-17 | subway | 中等 | 2 | decision_budget_reached | False | None | 38 | 38 | 0.03214256 | `cumulative_wait_person_ticks`=24; `overcapacity_events`=0 |
| 52 | MAP-18 | subway | 困难 | 0 | censored | False | ACTION_LIMIT_REACHED | 12 | 12 | 0.0126596 | `collision_violations`=0; `completed_train_moves`=0 |
| 53 | MAP-18 | subway | 困难 | 1 | failure | False | STATION_CAPACITY_EXCEEDED | 3 | 3 | 0.00185604 | `collision_violations`=0; `completed_train_moves`=0 |
| 54 | MAP-18 | subway | 困难 | 2 | censored | False | ACTION_LIMIT_REACHED | 12 | 12 | 0.01118360 | `collision_violations`=0; `completed_train_moves`=3 |
| 55 | MAP-19 | volcano | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.01906692 | `critical_overheat_ticks`=0; `oscillation_count`=2 |
| 56 | MAP-19 | volcano | 简单 | 1 | failure | False | THERMAL_RUNAWAY | 23 | 23 | 0.01512828 | `critical_overheat_ticks`=1; `oscillation_count`=0 |
| 57 | MAP-19 | volcano | 简单 | 2 | decision_budget_reached | False | None | 30 | 30 | 0.01850988 | `critical_overheat_ticks`=0; `oscillation_count`=0 |
| 58 | MAP-20 | volcano | 中等 | 0 | failure | False | THERMAL_OVERHEAT | 22 | 22 | 0.01901904 | `flow_conservation_violations`=0; `max_node_exceedance`=20 |
| 59 | MAP-20 | volcano | 中等 | 1 | success | True | PRODUCTION_TARGET_MET | 19 | 19 | 0.01298908 | `flow_conservation_violations`=0; `max_node_exceedance`=0 |
| 60 | MAP-20 | volcano | 中等 | 2 | success | True | PRODUCTION_TARGET_MET | 17 | 17 | 0.01325256 | `flow_conservation_violations`=1; `max_node_exceedance`=0 |
| 61 | MAP-21 | volcano | 困难 | 0 | success | True | EVACUATED_BEFORE_ERUPTION | 2 | 2 | 0.0010214 | `evacuation_coverage`=1.0; `false_safety_claims`=None |
| 62 | MAP-21 | volcano | 困难 | 1 | success | True | EVACUATED_BEFORE_ERUPTION | 1 | 1 | 0.00013024 | `evacuation_coverage`=1.0; `false_safety_claims`=None |
| 63 | MAP-21 | volcano | 困难 | 2 | success | True | EVACUATED_BEFORE_ERUPTION | 2 | 2 | 0.00027476 | `evacuation_coverage`=1.0; `false_safety_claims`=None |
| 64 | MAP-22 | jungle | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.02321652 | `illegal_bearing_actions`=1; `memory_grounding_violations`=1 |
| 65 | MAP-22 | jungle | 简单 | 1 | decision_budget_reached | False | None | 30 | 30 | 0.02036660 | `illegal_bearing_actions`=0; `memory_grounding_violations`=0 |
| 66 | MAP-22 | jungle | 简单 | 2 | decision_budget_reached | False | None | 30 | 30 | 0.01894224 | `illegal_bearing_actions`=0; `memory_grounding_violations`=0 |
| 67 | MAP-23 | jungle | 中等 | 0 | failure | False | SUPPLY_DEPLETED | 16 | 16 | 0.0094424 | `clue_utilization`=1.0; `cost_per_discovery`=None |
| 68 | MAP-23 | jungle | 中等 | 1 | failure | False | SUPPLY_DEPLETED | 22 | 22 | 0.01201268 | `clue_utilization`=1.0; `cost_per_discovery`=None |
| 69 | MAP-23 | jungle | 中等 | 2 | success | True | TRUE_ENTRANCE_FOUND | 10 | 10 | 0.00511756 | `clue_utilization`=1.0; `cost_per_discovery`=9.0 |
| 70 | MAP-24 | jungle | 困难 | 0 | failure | False | STRANDED_ON_BRIDGE | 9 | 9 | 0.0059154 | `collapsed_edge_attempts`=0; `replanning_latency`=None |
| 71 | MAP-24 | jungle | 困难 | 1 | success | True | ALL_ITEMS_DELIVERED | 9 | 9 | 0.00240008 | `collapsed_edge_attempts`=0; `replanning_latency`=None |
| 72 | MAP-24 | jungle | 困难 | 2 | success | True | ALL_ITEMS_DELIVERED | 12 | 12 | 0.00647696 | `collapsed_edge_attempts`=0; `replanning_latency`=1 |
| 73 | MAP-25 | lunar | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.01400724 | `dependency_order_correctness`=0.454545; `required_check_coverage`=0.428571 |
| 74 | MAP-25 | lunar | 简单 | 1 | failure | False | OXYGEN_DEPLETED | 29 | 29 | 0.01034928 | `dependency_order_correctness`=0.555556; `required_check_coverage`=0.428571 |
| 75 | MAP-25 | lunar | 简单 | 2 | decision_budget_reached | False | None | 30 | 30 | 0.01114996 | `dependency_order_correctness`=0.692308; `required_check_coverage`=1.0 |
| 76 | MAP-26 | lunar | 中等 | 0 | decision_budget_reached | False | None | 38 | 38 | 0.02055772 | `diagnosis_accuracy`=None; `recovery_latency`=None |
| 77 | MAP-26 | lunar | 中等 | 1 | decision_budget_reached | False | None | 38 | 38 | 0.01883928 | `diagnosis_accuracy`=None; `recovery_latency`=None |
| 78 | MAP-26 | lunar | 中等 | 2 | decision_budget_reached | False | None | 38 | 38 | 0.01941904 | `diagnosis_accuracy`=None; `recovery_latency`=None |
| 79 | MAP-27 | lunar | 困难 | 0 | failure | False | VEHICLE_STRANDED | 8 | 8 | 0.00580636 | `communication_blackout_ticks`=13; `critical_path_delay`=None |
| 80 | MAP-27 | lunar | 困难 | 1 | failure | False | VEHICLE_STRANDED | 10 | 10 | 0.00448080 | `communication_blackout_ticks`=12; `critical_path_delay`=None |
| 81 | MAP-27 | lunar | 困难 | 2 | failure | False | VEHICLE_STRANDED | 6 | 6 | 0.00210904 | `communication_blackout_ticks`=14; `critical_path_delay`=None |
| 82 | MAP-28 | castle | 简单 | 0 | decision_budget_reached | False | None | 30 | 30 | 0.02140084 | `key_evidence_coverage`=0.25; `timeline_constraint_satisfaction`=0.0 |
| 83 | MAP-28 | castle | 简单 | 1 | decision_budget_reached | False | None | 30 | 30 | 0.02366732 | `key_evidence_coverage`=0.75; `timeline_constraint_satisfaction`=0.0 |
| 84 | MAP-28 | castle | 简单 | 2 | decision_budget_reached | False | None | 30 | 30 | 0.01490564 | `key_evidence_coverage`=0.25; `timeline_constraint_satisfaction`=0.0 |
| 85 | MAP-29 | castle | 中等 | 0 | decision_budget_reached | False | None | 38 | 38 | 0.04048732 | `contradiction_detection_rate`=0.0; `evidence_supported_testimony_ratio`=None |
| 86 | MAP-29 | castle | 中等 | 1 | decision_budget_reached | False | None | 38 | 38 | 0.04046624 | `contradiction_detection_rate`=0.0; `evidence_supported_testimony_ratio`=None |
| 87 | MAP-29 | castle | 中等 | 2 | decision_budget_reached | False | None | 38 | 38 | 0.03567872 | `contradiction_detection_rate`=0.0; `evidence_supported_testimony_ratio`=None |
| 88 | MAP-30 | castle | 困难 | 0 | decision_budget_reached | False | None | 46 | 46 | 0.03396008 | `accusation_claim_precision`=None; `evidence_chain_coverage`=0.0 |
| 89 | MAP-30 | castle | 困难 | 1 | decision_budget_reached | False | None | 46 | 46 | 0.04683228 | `accusation_claim_precision`=None; `evidence_chain_coverage`=0.0 |
| 90 | MAP-30 | castle | 困难 | 2 | decision_budget_reached | False | None | 46 | 46 | 0.04502456 | `accusation_claim_precision`=0.666667; `evidence_chain_coverage`=0.0 |

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
| MAP-15 | pyramid | 困难 | default | 3/3 | {'success': 3} | 12.3 | 0.02055960 |
| MAP-16 | subway | 简单 | constraint_table | 0/3 | {'failure': 3} | 15.0 | 0.02328852 |
| MAP-17 | subway | 中等 | default | 0/3 | {'decision_budget_reached': 3} | 38.0 | 0.11803072 |
| MAP-18 | subway | 困难 | alert_on | 0/3 | {'censored': 2, 'failure': 1} | 9.0 | 0.02569924 |
| MAP-19 | volcano | 简单 | default | 0/3 | {'decision_budget_reached': 2, 'failure': 1} | 27.7 | 0.05270508 |
| MAP-20 | volcano | 中等 | default | 2/3 | {'failure': 1, 'success': 2} | 19.3 | 0.04526068 |
| MAP-21 | volcano | 困难 | default | 3/3 | {'success': 3} | 1.7 | 0.00142640 |
| MAP-22 | jungle | 简单 | history5_graph_memory | 0/3 | {'decision_budget_reached': 3} | 30.0 | 0.06252536 |
| MAP-23 | jungle | 中等 | default | 1/3 | {'failure': 2, 'success': 1} | 16.0 | 0.02657264 |
| MAP-24 | jungle | 困难 | default | 2/3 | {'failure': 1, 'success': 2} | 10.0 | 0.01479244 |
| MAP-25 | lunar | 简单 | default | 0/3 | {'decision_budget_reached': 2, 'failure': 1} | 29.7 | 0.03550648 |
| MAP-26 | lunar | 中等 | free_diagnosis | 0/3 | {'decision_budget_reached': 3} | 38.0 | 0.05881604 |
| MAP-27 | lunar | 困难 | default | 0/3 | {'failure': 3} | 8.0 | 0.01239620 |
| MAP-28 | castle | 简单 | default | 0/3 | {'decision_budget_reached': 3} | 30.0 | 0.05997380 |
| MAP-29 | castle | 中等 | default | 0/3 | {'decision_budget_reached': 3} | 38.0 | 0.11663228 |
| MAP-30 | castle | 困难 | history5_casebook | 0/3 | {'decision_budget_reached': 3} | 46.0 | 0.12581692 |

## 3. 状态与费用分布

- `censored`：2
- `decision_budget_reached`：35
- `failure`：36
- `success`：17
- 成功：17/90（18.9% of completed）
- 单局平均费用：¥0.013929
- 单局平均请求：21.1

## 4. 补跑与中断

- 尝试记录：94（含补跑与原失败）
- provider_error 的正式局：0
- unknown_spend 的正式局：0
  - MAP-13 R2 `V8-MAP-13-R2-20261017T083750Z-787ade08` status=unknown_provider_spend error=InternalServerError unknown_spend=True
  - MAP-15 R0 `V8-MAP-15-R0-20261017T085151Z-a8381a55` status=unknown_provider_spend error=APIConnectionError unknown_spend=True
  - MAP-26 R2 `V8-MAP-26-R2-20261017T101609Z-05797deb` status=unknown_provider_spend error=InternalServerError unknown_spend=True
  - MAP-28 R0 `V8-MAP-28-R0-20261017T103954Z-1abe3469` status=unknown_provider_spend error=APIConnectionError unknown_spend=True

## 5. 缺口

无：90 局均有正式结果。
