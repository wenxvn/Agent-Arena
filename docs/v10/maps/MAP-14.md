# MAP-14｜金字塔 · 说谎的祭司（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-09`
- `rule_hash`：`03d82794ea57ca0509315a542683816fdf6772dbc649d433284d0983697d1b83`
- `metric_hash`：`704e054d121a72a375bde7bad5c999597625839884bf9c98090301acea6897b2`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：公开推理规则；开门需要相容封存假设；6 实例；blind_two_submissions 0/6（V9 为 2/3 开门）、no_seal 0/6、one_question 2/6

- 主指标：`map14.v10.deduction_success`
  - `map14.v10.deduction_success`：门开 且 封存假设一致 且 问数 ≤ 最少问数（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 6/6。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. P—A—O—J 三点链条：P 是证词厅、A 是档案室、O 是比对台、J 是审判门。
2. 锁型候选只有 3 种（见 configurations）。
3. **推理规则**：三名祭司中恰有一人对每一条命题都如实作答，另外两人对每一条命题都反报（说反话）。谁诚实未知。
4. 整局最多问 4 条命题（在 P），最多错交 1 次。
5. read_archive 在 A 读取一条排除性档案（有且只有一条）。
6. compare_evidence 在 O 封存一个（锁型, 诚实者）假设，只记录、不判对错。
7. submit_configuration 在 J：只有当**最近一次封存的假设与提交锁型一致、且该假设与全部已观察答复/档案相容**时门才打开；否则记一次错交。

### Observation 公开字段

`archive_record_if_read`、`comparison_record`、`configurations`、`gate_open`、`goal`、`location`、`public_statement_cards`、`question_answers`、`questions_remaining`、`questions_used`、`tick`、`truth_rule`、`visible_edges`、`wrong_submissions`、`wrong_submissions_remaining`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`claim_ids`、`configurations`、`question_budget`、`wrong_submission_limit`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`claims`、`configuration`、`excluded_configuration`、`truthful_priest`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `ask` | {claim_id,tool} |
| `compare_evidence` | {choice,person_id,support_evidence_ids,tool} |
| `move` | {edge_id,tool} |
| `read_archive` | {tool} |
| `submit_configuration` | {choice,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5`（6 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`6`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `806c816d8527965e` |
| 1 | `6eeaae1ed09069df` |
| 2 | `45c7eed6864a5f72` |
| 3 | `6c717e1e70c961ed` |
| 4 | `89743875d0bb36d0` |
| 5 | `4e4ea0b22bbbd2b1` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map14.v10.deduction_success` | primary | higher | 门开 且 封存假设一致 且 问数 ≤ 最少问数 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map14.v10.consistent_hypothesis_rate` | secondary | higher | 封存的假设中与全部已观察答复/档案相容的比例 | 封存过的局（≥1） | 从未封存 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map14.v10.blind_submit_attempts` | guardrail | lower | 没有相容封存假设的提交次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |
| `map14.v10.queries_used` | diagnostic | lower | 已消耗的提问数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 8.0) |
| `map14.v10.query_budget_overruns` | guardrail | lower | 超出预算被拒的提问次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_two_submissions` | 0/6 | 0.0 |
| `no_seal` | 0/6 | 0.0 |
| `one_question` | 2/6 | 0.3333 |
| `waste_questions` | 6/6 | 0.3333 |

- Oracle：6/6（机制触发 6/6）
- 公开启发式：6/6（主指标均值 0.6667）
- legal_random：0/120（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`GATE_OPENED_WITH_CONSISTENT_HYPOTHESIS`、`WRONG_SUBMISSION_LIMIT`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-14-S0-ext` | WRONG_SUBMISSION_LIMIT（failure） | 35 | 0 | 0.02588176 | 是 |
| 1 | `V10-MAP-14-S1-ext` | WRONG_SUBMISSION_LIMIT（failure） | 35 | 0 | 0.02650352 | 是 |
| 2 | `V10-MAP-14-S2-ext` | WRONG_SUBMISSION_LIMIT（failure） | 24 | 0 | 0.01961204 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.07199732（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；6 实例
- 当前裁定：Batch 4：公开推理规则；开门需要相容封存假设；6 实例；blind_two_submissions 0/6（V9 为 2/3 开门）、no_seal 0/6、one_question 2/6
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-09.md`
- `runs/v10/baselines/MAP-14.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

