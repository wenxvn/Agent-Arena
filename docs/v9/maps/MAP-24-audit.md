# MAP-24 审计：消失的道路（jungle / 困难）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-24 / jungle / 困难 |
| condition | `default` |
| `rule_hash` | `394665914bb5c2e22f0dddf070142e23ed1ebe28f8432756a05665a34eb0fa9f` |
| `scenario_hash` | `15b070864d4d70f109e31aec0f5d77761ead75775181f22fec4ab414885ff7ae` |
| `prompt_hash` | `e3de9bb00f301a1be00f419ab8bb339cd2b578fa44545278a1d4e0e1f72cf0d3` |
| `metric_schema_hash` | `d86f91f264766519786113bb65ac9f0dd7f247174f61b8ce87e00e3e2668dae2` |
| `oracle_hash` | `2fd0ac718f61cc92bed2b84e4fe3084425969d96fb2584b4d6c1baafd2f6c6cd` |
| 决策预算 | 46（`BUDGETS["困难"]`）；环境 `step_limit=160` |
| V8 三局 | 2/3 成功；R0 `failure`/`STRANDED_ON_BRIDGE`（9 决策，tick 8），R1 `success`/`ALL_ITEMS_DELIVERED`（9 决策，tick 8），R2 `success`（12 决策，tick 13） |
| 费用（正式行） | 0.0059154 / 0.00240008 / 0.00647696 CNY |
| 证据包 | `runs/v9/evidence/MAP-24.json`、`docs/v9/run-index.csv`（MAP-24 三行） |
| 规则资料 | `docs/v8/maps/MAP-24-final.md`、`worlds/v4/MAP-24/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v8/maps/map24.py`、`src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-24"]` |
| 基线 | `runs/v9/baselines/MAP-24.json` |
| 运行 commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674`；定稿 commit `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 能力构念

这张图想测的是：**当"出发时看到的路线图"在局中失效时，Agent 是否会发现旧计划已过期，并在 deadline 前改走仍然可行的路，把两件物资都带回 A**。

- 成功行为：在 `tick ≤ 24` 前把 `relic_C`、`supply_case_D` 都带回 A，终局 `ALL_ITEMS_DELIVERED`（`map24.py:274-282`）。
- 明确反例：走 A-B-C 桥环且在 tick 8 停在 B（R0，`STRANDED_ON_BRIDGE`）；桥断后仍反复尝试已移除的边（本批 `no_replan` 消融，16 次 `MOVE_FAILED_EDGE_CLOSED` 后 `DEADLINE_EXCEEDED`）。
- 本图在 jungle 三图中的位置（只写本图）：**图会在局中改变**，难点是"改路"；MAP-22 考记忆与返程，MAP-23 考信息价值。

## 2. 机制与因果链

初始 Observation 原文（`runs/v9/evidence/MAP-24.json`，rep 0）：

```json
{"bridge_probe_result":null,"carried_items":[],
 "goal":"在 tick 24 前把 relic_C 与 supply_case_D 都带回 A；桥会在未知时刻永久断开，D-E 潮道只在部分窗口可过。",
 "latest_local_tide_reading":null,"local_connections":[
   {"edge":"A-B","ticks":1,"to":"B"},{"edge":"A-E","ticks":1,"to":"E"},{"edge":"A-F","ticks":2,"to":"F"}],
 "location":"A","route_notes":{},"tick":0,"tide_rule":{"open_ticks":2,"period_ticks":4,"phase_is_seed_private":true},
 "visible_item_here":null}
```

因果链：

1. **起始**：A 同时公布三条出边——**桥环**（A-B 1 tick / B-C 1 tick）与**山路/潮道**（A-F 2 tick；A-E 1 tick），加上 `tide_rule`（周期 4、开 2 tick、相位私有）。
2. **必需观察**：`tick`（deadline 24）、`local_connections`（本地边表，坍塌后 A/B/C 的出边会少一条）、`visible_item_here`、`latest_local_tide_reading`。
3. **关键决策**：走桥环还是山路；是否在 D 等潮窗；桥断后是否换路。
4. **立即后果**：tick ≥ 8 时 `collapsed=True`，A-B、B-C 永久移除；**若此刻身在 B，立即 `STRANDED_ON_BRIDGE`**（`map24.py:258-266`）。D-E 只在 `(tick+phase)%4 ∈ {0,1}` 可过，相位私有。每个动作至少推进 1 tick，`tick > 24` 则 `DEADLINE_EXCEEDED`。
5. **终局**：两件物资都在 A 且 `tick ≤ 24` → 成功；否则截断或超时。

**可绕过核心机制的动作**：

1. **完全不走桥就不会遇到"改路"**。移除 A-B、B-C 后图仍然连通：A-F-C（2+2）与 A-E-D（1+1）都在开局就公开。本批 `Map24Heuristic` 全程走 `A→E→D→C→D→E→A`（潮道方向），**14 个决策成功，`collapsed_edge_attempts=0`、`replanning_latency=None`、`route_cost_ratio=None`**——两个"primary"指标都是 N/A，因为坍塌从未进入它的观察。
2. **桥路线的成功窗口恰好只有 8 个动作**。`A→B→C→take→D→take→C→B→A` 正好在 tick 8 抵达 A（R1 就是这么赢的）；任何多出来的 1 tick（R0 的 `measure_tide`、任何 `wait`、任何绕行）都会让最后一个"过 B"的动作落在 tick 8 而被 `STRANDED_ON_BRIDGE` 截住。因此桥路线不是"快一点"的策略，而是**零容错**的策略。
3. **`probe_bridge` 无法为它本来要回答的问题提供信息**。`_probe_bridge` 只在 B 可用；坍塌前永远返回 `PASSABLE_WITH_CRACKS`；坍塌后 B 已经不可达（A-B、B-C 都被移除，且停在 B 就是死亡）。所以 `COLLAPSED` 这个返回值在**任何非终局轨迹里都不可达**。它在 B 上执行要花 2 tick；在 A/C/D/E/F 上执行虽然 0 tick，但只会得到 `PROBE_ONLY_AT_B`（R0/R1 决策 1 就是这样）。

**机制是否在三条真实轨迹中实际触发**：**坍塌触发了，但"改路"没有触发**。

- 三局都在 tick 8 遇到 `collapsed=True`（R0 因此死亡）。
- `route_notes` 三局全为 `{}`：`record_route` 从未被调用，所以"旧笔记与世界不一致"这个设计主机制**在三条轨迹里一次都没被建立**。
- `replanning_latency`：R0/R1 为 `None`，R2 为 1——而 R2 的 `route_cost_ratio=1.0` 说明它的剩余路线就是最短路，**没有发生任何改路**（§6、§11）。
- `collapsed_edge_attempts`：三局全 0。三局里"桥断后仍试旧桥边"的次数是 0，因为两局成功局根本没在断桥区活动，一局在 B 上直接终止。

**触发所需的最小动作数**：被 `STRANDED_ON_BRIDGE` 抓住 = 8 个动作（`move A→B` + 7 次 `wait`，或等价的 8 tick 停留）；靠桥路线成功 = 恰好 8 个动作（零冗余）；走山路/潮道成功 = 8–12 个动作（Oracle `mountain_and_tide` 8 步）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `goal`（deadline 24、两件物资、桥会断、潮窗） | 是 | 每步 | 是 |
| `tick` | 是 | 每步 | 是 |
| `local_connections`（当前节点的边 + 耗时） | 是 | 每步，仅当前节点 | 是：可在 A 就看到 A-F/A-E，从而绕开桥 |
| `tide_rule`（周期 4 / 开 2 / 相位私有） | 是 | 每步 | 是 |
| `latest_local_tide_reading` | 是 | `measure_tide` 后 | 是：读数指向"下一个 tick"的状态，配合相位可安全过潮道 |
| `visible_item_here` / `carried_items` | 是 | 每步 | 是 |
| `route_notes`（自己的笔记） | 是 | `record_route` 后 | 是，但三局都没用 |
| **坍塌的具体时刻（tick 8）** | **否** | 不可见 | 不需要：公开文本已说"未知时刻"，保守策略应假设随时可能 |
| **"坍塌时人在 B 就立即死亡"** | **否** | 不可见 | 部分：只知道"桥会断"，不知道"断的瞬间站在桥上是终局" |
| **`probe_bridge` 返回值的含义/局限** | 否（词表只说 `probe_bridge()`） | 不可见 | 否：模型会以为它能回答"桥什么时候断"，实际只能回答"此刻断没断"，且 `COLLAPSED` 不可达 |
| 潮道相位 `phase_offset = seed % 4` | 否（hidden） | 不可见 | 不需要：`measure_tide` + 1 tick 重试即可过 |
| 图的完整 7 条边 / 物资位置 | 部分（`take` 词表直接给了 `relic_C|supply_case_D`） | 初始词表 | 是：物品 id 与地点字母直接对应，等于公开了"C 有 relic、D 有 supply" |
| `collapsed` / `observation_tick` / `first_replan_tick` 等 judge 字段 | 否 | 不可见 | 不用于公开策略 |

## 4. 可解性与可观察性

- Oracle：2 条，`ok=true`——`probe_then_update`（11 步，走桥 + 记录 + 返回）、`mountain_and_tide`（8 步，走 A-F-C-D-E-A + 测潮）。
- 手算 fixture 4 条：`normal_update_after_collapse`（11 步，latency 2 / ratio 1.0）、`mountain_route_has_no_replan`（8 步，latency None / ratio None）、`stranded_on_bridge`（8 步）、`stale_note_repeats_collapsed_edge`（24 步，ratio 4.0 / attempts 16）。
- **仅凭公开信息是否存在可执行策略：存在，而且不需要重规划**。`Map24Heuristic` 只用 `local_connections` + `tide_rule` + `measure_tide` + `visible_item_here`：`A→E→(测潮)→D→C→take relic→D→take supply→(测潮)→E→A`，14 个决策成功，`collapsed_edge_attempts=0`。
- 反向也可执行但零容错：Oracle `probe_then_update` 用 11 个动作、在 tick 14 经 `C→F→A` 返回（它确实在 tick 9 发现 C-B 已不可用后改了路）；R1 用 9 个决策在 tick 8 恰好返回，差 1 tick 就会变成 R0。
- 判定：**不是 `INTERFACE_BLOCKED`、不是 `BUDGET_BLOCKED`**（46 个决策、8 步可解）。问题是 **`CONSTRUCT_BYPASS`**：核心构念是"发现旧路失效后改路"，但**避开桥就可以完全不遇到这个情境**，而避开桥所需的信息在开局第一帧就完全公开。两个 primary 指标对这条成功路线都返回 `None`。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 11（桥）/ 8（山路+潮道） |
| 决策预算 | 46 |
| `legal_random` × 20 | 0 成功；15/20 `decision_budget_reached`、4 `STRANDED_ON_BRIDGE`、1 `DEADLINE_EXCEEDED`；决策 12–46；schema 非法 0；`rejected` 276（只统计 `INVALID*` 前缀） |
| `public_heuristic`（避桥 + 测潮） | 14 决策，`ALL_ITEMS_DELIVERED`（tick 14） |
| 消融 `no_replan`（计划走桥、断后重试） | 25 决策，`DEADLINE_EXCEEDED`，`collapsed_edge_attempts=16`，`route_cost_ratio=4.0` |
| V8 三局 | 9 / 9 / 12 决策；R0 在 tick 8 终止 |

- 判定：**不是预算不够**。46 个决策对应最长成功路线 14 个决策，且 deadline 只有 24 tick、最优路线 8 tick，时间维度有 3 倍余量。R0 的失败也不是"来不及"：它在 tick 6 就已经拿齐两件物资，是回程路径选择把它送进了 tick 8 的 B。
- 随机基线里 4/20 局 `STRANDED_ON_BRIDGE`，说明 B 上的死亡陷阱在无策略采样下**确实频繁触发**（20%），但它与决策预算无关。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map24.replanning_latency` | primary | `first_replan_tick − 8` | 坍塌实际发生的 episode | 运行时缺来源 → UNAVAILABLE；`first_replan_tick=None` → None |
| `map24.route_cost_ratio` | primary | `remaining_move_cost / 同点最短可行成本` | 坍塌后最短可行成本 | 未观察断边 → None；最短成本为 0/不可达 → None |
| `map24.collapsed_edge_attempts` | guardrail | 坍塌后对已移除桥边的 `move` 次数 | episode | 0 次合法为 0 |
| `map24.rescue_failure` | diagnostic | 终局未把两件物资都带回 A | episode | 无终局 → CENSORED |

- **`replanning_latency` 的实现与登记规则不一致（关键）**。登记口径是"坍塌后首次**改路**移动的发起 tick − 8"，并要求"没有改路需求 → None"；但代码在 `_move` 里对**任何**非桥边移动都置 `first_replan_tick`（`map24.py:196-198`）。R2 因此得到 `latency=1`：它在 tick 8 站在 C（刚看到 `relic_C`），tick 9 走 C→F——那本来就是原计划的一段，`route_cost_ratio=1.0` 证明它走的是最短路。**这是一个假阳性**：0 次改路，指标却报"改路延迟 1 tick"。
- **`replanning_latency` 对真正的"不改路"也不敏感**。本批 `no_replan` 在桥断后连续 16 次尝试已移除的 C-B 边（`collapsed_edge_attempts=16`），因为没有走任何非桥边，`first_replan_tick` 始终是 `None`，`latency=None`。也就是说：**该指标既会给"没改路"报小值，也会给"死守旧路"报 None，唯一漏掉的正是"改路"本身**。
- **`route_cost_ratio` 的 None 分支**：R0 被隔离在 B，`_shortest_cost("B")` 返回 `None`（桥断后 B 无可行边）→ None；R1 在 A 交付，`_shortest_cost("A")=0` 被 `if shortest:` 判为假 → None；本批启发式同样在 A 交付 → None。三个 None 的成因不同，但对外都显示为"没有值"。
- **未通关仍有意义的连续指标**：只有 `collapsed_edge_attempts`（0/0/0 vs 消融 16）。`rescue_failure` 是二值；两个 primary 在三局里一个全 None、一个只有假阳性。
- **三局 N/A**：R0/R1 各有 2 条 N/A（`replanning_latency`、`route_cost_ratio`），`run-index.csv` 的 `not_applicable=2` 与之一致。R0 的 N/A 有真实原因（B 被隔离、无可行最短路），R1 的 N/A 来自"在 A 交付、最短成本为 0"，属于口径边界而非真实缺失。
- **区分度**：`rescue_failure` 能区分 R0 与 R1/R2；`collapsed_edge_attempts` 能区分 `no_replan`（16）与所有真实局（0）；两个 primary **一个假阳性、一个全 None**，在三局+消融中没有任何一次正确指向"改路"。记为 **`LOW_DISCRIMINATION` + `METRIC_DEFECT`**。

## 7. 三次轨迹归因

### R0 `V8-MAP-24-R0-20261017T100123Z-3523377d`（9 决策，tick 8，`STRANDED_ON_BRIDGE`）

- 决策 1：`{"tool":"probe_bridge"}`（在 A）→ `PROBE_ONLY_AT_B`；观察变化 `{}`（`_cost=0`，不推进 tick，但消耗一个决策）。
- 决策 3：`{"to":"C","tool":"move"}` → `MOVED:C`；`{"local_connections":[{"edge":"B-C","ticks":1,"to":"B"},{"edge":"C-D","ticks":1,"to":"D"},{"edge":"C-F","ticks":2,"to":"F"}],"location":"C","tick":2,"visible_item_here":"relic_C"}`。
- 决策 6：`{"tool":"measure_tide"}` → `TIDE_MEASURED:OPEN`；`{"latest_local_tide_reading":{"state":"OPEN","tick":5},"tick":5}`。**这一 tick 是全局的分水岭**。
- 决策 8：`{"to":"C","tool":"move"}` → `MOVED:C`；`{"location":"C","tick":7}`（已持 `["relic_C","supply_case_D"]`）。
- 决策 9：`{"to":"B","tool":"move"}` → `MOVED:B`；`{"local_connections":[],"location":"B","terminal":true,"terminal_reason":"STRANDED_ON_BRIDGE","tick":8}`。

**首次偏离合理策略的可观测事件：决策 6**。到决策 5 时它在 D（tick 4），两件物资均已到手；此时距 tick 8 只剩 3 tick，而回 A 的两条路分别是 C→B→A（2 tick，但必须在 tick 7 之前过 B）和 C→F→A（4 tick）。它把其中一 tick 花在 `measure_tide` 上（决策 6），于是返回路径变成 tick 7 到 C、tick 8 到 B——**正好撞上坍塌**。R1 在同样位置跳过了 `measure_tide`，tick 6 到 C、tick 7 到 B、tick 8 到 A，成功（见 R1）。**同一路线、相差 1 tick、结局相反**。

**失败链**：走零容错的桥环 → 额外花 1 tick 观测潮位（且潮位对桥环回程没有任何用处）→ 回程在 tick 8 抵达 B → 坍塌瞬间被隔离。注意它在决策 8 站在 C，此时还有 C→F→A（4 tick，tick 11 到 A）这条活路；但它选了 C→B。

**替代解释**：规则缺陷（否，`STRANDED_ON_BRIDGE` 是文档化结局，且 Oracle/fixture 都能复现）；公开信息不足（部分成立：不知道"坍塌时在 B 会死"，只知道"桥会断"）；预算不足（否，46 个决策只用了 9 个）。

### R1 `V8-MAP-24-R1-20261017T100207Z-2b1d8bb1`（9 决策，tick 8，成功）

- 决策 1：`{"tool":"probe_bridge"}`（在 A）→ `PROBE_ONLY_AT_B`；`{}`。
- 决策 6：`{"item_id":"supply_case_D","tool":"take"}` → `ITEM_COLLECTED:supply_case_D`；`{"carried_items":["relic_C","supply_case_D"],"tick":5,"visible_item_here":null}`。
- 决策 8：`{"to":"B","tool":"move"}` → `MOVED:B`；`{"local_connections":[{"edge":"A-B","ticks":1,"to":"A"},{"edge":"B-C","ticks":1,"to":"C"}],"location":"B","tick":7}`。
- 决策 9：`{"to":"A","tool":"move"}` → `MOVED:A`；`{"local_connections":[{"edge":"A-E","ticks":1,"to":"E"},{"edge":"A-F","ticks":2,"to":"F"}],"location":"A","terminal":true,"terminal_reason":"ALL_ITEMS_DELIVERED","tick":8}`。

**观察到的关键细节**：决策 9 的 `local_connections` 已经不含 A-B（只剩 A-E、A-F）——**同一帧里"桥已断"和"我赢了"同时发生**，因为 `_move` 在 `_after_tick` 之前完成。这也解释了为什么 `replanning_latency=None`：`observation_tick` 在交付的同一 tick 才被置位，`first_replan_tick` 永远没有机会被设置。

**判定**：这不是"重规划成功"，而是"在坍塌前 0 tick 完成"。它证明桥路线可通，但**没有任何余量**，不能作为"能应对世界变化"的证据。

### R2 `V8-MAP-24-R2-20261017T100237Z-087a6524`（12 决策，tick 13，成功）

- 决策 1：`{"tool":"measure_tide"}`（在 A）→ `TIDE_MEASURE_ONLY_AT_D_OR_E`；`{}`（`_cost=0`，白送一个决策）。
- 决策 3：`{"tool":"measure_tide"}` → `TIDE_MEASURED:CLOSED`；`{"latest_local_tide_reading":{"state":"CLOSED","tick":2},"tick":2}`。
- 决策 4：`{"to":"D","tool":"move"}` → **`MOVE_FAILED_EDGE_CLOSED`**；`{"tick":3}`（相位私有，读数是"下一 tick"，它按当前 tick 出发，正好落在关窗）。
- 决策 7：`{"to":"D","tool":"move"}` → `MOVED:D`；`{"location":"D","tick":6,"visible_item_here":"supply_case_D"}`。
- 决策 12：`{"to":"A","tool":"move"}` → `MOVED:A`；`{"location":"A","terminal":true,"terminal_reason":"ALL_ITEMS_DELIVERED","tick":13}`。

**改路判定：没有改路**。它走的是 A-E-D-C-F-A 的潮道路线，桥从头到尾没进入计划；`collapsed_edge_attempts=0`。`replanning_latency=1` 来自决策 11 的 C→F（tick 9 发起的第一个非桥边移动），而 `route_cost_ratio=1.0` 说明 C→F→A 就是当时的最短路——**指标把"按原计划走下一步"记成了"改路"**。

**重复证据有限**：三局都只有 9/9/12 个决策，R0 与 R1 的动作序列在前 8 步完全相同、只在第 9 步分叉（B vs A），因此 n=3 **不能**区分"个体策略差异"与"tick 8 的固定陷阱"；能区分的是路线族（桥 vs 潮道）。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E**（零容错桥路线 + 回程选择 C→B；在 C 时仍有 C→F→A 活路） | C（不知道"坍塌时在 B 即死"；`probe_bridge` 无法提供时机信息）、D 不成立 | 高 | 决策 1/6/8/9 |
| R1 | —（成功，0 tick 余量） | 风险策略，非能力证据 | 高 | 决策 8/9 |
| R2 | —（成功，未遇到坍塌） | 指标假阳性（latency=1） | 高 | 决策 4/11/12 |

- **E（策略规划错误）**：R0 在 tick 6 已持两件物资，回程有两条路；它选了必须在 tick 7 前过 B 的那条，并把一 tick 花在与回程无关的 `measure_tide` 上。
- **C（接口误导）**：`probe_bridge` 的名字与存在本身暗示"可以先探测桥再决定"，但它在坍塌前永远返回 `PASSABLE_WITH_CRACKS`、坍塌后不可达；R0/R1 都在决策 1 试了它（都得到 `PROBE_ONLY_AT_B`，因为不在 B）。这不是首因，但它是"为什么模型会低估桥风险"的一个合理解释。
- **A（规则缺陷）**：不成立——`STRANDED_ON_BRIDGE`、潮窗、deadline 都有 fixture 覆盖，规则自洽。
- **B（公开信息不足）**：仅"站在桥上是即时死亡"这一点成立，与 C 重叠。
- **H / I**：H 不成立（0 provider 错误）；I 成立（n=3，R0/R1 前 8 步相同）。

## 9. 标签

- **`MEASUREMENT_VALID`（失败信号层面）**：R0 的 `STRANDED_ON_BRIDGE` 是真实的、规则自洽的失败；同一张图上公开启发式 14 个决策成功，Oracle 8 步成功。
- **`CONSTRUCT_BYPASS`**：核心机制是"旧路失效后改路"，但开局第一帧就公开了 A-F 与 A-E 两条不经桥的路，避开桥即可完全不触发该机制；两局成功（R1/R2）都没有发生任何改路，`route_notes` 三局全空，`collapsed_edge_attempts` 三局全 0。**本图在 V9 里测到的是"路线风险选择"，不是"在线重规划"**。
- **`METRIC_DEFECT`**：(1) `replanning_latency` 在实现里对任何非桥边移动置位，与登记口径"首次**改路**移动"不符，R2 因此假阳性（latency=1 且 ratio=1.0）；(2) 同一指标对"死守旧桥边"（`no_replan`，16 次失败移动）返回 None，方向完全相反；(3) `route_cost_ratio` 在 A 交付时分母为 0 → None，在 B 被隔离时分母不可达 → None，两种完全不同的情形共用一个"无值"。
- **`LOW_DISCRIMINATION`**：三局 + 消融里，唯一正确指向"未改路"的指标是 `collapsed_edge_attempts`；两个 primary 指标一次假阳性、其余全 None。
- **`INCONCLUSIVE`（构念层面）**：三局没有任何一次真实的重规划，因此不能用它们声称"模型具备/不具备在线改路能力"。

## 10. 最小可证伪修复（无证据不修改）

**旧规则/旧公开信息**：

1. `replanning_latency` 的实现把"任何非桥边移动"当成"改路移动"；
2. `probe_bridge` 在非终局轨迹里只能返回 `PASSABLE_WITH_CRACKS`，`COLLAPSED` 不可达；
3. 公开文本没有说"坍塌瞬间站在 B 会立即死亡"；
4. `route_cost_ratio` 在"已在 A"与"B 被隔离"两种情形都返回 None。

**证据与根因**：R2 `latency=1` 且 `ratio=1.0`（最短路、零改路）；`no_replan` 16 次失败移动却 `latency=None`；R0 `route_cost_ratio=None` 因 B 无可行路径；R1 因在 A 交付而 `_shortest_cost=0`。

**候选 A（首选，只改指标实现，不改规则）**：把 `first_replan_tick` 定义为"坍塌被观察到之后，第一次**偏离当时已知最短路**的移动"，并用 `route_cost_ratio>1` 作为一致性校验；或者更保守地把 `replanning_latency` 降级为 diagnostic，把 `route_cost_ratio` 提为唯一 primary。预期：R2 从 1 变成 None（或 0），`no_replan` 得到一个明确的大值而不是 None。

**候选 B（只补公开信息）**：在 `goal` 或词表里写明"桥断的瞬间站在桥上即失败；`probe_bridge` 只报告当前是否可通，不预测时刻"。预期：模型不再把 `probe_bridge` 当作时机探测，R0 这类"多花 1 tick 然后撞上 tick 8"的路径会减少。构念不变。

**候选 C（可选，收窄旁路，需 DCR）**：让桥环成为**唯一**可行路线（例如把 A-F 的耗时改到 6、或让 A-E 潮道只在坍塌后开放），迫使 Agent 进入"旧路失效"的情境。这会改变 `rule_hash` 与全部 fixture，风险最高，且会让 MAP-24 与 MAP-22/23 的难度定位重叠。

**候选 D（实验设计）**：即使不改规则，也应在 V9 报告里同时给出"避开桥的成功路线"的指标（本批启发式 latency/ratio 全 None），并在解释成功率时明确区分"桥路线 8 tick 零容错"与"山路 10–14 tick 有余量"两种成功。否则 2/3 的成功率会被读成"重规划能力强"。

**预期变化与构念影响**：A 只影响指标层（旧 Trace 可复算）；B 影响 `prompt_hash`；C 影响 `rule_hash` 且旧 Trace 不可直接回放。

**反例与回归风险**：

- 只做 A，`CONSTRUCT_BYPASS` 不变：避开桥仍然拿不到 latency/ratio。
- 只做 B，R0 那类"恰好差 1 tick"的失败可能减少，但成功仍可能靠"刚好赶上"，不能证明改路能力。
- 做 C 会让 MAP-24 的成功率显著下降，n=3 下无法区分"更难"与"更坏"；且需要重算 4 条 fixture 与 2 条 Oracle。
- 任何 `rule_hash` 变更都需要新账本，不能续跑已关闭的 V8 账本。

**若无需修改**：不成立——`replanning_latency` 的假阳性与 None 的错误方向都是可复算的硬事实（R2 latency=1 且 ratio=1.0；`no_replan` attempts=16 但 latency=None）。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-24.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `probe_then_update` | `scenario_success` | 11 | ok=true（走桥 + 记录 + 返回） |
| Oracle `mountain_and_tide` | `scenario_success` | 8 | ok=true（latency None、ratio None） |
| `legal_random` × 20 | 0 成功 | 12–46 | 15 预算耗尽、4 `STRANDED_ON_BRIDGE`、1 `DEADLINE_EXCEEDED` |
| `public_heuristic`（避桥 + 测潮） | `scenario_success`（tick 14） | 14 | attempts 0、latency None、ratio None、rescue 0 |
| 消融 `no_replan`（计划走桥、断后重试） | `DEADLINE_EXCEEDED` | 25 | attempts **16**、ratio **4.0**、latency None、rescue 1 |
| V8 三局 | 2/3 | 9/9/12 | attempts 0/0/0；latency None/None/1；ratio None/None/1.0 |

**独立复算 1（`replanning_latency`，R2）**：按 Trace 的 `tick` 序列，tick 8 的 `_after_tick` 在 C 置 `observation_tick=8`；随后第一个非桥边移动是决策 11 的 C→F，发起时 `tick_count=9`，故 `first_replan_tick−8 = 1`，与 judge 一致。**同时**：该移动的边 C-F 与"原计划"一致，`route_cost_ratio=1.0` 证明剩余成本等于最短路，所以 `latency=1` 不是改路。这就是 §6 的假阳性，手工可复算。对照 Oracle fixture `normal_update_after_collapse`：它的 `latency=2` 来自同一实现机制（tick 9 观察到断边、tick 10 走 C→F），只是那一次 C→F 恰好**真的**是改路——同一个实现，靠巧合与登记语义对齐。

**独立复算 2（`route_cost_ratio`，`no_replan`）**：坍塌后 `observation_node=C`，`_shortest_cost("C")` 在"潮道未知开窗"的前提下取 C-F(2)+F-A(2)=4；`remaining_move_cost` 从 tick 8 起累计所有含失败的移动成本，实测 16 次 C→B 失败每次 +1，共 16，故 `16/4 = 4.0`，与 judge 与 fixture `stale_note_repeats_collapsed_edge`（期望 4.0）三者一致。

**独立复算 3（`rescue_failure`）**：R0 终局 `carried=["relic_C","supply_case_D"]` 但 `location="B"` ≠ A → 1；R1/R2 在 A 交付 → 0。手工核对三局的 `final_observation.carried_items` 与 `location` 即可，与 judge 一致。

**区分度**：`rescue_failure` 与 `collapsed_edge_attempts` 可用；两个 primary 无法正确区分"改路/未改路"，反例分别是 R2（1 / 1.0，未改路）与 `no_replan`（None / 4.0，死守旧路）。记 **`LOW_DISCRIMINATION`（primary 层）**。

## 12. V9 状态

**`NEEDS_REDESIGN`（P1）**。理由：成功/失败的判定与规则本身是干净的（R0 的 `STRANDED_ON_BRIDGE` 真实、覆盖 20% 的随机局），但**这张图在 V9 里没有测到它宣称的构念**——避开桥就能绕开"旧路失效"，两局成功都没有发生改路，`route_notes` 三局全空；而唯一为改路设计的 `replanning_latency` 既对"没改路"报 1（R2），又对"死守旧路"报 None（`no_replan`）。在指标修好、并让至少一条成功路线必须穿越坍塌区之前，MAP-24 的 2/3 只能读作"路线风险选择"的成绩。
