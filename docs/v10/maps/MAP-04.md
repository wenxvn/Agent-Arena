# MAP-04｜灯塔 · 潮汐密道（简单）

- 运行时：`v10 原生`
- 构念标签：`OPTIONAL`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-08`
- `rule_hash`：`6be9f74d050d20e48a7c907d7dd03b35226a84cac980bad171015b9c4f055958`
- `metric_hash`：`6a7b8a5f7c7c429581ab96596da0853e25cce171ac87568ecdc5a74bcb1c5a85`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：盲撞计 3 tick 代价；绕行保留但余量恒 ≤ Oracle；blind_retry 1/6（仅开局安全相位的对照实例），excess_wait/fixed_phase_script 0/6

- 主指标：`map04.v10.time_margin`
  - `map04.v10.time_margin`：成功时 deadline − 点亮 tick；失败 = 0（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 6/6。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 地形：T—S—G 与 T—B1—…—B4—D—G 两条路线；G 存放灯芯，T 有灯塔。
2. tide_phase 每 tick +1 并对 tide_period 取模；open_phases 是安全相位。
3. S_G 只能在安全相位通过；否则失败并耗 3 tick、被潮水推回原侧。
4. pickup(wick) 在 G；interact(lamp, fit_wick) 与 interact(lamp, ignite) 在 T。
5. rescue_deadline_tick 前必须点亮；评分是成功时的时间余量，越早越好。

### Observation 公开字段

`failed_crossing_ticks`、`goal`、`inventory`、`lamp_lit`、`lamp_wick_fitted`、`location`、`open_phases`、`rescue_deadline_tick`、`tide_period`、`tide_phase`、`visible_edges`、`wick_location`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`edges`、`open_phases`、`rescue_deadline_tick`、`tide_period`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`deadline`、`extra_detour`、`initial_phase`、`period`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target,tool} |
| `interact` | {choice,target,tool} |
| `move` | {edge_id,tool} |
| `pickup` | {item_id,tool} |
| `wait` | {tool,turns} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5`（6 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`6`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `bd15576fb43de963` |
| 1 | `259230bb4e8e98d2` |
| 2 | `4bbdf0bef5641169` |
| 3 | `e132b1062fe521ce` |
| 4 | `5ddfba46c0fcbecb` |
| 5 | `d07e9a2161cac477` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map04.v10.time_margin` | primary | higher | 成功时 deadline − 点亮 tick；失败 = 0 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ticks | (-60.0, 60.0) |
| `map04.v10.window_hit_rate` | secondary | higher | 安全相位通过次数 / 尝试次数 | 尝试过 S_G 的局 | 从未尝试过 S_G → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map04.v10.high_tide_entries` | guardrail | lower | 非安全相位尝试次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 30.0) |
| `map04.v10.wait_ticks` | diagnostic | none | 主动等待 tick | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 60.0) |
| `map04.v10.detour_edges` | diagnostic | lower | 走绕行海岸路的边数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 40.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_retry` | 1/6 | 0.8333 |
| `detour_only` | 6/6 | 0.6667 |
| `excess_wait` | 0/6 | 0.0 |
| `fixed_phase_script` | 0/6 | 0.0 |

- Oracle：6/6（机制触发 6/6）
- 公开启发式：6/6（主指标均值 3.0）
- legal_random：0/120（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`RESCUE_SIGNAL_WINDOW_EXPIRED`、`SIGNAL_LIT`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-04-S0-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED（failure） | 12 | 0 | 0.0065264 | 是 |
| 0 | `V10-MAP-04-S0-x2-v2` | RESCUE_SIGNAL_WINDOW_EXPIRED（failure） | 7 | 0 | 0.00344236 | 是 |
| 1 | `V10-MAP-04-S1-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED（failure） | 10 | 0 | 0.00404544 | 是 |
| 1 | `V10-MAP-04-S1-x2-v2` | SIGNAL_LIT（success） | 9 | 3 | 0.00454248 | 是 |
| 2 | `V10-MAP-04-S2-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED（failure） | 10 | 0 | 0.00493452 | 是 |
| 2 | `V10-MAP-04-S2-x2-v2` | RESCUE_SIGNAL_WINDOW_EXPIRED（failure） | 10 | 0 | 0.00477816 | 是 |

- 有效局成功：1/6
- 结算成本合计 CNY 0.02826936（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：Batch 9 改标：绕行是合法替代（detour_only 6/6），但主指标 time_margin 0.67 ≪ Oracle 3.33，机制影响效率而非通过与否
- 当前裁定：Batch 4：盲撞计 3 tick 代价；绕行保留但余量恒 ≤ Oracle；blind_retry 1/6（仅开局安全相位的对照实例），excess_wait/fixed_phase_script 0/6
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-08.md`
- `runs/v10/baselines/MAP-04.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

