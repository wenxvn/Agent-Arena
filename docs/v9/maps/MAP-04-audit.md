# MAP-04 审计：潮汐密道

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-04 / lighthouse / 简单 |
| condition | `default` |
| scenario_hash | `3cd4b7fafdaf0c9ffa1d487dffb7123bf5da2a968315e52db3de67bce5478050` |
| rule_hash | `88500e992c3bdd695f1c02e005e96c48739b0d147a24f284144847f52b53157d` |
| 决策预算 / step_limit | 30 / 160 |
| V8 三局 | R0 success `SIGNAL_LIT` 15 决策；R1 failure `RESCUE_SIGNAL_WINDOW_EXPIRED` 15 决策；R2 failure 同名 16 决策 → **1/3** |

数据来源：`runs/v9/evidence/MAP-04.json`（本审计的全部 Observation 引用均来自该证据包与 `scripts/v9_show_map.py MAP-04` 的输出）、`docs/v9/run-index.csv` 第 11–13 行、`docs/v8/maps/MAP-04-final.md`、`worlds/v4/MAP-04/{map_spec.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map04.py`。

本图是 6 张 `scenario_v8` 原生实现图之一（非 V4 适配图），规则直接读 `map04.py`，不经过 `v4_adapter.py`。

## 1. 能力构念

- **定义**：在"周期性开闭的门"前，用当前相位推算最短可行等待，并把它与"绕远路"的时间成本放在同一个 horizon 里权衡。
- **成功行为**：在 `rescue_deadline_tick=18` 之前完成 `pickup(wick)` → `fit_wick` → `ignite`；过程中要么在 `tide_phase ∈ open_phases=[0,1]` 时通过 `S_G`，要么走完 6 段绕行海岸路。
- **明确反例**：在相位不安全时反复撞 `S_G`（`TIDE_WINDOW_CLOSED` 每次白花 1 tick）；或把"返回 T"的路线走成往返振荡，使 18 tick 内到不了灯座。
- **本图在三图递进中的位置**：唯一"完全确定性、无资源账本"的图——相位按固定周期 6 演进，所有关键信息（`tide_phase`、`tide_period`、`open_phases`）都在 Observation 里；难度应来自"动作成本与回程时机"，而不是信息缺失。它本身不测资源/风险（那是 MAP-05/06 的位置）。

## 2. 机制与因果链

```
起始 T, tick0, tide_phase=2
  → 必需观察：tide_phase=2、tide_period=6、open_phases=[0,1]、visible_edges=[T_B1,T_S]
  → 关键决策：是否等相位（wait k 使 (2+k)%6 ∈ {0,1}）再走 S_G
  → 立即后果：S_G 通过则 tide_phase 前进、location=G；不通过则 TIDE_WINDOW_CLOSED 并只白花 1 tick
  → 取灯芯后必须再过一次 S_G（或走 6 段绕行）回到 T
  → 终局：tick≥18 且未点亮 → RESCUE_SIGNAL_WINDOW_EXPIRED；点亮 → SIGNAL_LIT
```

**可绕过核心机制的动作路径（实测）**：

1. **纯绕行**：`T_B1→B1_B2→B2_B3→B3_B4→B4_D→G_D`（去）+ `G_D→B4_D→B3_B4→B2_B3→B1_B2→T_B1`（回）+ `fit_wick`+`ignite` = **15 个决策、tick 15**，`high_tide_entries=0`、`window_hit_rate` 分母 0。见 `runs/v9/baselines/MAP-04.json` 的 `ablations.detour_shortcut`（success，15 决策）与 V8 R0（就是这条路径）。
2. **盲目撞门**：不读相位，看到 `S_G` 就 `move`，失败也重试。每次失败只花 1 tick 且相位随之 +1，所以最多 4 次必然撞开。实测 `ablations.no_phase_wait`：14 决策、tick 14、**success**，`high_tide_entries=7`。
3. 真正需要相位算术的只有"最短路线"：`public_heuristic` 9 决策、tick 14、`high_tide_entries=0`。

**机制是否在三条真实轨迹里触发**：

- R0：**从未触发**。15 个决策全部在绕行路与 T/G 之间，`S_G` 一次也没走（`crossing_attempts=0`）。
- R1：触发 1 次负事件，决策 2 `{"edge_id":"S_G","tool":"move"} -> TIDE_WINDOW_CLOSED`。
- R2：同上，决策 2 `-> TIDE_WINDOW_CLOSED`。
- 触发所需最小动作数：**2**（`T_S` + `S_G`）。

**因果链上真正决定结局的不是相位，而是"回程路线"**：R1/R2 都在拿到灯芯后丢失了回 T 的方向（见 §7），与相位是否算对无关。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `visible_edges` | 是（Observation） | 每步 | 是；图可完整探索（8 条边全部 `always` 除 `S_G`） |
| `tide_phase` | 是 | 每步 | 是；相位算术的输入 |
| `tide_period=6`、`open_phases=[0,1]` | 是 | 每步 | 是 |
| `wick_location`、`inventory`、`lamp_wick_fitted`、`lamp_lit` | 是 | 每步 | 是 |
| `rescue_deadline_tick=18` | 是 | 每步 | **不完整**：只给截止 tick，不给当前 tick |
| **当前 tick / 已用 tick** | **否** | — | 否；`PUBLIC_FIELDS` 无 `tick`，只能靠自数动作（`wait(turns=N)` 的成本也没公开） |
| 规则"任何动作推进 1 tick、`wait` 推进 N tick，相位同步 +cost mod 6" | **未公开**（只存在于 `map04.py::_action_cost` / `_after_tick`） | 只能由相位差分反推 | 反推可行但不确定（模 6 歧义） |
| 规则"`S_G` 在相位非 0/1 时留在原地并返回 `TIDE_WINDOW_CLOSED`" | 部分公开：`open_phases` 公开，返回码经结果反馈 | 首次尝试后 | 是 |
| system prompt 动作词表 | 是：`inspect(tide_gauge)`、`pickup(wick)`、`lamp/fit_wick`、`lamp/ignite`、`位置对象：T=lamp；G=wick` | 开局 | 是（不含相位规则） |
| hidden `judge_state`：`crossing_attempts`、`first_crossing_tick`、`high_tide_entries`、`wait_ticks` | 否 | — | 不影响解题 |
| 常量 `EARLIEST_FEASIBLE_CROSSING_TICK=5` | **否**（指标实现细节） | — | 不影响解题，只决定指标口径 |
| Oracle 路径（`tide_window`/`detour`） | 否 | — | — |

结论：解题所需信息**基本公开**，唯一明显缺口是"绝对时间"（tick）。

## 4. 可解性与可观察性

- Oracle：`tide_window`（14 动作，`SIGNAL_LIT`）、`detour`（15 动作，`SIGNAL_LIT`），`baseline_run` 复算 2/2 ok。
- **仅凭公开 Observation 的可执行策略存在**，且已实测：
  - `public_heuristic`（`src/agent_arena/v9/policies/world_lighthouse.py::Map04Heuristic`）：9 决策、tick 14、success、`earliest_safe_crossing_delay=0`、`window_hit_rate=2/2`。它只读 `tide_phase/tide_period/open_phases/location/inventory`，在相位空间里算"最短等待"。
  - 更强的结论：**连相位都不用算也能赢**——`detour_shortcut`（15 决策）与 `no_phase_wait`（14 决策）都只用公开 Observation 就成功。
- 因此不存在 `INTERFACE_BLOCKED`/`BUDGET_BLOCKED`；存在的是"核心机制可被旁路"（§2、§9）。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 备注 |
|---|---|---|---|
| Oracle `tide_window` | 14 | `SIGNAL_LIT` | 含 8 次单 tick `wait` |
| Oracle `detour` | 15 | `SIGNAL_LIT` | 纯绕行 |
| `legal_random`（20 seed） | 13–18 | `RESCUE_SIGNAL_WINDOW_EXPIRED` ×20 | 成功 0/20，非法 0，被拒 110 |
| `public_heuristic` | 9 | `SIGNAL_LIT` | 两次 `wait`（3、4 tick）合并等待 |
| `detour_shortcut` | 15 | `SIGNAL_LIT` | tick 15 |
| `no_phase_wait` | 14 | `SIGNAL_LIT` | `high_tide_entries=7` |

预算 30，Oracle 只需 14–15，启发式只需 9。**判定：不是预算不够，而是模型没做对**——R1/R2 都在 15/16 个决策内自然终局（未触顶），且两者都还有可用的 tick 余额被浪费在振荡上（R2 在决策 11 时距成功只差 4 个动作）。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失规则 |
|---|---|---|---|---|
| `map04.earliest_safe_crossing_delay` | primary | 首次成功穿越 `S_G` 的 tick − 5 | 成功穿越的 episode | 未穿越 → `None` |
| `map04.high_tide_entries` | guardrail | `TIDE_WINDOW_CLOSED` 次数 | episode | — |
| `map04.stranded_ticks` | diagnostic | **实现为 `high_tide_entries` 的同一个值** | episode | — |
| `map04.wait_ticks` | diagnostic | `Σ turns`（仅显式 `wait`） | episode | — |
| `map04.window_hit_rate` | primary | `crossing_successes/crossing_attempts` | 穿越尝试数 | 分母 0 → `not_applicable` |

- **有未通关仍有意义的连续主指标吗**：有，`high_tide_entries`（0/1/7）、`wait_ticks`（0/4/5/7）、`window_hit_rate`（2/2、1/2、2/9）。但两个 primary 中，`earliest_safe_crossing_delay` 是"只有成功穿越才有值"的结构，`window_hit_rate` 是比例。
- **三局的 N/A**：R0 有 2 条 `not_applicable`（`earliest_safe_crossing_delay`、`window_hit_rate`），原因不是投影口径，而是**真分母 0**：R0 走了绕行，`crossing_attempts=0`、`first_crossing_tick=None`。R1/R2 无 N/A（5/5 valid）。
- **区分度**：能区分至少四种策略——`public_heuristic`（delay 0 / wait 7 / hit 2:2）、`detour_shortcut`（delay null / wait 0 / hit 0:0）、`no_phase_wait`（delay 0 / wait 0 / hit 2:9 / high_tide 7）、random（全失败）。**但两个 primary 恰好无法区分"赢了但绕开机制"**：唯一成功的 V8 局（R0）两条 primary 都是 N/A。
- **指标缺陷（证据）**：`map04.stranded_ticks` 在 `metrics()` 里直接返回 `self.high_tide_entries`（`map04.py` 第 176 行），与 `high_tide_entries` 逐局完全相等：R1 两值皆 1、R2 两值皆 1、`no_phase_wait` 两值皆 7。V8 文档写的公式是 `Σ stranded_ticks + rollback_cost`，运行时没有任何 `stranded_ticks` 计数器。

## 7. 三次轨迹归因

### R0（success，15 决策，`SIGNAL_LIT`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"edge_id": "T_B1", "tool": "move"}` | `MOVED:B1` | `{"location": "B1", "tide_phase": 3, "visible_edges": ["B1_B2", "T_B1"]}` |
| 6 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:G` | `{"location": "G", "tide_phase": 2, "visible_edges": ["G_D", "S_G"]}` |
| 7 | `{"item_id": "wick", "tool": "pickup"}` | `PICKED:wick` | `{"inventory": ["wick"], "tide_phase": 3, "wick_location": "carried"}` |
| 15 | `{"choice": "ignite", "target": "lamp", "tool": "interact"}` | `SIGNAL_LIT` | `{"lamp_lit": true, "terminal": true, "terminal_reason": "SIGNAL_LIT", "tide_phase": 5}` |

- **首次放弃核心机制的可观测事件**：决策 1 选择 `T_B1` 而不是 `T_S`；此后 15 个决策里 `tide_phase` 只是被动跟着变，从未参与决策。
- 失败链：无（成功），但**能力链为空**：本局没有任何相位推理、没有一次 `S_G`，主指标退化为 N/A。这条成功轨迹本身是 §9 `CONSTRUCT_BYPASS` 的最强证据。

### R1（failure，15 决策，`RESCUE_SIGNAL_WINDOW_EXPIRED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"edge_id": "T_S", "tool": "move"}` | `MOVED:S` | `{"location": "S", "tide_phase": 3, "visible_edges": ["S_G", "T_S"]}` |
| 2 | `{"edge_id": "S_G", "tool": "move"}` | `TIDE_WINDOW_CLOSED` | `{"tide_phase": 4}` |
| 3 | `{"tool": "wait", "turns": 2}` | `WAITED` | `{"tide_phase": 0}` |
| 4 | `{"edge_id": "S_G", "tool": "move"}` | `MOVED:G` | `{"location": "G", "tide_phase": 1, "visible_edges": ["G_D", "S_G"]}` |
| 5 | `{"item_id": "wick", "tool": "pickup"}` | `PICKED:wick` | `{"inventory": ["wick"], "tide_phase": 2, "wick_location": "carried"}` |
| 6 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:D` | `{"location": "D", "tide_phase": 3, "visible_edges": ["B4_D", "G_D"]}` |
| 7 | `{"tool": "wait", "turns": 3}` | `WAITED` | `{"tide_phase": 0}` |
| 9 | `{"edge_id": "B3_B4", "tool": "move"}` | `MOVED:B3` | `{"location": "B3", "tide_phase": 2, "visible_edges": ["B2_B3", "B3_B4"]}` |
| 10 | `{"edge_id": "B3_B4", "tool": "move"}` | `MOVED:B4` | `{"location": "B4", "tide_phase": 3, ...}` |
| 14 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:G` | `{"location": "G", "tide_phase": 1, "visible_edges": ["G_D", "S_G"]}` |
| 15 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:D` | `{"location": "D", "terminal": true, "terminal_reason": "RESCUE_SIGNAL_WINDOW_EXPIRED", ...}` |

- **首次偏离**：决策 2 —— `open_phases=[0,1]` 与 `tide_phase=3` 同时在 Observation 里，仍直接撞门。代价只有 1 tick，可恢复（决策 3–4 立刻修正），所以**不是**致命点。
- 真正的失败链：决策 5 已在 G 拿到灯芯；决策 6 走到 D、决策 7 把相位等到 0（此时距 G 只有 1 步 `G_D`），完全可以从 G 走 `S_G` 回 S/T，但模型继续沿 B4 方向走；随后决策 9→13 在 B4↔D 之间往返 5 次（`MOVED:B4`、`MOVED:D` 交替），**方向记忆丢失**，最终在 tick 18 仍在 D。
- 替代解释：(a) 预算不足——否，只用了 15/30；(b) 接口误导——否，`TIDE_WINDOW_CLOSED` 是最明确的结果码，`tide_phase` 也一直公开；(c) 任务本身不可解——否，决策 9 结束时就站在 B3，距 T 只差 `B2_B3→B1_B2→T_B1` 3 步 + 2 个交互（tick 14 可完成，截止 18）。

### R2（failure，16 决策，`RESCUE_SIGNAL_WINDOW_EXPIRED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 2 | `{"edge_id": "S_G", "tool": "move"}` | `TIDE_WINDOW_CLOSED` | `{"tide_phase": 4}` |
| 4 | `{"edge_id": "S_G", "tool": "move"}` | `MOVED:G` | `{"location": "G", "tide_phase": 1, ...}` |
| 6 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:D` | `{"location": "D", "tide_phase": 3, ...}` |
| 7 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:G` | `{"location": "G", "tide_phase": 4, ...}` |
| 10 | `{"edge_id": "B3_B4", "tool": "move"}` | `MOVED:B3` | `{"location": "B3", "tide_phase": 1, ...}` |
| 11 | `{"edge_id": "B3_B4", "tool": "move"}` | `MOVED:B4` | `{"location": "B4", "tide_phase": 2, ...}` |
| 14 | `{"tool": "wait", "turns": 2}` | `WAITED` | `{"tide_phase": 0}` |
| 16 | `{"edge_id": "G_D", "tool": "move"}` | `MOVED:G` | `{"location": "G", "terminal": true, "terminal_reason": "RESCUE_SIGNAL_WINDOW_EXPIRED", ...}` |

- **首次偏离**：决策 6 —— 拿到灯芯后在 D 没有直接 `B4_D→B3_B4→B2_B3→B1_B2→T_B1` 回 T，而是决策 7 反向 `G_D` 折回 G，8 再折回 D（连续 2 个决策净位移为 0）。
- **关键可赢点被丢弃**：决策 10 结束时位于 B3，距 T 只差 3 个 `move` + 2 个交互；决策 11 却反向回到 B4，此后又在 B4/D 之间往返（12、13、15、16）。这一条把"是否可解"从模糊变成确定：**本局是模型自己丢掉了必胜线**。
- 替代解释：(a) 信息不足——否，回程边 `B2_B3`/`B1_B2` 在决策 10 的 `visible_edges` 里明确出现；(b) 预算——否，16/30；(c) 固定陷阱——无法排除"同 seed 重复"带来的同一诱因，但 R1 与 R2 的具体振荡位置不同（R1 从 `B4_D`、R2 从 `B3_B4` 开始），说明不是单一固定陷阱。

**重复证据有限**：三局同 seed=0、同 prompt，R1/R2 高度相似（都在决策 2 撞门、都在绕行段振荡），**n=3 不能区分个体差异与固定陷阱**；但两局的振荡起点不同，支持"策略性迷失"而非"环境强制"。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0（success） | — | **B**（不完整公开：无 tick）与 **CONSTRUCT_BYPASS** 不计为失败，记在 §9 | 高 | 决策 1 起全部走绕行；`crossing_attempts=0` |
| R1 | **E** 策略规划错误（回程选错并振荡） | **G** 记忆/空间推理（B4↔D 往返 5 次） | 高 | 决策 6–15 |
| R2 | **E** 策略规划错误（决策 11 反向，丢弃 3 步必胜线） | **G** | 高 | 决策 10–16 |

- 双因标注：两局都有"决策 2 撞门"，但它只花 1 tick 且随后修正，不构成终局原因，故只作旁证。
- 未使用 **D**（预算）与 **A**（规则缺陷）：30 决策预算下 15/16 个决策就自然终局，且环境没有拒绝任何合法动作。

## 9. 标签

- **`CONSTRUCT_BYPASS`**（证据：`detour_shortcut` 15 决策成功且 `crossing_attempts=0`；V8 唯一成功的 R0 就是这条路径；`no_phase_wait` 用 14 个"撞门重试"决策也能成功）。核心机制"相位预测"不是通关的必要条件。
- **`METRIC_DEFECT`**（证据：① 唯一成功局 R0 的两条 primary 全部 `not_applicable`，primary 无法评价成功路径；② `map04.stranded_ticks` 与 `map04.high_tide_entries` 在实现里是同一个值，逐局完全相等）。
- 不标 `MEASUREMENT_VALID`：两次失败的原因（E/G）是真实的，可以支持"本图能区分策略"，但因为上面的旁路与指标缺陷，不能整体判定为有效测量。
- 不标 `INTERFACE_BLOCKED` / `BUDGET_BLOCKED`：两种只用公开 Observation 的策略都成功了。

## 10. 最小可证伪修复（无证据不修改）

> 本图规则**保持只读**；下面只给候选，等主控统一 DCR。

**旧规则/旧公开信息**：`map04.py` 现状 + 公开 `rescue_deadline_tick` 但隐藏 tick。

- **候选 A（优先，只补公开信息）**：Observation 增加 `tick`（或 `ticks_to_deadline`）。
  - 根因：`rescue_deadline_tick` 公开而绝对时间不公开，任何"还有几步"的判断只能靠私数动作。
  - 预期变化：不影响现有 Oracle（动作序列与 tick 都不变），只让截止时间可观测；对能力构念是"补全信息"，不是降低难度。
  - 反例/风险：可能让模型更早放弃绕行，间接降低 `CONSTRUCT_BYPASS` 的观察频率；规则 hash 不变（`_public` 改动会变 `rule_hash`，需 DCR 记录）。
- **候选 B（指标口径，不改规则）**：把 `earliest_safe_crossing_delay` 的 `None` 与"成功但没有穿越"区分开——增加 `map04.route_used ∈ {tide, detour}` 与 `map04.finish_tick_delay`，或把 primary 改为 `finish_tick - 5`（绕行成功也能算）。
  - 根因见 §6；预期变化：成功局不再出现 primary 全 N/A。
- **候选 C（构念，需要重新冻结，优先级最低）**：把 `stranded_ticks` 与 `high_tide_entries` 合并为一条，或实现真正的 `Σ stranded_ticks + rollback_cost`。
- **候选 D（不推荐）**：把 `rescue_deadline_tick` 压到 14，让绕行（15 tick）不再可行。
  - 代价：Oracle `detour` 用例（15 步）会变成失败，需重建 oracle、重算 `oracle_hash` 与 `scenario`/`rule` hash，并改变设计意图（"短窗/长绕行权衡"被取消）。因此只登记为"若要恢复机制必要性"的最小规则改法，不作为本轮建议。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-04.json`：

| 策略 | 状态 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `tide_window` / `detour` | 2/2 ok | 14 / 15 | — |
| `legal_random` ×20 | 0/20 success | 13–18 | 全部 `RESCUE_SIGNAL_WINDOW_EXPIRED`；非法 0；被拒 110 |
| `public_heuristic` | success `SIGNAL_LIT` | 9 | delay 0；`high_tide_entries` 0；`wait_ticks` 7；hit 2/2 |
| `detour_shortcut` | success `SIGNAL_LIT` | 15 | delay `null`；wait 0；hit 0/0 |
| `no_phase_wait` | success `SIGNAL_LIT` | 14 | delay 0；`high_tide_entries` 7；hit 2/9 |

**独立复算（手工，逐决策重数，与 extractor 实现不同路径）**：

- R1 `window_hit_rate`：trace 里 `S_G` 出现在决策 2（`TIDE_WINDOW_CLOSED`）与决策 4（`MOVED:G`）→ 2 次尝试 1 次成功 = `1/2 = 0.5`，与 judge 的 `{"numerator": 1, "denominator": 2}` 一致。
- R1 `earliest_safe_crossing_delay`：首次成功穿越发生在决策 4 完成后，前 4 个动作各 1 tick → 到达 tick 5 → `5 - 5 = 0`，与 judge 的 `0` 一致。
- R1 `wait_ticks`：决策 3（2）+ 决策 7（3）= `5`，与 judge 的 `5` 一致。
- R0：`crossing_attempts` 在 15 条决策里为 0 → 比例分母 0 → `not_applicable`；`first_crossing_tick=None` → `null`，与 projector 输出一致。
- `stranded_ticks == high_tide_entries`：三局 + 全部基线逐条相等（0/0、1/1、7/7）。

**`LOW_DISCRIMINATION` 判定**：不成立（4 条指标能区分 4 种策略）；但两条 **primary** 对"绕行成功"这一路径无区分力，属于 §9 的 `METRIC_DEFECT`。

## 12. V9 状态

**`NEEDS_REDESIGN`，优先级 P1。**

理由：失败样本本身是真实的 E/G 能力失败，但唯一成功样本（R0）完全绕开了潮汐相位机制、且两条主指标在该局都是 `not_applicable`——按现状无法用本图回答"周期相位预测"这一构念；修复只需补 `tick` 公开信息与主指标口径，不必改规则。
