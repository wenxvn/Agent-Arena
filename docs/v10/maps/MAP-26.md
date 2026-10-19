# MAP-26｜月球 · 失败的维修计划（中等）

- 运行时：`v10 原生`
- 构念标签：`OPTIONAL`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-17`
- `rule_hash`：`56709d4b419a7f050828976a81b9a83cdd2a519b8c08b224f6646b2956bce6df`
- `metric_hash`：`fac29eb6414be5ff510ba5c40edfa02da22f5672a420595338ffc10247b72e6e`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：换错耗备件并 +1 磨损（达 2 即不可恢复）、rollback 不返还备件；no_diagnosis 3/4 但备件 2/2/1/2 且均有换错、test_but_ignore 0/4；启发式 4/4 且 spares 恒 1、precision 1

- 主指标：`map26.v10.mission_success`
  - `map26.v10.mission_success`：装上与真实故障匹配的备件并重启成功（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 三种故障 F1/F2/F3 分别需要备件 P1/P2/P3；当前只有一台机器要修。
2. run_test(test_id) 耗 1 tick，按公开分区返回读数并缩小 candidate_faults。
3. read_log(log_id) 耗 1 tick，日志会披露一条历史维修记录（不影响候选集）。
4. replace(part_id) 耗 2 tick：装上备件；若与真实故障匹配，restart 即可恢复。换错会消耗该备件、磨损 +1。
5. rollback 撤销最后一次更换，但**已消耗的备件不返还**。
6. 磨损达到 2 时机器不可恢复；截止 tick 16。
7. 诊断不是开门的必要步骤：盲换也是合法策略，但会更费备件、更容易磨损失败。

### Observation 公开字段

`available_tests`、`candidate_faults`、`deadline_tick`、`faults`、`goal`、`installed_part`、`last_replaced`、`max_wear`、`parts`、`rollbacks_used`、`spares`、`test_partitions`、`test_results`、`tick`、`wear`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`deadline_tick`、`faults`、`initial_spares`、`label`、`max_wear`、`parts`、`tests`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`fault`、`label`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `read_log` | {log_id,tool} |
| `replace` | {part_id,tool} |
| `restart` | {tool} |
| `rollback` | {tool} |
| `run_test` | {test_id,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `31fa5128245d8225` |
| 1 | `d6aab3f91da75759` |
| 2 | `bc861e5e7e0624c8` |
| 3 | `be004fe023edc596` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map26.v10.mission_success` | primary | higher | 装上与真实故障匹配的备件并重启成功 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map26.v10.spares_used` | secondary | lower | 消耗的备件数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 6.0) |
| `map26.v10.wrong_swaps` | guardrail | lower | 换错部件的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 6.0) |
| `map26.v10.rollbacks` | guardrail | lower | rollback 次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 6.0) |
| `map26.v10.diagnosis_precision` | secondary | higher | 第一次更换就正确的 0/1 | 更换过的局（1） | 从未更换 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `no_diagnosis` | 3/4 | 0.75 |
| `test_but_ignore` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：1/80（主指标均值 0.0125）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DEADLINE_EXCEEDED`、`UNIT_RESTORED`、`UNIT_UNRECOVERABLE`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-26-S0-interface` | UNIT_RESTORED（success） | 3 | 1 | 0.001836 | 是 |
| 1 | `V10-MAP-26-S1-interface` | UNIT_RESTORED（success） | 3 | 1 | 0.0012108 | 是 |
| 2 | `V10-MAP-26-S2-interface` | UNIT_RESTORED（success） | 3 | 1 | 0.0015204 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.00456720（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；诊断 OPTIONAL 但质量可区分
- 当前裁定：Batch 5：换错耗备件并 +1 磨损（达 2 即不可恢复）、rollback 不返还备件；no_diagnosis 3/4 但备件 2/2/1/2 且均有换错、test_but_ignore 0/4；启发式 4/4 且 spares 恒 1、precision 1
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-17.md`
- `runs/v10/baselines/MAP-26.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

