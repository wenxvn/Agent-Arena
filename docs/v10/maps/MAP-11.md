# MAP-11｜极地 · 极地搜救（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-18`
- `rule_hash`：`8b98559be856d31daf2c7cff3b91291c5081b2b3c4e89745c209d3513bdaa2d1`
- `metric_hash`：`1986fed7b041f4b59d4d9b6e421f04201b2c1a7499410c48fba133f7a09b05ed`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：救援需先有信号、风暴窗口公开且漏检 0.5–0.7、生命窗；blind_rescue 0/4（V9 旁路）、storm_search 有风暴搜索但合法、single_search_giveup/waste_window 2/4；启发式风暴搜索 0 次

- 主指标：`map11.v10.mission_success`
  - `map11.v10.mission_success`：在生命窗内救到生还者（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 3/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 三个搜索区 Z1, Z2, Z3；生还者恰在其中一处。
2. search(area) 耗 1 tick；若处于风暴窗口则耗 3 tick，且漏检率显著更高（面板公开 storm_miss_rate / calm_miss_rate）。
3. rescue(area) 耗 1 tick；对错误区域会惊动现场，扣 3 tick。
4. 生命窗结束（life_window_end）仍未救到即失败。
5. 漏检是概率性的：一次 NO_SIGNAL 不代表该区一定没有生还者。

### Observation 公开字段

`goal`、`in_storm`、`life_window_end`、`rescued`、`search_attempts`、`search_cost`、`search_miss_rate`、`signals`、`storm_windows`、`tick`、`zones`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`calm_miss_rate`、`label`、`life_window_end`、`storm_miss_rate`、`storm_windows`、`zones`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`label`、`survivor`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `rescue` | {area,tool} |
| `search` | {area,tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `7d006de0b71ed561` |
| 1 | `3c5199ee42237fbc` |
| 2 | `5d5cabdd5674bd3f` |
| 3 | `d1d2c73f35cb6973` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map11.v10.mission_success` | primary | higher | 在生命窗内救到生还者 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map11.v10.searches_used` | secondary | lower | 执行的搜索次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 30.0) |
| `map11.v10.storm_searches` | guardrail | lower | 在风暴窗口内进行的搜索次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map11.v10.wrong_rescues` | guardrail | lower | 对错误区域尝试营救的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |
| `map11.v10.time_margin` | secondary | higher | 生命窗 − 营救 tick | 成功局（1） | 未救到 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (-20.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_rescue` | 0/4 | 0.0 |
| `single_search_giveup` | 2/4 | 0.5 |
| `storm_search` | 4/4 | 1.0 |
| `waste_window` | 2/4 | 0.5 |

- Oracle：4/4（机制触发 3/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`SURVIVOR_LOST`、`SURVIVOR_RESCUED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-11-S0-interface` | SURVIVOR_RESCUED（success） | 3 | 1 | 0.00110912 | 是 |
| 1 | `V10-MAP-11-S1-interface` | SURVIVOR_RESCUED（success） | 2 | 1 | 0.000871 | 是 |
| 2 | `V10-MAP-11-S2-interface` | SURVIVOR_RESCUED（success） | 5 | 1 | 0.00198024 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.00396036（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例（含晴稳对照）
- 当前裁定：Batch 5：救援需先有信号、风暴窗口公开且漏检 0.5–0.7、生命窗；blind_rescue 0/4（V9 旁路）、storm_search 有风暴搜索但合法、single_search_giveup/waste_window 2/4；启发式风暴搜索 0 次
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-18.md`
- `runs/v10/baselines/MAP-11.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

