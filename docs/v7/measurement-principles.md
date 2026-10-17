# V7 测量原则与事件契约

## 1. 四类指标不可互相替代

| 类别 | 回答的问题 | 典型量 | 禁止 |
|---|---|---|---|
| 结果 outcome | 这局在规则上发生了什么 | success / failure / partial / censored / invalid | 不把截尾一律算失败 |
| 能力 primary | 该图声称测的构念表现如何 | 每图 1–2 条连续量 | 不因结果显著而事后换主指标 |
| 安全/约束 guardrail | 是否越过硬边界 | 碰撞、超压、失温、误指控 | 不能用效率收益抵消重大违例 |
| 过程/成本 diagnostic | 付出多少、卡在哪 | 合法动作率、重复动作、token、费用、墙钟 | 过程量不自动等于能力 |

主指标必须来自真实状态转移和 trace，不能由 LLM 主观打分。每图必须至少有：一个核心连续指标、一个安全/约束指标、一个失败归因指标、一个成本指标。

## 2. MetricSpec 契约

每条指标在 `src/agent_arena/v7/metrics/` 中以 `MetricSpec` 注册，字段含义：

| 字段 | 要求 |
|---|---|
| `metric_id` | `mapNN.<snake_case>`，全仓库唯一 |
| `map_id` | 与地图一致 |
| `kind` | outcome / primary / guardrail / diagnostic |
| `construct_name` | 一句“它测什么”，不得只写“表现” |
| `unit` | tick / 比例 / 人·tick / bit / 次 / 0-1 … |
| `direction` | higher / lower / descriptive |
| `formula` | 可直接实现的表达式 |
| `denominator` | 明确分母与 0 分母规则 |
| `window` | 计算窗口（整局/阶段/事件后） |
| `applicability` | 哪些实例/条件适用 |
| `missing_rule` | 缺字段时的 N/A 或 UNAVAILABLE |
| `censor_rule` | 预算/provider 截尾时的处理 |
| `source_events` | 逐字段来源（trace / judge 仅离线） |
| `adversarial_note` | 什么反例会误导该指标 |
| `implemented` | 是否真有可执行 extractor |
| `doc_ref` | 对应设计卡 |

### 2.1 五种状态

- `valid`：值可解释。
- `not_applicable`：构念在该局不成立（如无故障实例的恢复延迟）。
- `censored`：episode 被预算/provider 终止，未观察到可判定结果；若已有部分值，值可以非空，但状态仍是 `censored`。
- `unavailable`：trace/裁判数据缺字段，无法计算。
- `invalid_trace`：trace 结构不合法或 map_id 不匹配。

**未观察到的值不得默认为 0。** `0` 只用于“确实观察到了 0 次/0 比例”。

### 2.2 截尾

- `ACTION_LIMIT_REACHED`、`STEP_LIMIT_REACHED`、provider 错误、输入预算超限、决策上限：结果与终局型指标标 `censored`。
- 地图设计内的 deadline（如 MAP-30 的 40 tick）是**规则失败**，不是截尾；但要在 note 中保留“deadline”原因。
- 部分值仍报告（例如已交付乘客数），避免用截尾吞掉已有信息；但不得把部分值当成完整局参与最优差。

## 3. 归一化事件契约

V7 不重写 V6 trace。`schema.parse_trace_rows` 把现有 `agent_trace.jsonl` 归一化为：

| 字段 | 来源 |
|---|---|
| `run_id / episode_id` | `trace_header.episode_id` |
| `map_id / instance_id / seed` | `trace_header` |
| `scenario_hash / rules_version` | `trace_header.scenario_hash`；规则版本由 V4 spec 提供 |
| `agent_condition` | `trace_header.condition_id` |
| `tick_before / tick_after` | `observation_before/after` 的 `tick` / `current_tick` / `movement_steps` |
| `action / action_valid` | `action`；`result` 是否属于明确拒绝 |
| `public_observation_hash` | 可选：对公开 Observation 做 canonical SHA-256 |
| `private_state_hash_for_offline_only` | 可选：`state_hash_after`，只允许离线裁判使用 |
| `event_type` | `decision` / `prefix_action` |
| `resource_deltas` | 由 observation 前后差值派生 |
| `constraint_violations` | 由 `result` 原因码映射 |
| `milestone_events` | 由 observation 字段变化派生 |
| `terminal_status / stop_reason` | 最后一个 observation + judge `status` |
| `usage` | `judge_metrics.usage`（token/费用/墙钟） |

公开日志、prompt、工具响应、报告表格**不得**包含 `private_state_hash_for_offline_only`、`true_leak`、`fault_part`、案情真凶、未解锁证据或 Oracle 路径。

## 4. 通用派生量

- 合法动作率 = 被规则接受的决策数 / 已提交决策数；分母 0 → N/A。prefix action 不计入模型决策。
- 资源消耗 = 初值 − 终值 + 补给量，按事件账本；不能用动作次数估算。
- 最优差 = 实际可比成本 − 同一实例同约束的求解器基准；基准不可用 → N/A；失败局不计算最优差。
- 恢复延迟 = 故障首次公开可观察时刻 → 首次有效响应时刻；没有响应且截尾 → CENSORED。
- 信息增益 = `H(prior) − H(posterior)`，单位 bit（或 nats，必须注明）；重复观测的信息增益必须为 0。
- 风险暴露积分 = `Σ risk_t × exposure_t`；必须声明风险刻度与 tick 单位。

## 5. 三种比较层级

1. **同实例同难度同预算配对**：唯一支持因果对照的层级。固定场景多 seed 只是模型采样重复，不是独立环境实例。
2. **同能力跨场景**：只比较预登记的标准化相对改善或方向一致性；不得把水位与列车延误原值相加。
3. **跨 30 图画像**：按世界/能力/难度展示分项矩阵与分布；**默认不发布单一总分**。若未来必须总分，先冻结标准化、权重、缺失值与安全惩罚，并报告敏感性分析和分项。

## 6. 难度是六维设计向量，不是步数

每图记录 `D=(可见性, 依赖深度, 事件动态性, 资源耦合, 记忆跨度, 分支复杂度)`，每维 0–3。详见 `difficulty-rubric.md`。

难度标签是产品结构，不是已被统计验证的同尺度量表。简单/中等/困难必须说明“增加了哪一维”，不能只延长倒计时或增加空走步数。

## 7. 失败归因

统一原因码（可与地图专属码并存）：

`environment_unsolvable / model_strategy / invalid_action / unsafe_action / resource_exhausted / censored_step / censored_time / provider_error / unknown_spend / metric_unavailable`

一局可有多个原因，保留事件序列，不强制唯一原因。地图专属终止码（如 `NODE_CAPACITY_CONFLICT`、`SPARES_EXHAUSTED`）作为子原因保留。

## 8. 反作弊与无泄漏

- 不把隐藏真值、未来事件、最优路径、未解锁证据写入 Observation/prompt/工具响应。
- 不针对已知模型错误修改胜负条件；只允许澄清公开接口（DCR 记录）。
- 提示词只说明动作契约与公开规则，不暗示答案或推荐策略。
- 对照条件除预登记处理外必须一致：同初态、同公开信息、同预算、同 Action contract。
- 信息量不同的条件标为“信息可用性实验”，不能称“纯能力提升”。

## 9. 报告纪律

- 逐图逐实例报告原始单位、有效分母、N/A 与截尾、paired difference、失败原因。
- 不把不同地图的原始成本相加；不把通关率当唯一总结。
- 单次运行只作描述性结果，不做显著性/排名断言。
- 设计态与实测结果分区展示；`design_complete` 不等于 `runtime_validated`。
