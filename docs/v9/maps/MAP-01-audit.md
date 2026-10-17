# MAP-01 逐图审计：破损的曙光号

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-01 / spaceship / 简单 |
| condition | `default` |
| `scenario_hash` | `e130d30cf7b59738fbff1d7016cab5fe920bf376fb220f6bf0f7cabba92ed987` |
| `rule_hash` | `b0b4cf2c14e981f2ff4f561be50266f235e8e021fea00d01857ed2ceea7c248f` |
| `prompt_hash` | `65fb8d0bdc4d80d2da962ea4dde959a0932c3119ff6c69230bca5978a96dd4a3` |
| `metric_schema_hash` | `31c2795d2a3ac4e6f9cb8a623099ac4d17dba0a4a59bef2a8be39742daa26305` |
| `oracle_hash` | `753f601461a743c03b294d0c9c3997565c4b205b30d60aee8ab3d0e0f4c1f8e6` |
| 决策预算 | 30（V8 冻结口径，`BUDGETS["简单"]`） |
| V8 三局 | 0/3 成功；`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`（R0，11 决策）、`BUS_RESET_WITH_HULL_OPEN`（R1，22 决策）、`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`（R2，4 决策） |

数据来源：`runs/v9/evidence/MAP-01.json`（每步 `action`/`result`/`delta`）、`docs/v9/run-index.csv` 行 `MAP-01,0..2`、`docs/v8/maps/MAP-01-final.md`、`worlds/v4/MAP-01/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map01.py`、`runs/v9/baselines/MAP-01.json`（本次生成）。

> 本文件从 Trace 与源码重新推导，不复制 `docs/v8` 结论；`docs/v8` 仅用于对照 hash 与登记口径。

## 1. 能力构念

**一句话**：在“持续生命支持先于一切”的硬约束下，完成一条带互斥电支路的前置依赖链（供氧 → 取件 → 维修臂 → 补壳 → 回切供氧 → 母线 → 气闸 → 舰桥确认）。

**成功行为**：在一次不超过 30 决策的 episode 中，使 `hull_intact=true`、`main_bus=true`、`pressure_test="pass"`，并在 B 执行 `bridge_console/confirm_repair`（成功码 `REPAIR_CONFIRMED`）；过程中任何连续未供氧 tick 不超过 3。

**明确反例**：
- 为了让维修臂上电而主动切断供氧后，**忘记回切**（`local_breaker/route_support`），断供计数累积到第 4 tick；
- 在 `hull_intact=false` 时复位母线（环境直接判死，不是扣分）；
- 把 `inspect` 当作 `interact` 使用，或长时间不启动供氧而把前 3 个免费 tick 花在探索上。

**在本世界三图中的位置**：本图是唯一以“互斥资源 + 严格前置链”为主负担的简单图；MAP-02 的负担是事件后的在线重排，MAP-03 的负担是跨阶段里程碑与远期召回。本图的动作数（18 Oracle / 15 公开启发式）最少，但“零容错的 3 tick 断供窗”使它成为本世界唯一会在**第 4 个决策**就结束的图。

## 2. 机制与因果链

**本图专属因果链**：

`B 起始，oxygen_output=false、reserve=18、routed_branch=none`
→ **必需观察**：`oxygen_output=false`、`oxygen_reserve=18`、`visible_edges=["B_H"]`、prompt 公开规则“未供氧每 tick -1；连续断供超过 3 tick 失败”
→ **关键决策 1**：在 B 或 H 执行 `oxygen_relay/start_support`（`OXYGEN_ON`，`routed_branch=support`）
→ **必需观察**：W 处 `inventory` 出现 `patch_kit` 前置；`inspect power_diagram` 返回 `capacity=6,fixed=3,support=2,arm=2`
→ **关键决策 2**：W 取件 → `local_breaker/route_arm`（供氧被关闭，`repair_arm=true`）
→ **关键决策 3**：3 tick 内 `hull_panel/apply_patch`（`hull_intact=true`，`service_edge_open=true`）→ **关键决策 4**：`local_breaker/route_support` 回切（断供计数清零）
→ P 复位母线 → A 压力测试 → B 确认 → `REPAIR_CONFIRMED`

**可绕过点**：
- `inspect` 全部可选：Oracle 用 18 步含 2 次 inspect，公开启发式只用 15 步、0 次 inspect 即成功（`runs/v9/baselines/MAP-01.json` `public_heuristic`）。
- 无法绕过互斥：`route_arm` 在前时 `start_support` 返回 `POWER_CAPACITY_CONFLICT`；`apply_patch` 在 `routed_branch!="arm"` 时返回 `ARM_UNPOWERED`（代码 `map01.py:141-169`）。因此“先补壳再上臂”不可行，只能按 供氧→取件→切臂→补壳→回切 的次序。

**机制是否在三条真实轨迹中触发**：
- R0：**触发**（决策 8 `REPAIR_ARM_ON` 使 `oxygen_output=false`，到决策 11 断供计满 4 tick）。
- R1：**未触发互斥机制**（从未成功 `route_arm`，三次 `ARM_UNPOWERED` 后绕过补壳直接在 P 复位母线），触发的是“开壳复位”失败分支。
- R2：**未触发**（4 个决策内没有启动供氧，直接触发断供上限）。

**触发所需最小动作数**：断供上限 4 tick（4 个不供氧动作即死，实测 `wait`×4 → `OXYGEN_SUPPLY_INTERRUPTION_LIMIT`）；互斥支路最早在第 5 个动作触发（B 起步：B_H、H_W、pickup、route_arm）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `visible_edges` | 是（Observation） | 每步 | 是（拓扑自 public 边标识可得） |
| `oxygen_output` / `oxygen_reserve` | 是（Observation） | 每步 | 是（断供可即时观测） |
| `routed_branch` / `repair_arm` | 是（Observation） | 每步 | 是（互斥状态可见） |
| `hull_intact` / `main_bus` / `pressure_test` / `inventory` / `service_edge_open` | 是（Observation） | 每步 | 是 |
| 断供阈值“超过 3 tick 失败、恢复后清零” | **是（system prompt 的公开规则行）** | 第 0 步 | 是。注意：`docs/v8/maps/MAP-01-final.md` §10 写“`oxygen_off_ticks` 仍为私有，阈值需由失败归因推断”，但 `src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-01"]` 已公开规则文本；**阈值公开、计数器值私有** |
| 电容量 6/3/2/2 | 是，但仅在 H 执行 `inspect power_diagram` 后 | 主动检查时 | 是（也可由 `POWER_CAPACITY_CONFLICT` 反推） |
| `route_arm` 会关闭供氧 | 否（规则文本未写） | 执行后由 `oxygen_output=false` 观测 | 是（后果一步内可见，且可用 `route_support` 回切） |
| `judge_state`（`dependencies`、`oxygen_off_ticks`、`violations`） | **否** | — | 不需要：6 条依赖全部可由公开状态机复算 |
| Oracle 路径（18 步） | **否** | — | 不需要（15 步公开启发式即可成功） |

结论：本图**没有只存在于私有 docstring 或代码的成功前置条件**。唯一的“半公开”是互斥供电的容量数字，但它有公开的 inspect 入口与可观测的拒绝码兜底。

## 4. 可解性与可观察性

- Oracle：`default` 1 个用例、18 步，`replay_all("MAP-01")` → `ok=true`（本次 `baseline_run` 复算：`oracle_ok=1/1`）。
- 仅凭公开信息的可执行策略：**存在**。本次实现 `Map01Heuristic`（`src/agent_arena/v9/policies/world_spaceship.py`）只用 `location`、`visible_edges`、`oxygen_output`、`routed_branch`、`hull_intact`、`inventory`、`main_bus`、`pressure_test`，**15 决策成功**，`invalid=0`、`rejected=0`，`completion_ticks=15`，`longest_oxygen_outage_ticks=2`。
- 该策略不需要知道 Oracle 顺序，也不需要读 `judge_state`；它把“先开供氧、切臂后 2 tick 内回切”作为显式规则。
- 判定：**不构成 `INTERFACE_BLOCKED`**，也不构成 `BUDGET_BLOCKED`（15 ≪ 30）。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 18 |
| 决策预算 | 30 |
| 公开启发式 | 15（成功） |
| `legal_random` 20 seed | 0/20 成功；20/20 `OXYGEN_SUPPLY_INTERRUPTION_LIMIT`；平均 4.0 决策；非法 0；被拒 32 |

- `legal_random` 的 20 个 seed **全部在第 4 个决策死亡**，终止码完全相同：随机采样把前 3 个免费 tick 用在 `move/inspect/wait` 上，第 4 个动作结算时 `oxygen_off_ticks=4`。这说明随机基线在本图是**退化的**（无法给出方差估计）。
- 判定：**不是预算不够，而是模型没做对**。R0 用了 11 个决策就拿到 4/6 依赖，剩余 19 个决策足够完成余下流程；R2 只用了 4 个决策，是规划起点错误。
- 反例边界：即使给到 30 决策，任何连续 4 个“不供氧”动作仍然必死，所以预算不是本图的约束面。

## 6. 指标

| 指标 | 类别/方向 | 计算事件与分母 | 缺失/截尾 | 本次三局 |
|---|---|---|---|---|
| `map01.completion_ticks` | diagnostic / lower | 成功局的 `terminal_tick` | 未成功 → `not_applicable`（不得填 0） | 3 局全 `not_applicable`（真分母 0：三局均失败） |
| `map01.dependency_satisfaction_rate` | primary / higher | `completed_required_edges / 6`，事件为 6 个依赖布尔位 | 有来源事件即 `valid` | 0.667 / 0.167 / 0.0 |
| `map01.dependency_violations` | diagnostic / lower | `count(ILLEGAL_PREREQUISITE_ORDER)` | 同上 | 1 / 4 / 0 |
| `map01.longest_oxygen_outage_ticks` | primary / lower | 每局最长连续 `oxygen_output=false` tick | 同上 | 4 / 3 / 4 |
| `map01.oxygen_guardrail_violations` | guardrail / lower | 终止码属于两类氧气失败的 0/1 | 同上 | 1 / 0 / 1 |

- **未通关仍有意义的连续主指标**：`dependency_satisfaction_rate` 与 `longest_oxygen_outage_ticks` 都在失败局有值，且三局分别取 0.667/0.167/0.0 与 4/3/4，能反映“走到链条哪一步”。
- 三局 `not_applicable` 只出现在 `completion_ticks`，原因是**真分母 0**（无成功局），不是投影口径问题。
- 区分度：`dependency_satisfaction_rate` 可区分 随机(0.0)、R1(0.167)、R0(0.667)、启发式(1.0)、消融(0.5)；`dependency_violations` 只区分 R1(4) 与其他(0/1)。存在可用判别力。

## 7. 三次轨迹归因

### 7.1 R0（`V8-MAP-01-R0-…-ca460a38`，11 决策，`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`）

原文引用：

1. 决策 6 `{"choice": "apply_patch", "target": "hull_panel", "tool": "interact"}` → `ARM_UNPOWERED`，`delta: {}`（观察无任何变化）。
2. 决策 8 `{"choice": "route_arm", "target": "local_breaker", "tool": "interact"}` → `REPAIR_ARM_ON`，`delta: {"oxygen_output": false, "oxygen_reserve": 17, "repair_arm": true, "routed_branch": "arm"}`。
3. 决策 10 `{"edge_id": "W_P_SERVICE", "tool": "move"}` → `MOVED:P`，`delta: {"location": "P", "oxygen_reserve": 15, ...}`。
4. 决策 11 `{"choice": "reset_bus", "target": "main_reactor", "tool": "interact"}` → `BUS_ON`，`delta: {"main_bus": true, "oxygen_reserve": 14, "terminal": true, "terminal_reason": "OXYGEN_SUPPLY_INTERRUPTION_LIMIT"}`。

**首次偏离合理策略的可观测事件**：决策 6 的 `ARM_UNPOWERED`——它在 `routed_branch="support"` 时试图补壳，说明没有建立“维修臂必须先上电”的前置。

**失败链**：决策 6 顺序错误（耗 1 tick，无副作用）→ 决策 7 试图走 `W_P_SERVICE`（`EDGE_LOCKED_HULL_OPEN`）→ 决策 8 才切臂 → 决策 9 补壳（成功）→ **决策 10 未回切供氧就离开 W**，`oxygen_output` 从决策 8 起一直为 false，决策 11 结算时第 4 个断供 tick 直接判死。它已经完成了 4/6 依赖（`PICKED`、`REPAIR_ARM_ON`、`HULL_PATCHED`、`BUS_ON`），只差一次 `route_support`。

**替代解释**：不是预算（11/30）、不是接口（`ARM_UNPOWERED` 是明确拒绝码）、不是非法动作（0）。主因是**把“补壳”当作终点，漏掉“回切供氧”这一必须的收尾步骤**。

### 7.2 R1（`V8-MAP-01-R1-…-48162592`，22 决策，`BUS_RESET_WITH_HULL_OPEN`）

原文引用：

1. 决策 8 `{"choice": "apply_patch", "target": "hull_panel", "tool": "interact"}` → `ARM_UNPOWERED`，`delta: {}`。
2. 决策 17 `{"choice": "apply_patch", "target": "hull_panel", "tool": "interact"}` → `ARM_UNPOWERED`，`delta: {}`（第 3 次同一拒绝码）。
3. 决策 21 `{"edge_id": "H_P", "tool": "move"}` → `MOVED:P`，`delta: {"location": "P", "visible_edges": ["H_P", "W_P_SERVICE"]}`。
4. 决策 22 `{"choice": "reset_bus", "target": "main_reactor", "tool": "interact"}` → `BUS_RESET_WITH_HULL_OPEN`，`delta: {"terminal": true, "terminal_reason": "BUS_RESET_WITH_HULL_OPEN"}`。

**首次偏离**：决策 8 的 `ARM_UNPOWERED`（与 R0 同型）。此后它在 W 与 H 之间来回 6 次（决策 6/11/13/15/16/20 的 `H_W` 或 `B_H`）、重复 `apply_patch` 3 次（决策 8/10/17），从未尝试 `local_breaker/route_arm`——而该动作就在 prompt 的公开词表里，且 `repair_arm=false` 在 Observation 中一直可见。

**失败链**：把“补壳失败”反复归因为“位置/时机不对”，没有把 `repair_arm` 这个公开布尔位读成前置 → 绕过补壳直接走 `H_P` 到 P → 在 `hull_intact=false` 时复位母线，触发 fail-fast。

**替代解释**：预算充足（22/30）、动作全部合法形状（`invalid=0`）。这是**反馈使用失败**：同一个明确拒绝码 `ARM_UNPOWERED` 出现 3 次仍未改变假设。

### 7.3 R2（`V8-MAP-01-R2-…-b3547066`，4 决策，`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`）

原文引用：

1. 决策 1 `{"target": "oxygen_relay", "tool": "inspect"}` → `TARGET_NOT_VISIBLE`，`delta: {"oxygen_reserve": 17}`。
2. 决策 3 `{"target": "power_diagram", "tool": "inspect"}` → `DIAGRAM:capacity=6,fixed=3,support=2,arm=2`，`delta: {"oxygen_reserve": 15}`。
3. 决策 4 `{"edge_id": "H_W", "tool": "move"}` → `MOVED:W`，`delta: {"location": "W", "oxygen_reserve": 14, "terminal": true, "terminal_reason": "OXYGEN_SUPPLY_INTERRUPTION_LIMIT"}`。

**首次偏离**：决策 1。公开词表明确给出 `interact(target, choice): oxygen_relay/start_support`，模型却选了 `inspect`，把唯一可用的“立刻开供氧”动作变成了无效果观察，并在同一个 Observation 里看到 `oxygen_reserve` 从 18 掉到 17 仍未纠正。

**失败链**：决策 1 用错工具 → 决策 2 移动 → 决策 3 观察配电图（此时 reserve=15，已用掉 2 个免费 tick）→ 决策 4 移动结算第 4 个断供 tick，终局。

**替代解释**：接口误导（`inspect` 与 `interact` 都在契约里，且位置对象表写着 `B/H=oxygen_relay`）可以解释第一次错误；但 Observation 的 `oxygen_reserve` 每步递减是公开且显著的，连续 3 次未响应属于策略错误。

### 7.4 重复证据的边界

三局只有 R0 与 R1 在“补壳前不切臂”这一点上重复（2/3）；R2 是另一类错误（工具选择错误）。n=3 只能说明这张图存在**两个固定陷阱**（互斥顺序、开局供氧），不能区分个体差异与模型固有倾向。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E 策略规划错误**（未把“回切供氧”纳入计划） | G 记忆/推理（漏掉已建立的中间状态） | 高 | 决策 8 `oxygen_output=false`、决策 10 离开 W、决策 11 终局 |
| R1 | **E 策略规划错误**（反复忽略 `repair_arm=false`，绕过补壳） | G 反馈使用失败 | 高 | 决策 8/10/17 `ARM_UNPOWERED`、决策 21-22 |
| R2 | **E 策略规划错误**（用 `inspect` 代替 `interact`，开局不供氧） | C 接口误导（`inspect`/`interact` 同名对象） | 中高 | 决策 1 `TARGET_NOT_VISIBLE`、决策 4 终局 |

无 A（规则缺陷）、D（预算）、H（运行异常）证据。首因均为 E，说明本图测到的主要是**依赖链规划**而非资源或接口问题。

## 9. 标签

- **`MEASUREMENT_VALID`**：存在仅凭公开 Observation 的 15 步成功策略（`runs/v9/baselines/MAP-01.json`），三局失败码与 Trace 一致，指标在三局均有值且能区分 0.0 / 0.167 / 0.667 / 1.0。
- 不标 `INTERFACE_BLOCKED`：断供阈值已在 prompt 公开，互斥后果一步内可观测。
- 不标 `BUDGET_BLOCKED`：15/30 与 11/30 都远未触顶。
- 不标 `RULE_DEFECT`：所有终局都能从公开状态机复算，未发现规则与文档矛盾。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：`map01.py` 的 6 条依赖与互斥支路；prompt 已公开断供规则。
- 证据与根因：R0/R1 的根因是策略错误（E），不是信息缺失；R2 的 `inspect`/`interact` 混淆可由公开词表纠正。
- 候选 A（补公开信息，低风险）：在词表里补一行“`route_arm` 会使供氧支路断电，必须在补壳后用 `route_support` 回切”。**不建议**：该后果已在 `oxygen_output=false` 中一步可见，补文本会削弱“跟踪自身动作副作用”的构念。
- 候选 B（改规则）：给 `route_arm` 增加“先自动回切”或延长断供窗。**拒绝**：这会移除本图唯一的硬约束，使 3/30 的失败变为无代价。
- 结论：**无修复，保持只读**。本图作为“依赖规划 + 自跟踪副作用”的简单图成立，V8 的 0/3 是有效的能力测量结果。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-01.json`（本次运行）：

| 策略 | 成功 | 决策 | 终止码 | `dependency_satisfaction_rate` | `longest_oxygen_outage_ticks` |
|---|---|---|---|---|---|
| Oracle `default` | 是 | 18 | `REPAIR_CONFIRMED` | —（Oracle 只记录动作与状态） | — |
| `legal_random`（20 seed） | 0/20 | 4.0 平均 | `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` ×20 | 0.0 | 4 |
| `public_heuristic` | 是 | 15 | `REPAIR_CONFIRMED` | 1.0（6/6） | 2 |
| 消融 `no_support_handoff` | 否 | 8 | `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` | 0.5（3/6） | 4 |

**独立复算**（不调用 `map01.metrics()`，只读 `public_heuristic.actions[*].observation_after` 的公开字段流）：

- 依赖分子：`patch_kit` 首次进入 `inventory`（决策 4）计 1；`routed_branch` 首次变为 `arm`（决策 5）计 1；`hull_intact` 由 false→true（决策 6）计 1；`main_bus` false→true（决策 9）计 1；`pressure_test` 由 `not_done`→`pass`（决策 12）计 1；`terminal_reason=="REPAIR_CONFIRMED"`（决策 15）计 1 → **6/6**，与 extractor 一致。
- 最长断供：`oxygen_output` 在决策 5、6 为 false，决策 7 恢复 → **2**，与 extractor 一致。
- 同一算法对消融轨迹给出 3/6 与 4，与 extractor 一致；对 `legal_random` seed 0 给出 0/6 与 4，一致。
- 判别力：可区分四种策略（0.0 / 0.5 / 1.0 与 2 vs 4），**不是** `LOW_DISCRIMINATION`。

## 12. V9 状态

**`VALIDATED`，优先级 P2。**

一句话理由：存在 15 决策、零非法动作的纯公开信息成功策略，三局失败均为可定位的策略错误而非规则/信息/预算缺陷；无需 DCR，保留只读。

（`VALIDATED` 是本审计的机器推导结论，**待用户确认**，不构成人工审核。）
