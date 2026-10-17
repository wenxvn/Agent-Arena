# MAP-22｜丛林｜简单｜没有地图的森林

```yaml
map_id: MAP-22
world: jungle
nominal_level: 简单
capability_primary: local_navigation_return_memory
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 79b5501b83d09858a80a1d7a89ca96080440e1a121885125311d27cfd3c93c36
source_design_hash: a228b2cc8418fe2701be00e8565d9c889b7f522d936efd675e37f120cfdd791b
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“局部标识 → 可返回拓扑”的记忆构建。营地 A 与目标遗迹 L 之间是固定 12 节点、15 条无向边的图（循环秩 4）；Observation 只给当前路标的粗形与出口方位（NE/SE/…），**不给邻居名称、不给完整邻接表**。B/E/H/K 都是相似的三叉桩，必须靠桩脚缺口/横刻/根纹/苔楔区分。Agent 要自己 `write_memory` 记录“已观察的节点卡或刚走过的边”，再用这些记录回到 A。核心不是“走最短”，而是**把走过的边变成可回放的返回路径**。

## 2. 真实规则字段

- 图：12 节点、15 条无向边，循环秩 `15−12+1=4`；每步只能走当前路标列出的一个出口，移动成本恒 1；无随机事件。
- `A→L` 唯一最短路 `A-C-F-I-L`（4 步）；另一条内部不相交备选 `A-B-E-H-K-L`（5 步）；往返最短 8 步（仅离线比较用）。
- 动作：`move(bearing)`、`inspect_sign`、`write_memory(fact)`、`return_to_camp`（只改目标为 A，不规划、不移动）。
- 记忆：写一条已观察证据，最多 32 条；可写当前节点标记/出口卡，或**最近实际走过**的边及两端方向卡；不能写未来节点或未走过的边，违规 → `MEMORY_FACT_NOT_OBSERVED`。
- 步数预算 30；成功条件 `RETURNED_TO_CAMP_WITH_RUIN_RECORD`（先到 L 见到遗迹记录，再回 A）。
- 失败：`STEP_LIMIT_REACHED`；非法方位 → `INVALID_BEARING`。
- 公开：当前位置、粗形、可见出口方位、当前目标、记忆 journal、步数、终止原因；**不公开** `target_node` 与完整邻接。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map22.return_success` | primary | `1[terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD]` | 0/1 / 高 | episode | 无终局 → CENSORED；截尾值仍 0 但标 CENSORED |
| `map22.path_gap` | primary | `movement_steps − 同实例 BFS 最优` | moves / 低 | 成功返程 | 未成功 → N/A；无冻结最优 → UNAVAILABLE；截尾 → CENSORED |
| `map22.repeated_public_edge_rate` | diagnostic | 重复**有向**公开边 / 可解析有向移动数 | 比例 / 低 | 两端签名可解析的移动数；0 → N/A | 按已发生移动算 |
| `map22.memory_grounding_violations` | guardrail | `count(MEMORY_FACT_NOT_OBSERVED)` | 次 / 低 | episode | 0 合法 |
| `map22.illegal_bearing_actions` | guardrail | `count(INVALID_BEARING)` | 次 / 低 | episode | 0 合法 |
| `map22.memory_facts_written` | diagnostic | `len(final agent_authored_memory_journal)` | 条 / 描述性 | episode | 无 journal → UNAVAILABLE |
| `map22.legal_action_rate` | diagnostic | 接受决策 / 提交决策 | 比例 / 高 | 模型决策数；0 → N/A | — |

实现：`src/agent_arena/v7/metrics/map22.py`，共 7 条 `implemented=True`。最优值按实例冻结：`l1_short_return=4`、`l2_branch_loop=4`、`l2_dead_end_spur=8`、`l3_original=8`（`references.MAP22_OPTIMAL_MOVES`）。

## 4. 能力混淆分析

- `return_success=1` 可能靠 DFS 式穷举：30 步 DFS 也成功，但 `path_gap=22`；必须与 gap 并列。
- `path_gap=0` 可能只因为实例短（L1 最优 4）；L1 不能证明长程记忆，必须按实例分报。
- `repeated_public_edge_rate=0` **不等于高效**：DFS 巡游把每条无向边走两次但方向相反，**有向**重复率为 0；它靠节点回访（7 次）换覆盖。该指标是过程诊断，不单独支撑记忆结论。
- `memory_facts_written` 是**成本**：写得越多不表示记得越好；要同时看 `return_success` 与 `path_gap`。
- 低 `illegal_bearing_actions` 只说明接口用法正确：固定罗盘贪心 F01 也几乎不产生非法方位，却 30 步失败。

## 5. 两条手算轨迹

**A. 18 步图记忆巡回（成功，27 条事实）**：`A-B-D-G-J-K-H-E-B-E-F-I-L-K-H-I-F-C-A`，把 15 条独立边全部至少走一次，`B-E / F-I / H-K` 各多走一次；第 12 步到 L，之后靠已存边记录回 A，第 18 步成功。沿路写 12 张节点卡 + 15 张边卡 = 27 条；回访节点 7 次、重复无向边 3 次。指标：`return_success=1`；`path_gap = 18 − 8 = 10`；有向重复率 = 3/18 ≈ **0.1667**；grounding 违例 0；非法方位 0；`memory_facts_written=27`。

**B. 30 步 DFS 巡游（成功，边界）**：`A-B-D-G-J-K-L-I-H-K-H-E-F-I-F-C-A-C-F-E-B-E-H-I-L-K-J-G-D-B-A`，15 条边各走两次，覆盖 12 节点，第 6 步见到 L，第 30 步回 A。指标：`return_success=1`；`path_gap = 30 − 8 = 22`；有向重复率 **0.0**（每条边正反各一次）；grounding/非法方位 0。**这条轨迹专门说明“重复率 0 但极不高效”**。

> 两条轨迹只在“是否穷举覆盖”上有差异，均合法；它们不是同一策略的换序模板。

## 6. 三个机制特有失败

1. **F01 无笔记罗盘贪心**：`A→B→D→G→J→K` 后 K 优先走 N 回 J，随后 J-K 反复摆荡，第 30 步仍在 J、未见 L。局部方向重复 ≠ 拓扑进展。
2. **F02 误记回程边**：先走最短路到 L，但把 I 处“北”误记成回程边，`L-I-H-K-L` 小环重复，第 30 步仍在 H。目标已见却回不去。
3. **F03 环 + 往返**：走 `A-B-E-F-C-A` 五边环，再把 A-B 往返 9 次，之后走最短路到 L 再回营；第 27 步见 L，第 30 步只到 C，第 31 步才回 A → `STEP_LIMIT_REACHED`。

## 7. 两个边界

- **30 步恰好成功 vs 第 31 步**：B01 的 DFS 恰在 30 步回 A 成功；F03 需要 31 步，失败。步数预算是包含端点，不是“小于 30”。
- **完整图上界 8 步 vs 实际可见信息**：8 步只在拥有全图时可达，Agent 看不到全图；不能把 `path_gap>0` 一律解释为“能力差”，它同时反映探索成本。L1（最优 4）与 L3（最优 8）必须分报。

## 8. 信息泄漏负例

若 Observation 给出 `complete_adjacency`、`target_node` 或“下一跳应走 NE”，空间记忆被替代。V7 只允许公开当前粗形、出口方位、已观察的本地标记、Agent 自己的 journal 与步数；`map_spec.yaml` 的完整方位表、`target_node`、BFS 最短路只在离线裁判侧。`write_memory` 也不能接受“预装全图”的条目。

## 9. Oracle/求解状态

V4 `oracle_trace.jsonl` 有 18 步图记忆巡回与 30 步 DFS 两条手写成功，`planning/` 的审计器两次重放图巡回与局部 Observation 并核对字节一致；V6 `solve_map22` 用 `(node, target_visited)` 状态 BFS 得每实例最短往返（4/4/8/8）。V6 真实 API 6 局：**5/6**；L3 出现条件差异——`history5` 30 moves 截尾、`history5_graph_memory` 11 moves 成功。**单局证据，不能外推。**

## 10. 与同世界另两图差异

**vs MAP-23**：MAP-23 是线索价值 + 补给约束下的候选区域缩减，核心是“哪条线索值得买”；MAP-22 没有线索经济，只有“走过的边是否被记住”。MAP-23 的成功是新发现，MAP-22 的成功是**回到已知起点**。

**vs MAP-24**：MAP-24 有地形突变与在线重规划，地图在局中改变；MAP-22 的图完全静态，全部难度来自信息局部性。把 MAP-22 加突变会变成 MAP-24 的构念。

## 11. 可计算性来源

需要的公开字段：`movement_steps, current_coarse_silhouette, visible_exit_bearings, inspected_current_sign_detail, active_goal_marker, agent_authored_memory_journal, terminal_reason`，以及每次 `move` 的 `observation_before/after`。有向边由两端签名（`sign_id` 或 `silhouette+bearings`）构造；同签名不同节点的重名风险是已知代理局限。最优值来自冻结实例表，不进入 Agent 输入。

## 12. 难度定位与对照

D=(3,1,0,1,3,2)。本世界基线：全局部观测 + 长跨度记忆（M=3），无资源耦合、无事件动态。相对 MAP-23 少了“线索价值/补给”，相对 MAP-24 少了“突变”。

预登记对照：**`history5` vs `history5_graph_memory`**（V6 机制）。两条件共享实例、初态、预算与动作契约，只改可用外部记忆。V6 仅在 L3 出现方向性差异（30 moves 截尾 vs 11 moves 成功），L1/L2 上记忆条件并未更优，因此只能表述为“该实例上的方向性差异”。

## 13. 未决

- 有向重复率依赖公开位置签名唯一性；若两个不同节点粗形 + 出口完全相同，会被误并为同一边。`V7-DCR-011` 请求确认是否允许增加公开节点别名（不泄露全图）。
- `path_gap` 只在成功局有定义；失败局的探索成本目前只能看 `movement_steps`，需要一个独立的“探索效率”诊断（尚未注册）。
- V6 的 L2 双死路变体未跑真实 API；L3 记忆差异为单局。所有实例 `pending_human_review`。
