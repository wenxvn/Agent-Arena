# V10 指标 schema 与五态语义

- 版本：`metric_schema_version = "v10"`；`schema_hash` 由 `agent_arena.v10.metrics.governance.schema_hash()` 实时计算
- 当前 `schema_hash`：`0bf8121dc3b29b199d42afb20e02b93a34417d8929bc6524b1a1a3f15c35a273`（154 + 140 条规格、25 张原生图）
- 旧值：V7/V8 的 154 条注册指标与 V8/V9 的投影值**原样保留**，不覆盖、不跨版本求均值
- 生成：`python -c "from agent_arena.v10.metrics.governance import *; print(schema_hash())"`

## 1. 154 项枚举

`agent_arena.v7.metrics.registry.all_specs()` 提供 **154** 条指标规格（30 图 × 4–6 条）。
其中 6 张图（08/16/18/22/26/30，均为 V4 适配图）有运行时 extractor，其余 24 张为 design-only。

V10 的处理：

| 类别 | 数量 | 处理 |
|---|---:|---|
| V7/V8 注册规格 | 154 | 只读保留；`metric_id`、`formula`、`valid_range` 不改写 |
| V10 新增规格 | **159** | 28 张 V10 原生图的 `METRIC_SPECS`，逐条带 `role/direction/formula/denominator/zero_denominator/censored_rule/unit/valid_range/event_source/comparable_scope` |
| 合计可寻址指标 | 313 | 两套并列；跨版本只做“语义同构量”的定性对照 |

## 2. 五态与优先级

| 优先级 | 状态 | 触发条件 |
|---:|---|---|
| 1 | `INVALID_TRACE` | 轨迹不可解析，或与环境回放不一致 |
| 2 | `UNAVAILABLE` | 本该有的事件来源缺失（外部 judge 丢失、账本未结算） |
| 3 | `NOT_APPLICABLE` | **真分母为 0**：该指标定义的事件从未发生且不可能发生 |
| 4 | `CENSORED` | 预算截尾时事件尚未发生，但继续运行仍可能发生 |
| 5 | `VALID` | 可计算 |

硬性约束：

- **不能把 `None` 机械改成 `CENSORED`**。部分进度类指标（阶段完成度、覆盖率、已结算区·tick）在截尾时仍 `VALID`；
- 失败但事件确实发生（例如提交了错误答案）→ `VALID` 且取值为失败值，不是 `N/A`；
- 分母为 0 且**不可能**发生 → `N/A`；分母为 0 但**本可以**发生只是没做 → `VALID 0` 或 `CENSORED`，按指标定义的 `zero_denominator` 字段决定。

## 3. 13/20 项缺陷的处理结论

V9 `failure-taxonomy.md` 中带 `METRIC_DEFECT` 标签的地图实测为 **20 张**（提纲 §8.1 提到的“13 项”是其中被逐条复核的子集）。逐图结论记录在 `src/agent_arena/v10/metrics/governance.py::DEFECT_RESOLUTIONS`，与 DCR 对应：

| 图 | 缺陷 | V10 处理 | 证据 |
|---|---|---|---|
| MAP-02 | `response_latency` 恒 1 | 改用 `adaptive_response_within_2`；latency 降为 diagnostic | DCR-09 / V8 只读 |
| MAP-03 | `long_delay_recall_accuracy` 与成功共线 | 拆成 `code_recall_correct` + `memory_gap_actions` | DCR-V10-01 §7 |
| MAP-04 | `earliest_safe_crossing_delay` 未走 S_G 时为空；area 无分母 | 主指标改 `time_margin`；零分母 → N/A | DCR-V10-08 §7 |
| MAP-05 | `missed_windows` 与 `effective_signals` 重叠 | 前者降 diagnostic | V9 metric-check §3 |
| MAP-06 | `info_value_of_observation` 恒 None | 改用 `risk_time_utility` + `utility_regret` | DCR-V10-03 §7 |
| MAP-12 | `survival_days` 与 `fuel_consumed` 混用 | 改用 `research_completion` + `min_food` | DCR-V10-22 §7 |
| MAP-12 | `research_completion` 声明 `(0,1)` 但 Oracle 会超额研究（1.09–1.12） | 范围改 `(0,3)`、公式注明“可 >1”；新 `metric_hash` `f4549bd7…`、新 `schema_hash` `e9b5a143…` | DCR-V10-23 + `independent-metric-check.md` |
| MAP-13 | `illegal_door_attempts` 混合未成型与错排 | 拆两计数；未试排 → N/A | DCR-V10-15 §7 |
| MAP-14 | `minimum_query_gap` 欠问截 0；`queries_used` 反向 | 改用 `deduction_success` + `consistent_hypothesis_rate` | DCR-V10-09 §7 |
| MAP-15 | `unseen_transition_accuracy` 与成功共线 | 改用 `test_gate_first_try_accuracy` + `rule_generalization` | DCR-V10-04 §7 |
| MAP-17 | `overcapacity_events` 计入口径错 | 按“被拒绝的预约”重算并单列 guardrail | V9 metric-check §3 |
| MAP-18 | replanning 指标在截断预算下误标 valid | 按声明 censored 口径处理 | DCR-V10-02 §7 |
| MAP-19 | area 无分母；forecast 误差无出口；`coolant_exhausted` 恒 0 | area 带分母；新增 `mean_forecast_error`；删不可达指标 | DCR-V10-10 §7 |
| MAP-20 | 旁路损耗参数与产能线性冲突 | 产能与热量解耦；新增 `bypass_used_ticks` | DCR-V10-11 §7 |
| MAP-21 | `terminal_score` 未登记；`risk_exposure` 奖励直达 | 拆分 safety/science/overall；risk_exposure 降 guardrail | DCR-V10-05 §7 |
| MAP-22 | journal 不参与任何指标 | `route_recall` 直接读 `agent_notes` | DCR-V10-12 §7 |
| MAP-23 | `cost_per_discovery` 分母 0；覆盖率计被拒 | `clue_utilization` 带分母；`unjustified_investigations` 单列 | DCR-V10-13 §7 |
| MAP-24 | `replanning_latency` 对任何非桥边置位；ratio 分母歧义 | 改 `replan_success` + 观察后 latency | DCR-V10-14 §7 |
| MAP-25 | 覆盖率计入被拒诊断 | 按“被接受的诊断”重算 | V9 metric-check §3 |
| MAP-26 | `tests_run` 计入被拒；`no_diagnosis` 也成功 | 改为 `spares_used` / `wrong_swaps` / `diagnosis_precision` | DCR-V10-17 §7 |
| MAP-30 | `accusation_claim_precision` 统计未进法庭的指控；q4 未要求入卷 | 只统计被接受指控；q4 要求条目已记录 | DCR-V10-07 §4 |

## 4. 主指标政策

`primary_policy()` 逐图给出 1–2 条主指标（23 张 V10 图共 23 组）。规则：

- 每图**恰好 1 条**主指标（部分图另有 1 条并列 primary，如 MAP-06 的 `risk_time_utility` + `utility_regret`）；
- 其余分为 `secondary` / `guardrail` / `diagnostic`；
- **跨图只比较语义同构量**（成功率、时间余量、资源余量、覆盖率等），不做“把 282 项加总成单一榜单”；
- 允许能力剖面/雷达图，但必须标注每轴的单位与 `valid_range`。

## 5. 五态核对（独立于各图内部计算）

`audit_states(map_id, seed, actions)` 是**规格驱动**的检查，不信任各图 `v10_metrics()` 的实现：

1. 投影出来的每条指标都必须在该图 `METRIC_SPECS` 中注册；
2. `VALID` ⇒ 取值非 None 且在 `valid_range` 内；
3. `NOT_APPLICABLE` / `CENSORED` / `UNAVAILABLE` / `INVALID_TRACE` ⇒ 取值必须为 None。

覆盖场景（`tests/test_v10_batch6.py`）：Oracle 成功、合法失败、预算截尾、零分母、非法动作、缺失事件、跨 seed。

## 6. 血缘

每条 V10 指标都可追溯到：`map_id` + `rule_hash` + `scenario_hash` + `metric_schema_hash` + `runner` 的 `V10PolicyRun.metrics`。
`metric_hash(map_id)` 是该图 `METRIC_SPECS` 的哈希；`schema_hash()` 是 154 + 128 的整体身份。
旧数据重算只作为**历史再解释**，不写回 V8/V9 文件（`freeze verify` 每次批末校验 9/9 `unchanged`）。
