# MAP-03 逐图审计：最后的百步

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-03 / spaceship / 困难 |
| condition | `default` |
| `scenario_hash` | `9c322bb5a43955af1ae85b8cb79eba8126fcdd5b0782f16b26661683de941879` |
| `rule_hash` | `ba6ee7abcbb1bf4fa915ca43a22985640b9378cd38c3483eed56f6e83ea8dad4` |
| `prompt_hash` | `8647f5409b23c375c44ba630c55f9f6d5be3b5e36d5d4c3cd6135244e3d8c998` |
| `metric_schema_hash` | `54cbe1b6893f87f5f236741bb92daea7c25724d8ffce4440a5ab75aa6fab0a82` |
| `oracle_hash` | `0ba3a97587da65b4cd8cfc4dd85a4673ddac6bb6edb4afac6dd56716a923f335` |
| 决策预算 | 46（`BUDGETS["困难"]`） |
| V8 三局 | 0/3 成功；`EVA_OXYGEN_EXHAUSTED`（R0，28 决策）、`EVA_OXYGEN_EXHAUSTED`（R1，21 决策）、`SAMPLE_COLD_WINDOW_EXPIRED`（R2，27 决策） |

数据来源：`runs/v9/evidence/MAP-03.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-03-final.md`、`worlds/v4/MAP-03/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map03.py`、`src/agent_arena/v8/{runner.py,prompts.py}`、`src/agent_arena/llm/openai.py`、`runs/v9/baselines/MAP-03.json`（本次生成）。

## 1. 能力构念

**一句话**：在一条五阶段、强前置的里程碑链上保持长期目标，并把只在第 15 个动作附近出现**一次**的航线码 K7 保留到第 30 个动作、在起点 U2 精确复用。

**成功行为**：`P1`（D1 恢复辅助供电）→ `P2`（U1 读码后 4 tick 内冷藏样本）→ `P3`（V 修天线）→ `P4`（U3 发遥测）→ `P5`（U2 提交 `K7`），成功码 `ROUTE_CALIBRATED`，且不触发 EVA、冷窗、返航窗三类失败。

**明确反例**：
- 先跑去看天线（V）再补供电：`antenna/repair` 返回 `PHASE_OUT_OF_ORDER`，且每次进出 V 都在消耗 EVA；
- 读到 K7 后离开 U1 再回头：冷窗 4 tick 内样本失效（`SAMPLE_COLD_WINDOW_EXPIRED`）；
- 在 U2 提交错误的码：只有 1 次提交机会，`ROUTE_KEY_REJECTED` 直接失败；
- 把 K7 当作“之后还能再看到”的信息：`route_tag_value` 只在读码后的**一个** Observation 中出现。

**在本世界三图中的位置**：本图是本世界唯一的“长时程 + 一次性信息”图，动作数是三图最大（Oracle 30/31，预算 46），但真正的难点不是路程：**正确路线的最短完成时间就是 30 tick**，几乎没有绕路余量（返航窗 36）。它是三图中唯一同时具备“阶段顺序”与“远期召回”两个独立失败面的图。

## 2. 机制与因果链

**本图专属因果链**：

`U2 起始，aux_power=false、eva_supply=3、milestones 全 false、return_window_end_tick=36`
→ **必需观察**：`goal`（“完成供电、样本保全、天线修复、遥测与 K7 航线校准”，顺序即 P1→P5）、`milestones` 五个布尔位、`sample_thermal_ticks=null`
→ **关键决策 1**：D1 `aux_panel/restore_power`（`AUX_POWER_ON`，同时点亮 cryo/communications，`P1=true`）
→ **关键决策 2**：U1 `sample_manifest/read_tag`（`TAG:K7`，同时 `route_tag_read=true`、`sample_thermal_ticks=4`、`route_tag_value="K7"`）
→ **关键决策 3**：U1 `cryo_case/stabilize_sample`（`SAMPLE_STABILIZED`，`P2=true`，冷窗关闭）
→ **关键决策 4**：D3→V（`EVA_UNIT_SPENT`，`eva_supply 3→2`）→ `antenna/repair`（`ANTENNA_REPAIRED`，`P3=true`，`eva_supply 2→1`）
→ **关键决策 5**：U3 `telemetry/transmit`（`P4=true`）→ **关键决策 6**：U2 `submit/route_console` 且 `answer="K7"`（`P5=true`，成功）
→ **终局**：`ROUTE_CALIBRATED`，tick 30

**可绕过点**：
- `inspect telemetry_panel`（U3）会返回 `TELEMETRY_REQUIRES_REPAIRED_ANTENNA`，是公开的依赖提示，但**不是**必需动作。
- 五阶段之间**不可绕过**：`_submit` 要求 `P1..P4` 全为 true；`stabilize` 要求 `aux_power and route_tag_read`；`antenna/repair` 要求 `P1 and P2`；`telemetry` 要求 `P3`。每一次跳步都会得到 `PHASE_OUT_OF_ORDER` 并计入 `phase_order_violations`。
- **EVA 约束不是硬前置**：`eva_supply` 只限制“进入 V 的次数”，不阻止任何里程碑；它只会让浪费式往返提前终局（见 §10 的规则漂移）。

**机制是否在三条真实轨迹中触发**：
- R0：**触发**冷窗机制未触发（从未读码），EVA 机制触发（决策 11 进入 V、18 再次进入、28 第三次进入时归零）。
- R1：**触发** EVA（决策 6、15、21 三次进入 V，第三次归零），阶段顺序拒绝 1 次（决策 7）。
- R2：**触发**冷窗（决策 23 读到 K7 后 `sample_thermal_ticks` 4→3→2→1→0）、阶段顺序拒绝 2 次（决策 9、22），EVA 未被耗尽。

**触发所需最小动作数**：读码最早在第 15 个动作（6 移动到 D1 + 1 次 restore + 7 移动回 U1 + read）；成功最早在第 30 个动作（与 Oracle `milestone_first` 完全一致）。冷窗只给**4 tick**，而读码到冷藏只需 1 个动作，所以冷窗惩罚的是“读码后继续赶路”而不是“读码本身”。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `visible_edges` | 是 | 每步 | 是（九节点图可由边标识复原） |
| `aux_power` / `cryo_power` / `communications_power` | 是 | 每步 | 是 |
| `milestones`（P1–P5）与 `milestones_completed` | 是 | 每步 | 是（阶段进度完全公开） |
| `route_tag_read` / `sample_cold` / `sample_thermal_ticks` | 是 | 每步（冷窗倒计时在读码后逐步递减） | 是 |
| `route_tag_value` | **是，但只在一个 Observation 内** | 执行 `read_tag` 后的那一步 | **本身足够，但需要 Agent 自己有跨步存储** |
| `eva_supply` / `eva_active` | 是 | 每步 | 是（进入 V 后可见 3→2→1→0） |
| `return_window_end_tick=36` | 是 | 第 0 步 | 是 |
| 阶段前置（P1<P2<P3<P4<P5） | 部分：`goal` 文本按顺序列出五个里程碑；违规时返回 `PHASE_OUT_OF_ORDER` | 第 0 步 / 违规时 | 是（顺序即公开目标文本，拒绝码提供反馈） |
| 冷窗长度 = 4 | 否（事前未写）；读码后以 `sample_thermal_ticks=4` 公开 | 读码后 | 是（倒计时可见，1 步内必须冷藏） |
| **EVA 计费点（进入扣 1 / 维修扣 1 / 退出不扣）** | 否（`evidence_or_rules.yaml` 写退出也扣，运行时不扣） | 第一次进出 V 后可由 `eva_supply` 推断 | 是（不依赖该细节也能成功，但会误导资源规划） |
| `judge_state`（`thermal_ticks`、`submissions`、`violations`） | 否 | — | 不需要 |
| Oracle 两条路径（30 / 31 步） | 否 | — | 不需要（30 步公开策略可复现） |

**关键接口事实（本图最重要的一条）**：`route_tag_value` 的公开窗口只有一步。`map03.py:105` 在每次 `_apply` 开头执行 `self.just_read_tag = False`，而 `_public()` 仅在 `just_read_tag` 为真时返回 `"K7"`；因此读码后的下一个动作一开始，该字段就变回 `null`（R2 决策 23 → 决策 24 的 `delta` 是直接证据：`{"route_tag_value": "K7"}` → `{"route_tag_value": null}`）。而 V8 模型侧可见的跨步上下文只有：

- `v8/runner.py:361-369`：`history.append({"action": …, "result": …, "tick": …})` —— **不含任何 Observation**（`result` 字符串会带上 `TAG:K7`，但它只活在最近 5 条窗口内：读码发生在第 15 个决策，窗口最远覆盖到第 20 个决策，而最早提交在第 30 个决策）；
- `v8/prompts.py:384-411`：用户消息 = 当前 Observation + 最近 5 条 history；
- `v8/runner.py:266-279`：`DecisionRequest` 未设置 `memory_data`（对比 `v5/runner.py:936`、`v6/runner.py:550` 都会设置）；
- `llm/openai.py:118-146`：`input` 只由 `memory_data`（若有）、Observation、`recent_history`、反馈拼接；`decision_reason` 不回灌；
- `v8/runner.py:82-91`：`_repeat_hint` 仅在最近 3 次结果完全相同的错误码时触发，`TAG:K7` 不会经此通道复现。

结论：**在 V8 的 default 条件下，K7 在模型可见上下文里最多存活 5 个决策，之后不可恢复**（详见 §4 与 §10）。这是接口层缺陷，不是环境规则缺陷。

## 4. 可解性与可观察性

- Oracle：2 个用例，`milestone_first` 30 步、`zone_first` 31 步；`baseline_run` 复算 `oracle_ok=2/2`。
- 仅凭公开信息的可执行策略：**存在**。`Map03Heuristic` 只用 `location`、`visible_edges`、`aux_power`、`route_tag_read`、`route_tag_value`、`sample_cold`、`milestones`、`telemetry`、`route_calibrated`，**30 决策成功**，`invalid=0`、`rejected=0`、`phase_order_violations=0`。它在决策 15 读到 `K7` 后，把值保存在策略自身状态里，直到决策 30 才使用（跨 15 个动作），证明**环境侧的信息是充分的**。
- **但该“自身状态”在 V8 模型接口里没有对应通道**：策略之所以能保存，是因为 V9 `run_policy` 会把每步的 `observation_after` 放进 `history`（`v9/baselines.py` 的 `history.append({... "observation_after": observations_after})`），而 V8 runner 的 history 只有 `action/result/tick`，且没有 note/memory 动作。三条真实轨迹中，R2 确实读到了 K7，但提交发生在读码后第 15 个决策，远超 `result` 字符串的 5 条窗口——它在需要提交时已无任何渠道取回该值。
- 因此本图的可解性要分两层：
  - **环境层**：公开信息充分，30 步策略可复现 → 不是 `INTERFACE_BLOCKED` 意义上的“必须知道隐藏规则才能避免秒失败”。
  - **V8 测量接口层**：`default` 条件不提供任何跨步记忆通道，`long_delay_recall_accuracy` 对**任何** LLM 都只能取 0（除非它把这个常量背下来）→ 该主指标 **`INTERFACE_BLOCKED`**。
- 判定：地图可解（P5 可由公开策略达成），但“远期召回”这一构念在 V8 当前请求协议下不可测量。这是本批最重要的测量有效性问题。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 30（milestone_first）/ 31（zone_first） |
| 决策预算 | 46 |
| 公开启发式 | 30（成功） |
| `legal_random` 20 seed | 0/20 成功；20/20 `RETURN_WINDOW_EXPIRED`；平均 36.0 决策；非法 0；被拒 407 |

- 随机基线 20 个 seed **全部恰好死在第 36 tick**（返航窗），与动作内容无关——这又一次说明随机基线在本图是**退化**的：它测到的是固定 horizon，而不是策略差异。407 次被拒动作说明随机采样在九节点图里几乎每一步都撞拒绝码（`TARGET_NOT_VISIBLE`/`EDGE_NOT_ADJACENT`）。
- 判定：**不是预算不够，而是模型没做对**。正确路线 30 步 / 预算 46，余量 16；三局分别用了 28、21、27 个决策，都没触顶，且都在“30 步最短路线”附近就失败。
- 需要单独指出：预算 46 对“30 步最优解”只留 16 步容错，而本图有 3 类会**立即终局**的错误（EVA 归零、冷窗归零、错码），因此有效容错比数字看起来更小。

## 6. 指标

| 指标 | 类别/方向 | 计算事件与分母 | 缺失/截尾 | 本次三局 |
|---|---|---|---|---|
| `map03.completion_ticks` | diagnostic / lower | 成功局 `terminal_tick` | 未成功 → `not_applicable` | 3 局全 N/A（真分母 0） |
| `map03.long_delay_recall_accuracy` | primary / higher | `correct_early_facts / required_early_facts` = 是否 `route_calibrated` | 4 个 valid | 0.0 / 0.0 / 0.0 |
| `map03.lost_sample` | diagnostic / lower | `terminal_reason==SAMPLE_COLD_WINDOW_EXPIRED` | 4 个 valid | 0 / 0 / 1 |
| `map03.phase_completion_coverage` | primary / higher | `completed_milestones / 5` | 4 个 valid | 0.2 / 0.2 / 0.2 |
| `map03.phase_order_violations` | guardrail / lower | `count(PHASE_OUT_OF_ORDER)` | 4 个 valid | 2 / 1 / 2 |

- **未通关仍有意义的连续主指标**：`phase_completion_coverage` 在失败局有值（三局均 0.2），`phase_order_violations` 也能反映“试错次数”。
- `not_applicable` 只出现在 `completion_ticks`（真分母 0）。
- **`long_delay_recall_accuracy` 名不副实**：它是 `route_calibrated` 的 0/1 重编码，与成功完全共线；三局全 0 且**被 §3 的接口缺陷强制为 0**。它无法区分“记不住 K7”与“根本没有渠道记住 K7”，因此作为“远期召回”指标是 **`METRIC_DEFECT`**（当前实现测的是二值完成，不是召回准确率）。
- 区分度：`phase_completion_coverage` 可区分 随机 0.0 / MiMo 0.2 / 消融 0.8（4/5）/ 启发式 1.0，判别力最好；`lost_sample` 只能区分 R2；`phase_order_violations` 区分 0/1/2，但这是“试错次数”，不是能力方向。

## 7. 三次轨迹归因

### 7.1 R0（`V8-MAP-03-R0-…-238898f5`，28 决策，`EVA_OXYGEN_EXHAUSTED`）

原文引用：

1. 决策 2 `{"target": "sample_manifest", "tool": "inspect"}` → `TARGET_NOT_VISIBLE`，`delta: {}`。
2. 决策 3 `{"choice": "read_tag", "target": "sample_manifest", "tool": "interact"}` → `PHASE_OUT_OF_ORDER`，`delta: {}`（此时 `aux_power=false`）。
3. 决策 11 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_UNIT_SPENT`，`delta: {"eva_active": true, "eva_supply": 2, "location": "V", ...}`。
4. 决策 18 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_UNIT_SPENT`，`delta: {"eva_active": true, "eva_supply": 1, "location": "V", ...}`。
5. 决策 20 `{"choice": "repair", "target": "antenna", "tool": "interact"}` → `PHASE_OUT_OF_ORDER`，`delta: {}`。
6. 决策 28 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_OXYGEN_EXHAUSTED`，`delta: {"eva_active": true, "eva_supply": 0, "location": "V", "terminal": true, ...}`。

**首次偏离**：决策 2——把 `sample_manifest` 当作 `inspect` 目标（该对象只支持 `interact/read_tag`）。紧接着决策 3 的 `PHASE_OUT_OF_ORDER` 已经把唯一缺失的前置（`aux_power`）说清楚，但模型没有回头去 D1。

**失败链**：决策 3 被拒后，决策 4-6 在 U1/U2 之间来回 3 次 → 决策 7-10 沿升降机走廊走到 D3 → 决策 11 首次进入 V（消耗 1）→ 决策 12-16 五次 `wait`（在 V 里空转，`eva_active=true`）→ 决策 17 退出 → 决策 18 **第二次**进入 V → 决策 20 在 V 里试修天线（`PHASE_OUT_OF_ORDER`，因为 P1/P2 都没做）→ 决策 21-24 才去 D1 补 P1 → 决策 25-27 回到 D3 → 决策 27 从 D3 试图修天线（`TARGET_NOT_VISIBLE`）→ 决策 28 **第三次**进入 V，`eva_supply 1→0`，终局。

**替代解释**：预算 28/46 不是原因；阶段顺序已在 `goal` 文本里按 P1→P5 列出，所以 B 也不成立。核心是**没有把 `goal` 的顺序当作执行顺序**，把“天线”当成了首要目标，并在 V 内空转消耗 EVA。

### 7.2 R1（`V8-MAP-03-R1-…-92eadacf`，21 决策，`EVA_OXYGEN_EXHAUSTED`）

原文引用：

1. 决策 6 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_UNIT_SPENT`，`delta: {"eva_active": true, "eva_supply": 2, "location": "V", ...}`。
2. 决策 7 `{"choice": "repair", "target": "antenna", "tool": "interact"}` → `PHASE_OUT_OF_ORDER`，`delta: {}`。
3. 决策 12 `{"choice": "restore_power", "target": "aux_panel", "tool": "interact"}` → `AUX_POWER_ON`，`delta: {"aux_power": true, "communications_power": true, "cryo_power": true, "milestones": {"P1": true, ...}, "milestones_completed": 1}`。
4. 决策 15 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_UNIT_SPENT`，`delta: {"eva_active": true, "eva_supply": 1, "location": "V", ...}`。
5. 决策 21 `{"edge_id": "D3_V", "tool": "move"}` → `EVA_OXYGEN_EXHAUSTED`，`delta: {"eva_active": true, "eva_supply": 0, "location": "V", "terminal": true, ...}`。

**首次偏离**：决策 6——在 `aux_power=false`、`milestones_completed=0` 时先跑去 V。

**失败链**：决策 6 进入 V → 决策 7 修天线被拒（明确告知阶段顺序）→ 决策 8 在 V 空转 1 tick → 决策 9-11 返回 D1（D3→D2→D1）→ 决策 12 补 P1（这一步说明它理解了 P1）→ 决策 13-14 又回 D3 → 决策 15 **第二次**进入 V（此时 P2 仍未完成）→ 决策 16-17 空转 → 决策 18 退出 → 决策 19-20 空转 → 决策 21 **第三次**进入 V 归零。

**替代解释**：它在决策 12 已经拿到 `P1=true` 与 `milestones_completed=1`，说明反馈被部分吸收；但“P2（读码冷藏）是 P3 的前置”这一条始终没有建立——`goal` 文本里“样本保全”排在“天线修复”之前，属于公开顺序提示，因此仍是 E/G 而非 B。

### 7.3 R2（`V8-MAP-03-R2-…-a8156d63`，27 决策，`SAMPLE_COLD_WINDOW_EXPIRED`）

原文引用：

1. 决策 2 `{"target": "telemetry_panel", "tool": "inspect"}` → `TELEMETRY_REQUIRES_REPAIRED_ANTENNA`，`delta: {}`（公开依赖提示）。
2. 决策 22 `{"choice": "stabilize_sample", "target": "cryo_case", "tool": "interact"}` → `PHASE_OUT_OF_ORDER`，`delta: {}`（在 `read_tag` 之前冷藏）。
3. 决策 23 `{"choice": "read_tag", "target": "sample_manifest", "tool": "interact"}` → `TAG:K7`，`delta: {"route_tag_read": true, "route_tag_value": "K7", "sample_thermal_ticks": 4}`。
4. 决策 24 `{"edge_id": "U1_U2", "tool": "move"}` → `EDGE_NOT_ADJACENT`，`delta: {"route_tag_value": null, "sample_thermal_ticks": 3}`。
5. 决策 25-27 `{"edge_id": "U2_U1"}` / `{"edge_id": "U3_U2"}` / `{"edge_id": "XU_U3"}` → `MOVED:U2` / `MOVED:U3` / `MOVED:XU`，`delta` 依次为 `{"sample_thermal_ticks": 2}`、`{"sample_thermal_ticks": 1}`、`{"sample_thermal_ticks": 0, "terminal": true, "terminal_reason": "SAMPLE_COLD_WINDOW_EXPIRED"}`。

**首次偏离**：决策 24。读到 K7 后，它没有在同一个地点执行 `cryo_case/stabilize_sample`，而是试图沿一个**不存在的边 id** `U1_U2` 离开（真实边是 `U2_U1`），白耗 1 tick；此后连续 3 个动作**背着 U1 方向走**（U2→U3→XU），而每一步的 `sample_thermal_ticks` 都在公开递减 3→2→1→0。

**失败链**：决策 22 提前冷藏被拒 → 决策 23 读码（冷窗 4）→ 决策 24 错误边 id（窗 3）→ 决策 25-27 继续远离 U1，窗 0 → 样本损失。它离成功只差“读码后立刻冷藏”这一个动作。

**替代解释**：`U1_U2` 这个错误边 id 是接口细节（公开边标识确实叫 `U2_U1`，方向不敏感，模型自行重排了 token）；但即使这一次不算，后面 3 步在**可见倒计时**下继续远离，无法用接口解释。主因 G（不使用当前 Observation 的倒计时），次因 E（读码后未建立“先冷藏再走”的局部计划）。

### 7.4 重复证据的边界

三局都**从未完成 P2**（读码 + 冷藏），因此五阶段链的后半段在真实模型上完全没有被测试到：`P3/P4/P5` 三局全 false。n=3 的同型失败（三局都先去 V、三局都跳过 P2）更像是“被最显眼的目标吸引”的固定陷阱，而不是个体差异。另一个统一现象：三局都没有在任何时刻提交过 `K7`，所以“远期召回”这一构念在 V8 数据里**一次都没有被真正测到**。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E 策略规划错误**（忽略 `goal` 的顺序，先去 V，V 内空转） | F 资源管理（三次进入 V 耗尽 EVA） | 高 | 决策 3 `PHASE_OUT_OF_ORDER`、11/18/28 三次 `EVA_UNIT_SPENT`/`EVA_OXYGEN_EXHAUSTED` |
| R1 | **E 策略规划错误**（P1 已完成后仍跳过 P2 直奔 V） | G 记忆/推理（`milestones_completed=1` 后未补 P2） | 高 | 决策 7 `PHASE_OUT_OF_ORDER`、12 `AUX_POWER_ON`、15/21 两次进入 V |
| R2 | **G 记忆/推理错误**（冷窗倒计时公开递减仍远离 U1） | E 局部规划（读码后未立即冷藏）、C 边 id 拼写（`U1_U2`） | 高 | 决策 23 `TAG:K7`、24 `EDGE_NOT_ADJACENT`、25-27 倒计时 3→2→1→0 |
| （全局） | **接口缺陷（非模型）**：`default` 条件无跨步记忆通道，K7 读到即丢 | — | 高 | §3 的四处代码位置 + R2 决策 23/24 的 `route_tag_value` 消失 |

不存在 A（环境规则缺陷导致秒败）、D（预算）、H（运行异常）证据；`B` 仅在“冷窗长度事前未公开”这一点上有弱证据，但读码后倒计时立即可见，且 `goal` 已给出阶段顺序，因此不作为首因。

## 9. 标签

- **`INTERFACE_BLOCKED`（限 `long_delay_recall_accuracy` / P5 的召回构念）**：V8 `default` 条件的请求载荷不携带历史 Observation、也没有 note/memory 动作，`route_tag_value` 只活一个 Observation，`TAG:K7` 的结果字符串也只活 5 个决策；而提交在读码后第 15 个决策。证据：`map03.py:105`、`v8/runner.py:361-369`、`v8/runner.py:266-279`、`llm/openai.py:118-146`，以及 R2 决策 23→24 的 `route_tag_value` 由 `"K7"` 变 `null`。
- **`MEASUREMENT_VALID`（限 `phase_completion_coverage` / `phase_order_violations`）**：这两个指标在三局有连续值（0.2 / 1–2）且能区分 随机 0.0、MiMo 0.2、消融 0.8、启发式 1.0。
- **`METRIC_DEFECT`（限 `long_delay_recall_accuracy`）**：实现是 `route_calibrated` 的 0/1 重编码，与成功共线；三局全 0 且被接口强制为 0，不能测“召回准确率”。
- **`RULE_DEFECT`（文档-规则不一致，低严重度）**：`evidence_or_rules.yaml` 与 `acceptance.md` 声明“进入、维修、返回各消耗 1（成功路线恰用 3 单位）”，运行时退出 V **不扣**（实测 Oracle 回放在第 24 步后 `eva_supply=1` 而非 0）。因此真实成本是“每次进入 1 + 维修 1”，成功路线只花 2，`successful_route_cost: 3` 与代码不符。
- 不标 `BUDGET_BLOCKED`：30/46、21/46、27/46。
- 不标 `CONSTRUCT_BYPASS`：五阶段每步都是硬门，没有绕过路径。

## 10. 最小可证伪修复（无证据不修改）

### 10.1 召回接口（P0，建议 DCR）

- 旧规则/旧公开信息：`route_tag_value` 仅一步可见；`default` 条件无记忆通道。
- 证据与根因：见 §3/§4。三条 Trace 中 R2 读到了 K7 却无法在 15 步后使用；策略实现证明环境侧信息充分，缺的是**模型侧可写通道**。
- 候选 A（补接口，**推荐**）：新增 agent-owned 的 `note`/`write_memory` 动作（与 MAP-22 的 `write_memory(facts)` 同型），把“已读到的航线码”写入一个公开的 `notes` 字段，后续请求原样回传。只增加一个可写通道，不改任何规则与判定。
  - 预期变化：`long_delay_recall_accuracy` 从“恒 0”变为可区分 0/1；MAP-03 的“远期召回”构念才真正被测量。
  - 反例与风险：若 `notes` 内容不受限制，模型可能写入超过 K7 的信息（例如把整段 Observation 抄进去），从而把记忆题变成抄写题。缓解：`notes` 只允许 `{route_key: string}` 且写入动作耗 1 tick。
- 候选 B（补公开信息，不推荐）：让 `route_tag_value` 在读码后常驻 Observation。风险：直接移除记忆构念，把 P5 变成“读一次就能用”。
- 候选 C（条件对照）：按 `evidence_or_rules.yaml` 原计划启用 `full_history / short_history / structured_memory` 三种记忆条件，分别测量。这是最贴合研究设计的方向，但需要 3 倍运行预算，且必须重新冻结 prompt/scenario hash。
- 结论：**必须走 DCR**，优先 A 或 C；在修复前，MAP-03 的 `long_delay_recall_accuracy` 不得作为能力结论。

### 10.2 EVA 计费点（P2，建议文档对齐而不是改规则）

- 旧规则/旧公开信息：`evidence_or_rules.yaml: consume_on: [move_D3_to_V, one_repair_action_at_V, move_V_to_D3]`；`acceptance.md`：“EVA 恰用 3 单位；进入、维修、返回各消耗 1”。运行时代码 `map03.py:113-122` 在 `move_edge` **之后**判断 `destination == "V" or self.node == "V"`，退出时 `node` 已是 D3，两个条件都不成立 → 退出不扣。
- 证据与根因：Oracle `milestone_first` 回放（本次手工执行）第 22 步 `eva_supply=2`、第 23 步 `=1`、第 24 步（退出 V）**仍为 1**，而 oracle 文本期望 `eva_supply=0`；`oracle.py:73-98` 的 `_expected_checks` 只校验 `location=`/`phase=`/`tick=`/`terminal=`，自由文本期望被忽略，所以这个偏差从未被 gate 拦住。
- 影响：真实成本是“每次进入 1 + 维修 1”，3 单位可支持**一次完整 sortie + 一次重进**；这解释了三局都出现“第 3 次进入才归零”。它没有制造假成功（本次启发式只用 1 次进入），但让资源约束比登记值更宽松，并给了失败策略重试空间。
- 候选 A（文档对齐，**推荐**）：把 YAML/acceptance 改为“每次进入 V 扣 1；维修扣 1；退出不扣；3 单位 = 1 次完整 sortie + 1 次重进”，并把 `successful_route_cost` 改为 2。行为不变，但需重算 `source_hash`。
- 候选 B（改规则）：把退出也计费，使 3 单位恰好等于一次 sortie。**不建议**：这是提高难度，会改变 `rule_hash` 与 V8 冻结口径，且与“V9 只做测量修复”的边界冲突。
- 结论：登记为 **DCR 候选（P2，文档优先）**；在裁决前，任何“EVA 恰好用 3 单位”的结论都应视为**未验证**。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-03.json`（本次运行）：

| 策略 | 成功 | 决策 | 终止码 | `phase_completion_coverage` | `long_delay_recall_accuracy` | `phase_order_violations` |
|---|---|---|---|---|---|---|
| Oracle `milestone_first` | 是 | 30 | `ROUTE_CALIBRATED` | — | — | — |
| Oracle `zone_first` | 是 | 31 | `ROUTE_CALIBRATED` | — | — | — |
| `legal_random`（20 seed） | 0/20 | 36.0 平均 | `RETURN_WINDOW_EXPIRED` ×20 | 0.0 | 0.0 | 0 |
| `public_heuristic` | 是 | 30 | `ROUTE_CALIBRATED` | 1.0（5/5） | 1.0 | 0 |
| 消融 `no_key_memory` | 否 | 30 | `ROUTE_KEY_REJECTED` | 0.8（4/5） | 0.0 | 0 |

**独立复算**（不调用 `map03.metrics()`，只读 `actions[*].observation_after` 的 `milestones` 与 `route_calibrated`）：

- `phase_completion_coverage`：启发式 `milestones` 依次在决策 7（P1）、16（P2）、23（P3）、28（P4）、30（P5）变 true → 5/5，与 extractor 一致；消融只到 P4 → 4/5，一致；随机 seed 0 终局无任何里程碑 → 0/5，一致。
- `long_delay_recall_accuracy`：启发式终局 `route_calibrated=true` → 1.0；消融在决策 30 提交 `K0` → `ROUTE_KEY_REJECTED`、`route_calibrated=false` → 0.0。两者一致，但这也再次说明该指标 = 成功与否。
- 另做一次**逐步重放**（`replay_all("MAP-03")` 的 `milestone_first`）：第 22 步 `eva_supply=2`、23 步 `=1`、24 步 `=1`，与 oracle 文本 `eva_supply=0` 不符 —— 即 §10.2 的证据。
- 判别力：`phase_completion_coverage` 可区分 0.0 / 0.2 / 0.8 / 1.0 四种策略，**不是** `LOW_DISCRIMINATION`；`long_delay_recall_accuracy` 在当前接口下无判别力。

## 12. V9 状态

**`NEEDS_REDESIGN`，优先级 P0。**

一句话理由：环境本身可解（30 步公开策略成功），但 V8 `default` 条件没有任何跨步记忆通道，`route_tag_value` 只公开一个 Observation，导致“远期召回”主指标对任何模型都恒为 0 —— 这是本批唯一一处**构念不可测量**的缺陷；同时 EVA 计费点与登记文档不一致（P2，文档修复）。

（`NEEDS_REDESIGN` 是本审计的机器推导结论，**待用户确认**，不构成人工审核；P0 只表示需要主控优先裁决 DCR，不表示已授权修改任何 V8 文件。）
