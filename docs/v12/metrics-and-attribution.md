# V12 指标与失败归因

## 1. 指标来源：只读 V10，不新增公式

V12 **没有**发明新指标。所有数值来自 V10 各图的 `v10_metrics()` 与
`v10.metrics.schema.MetricSpec`：

- 每条 `MetricSpec` 有 `role`（primary/secondary/guardrail/diagnostic）、`direction`、
  `formula`、`denominator`、`zero_denominator`、`censored_rule`、`valid_range`；
- V12 只做**投影与聚合**：`lab/compare.py::aggregate_metrics`；
- 五态原样保留：`VALID` / `CENSORED` / `NOT_APPLICABLE` / `INVALID_TRACE` / `UNAVAILABLE`，
  导出层额外允许 `MISSING` 表示"该局没有这条指标"。

### 聚合规则（硬约束）

| 情形 | 处理 |
|---|---|
| `VALID` 且 `value` 是数值 | 进入均值 |
| `VALID` 且有 `numerator`/`denominator` | 同时算合并比值（pooled） |
| `CENSORED` / `NOT_APPLICABLE` / `UNAVAILABLE` / `INVALID_TRACE` | **只计频次，不进均值，不补 0** |
| 整图没有任何 `VALID` | `mean=null`，`not_computed_reason="没有任何 VALID 取值；不补零"` |
| 跨图 | **不做**绝对分平均；按图分别给出 |

### 六图重点指标（实际运行时字段）

| 地图 | 主指标 | 关键次指标/护栏 |
|---|---|---|
| MAP-08 漏点诊断 | `map08.v10.mission_success` | `hypothesis_reduction`、`tests_used`、`wrong_repairs`、`unjustified_repairs` |
| MAP-16 单线预约 | `map16.v10.mission_success` | `legal_action_rate`、`node_capacity_conflicts`、`deadlock_count`、`makespan_gap` |
| MAP-18 故障传播 | `map18.v10.service_rate` | `recovery_delay_ticks`、`conflict_terminal`、`closed_entry_attempts`、`window_violations` |
| MAP-22 无地图丛林 | `map22.v10.mission_success` | `route_recall`、`wasted_moves`、`memory_writes`、`goal_recorded` |
| MAP-26 失败维修 | `map26.v10.mission_success` | `spares_used`、`wrong_swaps`、`rollbacks`、`diagnosis_precision` |
| MAP-30 午夜审判 | `map30.v10.evidence_chain_coverage` | `accusation_claim_precision`、`q4_recall_accuracy`、`chain_reconciled`、`unsupported_accusations` |

（字段名由 `create_environment(map_id).METRIC_SPECS` 在运行时核验，不手写假设。）

## 2. 代价指标

| 指标 | 来源 | 说明 |
|---|---|---|
| 请求数 | `usage.requests` | **包含** Planner/Reflection 的额外请求 |
| 输入/输出 token | `usage.input_tokens` / `output_tokens` | 同上 |
| 费用 | `usage.cost_settled_cny` | 只有登记价目的模型才有值 |
| 未知消费 | `usage.cost_unknown` | `true` 时该局不进成本对比 |
| 延迟 | `usage.latency_ms` | Provider 墙钟 |
| 决策数 | `decision_count` | 与预算上限比较 |
| 被拒/非法动作 | `rejected_actions` / `invalid_actions` | 冻结口径（`REJECT_MARKERS`） |

`lab/gateway.py::GatewayStats.purposes` 额外记录 `decision` / `planner` / `reflection` 的
请求分布，便于证明"规划的额外调用没有被隐藏"。

## 3. 失败归因：三层，全部可复核

### 第 1 层：运行类别（互斥、穷尽）

`lab/compare.py::classify_child` → `completed_success` / `mechanism_failure` /
`budget_censored` / `cancelled` / `provider_error` / `interrupted` / `invalid_run` / `pending`。

**Provider 错误不是认知失败**；预算截尾不是失败，是"没测完"。

### 第 2 层：机制归因（复用 V10）

`web/attribution.py` 的标签：`TRIGGERED` / `CONTRACT_ARTIFACT` /
`KEY_ACTION_NEVER_ATTEMPTED` / `KEY_ACTION_ATTEMPTED_REJECTED` /
`KEY_ACTION_USED_NO_TRIGGER` / `INCOMPLETE`。

`CONTRACT_ARTIFACT`（非法动作 > 50%）的局**不能**用于能力结论。

### 第 3 层：证据级诊断（V12 新增）

`lab/diagnostics.py::diagnose_run` 产出 `Finding`：

| 字段 | 含义 |
|---|---|
| `category` | 诊断类别（见下表） |
| `severity` | `critical` / `warning` / `info` |
| `evidence_event_ids` | **具体** `step-<n>` 事件 ID |
| `evidence_steps` | 对应 `decision_index` |
| `summary` / `detail` | 只描述观察到的行为 |
| `source` | 固定 `deterministic_trace_rule` |
| `confidence_scope` | `behavior_observed_not_internal_cause` / `interface_not_behavior` / `infrastructure_not_behavior` |
| `suggested_check` | 下一次可验证的检查项 |

诊断类别：

| 类别 | 触发规则 | 严重度 |
|---|---|---|
| `contract_artifact` | 非法动作 > 50% | critical |
| `provider_error` | 运行状态为 Provider 错误 | critical |
| `unsupported_accusation` | MAP-30 指控被拒或条目不足 | critical / warning |
| `budget_censored` | 决策/预算耗尽 | info |
| `cancelled` / `interrupted` | 用户取消 / 进程中断 | info |
| `repeated_action_loop` | 同工具同结果连续 ≥3 步 | warning |
| `repeated_rejected_action` | 同上且结果为拒绝 | warning |
| `no_progress_window` | 公开进度指纹连续 ≥4 步不变 | warning |
| `key_action_never_attempted` | 机制动作一次未调用 | warning |
| `key_action_attempted_rejected` | 机制动作全被拒 | warning |
| `key_action_used_no_trigger` | 机制动作被接受但未触发 | warning |
| `unused_public_tests` | MAP-08 未测试就维修 | warning |
| `premature_commit` | 前置条件未满足就封存/返程 | warning |
| `frame_mismatch` | MAP-16 未登记路由就 `move_train` | warning |
| `window_violation` | MAP-18 早于公开窗口发车 | warning |
| `memory_not_used` | MAP-22 未写方位记忆 | warning |
| `blind_swap` | MAP-26 未测试就换件 / 换件 ≥3 次 | warning |
| `NOT_ENOUGH_EVIDENCE` | 未命中任何规则 | info |

**明确不做**：

- 不断言"模型认为/模型以为"；
- 不在核心诊断里调用 LLM（可选 LLM 解说默认关闭，V12 未实现）；
- 不把 Provider 错误或预算截尾写成策略失败；
- 不读取 `judge_state` / `sealed_truth`（`lab/adapters.py::assert_public` 强制扫描）。

## 4. 轨迹 Diff

`lab/diagnostics.py::pairwise_diff`：

- 用 `(tool, 结果类别, 动作 JSON)` 作为步签名；
- 步数不同时用**长度差异 + 锚点**（`tick` / `location` / `current_sign` / `node`），
  不硬减第 n 步；
- 输出"首次有意义差异 + 锚点 + 指标增量 + 可验证假设"。

`diff_hypotheses` 只给三类行：`evidence`（已有证据）、`gap`（不足证据）、
`hypothesis`（下一次可验证假设）。

## 5. 可复算性

- `summary.json` 的有效分母可从 `exports/runs.csv` 独立重算（`scripts/verify_v12.py` 的
  `export_recompute` 检查项即此）；
- `metrics.csv` 行数 = 所有子局 `result.metrics` 条目总数；
- `paired_comparison.csv` 每行都带 `left_run_id` / `right_run_id` / `verdict` / `reasons`；
- 报告里每个数字都能追到 `runs/web/<run_id>/result.json`。
