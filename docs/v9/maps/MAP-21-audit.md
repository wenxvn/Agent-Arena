# MAP-21 审计：喷发倒计时

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-21 / volcano / 困难 |
| condition | `default` |
| `rule_hash` | `59675a2c82400a7f571fedecfeed78ebea4f72e963778a0efd58816e4f08439e` |
| `scenario_hash` | `9bd77d5dcb8ae60fe9cd78bbc9343e9fd13d316ff46c57e75f1fa96b679085f9` |
| `source_hash` | `1223109c8bd0460ed3d2922008a50a2e1ad4d7da61bb776ac98b1ac3dbfce156` |
| `prompt_hash` | `d1480bc9838f9d5b9f8b9af0e732fa38eef85b4a7ea692b03da6314722df1338` |
| `metric_schema_hash` | `98f4748000a0c1505103576ce538cda62050a1eb1dda71fd3ae3d87724f69ed9` |
| 决策预算 | 46 |
| V8 三局 | 3/3 成功，全部 `EVACUATED_BEFORE_ERUPTION`；决策 2 / 1 / 2 |

数据来源：`runs/v9/evidence/MAP-21.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-21-final.md`、`worlds/v4/MAP-21/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map21.py`、`src/agent_arena/v8/prompts.py`。本审计新增的只读产物为 `runs/v9/baselines/MAP-21.json`、`src/agent_arena/v9/policies/world_volcano.py`，以及 §11 的离线探针（只在本机内存中重放，不写 Trace）；未改写任何 V8 文件、账本或 Trace。

## 1. 能力构念

这张图声称测的是**在隐藏喷发时刻下的风险条件停手能力**：喷发只可能是 12/16/20 之一且不可见；唯一的信息动作是在 O 花 2 tick 做一次有噪测量；样品从 1 tick 的低阶灰样到 6 tick 的深部同位素，撤离路线只有 6 tick 的直达边和 7 tick 的链式边。

- 成功行为（V8 判定）：在隐藏喷发 tick 之前（或同一 tick）进入 E。
- 明确反例：为了多取一档样品而错过喷发，在非 E 位置被喷发吞掉（`FATAL_ERUPTION`）。
- 递进位置：本图是该世界的**困难**图，但递进方式是“换机制”而不是“加复杂度”：MAP-19/20 是确定性热/水控制，本图没有温度、没有流量，只有隐藏时刻、有噪测量和样品价值。

**构念与成功判定之间存在缺口（事实）**：V4 `map_spec.yaml` 的 `scoring` 把安全撤离记 100、测量记录 +2、样品分只在带回 E 时计，并明确 `terminal_success: player_enters_E_at_or_before_hidden_eruption_tick`；`terminal_score` 只写进 `judge_state`（`map21.py::judge_state` 的 `terminal_score`），**既不参与成功判定，也没有登记成 V8 指标**。也就是说，构念里的“科研价值 vs 风险”在 V8 里没有出口。

## 2. 机制与因果链

**本图专属因果链**

1. 起始状态：`location=O`、`elapsed_tick=0`、`posterior_over_eruption_ticks={"12":0.2,"16":0.5,"20":0.3}`、`available_edges={"O_E":{"ticks":6,"to":"E"},"O_R":{"ticks":1,"to":"R"}}`、`measurement_available=true`。
2. 必需观察（若走“风险决策”构念）：`posterior_over_eruption_ticks`、`returned_measurement`、`available_edges[].ticks`、`visible_local_sample_tier`、`reinforcement_kit_available`。
3. 关键决策（构念内）：是否花 2 tick 测量；测到早/晚报后是否改走低阶样品；是否加固中阶样品；何时停手转向 E。
4. 立即后果：`move` 按边的 tick 数推进时钟，途中 `in_transit_edge` 可见；每 tick 若位于 E 则立即成功，否则在 `tick >= eruption_tick` 时 `FATAL_ERUPTION`；采集与加固各消耗固定 tick。
5. 终局：进入 E → `EVACUATED_BEFORE_ERUPTION`；被喷发追上 → `FATAL_ERUPTION`。

**可绕过点（事实，且可由公开信息证明）**

- 直达边 `O_E` 的耗时是 **6 tick**，而 `posterior_over_eruption_ticks` 的键公开了喷发时刻只可能是 **12/16/20**。因此 `6 < 12 <= eruption`，一次 `move O_E` 在任何隐藏时刻下都必然早于喷发。
- 同刻抵 E 的优先级也已公开（goal：“喷发同步抵 E 时撤离优先”；代码 `_after_tick` 先结算到达、再判喷发），所以连“第 12 tick 恰好到达”也不会失败。
- 推论：**测量、样品、加固、风险评估全部不是成功所必需**。测量只把最坏到达从 6 推到 8（仍 `< 12`），并且会把 `evacuation_coverage` 的分母从 1 抬到 2。

| 核心机制 | 是否成功所需 | 三条真实轨迹中的实际使用 | 证据 |
|---|---|---|---|
| 测量（2 tick，有噪） | 否 | R0/R2 各用 1 次，但后验没有改变动作；R1 未用 | R0 决策 1、R2 决策 1、R1 决策 1 |
| 样品（1/5/6 tick） | 否 | 0 次 | 三局 `carried_sample_tier=null`、`visible_local_sample_tier` 始终为 `null` |
| 加固（1 tick） | 否 | 0 次 | 三局从未到达 W/S，`reinforcement_kit_available` 在 O/E 均为 `false` |
| 风险评估（后验→停手） | 否 | 无“停手”决策点 | 6 tick 直达边在 tick 0 就可见，`6 < 12` 已给出确定性安全 |

**机制是否在三条轨迹中实际触发（引用决策序号）**

- R0/R2 决策 1 `measure` → `MEASURED:LATE_WARNING`，后验从 `{"12":0.2,"16":0.5,"20":0.3}` 变为 `{"12":0.060606060606,"16":0.530303030303,"20":0.409090909091}`：**测量机制实际触发**。
- 但 R0/R2 决策 2 与 R1 决策 1 的动作完全相同（`move O_E`）：**后验没有改变任何决策**。样品与加固在三条轨迹中 0 次触发。
- R1 只有 1 个决策，说明“风险条件停手”这个构念在真实轨迹里从未被要求。

**触发所需最小动作数**：成功 1 个（`move O_E`）；测量 1 个（`measure`，自带 2 tick）；样品 1 个（`collect_and_carry_sample`，自带 1/5/6 tick）；加固 1 个（`reinforce_sample_case`，自带 1 tick）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `available_edges[].ticks`（O_E=6、O_R=1、R_W=2、W_S=2、S_E=2） | 是 | 每步（当前节点相邻边） | **是：6 与最早 12 的关系直接可读** |
| `posterior_over_eruption_ticks` 的键 `12/16/20` 与权重 | 是 | 初始即公开；测量后更新 | **是：喷发候选集公开，隐藏的只是哪一个** |
| `measurement_available` / `returned_measurement` | 是 | 每步 | 是（但见下：对成功无影响） |
| 喷发真值 `eruption_tick` | 否 | — | 不需要（6 已足够安全） |
| 测量耗时 2 tick | 是（词表 “measure()（2 tick）” 与 goal） | 初始 prompt | 是 |
| 测量似然 `EARLY_LIKELIHOOD`、抽样值 | **否**：只公开更新后的后验 | 只能看到结果 | 不影响成功；只影响信念 |
| 样品耗时/分值（1/5/6 tick、5/12/40 分） | **否**：词表与 goal 都没有 | 只能靠尝试 | 否（无法先验判断采样是否值得） |
| 加固 1 tick 与“只保护本站样品” | 部分：goal 说 1 tick 加固 | 初始 prompt | 否（分值规则仍隐藏） |
| `visible_local_sample_tier.tier` | 是，但返回的是 `sample_id.split("_")[0]`，即 `R`/`W`/`S` 而不是 `low/medium/high` | 到达 R/W/S 时 | 字段名与实际值不一致（C 类小瑕疵） |
| `terminal_score` | **否**：只进 `judge_state` | — | 不参与成功与指标 |
| `judge_state`（`eruption_tick`、`posterior` 原始权重、`exposure`） | 否 | — | 不应被使用 |
| Oracle 路径（`ORACLE_CASES`、`oracle_trace.jsonl`） | 否 | — | 不参与运行时 |

结论：本图不存在“必须知道隐藏规则才能避免秒失败”的情况；相反，**仅凭初始 Observation 就能证明直达撤离必然安全**。因此不标 `INTERFACE_BLOCKED`。

## 4. 可解性与可观察性

- Oracle：3 个用例，`exact_boundary_medium_sample`（5 动作）、`early_evacuation`（1 动作）、`deep_reinforced_sample`（6 动作），`oracle_ok=3/3`（`runs/v9/baselines/MAP-21.json`）；3 个手算 fixture 全部 OK（`scripts/check_v8_map.py MAP-21`）。
- **最短可行公开策略（逐步）**：
  1. tick 0，读到 `available_edges` 含 `O_E: {ticks: 6, to: E}` 与 `posterior_over_eruption_ticks` 的键 `{12,16,20}`；
  2. 提交 `{"tool":"move","edge_id":"O_E"}`；
  3. tick 6 到达 E，`EVACUATED_BEFORE_ERUPTION`。
  仅 1 个决策、0 次测量、0 件样品、0 次加固。
- **2 决策版本**：`measure` → `move O_E`，tick 8 到达，同样成功；它是 `Map21Heuristic` 的默认策略，用来证明“即使做测量也仍有余量”。
- **证明（公开信息，非隐藏真值）**：
  - 边的耗时 6 来自 `available_edges`；
  - 最早喷发 12 来自公开后验的键；
  - `6 < 12`，且 `move` 的时间只由边耗时推进；途中每 tick 仍会判喷发，但 tick 6 之前不会达到任何候选喷发时刻（12/16/20）；
  - 同刻到达优先（goal 文本 + `_after_tick` 的到达先于喷发），覆盖 `tick == eruption` 等号情形；
  - 因此对 `eruption ∈ {12,16,20}` 的任意取值，存活概率都是 1.0（与 V4 `evidence_or_rules.yaml::direct_evacuation.survival_probability: 1.0` 一致）。
- 因此不标 `BUDGET_BLOCKED`（用 1/46 个决策）也不标 `INTERFACE_BLOCKED`。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| 决策预算 | 46 |
| Oracle 动作数 | 5 / 1 / 6 |
| 公开启发式动作数 | 2（`measure` + `move O_E`） |
| 消融 `shortcut_direct_evac` 动作数 | **1**（`move O_E`） |

`legal_random` 20 seed：成功 **6/20（30%）**，其余 14 局 `decision_budget_reached`；非法动作 0、被拒动作 **355**；决策数 2–46。随机成功的原因不是“随机策略聪明”，而是**语义非法的 `move` 不消耗 tick**（`map21.py::_move` 对 `INVALID_EDGE` 直接返回、`_cost` 保持 0），所以随机策略可以在 46 个决策内零时间试出 `O_E`；14 个失败局大多停在 `elapsed_tick=2–3`，时钟根本没走。

**判定：既不是预算不够，也不是随机策略有能力，而是成功动作只有 1 个且可以被盲试出来。** 46 个决策对 1 个必要动作而言是 46 倍冗余。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾规则 | 三局取值 |
|---|---|---|---|---|---|
| `map21.evacuation_coverage` | primary | `evacuated_units / invested_units`；`invested = 1(人员) + 1(已采样品) + 1(已测量)`；成功时 `evacuated = invested`，失败时 0 | 已投入单位 | 分母为 0 → N/A；预算截尾 → CENSORED | R0=2/2、R1=1/1、R2=2/2，投影均为 1.0 |
| `map21.risk_exposure_integral` | primary | Σ 在 E 之外且未死亡 tick 的 `P(T<=t \| 当前后验)`；死亡 tick 计入，抵 E tick 不计 | 有效 tick 数（实现返回未归一化的和） | 同上 | 三局均为 0.0 |
| `map21.false_safety_claims` | guardrail | 现有动作集没有“安全承诺”动作，`metrics()` 恒返回 `None` | episode | 规则要求“缺来源事件 → UNAVAILABLE” | 三局均 `null`，投影为 `not_applicable` |
| `map21.late_evacuation` | diagnostic | `FATAL_ERUPTION` 记 1、成功记 0、运行中 `None` | 发生喷发的 episode | 同上 | 三局均为 0 |

**`evacuation_coverage` 的分母为什么 R1 是 1、R0 是 2（读 `map21.py::metrics`）**

```python
invested = 1 + (1 if self.sample_collected else 0) + (1 if self.measurement_used else 0)
evacuated = invested if self.is_success else 0
```

- R1（`V8-MAP-21-R1-…-3d9c410d`）：只有人员 1 个单位，没测量、没样品 → 分母 **1**，`evacuated=1` → 1/1。
- R0（`V8-MAP-21-R0-…-a4e73f43`）：人员 + 一次测量记录 → 分母 **2**，`evacuated=2` → 2/2。
- 也就是说，分母不是“人数”，而是“**投入资产单位数**”：测量记录与样品都被当作必须一起撤出的资产。`numerator` 在成功时被定义成与分母相等的 `invested`，所以这个比例在成功路径上**恒为 1.0**，在失败路径上恒为 0.0——它是成功/失败的 0/1 指示器，不是“撤出了多少”的连续量。
- 附带效果：测量会让分母变大；一旦失败，测量过的局（0/2）比没测量的局（0/1）看起来“覆盖更差”，于是**测量在指标上被弱支配**。

- **未通关仍有意义的连续主指标**：只有 `risk_exposure_integral`，但它的方向是 `lower_is_better`，而且直达路线的暴露恒为 0——它奖励的正是绕过。
- **N/A / censored**：三局各 1 条 `not_applicable`（`false_safety_claims`）。这是**真分母 0 / 无来源事件**，按指标卡应记 `UNAVAILABLE`，但 `src/agent_arena/v8/metrics.py::_empty_status` 对非 censored 结局统一返回 `not_applicable`，属投影口径问题（`docs/v9/data-integrity.md` §4.1 已登记）。
- **判别力**：`LOW_DISCRIMINATION`。三条真实轨迹（1 动作直达、2 动作测量后直达）的 coverage/late/risk **完全相同**（1.0 / 0 / 0）；启发式（2 动作、含测量）与 shortcut（1 动作、无测量）也完全相同。只有“深部加固样”这种失败/高风险路线才会让 risk 变成 0.2/0.4，而它恰好是被成功判定排除的路线。

## 7. 三次轨迹归因

### R0（`V8-MAP-21-R0-20261017T094201Z-a4e73f43`，`success`，2 决策，tick 8）

- 决策 1：`{"tool":"measure"}` → `MEASURED:LATE_WARNING`，观察变化 `{"elapsed_tick":2,"measurement_available":false,"posterior_over_eruption_ticks":{"12":0.060606060606,"16":0.530303030303,"20":0.409090909091},"returned_measurement":"LATE_WARNING"}`。
- 决策 2：`{"edge_id":"O_E","tool":"move"}` → `MOVING:O_E`，观察变化 `{"available_edges":{"O_E":{"ticks":6,"to":"O"},"S_E":{"ticks":2,"to":"S"}},"elapsed_tick":8,"location":"E","terminal":true,"terminal_reason":"EVACUATED_BEFORE_ERUPTION"}`。

**首次偏离合理策略的可观测事件**：无偏离。**但这正是问题**：决策 1 花 2 tick 换来的后验（`12: 0.061`）没有改变决策 2；决策 2 与不做测量的 R1 完全同构。
**失败链**：无（成功）。**替代解释**：不能把这局解释为“模型完成了风险条件停手”，因为没有出现任何“停手/放弃采样”的决策点；它只是先测量再走最短边。

### R1（`V8-MAP-21-R1-20261017T094213Z-3d9c410d`，`success`，1 决策，tick 6）

- 决策 1：`{"edge_id":"O_E","tool":"move"}` → `MOVING:O_E`，观察变化 `{"available_edges":{"O_E":{"ticks":6,"to":"O"},"S_E":{"ticks":2,"to":"S"}},"elapsed_tick":6,"location":"E","terminal":true,"terminal_reason":"EVACUATED_BEFORE_ERUPTION"}`。

**首次偏离合理策略的可观测事件**：无（这是最短成功序列）。这局证明 `move O_E` 一个动作就够，且始终为 `true` 的 `measurement_available` 被完全忽略。
**失败链**：无。**替代解释**：这局不能作为“风险评估能力”的证据——它没有读取或使用后验。

### R2（`V8-MAP-21-R2-20261017T094219Z-6177107b`，`success`，2 决策，tick 8）

- 决策 1：`{"tool":"measure"}` → `MEASURED:LATE_WARNING`，观察变化 `{"elapsed_tick":2,"measurement_available":false,"posterior_over_eruption_ticks":{"12":0.060606060606,"16":0.530303030303,"20":0.409090909091},"returned_measurement":"LATE_WARNING"}`。
- 决策 2：`{"edge_id":"O_E","tool":"move"}` → `MOVING:O_E`，观察变化 `{"available_edges":{"O_E":{"ticks":6,"to":"O"},"S_E":{"ticks":2,"to":"S"}},"elapsed_tick":8,"location":"E","terminal":true,"terminal_reason":"EVACUATED_BEFORE_ERUPTION"}`。

**首次偏离合理策略的可观测事件**：无。R0 与 R2 的动作序列逐字相同，只有 run_id/费用不同。
**失败链**：无。**替代解释**：三局中两局完全相同、一局少一步；**重复证据极有限**，n=3 只说明“直达边存在且被看见”，不能说明模型具备隐藏时刻推理。

**补充（证据覆盖）**：三局 `judge_state.eruption_tick` 均为 **16**（离线回放 seed=0 一致；测量结果 `LATE_WARNING` 也与 seed 0 的抽样值 0.42 ≥ 0.3 一致）。V8 的 90 局是同一实例的重复运行，不覆盖 `eruption=12` 与 `20`。因此“12 同刻抵 E 安全”这条最关键边界只由代码与 fixture 保证，**没有被任何正式 Trace 覆盖**。

## 8. 失败分类

三局均成功，没有可归因的失败局；下表归因的是“构念为何失效”。

| 对象 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| 本图构念 | A 环境规则缺陷（成功判定只要求进 E，`terminal_score` 不进成功也不进指标） | B 公开信息不足（样品耗时/分值与测量似然未公开，公开观测里没有任何“采样有收益”的信号）；C 接口误导（语义非法 `move` 不耗时，可零时间盲试） | 高 | `map21.py::_after_tick`、`metrics()`、`_move`；`worlds/v4/MAP-21/map_spec.yaml::scoring`；随机 6/20、355 次被拒 |
| 正式证据 | I 证据不足（只有 seed 0 / 喷发 16，最坏 12 未出现） | — | 高 | 三局 `judge_state.eruption_tick=16`；`_seed_fixture(0)=(16,0.42)` |

## 9. 标签

- `CONSTRUCT_BYPASS`：一张“困难”图被 1 个 `move O_E` 决策 100% 通关（启发式 1/1、随机 6/20）；测量/样品/加固/风险评估全部不需要。公开信息本身（6 tick vs 最早 12）就足以证明直达必然安全。
- `METRIC_DEFECT`：① `evacuation_coverage` 的分子在成功时被定义成等于分母，恒为 1.0，是 0/1 指示器；② 分母把测量记录算作“投入资产”，测量反而弱支配自己；③ `terminal_score`（100/102/112/150）未登记为指标；④ `false_safety_claims` 无来源事件，应按 `UNAVAILABLE` 记录却投影为 `not_applicable`。
- `INCONCLUSIVE`（仅针对 `risk_conditioned_stopping` 构念）：正式 90 局只覆盖 `eruption=16`，最坏 `12` 从未在真实 Trace 中出现；不能从 3/3 推断风险决策能力。

## 10. 最小可证伪修复（无证据不修改）

**候选 A（推荐，指标层，不改规则）**：重定义 `evacuation_coverage` 的分母为固定 3（人员 + 一件可携带样品 + 测量记录），或改为“已撤出/已投入”并以**真实撤出单位**作分子；同时登记 `map21.terminal_score` 与 `map21.sample_points` 为 primary。
- 证据与根因：`metrics()` 的 `evacuated = invested if success` 是自指；shortcut（1/1）与启发式（2/2）无法区分；`terminal_score` 100/102/112/150 已经存在但没有出口。
- 预期变化：直达撤离的 coverage 变为 1/3，测量后直达 2/3，测量+中阶样 3/3，指标第一次能排序“保人”与“保科研”。
- 反例与回归：分母固定为 3 会让“没有携带样品”的失败局也记 1/3；需要同时明确“可携带样品”是否只有一件，否则会把“没去采”当成“采了没带回”。

**候选 B（规则层，需新 spec）**：成功条件加入最低科研价值，例如 `terminal_score >= 110` 或“必须带回至少一件样品”。
- 证据与根因：`_after_tick` 只要进 E 就 `_succeed`，样品分只在 `terminal_score` 里；V4 的 `expected_utility` 设计意图没有落到成功判定。
- 预期变化：直达 100 分不再成功，测量后直达 102 仍不成功，中阶样 112 成功，深部加固在 12 喷发时失败——风险停手第一次成为必需。
- 反例与回归：这是改规则，V8 Trace 不可直接回放，必须新 `scenario_hash`/`rule_hash`；并且需要重新证明“存在 ≥110 且对所有隐藏时刻安全的路线”（现有 probe 显示中阶样 112 在 12/16/20 下都成功，可以作为新 Oracle 候选）。

**候选 C（场景参数，需 spec）**：保留成功判定，改拓扑/时刻——例如把 `O_E` 拉长到 13 tick，或把最早喷发压到 6 tick 以下，使直达不再必然安全。
- 证据与根因：`6 < 12` 是绕过的充分条件；只要这条不等式成立，任何以“进 E”为成功的判定都会被 1 动作击穿。
- 预期变化：测量与样品重新获得决策价值。
- 反例与回归：会改变 `scenario_hash`，且需要重算全部 Oracle/fixture；比候选 A+B 的改动更大，优先级最低。

**候选 D（实例 seed，不改规则，配合 A）**：V9 正式运行必须覆盖 `eruption=12/16/20` 三个实例（离线探针已找到 seed 2/0/4），不能再用同一实例重复 3 次。
- 证据与根因：三局都是 `eruption=16`；最坏边界 `12` 没有 Trace。
- 预期变化：`late_evacuation`、`risk_exposure_integral` 第一次有真实方差。
- 反例与回归：只增加实例覆盖，不改规则；但需要新 experiment ID 与预算，不得复用已关闭账本。

**优先级**：A + D 先做（不改规则、可逆、直接修复 `METRIC_DEFECT` 与证据覆盖）；B 或 C 二选一，若研究目标确实是 `risk_conditioned_stopping`，B 更贴近构念，C 更贴近“风险”本身。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-21.json`：

| 策略 | 成功 | 决策 | 终止码 | coverage | late | risk | terminal_score |
|---|---|---|---|---|---|---|---|
| Oracle `exact_boundary_medium_sample` | 是 | 5 | `EVACUATED_BEFORE_ERUPTION` | 1.0（2/2） | 0 | 0.0 | 112 |
| Oracle `early_evacuation` | 是 | 1 | `EVACUATED_BEFORE_ERUPTION` | 1.0（1/1） | 0 | 0.0 | 100 |
| Oracle `deep_reinforced_sample` | 是 | 6 | `EVACUATED_BEFORE_ERUPTION` | 1.0（2/2） | 0 | 0.4 | 150 |
| `legal_random`（20 seed） | 6/20 | 2–46 | 6×成功、14×预算 | — | — | — | — |
| `public_heuristic` | 是 | **2** | `EVACUATED_BEFORE_ERUPTION` | 1.0（2/2） | 0 | 0.0 | 102 |
| 消融 `shortcut_direct_evac` | 是 | **1** | `EVACUATED_BEFORE_ERUPTION` | 1.0（1/1） | 0 | 0.0 | 100 |

**独立复算（手算，不复用 `map21.metrics()`）**：

| 局 | 投入单位 | 撤出单位 | 我的 coverage | judge | 我的 risk | judge |
|---|---|---|---|---|---|---|
| R0 | 1 人员 + 1 测量 = 2 | 2 | 2/2 = 1.0 | 1.0（2/2） | `Σ_{t=1..7} P(12<=t)=0`（t=8 抵 E，不计） | 0.0 |
| R1 | 1 人员 = 1 | 1 | 1/1 = 1.0 | 1.0（1/1） | `Σ_{t=1..5} 0 = 0`（t=6 抵 E） | 0.0 |
| R2 | 2 | 2 | 1.0 | 1.0（2/2） | 0 | 0.0 |
| 深部加固 @16（fixture 同构） | 1 + 1 样品 = 2 | 2 | 1.0 | 1.0 | t=12,13 各 `P(12)=0.2` → 0.4 | 0.4 |
| 深部加固 @12（离线探针） | 2 | 0 | 0.0 | 0.0（0/2） | t=12 死亡 tick `P=0.2` → 0.2 | 0.2 |

**离线探针（只读复算，不是正式实验）**：用 `_seed_fixture` 找到 `eruption=12/16/20` 的实例 seed 为 **2 / 0 / 4**，在同一规则下重放四条路线：

| 路线 | 到达 tick | @12 | @16 | @20 |
|---|---|---|---|---|
| `move O_E` | 6 | 成功 100 | 成功 100 | 成功 100 |
| `measure` → `move O_E` | 8 | 成功 102 | 成功 102 | 成功 102 |
| `O_R→R_W→采 W→W_S→S_E` | 12 | **成功 112**（同刻优先） | 成功 112 | 成功 112 |
| `…→S→加固→采 S→S_E` | 14 | **`FATAL_ERUPTION`**（risk 0.2） | 成功 150（risk 0.4） | 成功 150（risk 0.4） |

这张表是 §4“必然安全”证明的实证版本：直达与“测量后直达”在**三个**隐藏时刻下都成功；中阶样恰好在 12 同刻到达也成功；只有深部加固样在 12 时失败。它同时说明：**唯一带风险的路线，是唯一被 V9 指标判为更差（risk 0.4 或死亡）的路线**。

**判别力**：`LOW_DISCRIMINATION`。在成功路径上 coverage/late/risk 对 1 动作、2 动作、5 动作三种策略给出完全相同的值；只有失败/深部路线才产生差异，而失败路线不参与“能力”排序。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P0**。

理由：一张标注“困难”的图可以被 1 个公开可见的 `move O_E` 100% 通关，随机基线 6/20 也能撞上；测量、样品、加固与风险评估在三条真实轨迹中要么未被使用、要么不改变动作，而现有指标对“直达”和“完整机制”给出完全相同的分数。这是 `CONSTRUCT_BYPASS` + `METRIC_DEFECT`，不是模型能力问题；在任何后续模型实验之前必须先修成功判定或指标口径，否则 MAP-21 的成功率不能解释为风险决策能力。
