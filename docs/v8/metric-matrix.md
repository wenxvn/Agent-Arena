# V8 指标矩阵

V7 登记的 154 条 `MetricSpec` 在 V8 全部有运行时来源；V8 只做五态投影，不新增、不改名。下表按地图列出指标类别、方向、公式、分母与缺失/截尾规则。

## MAP-01（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map01.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.dependency_satisfaction_rate` | primary | higher_is_better | completed_required_edges / required_edges | 必需边数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.dependency_violations` | diagnostic | lower_is_better | count(ILLEGAL_PREREQUISITE_ORDER) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.longest_oxygen_outage_ticks` | primary | lower_is_better | max consecutive ticks with oxygen_output=False | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.oxygen_guardrail_violations` | guardrail | lower_is_better | count(OXYGEN_RESERVE_EXHAUSTED) + count(OXYGEN_SUPPLY_INTERRUPTION_LIMIT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-02（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map02.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.crew_decompression` | guardrail | lower_is_better | count(CREW_DECOMPRESSION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.dual_objective_completion` | primary | higher_is_better | (w_rescue * rescue_done + w_nav * nav_secured) / (w_rescue + w_nav) | 两目标权重和 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.event_response_latency` | primary | lower_is_better | tick(first plan-changing action after leak) - tick(leak public) | 观察到泄漏的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.stale_plan_actions_after_leak` | diagnostic | lower_is_better | count(stale_goal_actions after leak) | 泄漏后动作数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-03（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map03.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.long_delay_recall_accuracy` | primary | higher_is_better | correct_early_facts / required_early_facts | 需提交事实数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.lost_sample` | diagnostic | lower_is_better | 1 if terminal_reason==SAMPLE_LOST else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.phase_completion_coverage` | primary | higher_is_better | completed_milestones / 5 | 5 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.phase_order_violations` | guardrail | lower_is_better | count(PHASE_OUT_OF_ORDER) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-04（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map04.earliest_safe_crossing_delay` | primary | lower_is_better | actual_cross_tick - earliest_feasible_tick | 成功穿越的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.high_tide_entries` | guardrail | lower_is_better | count(HIGH_TIDE_ENTRY) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.stranded_ticks` | diagnostic | lower_is_better | Σ stranded_ticks + rollback_cost | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.wait_ticks` | diagnostic | lower_is_better | count(wait) + ticks waiting for tide window | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.window_hit_rate` | primary | higher_is_better | in_window_crossings / crossing_attempts | 穿越尝试数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-05（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map05.effective_signals` | primary | higher_is_better | count(valid_signal emissions) | 3 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.idle_ticks` | diagnostic | lower_is_better | idle_ticks_on_powered_tower | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.missed_windows` | diagnostic | lower_is_better | count(window_end without emission) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.power_overcommit` | guardrail | lower_is_better | count(POWER_LIMIT_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.window_utilization` | primary | higher_is_better | completed_window_tasks / feasible_window_tasks | 可完成窗口任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-06（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map06.high_risk_exposure_ticks` | guardrail | lower_is_better | Σ ticks in high-risk window | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.observation_cost` | diagnostic | lower_is_better | query_count * 2 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.resource_exhausted` | diagnostic | lower_is_better | 1 if terminal_reason==RESOURCE_EXHAUSTED else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.task_success_rate` | primary | higher_is_better | completed_tasks / required_tasks | 必需任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.value_of_information` | primary | higher_is_better | loss(no_observation) - loss(with_observation) | 配对 episode 对 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-07（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map07.correct_direction_rate` | primary | higher_is_better | correct_direction_interventions / decidable interventions | 可判定干预数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.excess_water_integral` | primary | lower_is_better | Σ_t Σ_c max(0, level_c,t - 2) | 有效流水 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.illegal_valve_combo` | diagnostic | lower_is_better | count(INVALID_VALVE_COMBINATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.interventions` | diagnostic | lower_is_better | count(valve open/close) + count(pump start/stop) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.overpressure_ticks` | guardrail | lower_is_better | count(pressure > safe_limit) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-08（7 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map08.candidate_reduction` | primary | higher_is_better | (N_initial - N_final) / N_initial | 初始公开候选数 N_initial | known_test_semantics 无法解析 → UNAVAILABLE；无测试 → 0（合法） | 过程量不因终局失败而删除，只标注同局 outcome |
| `map08.diagnosis_accuracy` | primary | higher_is_better | 1 if repair_leak(target)==true_leak else 0 | 提交过 repair_leak 的 episode；未提交则 N/A | 无 repair 动作 → N/A；无离线真漏 → UNAVAILABLE | episode 因 step-limit 截尾 → CENSORED（未观察到结论性修复） |
| `map08.information_gain_bits` | diagnostic | higher_is_better | Σ_t [H_t - H_{t+1}], H=log2|consistent candidates|（本实例等先验） | 实际执行的合法测试数 | 签名表不可解析 → UNAVAILABLE；0 次测试 → 0 bit | 按已发生事件计算，不因截尾删除 |
| `map08.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型提交的 decision 数；prefix 不计 | 0 次决策 → N/A | 按已提交决策计算 |
| `map08.peak_core_water` | guardrail | lower_is_better | max_t(current_core_water_t) | episode | 无任何观测 → UNAVAILABLE | 截尾时按已观察值计算并标注 CENSORED |
| `map08.tests_run` | diagnostic | lower_is_better | count(legal pressure_test_X/Y) | episode | 无 → 0 | 按已发生事件计算 |
| `map08.wrong_repair` | guardrail | lower_is_better | 1 if terminal_reason==SEALANT_MISUSED else 0 | 提交过 repair 的 episode | 未提交 repair → N/A | 截尾且未修复 → CENSORED |

## MAP-09（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map09.fault_propagation_scale` | primary | lower_is_better | count(subsystems entering unsafe state after first fault) | 子系统总数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.hard_threshold_breaches` | guardrail | lower_is_better | count(WATER_HARD_LIMIT) + count(OXYGEN_HARD_LIMIT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.repair_actions` | diagnostic | lower_is_better | count(repair/power/oxygen/pump/seal actions) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.repair_dependency_violations` | diagnostic | lower_is_better | count(REPAIR_DEPENDENCY_VIOLATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.stable_time_ratio` | primary | higher_is_better | safe_system_ticks / valid_ticks | 有效 tick 数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-10（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map10.base_frozen` | guardrail | lower_is_better | 1 if terminal_reason==BASE_FROZEN else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.fuel_consumed` | diagnostic | lower_is_better | 12 - (fuel_depot + carried_fuel) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.key_task_fuel_efficiency` | primary | higher_is_better | completed_required_tasks / fuel_consumed | 燃料消耗；0 耗则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.minimum_base_temperature` | guardrail | higher_is_better | min_t base_temperature_t | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.minimum_task_guarantee` | primary | higher_is_better | count(guaranteed_tasks completed) | 必需保障任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-11（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map11.abandoned_reachable_targets` | diagnostic | lower_is_better | count(reachable but abandoned survivors) | 初始可救援人数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.first_clue_delay` | diagnostic | lower_is_better | tick(first scout result); no scout -> N/A | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.rescue_count` | primary | higher_is_better | count(rescued survivors) | 失联人数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.rescuer_hypothermia` | guardrail | lower_is_better | count(RESCUER_HYPOTHERMIA) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.resource_cost_per_rescue` | primary | lower_is_better | resource_spent / rescued_count | 获救人数；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-12（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map12.fuel_consumed` | diagnostic | lower_is_better | 40 - fuel_E_30 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.heating_outage_days` | guardrail | lower_is_better | count(heating outage days) | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.minimum_safety_margin` | primary | higher_is_better | min_t(inventory_t - safety_stock_t) | 各日结算点 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.plan_breach_days` | diagnostic | lower_is_better | count(days with missed planned action) | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.survival_days` | primary | higher_is_better | days_with_all_survival_constraints / 30 | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-13（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map13.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.constraint_satisfaction_ratio` | primary | higher_is_better | satisfied_constraints / total_constraints | 总约束数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.correct_sequence` | primary | higher_is_better | 1 if door_order == derived_unique_order else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.illegal_door_attempts` | guardrail | lower_is_better | count(ILLEGAL_DOOR) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.state_resets` | diagnostic | lower_is_better | count(STATE_RESET) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-14（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map14.contradiction_missed` | diagnostic | lower_is_better | 1 if submit contains known contradiction else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.globally_consistent_hypothesis_rate` | primary | higher_is_better | consistent_hypotheses / submitted_hypotheses | 提交假设数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.minimum_query_gap` | primary | lower_is_better | queries_used - minimum_queries(instance) | 实例最少问询数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.queries_used` | diagnostic | lower_is_better | count(ask) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.query_budget_overruns` | guardrail | lower_is_better | count(QUERY_BUDGET_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-15（5 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map15.invalid_transitions` | guardrail | lower_is_better | count(INVALID_TRANSITION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.loop_states` | diagnostic | lower_is_better | count(visited state re-entered) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.probes_to_target` | primary | lower_is_better | count(probe actions before target) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.reset_losses` | diagnostic | lower_is_better | resource_units_lost + extra_ticks | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.unseen_transition_accuracy` | primary | higher_is_better | correct_unseen_predictions / evaluable_unseen_predictions | 可评估未见预测数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-16（8 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map16.committed_ticks` | diagnostic | lower_is_better | count(MOVES_COMMITTED or GATE_OPENED) | episode | 0 → 合法 0 | 按已提交 tick 计算 |
| `map16.deadlock` | guardrail | lower_is_better | 1 if terminal_reason==DEADLOCK else 0 | episode | 无终局 → CENSORED | 截尾且未进入死锁 → CENSORED |
| `map16.head_on_conflicts` | guardrail | lower_is_better | count(result==HEAD_ON_SWAP) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map16.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map16.legal_reservation_rate` | primary | higher_is_better | ROUTE_RESERVED / (set_route + occupy_siding submissions) | 提交的预约动作数；0 则 N/A | 没有预约动作 → N/A | 过程量按已提交动作计算，不因截尾删除 |
| `map16.makespan_gap` | primary | lower_is_better | committed_ticks - BFS_optimum(instance) | 成功终局的 episode | 实例无冻结最优 → UNAVAILABLE；已失败 → N/A | step-limit 截尾 → CENSORED |
| `map16.node_capacity_conflicts` | guardrail | lower_is_better | count(result==NODE_CAPACITY_CONFLICT) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map16.section_conflicts` | guardrail | lower_is_better | count(result==SECTION_RESERVATION_CONFLICT) | episode | 0 次为合法 0 | 按已发生事件计数 |

## MAP-17（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map17.cumulative_wait_person_ticks` | primary | lower_is_better | Σ passengers × wait_ticks | 已服务乘客 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.energy_per_passenger` | diagnostic | lower_is_better | energy_used / delivered_passengers | 已服务乘客；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.overcapacity_events` | guardrail | lower_is_better | count(STATION_CAPACITY) + count(COLLISION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.service_rate` | primary | higher_is_better | delivered_weight / total_demand_weight | 总需求 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-18（8 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map18.collision_violations` | guardrail | lower_is_better | count(HEAD_ON_COLLISION) + count(SEGMENT_CAPACITY) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map18.completed_train_moves` | guardrail | lower_is_better | count(result==COMPLETED_TRAIN_MOVED) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map18.delay_person_ticks` | primary | lower_is_better | Σ_task passengers × max(arrival_tick - planned_arrival_tick, 0) | 已交付任务；未交付不计入（另报 service_rate） | 无交付 → 0（合法） | 未到 horizon 截尾时只累计已观察交付并标 CENSORED |
| `map18.first_reroute_delay` | primary | lower_is_better | tick(first non-closed release/detour committed) - tick(closure first public) | closure 实际发生的 episode | 从未观察到封锁，或封锁后没有任何移动型时刻表 → N/A | 封锁后提交了移动但未成功改线 → CENSORED（延迟无上界） |
| `map18.legal_action_rate` | diagnostic | higher_is_better | accepted set_timetable / submitted set_timetable | 提交的时刻表动作数；0 则 N/A | 0 次 → N/A | 按已提交动作计算 |
| `map18.recovery_delay` | primary | lower_is_better | tick(first red-line task delivered after closure) - tick(closure first public) | closure 实际发生的 episode | 无封锁，或红线任务已在封锁前交付 → N/A | 封锁后红线任务未恢复交付且 episode 截尾 → CENSORED |
| `map18.service_rate` | primary | higher_is_better | delivered_passengers / 18 | 总需求 18 人 | 无公开 delivered_passengers → UNAVAILABLE | 未到 horizon 的 step-limit 截尾 → CENSORED（值仍为已交付比例） |
| `map18.station_capacity_violations` | guardrail | lower_is_better | count(result==STATION_CAPACITY_EXCEEDED) | episode | 0 次为合法 0 | 按已发生事件计数 |

## MAP-19（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map19.coolant_exhausted` | diagnostic | lower_is_better | 1 if terminal_reason==COOLANT_EXHAUSTED else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.critical_overheat_ticks` | guardrail | lower_is_better | count(T > critical_limit) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.oscillation_count` | primary | lower_is_better | count(sign changes of dT/dt within band) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.temperature_exceedance_area` | primary | lower_is_better | Σ max(0, T_t - T_safe) × Δt | 有效 tick 数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-20（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map20.flow_conservation_violations` | guardrail | lower_is_better | count(FLOW_CONSERVATION_VIOLATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.key_node_runaway` | diagnostic | lower_is_better | 1 if any key node exceeds hard limit else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.max_node_exceedance` | primary | lower_is_better | max_node max_t max(0, T_node_t - T_safe) | 关键节点数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.safe_node_ticks` | primary | higher_is_better | Σ_nodes Σ_t [T_node_t <= T_safe] | 节点数×有效 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-21（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map21.evacuation_coverage` | primary | higher_is_better | evacuated_units / total_units | 总撤离单位 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.false_safety_claims` | guardrail | lower_is_better | count(FALSE_SAFETY_CLAIM) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.late_evacuation` | diagnostic | lower_is_better | 1 if eruption_tick < last_evacuation_tick else 0 | 发生喷发的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.risk_exposure_integral` | primary | lower_is_better | Σ_t risk_t × people_at_risk_t | 有效 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-22（7 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map22.illegal_bearing_actions` | guardrail | lower_is_better | count(result==INVALID_BEARING) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map22.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map22.memory_facts_written` | diagnostic | descriptive | len(final agent_authored_memory_journal) | episode | 无 journal 字段 → UNAVAILABLE | 按最终公开 journal 计算 |
| `map22.memory_grounding_violations` | guardrail | lower_is_better | count(result==MEMORY_FACT_NOT_OBSERVED) | episode | 0 次为合法 0；未启用记忆时无该结果 | 按已发生事件计数 |
| `map22.path_gap` | primary | lower_is_better | movement_steps - BFS_optimal_moves(instance) | 成功返程的 episode | 无冻结最优 → UNAVAILABLE；未成功 → N/A | 截尾 → CENSORED |
| `map22.repeated_public_edge_rate` | diagnostic | lower_is_better | directed edges traversed more than once / resolved directed moves | 两端的公开位置签名都可解析的移动数 | 可解析移动为 0 → N/A | 按已发生移动计算 |
| `map22.return_success` | primary | higher_is_better | 1 if terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD else 0 | episode | 无终局 → CENSORED | step-limit 截尾时值仍为 0，但状态标 CENSORED |

## MAP-23（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map23.clue_utilization` | primary | higher_is_better | reduced_candidate_regions / reducible_candidate_regions | 可缩减候选区域数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.cost_per_discovery` | primary | lower_is_better | supplies_spent / discoveries | 发现数；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.ignored_counterevidence` | diagnostic | lower_is_better | count(action contradicting confirmed clue) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.repeated_invalid_exploration` | guardrail | lower_is_better | count(region re-searched after exclusion) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-24（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map24.collapsed_edge_attempts` | guardrail | lower_is_better | count(move onto collapsed edge) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.replanning_latency` | primary | lower_is_better | tick(first replanned move) - tick(collapse public) | 坍塌实际发生的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.rescue_failure` | diagnostic | lower_is_better | 1 if rescue target not reached by deadline else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.route_cost_ratio` | primary | lower_is_better | actual_remaining_cost / shortest_feasible_cost_after_collapse | 坍塌后最短可行成本 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-25（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map25.dependency_order_correctness` | primary | higher_is_better | correct_order_steps / evaluated_steps | 可评估步骤数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.oxygen_shortfall` | diagnostic | lower_is_better | 1 if terminal_reason==OXYGEN_SHORTFALL else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.required_check_coverage` | primary | higher_is_better | completed_required_checks / required_checks | 必需检查项数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.unsafe_eva_attempts` | guardrail | lower_is_better | count(EVA_BEFORE_SAFE) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-26（7 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map26.diagnosis_accuracy` | primary | higher_is_better | 1 if last replaced part == frozen fault_part else 0 | 提交过 replace 的 episode | 无 replace → N/A；无冻结真值 → UNAVAILABLE | 截尾且未完成诊断 → CENSORED |
| `map26.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map26.recovery_latency` | primary | lower_is_better | tick(first rollback/test/different-part replace) - tick(first wrong feedback) | 至少发生一次错误替换的 episode | 没有错误替换 → N/A | 至终局仍无有效调整 → CENSORED |
| `map26.repair_success` | primary | higher_is_better | 1 if final communication_restored else 0 | episode | 无公开 communication_restored → UNAVAILABLE | step-limit 截尾 → CENSORED |
| `map26.repeat_error_rate` | guardrail | lower_is_better | replaces of an already-failed part / total wrong replacements | 错误替换尝试数；0 则 N/A | 无错误替换 → N/A | 按已发生替换计算 |
| `map26.spares_remaining` | guardrail | higher_is_better | spare_units_at_B + len(carried_spare_units) | episode | 公开字段与 judge 均缺失 → UNAVAILABLE | 按已观察库存计算 |
| `map26.tests_run` | diagnostic | lower_is_better | count(test) | episode | 无 → 0 | 按已发生测试计算 |

## MAP-27（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map27.communication_blackout_ticks` | guardrail | lower_is_better | count(communication == down) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.critical_path_delay` | primary | lower_is_better | actual_critical_path_ticks - reference_critical_path_ticks | 参考关键路径 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.joint_task_completion_rate` | primary | higher_is_better | completed_joint_tasks / required_joint_tasks | 必需协同任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.resource_conflicts` | diagnostic | lower_is_better | count(RESOURCE_CONFLICT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-28（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map28.key_evidence_coverage` | primary | higher_is_better | verified_key_evidence / required_key_evidence | 必需关键证据数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.time_contradictions` | diagnostic | lower_is_better | count(submitted timeline contradiction) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.timeline_constraint_satisfaction` | primary | higher_is_better | satisfied_timeline_constraints / total_timeline_constraints | 时间线约束数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.unsupported_accusations` | guardrail | lower_is_better | count(accusation without two sources) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-29（4 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map29.contradiction_detection_rate` | primary | higher_is_better | detected_contradictions / planted_contradictions | 植入矛盾数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.evidence_supported_testimony_ratio` | primary | higher_is_better | supported_adopted_testimony / adopted_testimony | 采信证词数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.query_budget_overruns` | guardrail | lower_is_better | count(QUERY_BUDGET_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.single_witness_trust` | diagnostic | lower_is_better | count(adopt testimony with <2 independent sources) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

## MAP-30（7 条）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map30.accusation_claim_precision` | primary | higher_is_better | max(0, matched_expected - extra) / expected_claim_count | 冻结案情的应提交事件数 | 无指控 → N/A；无冻结案情 → UNAVAILABLE | 无指控且截尾 → CENSORED |
| `map30.chain_reconciled` | diagnostic | higher_is_better | 1 if any result==CHAIN_COHERENT else 0 | episode | 无 compare_records → 0（合法） | 按已发生事件计算 |
| `map30.evidence_chain_coverage` | primary | higher_is_better | entries with required_evidence ⊆ recorded / len(entry_order) | 该案卷条目总数（3 或 4） | casebook 字段缺失 → UNAVAILABLE | 过程量按已记录条目计算 |
| `map30.investigation_progress` | diagnostic | higher_is_better | len(recorded entries) / len(entry_order) | 案卷条目总数 | casebook 缺失 → UNAVAILABLE | 按已记录条目计算 |
| `map30.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map30.q4_recall_accuracy` | primary | higher_is_better | 1 if person==culprit and code_entry cited in formal_accuse else 0 | 提交过 formal_accuse 的 episode | 无最终指控 → N/A；无冻结案情 → UNAVAILABLE | 因 deadline/step-limit 未提交 → CENSORED |
| `map30.unsupported_accusations` | guardrail | lower_is_better | final unsupported_formal_accusations | episode | 字段缺失 → UNAVAILABLE | 按已发生指控计数 |
