# MAP-17｜地铁 · 四车排程（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-34`
- `rule_hash`：`cd7765f7159a0df1ebb4296e83855818682cf61767bdf48613c88464625bb9ef`
- `metric_hash`：`7fb46f5ef704ae20ff3128340c743026fd94effc79d6fa185b8bffe928523b37`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9g：Oracle 4/4、启发式 4/4、三消融 0/4；公开规则含瓶颈共用与整帧提交语义

- 主指标：`map17.v10.mission_success`
  - `map17.v10.mission_success`：在时限内送达人数达到该实例的服务阈值（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 环线 A—B—C—D 与支线 B—E—F 共用 B 站咽喉；每段每 tick 只能过 1 列车。
2. 每 tick 提交一整行时刻表：set_timetable(tick, operations)。operations 以列车 id 为键，每项含 op（stop/release/detour/switch_line/delay）与目标/上车人数。
3. 上车（board）必须对应列车的 task 路线与需求表 demand_matrix；站台/区段容量或同段冲突会让整帧被拒（tick 不前进）。
4. 需求表共 10 人；到时限时送达人数达到本实例的服务阈值即成功。
5. 公开验收参数（服务阈值与时限）见 goal 与 ticks_remaining。

### Observation 公开字段

`delivered_by_od`、`demand_matrix`、`energy_consumed`、`energy_remaining`、`goal`、`last_delivery_tick`、`onboard_passengers`、`passenger_wait_person_ticks`、`station_train_counts`、`tick`、`ticks_remaining`、`topology`、`train_positions`、`train_seat_capacity`、`waiting_demand`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`horizon`、`label`、`threshold`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`schedule`、`threshold`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `set_timetable` | {operations,tick,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `a895b1e57dc5996a` |
| 1 | `12d9e3ec853f9c82` |
| 2 | `cf20af527734aa05` |
| 3 | `aacb27ec5078e36c` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map17.v10.mission_success` | primary | higher | 在时限内送达人数达到该实例的服务阈值 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；到时限未达标 → VALID 0 | ratio | (0.0, 1.0) |
| `map17.v10.service_rate` | secondary | higher | 已送达人次 / 10 | 10 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map17.v10.threshold_margin` | secondary | higher | 送达人次 − 本实例服务阈值（正数表示超过门槛） | 1 | NOT_APPLICABLE | 截尾 → CENSORED | passengers | (-10.0, 10.0) |
| `map17.v10.wait_person_ticks` | guardrail | lower | 累计候车人·tick | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | person_ticks | (0.0, 500.0) |
| `map17.v10.refused_frames` | guardrail | lower | 被环境整帧拒绝的时刻表数（容量/冲突/时刻不符） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map17.v10.energy_used` | diagnostic | lower | 已消耗的线路能量 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | energy | (0.0, 500.0) |
| `map17.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `half_board` | 0/4 | 0.0 |
| `no_board` | 0/4 | 0.0 |
| `no_ring` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DEADLINE_SERVICE_BELOW_THRESHOLD`、`DEMAND_THRESHOLD_MET`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-17-S0-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD（failure） | 12 | 0 | 0.01474412 | 是 |
| 1 | `V10-MAP-17-S1-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD（failure） | 12 | 0 | 0.0108868 | 是 |
| 2 | `V10-MAP-17-S2-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD（failure） | 12 | 0 | 0.0108968 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.03652772（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：服务阈值（8/9/10）与时限（12/14）随 seed 变化
- 当前裁定：Batch 9g：Oracle 4/4、启发式 4/4、三消融 0/4；公开规则含瓶颈共用与整帧提交语义
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-34.md`
- `runs/v10/baselines/MAP-17.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

