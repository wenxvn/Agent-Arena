# MAP-16｜地铁 · 单线预约与节点容量（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-36`
- `rule_hash`：`a8dc8697b1535df480dcdba9b8bec061ce7ae4cbdc0143a06396b338ddc7c0da`
- `metric_hash`：`78a01c390ee939d55f584b7fa60b065e89b4ecc700abb5d0988556777b54c335`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9h：Oracle 4/4、启发式 4/4、三消融 0/4；阶段 12 三局非法动作 0

- 主指标：`map16.v10.mission_success`
  - `map16.v10.mission_success`：两列车都在不发生区段/节点冲突的前提下到达各自终点（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 线路：A—X—M—Y—B 为单线主线，M—D 为唯一侧线；每段同一 tick 只能过 1 列车，每个节点（含侧线）同一时刻只能停 1 列车。
2. 两列车 a、b 各自有固定方向表（见 train_route_directions）；set_route(train_id, next_node) 只登记下一跳，move_train() 才会把**所有**已登记的路由作为一整帧提交并推进 1 tick。
3. 若两列车的下一跳占用同一区段，或同帧后停在同一节点，立即以对应冲突终局。
4. 让行必须把一列车临时停到侧线 D：occupy_siding(train_id, next_node) 与 set_route 等价，但目标必须是侧线。
5. 两列车都到达各自终点即成功；提交后若不存在安全完成路径，则判定死锁失败。
6. 本实例的起点、终点与侧线节点见 Observation 的 train_positions、train_goals、siding_nodes 与 topology。

### Observation 公开字段

`未显式声明`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`goals`、`label`、`siding_nodes`、`start_positions`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`goals`、`label`、`shortest_makespan`、`start_positions`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `check_goal` | {tool} |
| `compare_records` | {entry_ids,tool} |
| `formal_accuse` | {cited_entry_ids,event_claims,person_id,tool} |
| `inspect` | {evidence_id,tool} |
| `inspect_network` | {tool} |
| `interact` | {operation,target_id,tool} |
| `interview` | {npc_id,shown_casebook_entry_ids,shown_evidence_ids,tool,topic_id} |
| `move` | {to,tool} |
| `move_train` | {tool} |
| `observe_signpost` | {tool} |
| `occupy_siding` | {next_node,tool,train_id} |
| `read_log` | {log_id,tool} |
| `record` | {entry_id,evidence_ids,tool} |
| `release_section` | {section_id,tool,train_id} |
| `replace` | {part_id,tool} |
| `restart` | {tool} |
| `return_to_camp` | {tool} |
| `rollback` | {tool} |
| `set_route` | {next_node,tool,train_id} |
| `set_timetable` | {operations,tick,tool} |
| `submit_intermediate_hypothesis` | {candidate_person,confidence,event_ids_known,tool} |
| `take_spare` | {part_id,tool} |
| `test` | {test_id,tool} |
| `wait` | {tool,turns} |
| `write_memory` | {facts,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `5228a6395f3d9fd7` |
| 1 | `c6f8209e96f8ef5c` |
| 2 | `2f7fbc072cca51c1` |
| 3 | `866627cf4d7521f1` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map16.v10.mission_success` | primary | higher | 两列车都在不发生区段/节点冲突的前提下到达各自终点 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；冲突/死锁终局 → VALID 0 | ratio | (0.0, 1.0) |
| `map16.v10.legal_action_rate` | secondary | higher | 合法决策数 / 总决策数（结构不符或非法路由计为不合法） | 总决策数 | 无决策 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map16.v10.node_capacity_conflicts` | guardrail | lower | 节点容量冲突次数（含侧线容量冲突） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 100.0) |
| `map16.v10.deadlock_count` | guardrail | lower | 进入无安全完成状态（死锁）的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 100.0) |
| `map16.v10.makespan_gap` | secondary | lower | 成功时的完成 tick 与最短排程之差 | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 100.0) |
| `map16.v10.committed_ticks` | diagnostic | lower | 终局时的已提交移动 tick 数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `double_booking` | 0/4 | 0.0 |
| `no_siding` | 0/4 | — |
| `route_only` | 0/4 | — |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DEADLOCK`、`GATE_OPENED`、`NODE_CAPACITY_CONFLICT`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-16-S0-r2` | NODE_CAPACITY_CONFLICT（failure） | 7 | 0 | 0.0040712 | 是 |
| 1 | `V10-MAP-16-S1-r2` | GATE_OPENED（success） | 19 | 1 | 0.00975064 | 是 |
| 2 | `V10-MAP-16-S2-r2` | NODE_CAPACITY_CONFLICT（failure） | 4 | 0 | 0.00211672 | 是 |

- 有效局成功：1/3
- 结算成本合计 CNY 0.01593856（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：起点/终点四组实例随 seed 变化（复用 V4 公开构造参数，不改规则）
- 当前裁定：Batch 9h：Oracle 4/4、启发式 4/4、三消融 0/4；阶段 12 三局非法动作 0
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-36.md`
- `runs/v10/baselines/MAP-16.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

