# MAP-18｜地铁 · 故障传播（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-02`
- `rule_hash`：`b57e6849242bf02bc591e38303a459d7b7d15f116cd806eabd8e43c5fae7fe35`
- `metric_hash`：`22338c8a5ae9a9b08086d16b11ac767bf5a6fe51913c15fc11c949821084f527`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，greedy 3/5，启发式 5/5

- 主指标：`map18.v10.service_rate`, `map18.v10.recovery_delay_ticks`
  - `map18.v10.service_rate`：delivered_passengers / 18（方向：higher）
  - `map18.v10.recovery_delay_ticks`：max(受影响任务送达/取消 tick) - fault_start（方向：lower）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 5/5。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 每个决策提交当前 tick 的一整行时刻表：set_timetable(tick=当前 tick, operations)。operations 只列需要动作的列车；未列出的列车原地等待。被提交的行使物理 tick +1。
2. op ∈ release(to)|detour(to)：沿一条相邻区段移动一站（detour 与 release 等价，用于跨线联络段）；temporary_stop：原地等待；cancel_service(task_id)：列车在起点时取消本车任务，3 人计入服务损失且不可撤销，空车之后可用 release 调位。
3. 每项任务只能由 train_task 指定的列车沿 task_routes 的路线完成；列车在 release_tick 之前离开起点 → 整行被拒 DISPATCH_WINDOW_VIOLATION（tick 不前进，消耗动作预算）。
4. 每个区段每 tick 最多 1 列车（双向合计）；每站最多 2 列车（含已交付停靠的车）。相向对穿 HEAD_ON_COLLISION、同段双车 SEGMENT_CAPACITY、站台超员 STATION_CAPACITY_EXCEEDED 都会立即终局。
5. 已交付的列车不能再移动（整行被拒 COMPLETED_TRAIN_MOVED）。非法相邻、未知列车、tick 不符等也整行被拒，tick 不前进但消耗动作预算。
6. 运行期间可能有一个区段临时封闭；区段与时长事先未知，封闭期间出现在 closed_segments。进入封闭区段的列车返回 TRACK_CLOSED 并原地等待，同行其他操作照常结算。
7. 到 horizon 结算：送达 ≥ 13/18 人为成功；所有任务都已交付或取消时提前结算。动作预算用尽仍未结算即截尾。

### Observation 公开字段

`action_budget_remaining`、`alert_message_if_any`、`canceled_passengers`、`closed_segments`、`delivered_passengers`、`goal`、`horizon`、`published_dispatch_windows`、`recovery_status`、`station_berths`、`success_threshold_passengers`、`task_routes`、`task_status`、`tick`、`ticks_remaining`、`topology`、`train_positions`、`train_task`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`action_budget`、`alert_tick`、`horizon`、`release_ticks`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`affected_tasks`、`fault_duration`、`fault_edge`、`fault_start`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `set_timetable` | {operations,tick,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4`（5 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`5`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `5c0128e47f1b1f38` |
| 1 | `20ae1a219495a0db` |
| 2 | `18d58e28aaf826cb` |
| 3 | `1eadfcb7fa9130d0` |
| 4 | `fe481234bd1c6e28` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map18.v10.service_rate` | primary | higher | delivered_passengers / 18 | 18（取消不删分母） | NOT_APPLICABLE | 部分送达在截尾/失败时仍 VALID | ratio | (0.0, 1.0) |
| `map18.v10.recovery_delay_ticks` | primary | lower | max(受影响任务送达/取消 tick) - fault_start | 受影响任务全部了结（1） | NOT_APPLICABLE | 截止或预算截尾时仍有受影响任务未了结 → CENSORED；冲突终局 → NOT_APPLICABLE | ticks | (-14.0, 20.0) |
| `map18.v10.conflict_terminal` | guardrail | lower | 终局原因 ∈ {HEAD_ON_COLLISION, SEGMENT_CAPACITY, STATION_CAPACITY_EXCEEDED} | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map18.v10.closed_entry_attempts` | guardrail | lower | count(release/detour 进入封闭区段) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map18.v10.plan_changes` | secondary | none | 故障开始后，受影响列车的操作偏离公开无故障时刻表的次数（含暂停、取消、调位） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map18.v10.window_violations` | guardrail | lower | count(DISPATCH_WINDOW_VIOLATION 行) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map18.v10.rejected_rows` | guardrail | lower | count(被拒、物理时钟未前进的决策) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map18.v10.delay_person_ticks` | secondary | lower | Σ 3 × max(实际到达 - 计划到达, 0)（仅送达任务） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | person_ticks | (0.0, 300.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `greedy_dispatch` | 3/5 | 0.8667 |
| `ignore_windows` | 0/5 | 0.3 |
| `no_replan` | 1/5 | 0.7 |

- Oracle：5/5（机制触发 5/5）
- 公开启发式：5/5（主指标均值 0.9667）
- legal_random：0/100（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ACTION_LIMIT_REACHED`、`HEAD_ON_COLLISION`、`SEGMENT_CAPACITY`、`SERVICE_COMPLETE`、`STATION_CAPACITY_EXCEEDED`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-18-S0-i2` | HEAD_ON_COLLISION（failure） | 13 | 0.5 | 0.01704928 | 是 |
| 0 | `V10-MAP-18-S0-p0` | ACTION_LIMIT_REACHED（failure） | 20 | 0.0 | 0.02415288 | 是 |
| 1 | `V10-MAP-18-S1-i2` | STATION_CAPACITY_EXCEEDED（failure） | 8 | 0.5 | 0.00803436 | 是 |
| 1 | `V10-MAP-18-S1-p0` | ACTION_LIMIT_REACHED（failure） | 20 | 0.0 | 0.00577792 | 是 |
| 2 | `V10-MAP-18-S2-i2` | SEGMENT_CAPACITY（failure） | 7 | 0.333333 | 0.00764352 | 是 |
| 2 | `V10-MAP-18-S2-p0` | ACTION_LIMIT_REACHED（failure） | 20 | 0.0 | 0.01964128 | 是 |

- 有效局成功：0/6
- 结算成本合计 CNY 0.08229924（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过
- 当前裁定：Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，greedy 3/5，启发式 5/5
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-02.md`
- `runs/v10/baselines/MAP-18.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

