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
| `memory_key_not_in_metric` | MAP-22 未使用指标口径内的键（bearing/path_state） | warning |
| `memory_sequence_short` | MAP-22 写入方位数 < 真实 move 数的一半（记了但太短） | warning |
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

## 6. 可访问性

V12 新增自动审计（`scripts/a11y_v12.py` + `src/agent_arena/lab/a11y.py`），分三层：

| 层 | 规则 | 可离线运行 |
|---|---|---|
| 主题对比度 | 文字 token ≥ 4.5:1（WCAG AA）、填充/边框 ≥ 3:1，浅色与深色各查一遍 | 是 |
| 焦点样式 | 样式表不得抑制轮廓，必须有 `:focus-visible` | 是 |
| 浏览器 DOM/键盘 | 可交互元素必须有可访问名、页面必须有 h1、标题不跳级、图片有 alt、Tab 焦点必须前进且可见 | 需 Playwright |

**审计发现并修复的真实缺陷**（不是"补一个报告"）：

1. `--aa-warning` 在白底只有 **2.65:1**，低于 3:1；其余 tone 文字色（accent 4.32、success 3.37、
   danger 3.91、info 3.87、neutral 3.02）也低于 AA 4.5:1。修复：拆出 `--aa-*-text`
   文字 token（浅色/深色两套，经 `prefers-color-scheme` 切换），填充色保留原值；
   `--aa-warning` 填充色微调到 3.05:1。
2. 页面标题层级是 `h1 → h3`（`st.title` + `st.subheader`），跳级。修复：区块标题改用
   `st.header`（h2），并把原来的"左侧强调条"视觉样式移到 h2，外观不变、语义正确。
3. `st.json` 的工具栏含无名称图标按钮。修复：费用边界改用表格渲染。
4. 审计脚本自身有两处误报（折叠 expander 内的按钮被当成可见；同名锚点链接被当成焦点陷阱），
   已改为 `checkVisibility` + `details:not([open])` 判定，并用元素标识而非"标签+文本"去重。

**已知框架限制**：`<html lang>` 由 Streamlit 前端固定为 `en`，应用层无法覆盖；中文内容
需要屏幕阅读器手动切换语言。已在报告中单列，不计为通过也不计为失败。

当前结果：主题 22 个 token 全部通过，焦点样式通过，浏览器 6 页 × 浅色/深色
**critical 0 / serious 0 / moderate 0**（仅剩上述 `lang` 框架限制）。

## 7. 补充实验（中断/未知消费子局）

`ExperimentService.supplement_candidates()` 只把四类子局列为候选：

| 子局状态 | 是否补跑 | 原因 |
|---|---|---|
| `INTERRUPTED` | 是 | 进程中断，没有终局判定 |
| `PROVIDER_ERROR` | 是 | 基础设施失败，不是策略结果 |
| `cost_unknown=true` | 是 | 消费未知，需要独立账本重测 |
| 未执行（`pending`） | 是 | 计划内但没跑 |
| `SUCCEEDED` / 机制失败 / 预算截尾 / 取消 | **否** | 都是有意义的结果，补跑会污染分母 |

`create_supplement()` 会：

- 新建**独立**实验（新 `experiment_id`、新 `run_id`），原实验 manifest、账本与 run 记录一律不动；
- 写入 `supplement_of` / `supplement_reason`，指纹因此不同；
- 只跑候选条件（`only_conditions`），并重新走预检（预算与版本检查）；
- 幂等键 = `supplement:<源实验>:<指纹前 12 位>`，重复调用返回同一补充实验。

报告与汇总都会显示"补充实验：来源 `<id>`"，并声明"原始实验的记录与账本未被修改"。

## 8. 指标命名空间

V12 只**新增**命名空间，不覆盖 V10 任何指标：

| 命名空间 | 内容 | 谁定义 | 是否参与 V10 均值 |
|---|---|---|---|
| `v10`（如 `map22.v10.route_recall`） | V10 冻结指标 | `v10/metrics/schema.py` + 各图 `METRIC_SPECS` | 是 |
| `v12.projection`（如 `v12.projection.route_recall`） | V12 研究投影 | `lab/metrics_v12.py` | **否** |

### `v12.projection.route_recall`（DCR-V12-02）

**为什么需要**：V10 版只读 `key ∈ {bearing, path_state}`，而 MAP-22 的公开规则只要求
`{key, value}` 任意键值对。真实模型因此写出 `{"key": "path_to_here", "value": "..."}`
——语义正确、指标读不到，`route_recall` 恒为 `NOT_APPLICABLE`。

**定义**：与 V10 同义（写入的方位序列与真实走过的方位序列逐位匹配比例，分母为真实
move 数），但**键名宽容**：

- 接受 `bearing` / `path_state`；
- 也接受键名含 `bearing` / `path` / `route` / `visited` / `trail` / `路线` 等提示的条目；
- 值里按出现顺序解析方位（支持 `->`、逗号、空格分隔，以及 `n/e/s/w` 与中文方位）；
- 多条候选时取"匹配位数最多"的那条，避免被最后一条无关记忆压低。

**不做**：不读 `judge_state`、不读隐藏路线、不修改 V10 指标或账本。

导出时 `metrics.csv` 用 `namespace` 列区分（`v10` / `v12.projection`），下游可以只取其一。

## 9. 可复算性

- `summary.json` 的有效分母可从 `exports/runs.csv` 独立重算（`scripts/verify_v12.py` 的
  `export_recompute` 检查项即此）；
- `metrics.csv` 行数 = 所有子局 `result.metrics` 条目总数；
- `paired_comparison.csv` 每行都带 `left_run_id` / `right_run_id` / `verdict` / `reasons`；
- 报告里每个数字都能追到 `runs/web/<run_id>/result.json`。
