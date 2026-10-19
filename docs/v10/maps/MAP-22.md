# MAP-22｜丛林 · 无地图的丛林（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-12`
- `rule_hash`：`88d36cf3fae35366ff9bb9a665fa3b5eab294be7318c9fe2861e005905608603`
- `metric_hash`：`6271b1d058dffeaba9715c8d3d865b1ecd7da601a937d948ba89cf45588b26d0`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：遮蔽（只给当前路标与方位）+ 死胡同分岔 + 跨阶段返程；no_memory_write 0/4（V9 为 12 决策成功）、fixed_bearings/no_return/random_walk 0/4；公开记忆 DFS 3/4（seed 1 因贪心方位顺序超预算，属策略弱点）

- 主指标：`map22.v10.mission_success`
  - `map22.v10.mission_success`：先 check_goal 再 return_to_camp（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 你在一片没有地图的丛林里，只能看到**当前**路标与可用方位（north/east/south/west）。
2. move(bearing) 沿该方位走到相邻节点；方位不可用 → BEARING_NOT_AVAILABLE。
3. observe_signpost 耗 1 tick，给出当前路标的特征（用于自证记忆），不改变位置。
4. write_memory(facts) 把 1–3 条 {key,value} 写进 agent_notes；内容原样保留，是跨阶段唯一可靠通道。
5. 先在遗迹 check_goal，再回到营地 return_to_camp 才算完成。
6. 移动次数上限 44；相邻节点在你走过去之前不可见。

### Observation 公开字段

`agent_notes`、`bearings`、`current_sign`、`distinctive_feature`、`goal`、`move_budget`、`moves_used`、`ruin_recorded`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`bearings`、`depth`、`move_budget`、`node_count`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`depth`、`goal_sign`、`graph`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `check_goal` | {tool} |
| `move` | {bearing,tool} |
| `observe_signpost` | {tool} |
| `return_to_camp` | {tool} |
| `write_memory` | {facts,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `3ade021e2a1278b4` |
| 1 | `31d9f4a2f2896a65` |
| 2 | `e9e6cc8c9fd6b480` |
| 3 | `65653ab1658205aa` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map22.v10.mission_success` | primary | higher | 先 check_goal 再 return_to_camp | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map22.v10.route_recall` | secondary | higher | 写入的方位序列与真实路线的最长匹配比例 | 写入过记忆的局（1） | 未写记忆 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map22.v10.wasted_moves` | guardrail | lower | 实际移动数 − 该种子最短往返移动数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 60.0) |
| `map22.v10.memory_writes` | diagnostic | none | write_memory 调用次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 60.0) |
| `map22.v10.goal_recorded` | secondary | higher | 是否先完成遗迹打卡再返程 | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `fixed_bearings` | 0/4 | 0.0 |
| `no_memory_write` | 0/4 | 0.0 |
| `no_return` | 0/4 | — |
| `random_walk` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：3/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`MOVE_BUDGET_EXHAUSTED`、`RETURNED_TO_CAMP_WITH_RUIN_RECORD`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-22-S0-ext` | unknown_provider_spend（unknown_provider_spend） | 34 | 0 | 0.01851776 | 否（中断保留） |
| 0 | `V10-MAP-22-S0-ext-r2` | MOVE_BUDGET_EXHAUSTED（failure） | 59 | 0 | 0.03265288 | 是 |
| 1 | `V10-MAP-22-S1-ext` | MOVE_BUDGET_EXHAUSTED（failure） | 58 | 0 | 0.0306594 | 是 |
| 2 | `V10-MAP-22-S2-ext` | unknown_provider_spend（unknown_provider_spend） | 10 | 0 | 0.00543668 | 否（中断保留） |
| 2 | `V10-MAP-22-S2-ext-r2` | RETURNED_TO_CAMP_WITH_RUIN_RECORD（success） | 28 | 1 | 0.01779472 | 是 |

- 有效局成功：1/3；另有 2 局 provider/账本中断（保留但不计入）
- 结算成本合计 CNY 0.10506144（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 迷宫
- 当前裁定：Batch 4：遮蔽（只给当前路标与方位）+ 死胡同分岔 + 跨阶段返程；no_memory_write 0/4（V9 为 12 决策成功）、fixed_bearings/no_return/random_walk 0/4；公开记忆 DFS 3/4（seed 1 因贪心方位顺序超预算，属策略弱点）
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-12.md`
- `runs/v10/baselines/MAP-22.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

