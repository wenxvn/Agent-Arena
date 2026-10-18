# MAP-12｜极地 · 极夜三十天（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-22`
- `rule_hash`：`bf14aafe6bb7597ba233d1c22b5675e8d44cefaf649e1321db96fb335c2c8a79`
- `metric_hash`：`f4549bd75e62d0b7d8e89bc4f4789158b62a59ee40f4c8b1767a4568a3a288b3`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：30 天 × 槽位排班、每日双结算、双归零失败；all_research/all_forage/no_research/waste_slots 全 0/4；启发式研究 38/35/40/75

- 主指标：`map12.v10.mission_success`
  - `map12.v10.mission_success`：存活 30 天且研究积分达到目标（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 共 30 天，每天 3 个劳动槽；assign(plan=[...]) 一次排完当天。
2. forage：食物 +2；repair：站体 +2；research：研究 +1。
3. 每日结算：食物 -2、站体 -2。
4. 研究积分达到 34 且存活到第 30 天才算成功。
5. 食物归零 → STARVED；站体归零 → STATION_LOST。

### Observation 公开字段

`daily_consumption`、`daily_decay`、`day`、`days_remaining`、`food`、`goal`、`idle_slots`、`integrity`、`research_points`、`research_target`、`slots_per_day`、`tasks`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`daily_consumption`、`daily_decay`、`days`、`label`、`research_target`、`slots_per_day`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`initial_food`、`initial_integrity`、`label`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `assign` | {plan,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `af9e1f6d36f528e5` |
| 1 | `8f384575a50a04a2` |
| 2 | `ca995dbd8b0c177e` |
| 3 | `ab812ebacee0ea58` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map12.v10.mission_success` | primary | higher | 存活 30 天且研究积分达到目标 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map12.v10.research_points` | secondary | higher | 累计研究积分 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | points | (0.0, 200.0) |
| `map12.v10.research_completion` | secondary | higher | 研究积分 / 目标（可 >1：超额研究计入） | 目标积分 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 3.0) |
| `map12.v10.min_food` | guardrail | higher | 过程中最低食物库存 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | stock | (0.0, 100.0) |
| `map12.v10.idle_slots` | diagnostic | lower | 未分配任何任务的槽位总数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 100.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `all_forage` | 0/4 | 0.0 |
| `all_research` | 0/4 | 0.0 |
| `no_research` | 0/4 | 0.0 |
| `waste_slots` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`RESEARCH_COMPLETED`、`RESEARCH_SHORT`、`STARVED`、`STATION_LOST`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-12-S0-interface` | RESEARCH_COMPLETED（success） | 30 | 1 | 0.01534724 | 是 |
| 1 | `V10-MAP-12-S1-interface` | RESEARCH_COMPLETED（success） | 30 | 1 | 0.01490592 | 是 |
| 2 | `V10-MAP-12-S2-interface` | STATION_LOST（failure） | 12 | 0 | 0.00577524 | 是 |

- 有效局成功：2/3
- 结算成本合计 CNY 0.03602840（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例；补上 V9 缺失的离线跨期证据
- 当前裁定：Batch 5：30 天 × 槽位排班、每日双结算、双归零失败；all_research/all_forage/no_research/waste_slots 全 0/4；启发式研究 38/35/40/75
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-22.md`
- `runs/v10/baselines/MAP-12.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

