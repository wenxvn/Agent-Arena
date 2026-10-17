# MAP-20 审计：冷却网络

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-20 / volcano / 中等 |
| condition | `default` |
| `rule_hash` | `983f83987d118852a14786cd7053721e7211b9334a1490cc62441c10486c52b5` |
| `scenario_hash` | `5a5bcd0ba3871f4eeecd48af7524a6321dbc9810a975fdf54ed99f54d8116490` |
| `source_hash` | `19eb982b2733f0e5f6ed5e46c5590d53a0ad577cf371a81b16107ada0d5c3d18` |
| `prompt_hash` | `2e9a5c9112ef3e60b160f93916978180e8e1ad3777dcc239f2f71ba3bf3a0753` |
| `metric_schema_hash` | `c3aad88588e64d69be592ee505fdf730c8c99feea98680eebd1e4f1c740e0269` |
| 决策预算 | 38 |
| V8 三局 | 2/3 成功；`failure`×1（`THERMAL_OVERHEAT`）、`success`×2（`PRODUCTION_TARGET_MET`）；决策 22 / 19 / 17 |

数据来源：`runs/v9/evidence/MAP-20.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-20-final.md`、`worlds/v4/MAP-20/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map20.py`、`src/agent_arena/v8/prompts.py`。本审计新增的只读产物为 `runs/v9/baselines/MAP-20.json` 与 `src/agent_arena/v9/policies/world_volcano.py`；未改写任何 V8 文件、账本或 Trace。

## 1. 能力构念

这张图声称测的是**在有损管网里做跨区水分配，同时守住三区热上限的能力**：每 tick 只有 6.0 单位来水，单支管 2.5 单位，区间旁路必损 20%，区阀 A/B/C 为 4.0/4.0/3.0，玩家要决定直供、旁路方向与负荷档。

- 成功行为：10 个结算 tick 内三区温度始终 `<= 10.0`，且产能 `>= 15`。
- 明确反例：保持 FULL 负荷却不给 A 区足够水——A 在 tick 1 到 9.0、tick 2 到 11.0 并熔断（`worlds/v4/MAP-20/evidence_or_rules.yaml::F01`）；R0 更晚，直到 tick 10 才到 12.0。
- 递进位置：本图是该世界的**中等**图。简单图（MAP-19）是“时滞 + 独立回路”，本图把时滞换成“无损水预算 + 有损旁路 + 区阀”的四重约束，困难图（MAP-21）则完全离开热/水，改测隐藏喷发时刻下的风险决策。

## 2. 机制与因果链

**本图专属因果链**

1. 起始状态：`direct_flow_tenths={A:20,B:20,C:20}`、`current_load_modes={FULL,FULL,FULL}`、`temperature_bands={A:WARM,B:WARM,C:COOL}`、`production_points=0/15`、`source_water_remaining_this_tick=0`（`initial_observation`）。
2. 必需观察：`previous_tick_flow_ledger.delivered_tenths`（每 tick 回显实际到区水量）、`temperature_bands`、`current_load_modes`、`production_points`、`flow_rules`（全部容量与 0.8 交付系数）。
3. 关键决策：选择直供向量与负荷档，使每区 `delivered >= 该区该档热量`；旁路只在需要把水从余量区搬到热点区时打开，且下游只收 4/5。
4. 立即后果：`wait` 时先算 `delivered`（直供 + 0.8×旁路 − 外送），任一区为负或超区阀 → 整帧拒绝、不推进时钟；否则按 `max(0, T + heat - delivered)` 同时更新三区，任一区 `> 100`（十分之一度）立即 `THERMAL_OVERHEAT`；安全则按负荷记产能。
5. 终局：tick 10 且产能 `>= 15` → `PRODUCTION_TARGET_MET`；否则 `PRODUCTION_BELOW_15`。

**可绕过点（事实 + 推导）**

- 三局真实轨迹中 `bypass_settings` **始终为 `{}`**（R0/R1/R2 的所有 `observation_after`），旁路机制从未触发。
- 由源码的隐藏表可直接推导：`PRODUCTION[zone][mode] = HEAT[zone][mode] / 10` 对六个组合全部成立（A 40/4、20/2；B 30/3、20/2；C 20/2、10/1）。也就是说**每单位交付水换来的产能是常数 0.1，和区、和档位无关**。旁路每投入 1 单位只交付 0.8 单位，因此在产能上被直供严格支配；在安全上，任何需要 >2.5 单位直供的区都可以降到 REDUCED 而不再需要搬水（A/B 的 REDUCED 热量都是 2.0，C 是 1.0）。唯一可能用到旁路的场景是把某区推到接近上限后的紧急补救，而最优规划不会把自己推到那里。
- 结论（推导，不是猜测）：不用旁路的稳态产能上限是 `6×10=60` 点（直供 `[20,20,20]` + 负荷 `REDUCED/REDUCED/FULL`，三区净变化全为 0）。为了把 A 维持 FULL 而开 B→A 旁路是可行的：A 直供 24 + 旁路 20（交付 16，恰好到 A 的区阀 40）、B 直供 20 全部外送并 IDLE、C 直供 10 并 REDUCED，水源 54 ≤ 60；但产量是 `A4+B0+C1=5/tick`，低于不开旁路的 `6/tick`——旁路可行，但严格更差。若允许烧掉初始热余量，V4 的线性松弛上界是 72 点，但未证明可达。V8 的 Oracle `a_priority` 走了旁路，运行时重放只拿到 **54** 点（`production=54`，峰值 A=94）；V4 `evidence_or_rules.yaml::A_priority_schedule` 记的是 56，存在 2 点口径差异，本审计以可复算的 54 为准。
- 产能目标 15 在三条轨迹里分别于 tick 3（R0、R2 的 `production_points=15`）和 tick 4（R1 的 17）达成，之后 6–7 个 tick 只剩“别过热”一件事。

**机制是否在三条轨迹中实际触发（引用决策序号）**

- R0 决策 6 `wait`：`previous_tick_flow_ledger` 首次回显 `delivered_tenths={A:20,B:20,C:20}`、`bypass_loss_tenths=0`，说明无旁路时“直供=交付”——**流量守恒链实际触发**。
- R0 决策 11 `read_temperature B` → `100`（十分之一度，正好等于上限）——**热量-交付差实际触发**。
- R0 决策 22 `wait` → `THERMAL_OVERHEAT`，A 到 `120`——**越限链实际触发**。
- 旁路链（`open_bypass`）在三条真实轨迹中**一次都没有触发**。

**触发所需最小动作数**：热量链 2 个（`set_flow` + `wait` 即可看到 `delivered` 与 band 变化）；旁路链最少 2 个（`open_bypass` + `wait`），但没有任何成功条件要求它。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `temperature_bands`（COOL<=5.0 / WARM<=8.0 / HOT<=10.0 / OVERHEAT>10.0） | 是 | 每步 | 是（判断是否接近上限） |
| 精确温度 | 部分：每 tick 至多一区（`temperature_tenths`） | 读温当步 | 是（辅以 band 足够闭环） |
| `flow_rules`（源 60、支管 25、旁路档 5/上限 20/交付 4/5、区阀 40/40/30、上限 100） | 是 | 初始 Observation，每步重发 | **是：流量守恒与旁路算术完全公开可推理** |
| `previous_tick_flow_ledger`（直供、旁路、交付、损耗） | 是 | 每个 `wait` 之后 | 是（可逐 tick 校验自己的分配） |
| `production_points` / `production_target` | 是 | 每步 | 是（但只给总和，不给单区/单档明细） |
| 各区各档热量 `HEAT` | **否**（只在源码与 V4 `map_spec.yaml`） | 只能由 band 变化 + 读数反推 | 是（可在线估计；不能先验证明） |
| 各区各档产能 `PRODUCTION` | **否** | 只能由 `production_points` 增量反推 | 是（例如 R0 的 +5、+6 增量） |
| `judge_state`（`temperatures_tenths`、`settled_states_tenths`、`ledger` 全量） | 否 | — | 不应被使用 |
| Oracle 路径（`ORACLE_CASES`、`oracle_trace.jsonl`） | 否 | — | 不参与运行时 |

结论：**流量守恒与旁路分配是公开可推理的**（`flow_rules` + `previous_tick_flow_ledger` 足够复算每一单位水）；真正未公开的是**热/产能系数**。因此 MAP-20 的失败不能归因为“流量规则不透明”，只能归因为热模型学习与负荷管理。

## 4. 可解性与可观察性

- Oracle：1 个用例（`a_priority`），16 个动作，`oracle_ok=1/1`（`runs/v9/baselines/MAP-20.json`）；同图另有 3 个手算 fixture 全部 OK（`scripts/check_v8_map.py MAP-20`）。
- **仅凭公开信息**的可执行策略：存在，`Map20Heuristic` 只用 `temperature_bands`、`current_load_modes` 与 `flow_rules`，13 个动作成功，`max_node_exceedance=0`、`safe_node_ticks=30`（§11）。
- 但要注意强度差别：策略的**安全性可以被在线验证**（每 tick 的 band 与 `delivered` 都在），却**不能被先验证明**——因为热量系数未公开。R0 恰好是“没有把 A 的 +20/tick 斜率建进模型”的失败，属于 B 类信息不足与 E 类规划错误的叠加，不是 `INTERFACE_BLOCKED`（存在 13 动作的公开策略）。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| 决策预算 | 38 |
| Oracle 动作数 | 16 |
| 公开启发式动作数 | 13（1 读温 + 1 直供 + 1 负荷 + 10 `wait`） |
| 消融动作数 | 4（读温 + 直供 + 2 `wait`，tick 2 熔断） |
| 走完 10 tick 的硬下限 | 10 个 `wait` |

`legal_random` 20 seed：成功 **0/20**，20 局全部 `THERMAL_OVERHEAT`；非法动作 23、被拒动作 34；决策数 3–16（随机策略在 3–16 个决策内就触发过热，几乎走不到 horizon）。

**判定：不是预算不够，是模型没做对。** 38 个决策里 10 个必须用于 `wait`，余量 28；R0 只用了 22 个决策，失败原因是热管理，不是 horizon。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾规则 | 三局取值 |
|---|---|---|---|---|---|
| `map20.max_node_exceedance` | primary | 所有已结算状态里 `max(0, T-100)` 的最大值（十分之一度） | 关键节点数 | 预算/provider 截尾 → CENSORED | R0=20、R1=0、R2=0 |
| `map20.safe_node_ticks` | primary | Σ 每 tick 每区 `T<=100` 的计数 | 节点数×有效 tick | 同上 | R0=29、R1=30、R2=30 |
| `map20.flow_conservation_violations` | guardrail | `sum(violations.values())`，**包含** `SOURCE_BUDGET_EXCEEDED`/`FEEDER_CAPACITY_EXCEEDED`/`INVALID_BYPASS_TRANSFER`/`ZONE_VALVE_CAPACITY` | episode | 同上 | R0=0、R1=0、R2=1 |
| `map20.key_node_runaway` | diagnostic | 任一区曾 `>100` 的 0/1 | episode | 同上 | R0=1、R1=0、R2=0 |

- **计算事件与分母**：`max_node_exceedance` 的 20 是**十分之一度**（A 到 120，即超上限 2.0 °C），不是 20 °C；`safe_node_ticks` 满值是 3 区 × 10 tick = 30，已饱和。
- **未通关仍有意义的主指标**：有，`safe_node_ticks`（R0=29 vs 30）与 `max_node_exceedance`（20 vs 0），但前者只差 1，后者才是主判别量。
- **N/A / censored**：三局都没有 N/A 或 censored（4/4 `valid`），也没有预算截尾局。
- **判别力**：能区分。`max_node_exceedance` 0（启发式/Oracle）vs 10（消融）vs 20（R0）；`safe_node_ticks` 30 vs 5（消融）vs 29（R0）。
- **指标缺陷（事实）**：`flow_conservation_violations` 的名字与分子不一致——R2 的唯一一次违例来自决策 6 的 `SOURCE_BUDGET_EXCEEDED`（请求 75 > 60），它并不是“守恒违例”，而是“控制帧非法”。按 registry 的公式 `count(FLOW_CONSERVATION_VIOLATION)` 应只数守恒类拒绝。
- **缺失维度（事实）**：V4 `map_spec.yaml` 的 primary 是 `overheat_count / total_production_points / source_water_used_units / bypass_loss_units`，V8 只保留了热安全两项；`production_points` 与旁路损耗都**没有登记为指标**，因此“水分配得好不好”在本图不可测——这也是旁路机制被绕过却无人察觉的原因。

## 7. 三次轨迹归因

### R0（`V8-MAP-20-R0-20261017T093752Z-3824d0d4`，`failure`/`THERMAL_OVERHEAT`，22 决策）

- 决策 1：`{"station":"A","tool":"read_temperature"}` → `TEMPERATURE_READ:A`，观察变化 `{"last_temperature_reading":{"temperature_tenths":70,"tick":0,"zone":"A"}}`。
- 决策 6：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"previous_tick_flow_ledger":{"bypass":{},"bypass_loss_tenths":0,"delivered_tenths":{"A":20,"B":20,"C":20},"direct_tenths":{"A":20,"B":20,"C":20},"tick":0},"production_points":5,"temperature_bands":{"A":"COOL","B":"WARM","C":"COOL"},"tick":1,"ticks_remaining":9}`。
- 决策 9：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化（节选，省略 `previous_tick_flow_ledger`）`{"production_points":15,"temperature_bands":{"A":"COOL","B":"HOT","C":"COOL"},"tick":3,"ticks_remaining":7}`（产能目标已达成）。
- 决策 11：`{"station":"B","tool":"read_temperature"}` → `TEMPERATURE_READ:B`，观察变化 `{"last_temperature_reading":{"temperature_tenths":100,"tick":4,"zone":"B"}}`。
- 决策 15：`{"adjust_loads":["FULL","IDLE","FULL"],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{"current_load_modes":{"A":"FULL","B":"IDLE","C":"FULL"}}`。
- 决策 21：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化（节选，省略 `previous_tick_flow_ledger`）`{"production_points":50,"temperature_bands":{"A":"HOT","B":"COOL","C":"COOL"},"tick":9,"ticks_remaining":1}`。
- 决策 22：`{"tool":"wait"}` → `THERMAL_OVERHEAT`，观察变化（节选，省略 `previous_tick_flow_ledger`）`{"temperature_bands":{"A":"OVERHEAT","B":"COOL","C":"COOL"},"terminal":true,"terminal_reason":"THERMAL_OVERHEAT","tick":10}`。

**首次偏离合理策略的可观测事件**：决策 15 把 A 从 0 恢复到 `FULL`，而 A 的直供仍只有 20。此时 B 刚被读到 100（已达上限），模型把注意力放在 B 上，却没有跟踪 A 的斜率。
**失败链**：A 在 IDLE 下被抽到 0（tick 1–4）→ 决策 15 恢复 FULL，热量 40 减交付 20 = 每 tick +20 → tick 4–9 从 0 线性升到 100 → 决策 21 已看到 `A: HOT`、产能 50 早已超过 15，仍再 `wait` 一次 → tick 10 到 120 熔断。
**替代解释**：这不是“数值运气”或“规则不透明”：A 的 band 在决策 19（tick 7）已是 `WARM`、决策 21（tick 9）已是 `HOT`；`delivered_tenths` 每 tick 都回显 20；产能也已满足。更合理的解释是 G 类（没有维护 A 的热斜率记忆）叠加 B 类（热量系数未公开，必须在线估计）。

### R1（`V8-MAP-20-R1-20261017T093931Z-00dbed48`，`success`/`PRODUCTION_TARGET_MET`，19 决策）

- 决策 1：`{"station":"A","tool":"read_temperature"}` → `TEMPERATURE_READ:A`，观察变化 `{"last_temperature_reading":{"temperature_tenths":70,"tick":0,"zone":"A"}}`。
- 决策 2：`{"adjust_loads":["REDUCED","FULL","FULL"],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{"current_load_modes":{"A":"REDUCED","B":"FULL","C":"FULL"}}`。
- 决策 3：`{"adjust_loads":["IDLE","FULL","FULL"],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{"current_load_modes":{"A":"IDLE","B":"FULL","C":"FULL"}}`。
- 决策 10：`{"adjust_loads":["IDLE","REDUCED","FULL"],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{"current_load_modes":{"A":"IDLE","B":"REDUCED","C":"FULL"}}`。
- 决策 19：`{"tool":"wait"}` → `PRODUCTION_TARGET_MET`，观察变化（节选，省略 `previous_tick_flow_ledger`）`{"production_points":41,"terminal":true,"terminal_reason":"PRODUCTION_TARGET_MET","tick":10}`。

**成功是否只是数值运气**：不是。终局三区温度（离线回放，十分之一度）为 `A=0, B=70, C=50`：A 在 IDLE 下被抽到 0 并保持，`B` 的 REDUCED 热量 20 与交付 20 抵消，`C` 的 FULL 热量 20 与交付 20 抵消。这是一个**净变化恒为 0 的静态不动点**，不依赖任何 tick 的巧合；剩余 9 个 `wait` 只是重复同一状态。

### R2（`V8-MAP-20-R2-20261017T094050Z-669e7442`，`success`/`PRODUCTION_TARGET_MET`，17 决策）

- 决策 2：`{"adjust_loads":["REDUCED","REDUCED","REDUCED"],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{"current_load_modes":{"A":"REDUCED","B":"REDUCED","C":"REDUCED"}}`。
- 决策 4：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"previous_tick_flow_ledger":{"bypass":{},"bypass_loss_tenths":0,"delivered_tenths":{"A":20,"B":20,"C":20},"direct_tenths":{"A":20,"B":20,"C":20},"tick":0},"production_points":5,"tick":1,"ticks_remaining":9}`。
- 决策 6：`{"set_flow_tenths":[25,25,25],"tool":"set_flow"}` → `SOURCE_BUDGET_EXCEEDED`，观察变化 `{}`。
- 决策 7：`{"set_flow_tenths":[20,20,20],"tool":"set_flow"}` → `FLOW_SET`，观察变化 `{}`。
- 决策 17：`{"tool":"wait"}` → `PRODUCTION_TARGET_MET`，观察变化（节选，省略 `previous_tick_flow_ledger`）`{"production_points":50,"terminal":true,"terminal_reason":"PRODUCTION_TARGET_MET","tick":10}`。

**成功原因**：同样是一个静态不动点（A 70、B 60、C 从 50 降到 0），三区净变化分别为 0、0、−10。决策 6 的 `SOURCE_BUDGET_EXCEEDED` 说明模型确实尝试过提高水量，但被公开的 60 上限挡回；它没有因此改用旁路，而是退回 `[20,20,20]` 并靠 REDUCED 稳住——这既证明流量约束是公开可用的，也证明旁路并非必需。

**重复证据有限**：三局只有一处实质差异（R0 让 A 长时间跑 FULL）；R1 与 R2 都是“找到一个静态安全点后重复 `wait`”。n=3 不能区分“模型偶尔能收敛”与“静态解足够显眼”。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | E 策略规划错误（把 A 恢复 FULL 却没有给 A 增量水，未建模 +20/tick 斜率） | B 公开信息不足（`HEAT` 表未公开，只能在线估计）；G 记忆/推理（前 4 tick 的 A 降温和 B=100 读数没有被组合成模型） | 高 | 决策 15/21/22；复算 A 序列 `0→20→40→60→80→100→120` |
| R1 | 无失败（静态安全点：A=0/B=70/C=50） | — | 高 | 决策 10/19；复算终局温度 |
| R2 | 无失败（静态安全点：A=70/B=60/C=0） | — | 高 | 决策 2/4/17；复算终局温度 |

## 9. 标签

- `MEASUREMENT_VALID`：热安全主指标可复算且有判别力（0 / 10 / 20；30 / 5 / 29），2/3 成功与 1/3 失败都是真实热管理差异。
- `CONSTRUCT_BYPASS`：声称的“有损旁路分配”在三条轨迹中一次未用；由隐藏表可证 `产能 = 交付水量 / 10` 与区/档无关，旁路必损 20% 因而在稳态规划中被直供严格支配；静态 `[20,20,20] + REDUCED` 13 动作即成功。核心机制在稳态下既非必需也非理性可选（旁路只在“已经把某区推到上限”后的补救中才可能有用，而最优规划不会进入该状态）。
- `METRIC_DEFECT`：① `flow_conservation_violations` 把 `SOURCE_BUDGET_EXCEEDED` 等控制帧非法计入“守恒违例”；② V4 的产能/用水/旁路损耗维度未登记，导致“分配质量”不可测；③ `safe_node_ticks` 上限 30，R0 仍得 29，几乎不区分。

## 10. 最小可证伪修复（无证据不修改）

**候选 A（推荐，指标，不改规则）**：登记 `map20.total_production_points`、`map20.source_water_used`、`map20.bypass_loss` 三个 V4 原 primary 指标；把 `flow_conservation_violations` 的分子收窄为真正的守恒违例（或在名字/公式上改成“控制帧非法次数”）。
- 证据与根因：V4 `metrics.primary` 与 V8 registry 不一致；R2 的 1 次“违例”实际是源预算超限。
- 预期变化：旁路使用与水的浪费第一次可见；Oracle(54 点、含旁路) 与启发式(50 点、无旁路) 会在产能上被区分（注意两者都不及不用旁路的稳态上限 60）。
- 反例与回归：新增指标不得改变成功判定；旧 90 局数值进 `runs/v9/rescore/` 只读重算。

**候选 B（公开信息，不改规则）**：把 `HEAT`/`PRODUCTION` 六组合表（或至少“同区同档热量=10×产能”这条比例关系）写进 `flow_rules`。
- 证据与根因：R0 的失败完全建立在“不知道 A 的 FULL 热量是 20 的两倍”上；而 V4 设计文档里这张表本来是公开规则的一部分。
- 预期变化：热规划从“试错”变成“算术”，R0 式漂移可在决策 15 前被算出来。
- 反例与回归：会显著降低难度，并让旁路的“被支配”更明显——所以必须与候选 C 同时做，否则只是把绕过写得更清楚。

**候选 C（场景参数，需 spec，不改运行规则语义）**：要让旁路成为理性选择，必须同时满足两点——某区高档位的 `产能/热量` 比严格高于低档位，且该档位的热量超过 25 的直供上限。当前六个组合的比例全是 0.1，所以任何搬水都在稀释产能。一个可行方向是把 A 的 FULL 产能从 4 提到 6（比例 0.15），并把产能目标提高到 60 以上，使“全 REDUCED + C FULL”的 60 点解不够；具体参数必须先用离线审计证明存在安全达标路线，本审计不预设数值。
- 证据与根因：`PRODUCTION/HEAT ≡ 0.1` 是旁路被支配的充分条件；目标 15 只需 tick 3 就达成，产能约束不绑定；上文的“A FULL + B→A 旁路”实例产量 5/tick，低于纯直供的 6/tick，可直接复算。
- 预期变化：`lossy_water_resource_allocation` 才真正需要“在有损搬运与直供之间取舍”。
- 反例与回归：改参数会改变 `scenario_hash`，V8 三局不可直接对比；必须先证明新目标下 Oracle 仍可解（运行时 `a_priority` 只有 54 点，若目标 >54 需新 Oracle）。**单纯提高产能目标或缩短 horizon 不会让旁路变必需**，因为旁路只会降低可达上限。

**若都不做**：保持只读，但 MAP-20 只能宣称“测量了多区热安全”，不能宣称“测量了有损水分配”。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-20.json`：

| 策略 | 成功 | 决策 | 终止码 | max_exceedance | safe_ticks | violations |
|---|---|---|---|---|---|---|
| Oracle `a_priority` | 是 | 16 | `PRODUCTION_TARGET_MET` | 0 | 30 | 0 |
| `legal_random`（20 seed） | 0/20 | 3–16 | 20×`THERMAL_OVERHEAT` | — | — | — |
| `public_heuristic` | 是 | **13** | `PRODUCTION_TARGET_MET` | **0** | **30** | 0 |
| 消融 `no_load_management` | 否 | 4 | `THERMAL_OVERHEAT` | **10** | **5** | 0 |

注：Oracle 行的 max_exceedance/safe_ticks/violations 来自同图 fixture `a_priority_safe_network` 的期望值（0 / 30 / 0），`runs/v9/baselines/MAP-20.json` 只记录 Oracle 的动作数与成功与否；启发式/消融两行是本轮 `run_policy` 直接产出的 judge 指标。

**独立复算（按 `settled_states_tenths` 另写公式，不复用 `map20.metrics()`）**：

| 局 | 我的 exceedance | judge | 我的 safe_ticks | judge | 我的 violations | judge |
|---|---|---|---|---|---|---|
| R0 | 20 | 20 | 29 | 29 | 0 | 0 |
| R1 | 0 | 0 | 30 | 30 | 0 | 0 |
| R2 | 0 | 0 | 30 | 30 | 1 | 1 |
| 启发式 | 0 | 0 | 30 | 30 | 0 | 0 |
| 消融 | 10 | 10 | 5 | 5 | 0 | 0 |

手算旁证：R0 的 A 序列为 `50,30,10,0,20,40,60,80,100,120`，`max(0,120-100)=20`；B 在 tick 4 恰好 100（不计越限），所以 `safe_node_ticks = 30 - 1 = 29`。消融的 `[90,110]` 给出 `110-100=10`，安全计数 `3+2=5`。均与 judge 一致。

`violations` 的独立口径是逐决策统计四类控制帧拒绝码（`SOURCE_BUDGET_EXCEEDED`/`FEEDER_CAPACITY_EXCEEDED`/`ZONE_VALVE_CAPACITY`/`INVALID_BYPASS_TRANSFER`）：R0/R1 为 0，R2 只在决策 6 命中 1 次 `SOURCE_BUDGET_EXCEEDED`，与 judge 一致。

**判别力**：主指标至少区分三种策略（启发式 0 / 消融 10 / R0 20）；`safe_node_ticks` 区分启发式 30 与消融 5，但对 R0 只差 1，单独使用会 `LOW_DISCRIMINATION`。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P1**。

理由：热安全部分是可测的（2/3 成功不是运气，而是两个静态不动点），但本图声称的“有损旁路水分配”在数学上被直供支配、在三条真实轨迹中从未触发，且对应的产能/损耗指标没有登记；不修，这张中等图实际只测“多区热上限”。
