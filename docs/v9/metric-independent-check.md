# V9 指标独立第二路径

- 代码：`src/agent_arena/v9/metric_checks/`（`part_a`–`part_d`）
- 运行：`python -c "from agent_arena.v9.metric_checks.base import run_all; print(run_all())"`
- 输出：`runs/v9/metric_checks/MAP-XX.json`、`runs/v9/metric_checks/summary.json`

## 1. 方法与独立性约束

- 每张图选 **R0 + 首条非 R0**（优先成功局），共 60 条 Trace。
- 每条 Trace 至少复算 **1 个 primary + 1 个 guardrail/diagnostic**，共 **120 条检查**。
- 复算只读：Trace 的公开 Observation 流、结果码、`judge_state`；**不调用** `environment.metrics()`、V7 extractor、V8 `project_metrics`。
- 复算公式来自 V7 登记卡与设计稿，不是从实现反推；实现口径与登记口径不一致时，检查按实现值复算并在 note 标出缺陷（否则无法定位是“算错”还是“定义错”）。

## 2. 结果

| 指标 | 数值 |
|---|---:|
| 检查数 | 120 |
| 与 V8 投影一致 | **120** |
| 不一致 | 0 |
| 无法复算 | 0 |
| 覆盖地图 | 30/30 |
| 覆盖 Trace | 60/90（每图 2 条） |

**结论**：V8 的投影数值本身是可复算的；问题不在“算错数”，而在**指标定义/事件口径**与构念不一致。

## 3. 逐图检查

| map | primary 复算 | 第二路径 |
|---|---|---|
| MAP-01 | `dependency_satisfaction_rate` 2/6、1/6、0/6 | `oxygen_guardrail_violations` |
| MAP-02 | `dual_objective_completion` 0/0.5 | `stale_plan_actions_after_leak` |
| MAP-03 | `phase_completion_coverage` 1/5–3/5 | `lost_sample` |
| MAP-04 | `window_hit_rate` N/A / 1/2 | `high_tide_entries` |
| MAP-05 | `effective_signals` 0/3、1/3 | `missed_windows` |
| MAP-06 | `task_success_rate` 1.0 | `observation_cost` |
| MAP-07 | `excess_water_integral` 180 | `overpressure_ticks` 0 |
| MAP-08 | `candidate_reduction` 0.0 | `legal_action_rate` 4/38、6/38 |
| MAP-09 | `stable_time_ratio` 0.5 | `hard_threshold_breaches` 1 |
| MAP-10 | `fuel_consumed` 2/7 | `base_frozen` 0 |
| MAP-11 | `rescue_count` 0 | `first_clue_delay` 2 |
| MAP-12 | `fuel_consumed` 30 | `survival_days` 1.0 |
| MAP-13 | `constraint_satisfaction_ratio` 0.2/0.8 | `illegal_door_attempts` 3/0 |
| MAP-14 | `minimum_query_gap` 0 | `queries_used` 0 |
| MAP-15 | `unseen_transition_accuracy` 1.0/0.0 | `invalid_transitions` 1 |
| MAP-16 | `legal_reservation_rate` 1.0/0.4 | `deadlock` 1/0 |
| MAP-17 | `service_rate` 0.4/0.2 | `cumulative_wait_person_ticks` 18/22 |
| MAP-18 | `service_rate` 12/18、6/18 | `station_capacity_violations` 0/1 |
| MAP-19 | `temperature_exceedance_area` 3/15 | `critical_overheat_ticks` 0/1 |
| MAP-20 | `max_node_exceedance` 20/0 | `safe_node_ticks` 29/30 |
| MAP-21 | `evacuation_coverage` 2/2、1/1 | `late_evacuation` 0 |
| MAP-22 | `return_success` 0 | `legal_action_rate` 0.93/1.0 |
| MAP-23 | `clue_utilization` 1.0 | `cost_per_discovery` N/A/9.0 |
| MAP-24 | `rescue_failure` 1/0 | `collapsed_edge_attempts` 0 |
| MAP-25 | `required_check_coverage` 7/7 | `dependency_order_correctness` |
| MAP-26 | `spares_remaining` 2 | `legal_action_rate` 0.39/0.45 |
| MAP-27 | `joint_task_completion_rate` 0.0 | `resource_conflicts` 0 |
| MAP-28 | `key_evidence_coverage` 0.25/0.75 | `timeline_constraint_satisfaction` 0.0 |
| MAP-29 | `contradiction_detection_rate` 0.0 | `query_budget_overruns` 0 |
| MAP-30 | `evidence_chain_coverage` 0.0 | `legal_action_rate` 0.80 |

## 4. 复算过程中确认的指标缺陷

这些条目在数值上 `match=True`，但**定义与事件口径**有证据问题：

1. **MAP-13 `illegal_door_attempts`**：登记 `count(ILLEGAL_DOOR)`，实现把 `STATE_RESET` 也计入；R0 报 3，字面只有 1。
2. **MAP-13 `constraint_satisfaction_ratio`**：docstring 是“最后一次试排”，实现取“最后一次被 verify 的布局”；R0 报 0.2，按 docstring 是 0.6。
3. **MAP-14 `minimum_query_gap`**：`max(0, queries - minimum)` 把“不问”变成 lower_is_better 的最优（0）；`queries_used` 方向相同，两个指标一起奖励欠问。
4. **MAP-17 `overcapacity_events`**：登记 `STATION_CAPACITY + COLLISION`，实现把 `PLATFORM_CAPACITY` 也算入；R1 报 1 但登记口径为 0。
5. **MAP-18 `legal_action_rate`**：`COMPLETED_TRAIN_MOVED`（整行被拒、tick 不变）被算作接受；R2 报 8/12，实际 5 行提交成功。
6. **MAP-19 `temperature_exceedance_area`**：声明分母“有效 tick 数”，实现返回未归一化和；R0 5 tick 得 3、R2 2 tick 也得 3，跨局不可比；截尾局仍投影 `valid`。
7. **MAP-21 `evacuation_coverage`**：成功时分子恒等于分母（已投入单位），本质是 0/1 指示器；测量会抬高分母，失败时反而“覆盖更差”。
8. **MAP-23 `cost_per_discovery`**：`resupply` 注入的 6 点未计入，真实支出 15 被低估为 9。
9. **MAP-24 `replanning_latency`**：对“没改路”报 1（R2），对“死守旧路”报 None；事件定义与构念相反。
10. **MAP-25 覆盖率**：被拒的 `diagnose(device_id="array")` 记为完成，R2 7/7 与 `diagnosed=False` 矛盾。
11. **MAP-26 `tests_run`/`diagnosis_accuracy`**：被拒测试/被拒 replace 计入分母；R2 4 次全拒仍报 `tests_run`。
12. **MAP-28 `timeline_constraint_satisfaction`**：从未 submit 与提交错都记 0.0，未区分 N/A。
13. **MAP-30 `investigation_progress` vs `evidence_chain_coverage`**：记录 2 条可得 0.5，但证据链 0.0，说明“记录≠证据”。

## 5. 未复算项与原因

- MAP-24 `route_cost_ratio`：需要“坍塌后同点最短成本”，R0 在 B 被隔离、R1 在 A 成本 0；两局均为 `None`，无法独立区分“真缺失”与“口径边界”。
- MAP-21 `risk_exposure_integral`：依赖逐 tick 后验与喷发分布耦合；两局 1–2 决策直达 E，Trace 无法重建中间量。
- MAP-19 `forecast_next` 误差：V8 已无该指标，三局 0 次使用。

## 6. 证据边界

- 本轮只覆盖 60/90 条 Trace；剩下 30 条可用于 V10 的扩展第二路径。
- “一致”只证明数值可复算，不证明指标有效；有效性判断见各图 §6 与 `docs/v9/dcr/DCR-09.md`。
- 复算使用 `judge_state`（离线核对允许），但没有把它用于任何公开策略。
