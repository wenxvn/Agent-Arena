# MAP-05｜灯塔 · 三束信号（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-27`
- `rule_hash`：`d13fecd05beb7444abbaeea92036b0122d6cd017609b9a7aab08ed97425a9a4f`
- `metric_hash`：`f39f6db1c49ce558d4dfe5ebf74b4dc75fa5561ef05a4568643851f635933e43`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9b：4 实例各自可行；Oracle 4/4、启发式 4/4、四消融 0/4；阶段 5b 的 3 局 MiMo 非法动作 0

- 主指标：`map05.v10.mission_success`
  - `map05.v10.mission_success`：三束信号都在各自窗口内发出（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. C 是唯一能切换供电的节点；供电一次只能指向 R/B/W 中的**一个**塔，切换必须在 C 进行。
2. 每个塔必须先在塔内完成两步校准（calibrate_align → calibrate_phase_lock）才能发信号；未校准发信号会被拒。
3. 发信号（send_signal）在该动作结算后的 tick 判定是否落在窗口内；窗口结束后仍未发出的塔立即判负。
4. 三塔由 C 经 C_R/C_B/C_W 到达，**各通道耗时不同且随实例变化**，可用一次移动观察 tick 增量。
5. 三个窗口的起止 tick 在 Observation 的 windows 中公开；C 的 schedule_chart 可查看排程（inspect(schedule_chart)）。

### Observation 公开字段

`calibration`、`goal`、`location`、`power_target`、`schedule_chart_inspected`、`tick`、`transmitted`、`visible_edges`、`windows`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`edge_cost`、`label`、`windows`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`reference_completion_tick`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target_id,tool} |
| `interact` | {operation,target_id,tool} |
| `move` | {edge_id,tool} |
| `switch_power` | {station,tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `5ac16ccffad4dc80` |
| 1 | `505eb6dbd48251be` |
| 2 | `9486e390137eda2e` |
| 3 | `d33879867180b045` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map05.v10.mission_success` | primary | higher | 三束信号都在各自窗口内发出 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；窗口错过 → VALID 0 | ratio | (0.0, 1.0) |
| `map05.v10.window_slack_ticks` | secondary | higher | min(窗口结束 tick − 该塔实际发送 tick) | 已发送信号的塔（1–3） | 未发出任何信号 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (-40.0, 40.0) |
| `map05.v10.effective_signals` | secondary | higher | 窗口内发出的信号数 / 3 | 3 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map05.v10.power_switches` | diagnostic | none | switch_power 次数（共享供电的调度成本） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map05.v10.missed_windows` | guardrail | lower | 窗口结束仍未发出的塔数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 3.0) |
| `map05.v10.idle_ticks` | diagnostic | lower | 已校准但仍等待窗口的 tick 数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `late_send` | 0/4 | 0.0 |
| `no_calibration` | 0/4 | 0.0 |
| `no_power_switch` | 0/4 | 0.0 |
| `wrong_order` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`SIGNAL_WINDOW_MISSED`、`THREE_SIGNALS_SENT`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-05-S0-k2` | SIGNAL_WINDOW_MISSED（failure） | 12 | 0 | 0.00606956 | 是 |
| 0 | `V10-MAP-05-S0-k2b` | SIGNAL_WINDOW_MISSED（failure） | 12 | 0 | 0.006196 | 是 |
| 0 | `V10-MAP-05-S0-m2` | SIGNAL_WINDOW_MISSED（failure） | 25 | 0 | 0.01723336 | 是 |
| 1 | `V10-MAP-05-S1-k2` | SIGNAL_WINDOW_MISSED（failure） | 6 | 0 | 0.002833 | 是 |
| 1 | `V10-MAP-05-S1-k2b` | SIGNAL_WINDOW_MISSED（failure） | 6 | 0 | 0.00273556 | 是 |
| 1 | `V10-MAP-05-S1-m2` | SIGNAL_WINDOW_MISSED（failure） | 20 | 0 | 0.01351336 | 是 |
| 2 | `V10-MAP-05-S2-k2` | SIGNAL_WINDOW_MISSED（failure） | 13 | 0 | 0.00653268 | 是 |
| 2 | `V10-MAP-05-S2-k2b` | SIGNAL_WINDOW_MISSED（failure） | 7 | 0 | 0.003464 | 是 |
| 2 | `V10-MAP-05-S2-m2` | SIGNAL_WINDOW_MISSED（failure） | 19 | 0 | 0.01241604 | 是 |

- 有效局成功：0/9
- 结算成本合计 CNY 0.07099356（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：窗口时刻与通道耗时随 seed 变化；规则/契约/成功条件不变
- 当前裁定：Batch 9b：4 实例各自可行；Oracle 4/4、启发式 4/4、四消融 0/4；阶段 5b 的 3 局 MiMo 非法动作 0
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-27.md`
- `runs/v10/baselines/MAP-05.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

