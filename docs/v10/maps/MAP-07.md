# MAP-07｜深海站 · 阀门方向（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-19`
- `rule_hash`：`24d56da77943032b5319a65bbce6ebb3ee7b3a3d4dc5e342a59363ab044959fd`
- `metric_hash`：`8982a694c8d5546ea26b39c727faa18d0a495d26148d3e318b4d8d88710b7957`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：面板只公开因果不公开开向、拧错进水 +1、水位预测进入成败；fixed_clockwise 2/4（固定脚本假设被证伪）、never_open/late_open 0/4

- 主指标：`map07.v10.mission_success`
  - `map07.v10.mission_success`：阀已开且截止时水位 ≤ 安全线（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. turn_valve(clockwise|counter)：转对方向开阀（此后每 tick 排水），转错方向会把阀再拧紧一档（进水速率 +1）并耗 1 tick。
2. inspect(control_panel) 耗 1 tick，公开阀门方向与进水/排水的因果，但不告诉你当前开向。
3. read_gauge 耗 1 tick，返回精确水位。
4. 进水从 tick 3 起按 inflow_schedule 上升；水位超过 8 即 FLOODED。
5. tick 10 结算：阀已开且水位 ≤ 8 即成功。

### Observation 公开字段

`current_level`、`deadline_tick`、`goal`、`inflow_schedule`、`inflow_tightened`、`level_reading`、`panel_read`、`safe_level`、`tick`、`valve_state`、`wrong_direction_turns`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`deadline_tick`、`directions`、`inflow_schedule`、`initial_level`、`label`、`safe_level`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`label`、`open_direction`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target_id,tool} |
| `read_gauge` | {tool} |
| `turn_valve` | {choice,tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `70203ee4ae75ae61` |
| 1 | `62165e42219a6d2a` |
| 2 | `fa616c50c399f58d` |
| 3 | `479b881cf3d8af68` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map07.v10.mission_success` | primary | higher | 阀已开且截止时水位 ≤ 安全线 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map07.v10.final_level` | secondary | lower | 截止时的水位 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | level | (0.0, 40.0) |
| `map07.v10.wrong_direction_turns` | guardrail | lower | 转错方向的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |
| `map07.v10.time_margin` | secondary | higher | 开阀后剩余 tick（截止 − 开阀 tick） | 开过阀的局（1） | 从未开阀 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (-20.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `fixed_clockwise` | 2/4 | 0.5 |
| `late_open` | 0/4 | 0.0 |
| `never_open` | 0/4 | 0.0 |
| `turn_both` | 2/4 | 0.5 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DRAINED_IN_TIME`、`FLOODED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-07-S0-interface` | DRAINED_IN_TIME（success） | 4 | 1 | 0.001992 | 是 |
| 1 | `V10-MAP-07-S1-interface` | FLOODED（failure） | 4 | 0 | 0.001969 | 是 |
| 2 | `V10-MAP-07-S2-interface` | FLOODED（failure） | 2 | 0 | 0.00094 | 是 |

- 有效局成功：1/3
- 结算成本合计 CNY 0.00490100（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 5：面板只公开因果不公开开向、拧错进水 +1、水位预测进入成败；fixed_clockwise 2/4（固定脚本假设被证伪）、never_open/late_open 0/4
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-19.md`
- `runs/v10/baselines/MAP-07.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

