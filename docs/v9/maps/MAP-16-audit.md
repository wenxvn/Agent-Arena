# MAP-16 审计：单线会车（V9 Batch 1）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 | MAP-16 / subway |
| 难度 | 简单 |
| condition | `constraint_table` |
| `scenario_hash` | `b1224ccd52a712c7bf60d51797633f345b304ae620b876225250179e1a3fb8bf` |
| `rule_hash` | `47548b6c5585a6d0d82b8de082d1ce1f99009e4e9bd9639f0957ed623b0b8048` |
| `source_hash` | `40003ce79d68afadf61c33686b82f830cf3666d486feadc8fdcd501724eb6fa3` |
| `prompt_hash` | `50cdea891e4cd0991657a50680082fecc1f79fe895fb8a67301ecf13af38e43d` |
| `metric_schema_hash` | `1fca8c5b91c939b9b8bfab0d71e0512c1f2c50c947576f782eb27dcc675a27e0` |
| 决策预算 / 步数上限 | 30 / 160（V4 `Map16Environment` 与适配器一致，无夹紧） |
| Oracle | 1 个用例 17 个动作（`MAP-16-solver-success`）；`worlds/v4/MAP-16/oracle_trace.jsonl` 另有 `a_yields_siding` / `b_yields_siding` 两条 16 动作手写轨迹 |
| V8 正式三局 | 0/3 成功。R0 `DEADLOCK` 6 决策；R1 `NODE_CAPACITY_CONFLICT` 24 决策；R2 `NODE_CAPACITY_CONFLICT` 15 决策 |

数据来源：`runs/v9/evidence/MAP-16.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-16-final.md`、`worlds/v4/MAP-16/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v4/map16.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`runs/v9/baselines/MAP-16.json`。

**V6 冻结实例边界（事实）**：适配器 `V8_INSTANCE_ID["MAP-16"] = "map16_l3_original"`，用 `get_scene()` + `build_v6_environment()` 构造 V6 冻结实例，condition 固定为 `constraint_table`。`Map16Environment._reset_state` 只接受 `seed ∈ {0,1,2}` 三个固定重复标签，没有随机事件；V8 三次重复是同一实例的三个标签，不是三个独立场景。`V4MapAdapter` 不重写规则、不改指标，只把 V8 动作转成 `ScenarioV4Action` 并记录决策日志。

## 1. 能力构念

- **一句话**：在只知道公开拓扑与容量的条件下，为两列反向列车排出"谁进侧线、谁先通过"的会车顺序，并在"每 tick 两次决策原子提交"的接口下避免不可恢复死锁。
- **成功**：两车互换端点（a→B、b→A）且无任何容量/区段冲突。6 个 `move_train` tick 是 BFS 最优，也是本图唯一可行的最短结构。
- **明确反例**：只推进一列车、从不让任何一列车进入 D 侧线；当位置到 `(a=Y, b=B)` 时两车互相指向对方所在的唯一邻节点，`_has_safe_completion` 返回 False，环境立即判定 `DEADLOCK`（事实：`map16.py` 第 206–211 行在同一 `move_train` 内完成判定，玩家没有反应窗口）。
- **递进位置**：本图是 subway 三图的状态空间最小样例——2 车、6 节点、无时钟压力、无故障、无随机；MAP-17 换成四车多目标时刻表，MAP-18 加闭塞故障与在线恢复。本图只测"离散预约 + 会车顺序"，不测在线恢复或多目标权衡。

## 2. 机制与因果链

```
起始 (a=A, b=B, tick 0, pending={})
  → 必需观察：topology 是 A-X-M-Y-B 单线 + M-D 叶节点；segment_capacities 全 1；
     node_capacities 全 1；train_route_directions 给出每车在当前节点允许的去向
  → 关键决策：把其中一列车经 M 送进 D 侧线（set_route/occupy_siding 到 D），
     另一列通过 M，之后再让侧线车出来
  → 立即后果：move_train 原子结算所有 pending；若两车落到同一节点或同一无向区段，
     终局 NODE_CAPACITY_CONFLICT / SECTION_RESERVATION_CONFLICT / HEAD_ON_SWAP；
     若结算后状态没有安全完成路径，终局 DEADLOCK
  → 终局：GATE_OPENED（6 tick，gap 0）或上述任一失败码
```

- **可绕过核心机制的动作：没有（事实）**。主线是一条路径 A-X-M-Y-B，两车必须交换两端；两车不能同节点，也不能同 tick 走同一无向区段，所以错车只能发生在 M 的唯一支路 D。独立复算：在公开拓扑上枚举联合后继，从 `(A,B)` 到 `(B,A)` 共 28 个可达状态、最短 6 tick（见 §11），与 `worlds/v4/MAP-16/acceptance.md` 的 28 态/6 tick 一致。
- **机制是否在三条真实轨迹中触发：3/3 触发（事实）**。
  - R0 决策 6 `move_train → DEADLOCK`：`train_positions {"a":"Y","b":"B"}`、`terminal_reason "DEADLOCK"`。
  - R1 决策 24 `move_train → NODE_CAPACITY_CONFLICT`：结算前 `pending_route_reservations {"a":"M","b":"M"}`。
  - R2 决策 15 `move_train → NODE_CAPACITY_CONFLICT`：同样 `{"a":"M","b":"M"}`。
- **触发所需最小动作数**：16 个决策（6 次 `move_train` + 10 次 `set_route`）；Oracle 17 个（多 1 次 `inspect_network`）。决策预算 30，余量 14。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `topology`（A-X-M-Y-B + D 叶节点） | 是（Observation） | 每步 | 是：可推断 D 是唯一避让位 |
| `train_route_directions` | 是（Observation） | 每步 | 是：给出每车每个节点的允许去向，等价于有向邻接 |
| `segment_capacities`、`node_capacities`（全 1） | 是（Observation） | 每步 | 是：给出容量 1 的事实 |
| `train_positions`、`train_goals`、`occupied_nodes`、`pending_route_reservations` | 是（Observation） | 每步 | 是：规划所需的全部状态 |
| 动作名与字段形状（`set_route`/`occupy_siding`/`release_section`/`inspect_network`/`move_train`） | 是（system prompt 词表 + 契约） | 开局 | 部分：只说明字段，不说明语义 |
| "本图机制"提示 | 是，但**内容退化** | 开局 | **否**：`system_prompt` 第 2 行为 `本图机制：A V4 environment behind the V8 public contract.`（事实，见 `prompts.py::map_docstring`；V4 适配器没有业务 docstring，Observation 也没有 `goal` 字段，于是回落到适配器类 docstring） |
| 单线会车硬规则：同段对向交换禁止、同 tick 一区段只能一列车、死锁立即判负、`move_train` 原子提交全部 pending | **未公开** | — | 只能从结果码与接口形状反推 |
| `occupy_siding` 的真实前置：`next_node` 必须 ∈ 侧线集合 `{D}` 且与当前节点相邻；实现上等价于 `set_route` 到 D | **未公开** | — | 用 `set_route` 到 D 即可，不需要 `occupy_siding` |
| `release_section` 的真实语义：只能撤销**本车尚未提交**的预约；不能释放别车、不能释放已提交区段 | **未公开** | — | 否：R1/R2 都在这里连错 3 次 |
| 节点容量**不在预约阶段**校验，只在 `move_train` 结算时校验 | **未公开** | — | 这是延迟硬失败的来源 |
| 隐藏 `judge_state`（`positions`、`pending`、`conflicts`、`status`、`terminal_reason`） | 否 | — | 不需要 |
| Oracle / BFS 最优值（6 tick） | 否 | — | 不需要（可由公开拓扑自行搜索得到） |

**结论（事实 + 推断）**：几何与容量是公开的；**规则语义没有公开**。一个只会读 prompt 的模型必须通过结果码试出"死锁""不能对向交换""release 只撤自己的预约"。这属于公开信息不足（B），不是"必须知道隐藏真值才能解题"——因为 16 决策的公开策略确实存在（§4）。

> 口径说明（事实）：以上"未公开"针对 **V8 冻结条件**（`v8_compat` 臂）。V9 另有一个 `v9_fixed` 臂（`src/agent_arena/v9/prompts.py::V9_PUBLIC_ADDENDA["MAP-16"]`），已补入第 4 条、`occupy_siding` 的前置，以及第 5 条的后半（"两车同节点会在 `move_train` 结算时冲突"）；仍缺"单线同段禁止对向交换""死锁立即判负""D 是唯一侧线"三条。两臂的 prompt hash 不同，不能混用。

## 4. 可解性与可观察性

- Oracle：1 个用例，17 个动作，6 tick，`GATE_OPENED`（`runs/v9/baselines/MAP-16.json` → `oracle[0] = {trace_id: "MAP-16-solver-success", actions: 17, ok: true}`）。`worlds/v4` 的两条手写轨迹各 16 动作。
- **仅凭公开信息是否存在可执行策略：存在（事实，已实测）**。`src/agent_arena/v9/policies/world_subway.py::Map16Heuristic` 只读 `topology`/`train_route_directions`/`train_positions`/`train_goals`/`segment_capacities`/`node_capacities`/`pending_route_reservations`，在联合后继空间上做 BFS，每 tick 先为所有要动的车提交 `set_route`，再 `move_train`。结果：16 决策、6 tick、`GATE_OPENED`、`makespan_gap = 0`、`legal_reservation_rate = 10/10`。
- 策略需要的"额外知识"只有一条：结算时同节点/同区段不能同时被占。这一条可以从 Observation 的容量 1 与 `move_train` 的失败码推断（推断，不是隐藏真值）。
- **不标 `INTERFACE_BLOCKED`**：没有"不知道隐藏规则就会秒失败"的结构；失败来自规划和接口语义试错。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 说明 |
|---|---|---|---|
| Oracle（V6 solver，经适配器） | 17 | `GATE_OPENED` | 6 tick |
| `public_heuristic` | 16 | `GATE_OPENED` | 6 tick，gap 0 |
| 消融 `no_siding` | 6 | `DEADLOCK` | 复现 R0 因果 |
| `legal_random`（20 seed） | 20/20 = 30（用满） | 20/20 `decision_budget_reached` | 最终 tick 全部为 0；0 成功 |

`legal_random` 20 seed 的结果码合计 600 条：`INVALID_ACTION_SCHEMA` 332、`NO_PENDING_ROUTE` 128、`NETWORK_INSPECTED` 106、`INVALID_ROUTE` 34；`invalid_actions = 0`（形状都合法），`rejected_actions = 494`。

**判定：预算不够？否。** 30 个决策是可行解的 1.9 倍。随机基线 20/20 烧光预算却**一次 `move_train` 都没提交成功**（最终 tick 恒为 0），说明 MAP-16 的失败主要是"接口语义 + 规划"，不是预算。MiMo 三局分别只用了 6/24/15 个决策就终局，也证明预算不是瓶颈。

## 6. 指标

| 指标 | 计算事件 | 分母 | 缺失/截尾 | 三局结果 |
|---|---|---|---|---|
| `map16.committed_ticks` | 结果 ∈ {`MOVES_COMMITTED`,`GATE_OPENED`} 的决策数 | episode | 0 合法 | 2 / 3 / 3 |
| `map16.deadlock` | `terminal_reason == DEADLOCK` | episode | 无终局 → CENSORED | 1 / 0 / 0 |
| `map16.head_on_conflicts` | `result == HEAD_ON_SWAP` | episode | 0 合法 | 0 / 0 / 0 |
| `map16.legal_action_rate` | 非拒绝决策 / 提交决策 | 模型决策数 | 0 决策 → N/A | 1.0 / 0.583333 / 0.8 |
| `map16.legal_reservation_rate` | `ROUTE_RESERVED` / (`set_route`+`occupy_siding`) | 提交的预约动作数 | 0 预约 → N/A | 1.0 / 0.4 / 1.0 |
| `map16.makespan_gap` | `committed_ticks − BFS_optimum` | 成功终局 | 失败 → N/A；截尾 → CENSORED；无冻结最优 → UNAVAILABLE | N/A ×3 |
| `map16.node_capacity_conflicts` | `NODE_CAPACITY_CONFLICT` 次数 | episode | 0 合法 | 0 / 1 / 1 |
| `map16.section_conflicts` | `SECTION_RESERVATION_CONFLICT` 次数 | episode | 0 合法 | 0 / 0 / 0 |

- **未通关仍有意义的连续主指标**：`legal_reservation_rate` 是过程量（按已提交动作计算，不因截尾删除），三局分别 1.0/0.4/1.0，可以区分"预约被接受"与"预约被拒"。`committed_ticks` 也能区分"推进了 2/3/5 个 tick"。
- **三局 N/A 全在 `makespan_gap`**：原因是**真分母为 0**（三局都没有成功终局），不是投影口径问题。`deadlock` 在 R0 为 1，不是 N/A。
- **区分度**：Oracle gap 0 / 启发式 gap 0 → 同一水平；`legal_random` committed_ticks 0、reservation rate N/A；消融 `deadlock = 1`。四条策略里至少三种可区分（成功最优、成功但更慢、死锁、从未推进）。注意 `legal_reservation_rate` 的对抗性：R0 与 R2 都是 1.0 却是失败局，必须与 `makespan_gap`/`deadlock` 并列读。

## 7. 三次轨迹归因

### R0（6 决策，`DEADLOCK`）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"next_node":"X","tool":"set_route","train_id":"a"}` | `ROUTE_RESERVED` | `{"pending_route_reservations":{"a":"X"}}` |
| 2 | `{"tool":"move_train"}` | `MOVES_COMMITTED` | `{"occupied_nodes":["B","X"],"pending_route_reservations":{},"tick":1,"train_positions":{"a":"X","b":"B"}}` |
| 4 | `{"tool":"move_train"}` | `MOVES_COMMITTED` | `{"occupied_nodes":["B","M"],"pending_route_reservations":{},"tick":2,"train_positions":{"a":"M","b":"B"}}` |
| 6 | `{"tool":"move_train"}` | `DEADLOCK` | `{"occupied_nodes":["B","Y"],"pending_route_reservations":{},"terminal":true,"terminal_reason":"DEADLOCK","tick":3,"train_positions":{"a":"Y","b":"B"}}` |

- **首次偏离合理策略的可观测事件**：决策 5 `set_route a → Y`（决策 6 提交）。在 `(a=M, b=B)` 时，a 进 Y 会让两车都只剩"对方的节点"这一个出口，`(Y,B)` 无法安全完成；应当先把 b 送经 Y→M，或先让 a 进 D。
- **失败链**：只推进 a → 决策 1/2 到 X → 决策 3/4 到 M → 决策 5/6 到 Y → 死锁判定。
- **替代解释**：① 接口误导——prompt 没有说"死锁立即判负"，模型可能认为还能倒车；② 模型策略错误——全程没给 b 安排任何移动（b 从 tick 1 到终局一直停在 B）；③ 预算不足——不成立（只用了 6/30）。**首因是策略（E），次因是规则未公开（B）。**

### R1（24 决策，`NODE_CAPACITY_CONFLICT`）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 6 | `{"section_id":"MY","tool":"release_section","train_id":"b"}` | `INVALID_ROUTE` | `{}` |
| 11 | `{"next_node":"M","tool":"set_route","train_id":"a"}` | `INVALID_ROUTE` | `{}` |
| 22 | `{"next_node":"M","tool":"set_route","train_id":"b"}` | `ROUTE_RESERVED` | `{"pending_route_reservations":{"a":"M","b":"M"}}` |
| 24 | `{"tool":"move_train"}` | `NODE_CAPACITY_CONFLICT` | `{"terminal":true,"terminal_reason":"NODE_CAPACITY_CONFLICT"}` |

- **首次偏离**：决策 6。b 当时没有 pending 预约，`release_section` 直接 `INVALID_ROUTE`；随后决策 8/9/10 又连续三次 `occupy_siding b → D` 也 `INVALID_ROUTE`（b 在 Y，D 不与 Y 相邻）。这 4 个决策（6、8、9、10）全部没有推进 tick，只烧预算。
- **失败链**：tick 1 两车到 `(X,Y)` → a 预约 M 并前进到 M（决策 5/16）→ b 停在 Y 无法去 M（a 占着 M）→ 决策 17/18 让 a 进 D、决策 19 让 a 回 M（`pending {"a":"M"}`）→ 决策 22 又给 b 预约 M（**接口接受**，`pending {"a":"M","b":"M"}`）→ 决策 24 `move_train` 才终局。
- **替代解释**：① 接口误导——`release_section` 的名字暗示"释放占用中的区段"，实际只能撤销本车未提交的预约；`occupy_siding` 的名字暗示"任意车可占侧线"，实际前置是"目标必须是 D 且相邻"；② 计划错误——两车同时预约 M 在物理上必然冲突，模型没有检查；③ 预算不足——不成立（24/30）。**首因 C（接口语义误导 + 容量只在结算时校验），次因 E。**

### R2（15 决策，`NODE_CAPACITY_CONFLICT`）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 9 | `{"tool":"move_train"}` | `MOVES_COMMITTED` | `{"occupied_nodes":["D","Y"],"pending_route_reservations":{},"tick":3,"train_positions":{"a":"D","b":"Y"}}` |
| 14 | `{"next_node":"M","tool":"set_route","train_id":"b"}` | `ROUTE_RESERVED` | `{"pending_route_reservations":{"a":"M","b":"M"}}` |
| 15 | `{"tool":"move_train"}` | `NODE_CAPACITY_CONFLICT` | `{"terminal":true,"terminal_reason":"NODE_CAPACITY_CONFLICT"}` |

- **首次偏离**：决策 10（a 从 D 预约 M，正确）之后，决策 11/12/13 连续三次 `release_section b "MY"` → `INVALID_ROUTE`（b 没有预约），决策 14 又给 b 预约 M。真正的致命点是决策 14：a 的 M 预约还挂着。
- **失败链**：与 R1 同构——a 让行成功（决策 8/9 进 D、b 在 Y），但回程与 b 的前进都想用 M，且都在"同一 tick 的 pending 集合"里被接受，直到 `move_train` 才失败。
- **替代解释**：① 接口（C）：`pending_route_reservations` 明示了 `{"a":"M","b":"M"}`，但接口没有拒绝，模型看不到"这已经非法"；② 规划（E）：应当先 `release_section a M` 再让 b 进 M，或等 a 回 M 后再放 b；③ 预算（D）：不成立（15/30）。

**重复证据有限**：三局都栽在"M 只有一个泊位"上，R1 与 R2 的终局甚至完全相同（`pending {"a":"M","b":"M"}` → `NODE_CAPACITY_CONFLICT`）。n=3 只能说明"这是一个固定陷阱"，**不能**区分个体差异与接口设计造成的系统性偏差。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E** 策略规划错误（只推进 a、从不安排避让） | **B** 公开信息不足（死锁立即判负未公开） | 高 | 决策 5/6；`map16.py` 206–211 |
| R1 | **C** schema/接口误导（`release_section`、`occupy_siding` 语义未公开；节点容量不在预约阶段校验） | **E** 两车同时预约 M | 高 | 决策 6、8–10、22、24 |
| R2 | **C** 同上（同一 `release_section` 连错 3 次；`pending` 双预约被接受） | **E** 未撤销 a 的 M 预约 | 高 | 决策 11–15 |

补充：R0 的次因 B 是"规则未公开"，不是"必须知道隐藏真值"；R1/R2 的 C 也不是形状问题（三局 `invalid_actions` 均为 0），而是**语义**问题。

## 9. 标签

- **`MEASUREMENT_VALID`**：机制真实触发（3/3），且可区分四种策略——Oracle gap 0、启发式 gap 0、`legal_random` 从未推进（tick 0、reservation N/A）、消融 `no_siding` 死锁。
- **未标 `INTERFACE_BLOCKED`**：存在 16 决策的纯公开策略（§4），不满足"只有知道隐藏规则才能避免秒失败"。
- **未标 `RULE_DEFECT`**：规则本身自洽且可复算（28 态 / 6 tick 独立复现）。
- **未标 `BUDGET_BLOCKED`**：预算 30 是可行解的 1.9 倍。
- **未标 `METRIC_DEFECT`**：8 条指标均能从 Trace 复算；`makespan_gap` 的 N/A 是真分母 0。
- **未标 `CONSTRUCT_BYPASS`**：不存在绕过侧线的成功路径（主线是路径图，错车只能在 D）。
- 公开信息不足（B）与接口语义误导（C）确实存在，但它们是**失败分类**，不是"测量无效"的充分条件；对应修复见 §10。

## 10. 最小可证伪修复（无证据不修改）

**旧规则 / 旧公开信息**：规则不变；公开信息目前只有 Observation 字段 + 动作名，`本图机制` 退化为适配器 docstring。

**证据与根因**：3/3 失败都在"未公开的语义"上：死锁立即判负（R0）、`release_section` 只撤本车预约（R1 决策 6、R2 决策 11–13）、`occupy_siding` 只能对 D 且需相邻（R1 决策 8–10）、节点容量只在 `move_train` 校验（R1 决策 22/24、R2 决策 14/15）。

**候选 A（部分已由 V9 overlay 实现，只补公开信息，不改规则）**：在 `_VOCABULARY["MAP-16"]` 或 system prompt 中补 5 条事实：
1. 主线 A-X-M-Y-B 为单线，任一无向区段每 tick 至多一列车，禁止同 tick 对向交换；
2. D 是唯一的侧线泊位，两车必须在此错车；
3. `move_train` 原子提交全部 pending，结算后若不存在安全完成路径立即 `DEADLOCK`；
4. `release_section` 只撤销本车**尚未提交**的预约；
5. `set_route`/`occupy_siding` 在预约阶段不校验节点容量，容量冲突在 `move_train` 才判定并终局。
- **现状（事实）**：`src/agent_arena/v9/prompts.py::V9_PUBLIC_ADDENDA["MAP-16"]` 已实现第 4 条、第 5 条的后半（"两车同节点在 `move_train` 结算时冲突"）与 `occupy_siding` 的"仅 D 且相邻"；第 1、2、3 条以及"预约阶段不校验容量"的显式表述仍缺失。该 overlay 只作用于 `v9_fixed` 臂，V8 冻结的 `v8_compat` 臂不变。
- 预期变化：`legal_action_rate`、`legal_reservation_rate` 上升；`DEADLOCK` 仍可发生（规则不变），`makespan_gap` 仍只对成功局有定义。
- 能力构念影响：不改变"会车规划"构念，只去掉"猜接口语义"的噪声；难度会下降，需要在 Batch 6 用同图对照确认不是把题变成纯抄规则。
- 反例与回归风险：若补完 3 条后模型仍失败，说明失败来自搜索/规划而非信息；若成功率跳到 3/3，则本图的简单档区分度可能不足。另需注意：`v9_fixed` 与 `v8_compat` 的 prompt hash 不同，跨臂比较只能作前后对照，不能与 V8 90 局混算。

**候选 B（不推荐先做，需更强证据）**：把节点/侧线容量校验提前到 `set_route`，让 `pending {"a":"M","b":"M"}` 在预约时就 `INVALID_ROUTE`。
- 这会改变规则（新 `rule_hash`），旧 Trace 不可直接回放；
- 会把"计划错误"变成"接口拒绝"，削弱 `NODE_CAPACITY_CONFLICT` 与死锁构念，可能让本图退化成形状题。
- 只有在候选 A 实施后仍观察到系统性延迟硬失败，才考虑 B。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-16.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle（V6 solver） | `scenario_success` / `GATE_OPENED` | 17 | 6 tick |
| `legal_random`（20 seed） | 0 成功，20/20 `decision_budget_reached` | 30（全部用满） | 最终 tick 全 0；`committed_ticks` 0 |
| `public_heuristic` | `GATE_OPENED` | 16 | `committed_ticks` 6、`makespan_gap` 0、`legal_reservation_rate` 10/10 |
| 消融 `no_siding` | `DEADLOCK` | 6 | `deadlock` 1、`committed_ticks` 2 |

**独立复算（与 V7 extractor 不同实现）**：本图 §11 的复算写在策略模块里（`_successors` / `_first_step`），不读 `MAP16_OPTIMAL_MAKESPAN`。从公开 Observation 出发：

- 可达联合状态数 = **28**（与 `acceptance.md` 的"28 个可达无碰撞位置组合"一致）；
- `(A,B) → (B,A)` 最短 = **6** tick（与冻结常量 `MAP16_OPTIMAL_MAKESPAN["map16_l3_original"] = 6` 一致）；
- 启发式实际 `committed_ticks = 6` → `makespan_gap = 6 − 6 = 0`（与 extractor 输出一致）。

三项独立得到同一结论，`makespan_gap` 不是 extractor 自证。**无 `LOW_DISCRIMINATION`**：四条基线的 `committed_ticks`/`deadlock`/`legal_reservation_rate` 至少覆盖三种不同结果。

## 12. V9 状态

**`VALIDATED`（P1）**。

理由：机制、终局与指标都能从 Trace 与源码复算；公开策略 16 决策即可拿到 BFS 最优，消融能稳定复现死锁，因此这张图在"会车/死锁"构念上是有效的测量。P1 的原因是 V8 冻结条件下公开信息仍缺 3 条硬规则（单线同段禁止对向交换、死锁立即判负、D 是唯一侧线；V9 overlay 已补另外 2 条语义）。不修会让失败里混入"猜接口语义"的成分；这不需要改规则，只需补 prompt 文本，并在 Batch 6 复测。
