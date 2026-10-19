# MAP-06｜灯塔 · 暴风眼（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-03`
- `rule_hash`：`24656744745ac9d0c049f7de5082ba88d9ceb35907e5eef29b8258f3f4081710`
- `metric_hash`：`f7d42fcdf72905ac52e6501a4ab961a7bc29f471348421eb2013f244f4cb5bea`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略

- 主指标：`map06.v10.risk_time_utility`, `map06.v10.utility_regret`
  - `map06.v10.risk_time_utility`：success × (1 − 0.5·risk/(budget+1) − 0.5·finish_tick/deadline)（方向：higher）
  - `map06.v10.utility_regret`：该 seed 真值感知最优效用 − 实得效用（方向：lower）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 9/10。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 起点 Q（预报站）。边耗时：M_Q=1、Q_P=1、M_G=2、G_P=2；Q_P 与 G_P 是暴露区段。
2. inspect(target_id=forecast) 只能在 Q 使用，耗 2 tick，读数为 short 或 long；预报准确率 0.8，长风暴先验 0.5；重复读取返回同一读数并再耗 2 tick。
3. interact(G, harden) 在 G 耗 3 tick 装上护盾；interact(P, repair_lighthouse) 在 P 耗 2 tick，完成即成功。wait(ticks) 原地等待。被拒动作耗 1 tick。
4. 天气隐藏，三种之一：calm 无风险；short 暴露区段与无护盾维修各 +1/tick；long 暴露区段 +1/tick、无护盾维修 +3/tick、有护盾维修 0。
5. 累计风险超过 4 立即失败；tick 达到 deadline_tick 仍未修好即失败。
6. 评分：成功时 U = 1 − 0.5·风险/5 − 0.5·完成 tick/deadline；失败 U = 0。越早修好、风险越低越好。

### Observation 公开字段

`deadline_tick`、`edge_ticks`、`exposed_edges`、`forecast_accuracy`、`forecast_queries`、`forecast_reading`、`goal`、`lamp_restored`、`location`、`prior_long_storm`、`risk`、`risk_budget`、`storm_shield`、`tick`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`cohort_size`、`deadline_tick`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`cohort`、`forecast`、`weather`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target_id,tool} |
| `interact` | {operation,target_id,tool} |
| `move` | {edge_id,tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5, 6, 7, 8, 9`（10 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`10`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `bb6be32ba54e26e2` |
| 1 | `a386e90a5a8dd8d0` |
| 2 | `12c8686d3ea34ba1` |
| 3 | `e60c5453f69dcfd9` |
| 4 | `904b6e1be7710bf0` |
| 5 | `7bd43f4726167e19` |
| 6 | `089d4f5fef559738` |
| 7 | `90885cab777aaeb2` |
| 8 | `b4fba5a47128a11d` |
| 9 | `3ea496eadae46bde` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map06.v10.risk_time_utility` | primary | higher | success × (1 − 0.5·risk/(budget+1) − 0.5·finish_tick/deadline) | 1 | NOT_APPLICABLE | 运行中截尾 → CENSORED；失败 → VALID 0 | ratio | (0.0, 1.0) |
| `map06.v10.utility_regret` | primary | lower | 该 seed 真值感知最优效用 − 实得效用 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map06.v10.shield_matches_truth` | secondary | higher | hardened == (weather == long) | 终局局（1） | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map06.v10.forecast_followed` | diagnostic | none | 读过预报时：hardened == (reading == long) | 读过预报的终局局 | 未读预报 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map06.v10.observation_cost_ticks` | guardrail | lower | forecast_queries × 2 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map06.v10.danger_exposure_ticks` | guardrail | lower | count(风险增加的 tick) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map06.v10.final_risk` | guardrail | lower | 累计风险 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | risk | (0.0, 30.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `always_direct` | 5/10 | 0.3455 |
| `always_reinforce` | 9/10 | 0.3904 |
| `forecast_always` | 8/10 | 0.3884 |

- Oracle：10/10（机制触发 9/10）
- 公开启发式：9/10（主指标均值 0.4228）
- legal_random：0/200（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`LAMP_RESTORED`、`REPAIR_DEADLINE_MISSED`、`RESOURCE_EXHAUSTED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-06-S0-p0` | LAMP_RESTORED（decision_budget_exhausted） | 3 | 0.821429 | 0.21135656 | 是 |
| 1 | `V10-MAP-06-S1-p0` | LAMP_RESTORED（decision_budget_exhausted） | 3 | 0.521429 | 0.21265944 | 是 |
| 2 | `V10-MAP-06-S2-p0` | LAMP_RESTORED（decision_budget_exhausted） | 6 | 0.371429 | 0.21904564 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.64306164（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；10 seed cohort
- 当前裁定：Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-03.md`
- `runs/v10/baselines/MAP-06.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

