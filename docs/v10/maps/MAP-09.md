# MAP-09｜深海站 · 连锁故障（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-21`
- `rule_hash`：`10c59b4117cf0a939dd206498e90919de27bf8ecb1e5ea6af773d849f66dafff`
- `metric_hash`：`a29715738c16d05830523b6ba30960437a413e71e4b06a5a4fc16451e4a04295`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：修复需水位与供氧双门槛、三链同时结算、漏速递增；skip_pump 0/4（FLOODED）、skip_vent 1/4（LOST_POWER）、seal_only 0/4（LOST_OXYGEN）

- 主指标：`map09.v10.mission_success`
  - `map09.v10.mission_success`：在水位/电力/供氧都不归零的前提下完成修复（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 每个 tick：漏水使水位 + 当前漏速；基载使电力 -1、供氧 -1。
2. 漏速每 5 tick 上升 1（surge）。
3. pump：水位 -4、电力 -2；seal：本 tick 停止漏水、供氧 -2；vent：供氧 +3、水位 +1。
4. repair 要求 水位 ≤ 4 且 供氧 ≥ 4，否则分别返回 TOO_MUCH_WATER / OXYGEN_TOO_LOW。
5. 水位 > 8 即 FLOODED；电力或供氧归零即 LOST_POWER / LOST_OXYGEN。

### Observation 公开字段

`current_leak`、`goal`、`min_oxygen`、`min_power`、`oxygen`、`power`、`repair_oxygen_min`、`repair_water_limit`、`sealed_this_tick`、`tick`、`wasted_pumps`、`water`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`initial`、`label`、`leak`、`repair_oxygen_min`、`repair_water_limit`、`surge_every`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`label`、`leak`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `pump` | {tool} |
| `repair` | {tool} |
| `seal` | {tool} |
| `vent` | {tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `f96e0a4120114e62` |
| 1 | `f0eb9181f010a2d9` |
| 2 | `f2d554c983ca2ec2` |
| 3 | `00ffaaeeb1b6027e` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map09.v10.mission_success` | primary | higher | 在水位/电力/供氧都不归零的前提下完成修复 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map09.v10.final_water` | secondary | lower | 终局水位 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | level | (0.0, 20.0) |
| `map09.v10.min_oxygen` | guardrail | higher | 过程中最低供氧 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | level | (0.0, 10.0) |
| `map09.v10.min_power` | guardrail | higher | 过程中最低电力 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | level | (0.0, 10.0) |
| `map09.v10.wasted_pumps` | diagnostic | lower | 水位已经很低时仍开泵的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `seal_only` | 0/4 | 0.0 |
| `skip_pump` | 0/4 | 0.0 |
| `skip_vent` | 1/4 | 0.25 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`FLOODED`、`HULL_SEALED`、`LOST_OXYGEN`、`LOST_POWER`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-09-S0-interface` | HULL_SEALED（success） | 4 | 1 | 0.00185 | 是 |
| 1 | `V10-MAP-09-S1-interface` | HULL_SEALED（success） | 2 | 1 | 0.000889 | 是 |
| 2 | `V10-MAP-09-S2-interface` | HULL_SEALED（success） | 5 | 1 | 0.00210512 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.00484412（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 5：修复需水位与供氧双门槛、三链同时结算、漏速递增；skip_pump 0/4（FLOODED）、skip_vent 1/4（LOST_POWER）、seal_only 0/4（LOST_OXYGEN）
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-21.md`
- `runs/v10/baselines/MAP-09.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

