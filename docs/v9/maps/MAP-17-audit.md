# MAP-17 审计：早高峰（V9 Batch 1）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 | MAP-17 / subway |
| 难度 | 中等 |
| condition | `default` |
| `scenario_hash` | `1f45fd8a4507c3154f278be7967e1ff023a8671893194433a954d76c80810989` |
| `rule_hash` | `9e9985a2238afcfccd3cb4ee43919f71cda953e291f69408df4c41d8da1eb203` |
| `source_hash` | `9ecf8c26c097fb432255164667df101925f0911ab8db96f5b10d9ccbbd735356` |
| `prompt_hash` | `1ff298c7c0dac93a2bd8aca9bfc110ff4d551ca924d9d7e0f1cc2d4bc8401ed5` |
| `metric_schema_hash` | `d82a19a1e94964db317283e281e56d9478e94f48e2aacd2103245b610f210dc1` |
| 决策预算 / 步数上限 | 38 / 160 |
| Oracle | 2 个用例各 12 个动作（`time_priority`、`energy_priority`） |
| V8 正式三局 | 0/3 成功，三局均 `decision_budget_reached`（38/38）；`service_rate` 0.4 / 0.2 / 0.4；`cumulative_wait_person_ticks` 18 / 22 / 24 |

数据来源：`runs/v9/evidence/MAP-17.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-17-final.md`、`worlds/v4/MAP-17/*`、`src/agent_arena/worlds/scenario_v8/maps/map17.py`、`runs/v9/baselines/MAP-17.json`。

**实例边界（事实）**：MAP-17 **不是** V4 适配图，它由 `worlds/scenario_v8/maps/map17.py` 直接实现，无 V6 冻结实例、无 adapter、无固定 seed 表；`seed` 参数被 `_reset_state` 直接丢弃，场景完全确定。三局是同一实例的重复运行。`CONDITIONS` 里没有 MAP-17 条目，因此 condition 取 `default`。

## 1. 能力构念

- **一句话**：在"每 tick 提交一整张四车时刻表"的联合动作空间里，围绕一个双向共用的 B-C 瓶颈，同时权衡服务率、乘客等待、人均能耗与最后交付 tick 的多目标排程能力。
- **成功**：12 tick 结算时送达 ≥8/10 人（`DEMAND_THRESHOLD_MET`）。注意 5 组 OD 中 **B→E 与 C→F 只能经 B-E-F 支线送达**，而进入支线必须先 `switch_line`；因此任何 8/10 的可行解都必然使用换线机制（事实，由 `ADJACENCY` 与 `line` 规则推出）。
- **明确反例**：把四列车全部开满环线、只送达 6/10 后停在 tick 12（`DEADLINE_SERVICE_BELOW_80`）；或像 V8 三局那样在 tick 7–9 用光 38 个决策、只送达 2–4 人。
- **递进位置**：MAP-16 是 2 车/单目标/状态搜索；本图是 4 车/4 目标/时序排程；MAP-18 是 6 车/故障/在线恢复。本图只测"静态多目标排程"，没有随机事件与故障。

## 2. 机制与因果链

```
起始：tick 0，T_A@A / T_C@C / T_D@D / T_F@F，waiting={5 组 OD ×2 人}，energy=18
  → 必需观察：demand_matrix、waiting_demand、train_positions、station_train_counts、
     train_seat_capacity、topology（BC 为双向共用段、每站 ≤2 车、每车 3 座）、tick
  → 关键决策：每 tick 一行 set_timetable{tick, operations}；release 推进并耗能，
     stop/switch_line 停 1 tick 装载，delay 原地等；同一 tick 只能有一列车走 BC
  → 立即后果：整行原子提交（任何预检失败则位置/能耗/等待/tick 全不变）；
     tick 开始时仍在站台的人各累计 1 人·tick；到达目的站自动下车
  → 终局：tick 12 结算，送达 ≥8 → DEMAND_THRESHOLD_MET，否则 DEADLINE_SERVICE_BELOW_80
```

- **可绕过核心机制的动作（事实）**：不存在能绕过"换线"的 8/10 路径。要拿到 8 人必须服务至少 4 组 OD，其中 B→E 或 C→F 至少一组在支线上；而 `release B→E` 在 `line != branch` 时返回 `INVALID_LINE_SWITCH`，`switch_line` 又只能在 B 执行。也就是说，**主机制（B 站换线 + B-C 瓶颈）是成功的必要条件**。
- **机制是否在三条真实轨迹中触发：3/3 触发（事实）**：三局都在 B 站尝试装载 `B_to_E`，也都在分支/换线上失败。
  - R0 决策 15：`T_D switch_line line="BE"` → `INVALID_LINE_SWITCH`；决策 20 已把 2 名 `B_to_E` 装上车，却始终没能进支线。
  - R1 决策 15：`T_A switch_line line="branch" board {"B_to_E":2}` → `INVALID_BOARDING_MANIFEST`（T_A 已载 `A_to_C` 2 人，2+2>3 座）。
  - R2 决策 12 起连续 `INVALID_LINE_SWITCH`，直到预算耗尽。
- **触发所需最小动作数**：12 个决策（一个 tick 一行）。Oracle 与公开启发式都是 12。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `goal`："在 12 tick 内运送至少 8/10 名乘客…" | 是（Observation） | 每步 | 是：目标、时限、阈值都公开 |
| `demand_matrix`（5 组 OD 各 2 人） | 是 | 每步 | 是 |
| `waiting_demand`、`onboard_passengers`、`delivered_by_od` | 是 | 每步 | 是：可逐站追踪客流 |
| `topology`（环线/支线节点、`shared_bidirectional_segment: "BC"`、`segment_capacity_per_tick: 1`、`station_train_berth_capacity: 2`） | 是 | 每步 | 是：瓶颈与容量公开 |
| `train_seat_capacity`（每车 3） | 是 | 每步 | 是 |
| `energy_consumed` / `energy_remaining`（上限 18） | 是 | 每步 | 是 |
| `passenger_wait_person_ticks`、`last_delivery_tick` | 是 | 每步 | 是（只能看总量，看不到逐人分解） |
| 动作词表：`release/stop/switch_line/delay`、`board` 形状 | 是（system prompt） | 开局 | 部分：**没有列出 `line` 的取值域** |
| `switch_line.line` 的合法值 `ring | branch` | **未公开**（推断：Observation 的 `topology` 恰好含 `ring_nodes`/`branch_nodes` 两个词，可猜） | — | 只能猜；猜错只得到 `INVALID_LINE_SWITCH`，不回显合法值 |
| `switch_line` 只能在 B 执行；`release B→E` 需要 `line=="branch"` | **未公开** | — | 只能试错 |
| `board` 的 OD 必须是"当前站始发"，且 `onboard+board ≤ 3 座` | **未公开** | — | 只能试错（R1 决策 15 就是座位超限） |
| 整行原子性：任一 op 预检失败则整行不提交、tick 不变 | **未公开** | — | 可从 `delta {}` 反推 |
| 等待记账：tick 开始时仍在站台的每个人都 +1 人·tick | **未公开** | — | 不影响可解性，但影响多目标判断 |
| 隐藏 `judge_state`（`waiting`、`onboard`、`pareto_vector`、`counters`） | 否 | — | 不需要 |
| Oracle / 两条参考前沿 | 否 | — | 不需要 |

**结论（事实 + 推断）**：思路所需的数据几乎全公开（客流、容量、能耗、目标），缺的是**两个枚举/前置条件**：`line ∈ {ring, branch}` 与"仅 B 可换线、B→E 需 branch"。这两条恰好是三局的主要失败点，但都能从 `topology` 的 `ring_nodes`/`branch_nodes` 推断（推断），因此不是"必须知道隐藏真值"。

## 4. 可解性与可观察性

- Oracle：2 个用例、每个 12 个动作、10/10 送达（`runs/v9/baselines/MAP-17.json`）。
- **仅凭公开信息是否存在可执行策略：存在（事实，已实测）**。`Map17Heuristic` 用 `demand_matrix`/`waiting_demand`/`train_positions`/`topology`/`tick` 排 12 行：tick 0 四车各装本站 OD；tick 1 四车并行推进；tick 2 在 B 换支线并各带 1 名 `B_to_E`；tick 3–5 收尾；tick 6–11 提交空行。结果：12 决策、10/10、等待 16、能耗/人 1.1、`DEMAND_THRESHOLD_MET`。
- 所需"额外知识"只有两个枚举值，且都能从公开 `topology` 的字段名推断；不需要 Oracle 的 OD→列车分配。
- **不标 `INTERFACE_BLOCKED`**：12 决策的纯公开策略已完成 10/10。

## 5. 预算可行性

| 策略 | 决策数 | 最终 tick | 终局 | 服务 |
|---|---|---|---|---|
| Oracle `time_priority` | 12 | 12 | `DEMAND_THRESHOLD_MET` | 10/10 |
| Oracle `energy_priority` | 12 | 12 | `DEMAND_THRESHOLD_MET` | 10/10 |
| `public_heuristic` | 12 | 12 | `DEMAND_THRESHOLD_MET` | 10/10，等待 16，能耗/人 1.1 |
| 消融 `no_branch_switch` | 12 | 12 | `DEADLINE_SERVICE_BELOW_80` | 6/10，等待 32 |
| `legal_random`（20 seed） | 38（全部用满） | 19 局 tick 4、1 局 tick 3 | 20/20 `decision_budget_reached` | 0 成功 |

`legal_random` 20 seed 共 760 条决策：`TICK_MISMATCH` 681、`TICK_COMMITTED` 79。随机策略把 `tick` 猜成 0–3 的随机值，5 次里有 4.5 次对不上当前 tick；语义拒绝按 `_action_cost = 0` 不推进时钟，所以 38 个决策只换来 3–4 个 tick。

**判定：是"模型没做对"，不是"预算不够"（高可信度）。** 38 个决策是 Oracle 的 3.2 倍；12 个决策就能 10/10。V8 三局分别在 tick 9 / 7 / 9 用光 38 个决策，其中 R2 的 dec 12–38 共 27 个决策里，**25 个是 `INVALID_LINE_SWITCH`**、1 个 `INVALID_LINK`、只有 1 个提交成功，属于重复同一错误而不是预算压力。**不标 `BUDGET_BLOCKED`。**

## 6. 指标

| 指标 | 计算事件 | 分母 | 缺失/截尾 | 三局结果 |
|---|---|---|---|---|
| `map17.service_rate` | `delivered_weight / 10`，目的站下车才计数 | 总需求 10 | 缺来源 → UNAVAILABLE；截尾 → CENSORED | 0.4 / 0.2 / 0.4 |
| `map17.cumulative_wait_person_ticks` | 每 tick 开始时站台人数累加 | 已服务乘客（登记口径） | 同上 | 18 / 22 / 24 |
| `map17.energy_per_passenger` | `energy_used / delivered` | 已服务乘客；0 → N/A | 同上 | 3.75 / 6.5 / 2.5 |
| `map17.overcapacity_events` | 运行时计 `PLATFORM_CAPACITY + SHARED_SEGMENT_CONFLICT` | episode | 0 合法 | 0 / 1 / 0 |

- **未通关仍有意义的连续主指标**：`service_rate` 与 `cumulative_wait_person_ticks` 都不依赖成功终局。三局虽然都耗尽预算，`service_rate` 仍能区分 0.4 / 0.2 / 0.4；`energy_per_passenger` 在送达 0 人时才是 N/A（本图三局分别送达 4/2/4 人，所以都有值）。
- **三局没有 `not_applicable`/`censored`**：4 条指标全部有值（`runs/v9/baselines/MAP-17.json` 与 V8 三局的 `v8_metrics.json` 一致）。
- **口径缺陷（候选，见 §8/§10）**：
  1. `cumulative_wait_person_ticks` 是**随 episode 长度单调累加**的量，而失败局在 tick 7–9 就结束，天然少累加 3–5 个 tick 的等待。R1 等待 22、R2 等待 24，看起来比"完整 12 tick 才 16"的启发式更差，是因为它们确实服务更少；但一个"只提交 1 行就结束"的策略会得到更低的等待值（首 tick 只有 10），指标方向本身不保证与服务率同向。解读时必须与 `service_rate` 成对，不能单看等待。
  2. `overcapacity_events` 的登记公式是 `STATION_CAPACITY + COLLISION`（V7 registry），运行时实现统计的是 `PLATFORM_CAPACITY + SHARED_SEGMENT_CONFLICT`；名称不同、语义相近，但**不在同一套码上**，跨图横比会导致口径漂移。
- **区分度**：Oracle 10/10（等待 16、能耗 1.1）、启发式 10/10（同值）、消融 6/10（等待 32、能耗 1.333）、随机 0/10（等待 40、能耗 N/A）。四种策略在 `service_rate` 上四档可分，**没有 `LOW_DISCRIMINATION`**。

## 7. 三次轨迹归因

### R0（38 决策，`decision_budget_reached`，tick 9，送达 4/10）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 2 | `{"operations":{"T_A":{"op":"release","to":"B"},"T_C":{"op":"release","to":"F"},"T_D":{"op":"release","to":"B"},"T_F":{"op":"release","to":"A"}},"tick":1,"tool":"set_timetable"}` | `INVALID_LINK` | `{}` |
| 5 | `{"operations":{"T_A":{"op":"release","to":"B"},"T_C":{"op":"delay"},"T_D":{"op":"delay"},"T_F":{"op":"delay"}},"tick":1,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":1,"energy_remaining":17,"passenger_wait_person_ticks":12,"station_train_counts":{"A":0,"B":1,"C":1,"D":1,"E":0,"F":1},"tick":2,"ticks_remaining":10,"train_positions":{"T_A":"B","T_C":"C","T_D":"D","T_F":"F"}}` |
| 15 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"delay"},"T_D":{"board":{"B_to_E":2},"line":"BE","op":"switch_line"},"T_F":{"op":"delay"}},"tick":4,"tool":"set_timetable"}` | `INVALID_LINE_SWITCH` | `{}` |
| 20 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"release","to":"C"},"T_D":{"board":{"B_to_E":2},"op":"stop"},"T_F":{"op":"delay"}},"tick":4,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":8,"energy_remaining":10,"onboard_passengers":{"T_A":{},"T_C":{"C_to_F":2},"T_D":{"B_to_E":2},"T_F":{"F_to_A":2}},"passenger_wait_person_ticks":18,"station_train_counts":{"A":0,"B":1,"C":2,"D":0,"E":0,"F":1},"tick":5,"ticks_remaining":7,"train_positions":{"T_A":"C","T_C":"C","T_D":"B","T_F":"F"},"waiting_demand":{"A_to_C":0,"B_to_E":0,"C_to_F":0,"D_to_B":0,"F_to_A":0}}` |
| 21 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"release","to":"D"},"T_D":{"board":{},"line":"BE","op":"switch_line"},"T_F":{"op":"delay"}},"tick":5,"tool":"set_timetable"}` | `INVALID_LINE_SWITCH` | `{}` |
| 26 | `{"tool":"set_timetable"}`（缺 `tick`/`operations`） | `INVALID_ACTION_SCHEMA` | `{"tick":6,"ticks_remaining":6}` |
| 38 | `{"operations":{"T_A":{"op":"release","to":"A"},"T_C":{"op":"release","to":"A"},"T_D":{"op":"delay"},"T_F":{"op":"release","to":"E"}},"tick":8,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":15,"energy_remaining":3,"station_train_counts":{"A":2,"B":1,"C":0,"D":0,"E":1,"F":0},"tick":9,"ticks_remaining":3,"train_positions":{"T_A":"A","T_C":"A","T_D":"B","T_F":"E"}}` |

- **首次偏离合理策略**：决策 2。四车同时写 `release` 到 `F`/`B`/`A`，其中 `C→F`、`D→B`、`F→A` 都不是相邻边，整行 `INVALID_LINK`；决策 3/4 又重复同一错误，3 个决策被浪费。
- **失败链**：tick 0 正确装载 8 人 → tick 1 起逐 tick 用 `delay` 兜底，服务率停在 4/10（A_to_C 2 + D_to_B 2）→ 决策 14 起试图用 `switch_line line="BE"` 进支线，共 13 次 `INVALID_LINE_SWITCH`（决策 14、15、17、18、21–25、28、29、31、33）→ 决策 26 又发了一次缺少 `tick` 的行 → 38 决策耗尽，tick 停在 9。
- **替代解释**：① 公开信息不足（B）——`line` 的取值域没公开，模型试了 `"BE"`、`"E"`、`"B"`；② 规划错误（E）——把 `C→F` 当成一条边（16 次 `INVALID_LINK`）；③ 推理/记忆（G）——同一个错误连续重试 13 次，没有任何"改参数"的策略；④ 预算不足（D）——不成立（12 决策即最优，38 是 3.2 倍）。

### R1（38 决策，tick 7，送达 2/10）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 4 | `{"operations":{"T_A":{"op":"release","to":"B"},"T_C":{"op":"release","to":"D"},"T_D":{"op":"release","to":"C"},"T_F":{"op":"release","to":"E"}},"tick":1,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":4,"energy_remaining":14,"passenger_wait_person_ticks":12,"station_train_counts":{"A":0,"B":1,"C":1,"D":1,"E":1,"F":0},"tick":2,"ticks_remaining":10,"train_positions":{"T_A":"B","T_C":"D","T_D":"C","T_F":"E"}}` |
| 10 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"delay"},"T_D":{"op":"release","to":"B"},"T_F":{"op":"delay"}},"tick":2,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"delivered_by_od":{"A_to_C":0,"B_to_E":0,"C_to_F":0,"D_to_B":2,"F_to_A":0},"energy_consumed":5,"energy_remaining":13,"last_delivery_tick":3,"onboard_passengers":{"T_A":{"A_to_C":2},"T_C":{"C_to_F":2},"T_D":{},"T_F":{"F_to_A":2}},"passenger_wait_person_ticks":14,"station_train_counts":{"A":0,"B":2,"C":0,"D":1,"E":1,"F":0},"tick":3,"ticks_remaining":9,"train_positions":{"T_A":"B","T_C":"D","T_D":"B","T_F":"E"}}` |
| 15 | `{"operations":{"T_A":{"board":{"B_to_E":2},"line":"branch","op":"switch_line"},"T_C":{"op":"release","to":"C"},"T_D":{"op":"release","to":"C"},"T_F":{"op":"delay"}},"tick":3,"tool":"set_timetable"}` | `INVALID_BOARDING_MANIFEST` | `{}` |
| 30 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"release","to":"D"},"T_D":{"op":"release","to":"D"},"T_F":{"op":"release","to":"F"}},"tick":5,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":12,"energy_remaining":6,"passenger_wait_person_ticks":20,"station_train_counts":{"A":0,"B":1,"C":0,"D":2,"E":0,"F":1},"tick":6,"ticks_remaining":6,"train_positions":{"T_A":"B","T_C":"D","T_D":"D","T_F":"F"}}` |
| 38 | `{"operations":{"T_A":{"op":"delay"},"T_C":{"op":"delay"},"T_D":{"op":"release","to":"C"},"T_F":{"op":"delay"}},"tick":6,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":13,"energy_remaining":5,"passenger_wait_person_ticks":22,"station_train_counts":{"A":0,"B":1,"C":1,"D":1,"E":0,"F":1},"tick":7,"ticks_remaining":5,"train_positions":{"T_A":"B","T_C":"D","T_D":"C","T_F":"F"}}` |

- **首次偏离**：决策 2/3（与 R0 同样的无效邻接，2 个决策浪费）。但真正的分水岭是决策 15：模型**猜对了** `line="branch"`，却给已经载着 2 名 `A_to_C` 的 T_A 再装 2 名 `B_to_E`，超过 3 座 → `INVALID_BOARDING_MANIFEST`。
- **失败链**：tick 0 装 8 人 → tick 1 四车推进（T_C 走 D、T_D 走 C，路线开始发散）→ D_to_B 送达 2 → 决策 15 座位超限 → 之后 T_C/T_D 在 D、C、B 之间来回，A_to_C/C_to_F/F_to_A 三组始终没送达 → 预算耗尽在 tick 7。
- **替代解释**：① B（`line` 枚举）+ F（座位容量管理：2+2>3 未检查）；② E（列车与 OD 的分配从 tick 1 起就错了，T_C 被送去 D 而它载着 C_to_F）；③ D 不成立。

### R2（38 决策，tick 9，送达 4/10）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 4 | `{"operations":{"T_A":{"op":"release","to":"B"}},"tick":1,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":1,"energy_remaining":17,"passenger_wait_person_ticks":12,"station_train_counts":{"A":0,"B":1,"C":1,"D":1,"E":0,"F":1},"tick":2,"ticks_remaining":10,"train_positions":{"T_A":"B","T_C":"C","T_D":"D","T_F":"F"}}` |
| 6 | `{"operations":{"T_C":{"op":"release","to":"B"},"T_D":{"op":"release","to":"C"}},"tick":2,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":3,"energy_remaining":15,"passenger_wait_person_ticks":14,"station_train_counts":{"A":0,"B":2,"C":1,"D":0,"E":0,"F":1},"tick":3,"ticks_remaining":9,"train_positions":{"T_A":"B","T_C":"B","T_D":"C","T_F":"F"}}` |
| 11 | `{"operations":{"T_C":{"op":"release","to":"C"},"T_D":{"board":{"B_to_E":2},"op":"stop"}},"tick":7,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":9,"energy_remaining":9,"onboard_passengers":{"T_A":{},"T_C":{"C_to_F":2},"T_D":{"B_to_E":2},"T_F":{"F_to_A":2}},"passenger_wait_person_ticks":24,"station_train_counts":{"A":0,"B":1,"C":2,"D":0,"E":1,"F":0},"tick":8,"ticks_remaining":4,"train_positions":{"T_A":"C","T_C":"C","T_D":"B","T_F":"E"},"waiting_demand":{"A_to_C":0,"B_to_E":0,"C_to_F":0,"D_to_B":0,"F_to_A":0}}` |
| 12 | `{"operations":{"T_C":{"op":"release","to":"B"},"T_D":{"op":"release","to":"E"}},"tick":8,"tool":"set_timetable"}` | `INVALID_LINE_SWITCH` | `{}` |
| 26 | `{"operations":{"T_C":{"op":"release","to":"B"}},"tick":8,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"energy_consumed":10,"energy_remaining":8,"station_train_counts":{"A":0,"B":2,"C":1,"D":0,"E":1,"F":0},"tick":9,"ticks_remaining":3,"train_positions":{"T_A":"C","T_C":"B","T_D":"B","T_F":"E"}}` |
| 38 | `{"operations":{"T_C":{"op":"release","to":"C"},"T_D":{"op":"release","to":"E"}},"tick":9,"tool":"set_timetable"}` | `INVALID_LINE_SWITCH` | `{}` |

- **首次偏离**：决策 2/3（同样的四车无效邻接）。核心死结在决策 11 之后：T_D 已在 B 装上 `B_to_E` 2 人，但接下来 27 个决策里，25 个 `INVALID_LINE_SWITCH`（`release B→E` 或 `switch_line line="BE"`）从未提交 `line="branch"`。
- **失败链**：4/10 送达（A_to_C、D_to_B）→ T_D 载着 B_to_E 停在 B → 25 次 `INVALID_LINE_SWITCH` → tick 9 耗尽预算。
- **替代解释**：① B（`line` 枚举，**首因**）；② G（同一错误重复 25 次，没有利用 `INVALID_LINE_SWITCH` 反馈缩小取值域）；③ E（`T_C release C` 等回环操作进一步消耗决策）；④ D 不成立。

**重复证据有限**：三局的失败都集中在"B 站换支线"，但具体断点不同（R0 猜错枚举值、R1 猜对枚举但超座、R2 25 次重复错误）。n=3 能说明"这是固定陷阱"，不能估计模型在该图上的稳定成功率。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E** 无效邻接路线（16 个 `INVALID_LINK`：把 `C→F`、`D→B`、`F→A` 当单边） | **B** `line` 取值域未公开（13 个 `INVALID_LINE_SWITCH`，试了 `"BE"`/`"E"`/`"B"`）；**G** 同一错误重复 | 高 | 决策 2–4、14–15、20–21、38 |
| R1 | **E** 无效邻接路线（22 个 `INVALID_LINK`，占 38 个决策的 58%） | **B** `line` 枚举（5 个 `INVALID_LINE_SWITCH`）+ **F** 资源管理错误（3 次 `INVALID_BOARDING_MANIFEST`：2+2>3 座） | 高 | 决策 4、10、15、19、30 |
| R2 | **B** 公开信息不足（`line` 枚举） | **G** 25 次重复 `INVALID_LINE_SWITCH`；**E** 回环操作 | 高 | 决策 11、12–25、26、38 |

补充事实（规则层，非模型错误）：决策 26 的 `INVALID_ACTION_SCHEMA` 让 tick 从 5 直接跳到 6，但 `passenger_wait_person_ticks` 没有变化——因为形状级拒绝走 `MapEnvironment.reject_invalid_action`（无条件 `tick_count += 1`），而语义级拒绝走 `_action_cost = 0`。同一"坏行"在两种拒绝路径下对时钟的代价不一致（见 §10 候选 C）。

## 9. 标签

- **`MEASUREMENT_VALID`**：4 条指标都能从 Trace 复算；`service_rate` 四档可分（Oracle/启发式 1.0、消融 0.6、V8 最好一局 0.4、随机 0.0），机制（换线 + 瓶颈）是成功的必要条件，不存在绕过。
- **`METRIC_DEFECT`（弱，P2）**：`cumulative_wait_person_ticks` 随 episode 长度单调累加，失败/截尾局天然少累加；`overcapacity_events` 的登记公式与运行时计数码不一致（`STATION_CAPACITY + COLLISION` vs `PLATFORM_CAPACITY + SHARED_SEGMENT_CONFLICT`）。
- **未标 `BUDGET_BLOCKED`**：38 决策是 Oracle 的 3.2 倍，12 决策即可 10/10；三局都在"重复同一个被拒动作"，不是"步数不够"。
- **未标 `INTERFACE_BLOCKED`**：存在 12 决策的纯公开策略。
- **未标 `RULE_DEFECT`**：规则自洽；唯一不一致是拒绝路径的时钟代价（候选 C），它没有改变任何一局的胜负。
- **未标 `CONSTRUCT_BYPASS`**：8/10 目标迫使至少服务一组支线 OD，换线无法绕过。

## 10. 最小可证伪修复（无证据不修改）

**旧规则 / 旧公开信息**：规则不变。公开信息只缺 `switch_line.line` 的取值域与"仅 B 可换线"。

**证据与根因**：三局共 114 个决策中，`INVALID_LINK` 占 R0 的 16 个、R1 的 22 个、R2 的 4 个；`INVALID_LINE_SWITCH` 占 R0 的 13 个、R1 的 5 个、R2 的 25 个；R1 猜对枚举后仍因座位超限（3 次 `INVALID_BOARDING_MANIFEST`）失败。失败不是"想不出排程"，而是"猜不到字段取值"。

**候选 A（推荐，只补公开信息）**：在 `_VOCABULARY["MAP-17"]` 中把 `switch_line` 写成
`switch_line(line, board)：line ∈ ring|branch；仅在 B 站可用；从 B 进支线必须先切到 branch`，并补一句 `board` 只能装当前站始发 OD 且 `onboard+board ≤ 3`。
- 预期变化：`INVALID_LINE_SWITCH` 归零；`service_rate` 上升；等待与能耗才开始真正反映多目标取舍。
- 能力构念影响：把"猜枚举"从测量里剔除，保留"4 车联合排程 + Pareto 取舍"这一真正构念。
- 反例与回归风险：如果补完枚举后仍普遍 <8/10，说明本图对中等档过难；如果瞬间 3/3 成功，则需要提高目标（例如要求 10/10 或收紧能耗）——但那属于难度调整，不应在 V9 审计里直接做。

**候选 B（只改指标文档，不改规则）**：把 `map17.overcapacity_events` 的登记公式改成运行时的 `PLATFORM_CAPACITY + SHARED_SEGMENT_CONFLICT`；把 `cumulative_wait_person_ticks` 的分母说明改为"总人·tick（不除以人数）"，并在报告层要求与 `service_rate` 成对解读（或加 `wait_per_delivered_passenger` 派生量）。
- 证据：`docs/v8/maps/MAP-17-final.md` §7 与 `map17.py::metrics()` 的码不同；R1 在 tick 7 结束、等待 22，与 tick 12 结束、等待 16 的启发式不可直接比较。
- 回归风险：改公式文本会改 `metric_schema_hash`，必须重建冻结清单；不改数值，不影响历史 Trace 复算。

**候选 C（不推荐先做，规则级）**：统一"坏行"的时钟代价——让形状级拒绝也按 `_action_cost = 0` 处理，或在公开信息里说明"格式错误也消耗 1 tick"。
- 证据：R0 决策 26 `INVALID_ACTION_SCHEMA` 使 `tick` 5→6，等待不变。
- 风险：改 `_action_cost` 会改 `rule_hash`，旧 Trace 不可直接回放；且这只影响 1/3 局的一个决策，证据强度不足以先动规则。只有在候选 A 实施后仍观察到"格式错误白送 tick"的系统性利用，才值得做。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-17.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle `time_priority` | `DEMAND_THRESHOLD_MET` | 12 | service 10/10、等待 16、能耗/人 1.1 |
| Oracle `energy_priority` | `DEMAND_THRESHOLD_MET` | 12 | 同名不同 Pareto 点 |
| `legal_random`（20 seed） | 0 成功，20/20 `decision_budget_reached` | 38（全部用满） | seed0：service 0/10、等待 40、能耗 N/A |
| `public_heuristic` | `DEMAND_THRESHOLD_MET` | 12 | service 10/10、等待 16、能耗/人 1.1、超容 0 |
| 消融 `no_branch_switch` | `DEADLINE_SERVICE_BELOW_80` | 12 | service 6/10、等待 32、能耗/人 1.333 |

**独立复算（手算，不经过 extractor）**——启发式那一局：

- 等待：tick 0 提交时站台 10 人 → +10；tick 1 剩 `B_to_E` 2 人 → +2；tick 2 开始仍 2 人（T_C 在本 tick 装 1 人）→ +2；tick 3 剩 1 人 → +1；tick 4 剩 1 人（T_D 装走最后 1 人）→ +1；tick 5 起 0 → 合计 **10+2+2+1+1 = 16**，与 `passenger_wait_person_ticks = 16` 一致。
- 服务：A_to_C 2（tick 3 到 C）+ C_to_F 2（tick 5 到 F）+ D_to_B 2（tick 4 到 B）+ F_to_A 2（tick 4 到 A）+ B_to_E 1+1（tick 4 到 E、tick 6 到 E）= **10/10**。
- 能耗：T_A 2 + T_C 3 + T_D 3 + T_F 3 = **11** → `11/10 = 1.1`。
- 消融对照：跳过 `switch_line` 后 C→F 与 B→E 都不可达，送达 6（A_to_C、D_to_B、F_to_A）→ `6/10 = 0.6`，与基线一致。

四项手算全部与运行时一致，**没有 `LOW_DISCRIMINATION`**。

## 12. V9 状态

**`VALIDATED`（P1）**。

理由：本图的构念（B-C 瓶颈下的四车多目标排程）在规则层成立，换线是成功的必要条件，指标四档可分，预算 38 远大于所需的 12。P1 的原因是公开信息缺少 `switch_line.line` 的取值域，三局的主要失败都落在这一条上；补一行词表即可把"猜枚举"从测量噪声里移除，不需要改规则。等待指标的截尾偏差与超容公式命名不一致属于 P2 文档/口径修复，应先成对解读，不急着改 schema。
