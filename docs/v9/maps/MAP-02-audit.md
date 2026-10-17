# MAP-02 逐图审计：双重警报

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-02 / spaceship / 中等 |
| condition | `default` |
| `scenario_hash` | `16dd9b625da0404a1aa9ca0491bbb4d3ca61bf68a441a30babc507f6354d1536` |
| `rule_hash` | `f48f10bc47fd68c0565a5dbd9f945602695eb0e3fae3a9eff554c3549532f5d4` |
| `prompt_hash` | `c58e552f6e4fc88735cc8984fd2e7bf52c8090b7b35e217db2a0d3d8608b2451` |
| `metric_schema_hash` | `8a5efbdb9af9a3c7c8ade5af2979a312f40145207df6489d0f9589a1706d8e50` |
| `oracle_hash` | `885f67a317f42969cb3ca57a79a24c2cccece36166d437ffb747874a52278ea9` |
| 决策预算 | 38（`BUDGETS["中等"]`） |
| V8 三局 | 0/3 成功；`NAV_CORE_FLOODED` ×3（各 6 决策） |

数据来源：`runs/v9/evidence/MAP-02.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-02-final.md`、`worlds/v4/MAP-02/*`、`src/agent_arena/worlds/scenario_v8/maps/map02.py`、`runs/v9/baselines/MAP-02.json`（本次生成）。

## 1. 能力构念

**一句话**：在目标执行途中被“动作序号触发”的突发泄漏打断时，能否放弃原计划、按新的紧迫性重排两个目标（封存导航核 vs 送船员进救生舱），并在隐藏的扩散倒计时内做出正确取舍。

**成功行为**：`nav_core_secured=true` 且 `crew_in_escape_pod=true`（成功码 `DUAL_OBJECTIVE_COMPLETE`），且不触发三个失败码中的任何一个。

**明确反例**：
- 看见 `leak_active=true` 后继续原路线（例如继续去 R1 救核却在半路被淹）；
- 把 `leak_active` 误当成“可以修的可修对象”（本图没有 repair 动作）；
- 先护送船员再回核，且不封闸——被 2 tick 扩散窗口判死；
- 封闸过早，切断了 `C_L1`，把“救船员”变成绕 X 外环的长路线（仍可赢，但余量只剩 1 tick）。

**在本世界三图中的位置**：这是唯一“事件驱动 + 双目标排序”的中等图。它不考记忆（MAP-03），也不考长链依赖（MAP-01），只考**在信息不完整时对两个倒计时排序**。本图也是本世界唯一一张：随机基线、消融、MiMo 三局**全部死在同一个第 6 决策**的图。

## 2. 机制与因果链

**本图专属因果链**：

`C 起始，navigation_alarm=true、center_gate=open、crew 在 L2、nav_core 在 R1、deadline_tick=20`
→ **必需观察**：`goal`（“封存导航核，并把左区船员送入右区救生舱”）、`nav_core_location=R1`、`crew_location=L2`、`visible_edges=["C_L1","C_R1","C_X"]`
→ **隐式事件**：第 4 个 schema 合法动作结算后 `leak_active=true`（`leak_location=L1`），并公开 `crew_pressure_ticks=8`、`spread_contained=false`
→ **关键决策**：立刻 `nav_core/brace_in_case`（若尚未封存）**或**在 C 执行 `center_gate/isolate_L1`（封闸后 `center_gate=closed`、`spread_contained=true`，但 `C_L1` 被永久封死）
→ **立即后果**：未封闸则第 5 tick `spread_ticks 2→1`、第 6 tick `1→0` → `NAV_CORE_FLOODED`（除非此时 `nav_core_secured=true`）；未进救生舱则每 tick `crew_pressure_ticks-1`，归零 → `CREW_PRESSURE_LOST`
→ **终局**：核封存 + 船员在 R2 → `DUAL_OBJECTIVE_COMPLETE`

**可绕过点**：
- 扩散机制可以**整体绕过**：只要在扩散归零前封存导航核，`spread_contained` 是否 true 都不影响生死（`map02.py:194-200` 的失败条件是 `not nav_core_secured`）。因此“封闸”与“封核”是两条互不依赖的保命线。
- 封闸之后 `C_L1` 永久不可通（`GATE_SEALED`），但 `C_X → X_L2` 外环仍可达（`map02.py:119-125`），所以封闸不是自杀，只是把救援路程从 2 步变成 4 步。
- 成功要求两个目标都达成，因此“封闸后放弃船员”只是延迟死亡（压力仍会耗尽）。

**机制是否在三条真实轨迹中触发**：
- R0：**触发**。决策 4 公开泄漏（`crew_pressure_ticks: 8, leak_active: true`），决策 5 尝试不存在的 `leak/repair`，决策 6 死亡。
- R1：**触发**（同上，决策 5/6 各一次 `ACTION_NOT_ALLOWED`）。
- R2：**触发**。决策 4 泄漏、决策 5 回 C、决策 6 进 R1 时结算淹水死亡——它已经在正确方向上，但比结算点晚了一个动作。

**触发所需最小动作数**：泄漏固定在第 4 个合法动作后触发，不可提前也不可避免；从 C 出发“先封核”只需 2 个动作（`C_R1` + `brace_in_case`），即可在泄漏发生前解除淹水威胁。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `navigation_alarm` | 是（恒为 true） | 第 0 步 | 是（提示存在导航故障） |
| `nav_core_location` / `crew_location` | 是 | 第 0 步 | 是 |
| `center_gate` / `spread_contained` | 是 | 每步 | 部分：二者同义，可推断“封闸=隔断扩散”，但**扩散还剩几 tick 未知** |
| `leak_active` / `leak_location` | 是 | 泄漏发生的那一步起 | 是（事件被公开） |
| `crew_pressure_ticks` | 是（泄漏前为 `null`） | 泄漏后每步 | 是（倒计时可观测） |
| `deadline_tick=20` | 是 | 第 0 步 | 是（全局期限） |
| `repair_pack_available` | 是 | 第 0 步 | 是（封核消耗修复包，但代码未强制“必须先取包”，`repair_pack_available` 会在封核时直接置 false） |
| **泄漏触发序号 = 4** | **否** | — | 不需要：泄漏会被公开，且先封核可完全规避 |
| **`spread_ticks = 2`（扩散倒计时）** | **否**（`judge_state` 私有） | — | **这是本图唯一可能影响“合法但不走运”的信息**：泄漏后只剩 1 个决策可封闸/封核 |
| **船员压力预算 = 8** | 否（但泄漏后以 `crew_pressure_ticks=8` 公开） | 泄漏后 | 是 |
| Oracle 两条路径（core_first 11 / crew_first 14） | **否** | — | 不需要 |

结论：**核心机制不依赖隐藏信息**——`nav_core_secured` 与 `crew_pressure_ticks` 都是公开可观测的，先封核的路线在泄漏公开之前就已完成，不需要知道触发序号。真正未公开的只有“扩散还有 2 tick”这一时间常数，它决定了“泄漏后再反应”是否来得及。

## 4. 可解性与可观察性

- Oracle：2 个用例，`core_first` 11 步、`crew_first` 14 步；`baseline_run` 复算 `oracle_ok=2/2`。
- 仅凭公开信息的可执行策略：**存在**。`Map02Heuristic` 只用 `location`、`center_gate`、`nav_core_secured`、`crew_escorted`、`crew_in_escape_pod`，**10 决策成功**（比两条 Oracle 都短），`invalid=0`、`rejected=0`，`completion_ticks=10`、`crew_decompression=0`。
- 关键可行性事实：该策略**不使用**泄漏触发序号与 `spread_ticks`。它把“`goal` 的第一个目标（封存导航核）+ 常亮的 `navigation_alarm`”当作第 0 步的排序依据，在泄漏发生前 2 步就完成封核；泄漏只是事后被观测到，不改变计划。
- 反向事实：**泄漏公开之后才开始救核，从 L1 出发已经来不及**（L1→C→R1→brace 需要 3 个动作，而淹水在第 6 tick 结算）。此路径只有“封闸”能救，但封闸后船员必超时（见 §5 反例复算）。
- 判定：**不构成 `INTERFACE_BLOCKED`**（公开策略成功），也不是 `BUDGET_BLOCKED`（10/38）。但“泄漏后再重排”这一构念的可行窗口只有 1 个决策，属于**设计锐度**问题，记录在 §10。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 11（core_first）/ 14（crew_first） |
| 决策预算 | 38 |
| 公开启发式 | 10（成功） |
| `legal_random` 20 seed | 0/20 成功；20/20 `NAV_CORE_FLOODED`；平均 6.0 决策；非法 0；被拒 46 |

- 随机基线 20 个 seed **全部在第 6 个决策死亡**，终止码一致：随机动作无法在 4 tick 内同时命中 `C_R1` 与 `brace_in_case`，也无法命中 `isolate_L1`。该基线在本图同样**退化**（无方差）。
- 判定：**不是预算不够**。38 个决策是本图所需（10）的 3.8 倍；三局都只用了 6 个决策，剩余 32 个从未使用。
- 反例复算（本次手工执行，`create_environment("MAP-02")`）：“先取船员 → 泄漏后封闸 → 走 X 外环”的路线在第 12 tick 触发 `CREW_PRESSURE_LOST`（压力序列 8,7,6,5,4,3,2,1,0），即使核已封存也无法成功。因此**船员优先只有在泄漏前封闸时才成立**，余量恰好 1 tick（Oracle `crew_first` 第 12 tick 进舱、压力剩 1）。

## 6. 指标

| 指标 | 类别/方向 | 计算事件与分母 | 缺失/截尾 | 本次三局 |
|---|---|---|---|---|
| `map02.completion_ticks` | diagnostic / lower | 成功局 `terminal_tick` | 未成功 → `not_applicable` | 3 局全 N/A（真分母 0） |
| `map02.crew_decompression` | guardrail / lower | `terminal_reason==CREW_PRESSURE_LOST` 的 0/1 | 每局有效 | 0 / 0 / 0 |
| `map02.dual_objective_completion` | primary / higher | `(crew_in_pod + nav_secured)/2` | 每局有效 | 0.0 / 0.0 / 0.0 |
| `map02.event_response_latency` | primary / lower | `first_plan_change_tick - leak_announced_tick` | 需两侧事件都存在 | 1 / 1 / 1 |
| `map02.stale_plan_actions_after_leak` | diagnostic / lower | 泄漏后仍指向 R1/核 的动作数 | 每局有效 | 0 / 0 / 1 |

- **未通关仍有意义的连续主指标**：`dual_objective_completion` 在失败局仍有值（0.0 或 0.5），`stale_plan_actions_after_leak` 也连续。但本图三局二者均为 0/0，**看不出“走到哪一步”**。
- `not_applicable` 只出现在 `completion_ticks`，真分母 0。
- **`event_response_latency` 完全不可区分**：MiMo 三局 = 1、启发式 = 1、消融 = 1、随机 = 1。原因是它把“第一个非 `wait`/`inspect` 动作”当作计划变更，而任何一次 `move` 都满足条件。该主指标在本图所有策略上取同一值 → **`LOW_DISCRIMINATION`**，属于指标定义缺陷而非地图缺陷。
- `dual_objective_completion` 只在 0 vs 1 两端有区分（随机 0、MiMo 0、消融 0、启发式 1），无法区分“救了一半”的过程性差异（本批也没有出现 0.5 的真实局）。

## 7. 三次轨迹归因

### 7.1 R0（`V8-MAP-02-R0-…-cb6ef5a5`，6 决策，`NAV_CORE_FLOODED`）

原文引用：

1. 决策 4 `{"edge_id": "L1_L2", "tool": "move"}` → `MOVED:L1`，`delta: {"crew_pressure_ticks": 8, "leak_active": true, "leak_location": "L1", "location": "L1", "visible_edges": ["C_L1", "L1_L2"]}`。
2. 决策 5 `{"choice": "repair", "target": "leak", "tool": "interact"}` → `ACTION_NOT_ALLOWED`，`delta: {"crew_pressure_ticks": 7}`。
3. 决策 6 `{"target": "alarm_panel", "tool": "inspect"}` → `TARGET_NOT_VISIBLE`，`delta: {"terminal": true, "terminal_reason": "NAV_CORE_FLOODED"}`（此时 `location=L1`）。

**首次偏离**：决策 5。泄漏公开后的第一个动作是**发明一个不存在的 `leak/repair` 交互**；本图公开词表只有 `nav_core/brace_in_case`、`center_gate/isolate_L1`、`crew/escort`。它把 `leak_active` 这个状态字段误读成了可操作对象。

**失败链**：决策 4 泄漏公开（仍在 L1，船员已护送）→ 决策 5 无效修复（耗 1 tick，压力 8→7）→ 决策 6 试图在 L1 读 `alarm_panel`（该对象只在 C 可见）→ 第 6 tick 结算 `spread_ticks 1→0`，核未封存 → 淹水。

**替代解释**：接口误导（C）有份：公开 Observation 里 `leak_active`/`leak_location` 是最显眼的字段，却没有给出对应的可执行动作名，容易诱导“修漏”。但 `center_gate`/`spread_contained` 同时在 Observation 里，且 `goal` 不含“修漏”。主因仍是 E。

### 7.2 R1（`V8-MAP-02-R1-…-12c6cc9e`，6 决策，`NAV_CORE_FLOODED`）

原文引用：

1. 决策 4 `{"edge_id": "L1_L2", "tool": "move"}` → `MOVED:L1`，`delta: {"crew_pressure_ticks": 8, "leak_active": true, "leak_location": "L1", "location": "L1", "visible_edges": ["C_L1", "L1_L2"]}`。
2. 决策 5 `{"choice": "repair", "target": "alarm_panel", "tool": "interact"}` → `ACTION_NOT_ALLOWED`，`delta: {"crew_pressure_ticks": 7}`。
3. 决策 6 `{"choice": "repair", "target": "alarm_panel", "tool": "interact"}` → `ACTION_NOT_ALLOWED`，`delta: {"terminal": true, "terminal_reason": "NAV_CORE_FLOODED"}`。

**首次偏离**：决策 5（与 R0 同型：泄漏后试图 `repair alarm_panel`）。

**失败链**：决策 5 无效 → 决策 6 **重复完全相同的动作**（连 `target` 都没换），在同一个 tick 内既没有换目标也没有移动，被淹水结算。

**替代解释**：预算不是原因（6/38），非法动作 0（形状合法、语义被拒）。这是**反馈-动作循环失效**：连续 `ACTION_NOT_ALLOWED` 没有触发任何假设更新。

### 7.3 R2（`V8-MAP-02-R2-…-223dcf46`，6 决策，`NAV_CORE_FLOODED`）

原文引用：

1. 决策 4 `{"edge_id": "L1_L2", "tool": "move"}` → `MOVED:L1`，`delta: {"crew_pressure_ticks": 8, "leak_active": true, "leak_location": "L1", "location": "L1", "visible_edges": ["C_L1", "L1_L2"]}`。
2. 决策 5 `{"edge_id": "C_L1", "tool": "move"}` → `MOVED:C`，`delta: {"crew_pressure_ticks": 7, "location": "C", "visible_edges": ["C_L1", "C_R1", "C_X"]}`。
3. 决策 6 `{"edge_id": "C_R1", "tool": "move"}` → `MOVED:R1`，`delta: {"location": "R1", "terminal": true, "terminal_reason": "NAV_CORE_FLOODED"}`。

**首次偏离合理策略的可观测事件**：决策 1 的目标排序——在 `navigation_alarm=true`、`nav_core_location=R1` 都公开的情况下选择“先护送船员”，把封核推迟到泄漏之后。决策 5 回 C 的方向本身没有错，但 2 tick 的扩散窗口不允许在泄漏公开后再赶到 R1 执行 `brace_in_case`；第 6 决策的 `NAV_CORE_FLOODED` 只是把这个早先的排序错误暴露出来。

**失败链**：泄漏公开 → 2 个动作返回 C/R1 → 第 6 tick 结算淹水 → 从未获得执行 `brace_in_case` 的机会。

**替代解释**：这是**唯一一条“策略方向正确但输在隐藏时间常数”**的轨迹。若公开 `spread_ticks`（或泄漏时直接给出“还剩 2 tick”），同一策略会在决策 5 改为“封闸”或更早封核。因此 B（公开信息不足）在**该局**上是有效次因，但对整张图不成立——先封核的公开策略不需要这个常数。

### 7.4 重复证据的边界

三局前 4 个动作完全相同（`C_L1`、`L1_L2`、`escort/pickup`、`L1_L2`），第 5 个动作分成“无效修复 ×2”与“回 C 救核 ×1”。n=3 说明第 4 决策是**固定陷阱点**，但无法区分“模型不会修漏”与“模型不知道修漏不存在”。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E 策略规划错误**（泄漏后未重排目标，改为修漏） | C 接口误导（`leak_active` 无对应动作名） | 高 | 决策 5 `ACTION_NOT_ALLOWED`、决策 6 终局 |
| R1 | **E 策略规划错误**（重复同一无效动作） | C 接口误导 | 高 | 决策 5/6 同一 payload、连续两次 `ACTION_NOT_ALLOWED` |
| R2 | **E 策略规划错误**（反应晚 1 个动作） | **B 公开信息不足**（`spread_ticks` 隐藏，反应窗只有 1 决策） | 中 | 决策 5-6 `MOVED:C`/`MOVED:R1` 后同 tick 终局 |

不存在 D（预算）、F（资源）、H（运行异常）证据。

## 9. 标签

- **`MEASUREMENT_VALID`**：10 决策公开策略成功（`runs/v9/baselines/MAP-02.json`），`dual_objective_completion` 在 0/1 两端有区分；三局失败码与 Trace 一致。
- **`METRIC_DEFECT`（限 `map02.event_response_latency`）**：MiMo 1/1/1、启发式 1、消融 1、随机 1 —— 在所有策略上取同一值，不能区分“重排”与“只是没发呆”。
- 不标 `INTERFACE_BLOCKED`：核心机制可用公开信息绕过（先封核）。
- 不标 `BUDGET_BLOCKED`：6/38。
- `RULE_DEFECT`：无。`spread_ticks=2` 与 `NAV_CORE_FLOODED` 的因果在三条轨迹里一致复现。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：`leak_trigger_index=4`、`spread_ticks=2`、`crew_pressure_ticks=8` 全部私有；`leak_active` 公开。
- 证据与根因：R2 证明“方向正确但晚 1 个动作”会死；而 `Map02Heuristic` 证明“泄漏前先封核”不需要任何隐藏信息。
- 候选 A（补公开信息，中等风险）：在 Observation 公开 `spread_ticks_remaining`（泄漏前为 `null`）。预期变化：R2 型策略可在线重排，`event_response_latency` 与 `stale_plan_actions_after_leak` 才有机会分化；风险：降低“突发”锐度，可能把这图变成可计算的最短路问题。
- 候选 B（只修指标，低风险，**推荐**）：把 `map02.event_response_latency` 从“第一个非 wait/inspect 动作”改为“第一个改变目标对象的动作（`nav_core`/`center_gate`）”或“泄漏后 3 个动作内是否出现封闸/封核”。预期变化：区分度从 1 值变为 0/1 或 1/2/3；不影响规则与 `rule_hash`（只改指标定义需走 `metric_schema_hash` 的 DCR）。
- 候选 C（改规则）：放宽扩散窗口到 3 tick。**拒绝**：这是为了让 R2 型失败变成成功而加时间，违反研究诚信。
- 结论：地图规则**无需修改，保持只读**；`event_response_latency` 的指标重定义登记为 **DCR 候选（P2）**，由主控统一裁决。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-02.json`（本次运行）：

| 策略 | 成功 | 决策 | 终止码 | `dual_objective_completion` | `event_response_latency` | `stale_plan_actions_after_leak` |
|---|---|---|---|---|---|---|
| Oracle `core_first` | 是 | 11 | `DUAL_OBJECTIVE_COMPLETE` | — | — | — |
| Oracle `crew_first` | 是 | 14 | `DUAL_OBJECTIVE_COMPLETE` | — | — | — |
| `legal_random`（20 seed） | 0/20 | 6.0 平均 | `NAV_CORE_FLOODED` ×20 | 0.0 | 1 | 0 |
| `public_heuristic` | 是 | 10 | `DUAL_OBJECTIVE_COMPLETE` | 1.0（2/2） | 1 | 1 |
| 消融 `no_leak_response` | 否 | 6 | `NAV_CORE_FLOODED` | 0.0 | 1 | 1 |

**独立复算**（不调用 `map02.metrics()`，只读 `actions[*].observation_after`）：

- `dual_objective_completion`：启发式终局 `nav_core_secured=true`（决策 2 起）、`crew_in_escape_pod=true`（决策 10）→ `(1+1)/2 = 1.0`，与 extractor 一致；消融终局两者皆 false → 0.0，一致。
- `event_response_latency`：泄漏首次出现在决策 4 的 `observation_after`（`leak_active=true`），其后第一个非 `wait`/`inspect` 动作为决策 5 → `5-4 = 1`，与 extractor 一致（这也正是该指标无区分度的复算证据）。
- `stale_plan_actions_after_leak`：启发式在泄漏后（决策 7-10）有 1 个 `move C_R1`（目的地 R1）→ 1，与 extractor 一致。
- 判别力：`dual_objective_completion` 可区分 0 与 1；`event_response_latency` **不可区分**（`LOW_DISCRIMINATION`）。

## 12. V9 状态

**`VALIDATED`，优先级 P2。**

一句话理由：地图本身有 10 决策的纯公开信息成功路径、规则与失败码在三条轨迹中一致复现，因此作为“双目标在线重排”测量成立；只有 `event_response_latency` 这一条主指标无区分度，需在指标层走 DCR，不涉及地图规则修改。

（`VALIDATED` 是本审计的机器推导结论，**待用户确认**，不构成人工审核。）
