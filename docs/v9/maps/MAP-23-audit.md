# MAP-23 审计：迷雾中的遗迹（jungle / 中等）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-23 / jungle / 中等 |
| condition | `default` |
| `rule_hash` | `7579ca9aa3fa5e4d752b215dc99c69ed90bf7737eafc7c5d91838fd242909682` |
| `scenario_hash` | `9dc4b4a5a17621b9b25f12201ebe36fed7098eb2c0a48bac8ef57319305d1a8b` |
| `prompt_hash` | `f90bcee72193100a2566cdd8e1d51199718e2a57309868ea0c6c701b3e2ac573` |
| `metric_schema_hash` | `678d9e0132d61ca9967709cfeb9f2eb8c8b625999ac1e0c1f562debd3c692627` |
| `oracle_hash` | `41e53eba2084a791b9c3740d4694011a23132083687c28e33c64d427c046f8ab` |
| 决策预算 | 38（`BUDGETS["中等"]`）；环境 `step_limit=160` |
| V8 三局 | 1/3 成功；R0/R1 `failure`/`SUPPLY_DEPLETED`（16 / 22 决策），R2 `success`/`TRUE_ENTRANCE_FOUND`（10 决策） |
| 费用（正式行） | 0.0094424 / 0.01201268 / 0.00511756 CNY |
| 证据包 | `runs/v9/evidence/MAP-23.json`、`docs/v9/run-index.csv`（MAP-23 三行） |
| 规则资料 | `docs/v8/maps/MAP-23-final.md`、`worlds/v4/MAP-23/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v8/maps/map23.py`、`src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-23"]` |
| 基线 | `runs/v9/baselines/MAP-23.json` |
| 运行 commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674`；定稿 commit `039e25ce6503871ceb31184e85c9265451ee7486` |

**本图专属事实（源码级）**：`true_entrance = VARIANTS[(seed + 2) % 3]`（`map23.py:104`），三局都用 `seed=0`，所以真入口**恒为 Z**；三局在 N 侦察都得到 `STONE_THREE_RINGS`，与 truth=Z 一一对应。"三个等概率真入口"在 V8 的三次正式运行里**只采样到一个变体**。

## 1. 能力构念

这张图想测的是：**Agent 能否把"一条线索的信息量"换算成"路费 + 2 点补给"的账，在 14 点初始补给 + A 处一次性补满的约束下，用最低代价锁定并抵达真入口**。

- 成功行为：站在真入口（X/Y/Z 之一）上执行 `investigate`，且扣费后 `supply > 0`，终局 `TRUE_ENTRANCE_FOUND`（`map23.py:209-233`）。
- 明确反例：拿到唯一线索后不去对应入口（R0/R1）；把补给耗到 0 才想起补满（R0 决策 16 在 A 归零）；对已排除入口重复调查（`REPEATED_INVALID_EXPLORATION`）。
- 本图在 jungle 三图中的位置（只写本图）：图**静态**、成本全公开，难点是"信息是否值它的价格"；MAP-22 考记忆与返程，MAP-24 考图变化后的改路。

## 2. 机制与因果链

初始 Observation 原文（`runs/v9/evidence/MAP-23.json`，rep 0）：

```json
{"actions_taken":0,"agent_marked_candidate":null,"available_scout_stations":[],
 "clues_received":[],"goal":"用 14 点补给调查到真入口，且调查扣费后补给必须严格大于 0；
 三处侦察各 2 点，A 的补给箱只能用一次。","last_action_result":"READY","location":"A",
 "map_id":"MAP-23","neighbors":{"H":2,"N":1,"R":2},"resupply_cache_available":false,
 "searched_false_entrances":[],"supply_remaining":14,"terminal":false,"terminal_reason":null}
```

因果链：

1. **起始**：A（补给箱），14 点补给；`neighbors={H:2,N:1,R:2}` 公开了三条边的**路费**，图结构与成本全部公开。
2. **必需观察**：`scout` 只能在 N/R/H 各用一次、每次 2 点，返回 `signal` 与 `supports`（候选入口子集）。线索表（`SIGNALS`/`SIGNAL_SUPPORTS`）**不公开**，只能靠侦察逐条看到。
3. **关键决策**：是否侦察、侦察几处、先试哪个入口、以及何时在 A 用掉一次性补满。
4. **立即后果**：`move` 扣 `neighbors` 里的成本；`investigate` 扣 X=3 / Y=2 / Z=3，错入口记入 `searched_false_entrances` 并继续；补给归 0 立即 `SUPPLY_DEPLETED`（`_after_tick`），站在入口却付不起调查费则 `SUPPLY_STRANDED`。
5. **终局**：真入口 + 扣费后 `supply>0` → 成功；否则资源耗尽。

**可绕过核心机制的动作**：

1. **完全不侦察也能通关**。直接按 X→Y→Z 逐个付费试，配合"低补给时回 A 补满"，可用 12 个决策成功（本批 `no_scout` 消融，`clue_utilization=0`、`cost_per_discovery=11.0`）。设计文档 `docs/v8/maps/MAP-23-final.md` §1 也承认这条路径存在（"玩家也可以不侦察，直接花 1–3 补给逐个试入口"），但 V8 三局恰好都没有走这条路径。
2. **`mark` 是纯装饰**。`map23.py:234-238` 只写 `agent_marked_candidate` 并返回 `MARKED:x`，没有任何规则或指标读取它；三局都没用，因此没有代价。
3. **单站即可确定真值**。H 的三条信号在 `SIGNAL_SUPPORTS` 里全是单元素集合（X→`RIDGE_NORTH_WHITE_MARK`{X}、Y→`RIDGE_CENTER_AMBER_MARK`{Y}、Z→`RIDGE_LOW_BLACK_MARK`{Z}），所以"花 2 点去 H 侦察一次"对三种真值都给唯一答案；N 只有 truth=Z 才是唯一，R 永远给两元素集合。A→H 的路费是 2，A→N 是 1——**多花 1 点路费就能换到必然确定**，这让"这条线索值不值"的判断退化。
4. **补满是"置满"而不是"加量"**。`resupply` 把补给设成 14（`map23.py:240-247`），所以花掉多少就补回多少，单次补满最多提供 13 点的净空间；`cost_per_discovery` 用 `(14 − 终局剩余)` 计算，完全看不见这次注入（§6）。

**机制是否在三条真实轨迹中实际触发**：**触发了侦察与补满，但没有触发"信息→决策"的链路**。

- 三局都在 N 侦察并拿到单元素线索 `supports=["Z"]`（R0 决策 2、R1 决策 3、R2 决策 2），也就是**在第 2–3 个决策就已经知道真入口是 Z**。
- R2 用它走到了 Z（决策 9–10 成功）；R0/R1 拿到同一条线索后**转而去了 Y/X/N**（R0 决策 7–15、R1 决策 14–20），线索没有进入路径规划。
- 补满：R0 决策 4、R1 决策 5、R2 决策 6 各用一次，三局都用掉了唯一一次机会。

**触发所需的最小动作数**：Oracle 7 个动作（`river_double_ripples_then_z`）；单次侦察 + 直达 = 8（A→N scout → A→R→Z investigate），本批启发式用了 9（多一次 H 往返）。用满 14 点需要 1 次 `resupply`。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `goal`（含"14 点补给 / 三处侦察各 2 点 / A 只能用一次"） | 是 | 初始，每步 | 是：胜利条件与主要约束全公开 |
| `neighbors`（相邻节点 + 每条边的路费） | 是 | 每步，仅当前节点 | 是：图与成本可通过移动逐步学全 |
| `supply_remaining` / `resupply_cache_available` | 是 | 每步 | 是 |
| `clues_received[].supports` | 是 | 侦察后永久 | 是：拿到即知候选子集 |
| `available_scout_stations` | 是 | 每步，**只报当前节点是否可侦察** | 部分：另外两个站在哪里要靠公开词表 `scout() 在 N\|R\|H` |
| `searched_false_entrances` | 是 | 每步 | 是 |
| `agent_marked_candidate` | 是 | 每步 | 不参与任何规则/指标（装饰字段） |
| **线索表本身**（哪一站给哪个 signal / 每个 signal 支持谁） | **否** | 不可见 | 不需要：侦察一次即得 |
| `true_entrance`（seed 私有） | 否（hidden `judge_state`） | 不可见 | 不用于公开策略 |
| 每个入口的调查费 X=3/Y=2/Z=3 | **否** | 不可见 | 部分：错误代价只知道"≥1"，不知道具体值 |
| `SUPPLY_STRANDED` 的判定细节（付不起任何一条边/调查） | 否 | 不可见 | 不需要精确知道，够用保守策略规避 |

**本图的信息面基本完整**：`goal`、`neighbors`、`clues_received`、`supply_remaining` 四个关键字段都公开，公开启发式只靠它们就能 9 个决策通关。唯一的结构性信息问题是**线索表不公开导致"侦察站之间的信息质量差异"不可预判**——玩家无法在侦察前知道"去 H 一定唯一、去 R 一定两个候选"，只能事后发现。这既不是作弊也不是封死，但它让"信息价值的计算"变成"信息价值的试错"。

## 4. 可解性与可观察性

- Oracle：2 条，均 7 个动作、`ok=true`：`river_double_ripples_then_z`（R 侦察 → 试 Y → 转 Z）、`ridge_unique_signal`（H 侦察 → 补满 → Z）。
- 手算 fixture 4 条：`river_clue_then_z`（7 步，`clue_utilization=0.5`、`cost_per_discovery=13.0`）、`ridge_scout_full_reduction`（7 步，1.0 / 7.0）、`repeat_false_entrance_is_counted`（4 步）、`ignoring_single_support_clue`（4 步，`ignored_counterevidence=1`）。
- **仅凭公开信息是否存在可执行策略：存在，而且有两条**。
  - 侦察路线：`Map23Heuristic` 9 个决策成功——A→N（`scout` 得 `STONE_THREE_RINGS` → Z）→A（`resupply` 补满）→H→A（一次多走的未探索分支）→R→Z（`investigate`），`clue_utilization=1.0`、`cost_per_discovery=11.0`、`ignored_counterevidence=0`。
  - 盲试路线：`Map23NoScout` 12 个决策成功——A→N→X（假）→N→A（补满）→N→Y（假）→R→Z（真），`clue_utilization=0.0`、`cost_per_discovery=11.0`。
- 两条路线的**补给成本完全相同（11.0）**，差别只有 3 个决策。也就是说本图存在"不侦察也不吃亏"的可执行策略，线索机制不是解题必需。
- 判定：**不是 `INTERFACE_BLOCKED`，也不是 `BUDGET_BLOCKED`**（预算 38，最长成功路线 12 个决策）；问题是 `CONSTRUCT_BYPASS`（盲试同价）+ 主指标退化（§6）。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 7 / 7 |
| 决策预算 | 38 |
| `legal_random` × 20 | 0 成功；20/20 `decision_budget_reached`，决策 38；schema 非法 0；`rejected_actions` 合计 277 |
| `public_heuristic`（侦察） | 9 决策，`TRUE_ENTRANCE_FOUND`，`cost_per_discovery=11.0` |
| 消融 `no_scout`（盲试 + 回 A 补满） | 12 决策，`TRUE_ENTRANCE_FOUND`，`cost_per_discovery=11.0` |
| V8 三局 | 16 / 22 / 10 决策；两局 `SUPPLY_DEPLETED` |

- `rejected_actions` 只统计以 `INVALID*`/`ALREADY*` 等前缀开头的结果（`v9/baselines.py::_TERMINAL_MARKERS`），`NOT_AT_ENTRANCE`、`NOT_ADJACENT`、`SCOUT_ALREADY_USED` **不计入**；因此 277 这个数字低估了随机基线的语义失败次数（见 §7 的两局里就有 5 次 `NOT_AT_ENTRANCE`/`NOT_ADJACENT`）。
- 判定：**不是预算不够，也不是资源机制不可行**。同一张图 9–12 个决策即可成功，38 个决策的上限留了 3 倍余量；两局的补给耗尽来自"拿到唯一线索后绕路"（R0 用掉 28 点总补给、R1 同样耗尽），不是 14+14 的总额度不够。补给机制是**惩罚乱走的约束**，不是不可满足的门槛。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map23.clue_utilization` | primary | `max(3 − len(supports)) / 2`（**最强单条线索**的缩减量） | 常数 2 | 未侦察 → 0（合法 0） |
| `map23.cost_per_discovery` | primary | `(14 − 终局 supply) / 成功发现数` | 成功发现数；0 → N/A | 未成功 → N/A |
| `map23.repeated_invalid_exploration` | guardrail | 对 `searched_false_entrances` 里的入口再次 `investigate` | episode | 0 次合法为 0 |
| `map23.ignored_counterevidence` | diagnostic | 最终调查的入口是否已被已购线索排除 | episode | 无调查 → 0 |

- **未通关仍有意义的连续主指标：名义上有 `clue_utilization`，实际上没有信息量**。三局的 `clue_utilization` 全是 1.0，包括两局失败：它衡量的是"买到的最强线索有多强"，不是"是否按线索行动"。`no_scout` 失败/成功时是 0.0。因此这个主指标只能区分"有没有侦察"，不能区分"用没用线索"。
- **三局 N/A**：`cost_per_discovery` 在 R0/R1 为 N/A（**真实分母 0**：没有成功发现，`metrics()` 返回 `None`），R2 为 9.0。`run-index.csv` 的 `not_applicable=1` 与之一致，属于指标卡"0 发现 → N/A"的规定，不是投影错误。
- **`cost_per_discovery` 看不见补满**。R2 的真实支出是 15 点（1+2+1+1+1+2+2+2+3），其中 d6 的 `resupply` 注入了 6 点，终局剩 5，公式报 `14−5=9`。fixture `ridge_scout_full_reduction` 同样：真实支出 13，公式报 7。**同一局的"消耗/发现"被系统性低估 6 点**。
- **区分度**：
  - `clue_utilization`：1.0（三局 + 侦察基线）vs 0.0（`no_scout`）——区分"侦察与否"，不区分成败。
  - `cost_per_discovery`：9.0（R2）vs 11.0（本批两条启发式路线）——区分"省不省"，但被补满污染。
  - `repeated_invalid_exploration`、`ignored_counterevidence` 三局全 0，无方差。
  - 三局的指标向量是 `{1.0, N/A, 0, 0}`、`{1.0, N/A, 0, 0}`、`{1.0, 9.0, 0, 0}`：**只有 1 个字段有方差**。记为 **`LOW_DISCRIMINATION` + `METRIC_DEFECT`（`cost_per_discovery` 口径）**。

## 7. 三次轨迹归因

### R0 `V8-MAP-23-R0-20261017T095752Z-a3d3a12a`（16 决策，`SUPPLY_DEPLETED`）

- 决策 2：`{"tool":"scout"}` → `SCOUTED:STONE_THREE_RINGS`；观察变化 `{"actions_taken":2,"available_scout_stations":[],"clues_received":[{"signal":"STONE_THREE_RINGS","station":"N","supports":["Z"]}],"supply_remaining":11}`。**第 2 个决策就知道真入口是 Z。**
- 决策 3：`{"to":"A","tool":"move"}` → `MOVED:A`；`{"resupply_cache_available":true,"supply_remaining":10,...}`。
- 决策 5：`{"to":"R","tool":"move"}` → `MOVED:R`；`{"location":"R","neighbors":{"A":2,"Y":1,"Z":2},"supply_remaining":12}`。**此时 Z 就在一步之外（`R→Z` 成本 2）。**
- 决策 7：`{"to":"Y","tool":"move"}` → `MOVED:Y`；`{"location":"Y","neighbors":{"N":2,"R":1},"supply_remaining":9}`。**没有走 R→Z。**
- 决策 9：`{"entrance":"Z","tool":"investigate"}`（此时在 N）→ **`NOT_AT_ENTRANCE`**；观察变化 `{"actions_taken":9}`（不扣补给、不推进位置）。
- 决策 11 / 12：`{"to":"Y","tool":"move"}` ×2（此时在 X，X 的唯一邻居是 N）→ **`NOT_ADJACENT`** ×2；观察变化 `{}`。
- 决策 16：`{"to":"A","tool":"move"}` → `MOVED:A`，`{"supply_remaining":0,"terminal":true,"terminal_reason":"SUPPLY_DEPLETED"}`。

**首次偏离合理策略的可观测事件：决策 5→7**。它站在 R 上，`neighbors` 明写 `Z:2`，而且自己的 `clues_received` 已经指向 Z，却在下一决策去了 Y。此后 5 次无效/失败动作（1 次 `NOT_AT_ENTRANCE`、2 次 `NOT_ADJACENT`）纯属浪费。

**失败链**：唯一线索到手 → 没有把它变成目标 → 在 N/X/Y 之间绕 → 一路扣费到 1 点 → 最后一次移动归零。补给总额 28 点（14 + 补满 14），实际花掉 28 点。

**替代解释**：补给机制太紧（**否**：9–12 个决策可解，R2 用 10 个决策成功、终局剩 5）；线索不可用（**否**：线索就在 Observation 里）；策略错误（**是**，首因）。

### R1 `V8-MAP-23-R1-20261017T095837Z-f7a63f5f`（22 决策，`SUPPLY_DEPLETED`）

- 决策 1：`{"tool":"scout"}`（在 A）→ `SCOUT_NOT_AVAILABLE_HERE`；观察变化 `{"actions_taken":1}`。**开局就浪费一个决策**。
- 决策 3：`{"tool":"scout"}` → `SCOUTED:STONE_THREE_RINGS`；`{"clues_received":[{"signal":"STONE_THREE_RINGS","station":"N","supports":["Z"]}],"supply_remaining":11}`。
- 决策 6：`{"entrance":"Z","tool":"investigate"}`（在 A）→ `NOT_AT_ENTRANCE`；`{"actions_taken":6}`。
- 决策 7 / 8：`{"to":"Z","tool":"move"}` ×2（在 A，A 的邻居是 H/N/R）→ `NOT_ADJACENT` ×2；`{}`。
- 决策 10：`{"to":"X","tool":"move"}` → `MOVED:X`；`{"supply_remaining":12}`；决策 11 `{"to":"Z","tool":"move"}`（X 只有邻居 N）→ `NOT_ADJACENT`。
- 决策 13：`{"tool":"scout"}`（在 N，已侦察过）→ `SCOUT_ALREADY_USED`。
- 决策 21：`{"to":"Y","tool":"move"}`（补给 1，N→Y 需 2）→ `INSUFFICIENT_SUPPLY`；决策 22 `{"to":"A","tool":"move"}` → 补给 0，`SUPPLY_DEPLETED`。

**首次偏离：决策 6**。它知道目标是 Z（决策 3），却在 A 直接 `investigate(Z)`；被拒后连续两次尝试 `move(to=Z)`——**A 与 Z 不相邻，`neighbors` 就在 Observation 里**。之后 16 个决策在 N/X/Y 之间来回，直到补给见底。

**失败链**：错误侦察位置 → 在错误节点调查 → 无视 `neighbors` 连续提交不可达移动 → 补满过早（决策 5）→ 22 个决策后归零。

**替代解释**：动作词表把 `investigate(entrance): X, Y, Z` 列成"可尝试的字符串"，不表示当前可执行（prompt 明确这么说），所以"在 A 调查 Z"是被文档允许的尝试；但 `move(to=Z)` 与公开 `neighbors` 直接矛盾，这一条只能算策略错误。

### R2 `V8-MAP-23-R2-20261017T100007Z-e08f6f78`（10 决策，成功）

- 决策 2：`{"tool":"scout"}` → `SCOUTED:STONE_THREE_RINGS`；`supports:["Z"]`，`supply_remaining:11`。
- 决策 6：`{"tool":"resupply"}` → `RESUPPLIED`；`{"supply_remaining":14}`（此前 8）。
- 决策 7：`{"to":"R","tool":"move"}` → `MOVED:R`；`{"neighbors":{"A":2,"Y":1,"Z":2},"supply_remaining":12}`。
- 决策 9：`{"to":"Z","tool":"move"}` → `MOVED:Z`；`{"neighbors":{"R":2},"supply_remaining":8}`。
- 决策 10：`{"entrance":"Z","tool":"investigate"}` → **`TRUE_ENTRANCE_FOUND`**；`{"supply_remaining":5,"terminal":true,"terminal_reason":"TRUE_ENTRANCE_FOUND"}`。

**与 R0 的对照**：两局在几乎同一位置（R）做了相反的决定。R2 在决策 7 到达 R 后**下一步就走向 Z**；R0 在决策 5 到达 R 后走向 Y。这是**同一公开信息、不同决策**的直接证据，说明本图能区分策略，R0/R1 的失败是真实的规划失败而非接口封死。

**重复证据有限**：三局都先侦察 N、都用掉唯一一次补满；R0/R1 的失败形态高度相似（拿到 Z 之后仍在 N/X/Y 之间绕）。n=3、seed=0 固定，**不能区分个体差异与固定陷阱**；不过 R2 证明该陷阱可被同一公开信息绕开。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E**（在 R 不走向 Z；5 次无效/失败动作） | F（28 点补给被绕路耗尽） | 高 | 决策 2/5/7/9/11/16 |
| R1 | **E**（在 A 调查 Z、两次 `move(to=Z)`；无视 `neighbors`） | F（补满过早 + 无效动作不扣费但耗决策） | 高 | 决策 1/3/6/7/10/21 |
| R2 | —（成功） | — | — | 决策 2/7/9/10 |

- **F（资源管理错误）**：两局确实是补给耗尽，但它不是机制性的——总额度 28 点，最短成功路线只要 13 点（Oracle 7 步）。F 是 E 的后果，不列首因。
- **C（schema/接口误导）**：只有"`scout()` 在 A 不可用"和"`investigate` 需要先到入口"两处，而这两条都在公开词表/`goal` 里；且 R2 证明按公开信息可以正确执行。不列首因。
- **D（决策预算）**：38 个决策，两局分别只用了 16/22 就用光补给，不是被决策预算截断。不成立。
- **A（规则缺陷）**：不成立——补给结算、`_stranded` 判定、Oracle 与两条启发式路线全部自洽。
- **H / I**：H 不成立（0 provider 错误）；I 成立（n=3、seed=0，只覆盖真入口 Z）。

## 9. 标签

- **`MEASUREMENT_VALID`（失败信号层面）**：两局失败是真实的规划失败——同一张图上公开启发式 9 个决策成功、R2 用 10 个决策成功，且 R2 与 R0 在同一个节点（R）做出相反选择。规则、补给结算与终止码都自洽。
- **`CONSTRUCT_BYPASS`**：`no_scout` 不侦察、纯盲试也能 12 个决策成功，且 `cost_per_discovery` 与侦察路线**完全相同（11.0）**；加上 H 站对三种真值都给出单元素支持集，"线索值不值它的路费+2 补给"这个构念在成本上没有区分度。
- **`METRIC_DEFECT`**：(1) `clue_utilization` 度量的是"最强线索的信息量"，与是否使用线索无关，两局失败仍是 1.0；(2) `cost_per_discovery` 用 `(14 − 终局 supply)`，忽略一次性补满注入的 6 点，R2 报 9.0 而真实支出 15 点。
- **`LOW_DISCRIMINATION`**：三局指标向量只有一个字段有方差（`cost_per_discovery`），且该字段被补满污染。
- **`INCONCLUSIVE`（条件/变体层面）**：三局 `seed=0` 使 `true_entrance` 恒为 Z，"三个等概率入口"只被采样一个；不能用这 3 局声称线索价值在三个变体上都成立。

## 10. 最小可证伪修复（无证据不修改）

**旧规则/旧公开信息**：

1. `clue_utilization` 定义成"最强单条线索的缩减量 / 2"；
2. `cost_per_discovery = (14 − 终局 supply) / 发现数`，不含补满注入；
3. H 站的三种信号全部是单元素支持集；
4. 正式运行固定 `seed=0`，真入口恒为 Z。

**证据与根因**：三局 `clue_utilization` 全 1.0（含两局失败）；`no_scout` 与侦察路线同价 11.0；R2 的 `(14−5)=9` 与真实支出 15 的差就是补满注入的 6。

**候选 A（首选，只改指标口径，不改规则）**：把 `cost_per_discovery` 改成"真实支出 / 发现数"，即 `(14 + 补满注入量 − 终局 supply) / 发现数`，或直接记录 `supplies_spent` 计数器。预期：R2 从 9.0 变 15.0，`ridge_scout_full_reduction` 从 7.0 变 13.0，侦察路线与盲试路线重新出现差异（需实测确认）。

**候选 B（只改指标语义，不改规则）**：把 `clue_utilization` 改成"已购线索中被后续决策实际使用的比例"（例如：最终调查的入口是否属于某条线索的交集、或路径是否先经过线索指向的入口），否则它只能叫 `clue_information_strength`。预期：R0/R1 从 1.0 掉到 0，R2 保持 1.0，主指标首次能区分成败。

**候选 C（改规则，需 DCR，优先级最低）**：让 H 站的信号不再对三种真值都唯一（例如把 Y/Z 在 H 上合并），恢复"每条线索只缩到两座"的设计意图。这会改变 `rule_hash`，且会与 fixture `ridge_scout_full_reduction`（期望 1.0）冲突，必须同步重算 4 条 fixture。

**候选 D（实验设计，不改规则）**：正式运行覆盖 seed ∈ {0,1,2} 以采样三个真入口变体；否则任何"线索价值"结论都只适用于 Z。若预算不允许，至少要在报告里把 `true_entrance` 固定这一点写明。

**预期变化与构念影响**：A/B 只影响指标层，旧 Trace 仍可复算（需要 extractor 版本升级）；C/D 影响规则或场景覆盖，旧 Trace 不可直接比较。

**反例与回归风险**：

- 只做 A，`clue_utilization` 仍然是常数，主指标依旧无法区分成败。
- 只做 B，`no_scout` 的 0.0 与侦察路线的 1.0 会放大，但这只是"是否侦察"，仍不证明"信息价值"。
- 做 C 会让 MAP-23 明显变难，在 n=3 下无法区分"变难"与"变坏"。
- 任何 `rule_hash` 变更都需要新账本，不能续跑已关闭的 V8 账本。

**若无需修改**：不成立——`cost_per_discovery` 与真实支出差 6 点、`clue_utilization` 在失败局仍报满分，都是可复算的硬事实。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-23.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `river_double_ripples_then_z` | `scenario_success` | 7 | ok=true |
| Oracle `ridge_unique_signal` | `scenario_success` | 7 | ok=true |
| `legal_random` × 20 | 0 成功，20/20 `decision_budget_reached` | 38 | 语义被拒 277（仅 `INVALID*` 前缀） |
| `public_heuristic`（N 侦察 → 回 A 补满 → R → Z，中间多走 H） | `scenario_success` | 9 | utilization 1.0、cost 11.0、repeated 0、ignored 0 |
| 消融 `no_scout`（X→Y→Z 盲试 + 回 A 补满） | `scenario_success` | 12 | utilization 0.0、cost 11.0、repeated 0、ignored 0 |
| V8 三局 | 1/3 | 16/22/10 | utilization 1.0/1.0/1.0；cost N/A/N/A/9.0 |

**独立复算 1（`cost_per_discovery`，手工逐动作记账）**：启发式 9 个动作的补给轨迹是
`14 →(move N,1) 13 →(scout,2) 11 →(move A,1) 10 →(resupply,注入 4) 14 →(move H,2) 12 →(move A,2) 10 →(move R,2) 8 →(move Z,2) 6 →(investigate,3) 3`。
真实总支出 15，注入 4，净 11，终局 3；公式 `(14−3)/1 = 11.0`，与 judge 一致。**同时说明口径问题**：真实消耗 15 点，而指标只报净 11 点，被补满抵掉的 4 点完全不可见。
**独立复算 2（`clue_utilization`）**：线索 `STONE_THREE_RINGS` 的 `supports=["Z"]`，`3 − 1 = 2`，`2/2 = 1.0`，与 extractor 一致；`no_scout` 没有线索，`max(reductions, default=0)=0`，0/2 = 0.0，一致。
**独立复算 3（R2 的 `cost_per_discovery`）**：Trace 的扣费序列为 `1,2,1,1,1,2,2,2,3`（决策 1–10 中的扣费动作），合计 15；决策 6 的 `resupply` 注入 6，终局 5，故 `(14−5)/1 = 9.0`，与 judge 一致；真实支出 15，指标少计 6。

**区分度**：`clue_utilization` 只能区分"是否侦察"（1.0 vs 0.0），不能区分成败（失败局也是 1.0）；`cost_per_discovery` 区分 9.0/11.0/11.0，但被补满口径污染；两局失败与一局成功在 `repeated_invalid_exploration`、`ignored_counterevidence` 上完全相同。记 **`LOW_DISCRIMINATION`**。

## 12. V9 状态

**`NEEDS_REDESIGN`（P1）**。理由：失败归因是干净的（R0/R1 是真的策略错误，R2 证明同一公开信息可解），但这条结论目前**只能由 `clue_utilization` 之外的证据支撑**——主指标在两局失败时仍是满分 1.0，`cost_per_discovery` 又漏算一次性补满的 6 点，三局指标里只有一个字段有方差。在修好这两个口径并至少覆盖一个非 Z 变体之前，MAP-23 的 1/3 只能读作"两次规划失败"，不能读作"线索价值判断能力"的测量。
