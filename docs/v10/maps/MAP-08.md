# MAP-08｜深海站 · 漏点诊断（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-16`
- `rule_hash`：`be5b46c9292ac158e51aa66f9671b8c07e31b117360a7c9e4cbccaaa14e33aef`
- `metric_hash`：`20ce8f126ef41a90af89d632d3e0510540874df9851a9ba282c610729f858bd1`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：封存诊断成为修复前提、测试必须缩小假设集；no_hypothesis 0/4（V9 旁路）、blind_repairs 0/4、single_test 1/4；over_testing 4/4 但 tests_used 3（合法但更慢）

- 主指标：`map08.v10.mission_success`
  - `map08.v10.mission_success`：在截止前修好真实漏点（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 候选站点 S1, S2, S3, S4, S5；其中恰有一处是真实漏点。
2. run_test(test_id) 耗 1 tick，按**公开分区**返回读数；每个测试只能读一次。
3. candidate_sites 是全部读数与初始候选的交集，随测试实时更新。
4. seal_diagnosis(diagnosis_code)：只有候选集**缩成唯一站点**时才成立；封存后不可更改。
5. repair(target_id) 耗 2 tick，只有与封存诊断一致时才执行；修错会浪费一个备件，两次错修即失败。
6. 截止 tick 14。

### Observation 公开字段

`available_tests`、`candidate_sites`、`deadline_tick`、`goal`、`sealed_diagnosis`、`sites`、`spares_remaining`、`test_partitions`、`test_results`、`tick`、`wrong_repairs`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`deadline_tick`、`label`、`max_wrong_repairs`、`sites`、`tests`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`label`、`leak`、`minimum_tests`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `repair` | {target_id,tool} |
| `run_test` | {test_id,tool} |
| `seal_diagnosis` | {diagnosis_code,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `baca19fe7381ec97` |
| 1 | `0345ce9d5a7ef28e` |
| 2 | `a265f0795fe95648` |
| 3 | `8c5131f4abd3e68b` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map08.v10.mission_success` | primary | higher | 在截止前修好真实漏点 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map08.v10.hypothesis_reduction` | secondary | higher | （初始候选 − 封存时候选）/（初始 − 1） | 封存过诊断的局（1） | 未封存 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map08.v10.tests_used` | diagnostic | lower | 执行的测试数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |
| `map08.v10.wrong_repairs` | guardrail | lower | 修错站点的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 5.0) |
| `map08.v10.unjustified_repairs` | guardrail | lower | 缺少封存诊断或与封存不一致的修复尝试 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_repairs` | 0/4 | 0.0 |
| `no_hypothesis` | 0/4 | 0.0 |
| `over_testing` | 4/4 | 1.0 |
| `single_test` | 1/4 | 0.25 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DEADLINE_EXCEEDED`、`LEAK_REPAIRED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-08-S0-interface` | LEAK_REPAIRED（success） | 3 | 1 | 0.001747 | 是 |
| 1 | `V10-MAP-08-S1-interface` | LEAK_REPAIRED（success） | 3 | 1 | 0.001745 | 是 |
| 2 | `V10-MAP-08-S2-interface` | LEAK_REPAIRED（success） | 4 | 1 | 0.002392 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.00588400（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 个分区实例
- 当前裁定：Batch 5：封存诊断成为修复前提、测试必须缩小假设集；no_hypothesis 0/4（V9 旁路）、blind_repairs 0/4、single_test 1/4；over_testing 4/4 但 tests_used 3（合法但更慢）
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-16.md`
- `runs/v10/baselines/MAP-08.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

