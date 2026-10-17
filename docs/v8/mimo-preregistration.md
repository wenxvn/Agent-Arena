# V8 MiMo 90 局预登记

本文件在正式调用前写定。任何后续变更都必须重新冻结并作为新版本运行，不得静默覆盖。

## 1. 实验身份

- 阶段：V8 三十图定稿与三重复验收。
- 模型：`mimo-v2.6-flash`，provider `openai`，Xiaomi MiMo Responses API（`https://api.xiaomimimo.com/v1`）。
- 温度：0；reasoning：`none`；输出：`json_object`；`retry_count=0`。
- 正式样本：30 图 × 3 次重复 = 90 局。`seed=0` 固定，`replicate_id=0/1/2`。
  - 这是**重复运行**，不是三个独立环境 seed。环境 seed 固定为 0，地图核心规则不随重复变化。
- 每图一个能力承载条件（不混入 V5–V7 消融）：
  `MAP-08 hypothesis_table`、`MAP-16 constraint_table`、`MAP-18 alert_on`、
  `MAP-22 history5_graph_memory`、`MAP-26 free_diagnosis`、`MAP-30 history5_casebook`；
  其余 24 图 `default`。
- 决策预算：简单 30、中等 38、困难 46；环境 `step_limit=160`。
- 每图三次使用完全相同的系统 prompt、动作契约、预算与模型配置。
- 运行器另有 30 分钟 wall-clock 安全上限，只用于防止单局卡死；正式约束仍是决策预算与
  `step_limit`。任何因该上限结束的局记 `episode_timeout` 并如实报告，不作为成功。

## 2. 输入边界

- Agent 只接收 `V8Observation` 的公开字段白名单。
- prompt 只由地图公开元数据、`SHAPES` 动作契约、当前公开 Observation 与最近 5 条公开动作结果组成。
- 对需要 `target/choice` 字符串的地图，系统 prompt 附带**公开静态交互词表**；词表只列
  可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确，也不含隐藏真值。
- Oracle、`judge_state`、私有真值、指标 id 与求解器路径不得进入 prompt。
- 离线门禁会扫描 prompt 中的指标 id、`judge_state`、`oracle_trace` 等标记。

## 3. 费用与停机

- 独立账本：`runs/v8/ledger.jsonl`，append-only，不与 V5/V6/V7 混账。
- 币种 CNY，硬上限 **¥10**；每次请求前按 8192 输入 + 1024 输出预留最坏费用，结算后释放该笔预留。
- 预警：50% 与 80%，写入 `budget_warning` 事件但不中断。
- 立即封账停机：
  - `unknown_provider_spend`（传输未确认，可能已计费）；
  - 连续 3 次 provider 故障；
  - 实际结算超过登记 token 上限；
  - 全局请求数或账本局数达到登记上限。
- 不自动突破 ¥10；若封账或预算不足，如实报告已完成数与缺口。

## 4. 补跑规则

- 仅 `provider_error`（传输/供应商中断且确认未计费）允许补跑一次；新 run ID、新 episode 目录，原失败记录和费用保留。
- `unknown_provider_spend` 不得补跑，直接封账。
- 模型侧正常失败（`failure`、`decision_budget_reached`、`episode_timeout`、`schema_fault_limit`、`censored`）不补跑。
- 补跑名额最多 15 局；每个 `(map, replicate)` 最多 2 次尝试。
- 连续 3 个 episode 触发 `schema_fault_limit` 时停止当前批并审计。

## 5. 结果与统计口径

- 每局保存：trace、judge metrics、V8 metrics、usage、manifest、冻结 hash。
- 每图三次分别报告原始值、均值/范围、有效分母、截尾与失败归因。
- n=3，不做显著性检验，不把 Oracle 成功率当作 MiMo 能力。
- 主指标与护栏来自 V7 的 154 条 `MetricSpec`，V8 只做五态投影，不新增或改名。
- 成功是任务层结果；机制失败、无效动作、截尾都单独报告。

## 6. 预登记哈希

`runs/v8/freeze_manifest.json` 记录 30 图的
`scenario_hash / rule_hash / prompt_hash / metric_schema_hash / oracle_hash / commit`
以及 `runtime_tree_hash` 与 `freeze_hash`。正式运行前必须通过
`scripts/run_v8_90.py --dry-run` 的冻结校验。

## 7. 与历史实验的关系

- 只读 V2/V4/V5/V6/V7 的 trace、账本与注册；本阶段不修改、不重算、不合并。
- V7 Pilot-001/001R 的 12 局只作为先导证据，不计入 V8 正式 90 局。
- `runs/v8/` 为隔离目录；V8 结束前不向其他版本回填任何结果。
