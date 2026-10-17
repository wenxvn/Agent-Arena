# MAP-22 审计：没有地图的森林（jungle / 简单，V4 适配图）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-22 / jungle / 简单 |
| condition | `history5_graph_memory`（V4 适配，`memory_enabled=true`） |
| `rule_hash` | `e856cec6daf4d388e89c2d239153cb5fbcb955de65c8d2ccd62753319f293856` |
| `scenario_hash` | `efc76acdc469af8fd965418396b2a549b2147300a33fdb3eab2c70b150151412` |
| `prompt_hash` | `5d1068396fb0e1c26a396afcae8d4cd7c42aef47f6dd7bee55fd8c4ccd80d704` |
| `metric_schema_hash` | `f0f6f77e4e0557f0ea1f479314f70b4dd167b84f3b137443addbc522178893ef` |
| `oracle_hash` | `388ae9bdf55001710afa6a7b6af76a6b7265f624dafd5e5b2815dee69b3e801d` |
| 决策预算 | 30（`BUDGETS["简单"]`）；环境 `move_budget=30`、`step_limit=160` |
| V8 三局 | 0/3 成功；R0/R1/R2 均 `decision_budget_reached`（`terminal_reason=None`），决策 30 / 30 / 30，schema 非法 0 |
| 移动步数（三局） | 13 / 11 / 16（`movement_steps`，上限 30） |
| 费用（正式行） | 0.02321652 / 0.02036660 / 0.01894224 CNY |
| 证据包 | `runs/v9/evidence/MAP-22.json`、`docs/v9/run-index.csv`（MAP-22 三行） |
| 规则资料 | `docs/v8/maps/MAP-22-final.md`、`worlds/v4/MAP-22/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v4/map22.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`src/agent_arena/v6/scenes.py::map22_l3_original`、`src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-22"]` |
| 基线 | `runs/v9/baselines/MAP-22.json` |
| 运行 commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674`（`run-index.csv`）；定稿 commit `039e25ce6503871ceb31184e85c9265451ee7486` |

**注意（本图专属）**：V8 运行的不是 V4 的 `NODES`（`CAMP_LANTERN_RING`…），而是 V6 场景 `map22_l3_original` 用 `_forest()` 生成的同构实例（`A_SIGN`…/`A_silhouette`…，`src/agent_arena/v6/scenes.py:21-31,298-323`）。几何相同（12 节点 / 15 边 / 最优往返 8），但**路标命名与"粗形可辨性"设计全部被替换**：V4 让 B/E/H/K 共享 `three_pronged_forkpost`、必须靠细部特征区分；V6 每个节点都有唯一 `X_silhouette`，节点身份从第一帧就完全公开。这条差异决定了本图实际测到的东西（见 §3、§9）。

## 1. 能力构念

这张图想测的是：**Agent 能否把"亲历的局部路标 + 出口方位"积累成一份可返程的拓扑记忆，并在步数上限内走到遗迹 L 再回到营地 A**。

- 成功行为：走到 L（`target_visited=true`）后**逐边走回 A**，且 `movement_steps ≤ 30`，终局 `RETURNED_TO_CAMP_WITH_RUIN_RECORD`（`scenario_v4/map22.py:193-206`）。
- 明确反例：只在已访问节点之间来回巡逻（MiMo R1/R2）；记住节点却不记边，导致 journal 里有页面但无法回答"哪个方位通向哪里"（R2 的 6 条事实全是 `node_page`）。
- 本图在 jungle 三图中的位置（只写本图）：图**永远不变**，难点是"记忆 + 返程"；MAP-23 的图静态但难点是信息价值，MAP-24 的图会在局中坍塌。

## 2. 机制与因果链

初始 Observation 原文（`runs/v9/evidence/MAP-22.json`，rep 0）：

```json
{"active_goal_marker":"L_SIGN","agent_authored_memory_journal":[],
 "current_coarse_silhouette":"A_silhouette","inspected_current_sign_detail":null,
 "last_action_result":"READY","map_id":"MAP-22","movement_steps":0,
 "terminal":false,"terminal_reason":null,"visible_exit_bearings":["NE","SE"]}
```

因果链：

1. **起始**：A 只公开 `A_silhouette` 与 `["NE","SE"]`；邻接表、邻居路标、L 的位置全部隐藏。
2. **必需观察**：`observe_signpost` 才给出 `sign_id`（`A_SIGN`）与 `distinctive_feature`（`A_feature`），且只在**当前节点、当次检查后**有效（`last_inspected_node == node`，`map22.py:146-152`）。
3. **关键决策**：`write_memory` 只能写两类事实——`node_page`（当前已检查节点 + 当前出口方位）与 `traversed_edge_page`（**仅最近一次移动**的 from/bearing/to/反向方位，`map22.py:227-246`）。写边必须在移动后的下一次决策前完成，否则该窗口永久丢失。
4. **立即后果**：`move` 只接受当前 `visible_exit_bearings`；非法方位返回 `INVALID_BEARING` 且不推进 `movement_steps`，但消耗一个决策。踩到 L 时置 `target_visited`；`movement_steps` 达 30 立即 `STEP_LIMIT_REACHED`。
5. **终局**：`target_visited && node==A && movement_steps<=30` → 成功；否则决策预算或步数上限截断。

**可绕过核心机制的动作**：

1. **`write_memory` 完全可选**。成功判定只看 `target_visited / node / movement_steps`，从不读取 journal。本批 `no_memory_write`（同一 DFS 导航、0 次写记忆）**12 个决策成功**（`path_gap=4`），证明记忆机制不是通关必要条件。
2. **节点身份免费**。`current_coarse_silhouette` 在本实例里就是 `A_silhouette…L_silhouette`，与 `active_goal_marker="L_SIGN"` 前缀一致，因此"是否到达目标"可用公开字符串直接判断，`check_goal` 也可省（三局从未调用 `check_goal`）。
3. **`return_to_camp` 不移动**。它只把 `active_goal` 改回营地路标（`map22.py:214-224`），成功仍要求 `node==A`；名字暗示"自动返营"，实际返回 `CAMP_SET_AS_GOAL`。三局都没有调用它，因此这条误导未在三局中被触发，但它是公开动作集里的一个陷阱。

**机制是否在三条真实轨迹中实际触发**：**形式上触发，功能上没有**。

- `MEMORY_WRITTEN` 三局分别 7 / 7 / 6 次（`memory_facts_written`=7/7/6），机制入口确实被使用。
- 但 R1、R2 的 journal **一条 `traversed_edge_page` 都没有**（R1 7 条、R2 6 条全是 `node_page`）。`node_page` 只记录 `exit_bearings`，不记录"该方位通向哪个节点"，所以 journal 无法重建任何一条边；R1 结束时停在 `J_silhouette`（`movement_steps=11`）、R2 停在 `C_silhouette`（16），两局都没到过 L。
- R0 写了 2 条边事实（`A_SIGN→B_SIGN`、`B_SIGN→D_SIGN`），另有 1 次 `MEMORY_FACT_NOT_OBSERVED`（决策 10）。

**触发所需的最小动作数**：一条节点页 = 2（`observe_signpost` + `write_memory`）；一条边页 = 2（`move` + `write_memory`，`sign_id` 若已由观察或命名约定确定）或 3（每个新节点都要先 `observe`）；通关本身 = 8 次 `move`（A-C-F-I-L-A）。**若通关同时要每个新节点留节点页、每条边留边页，实测需要 37 个决策；只留边页需要 24**（§5、§11）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `current_coarse_silhouette` | 是 | 每步 | 是：在本实例里等价于节点 ID（`A_silhouette`…），身份识别被免费化 |
| `visible_exit_bearings` | 是 | 每步，仅当前节点 | 是：足以逐步探索 |
| `inspected_current_sign_detail`（`sign_id` + `distinctive_feature`） | 是 | 仅 `observe_signpost` 后、且在当前节点 | 是；但 `sign_id` 是写记忆的必需值，必须先观察 |
| `active_goal_marker`（初始 `L_SIGN`；`return_to_camp` 后变 `A_SIGN`） | 是 | 每步 | 是：可直接与 silhouette 前缀比对 |
| `agent_authored_memory_journal` | 是 | 写后永久 | 是，但只含自己写进去的东西 |
| `movement_steps` | 是 | 每步 | 是 |
| **胜利条件**（先到 L、再物理回 A） | **否** | 不可见 | **否**：V4 的 `terminal_success` 只写在 `map_spec.yaml`，V8 prompt 没有任何一句说明 |
| **30 步移动上限** | **否** | 不可见 | prompt 只写"本局最多 30 个决策"，未说 `movement_steps` 另有 30 上限 |
| **`write_memory` 的地面约束**（边页仅"最近一次移动"有效） | 部分 | 词表写"只写亲历的页面" | 部分：能推断"要写亲历的"，但看不出"只有一步窗口" |
| **反向方位**（`arrival_reverse_bearing`） | 否 | 不可见 | 本实例 15 条边全部是反方位，可凭几何猜对；但公开文本没有承诺 |
| 图邻接表 / L 的坐标 / `target_visited` | 否（hidden `judge_state`） | 不可见 | 不用于公开策略 |
| **"本图机制"文案** | 是，但内容是 **`"A V4 environment behind the V8 public contract."`** | 每步（system prompt） | **否**：这是适配类的实现注释，不含任何玩法信息 |
| condition `history5_graph_memory` 的作用 | 部分（prompt 一句"允许使用 Agent-owned 图记忆"） | 每步 | 只影响 `write_memory` 是否被允许；V9 没有 `history5` 对照臂，无法测量该条件的增益 |
| Oracle 路径 | 否 | 不可见 | 不用于公开策略 |

**适配层带来的两个本图专属缺陷**：

1. **公开 prompt 缺目标文本**。`system_prompt` 在 Observation 没有 `goal` 字段时回退到 `type(environment).__doc__` 的首行（`v8/prompts.py:334-336,366-372`），而 `V4MapAdapter` 的 docstring 是 `"A V4 environment behind the V8 public contract."`。实跑生成的 system prompt 因此是："本图机制：A V4 environment behind the V8 public contract."——**同批 MAP-23/24 都有完整目标句，只有 6 张 V4 适配图没有**。
2. **`condition` 只有单臂**。`history5_graph_memory` → `memory_enabled=True`；`history5` → `write_memory` 返回 `MEMORY_DISABLED`（不终局）。V8 只跑前者，所以"图记忆条件"在 V9 没有任何对照，不能归因。

## 4. 可解性与可观察性

- Oracle：1 条（`MAP-22-solver-success`，来自 V6 独立求解器 `map22_l3_original`），**8 个动作**，`ok=true`，终态 `RETURNED_TO_CAMP_WITH_RUIN_RECORD`（`runs/v9/baselines/MAP-22.json`）。
- 手算 fixture 2 条：`illegal-bearing-then-solve`（1+8 步）、`exactly-30-moves`（30 步，`path_gap=22`，`repeated_public_edge_rate=0.3`）。
- **仅凭公开信息是否存在可执行策略：存在，而且有两条**。
  - 带记忆的路线：`Map22Heuristic` **24 个决策成功**——决策 1 `observe_signpost`（核对 `<X>_silhouette ↔ <X>_SIGN` 的公开命名约定），之后每次移动后写一条 `traversed_edge_page`，共 **11 条边事实**；终局 `RETURNED_TO_CAMP_WITH_RUIN_RECORD`，`path_gap=4`、`memory_grounding_violations=0`、`illegal_bearing_actions=0`（`runs/v9/baselines/MAP-22.json`）。它真的用上了记忆：前 7 步走到 L，返程 5 步（L→K→H→E→B→A）全部走在它自己写进 journal 的边上。
  - 不带记忆的路线：`Map22NoMemoryWrite` **12 个决策成功**，同样的 DFS 导航、0 次写记忆，`path_gap=4`。
- 记忆的**成本边界**（本批实测）：只写边页 = 24 个决策（1 次观察 + 12 次移动 + 11 次写边）；若同时写节点页（每新节点 `observe` + `write` 两条），同一导航需要 **37 个决策**（`--budget 38` 通关、`--budget 34` 不通关）。也就是说 30 个决策**够"边记忆"、不够"节点页 + 边页"的完整记账**。
- 判定：**不是 `INTERFACE_BLOCKED`（移动与观察接口自洽、公开策略 24 / 12 步通关），也不是无条件的 `BUDGET_BLOCKED`**；`BUDGET_BLOCKED` 只对"每个节点都留节点页"的记账方式成立。构念层面的问题仍是 `CONSTRUCT_BYPASS`（不留记忆 12 步通关）。另外公开 prompt 缺胜利条件属于 B/C 类信息缺陷，见 §8/§10。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 8（`MAP-22-solver-success`，`ok=true`） |
| 地图自身移动上限 | `move_budget=30`（`scenario_v4/map22.py:103`） |
| 决策预算 | 30（`BUDGETS["简单"]`）——**与移动上限同值** |
| `legal_random` × 20 | 0 成功；20/20 `decision_budget_reached`，决策 30；schema 非法 **136** 次，语义被拒 93 次 |
| `public_heuristic`（只写边页） | **24 决策通关**（`movement_steps=12`，`memory_facts_written=11`，`path_gap=4`） |
| 同一导航 + 节点页 + 边页（本批迭代中实测） | 30 决策**未通关**；`--budget 38` 才通关，需 **37** 个决策（facts 18） |
| 消融 `no_memory_write` | **12 个决策通关**（`path_gap=4`） |
| V8 三局 | 30 / 30 / 30，全部耗尽；移动仅 13 / 11 / 16 |

判定：**"预算不够"只对更重的记账方式成立，"模型没做对"才是三局的直接原因**。

- 纯导航层：30 个决策绰绰有余（12 步可解，Oracle 8 步）。
- 边记忆层：**够用**。1 次观察 + 12 次移动 + 11 次写边 = 24，留 6 个决策余量。
- 节点页 + 边页层：**不够**。节点页要"观察 + 写"两个决策，而这条路线经过 5 个以上新节点，实测把总量推到 37 > 30。
- 结构原因：V4 的 30 是**移动步数**上限，V8 的 30 是**全部决策**上限。任何 `observe_signpost` / `write_memory` / `check_goal` 都从移动额度里扣，于是"每个节点都记笔记"的 Agent 实际只有约 10–16 步可用（三局正是 13/11/16），而找到 L 再回到 A 至少 11 步。
- 副产品：`STEP_LIMIT_REACHED` 只有在"30 个决策全是移动"时才可能触发，因此 V8 里几乎不可达；三局的失败码只有 `CENSORED`（决策预算），地图自带的失败码没有被观测到。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map22.return_success` | primary | `terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD` | episode | 无终局 → CENSORED |
| `map22.path_gap` | primary | `movement_steps − BFS_optimal(8)` | 成功返程的 episode | 未成功 → N/A；截尾 → CENSORED |
| `map22.memory_facts_written` | diagnostic | `len(final journal)` | episode | 无 journal → UNAVAILABLE |
| `map22.repeated_public_edge_rate` | diagnostic | 同一条**有向**边第二次及以后 / 可解析移动数 | 可解析移动数 | 0 → N/A |
| `map22.illegal_bearing_actions` | guardrail | `count(result==INVALID_BEARING)` | episode | 0 次合法为 0 |
| `map22.memory_grounding_violations` | guardrail | `count(result==MEMORY_FACT_NOT_OBSERVED)` | episode | 0 次合法为 0 |
| `map22.legal_action_rate` | diagnostic | 被接受决策 / 提交决策 | 决策数 | 0 决策 → N/A |

- **未通关仍有意义的连续指标：有，但很弱**。`legal_action_rate`（0.933/1.0/1.0）、`repeated_public_edge_rate`（1/13=0.0769、1/11=0.0909、4/16=0.25）、`memory_facts_written`（7/7/6）三局都有值，可以区分"乱撞"与"有纪律地撞"。`illegal_bearing_actions`=1/0/0、`memory_grounding_violations`=1/0/0 只有 R0 非零。
- **三局 N/A**：只有 `path_gap`（`not_applicable` 3/3）。**这是指标卡自身的缺失规则（"未成功 → N/A"），不是投影口径错误**。`docs/v9/data-integrity.md` §4.1 把 MAP-22 列入"预算截尾被投影成 N/A"的例子，本图**不成立**：即使给 300 个决策，只要没成功，`path_gap` 按定义仍是 N/A。建议把 MAP-22 从该候选名单里移出。（其余 6 条指标三局全部 `valid`。）
- **区分度**：
  - `return_success` + `path_gap` 能区分可解策略（`public_heuristic` 24 决策、`no_memory_write` 12 决策，均 1 / 4）与三局 MiMo（0 / N/A）——但区分的是"能不能通关"，不是"记忆好不好"。
  - `memory_facts_written` 能区分 7 / 7 / 6 与 `no_memory_write` 的 0，但**它只数条数，不检查内容**：R1 的 7 条全是节点页，对导航零贡献，指标却显示"记忆更丰富"。
  - `repeated_public_edge_rate` 只统计**同一有向边重复**；"走过去再原路退回"（A→B→A）算两条不同有向边，记 0。R1 的 11 步里 6 步是即时折返，指标只报 1/11。记为 **`LOW_DISCRIMINATION` + `METRIC_DEFECT` 候选**（见 §10）。
  - `legal_random` 的 136 次 schema 非法与三局的 0 次，说明 `legal_action_rate` 能识别"动作格式失败"这一层。

## 7. 三次轨迹归因

### R0 `V8-MAP-22-R0-20261017T095222Z-68e884e9`（30 决策，13 步）

- 决策 1：`{"tool":"observe_signpost"}` → `SIGNPOST_OBSERVED`；观察变化 `{"inspected_current_sign_detail":{"distinctive_feature":"A_feature","sign_id":"A_SIGN"}}`。
- 决策 3：`{"bearing":"NE","tool":"move"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_coarse_silhouette":"B_silhouette","inspected_current_sign_detail":null,"movement_steps":1,"visible_exit_bearings":["E","NE","SW"]}`。
- 决策 10：`{"facts":[{"arrival_reverse_bearing":"SW","departure_bearing":"NE","fact_type":"traversed_edge_page","from_sign_id":"A_SIGN","to_sign_id":"D_SIGN"}],"tool":"write_memory"}` → **`MEMORY_FACT_NOT_OBSERVED`**；观察变化 `{}`。它想补记"上一段 A→D"，但实际刚走的是 B→D；边页只在最近一次移动有效。
- 决策 12：`{"bearing":"SW","tool":"move"}` → `MOVE_SUCCEEDED`；`{"movement_steps":3,...}`（回到 B）。此后进入 B→E→B→A→B→A→C→A→C 的折返。
- 决策 27：`{"bearing":"E","tool":"move"}`（此时在 F，出口只有 `["N","NE","W"]`）→ **`INVALID_BEARING`**；观察变化 `{}`。
- 决策 30：`{"bearing":"N","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"E_silhouette","movement_steps":13}`。

**首次偏离合理策略的可观测事件：决策 10**。它刚刚从 B 走到 D（决策 7），却在决策 10 试图把边记成 A→D——说明它在"用脑子里的旧状态"而不是"用最近一次移动"写记忆；这一次失败也让它丢掉了 B→D 这条边（下一次机会已被决策 12 的移动覆盖）。

**失败链**：每个新节点花 3 个决策（观察 + 节点页 + 边页）→ 每步平均 2.3 个决策 → 30 决策只换来 13 步；探索方式是"深度 1 折返"（B→E→B、A→B→A、C→A→C），没有前沿列表；决策 27 的非法方位说明它没读 `visible_exit_bearings` → 到 30 决策时只到 E，离 L 还有 3 条边。

**替代解释**：预算（部分成立：完整记账需 37 个决策，但只写边页只需 24，所以"预算不够"不足以解释三局只走到 11–16 步）；接口误导次之（边页一步窗口、prompt 无目标）；规则缺陷不成立（Oracle 8 步、公开策略 24 与 12 步均成功）。

### R1 `V8-MAP-22-R1-20261017T095410Z-5d7125fa`（30 决策，11 步）

- 决策 3：`{"bearing":"NE","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"B_silhouette","movement_steps":1,"visible_exit_bearings":["E","NE","SW"]}`。
- 决策 6：`{"bearing":"SW","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"A_silhouette","movement_steps":2,...}`（刚进 B 就折返）。
- 决策 20：`{"bearing":"E","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"E_silhouette","movement_steps":8,"visible_exit_bearings":["E","S","W"]}`。
- 决策 23：`{"bearing":"E","tool":"move"}` → `MOVE_SUCCEEDED`；观察变化只有 `{"current_coarse_silhouette":"H_silhouette","movement_steps":9}`——**出口方位与上一节点相同（`E,S,W`），因此差分里没有该字段**；这正好说明"方位集合"本身不携带节点身份，只有 silhouette 携带。
- 决策 30：`{"facts":[{"exit_bearings":["S","W"],"fact_type":"node_page","sign_id":"J_SIGN"}],"tool":"write_memory"}` → `MEMORY_WRITTEN`；`movement_steps=11`。终局停在 J，journal 7 条**全是**节点页。

**首次偏离：决策 6**。它已经走到 B（新节点、3 个未试出口 E/NE/SW），却在下一决策用 `SW` 直接退回 A，把 B 的其余两条边永久留作"未探索"。此后它反复 A↔B、A↔C，只有 11 步、0 条边事实。

**失败链**：折返式巡逻取代前沿探索 → 边事实为 0，journal 无法支持任何路径规划 → 30 决策内只覆盖 A/B/C/D/E/H/K/J 中的 8 个节点，未到 L。

**替代解释**：预算不足（否，纯导航 12 决策可解）；记忆机制本身难以使用（是，写边需要 3 个决策且只有一步窗口）；模型把"记录节点"当成目标（是，7 条节点页 0 条边页）。

### R2 `V8-MAP-22-R2-20261017T095608Z-0f0e3e48`（30 决策，16 步）

- 决策 10：`{"bearing":"E","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"F_silhouette","movement_steps":4,"visible_exit_bearings":["N","NE","W"]}`。
- 决策 13：`{"bearing":"N","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"E_silhouette","movement_steps":5}`。
- 决策 29：`{"bearing":"NW","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"A_silhouette","movement_steps":15}`。
- 决策 30：`{"bearing":"SE","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_coarse_silhouette":"C_silhouette","movement_steps":16}`。

**首次偏离：决策 13**。它到了 F（新节点，出口 N/NE/W，NE 通向 I→L 的最短路），却选择 `N` 回到 E，再由 E→B→A，把整条"最短成功分支"扔掉；随后 16 步里 A、C 各被访问 4 次（`repeated_public_edge_rate=4/16`）。

**失败链**：无前沿记忆 → 反复回 A 重启 → 16 步覆盖 6 个节点，未到 L；journal 6 条全节点页，0 条边页。

**重复证据有限**：三局都没有调用 `check_goal` / `return_to_camp`，都以"观察 + 写节点页"开局，都在 A/B/C 附近折返；n=3 且 seed=0 固定，**不能区分个体策略差异与固定陷阱**。可区分的是移动量：13 / 11 / 16，说明并非同一条轨迹的三次复制。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E**（折返巡逻 + 不读 `visible_exit_bearings` 的非法移动） | D（写记忆+观察吃掉 17/30 个决策）、C（边页一步窗口；prompt 无目标） | 高 | 决策 10、12、27、30 |
| R1 | **E**（进 B 立刻退回，边事实 0 条） | D（30 决策只剩 11 步）、C（同左） | 高 | 决策 3、6、20、23、30 |
| R2 | **E**（放弃 F→I 的最短分支，16 步循环） | D、C | 高 | 决策 10、13、29、30 |

- **D（决策预算/horizon）**：本图的结构性事实——30 个决策 = 30 步移动上限，任何记账动作都挤占移动；"每个节点写节点页 + 每条边写边页"的记账方式需要 37 个决策（只写边页需要 24，够用）。它不是 R0/R1/R2 的**首因**（因为即使给 30 步纯移动，三局那种折返也不会到 L），但它保证"修好探索但保留完整记账"仍然过不了。
- **C（schema/接口误导）**：三处——(1) prompt 的"本图机制"是适配层注释；(2) 胜利条件（先到 L 再回 A）与 30 步移动上限未公开；(3) 边页只认"最近一次移动"，而 R0 决策 10 正是在这条上翻车。注意 `write_memory` 的 **facts schema 本身已修好**（V8 已公开 `node_page` / `traversed_edge_page` 的精确字段，三局 0 次 schema 拒绝），所以 C 不是"格式不可知"，而是"语义窗口与目标不可知"。
- **B（公开信息不足）**：仅就"胜利条件"成立，与 C 重叠，合并计入 C。
- **A / F / G / H / I**：A 不成立（Oracle、公开策略均成功）；F 不成立（本图无资源账）；G 不成立（不是"记住了却用错"，而是"根本没记边"）；H 不成立（无 provider 错误）；I 成立（n=3、seed=0）。

## 9. 标签

- **`BUDGET_BLOCKED`（限定范围：节点页 + 边页的完整记账）**：同一导航只写边页 24 个决策通关（预算 30 够），但把每个新节点的节点页也算进"拓扑记忆"后需要 37 个决策（`--budget 38` 通关、`--budget 34` 不通关）。V4 的 30 是移动步数，V8 的 30 是全部决策；两者同值，所以记账动作直接吃掉移动额度。
- **`CONSTRUCT_BYPASS`**：`no_memory_write` 12 个决策通关、`path_gap=4`、`memory_facts_written=0`——记忆不是通关必要条件。且本实例把节点身份编码进 `current_coarse_silhouette`，V4 设计的"四个三叉桩要靠细部特征区分"在 V8 运行时不存在。本图在 V8 里测到的是"带记账开销的导航"，不是"拓扑记忆"。
- **`INTERFACE_BLOCKED`（限定范围）**：仅指"公开目标文本缺失"——system prompt 的机制句是 `"A V4 environment behind the V8 public contract."`，且没有任何字段说明必须先到 L 再物理回 A、`movement_steps` 另有 30 上限。它不阻止移动探索，但阻止 Agent 知道自己在追什么。
- **`METRIC_DEFECT`（候选，低严重度）**：`repeated_public_edge_rate` 按有向边计，"走一步原路退回"记 0（R1 的 6 次即时折返 → 1/11），无法反映本图最主要的浪费形态；`memory_facts_written` 只计条数不计内容，R1 的 7 条节点页对导航零贡献却被读成"记忆更丰富"。
- （不选 `MEASUREMENT_VALID`：规则与失败判定本身可复算，但 0/3 既不能归因于"拓扑记忆"能力（记忆可完全绕过），两个 primary 指标也区分不了记忆内容质量，见 §6/§10。不选 `RULE_DEFECT`：规则与 Oracle 自洽，三局没有任何规则异常。）

## 10. 最小可证伪修复（无证据不修改）

**旧规则/旧公开信息**：

1. `V4MapAdapter` 的 docstring 被当成"本图机制"（`v8/prompts.py:334-336`）；
2. MAP-22 的 Observation 没有 `goal` 字段，胜利条件与 30 步移动上限不在公开面；
3. 决策预算 30 = 移动上限 30，二者语义不同却同值；
4. `write_memory` 的边页只在"最近一次移动"后有效，且公开文本只说"只写亲历的页面"。

**证据与根因**：节点页 + 边页的记账方式需要 37 个决策（`--budget 38` 通关、`--budget 34` 不通关），只写边页只需 24；`no_memory_write` 12 个决策成功；三局 13/11/16 步、0–2 条边事实；R0 决策 10 的 `MEMORY_FACT_NOT_OBSERVED`。

**候选 A（首选，只补公开信息，不改规则）**：给 `V4MapAdapter` 增加 `goal` 属性/字段，让 MAP-22 的 system prompt 出现 V4 设计原句，例如"先走到三重拱遗迹，再沿原路返回营地；移动步数上限 30，观察与写记忆也占用决策名额"。预期：模型不再把"写节点页"当成目标；`return_to_camp` 的误导也被同一句话消解。能力构念不变。

**候选 B（对齐预算/记账语义，需主控 DCR）**：只写边页时 30 个决策够用（24），所以**不建议无条件加预算**。只有当设计坚持"每个节点都要留节点页"时才需要把预算提到 ≥37（或把 `write_memory` 设为不消耗决策的附注动作）。判断依据是可复算的：边页版 24、节点+边版 37。

**候选 C（可选，收紧旁路）**：若要真的测"拓扑记忆"，需要让节点身份不能直接从 `current_coarse_silhouette` 读出（恢复 V4 的"B/E/H/K 同为三叉桩"），并让通关判定要求 journal 中至少含一条覆盖实际路线的 `traversed_edge_page`。这会改变 `rule_hash`，属于规则修改，必须走 DCR 并且旧 Trace 不可直接回放。

**预期变化**：A 只影响 prompt 文本与 `prompt_hash`；B 影响 `decision_budget` 与预算 hash；C 影响 `rule_hash` 与所有指标的分母。三者不能同时上，否则无法归因。

**反例与回归风险**：

- 若只做 B 不做 A，模型仍不知道要返营，只会把多出的 16 个决策用在折返上（R1/R2 的行为支持这一预测）。
- 若只做 A 不做 B，`no_memory_write` 仍会 12 步通关，`CONSTRUCT_BYPASS` 不变。
- 任何 `prompt_hash` / `rule_hash` 变更都会让 V8 的 90 局不可与新版本直接比较，必须新开 run_id 与新账本。
- 候选 C 会让 MAP-22 从"简单"变成实际更难的地图，可能压到 0 成功；在 n=3、seed=0 下无法区分"难"与"坏"。

**若无需修改**：不成立——"节点页 + 边页"需要 37 > 30 是可复算的硬事实，prompt 缺目标也是可逐字引用的硬事实。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-22.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `MAP-22-solver-success` | `scenario_success` / `RETURNED_TO_CAMP_WITH_RUIN_RECORD` | 8 | ok=true |
| `legal_random` × 20 | 0 成功，20/20 `decision_budget_reached` | 30 | schema 非法 136、语义被拒 93 |
| `public_heuristic`（只写边页，seed 0） | **`scenario_success`** | 24 | moves 12、facts 11、gap 4、repeated 0/12、legal 24/24 |
| 同一导航 + 节点页 + 边页（本批迭代实测） | 30 决策未通关；`--budget 38` 用 37 决策通关 | 30 / 37 | moves 8 / 12、facts 15 / 18 |
| 消融 `no_memory_write`（seed 0） | **成功** | 12 | moves 12、facts 0、gap 4、repeated 0/12 |
| V8 三局 MiMo | 0/3 | 30/30/30 | moves 13/11/16；facts 7/7/6；R0 illegal 1 + grounding 1 |

**独立复算 1（`path_gap`，手工 BFS）**：按 `map_spec.yaml` 的 15 条双向边，A→L 最短为 A-C-F-I-L（4 步），L→A 原路返回 4 步，合计 **8**；`public_heuristic` 的动作序列有 12 次 `MOVE_SUCCEEDED`（A→B→E→H→K→J→K→L→K→H→E→B→A），故 `path_gap = 12 − 8 = 4`，与 extractor 一致。`no_memory_write` 走同一条 12 步路线，`gap=4`，也一致。

**独立复算 2（`repeated_public_edge_rate`）**：`public_heuristic` 的 12 条有向边为 A→B、B→E、E→H、H→K、K→J、J→K、K→L、L→K、K→H、H→E、E→B、B→A，**两两不同**，故 0/12；与 extractor 的 `{"numerator":0,"denominator":12}` 逐位一致。这也暴露了口径问题：同一条**无向**边被走了两次（K↔J、K↔L、K↔H、H↔E、E↔B、B↔A），指标仍报 0。

**独立复算 3（`memory_facts_written` / `memory_grounding_violations`）**：24 个决策 = 1 次 `observe_signpost` + 12 次 `move` + **11 次 `write_memory`**；第 12 次移动直接触发成功，策略没有机会写第 12 条边，故 journal 长度 11，与 judge 的 `memory_facts_written=11` 一致。11 条全部 `MEMORY_WRITTEN`，无 `MEMORY_FACT_NOT_OBSERVED`，故 grounding violations = 0（R0 的 1 来自它自己把边记错端点，见 §7）。

**区分度**：`return_success`/`path_gap` 能区分"有解策略"（1 / 4）与三局 MiMo（0 / N/A）；`memory_facts_written` 能区分 0 / 11 / 7，但**不能区分内容质量**——R1 的 7 条全是节点页、对导航零贡献，指标却显示"记得更多"。`repeated_public_edge_rate` 对即时折返不敏感（6 次折返记 0）。记为 **`LOW_DISCRIMINATION`（记忆质量维度）**。

**独立复算 4（V8 R0 的 `memory_grounding_violations`）**：R0 的 30 条决策里只有决策 10 返回 `MEMORY_FACT_NOT_OBSERVED`（它把刚走的 B→D 记成了 A→D），其余 `write_memory` 全部 `MEMORY_WRITTEN`，故 1；R1/R2 各 0。与 judge 输出一致。

## 12. V9 状态

**`NEEDS_REDESIGN`（P0）**。理由：0/3 不是"模型太差"这一条能解释的——同一张图上公开策略 24 个决策就能通关（只写边页的记忆策略），不写记忆只要 12 个决策；而按设计意图"每个节点都留页"的记账方式需要 37 个决策、正式预算只有 30。更关键的是 system prompt 把"本图机制"写成了适配层注释（`"A V4 environment behind the V8 public contract."`），胜利条件完全不在公开面，且本实例让节点身份直接从 silhouette 可读、记忆因此不是通关必要条件。在补公开目标文本、明确"要记到什么粒度"之前，MAP-22 的 0/3 不能解释为"拓扑记忆能力不足"。
