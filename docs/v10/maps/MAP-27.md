# MAP-27｜月球 · 月球车（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-30`
- `rule_hash`：`c5be1675ac7efe06084ee5841d2a59812c55018b013a02cb75567c322ac9230b`
- `metric_hash`：`c54986093b229053a969fd697c3752a714fb0d0f22c9133fd6c1ac233f346e15`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9d：Oracle 4/4、启发式 4/4、跳过目标消融 0/4、overload 1/4；公开规则含电量/货舱/充电/中继/伤员判据

- 主指标：`map27.v10.mission_success`
  - `map27.v10.mission_success`：在 B 提交时样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. B 是基地（提单与样本容器）、S 是中继站补给点与唯一充电桩、R 是中继塔、P 是采样点、E 是伤员位置；每条通道的耗时 = 电量消耗 = 氧气消耗。
2. 月球车有电量上限、货舱上限与余氧上限（数值见 Observation 的 battery_capacity / cargo_capacity / oxygen）；电量不足以进入下一段会抛锚。
3. 装载会占货舱槽位；货舱满时装载或充电会被拒绝并记一次冲突。
4. 在 S 可消耗充电桩充一次电（增益见实例）；充电桩数量见 Observation。
5. 中继塔需要 relay_repair_kit 才能修复；伤员需要 medical_kit 现场稳定后，在**中继在线**时才能远程撤离；样本容器需带到 P 采样封存。
6. 回到 B 提交才算完成：样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0。

### Observation 公开字段

`battery`、`battery_capacity`、`cargo`、`cargo_capacity`、`charger_cells_remaining`、`crew_alive`、`goal`、`local_edges`、`location`、`objectives`、`oxygen`、`relay_state`、`sample_state`、`supplies_here`、`survivor_state`、`tick`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`battery_capacity`、`cargo_capacity`、`charge_gain`、`label`、`oxygen`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`reference_critical_path`、`vehicle`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `charge` | {tool} |
| `drive` | {to,tool} |
| `load` | {item_id,tool} |
| `repair_relay` | {tool} |
| `rescue` | {item_id,operation,tool} ｜ {operation,tool} |
| `sample` | {item_id,tool} |
| `submit` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `ff79c9b75678ae3e` |
| 1 | `55153d44c1ec34c8` |
| 2 | `3580230c74b78130` |
| 3 | `ef2d7e44fd29aed4` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map27.v10.mission_success` | primary | higher | 在 B 提交时样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；任一目标缺失 → VALID 0 | ratio | (0.0, 1.0) |
| `map27.v10.joint_task_completion_rate` | secondary | higher | （中继在线 + 伤员撤离 + 样本封存）/ 3 | 3 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map27.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map27.v10.resource_conflicts` | guardrail | lower | 电量/货舱冲突导致的拒绝次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map27.v10.cargo_errors` | guardrail | lower | 货舱容量不足导致的装载失败次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map27.v10.blackout_ticks` | diagnostic | lower | 中继离线期间的累计 tick | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map27.v10.charge_cells_used` | diagnostic | none | 使用的充电桩次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `overload` | 1/4 | 1.0 |
| `skip_relay` | 0/4 | 0.0 |
| `skip_rescue` | 0/4 | 0.0 |
| `skip_sample` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ALL_OBJECTIVES_COMPLETE`、`OBJECTIVES_INCOMPLETE_AT_BASE`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-27-S0-n2` | VEHICLE_STRANDED（failure） | 20 | 0 | 0.01471032 | 是 |
| 1 | `V10-MAP-27-S1-n2` | VEHICLE_STRANDED（failure） | 27 | 0 | 0.01751156 | 是 |
| 2 | `V10-MAP-27-S2-n2` | unknown_provider_spend（unknown_provider_spend） | 21 | None | 0.01072384 | 否（中断保留） |
| 2 | `V10-MAP-27-S2-n2-r2` | decision_budget_exhausted（decision_budget_exhausted） | 46 | None | 0.018541 | 是 |

- 有效局成功：0/3；另有 1 局 provider/账本中断（保留但不计入）
- 结算成本合计 CNY 0.06148672（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：电量/货舱/充电增益/余氧随 seed 变化；电量收紧的实例只允许 stabilize-first
- 当前裁定：Batch 9d：Oracle 4/4、启发式 4/4、跳过目标消融 0/4、overload 1/4；公开规则含电量/货舱/充电/中继/伤员判据
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-30.md`
- `runs/v10/baselines/MAP-27.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

