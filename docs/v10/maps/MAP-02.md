# MAP-02｜飞船 · 双重警报（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-29`
- `rule_hash`：`8e5ca44dd66dc7afb0dd7207de13e217cad6c7e91be234df326cbaaee2e5cefc`
- `metric_hash`：`cf339673be702ebae9a9514219524aec6a5f2282a3c7d2acb0b49ddbd356c13c`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9c：Oracle 4/4、启发式 4/4、no_gate 1/4（实例相关）、其余消融 0/4；阶段 6 的 3 局 MiMo 非法动作 0

- 主指标：`map02.v10.mission_success`
  - `map02.v10.mission_success`：泄漏后同时保住导航核心并把乘员送入逃生舱（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. C 是中枢，连接 L1（乘员区）与 R1（导航核心）；L1–L2 通向乘员，R1–R2 通向逃生舱；C_X + X_L2 是备用通道。
2. 导航核心在 R1，需用维修包固定（interact(nav_core, brace_in_case)）；维修包开局可用一次。
3. 乘员在 L2：先 pickup(crew) 再护送；把乘员带到 R2 即进入逃生舱。
4. **泄漏会在若干动作后出现**（具体时点不公开）；公告后若未隔离 L1，船舱扩散倒计时递减，归零则导航核心报废；同时乘员压力倒计时独立递减，归零则任务失败。
5. 在 C 用 interact(center_gate, isolate_L1) 可隔离 L1；关闭后 C↔L1 不可通行。
6. 导航核心固定 + 乘员进逃生舱**两者都完成**才算成功；deadline 见 Observation。

### Observation 公开字段

`center_gate`、`crew_escorted`、`crew_in_escape_pod`、`crew_location`、`crew_pressure_ticks`、`deadline_tick`、`goal`、`leak_active`、`leak_location`、`location`、`nav_core_location`、`nav_core_secured`、`navigation_alarm`、`repair_pack_available`、`spread_contained`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`crew_pressure_ticks`、`global_deadline`、`label`、`leak_trigger_index`、`spread_ticks`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`deadline`、`event_order_seed`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target,tool} |
| `interact` | {choice,target,tool} |
| `move` | {edge_id,tool} |
| `pickup` | {item_id,tool} |
| `wait` | {tool,turns} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `71d8b6512f1bec82` |
| 1 | `fd2518c9df18e96b` |
| 2 | `644da64ff6fc7c9c` |
| 3 | `4696a753f18273b7` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map02.v10.mission_success` | primary | higher | 泄漏后同时保住导航核心并把乘员送入逃生舱 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；泄漏扩散/压力归零 → VALID 0 | ratio | (0.0, 1.0) |
| `map02.v10.event_response_latency` | secondary | lower | 泄漏公告后第一个有效动作的延迟 tick | 发生泄漏的局（1） | 未泄漏 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map02.v10.dual_objective_completion` | secondary | higher | （导航核心已固定 + 乘员已在逃生舱）/ 2 | 2 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map02.v10.stale_plan_actions_after_leak` | guardrail | lower | 泄漏后仍按旧计划前往受威胁区域的动作数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map02.v10.crew_decompression` | guardrail | lower | 乘员压力是否归零终局（1 表示失败） | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map02.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `crew_only` | 0/4 | 0.0 |
| `late_react` | 0/4 | 0.0 |
| `nav_only` | 0/4 | 0.0 |
| `no_gate` | 1/4 | 0.25 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`CREW_PRESSURE_LOST`、`DUAL_OBJECTIVE_COMPLETE`、`NAV_CORE_FLOODED`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-02-S0-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.002918 | 是 |
| 0 | `V10-MAP-02-S0-m2` | CREW_PRESSURE_LOST（failure） | 12 | 0 | 0.009126 | 是 |
| 0 | `V10-MAP-02-S0-x2-v2` | DUAL_OBJECTIVE_COMPLETE（success） | 11 | 1 | 0.0064664 | 是 |
| 1 | `V10-MAP-02-S1-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.00223008 | 是 |
| 1 | `V10-MAP-02-S1-m2` | CREW_PRESSURE_LOST（failure） | 10 | 0 | 0.00381052 | 是 |
| 1 | `V10-MAP-02-S1-x2-v2` | CREW_PRESSURE_LOST（failure） | 10 | 0 | 0.00334476 | 是 |
| 2 | `V10-MAP-02-S2-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.00266712 | 是 |
| 2 | `V10-MAP-02-S2-m2` | CREW_PRESSURE_LOST（failure） | 10 | 0 | 0.00305016 | 是 |
| 2 | `V10-MAP-02-S2-x2-v2` | CREW_PRESSURE_LOST（failure） | 10 | 0 | 0.004486 | 是 |

- 有效局成功：1/9
- 结算成本合计 CNY 0.03809904（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：泄漏时序/扩散窗口/乘员压力/deadline 随 seed 变化
- 当前裁定：Batch 9c：Oracle 4/4、启发式 4/4、no_gate 1/4（实例相关）、其余消融 0/4；阶段 6 的 3 局 MiMo 非法动作 0
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-29.md`
- `runs/v10/baselines/MAP-02.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

