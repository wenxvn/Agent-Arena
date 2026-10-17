# V9 有界 MiMo 验证结果

- 预登记：`docs/v9/mimo-preregistration.json`（manifest hash 见文件）
- 模型：`mimo-v2.6-flash` / temperature 0 / 同实例 seed
- 账本 settled：**¥0.34049884**；pending 预留 ¥0；projected ¥0.34049884；请求 512；失败 2；unknown spend 2；closed=True
- 口径：每条件 2 次重复（4 张主修复图）或 1 次（接口图/地板图/旁路图）；n 很小，只作描述，不做显著性断言。MAP-12 的 `v9_fixed` 臂未完成（provider 不稳定），因此 MAP-12 只有 `v8_compat` 两局与离线修复证据。逐局权威来源是各 `episode_manifest.json`；`runs/v9/mimo_results.json` 只保留最后一次执行的摘要。
- 账本事件：主账本在 MAP-12 R1 v8_compat 第 29 次请求、supplement_001 在 MAP-12 R0 v9_fixed 第 19 次请求均遇到 provider `InternalServerError`，按规则 `UNKNOWN_PROVIDER_SPEND` 封账；MAP-12 的 v9_fixed 臂两次失败后不再重试，其余 episode 在 `runs/v9/supplement_002/` 执行。两个旧账本均未重开。

## 1. 逐局结果

| map | arm | rep | status | success | 终止原因 | 决策 | 费用 ¥ | 主指标（overlay 优先） |
|---|---|---:|---|---|---|---:|---:|---|
| MAP-06 | v9_fixed | 0 | failure | False | RESOURCE_EXHAUSTED | 3 | 0.0014574 | `map06.high_risk_exposure_ticks`=3; `map06.observation_cost`=0 |
| MAP-07 | v8_compat | 0 | decision_budget_reached | False | - | 30 | 0.02428308 | `map07.correct_direction_rate`=None; `map07.excess_water_integral`=180 |
| MAP-07 | v9_fixed | 0 | success | True | LOW_WATER_STABLE | 8 | 0.00628728 | `map07.correct_direction_rate`=0.25; `map07.excess_water_integral`=24 |
| MAP-08 | v8_compat | 0 | decision_budget_reached | False | - | 38 | 0.01863364 | `map08.candidate_reduction`=0.0; `map08.diagnosis_accuracy`=None |
| MAP-08 | v9_fixed | 0 | failure | False | CORE_WATER_LIMIT_EXCEEDED | 24 | 0.01783608 | `map08.candidate_reduction`=0.0; `map08.diagnosis_accuracy`=None |
| MAP-09 | v8_compat | 0 | failure | False | SHORT_CIRCUIT | 2 | 0.001317 | `map09.fault_propagation_scale`=1; `map09.hard_threshold_breaches`=1 |
| MAP-09 | v8_compat | 1 | failure | False | SHORT_CIRCUIT | 2 | 0.00077724 | `map09.fault_propagation_scale`=1; `map09.hard_threshold_breaches`=1 |
| MAP-09 | v9_fixed | 0 | failure | False | OXYGEN_DEPLETED | 12 | 0.00583508 | `map09.fault_propagation_scale`=1; `map09.hard_threshold_breaches`=1 |
| MAP-09 | v9_fixed | 1 | failure | False | OXYGEN_DEPLETED | 12 | 0.00455940 | `map09.fault_propagation_scale`=1; `map09.hard_threshold_breaches`=1 |
| MAP-10 | v8_compat | 0 | failure | False | GENERATOR_FUEL_SHORTAGE | 3 | 0.001963 | `map10.base_frozen`=0; `map10.fuel_consumed`=3 |
| MAP-10 | v8_compat | 1 | failure | False | GENERATOR_FUEL_SHORTAGE | 4 | 0.00110428 | `map10.base_frozen`=0; `map10.fuel_consumed`=3 |
| MAP-10 | v9_fixed | 0 | success | True | TRANSMISSION_COMPLETE | 6 | 0.00271296 | `map10.base_frozen`=0; `map10.fuel_consumed`=8 |
| MAP-10 | v9_fixed | 1 | success | True | TRANSMISSION_COMPLETE | 6 | 0.00141628 | `map10.base_frozen`=0; `map10.fuel_consumed`=8 |
| MAP-11 | v8_compat | 0 | failure | False | SUPPLY_SHORTAGE | 1 | 0.000648 | `map11.abandoned_reachable_targets`=1; `map11.first_clue_delay`=None |
| MAP-11 | v8_compat | 1 | failure | False | SUPPLY_SHORTAGE | 2 | 0.00084424 | `map11.abandoned_reachable_targets`=1; `map11.first_clue_delay`=2 |
| MAP-11 | v9_fixed | 0 | success | True | FULL_SAFE_RETURN | 6 | 0.00382832 | `map11.abandoned_reachable_targets`=0; `map11.first_clue_delay`=None |
| MAP-11 | v9_fixed | 1 | success | True | FULL_SAFE_RETURN | 6 | 0.00164312 | `map11.abandoned_reachable_targets`=0; `map11.first_clue_delay`=None |
| MAP-12 | v8_compat | 0 | failure | False | RESEARCH_TARGET_MISSED | 60 | 0.04442216 | `map12.research_points_completion`=0.0 |
| MAP-12 | v8_compat | 1 | unknown_provider_spend | False | - | 28 | 0.01856232 | `map12.research_points_completion`=0.0 |
| MAP-12 | v8_compat | 1 | failure | False | RESEARCH_TARGET_MISSED | 60 | 0.03510880 | `map12.research_points_completion`=0.0 |
| MAP-12 | v9_fixed | 0 | unknown_provider_spend | False | - | 18 | 0.01482324 | `map12.research_points_completion`=0.0 |
| MAP-14 | v9_fixed | 0 | decision_budget_reached | False | - | 38 | 0.02332260 | `map14.query_gap_signed`=-3 |
| MAP-15 | v9_fixed | 0 | success | True | GATE_OPENED | 11 | 0.009119 | `map15.invalid_transitions`=3; `map15.loop_states`=0 |
| MAP-18 | v9_fixed | 0 | failure | False | STATION_CAPACITY_EXCEEDED | 7 | 0.00645176 | `map18.collision_violations`=0; `map18.completed_train_moves`=0 |
| MAP-21 | v9_fixed | 0 | failure | False | FATAL_ERUPTION | 6 | 0.00262340 | `map21.scientific_units_evacuated`=0 |
| MAP-22 | v9_fixed | 0 | decision_budget_reached | False | - | 30 | 0.02441584 | `map22.illegal_bearing_actions`=0; `map22.legal_action_rate`=1.0 |
| MAP-26 | v8_compat | 0 | decision_budget_reached | False | - | 38 | 0.02095276 | `map26.diagnosis_accuracy`=None; `map26.legal_action_rate`=0.236842 |
| MAP-26 | v9_fixed | 0 | success | True | ALL_OBJECTIVES_COMPLETE | 13 | 0.00791820 | `map26.diagnosis_accuracy`=1; `map26.legal_action_rate`=0.846154 |
| MAP-29 | v9_fixed | 0 | decision_budget_reached | False | - | 38 | 0.03763236 | `map29.contradiction_detection_rate`=0.0; `map29.evidence_supported_testimony_ratio`=None |

## 2. 同图前后对照

| map | v8_compat | v9_fixed | 变化 |
|---|---|---|---|
| MAP-07 | 0/1（decision_budget_reached） | 1/1（LOW_WATER_STABLE） | 改善 |
| MAP-08 | 0/1（decision_budget_reached） | 0/1（CORE_WATER_LIMIT_EXCEEDED） | 持平 |
| MAP-09 | 0/2（SHORT_CIRCUIT） | 0/2（OXYGEN_DEPLETED） | 持平 |
| MAP-10 | 0/2（GENERATOR_FUEL_SHORTAGE） | 2/2（TRANSMISSION_COMPLETE） | 改善 |
| MAP-11 | 0/2（SUPPLY_SHORTAGE） | 2/2（FULL_SAFE_RETURN） | 改善 |
| MAP-12 | 0/2（另有 1 次 provider 中断）（RESEARCH_TARGET_MISSED） | 无有效 post 局 | 无有效对照 |
| MAP-26 | 0/1（decision_budget_reached） | 1/1（ALL_OBJECTIVES_COMPLETE） | 改善 |

## 3. 关键读数

- **MAP-07**：`v8_compat` 30 决策耗尽、0 次阀门操作；`v9_fixed` 8 决策成功。公开 `control_panel` 后阀门链才真正启动。
- **MAP-10**：0/2 → **2/2**；失败从“未装载”转为完整的装载→发电机→发报链，`fuel_consumed=8`。
- **MAP-11**：0/2 → **2/2**；`abandoned_reachable_targets` 从 1 降到 0，救援链被触发。
- **MAP-26**：0/1（38 决策耗尽、合法率 0.24）→ **1/1**（13 决策、诊断准确率 1、合法率 0.85）。
- **MAP-09**：0/2 → 0/2，但失败从第 2 决策 `SHORT_CIRCUIT` 后移到第 12 决策 `OXYGEN_DEPLETED`；接口修复生效，能力仍未解决。
- **MAP-08**：0/1 → 0/1，但失败从 38 决策耗尽变成 24 决策 `CORE_WATER_LIMIT_EXCEEDED`；模型开始执行机制，仍未完成。
- **MAP-12**：`v8_compat` 两局均 `RESEARCH_TARGET_MISSED`（研究分 0）；`v9_fixed` 未完成（provider 两次 unknown spend），不能宣称在线效果。
- **MAP-06 seed 5**：3 决策 `RESOURCE_EXHAUSTED`，与 seed 0 的 2 决策直达成功形成对照，确认 V8 的 3/3 是实例旁路。
- **MAP-14/18/22/29**：仍在地板/截尾；MAP-14 `query_gap=-3`（从未问询），MAP-18 7 决策 `STATION_CAPACITY_EXCEEDED`，MAP-22/29 决策预算耗尽。
- **MAP-15/21**：MAP-15 11 决策成功（goal 仍泄露规则）；MAP-21 本次 6 决策 `FATAL_ERUPTION`（没有选择直达撤离），说明旁路存在但不等于模型必然使用。

## 4. 解读与限制

- 这是 **E3-pilot**：样本小、单实例 seed、模型单一；不构成 V9 主实验或能力排名。
- `v8_compat` 与 `v9_fixed` 的唯一差别是登记过的公开信息补充；规则、动作集、预算、模型、temperature 相同。
- 失败、截尾、provider 异常与费用全部保留；没有“试到成功为止”。
- 指标并列 V8 旧值与 V9 overlay；overlay 不是 V7 登记指标，不能与旧值相加。

## 5. 账本

| 项目 | 值 |
|---|---|
| settled | ¥0.34049884 |
| pending reserved | ¥0 |
| projected | ¥0.34049884 |
| requests | 512 |
| failed | 2 |
| unknown_spend | 2 |
| closed | True |

