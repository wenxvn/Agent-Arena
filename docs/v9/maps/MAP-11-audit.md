# MAP-11 逐图审计：失联的小队

> 本文件由 V9 Batch 1 依据 Trace、证据包与源码重新推导；不复制 `docs/v8` 结论，不声称人工审核。状态待用户确认。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-11 失联的小队 / polar / 中等 |
| condition | `default` |
| `rule_hash` | `86334e9a3fa67b50ad93d3962a6b64b3a1bf20a52611747701b400edaaaa0e88` |
| `scenario_hash` | `bc26ce92ed45beb82b407c4970bf7174986a8b74edc5348dbadedd5d16a9d296` |
| 决策预算 | 38 |
| V8 三局 | 0/3 成功；`SUPPLY_SHORTAGE` ×3；决策 2 / 2 / 2 |

数据来源：`runs/v9/evidence/MAP-11.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-11.json`、`docs/v8/maps/MAP-11-final.md`、`worlds/v4/MAP-11/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl,weather_seed_fixture.yaml}`、`src/agent_arena/worlds/scenario_v8/maps/map11.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v9/policies/world_polar.py`。

## 1. 能力构念

**一句话**：在“短线快但每段贵且暴露于相关风暴、长线慢但便宜且无风暴”的分叉上，先用侦察信号更新风险判断，再决定是否为省时间承担冻伤风险，同时保证带够往返补给、赶在队员生命窗之前救人。

- 成功行为：抵达 S 完成 `rescue`，两人 `heat>0`，带人回到 B（`FULL_SAFE_RETURN`）。
- 明确反例：身上 0 补给就出发（三局全部如此，首段即死）；或只带 7 补给走短线（fixture `seven_supplies_cannot_close_short_loop`：救到人但回程 `SUPPLY_SHORTAGE`，已耗 6）；或在两次风暴的 seed 上仍走短线（fixture `false_negative_scout_two_storms`，seed 8：`BODY_HEAT_DEPLETED`）。
- 递进位置：polar 中等图；比 MAP-10 多出“风险 vs 时间”的显式决策与噪声信号，比 MAP-12 少跨期排程。本图是唯一带**随机风暴抽签**的 polar 图。

## 2. 机制与因果链

起始状态（tick 0）：`location=B`、`supply_depot_B=8`、`carried_supply=0`、`carried_supply_capacity=8`、`agent_heat=10`、`teammate_heat=10`、`teammate_life_remaining=15`、`posterior=0.5`、`forecast=0.35`、`visible_edges=[B_D_LONG,B_P_SHORT]`。
必需观察：`carried_supply=0`（不能空手出营）、`supply_depot_B=8`（有补给可取）、`teammate_life_remaining=15`（越慢越危险）、`forecast/posterior`（短期风险估计）。
关键决策：先在 B `resupply`，再 `scout`，然后按后验选短线（2 段 × 2 补给，有风暴）或长线（3 段 × 1 补给，无风暴）。
立即后果：每次短线段落地抽一次风暴；风暴使在场者 -6 体温（1 基础 + 5 额外）；负重返程每段 +1 tick。
终局：`S` 救人后原路返回 B。

- 可绕过核心机制的动作：**有**。`scout` 是可选动作，且 seed 0 的隐藏风暴掩码是 `0000`；不侦察、直接走短线也能成功（Oracle `quick_short_seed0`，6 动作）。也就是说，本图在 V8 实际使用的唯一 seed 上，**噪声预报机制完全未被触发**（3 局 `short_crossings_resolved=0`，一局风暴都没抽）。
- 机制触发：三局都在决策 2 触发“随身补给不足”分支，发生在任何风暴抽签之前；风暴与负重返程未被触发，生命窗只发生常规倒计时（15→13→12），没有触发 `TEAM_LIFE_EXPIRED`。
- 触发所需最小动作数：失败 **1** 步（带 0 补给 `move B_P_SHORT`）；成功 **6** 步（`resupply` + 2 段去 + `rescue` + 2 段回，不侦察）或 7 步（多一次 `scout`）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `tick` / `visible_edges` | 是（Observation） | tick 0 起 | 足以选边；B 处只见两条边 |
| `supply_depot_B` / `carried_supply` / `carried_supply_capacity` | 是 | tick 0 起 | 足以发现“身上 0、库 8、容量 8” |
| `agent_heat` / `teammate_heat` / `teammate_life_remaining` / `teammate_rescued` | 是 | tick 0 起 | 足以判断生命窗与冻伤终局 |
| `current_storm` / `posterior_unstable_probability_belief` / `forecast_storm_probability_per_short_crossing` | 是 | tick 0 起（后验随短线段更新） | 足以做风险决策，但只是后验，不含本 seed 掩码 |
| `last_scout_signal` / `short_crossings_resolved` | 是 | 侦察/穿越后 | 足以确认信号与已用抽签数 |
| 每条边的补给成本（短 2 / 长 1） | **否** | 只能从 `carried_supply` 的下降反推 | 不能事前计算 8 vs 6 |
| 风暴扣热 6（1+5） | **否** | 只能从 `agent_heat` 跳变反推 | 不能事前计算“两次风暴必死” |
| “补给不足的移动立即终局”（不可重试） | **否** | 失败即终局 | 不能事前推导 |
| 隐藏气象态 `hidden_regime` / 逐段 `hidden_storm_mask` | 否（只在 `judge_state`） | — | 否 |
| Oracle 路径/用例 | 否 | — | 否 |

证据：`map11.py` 的 `EDGE_SUPPLY`（第 49–56 行）与 `_cold(1 + (5 if storm else 0), ...)`（第 326 行）都只存在于代码；`_VOCABULARY["MAP-11"]`（`prompts.py` 第 188–192 行）只写“使用 visible_edges 中的边；负重返程需 loaded_return=true”，没有成本；`system_prompt()` 只拼接 goal 与契约。设计侧的 `map_spec.yaml` 第 11–15、64 行有完整成本，但不是运行时公开面。

## 4. 可解性与可观察性

- Oracle：3 个用例，`quick_short_seed0` 6 动作、`scout_then_short_seed0` 7 动作、`scout_then_long_seed7` 9 动作；`replay_all` 全部 `FULL_SAFE_RETURN`。
- **首步 `scout` 后直接 `move B_P_SHORT` 是否必然失败？是，且与 seed 无关。** `_move()` 在抽风暴之前检查 `self.carried < required`（`map11.py:213–216`），不足立即 `_fail("SUPPLY_SHORTAGE")`；`B_P_SHORT` 需要 2，起始随身 0。用审计 fixture 的 0–9 号 seed 逐一验证：10/10 都在第一步返回 `SUPPLY_SHORTAGE` 并终局。三局真实 Trace 的决策 2 与之一致。
- **公开 Observation 是否足以推断“必须先 resupply”？** 分两层：
  1. “我现在身上没有补给，出营前应补满”**可以**从 `carried_supply=0`、`carried_supply_capacity=8`、`supply_depot_B=8` 和词表中的 `resupply(quantity)` 推出，不需要知道每段成本。
  2. “短线往返正好需要 8、长线需要 6、少 1 点就必死”**不能**推出：成本与终局性都未公开。因此“必死”不是公开信息的必然结论，而是“忽略了一个公开的零值字段”的结果。
- 仅凭公开信息的成功策略（已验证）：`resupply 8` → `scout` → 若 `posterior≤0.5` 走短线（`B_P_SHORT`、`P_S_SHORT`）否则走长线（`B_D_LONG`、`D_Q_LONG`、`Q_S_LONG`）→ `S` 救人 → 原路返回。7 决策成功，`supply_spent=8`。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `quick_short_seed0` | 6 | `FULL_SAFE_RETURN` | rescue 1；cost 8 |
| Oracle `scout_then_short_seed0` | 7 | `FULL_SAFE_RETURN` | rescue 1；cost 8；clue 2 |
| Oracle `scout_then_long_seed7` | 9 | `FULL_SAFE_RETURN` | rescue 1；cost 6 |
| 公开启发式（seed 0） | 7 | `FULL_SAFE_RETURN` | rescue 1；cost/救援 8.0；clue 3 |
| 消融 `no_key_mechanism`（不补给） | 1 | `SUPPLY_SHORTAGE` | rescue 0；cost N/A |
| V8 MiMo R0/R1/R2 | 2 / 2 / 2 | `SUPPLY_SHORTAGE` | rescue 0；cost N/A |

`legal_random` 20 seed：0 成功；`SUPPLY_SHORTAGE` 14、`TEAM_LIFE_EXPIRED` 6；平均 6.7 决策；schema 非法 0。随机策略能同时踩到“没补给”和“拖到队员死亡”两个陷阱，说明二者都可达。

公开启发式在审计 fixture 的 0–9 号 seed 上 **9/10 成功**：0–7、9 成功（短线 7 决策或长线 9 决策），**seed 8 失败**（`BODY_HEAT_DEPLETED`，7 决策）。seed 8 的掩码是 `1001`（两次风暴）而侦察信号仍是 `falling`——这正是设计中的“噪声假阴性”尾部。该结果说明策略不是只对 seed 0 过拟合，也说明本图确有真实风险。

**判定：不是预算不够。** 预算 38，成功 6–9 步；三局在第 2 步终止。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map11.rescue_count` | 成功带回 B | 失联人数 | 0/0/0 | 无 N/A |
| `map11.resource_cost_per_rescue` | 已耗补给 / 获救人数 | 获救人数 | 分子 0、分母 0 → N/A | 3 局全 `not_applicable`（真分母 0，不是投影口径） |
| `map11.rescuer_hypothermia` | `BODY_HEAT_DEPLETED` | episode | 0/0/0 | 无 N/A |
| `map11.abandoned_reachable_targets` | 未获救且生命>0 | 初始可救援数 | 1/1/1 | 无 N/A |
| `map11.first_clue_delay` | 首次 `scout` 结果落地 tick | episode | 2/2/2 | 无 N/A |

- 未通关仍有意义的连续主指标：`abandoned_reachable_targets=1`（救不到人）与 `resource_cost_per_rescue`（本批因 0 救援而 N/A，无法给连续值）。
- N/A 原因：真分母为 0（没有获救者），不是缺少来源事件；投影为 `null` 正确。
- 区分能力：Oracle/启发式（rescue 1、cost 8.0 或 6.0、abandoned 0）vs MiMo/消融（rescue 0、cost N/A、abandoned 1）可区分。
- **方向性警告**：`first_clue_delay` 标为 lower_is_better，但三局失败者的取值是 2（先侦察后空手出发），成功启发式是 3（先补给再侦察）。数值更低的一侧反而更差；该指标只能描述“信息延迟”，不能单独当质量指标，否则会奖励致命的行为顺序。三局的 `rescuer_hypothermia` 与 `abandoned_reachable_targets` 均无方差 → 这两项在本批 **LOW_DISCRIMINATION**。

## 7. 三次轨迹归因

三局的动作与结果逐字相同（同一 seed 0、同一策略），下面以 R0 为主，R1/R2 只列差异。

### R0（`V8-MAP-11-R0-20261017T081943Z-1fac09c9`，2 决策，`SUPPLY_SHORTAGE`）

- 决策 1 `{"tool":"scout"}` → `SCOUT:falling`；观察变化 `{"forecast_storm_probability_per_short_crossing":0.2,"last_scout_signal":"falling","posterior_unstable_probability_belief":0.2,"teammate_life_remaining":13,"tick":2}`。
- 决策 2 `{"edge_id":"B_P_SHORT","loaded_return":false,"tool":"move"}` → `SUPPLY_SHORTAGE`；观察变化 `{"teammate_life_remaining":12,"terminal":true,"terminal_reason":"SUPPLY_SHORTAGE","tick":3}`。
- 首次偏离：决策 1 时 `carried_supply` 仍为 0（公开可见），模型把“先侦察”排在“先补给”之前；侦察本身合法，但它消耗了 2 tick 生命窗，且没有解决零补给。
- 失败链：0 补给 → 首段需要 2 → 检查失败 → 1 tick 后终局；补给未被扣除、位置未改变（终局 `supply_depot_B=8`、`carried_supply=0`）。
- 替代解释：接口误导（成本与终局性未公开）+ 策略错误（忽略公开的 0 值）。**不是**预算、不是风暴（`short_crossings_resolved=0`）、不是 schema（非法 0）。

### R1（`V8-MAP-11-R1-20261017T081949Z-88d39115`，2 决策）

- 决策 1 `scout` → `SCOUT:falling`，`{"forecast_storm_probability_per_short_crossing":0.2,"last_scout_signal":"falling","posterior_unstable_probability_belief":0.2,"teammate_life_remaining":13,"tick":2}`。
- 决策 2 `move B_P_SHORT` → `SUPPLY_SHORTAGE`，`{"teammate_life_remaining":12,"terminal":true,"terminal_reason":"SUPPLY_SHORTAGE","tick":3}`。

### R2（`V8-MAP-11-R2-20261017T081958Z-6bd77165`，2 决策）

- 与 R0/R1 逐字相同（决策 1 侦察、决策 2 首段移动）。

**重复证据有限**：三局完全同序列，n=3 不能区分个体差异与固定陷阱；从“三个独立采样都选了同一条零补给路线”看，更像固定陷阱而非偶然。三局都没有触发任何风暴抽签，因此本批数据**不能**用于评价风险策略能力。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0/R1/R2 | E/F 资源管理（公开可见 `carried_supply=0` 仍出营） | B 公开信息不足（每段补给成本与“不足即终局”未公开）；C 接口（`SUPPLY_SHORTAGE` 与 `supply_depot_B=8` 并存，未指明“随身仓”） | E 高 / B 高 / C 高（事实） | 决策 1–2；`map11.py:213–216`；prompt 词表 |

排除：A（规则自洽，3 个 Oracle 通过）、D（预算 38，成功 6）、G（无记忆需求）、H（0 非法、0 provider 错误）。

## 9. 标签

- `MEASUREMENT_VALID`：存在 7 步公开启发式成功；随机基线同时踩中两个真实陷阱；主要指标可区分救到/没救到。
- `INTERFACE_BLOCKED`（限定于“未公开的补给成本与致死性”）：模型无法从事前信息算出 8 与 6，也无法知道一次不足即终局。
- `CONSTRUCT_BYPASS`：V8 实际使用的唯一 seed 0 掩码为 `0000`，不侦察直接走短线即可成功（Oracle `quick_short_seed0`）；三局 `short_crossings_resolved=0`，噪声预报与风暴风险在正式数据中从未被触发。本批不能证明该图测量了“噪声预报下的风险策略”。

不选 `BUDGET_BLOCKED`、不选 `RULE_DEFECT`。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：规则不改；公开面缺“每段补给成本”和“补给不足即终局”；终止码不区分补给仓。
- 证据与根因：R0/R1/R2 决策 1–2；10 个审计 seed 的 0 补给首步全部 `SUPPLY_SHORTAGE`；seed 0 掩码 `0000` 使风险机制失效。
- 候选 A（优先，补公开信息）：在 `_VOCABULARY["MAP-11"]` 增加：“短线每段消耗 2 随身补给、长线每段 1；补给不足的移动立即失败；风暴使在场者额外失温 5。”预期：模型能算清 8/6 并知道不可试探；失败将更明确地归因于风险决策。反例/回归：seed 0 上短线往返只要 8，补满即安全，成功率可能升至 3/3，风险构念仍未被测量。
- 候选 B（只改命名）：`SUPPLY_SHORTAGE` → `CARRIED_SUPPLY_SHORTAGE`；影响 `rule_hash` 与旧 Trace，需新建 DCR 并重跑。
- 候选 C（协议层，非规则改动）：V9 复测时不要只跑 seed 0，至少在审计 fixture 的 0–9 号 seed 上重复，使至少一个不稳定 seed（如 5/7/8/9）进入样本；否则“风险策略”无法被测量。该候选会改变 run 协议与成本，需要另行登记预算，不能在 Batch 1 直接执行。
- 不建议：增加补给上限、延长生命窗、把首段失败改成软拒绝（会抹掉本图最清晰的资源前置信号）。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-11.json`：

| 类别 | 结果 |
|---|---|
| Oracle | 3/3 成功（6 / 7 / 9 动作） |
| `legal_random`（20 seed） | 0 成功；`SUPPLY_SHORTAGE` 14、`TEAM_LIFE_EXPIRED` 6；平均 6.7 决策；schema 非法 0；被拒 54 |
| `public_heuristic` | 成功，7 决策；rescue 1、cost 8.0、clue 3 |
| 消融 `no_key_mechanism` | 失败，1 决策，`SUPPLY_SHORTAGE` |

独立复算（不使用 `Map11Environment.metrics()`，只读公开 Observation）：补给总量守恒 `depot + carried + spent = 8`，终局 `depot=0、carried=0` → `spent=8`；`rescue_count=1`（成功且 `teammate_rescued=true`）；`resource_cost_per_rescue=8/1=8.0`；`first_clue_delay = 首次出现 last_scout_signal 的 tick = 3`；`rescuer_hypothermia=0`。与 extractor 逐项一致。对三局 MiMo 用同一公式复算：终局 `depot=8、carried=0` → `spent=8−8=0`，与 judge 的分子 0 一致；`first_clue_delay` 由决策 1 后 `last_scout_signal="falling"` 首次出现的 `tick=2` 复算，与 judge 的 2 一致。

**基线可复现性**：`ShapeSampler.from_environment` 当前显式排序动作形状（`baselines.py:136–144`），两个独立进程复算得到相同的 54 个被拒动作，`legal_random` 可重放。本审计过程中曾观察到未排序版本在两次进程间给出 45 与 50；当前实现已消除该问题，本文以当前值（54）为准。

## 12. V9 状态

`NEEDS_REDESIGN`（P1）。理由：补给前置本身是可测的，但 V8 的唯一 seed（0）让风暴与噪声预报机制完全空转，且“短缺即终局”未公开；0/3 的结论只能覆盖“出发前补给”这一子行为，不能覆盖本图宣称的风险策略构念。优先补公开信息（A），并把复测 seed 覆盖纳入协议决策（C）。
