# MAP-21｜火山｜困难｜喷发倒计时

```yaml
map_id: MAP-21
world: volcano
nominal_level: 困难
capability_primary: risk_conditioned_stopping
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: eb8eb1f9ae8846fc57884f4850f99fb0ae19383368f832794074b1e4e4049aee
source_design_hash: f24289ecbad95b18d3770013106d63e07cd4cf7b3533a25b66d59f4085af461e
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“风险条件下的停手决策”。喷发时刻只可能是 tick 12/16/20，先验 `0.2/0.5/0.3`；没有公开倒计时，唯一的信息动作是 O 处**一次**耗时 2 tick 的有噪测量（早报/晚报），后验公开。Agent 要决定是否测量、取哪一级样品、是否花 1 tick 加固、走到多深再撤。核心不是“跑得快”，而是**用后验决定何时停止增值**：深部样品 50 分但 tick14 才到 E，T=12 必死；中阶不加固恰好 tick12 到 E 安全，加固 1 tick 就跨过生死边界。

## 2. 真实规则字段

- 拓扑：`O—R—W—S—E`，段耗时 `1/2/2/2`；另有 `O—E` 直达 6 tick；每条边双向，途中不能换边。
- 位置、已走时间、可达边公开；**不显示**“距喷发还剩几 tick”。
- 隐藏真值：`T ∈ {12,16,20}`，先验 `0.2/0.5/0.3`；`eruption_tick` 私有。
- 测量：O 处每局一次、耗 2 tick，返回 `EARLY/LATE`；似然 `P(EARLY|12)=0.8, P(EARLY|16)=0.3, P(EARLY|20)=0.1`；后验公开（早报 `[8/17,15/34,3/34]`，晚报 `[2/33,35/66,9/22]`）。先验熵 1.02965 nats，期望后验熵 0.89166，信息增益 0.13800 nats。
- 样品：每局只能带 1 件。`R` 表层灰 1 tick / 5 分；`W` 层理芯 5 tick / 未加固 12、加固 20；`S` 深部同位素芯 6 tick / 未加固 40、加固 50。加固 1 tick，只在 W/S，不改变喷发与路程。
- 计分：进 E 得 100；样品到 E 才计分；带回测量记录 +2；喷发时不在 E → 立即 0 分。
- 事件序：逐 tick 推进；**先完成抵边再检查同 tick 喷发**，所以 tick12 进 E 仍安全。
- 动作：`move`、`measure`、`reinforce_sample_case`、`collect_and_carry_sample`。
- 失败：`FATAL_ERUPTION`；成功：`EVACUATED_BEFORE_ERUPTION`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map21.risk_exposure_integral` | primary | Σ_t `P(T ≤ t | 当前信息) × 1[仍在 E 外且存活]`，后验取公开值 | 风险·tick / 低 | 有效 tick | 无后验 → UNAVAILABLE；截尾只累计已观察 tick |
| `map21.evacuation_coverage` | primary | 已撤出单位 / 已投入单位；单位 = 人员 1 + 已采样品 1 + 已取得测量记录 1 | 比例 / 高 | 已投入单位（1–3） | 分母 0 → N/A |
| `map21.false_safety_claims` | guardrail | `count(FALSE_SAFETY_CLAIM)` | 次 / 低 | episode | **当前无 claim 动作 → 恒 0，须标 UNAVAILABLE** |
| `map21.late_evacuation` | diagnostic | `1[T < 最后撤离到达 tick]`，未撤离按 +∞ | 0/1 / 低 | 发生喷发的 episode | 无喷发 → N/A |

实现状态：**未实现**（`implemented=False`）。`risk_exposure_integral` 使用**公开后验**而不是私有 `T`，因此不以真值泄漏为代价；单局 trace 的积分是“该局实际存活路径上的暴露”，期望值需按 `map_spec` 的全枚举另外计算。

## 4. 能力混淆分析

- 低风险暴露可能只是“早撤”：直达 E 计划暴露 0、得分 100，但科研 0；必须与 `evacuation_coverage`、科研分并列。
- 高覆盖率可能来自“只带人和数据、不带样品”：覆盖率 1.0 不等于高价值打捞。
- 高期望分可能靠一次幸运 seed：`map_spec` 明确要求对三个 T 与两种信号**全枚举**求期望，单局分数不能排名。
- `late_evacuation` 与死亡不是同义词：tick 介于最后行动与喷发之间仍可能生还；它是“撤离晚于喷发”的归因，不是结果分。
- `false_safety_claims` 在现有动作集下**无法触发**（没有承诺/广播动作），把它当 0 分会伪造安全表现。

## 5. 两条手算轨迹

**A. 精确边界中阶样（不测量，tick12 抵 E）**：`O→R`(1) → `R→W`(2，累计 3) → 取 W 层理芯 5 tick（累计 8）→ `W→S`(2，10) → `S→E`(2，12)。指标：`evacuation_coverage = 2/2 = 1.0`（人 + 样品）；`risk_exposure_integral = 0`（tick<12 时公开后验 `P(T≤t)=0`，tick12 已在 E）；`late_evacuation = 0`；科研 12 分、总分 112、死亡概率 0。

**B. 冒险深部高值样（不测量，tick14 抵 E）**：`O→R`(1) → `R→W`(3) → `W→S`(5) → 加固 1 tick（6）→ 取 S 深部芯 6 tick（12）→ `S→E`(14)。指标：`evacuation_coverage = 2/2 = 1.0`（在 T=16/20 世界）；`risk_exposure_integral` 在 T=16 实际轨迹为 `tick12 + tick13 = 0.2 + 0.2 = 0.4`；T=12 轨迹在 tick12 死亡，仅累计 `0.2`；`late_evacuation` 在 T=12 为 1；期望 120 分、死亡概率 20%。

> A 与 B 的差别只有“是否多走 2 tick 到 S 并加固/采集”：A 死亡概率 0、112 分；B 死亡概率 20%、期望 120 分。**期望更高不等于更安全**，两个指标必须分开报。C 计划“早撤保命”暴露 0、覆盖 1.0、100 分；D 计划“测量后分流”期望 112.02 分、死亡概率 4%。

## 6. 三个机制特有失败

1. **F01 盲取深部样**：T=12 时 tick12 仍在采集/离开 S 途中 → `FATAL_ERUPTION`，总分 0。风险暴露在死亡 tick 截断。
2. **F02 晚报分支仍走加固中阶**：实际 T=12 却抽到合法的晚报，按 tick15 路线行动，tick12 途中死亡。后验里 `P(T=12|LATE)=2/33≈6.06%` 不能被当 0。
3. **F03 收到早报仍追深部样**：早报后 `P(T=12)=8/17≈47.06%`，仍去 S，喷发时滞留 → 死亡。信息已获得但未被使用，属“信息使用”失败而非“信息不足”。

## 7. 两个边界

- **不加固 W 样 tick12 恰好到 E 成功（B01）vs 多加固 1 tick 失败（B02）**：同一路线只差 1 tick，生死翻转。事件序“到边先于喷发判定”必须固定，否则 B01 会被误判为死亡。
- **两种传感器结果的后验（B03）**：早报后验 `[8/17,15/34,3/34]`、晚报 `[2/33,35/66,9/22]`；两者之和必须为 1。任何“报告等于真值”的简化都会让 MAP-21 退化为已知 T 的路线题。

## 8. 信息泄漏负例

若 Observation 或 prompt 给出 `eruption_tick`、剩余 tick、随机抽样值或“晚报可以放心走深部”，风险决策被替代。V7 只允许公开位置、已走时间、可达边、后验、样品档位、加固可用性、携带物与终局；`private_seed_reference.yaml`、`decision_reference.json`、Oracle 与全枚举表只在离线侧。设计还要求公共 Oracle 只展示报告/后验/位置/行动，不输出隐藏 T 或随机数。

## 9. Oracle/求解状态

`planning/hand_traces.json` 有四条手写计划（早撤、测量分流、精确边界中阶、冒险深部），`decision_reference.json` 给出全枚举期望（100 / 112.02 / 112 / 120 分，死亡概率 0 / 4% / 0 / 20%），`failure_traces/cases.yaml` 有 F01–F03，`private_seed_reference.yaml` 固定 seed0 为 T=16、抽样 0.42（返回晚报）。**没有运行时、没有真实模型实验**；纸面枚举证明四策略的期望值，不证明存在更优策略。

## 10. 与同世界另两图差异

**vs MAP-19**：MAP-19 完全确定、无信息动作、核心是两 tick 控制延迟；MAP-21 有隐藏时刻、贝叶斯测量与生死阈值，核心是“何时停手”。MAP-19 没有“冒险”选项。

**vs MAP-20**：MAP-20 是确定性的多节点流量分配，失败来自越界；MAP-21 的失败来自**时间**（喷发时不在 E），资源只有“剩余 tick”。MAP-20 的指标是节点温度，MAP-21 的指标是风险暴露与撤离覆盖。

## 11. 可计算性来源

需要的公开字段：`elapsed_tick, current_node_or_in_transit_edge, available_adjacent_edges, measurement_available, returned_measurement_if_any, posterior_over_eruption_ticks, visible_local_sample_tier, reinforcement_kit_available, carried_sample_tier, terminal, terminal_reason, terminal_score`，以及动作与耗时。风险积分由公开后验与位置逐 tick 重算；覆盖率由“已投入/已撤出单位”重算；`late_evacuation` 需要 `terminal_reason` 与最后到达 tick。`false_safety_claims` 缺少对应动作，只能报 UNAVAILABLE。

## 12. 难度定位与对照

D=(3,2,3,2,2,3)。相对 MAP-20 提升 **V↑（喷发时刻隐藏，仅有噪信号）与 E↑（隐藏时限 + 概率事件）**；R 从 3 降到 2（只剩时间与一次性加固）。不会与 MAP-20 混淆：MAP-20 无水/热分配，MAP-21 无流量约束；两者指标无交集。

预登记对照：**公开后验 vs 仅公开原始信号（需自行贝叶斯）**。这是信息可用性实验（`V7-DCR-005` 类），不能称“纯能力提升”；两组共享同一 `T` 抽样与似然表。另需 **加固可用 vs 禁用** 对照，验证生死边界确实由 1 tick 决定。

## 13. 未决

- `map21.false_safety_claims` 在现有动作集中不可触发，`FALSE_SAFETY_CLAIM` 原因码也不在 `reason_codes` 中；需人工决定是新增“安全承诺”动作，还是把该 metric 标为 UNAVAILABLE（不得报假 0）。
- 风险积分的 `risk_t` 采用“公开后验的累积概率”；若运行时后验字段不可用，需退化为仅用原始信号重算，并标明口径。
- `evacuation_coverage` 的分母随“是否采样品/是否测量”变化，跨策略比较时须同时报分母。
- 无运行时、无真实模型结果；四策略期望值为纸面全枚举。状态 `human_approved`。
