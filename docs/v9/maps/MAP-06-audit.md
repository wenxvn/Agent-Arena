# MAP-06 审计：暴风眼

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-06 / lighthouse / 困难 |
| condition | `default` |
| scenario_hash | `f7ed000d38c6c5d74b3d947bc314c3560c26ec71259d6eee930a38599b2ee9ac` |
| rule_hash | `2adb4f3322d07b95fb81113a52d0b3e2a818fd464ada905ad630ae5b8c0e508f` |
| 决策预算 / step_limit | 46 / 160 |
| V8 三局 | R0 success `LAMP_RESTORED` **2** 决策；R1 success 3 决策；R2 success 3 决策 → **3/3** |

数据来源：`runs/v9/evidence/MAP-06.json`（本审计的 Observation 引用全部来自该证据包与 `scripts/v9_show_map.py MAP-06`）、`docs/v9/run-index.csv` 第 17–19 行、`docs/v8/maps/MAP-06-final.md`、`worlds/v4/MAP-06/{map_spec.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map06.py`、`runs/v9/baselines/MAP-06.json`。

> 本图是 30 图中 3 张"3/3 全成功"之一，也是本批**唯一需要判定机制旁路**的图。下面的判定基于规则源码 + 10 个注册 seed 的离线复算，不是基于 V8 单局观察。

## 1. 能力构念

- **定义**：在"天气不可观测、只有 80% 条件预报"的前提下，用风险预算做**信息获取与防护投入之间的取舍**——花 tick 读预报，或者花 tick 去加固，二者都要付出时间成本。
- **成功行为**：`lamp_restored=true` 且 `risk ≤ 4`，在 `deadline_tick=14` 前完成；按设计稿还要求在这一批 seed 上取得更高的期望效用。
- **明确反例**：长风暴下不加固直接修（`risk` 会到 7 > 4 → `RESOURCE_EXHAUSTED`）；或者为了省 tick 而完全不处理天气，把一切交给运气。
- **本图在三图递进中的位置**：唯一的"私有天气 + 随机（按 seed 固定）结果 + 资源预算"图；MAP-04/05 是确定性时序题，本图本应是"不确定性下的决策"题。

## 2. 机制与因果链

```
起始 Q, tick0, risk=0, risk_budget=4, deadline=14, weather=私有（short|long）
  → 必需观察：risk/risk_budget/deadline、forecast_accuracy=0.8、prior_short=prior_long=0.5、weather_observable=False
  → 关键决策：三选一
       (a) 直达 Q_P(1 tick, 暴露) + repair(2 tick)      → 2 决策、tick 3
       (b) 读预报 inspect(2 tick) 后再按读数选 (a) 或 (c) → 3–6 决策
       (c) 绕行 M_Q(1)+M_G(2) + harden(3) + G_P(2) + repair(2) → 5 决策、tick 10
  → 立即后果：weather=long 时，暴露移动每 tick +1 risk、无盾修复每 tick +3 risk；
              weather=short 时 risk 完全不变
  → 终局：risk>4 → RESOURCE_EXHAUSTED；tick≥14 未修好 → REPAIR_DEADLINE_MISSED；修好 → LAMP_RESTORED
```

**核心机制在 V8 三局里的触发计数**：

| 事件 | R0 | R1 | R2 | 依据 |
|---|---|---|---|---|
| 暴露边通行（`Q_P`） | 1 tick（决策 1） | 1 tick（决策 2） | 1 tick（决策 2） | `EXPOSED_EDGES={Q_P,G_P}`，`_exposure_ticks=cost` |
| 长风暴 tick（`weather=long`） | **0** | **0** | **0** | `high_risk_exposure_ticks=0`、`risk=0` |
| 风险累积事件 | **0** | **0** | **0** | `risk` 恒 0，`high_risk_ticks` 恒 0 |
| `harden`（加固） | 0 | 0 | 0 | trace 无 `interact G/harden` |
| `inspect(forecast)`（读预报） | **0** | **0** | **0** | `observation_cost=0`、`forecast_queries=0` |
| 修复 | 1（决策 2） | 1（决策 3） | 1（决策 3） | `REPAIR_STARTED` |

**V8 的 seed 固定为 0，而 `WEATHER[0]="short"`**（`map06.py` 第 50–61 行；`agent_arena/v8/runner.py` 的 `spec.seed` 默认 0，90 局全部未改）。这条推断有独立可证伪证据：**同一条 2 决策路径在 seed 5（long）会在 tick 3 `RESOURCE_EXHAUSTED`**（本审计实测，见 §5 的 `shortcut` 扫描），而 V8 R0 在 tick 3 得到 `LAMP_RESTORED` 且 `risk=0`。

**因此：本图的核心机制在三次正式运行中一次也没有触发。** 三条轨迹走的都是 (a) 直达：`Q_P` 只要 1 tick，`repair` 只要 2 tick，天气恰好是 short，风险永远为 0。

### 最短可行公开策略（实测）

**seed 0（V8 实际条件，2 个决策）** —— 与 V8 R0 完全一致：

1. `{"tool":"move","edge_id":"Q_P"}` → `MOVED:P`（tick 1，经过暴露边但 short 风暴不记风险）
2. `{"tool":"interact","target_id":"P","operation":"repair_lighthouse"}` → `REPAIR_STARTED`，tick 3 结算 → `LAMP_RESTORED`

**稳健最短（对 10 个注册 seed 都成立的最小决策数，5 个决策）** —— `public_heuristic` 实测 10/10 成功：

1. `{"tool":"move","edge_id":"M_Q"}` → `MOVED:M`（tick 1，sheltered）
2. `{"tool":"move","edge_id":"M_G"}` → `MOVED:G`（tick 3，sheltered）
3. `{"tool":"interact","target_id":"G","operation":"harden"}` → `STORM_SHIELD_READY`（tick 6）
4. `{"tool":"move","edge_id":"G_P"}` → `MOVED:P`（tick 8，暴露 2 tick：long 下 risk=2）
5. `{"tool":"interact","target_id":"P","operation":"repair_lighthouse"}` → `REPAIR_STARTED`，tick 10 → `LAMP_RESTORED`

注意：这条稳健策略**不读预报**。预报只影响时间（short 下 3 tick vs 10 tick），不影响成败；而 V8 的成败判定是二值的，所以预报在成功维度上的价值为 0（§6、§11 给出量化）。

**机制触发所需最小动作数**：2（`Q_P` + `repair`）——但只有在 `weather=long` 时才会触发；在 short 下这 2 个动作直接通关。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `risk`、`risk_budget=4`、`deadline_tick=14`、`tick`、`location`、`visible_edges` | 是（Observation） | 每步 | 是（目标可读：修好且风险 ≤4） |
| `forecast_accuracy=0.8`、`prior_short=0.5`、`prior_long=0.5` | 是 | 每步 | 是（先验与准确率可读） |
| `weather_observable=False` | 是 | 每步 | 是（明确告知天气不可观测） |
| `forecast_reading` | 是，但仅 `inspect(forecast)` 之后 | 读预报后 | 是，但只有 80% 正确 |
| 规则"哪些边是暴露边" | **未公开**（`EXPOSED_EDGES` 只在代码里） | — | 否 |
| 规则"long 下暴露 1 tick +1、无盾修复 1 tick +3" | **未公开**（`_after_tick`） | 只能事后从 `risk` 反推 | 否——无法在事前算"这条路线是否超预算" |
| 规则"加固只对修复生效、修完即失去盾" | **未公开** | 尝试后 | 否 |
| 返回码语义 | 是（结果反馈） | 尝试后 | 部分；`inspect` 的 `target_id` 要写 `forecast` 而不是 `Q` |
| system prompt 词表 | 是：`inspect(target_id): forecast`、`interact: P/repair_lighthouse, G/harden`、`位置对象：Q=forecast；P=repair_lighthouse；G=harden` | 开局 | 是（但"Q=forecast"这一行诱导了两局的错误 `inspect`） |
| hidden `judge_state`：`weather`、`forecast_queries`、`high_risk_ticks` | 否 | — | 不影响解题 |
| 10-seed 联合分布表（4 short/short、1 short/long、4 long/long、1 long/short） | **未公开**（只在 `map_spec.yaml` 与代码） | — | 否；模型只知道 0.8 与 0.5/0.5 |
| Oracle 路径（4 个用例） | 否 | — | — |

结论：**目标与预算公开，风险模型不公开**。模型可以知道"风险不得超过 4"，但无法知道"哪条路会加多少风险"——它只能靠付出 `RESOURCE_EXHAUSTED` 的代价去学。在一个 seed 固定、只跑 3 局的评测里，这等于不可学。

## 4. 可解性与可观察性

- Oracle：4/4 ok —— `immediate_short`(2)、`harden_long`(5)、`forecast_short_correct`(3)、`forecast_long_correct`(6)。
- **仅凭公开 Observation 的可执行策略存在**，已实测两条：
  - `Map06Shortcut`（2 决策，只在 short 天气成功；seed 0 成功）；
  - `Map06Heuristic`（5 决策，10/10 seed 全部成功，`risk` 0 或 2）。
  - 两条都只读公开字段。区别是：前者在 5/10 个注册 seed 上失败，后者 10/10 成功。
- **这不构成 `INTERFACE_BLOCKED`**（有可赢的公开策略），但构念层面有更严重的问题：**公开信息不足以做"风险算术"**，因此"用风险预算做取舍"这一构念无法从公开信息执行，只能靠规则知识硬编码（本审计的策略就是这种情况，已在模块 docstring 里声明）。这一点属于 §8 的 **B**。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 备注 |
|---|---|---|---|
| Oracle `immediate_short` | 2 | `LAMP_RESTORED` | seed 0 |
| Oracle `harden_long` | 5 | `LAMP_RESTORED` | seed 5 |
| Oracle `forecast_short_correct` | 3 | `LAMP_RESTORED` | seed 0 + 读预报 |
| Oracle `forecast_long_correct` | 6 | `LAMP_RESTORED` | seed 5 + 读预报 |
| `legal_random` ×20 | 7–12 | `REPAIR_DEADLINE_MISSED` ×20 | 成功 0/20，非法 0，被拒 99 |
| `public_heuristic` | 5 | `LAMP_RESTORED` | seed 0，`risk=0`，`observation_cost=0` |
| `shortcut` | 2 | `LAMP_RESTORED` | seed 0；**seed 5–9 → `RESOURCE_EXHAUSTED`** |
| `forecast_trusting` | 3 | `LAMP_RESTORED` | seed 0，`observation_cost=2` |

预算 46，最长的 Oracle 只用 6 个决策。**判定：完全不是预算问题**——V8 用掉了 2/3/3 个决策。

### 10 个注册 seed 的离线扫描（本审计新增，`seed=0..9`）

| 策略 | 成功 | 失败位置 | 平均决策 |
|---|---|---|---|
| `public_heuristic`（加固路线） | **10/10** | — | 5.0 |
| `shortcut`（只走直达） | **5/10** | seed 5–9 全部 `RESOURCE_EXHAUSTED`（tick 3，`risk=7`） | 2.0 |
| `forecast_trusting`（读预报并按字面执行） | **9/10** | seed 9：预报 short、实际 long → `RESOURCE_EXHAUSTED` | 4.5 |

这张表是本次"机制是否被绕过"判定的直接证据：**机制本身是有效的（shortcut 在 5 个 seed 上必死），但 V8 只采样了 seed 0。**

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 三局取值 |
|---|---|---|---|---|
| `map06.task_success_rate` | primary | `lamp_restored` | 1 | 1.0、1.0、1.0 |
| `map06.value_of_information` | primary | **实现里硬编码 `None`** | 配对 episode 对 | `null`、`null`、`null` |
| `map06.high_risk_exposure_ticks` | guardrail | 每次风险累积的 tick 计数 | episode | 0、0、0 |
| `map06.observation_cost` | diagnostic | `queries * 2` | episode | 0、0、0 |
| `map06.resource_exhausted` | diagnostic | `1 if terminal==RESOURCE_EXHAUSTED` | episode | 0、0、0 |

- **连续主指标**：`task_success_rate` 只有 0/1，`value_of_information` 恒 `None` → **本图没有任何一条"未通关也有意义"的连续主指标**。`high_risk_exposure_ticks` 与 `observation_cost` 是连续的，但它们不是 primary。
- **N/A 情况**：三局各有 1 条 `not_applicable`，就是 `value_of_information`——原因是**地图直接把 `None` 写死**（`map06.py` 第 220 行 `"map06.value_of_information": None`），不是投影口径，也不是真分母 0。
- **区分度**：三局的 5 条指标**完全相同**（1.0/None/0/0/0），因此 **`LOW_DISCRIMINATION` 成立**（仅就 V8 三局证据而言）。把 10 个 seed 的扫描放进来才有区分：`shortcut` 的 `resource_exhausted` 会是 0.5、`high_risk_exposure_ticks` 3，`public_heuristic` 是 0 与 0/2。
- **设计稿 vs 实现的口径差**：`worlds/v4/MAP-06/map_spec.yaml` 写的 `scoring.primary` 是 `expected_utility_over_fixed_seed_cohort`，`utility = 100*success - 7.2*terminal_tick - 1.0*risk_points`，`base_cohort: 10_equal_weight_seeds`。V8 指标表里**没有**这条效用，只留了二值 `task_success_rate` 和一个恒 `None` 的 `value_of_information`。

## 7. 三次轨迹归因

### R0（success，2 决策，`LAMP_RESTORED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"edge_id": "Q_P", "tool": "move"}` | `MOVED:P` | `{"location": "P", "tick": 1, "visible_edges": ["G_P", "Q_P"]}` |
| 2 | `{"operation": "repair_lighthouse", "target_id": "P", "tool": "interact"}` | `REPAIR_STARTED` | `{"lamp_restored": true, "terminal": true, "terminal_reason": "LAMP_RESTORED", "tick": 3}` |

- 首次偏离合理策略：**不适用**——这条路径在 short 天气下就是最短解。
- 失败链：无。
- 需要记录的是**能力链为空**：`risk` 全程 0，`forecast_queries=0`，`storm_shield=false`。本局对"信息价值 / 风险预算"零信息量。
- 替代解释：这不是运气好，而是 seed 固定为 0 的**必然结果**（`WEATHER[0]="short"`）。

### R1（success，3 决策，`LAMP_RESTORED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"target_id": "Q", "tool": "inspect"}` | `TARGET_NOT_VISIBLE` | `{"tick": 2}` |
| 2 | `{"edge_id": "Q_P", "tool": "move"}` | `MOVED:P` | `{"location": "P", "tick": 3, "visible_edges": ["G_P", "Q_P"]}` |
| 3 | `{"operation": "repair_lighthouse", "target_id": "P", "tool": "interact"}` | `REPAIR_STARTED` | `{"lamp_restored": true, "terminal": true, "terminal_reason": "LAMP_RESTORED", "tick": 5}` |

- 首次偏离：决策 1。词表写"位置对象：Q=forecast"，模型把节点 id `Q` 当成 `target_id`，白花 2 tick。
- 失败链：无（终局成功），但这一决策是**C 类接口缺陷的实证**：同一句话在 MAP-04 的格式是"T=lamp；G=wick"（节点=对象），在 MAP-06 是"Q=forecast"（节点=对象名），而实现要求 `target_id="forecast"`；两种读法都"符合"词表。
- 关键：这 2 tick 的浪费对结果没有影响（deadline 14，最终 tick 5）。**所以本图连"决策效率"都不惩罚**。

### R2（success，3 决策，`LAMP_RESTORED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"target_id": "Q", "tool": "inspect"}` | `TARGET_NOT_VISIBLE` | `{"tick": 2}` |
| 2 | `{"edge_id": "Q_P", "tool": "move"}` | `MOVED:P` | `{"location": "P", "tick": 3, "visible_edges": ["G_P", "Q_P"]}` |
| 3 | `{"operation": "repair_lighthouse", "target_id": "P", "tool": "interact"}` | `REPAIR_STARTED` | `{"lamp_restored": true, "terminal": true, "terminal_reason": "LAMP_RESTORED", "tick": 5}` |

- 与 R1 逐字相同（同 seed、同 prompt、同模型）。**重复证据极弱：n=3 里 R1/R2 完全同型，只能算 1 个独立样本 + R0 的 2 决策变体。**

**三局共同结论**：三条轨迹都没有读取任何"核心机制事件"。它们不是"通过了困难图"，而是"通过了一条在 seed 0 上不需要机制的路径"。

## 8. 失败分类

本图 3/3 成功，没有失败局；但**测量上有失败**，按 A–I 分类标注其成因：

| 对象 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| V8 三局作为"困难图能力证据" | **I** 证据不足（seed=0 固定，机制 0 次触发，无法支持构念） | **B** 公开信息不足（风险算术未公开，模型无法事前规划） | 高 | `WEATHER[0]="short"`、`high_risk_exposure_ticks=0`、`observation_cost=0` |
| R1/R2 决策 1 | **C** schema/接口误导（词表"Q=forecast" vs 实现 `target_id="forecast"`） | — | 高 | 决策 1 `TARGET_NOT_VISIBLE` |
| 指标层 | **METRIC_DEFECT**（`value_of_information` 硬编码 `None`；设计稿的 `mean_expected_utility` 未实现） | — | 高 | `map06.py` 第 220 行；`map_spec.yaml` `scoring` |

不标 **D**（预算）：46 个预算只用了 2–3 个。不标 **A**（规则缺陷）：风险与胜负规则本身自洽，`long` 下不加固必死是可复现的。

## 9. 标签

- **`CONSTRUCT_BYPASS`（主要标签）**。证据链：
  1. `WEATHER[0]="short"` + V8 全体 seed=0 → 三次运行都落在"无风险"分支；
  2. 最短成功路径 2 个决策（`Q_P` + `repair`），完全不经过 `forecast`/`harden`/风险预算；
  3. `high_risk_exposure_ticks=0`、`observation_cost=0`、`storm_shield=false` 三局一致；
  4. 同一路径在 seed 5–9 必死（`RESOURCE_EXHAUSTED`），证明**机制有效但未被采样**。
  5. 更严重的是方向性：在本图上，`forecast_trusting` 9/10、`public_heuristic` 10/10、`shortcut` 5/10，而 V8 的二值指标会给 seed 0 的 `shortcut` **满分**——即"用机制"与"绕过机制"在指标上不可区分。
- **`METRIC_DEFECT`**：`map06.value_of_information` 恒 `None`（3/3 `not_applicable`）；设计稿注册的 `expected_utility_over_fixed_seed_cohort` 没有实现；`task_success_rate` 分母恒 1，导致 3/3 与 2 决策的"运气路径"无法区分。
- **`LOW_DISCRIMINATION`**（§11 用词，不是标签集合成员，但与 `METRIC_DEFECT` 同时成立）：三局 5 条指标完全相同。
- 不标 `INTERFACE_BLOCKED`：存在 5 决策、10/10 seed 的公开策略。但 B 类（风险算术未公开）必须记录。
- 不标 `BUDGET_BLOCKED`。

## 10. 最小可证伪修复（无证据不修改）

> 规则保持只读。按"优先补公开信息 / 改评测设计，不改胜负规则"排序。

**旧规则/旧公开信息**：`map06.py` 的 `WEATHER`/`FORECAST` 表、`EXPOSED_EDGES`、`_after_tick` 风险公式；V8 的 `seed=0` 固定运行；V8 指标只投影 5 条。

- **候选 A（最高优先，改评测设计，不动规则）**：按 `map_spec.yaml` 已注册的 `base_cohort: 10_equal_weight_seeds` 评测，即 MAP-06 的 V9/V10 正式运行至少覆盖 seed 0–9（每 seed 1 局即可）。
  - 证据/根因：§2、§5、§9。当前 3 局全部落在 `weather=short`，机制 0 次触发。
  - 预期变化：shortcut 会得到 5/10，`resource_exhausted` 从 0 变 0.5，`high_risk_exposure_ticks` 从 0 变 3 → 机制第一次进入指标。
  - 能力构念影响：这是**唯一不改变规则**就能让"风险/加固"进入测量的办法。
  - 反例/回归风险：旧 3 条 Trace 仍然有效但只覆盖 seed 0，不能与新数据混算成功率；必须分列"seed 0 三重复"与"10-seed cohort"。
- **候选 B（指标，需与 A 一起做）**：实现设计稿里的 `mean_expected_utility = mean(100*success − 7.2*tick − 1.0*risk)` 与配对 `value_of_information`。
  - 手算（**推断**，用 §5 的实测 tick/risk 代入设计公式）：

    | 策略 | seed 0 | 4 个 short 均值 | 5 个 long 均值 | cohort 均值 |
    |---|---|---|---|---|
    | `shortcut` | 78.4 | 78.4 | −28.6 | **24.9** |
    | `public_heuristic`（加固） | 28.0 | 28.0 | 26.0 | **27.0** |
    | `forecast_trusting` | 64.0 | 64.0（seed 4 为 13.6） | 11.6（seed 9 为 −43.0） | **27.3** |

  - **必须同时记录的风险**：① 单看 seed 0，设计效用会把旁路（78.4）排成加固（28.0）的 2.8 倍——**如果不换 cohort，只实现效用函数会让缺陷更严重**；② cohort 均值 24.9 / 27.0 / 27.3 的差距只有约 10%，`-7.2/tick` 的权重明显压不过 `100*success`，所以**即便实现了效用，区分度仍然偏低**。因此 B 必须配 A，并考虑在 DCR 里重新标定 tick 权重（纯指标变更）。
- **候选 C（补公开信息）**：公开风险算术——至少把 `visible_edges` 标注 `exposed|sheltered`，并把"long 下暴露 +1/tick、无盾修复 +3/tick"写进 `_VOCABULARY["MAP-06"]` 或目标文本。
  - 证据/根因：§3 的"未公开"行。当前模型只能靠 `RESOURCE_EXHAUSTED` 学习。
  - 反例/风险：会让本图从"不确定性下的决策"退化为"读规则做算术"，削弱构念。**更保守的替代**：只公开 `exposed|sheltered` 标签、保留风险增量不公开。
- **候选 D（词表，零风险）**：把"位置对象：Q=forecast；P=repair_lighthouse；G=harden"改成"Q 处可 `inspect(target_id=forecast)`"这类显式写法，消除 R1/R2 决策 1 的 `TARGET_NOT_VISIBLE`。
- **候选 E（不推荐）**：把 short 分支也改成需要加固（让机制强制生效）。这会改写设计意图与 4 个 Oracle 用例，属于"为了通关率改规则"的反面，仅登记备查。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-06.json`：

| 策略 | 状态 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle ×4 | 4/4 ok | 2 / 5 / 3 / 6 | — |
| `legal_random` ×20 | 0/20 success | 7–12 | 全部 `REPAIR_DEADLINE_MISSED`；非法 0；被拒 99 |
| `public_heuristic` | success | 5 | `task_success_rate` 1/1；risk 0；`observation_cost` 0 |
| `shortcut` | success | 2 | 同上，全部相同 |
| `forecast_trusting` | success | 3 | `observation_cost` 2（唯一不同的指标） |

**独立复算（手工逐决策重数）**：

- R0 `observation_cost`：trace 无 `inspect` → `queries=0` → `0*2 = 0`，与 judge 一致。
- R0 `task_success_rate`：`lamp_restored=true` → `1/1`，一致。
- R0 `high_risk_exposure_ticks`：`Q_P` 产生 `_exposure_ticks=1`，但 `weather=short` 分支只做 `_exposure_ticks -= 1`，不累加 `high_risk_ticks` → `0`，一致。
- `value_of_information`：`metrics()` 直接返回 `None`，与三局 `not_applicable` 一致（不是分母 0）。
- 交叉验证（独立于 extractor）：用 `create_environment` + `judge_state()` 重放同一动作序列（离线脚本），`shortcut` 在 seed 0 得 tick 3 / risk 0，在 seed 5 得 tick 3 / risk 7 / `RESOURCE_EXHAUSTED`；`public_heuristic` 在 seed 0 与 seed 5 都得 tick 10，risk 0 / 2。这些数字与 `run_policy` 的 10-seed 扫描逐条一致。

**`LOW_DISCRIMINATION` 判定：成立。** 三局 5 条指标完全相同；`shortcut` 与 `public_heuristic` 在 V8 条件下 5 条指标也完全相同（唯一可能不同的 `observation_cost` 都是 0）。只有跨 seed 才出现区分。

## 12. V9 状态

**`NEEDS_REDESIGN`，优先级 P0。**

理由：本图是 30 图里 3/3 的三张之一，但三次成功都发生在 `weather=short` 的 seed 0 上，用 2 个决策走完"暴露直达 + 修复"，`forecast`、`harden`、`risk` 三个核心机制一次未触发；同时 `value_of_information` 恒 `None`、设计稿的期望效用未实现，二值成功率还会给旁路满分。**这是本批最需要修复的构造性缺陷**：修复的第一步不是改规则，而是按已注册的 10-seed cohort 评测 MAP-06，并补齐效用指标。
