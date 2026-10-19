# MAP-19｜火山 · 温度临界点（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-10`
- `rule_hash`：`a32b8f9651ae8fd9bb79b2a74cfa00f1a1ce988e0646be03ca01db5ff3ba580b`
- `metric_hash`：`4f3e6c6bf174de835c70259e8c385ca7e30f06c3bc03c1fb2a98b2772b32a0fe`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：预测成为产能的必要条件；精确温度与误差反馈公开；no_forecast 0/4、fixed_vector_no_lag 0/4、naive_forecast 1/4（容差 2 对照实例）

- 主指标：`map19.v10.production_credit`
  - `map19.v10.production_credit`：实得产能 / 目标（只计申报准确 tick 的负荷）（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 三区 A/B/C；每 tick 结算一次温度：T_next = max(0, T + 负荷 − 已生效冷却)。
2. 负荷每区 0–2；冷却向量每区 0–2 且总和不超过 4；同一生效 tick 上最后一条入队向量生效。
3. set_cooling 在提交后 tick+2 才生效。
4. **forecast_next 是申报**：必须提交下一 tick 的三区温度预测；预测最大误差 ≤ 1 时该 tick 的负荷才计入产能，否则该 tick 产能记 0。
5. 在 12 tick 内累计 49 点产能且温度不超 10 即成功。

### Observation 公开字段

`accepted_ticks`、`active_cooling`、`cooling_budget`、`current_load_levels`、`current_temperatures`、`forecast_tolerance`、`goal`、`last_forecast_error`、`last_temperature_reading`、`pending_cooling_commands`、`production_points`、`production_target`、`rejected_ticks`、`temperature_bands`、`tick`、`ticks_remaining`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`cooling_budget`、`forecast_tolerance`、`horizon`、`initial_temperatures`、`label`、`production_target`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`horizon`、`initial_loads`、`label`、`target`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `adjust_loads` | {adjust_loads,tool} |
| `forecast_next` | {forecast_next,tool} |
| `read_temperature` | {station,tool} |
| `set_cooling` | {set_cooling,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `28a955e260815cb1` |
| 1 | `caf8bbe6e04e7827` |
| 2 | `02fa06cb42a3fd8c` |
| 3 | `467575e681bbac31` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map19.v10.production_credit` | primary | higher | 实得产能 / 目标（只计申报准确 tick 的负荷） | 目标产能 | NOT_APPLICABLE | 截尾 → CENSORED；热失控 → VALID 0 | ratio | (0.0, 1.0) |
| `map19.v10.mean_forecast_error` | secondary | lower | 已结算 tick 的预测最大误差均值 | 提交过预测的 tick | 从未提交预测 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | temperature | (0.0, 20.0) |
| `map19.v10.rejected_ticks` | guardrail | lower | 预测误差超容差或未申报的 tick 数 | 已结算 tick | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map19.v10.temperature_exceedance_area` | guardrail | lower | Σ max(0, T − 8) / 已结算区·tick 数 | 已结算区·tick 数 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | temperature | (0.0, 12.0) |
| `map19.v10.critical_overheat_ticks` | guardrail | lower | T > 10 的区·tick 数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 36.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `fixed_vector_no_lag` | 0/4 | 0.3394 |
| `max_loads_no_cooling` | 0/4 | 0.3394 |
| `naive_forecast` | 1/4 | 0.9845 |
| `no_forecast` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`PRODUCTION_BELOW_TARGET`、`PRODUCTION_TARGET_MET`、`THERMAL_RUNAWAY`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-19-S0-ext` | decision_budget_exhausted（decision_budget_exhausted） | 60 | None | 0.0451994 | 是 |
| 0 | `V10-MAP-19-S0-i2` | decision_budget_exhausted（decision_budget_exhausted） | 60 | None | 0.0131528 | 是 |
| 1 | `V10-MAP-19-S1-ext` | decision_budget_exhausted（decision_budget_exhausted） | 60 | None | 0.0461032 | 是 |
| 1 | `V10-MAP-19-S1-i2` | decision_budget_exhausted（decision_budget_exhausted） | 60 | None | 0.0143592 | 是 |
| 2 | `V10-MAP-19-S2-ext` | unknown_provider_spend（unknown_provider_spend） | 2 | None | 0.00123 | 否（中断保留） |
| 2 | `V10-MAP-19-S2-ext-r2` | decision_budget_exhausted（decision_budget_exhausted） | 60 | None | 0.0073822 | 是 |
| 2 | `V10-MAP-19-S2-i2` | unknown_provider_spend（unknown_provider_spend） | 43 | None | 0.00956996 | 否（中断保留） |

- 有效局成功：0/5；另有 2 局 provider/账本中断（保留但不计入）
- 结算成本合计 CNY 0.13699676（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 4：预测成为产能的必要条件；精确温度与误差反馈公开；no_forecast 0/4、fixed_vector_no_lag 0/4、naive_forecast 1/4（容差 2 对照实例）
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-10.md`
- `runs/v10/baselines/MAP-19.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

