# MAP-10 逐图审计：最后一桶燃料

> 本文件由 V9 Batch 1 依据 Trace、证据包与源码重新推导；不复制 `docs/v8` 结论，不声称人工审核。状态待用户确认。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-10 最后一桶燃料 / polar / 简单 |
| condition | `default` |
| `rule_hash` | `d4bddf5702e6ae32487dbc92692cd9cb303b5a2b2ab9ff98274348e71215f74d` |
| `scenario_hash` | `c181e297e1007c5b20c6c21e2e424080fac3f5a0270ffecde366f0cef83f18a0` |
| 决策预算 | 30 |
| V8 三局 | 0/3 成功；`GENERATOR_FUEL_SHORTAGE` ×3；决策 2 / 5 / 2 |

数据来源：`runs/v9/evidence/MAP-10.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-10.json`、`docs/v8/maps/MAP-10-final.md`、`worlds/v4/MAP-10/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map10.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v9/policies/world_polar.py`。

## 1. 能力构念

**一句话**：在“同一燃料池被拆成油库与随身两仓、两仓不可互挪、时间会持续烧掉油库”的条件下，判断出发前必须把哪一部分燃料搬到身上，才能既启动远端发电机又不让基地冻结。

- 成功行为：`generator_online=true` 且 `transmission_complete=true`，全程 `base_temperature>0`。
- 明确反例：空手走到 E 直接 `activate_generator`（R0/R2），或反复往返而从不装载（R1）。二者都在启动检查处终止。
- 递进位置：本图是 polar 三图中唯一的**单期、无随机、短 horizon**资源分仓题；MAP-11 引入噪声与生命窗，MAP-12 引入 30 天跨期排程。本图只考“出发前的一次性资源前置”，不考风险或长期规划。

## 2. 机制与因果链

起始状态（tick 0）：`location=B`、`fuel_depot=12`、`carried_fuel=0`、`carry_capacity=5`、`base_temperature=5`、`heater_on=true`、`generator_online=false`、`visible_edges=[B_E,B_W]`。
必需观察：`carried_fuel=0` 与 `fuel_depot=12` 的分仓；`goal` 指定“于 E 启动发电机并在 T 完成发报”。
关键决策：在 B 执行 `load_fuel`（把油库燃料转为随身燃料），而不是直接出发。
立即后果：油库减少、随身增加；每 2 tick 油库再扣 1 维持供暖；`activate_generator` 从**随身**仓扣 3。
终局：`E_T` 走到 T，`transmit` 成功。

- 可绕过核心机制的动作：没有。发电机与发报是硬性目标。但 `E_W_SNOWMOBILE` 捷径是**被支配选项**：本图没有时间上限或生命窗，步行路线消耗 8 单位、捷径消耗 9 单位，捷径只省 2 tick 却多耗 1 单位燃料；所谓“路线/时间取舍”在本图不构成真实取舍（见 §5 的复算）。
- 机制触发：三局全部触发“随身燃料不足”分支。R0 决策 2、R2 决策 2、R1 决策 5 均为 `GENERATOR_FUEL_CHECK_FAILED`。
- 触发所需最小动作数：失败 2 步（`walk B_E` + `activate_generator`）；成功 5 步（`load_fuel` + `walk B_E` + `activate_generator` + `walk E_T` + `transmit`）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `tick` / `visible_edges` | 是（Observation） | tick 0 起 | 足以选路：B 处只见 `B_E/B_W`，到 E 后出现 `E_T/E_W_SNOWMOBILE` |
| `fuel_depot` / `carried_fuel` / `carry_capacity` | 是（Observation） | tick 0 起 | 足以看到“身上 0、油库 12、容量 5” |
| `base_temperature` / `heater_on` / `generator_online` / `transmission_complete` | 是（Observation） | tick 0 起 | 足以判断终局状态 |
| `goal`（E 启动、T 发报、基地不冻结） | 是（Observation + system prompt） | tick 0 起 | 足以确定目标顺序 |
| 动作名与字段形状 | 是（prompt 动作契约 + 词表） | 每步 | 足以提交合法形状，不含代价 |
| `load_fuel` 只能在 B | **否** | 只有被拒后由 `INVALID_LOCATION` 反馈 | 不能事前推导；R1 决策 2 即撞上 |
| 发电机消耗 **3 随身燃料**、油库不供发电机 | **否** | 只有失败时由 `GENERATOR_FUEL_CHECK_FAILED` 反馈，且随即终局 | 不能事前推导 |
| 雪地车每程 **2 随身燃料** | **否** | 只有失败时由 `SNOWMOBILE_FUEL_CHECK_FAILED` 反馈 | 不能事前推导 |
| 供暖每 2 tick 从油库扣 1（首次 tick 2） | **否** | 只能从 `fuel_depot` 的偶数 tick 下降反推 | 不能事前推导 |
| “燃料检查失败即终局”（不可重试） | **否** | 失败即终局，无第二次观察 | 不能事前推导 |
| `judge_state`（`fuel_spent`、`generator_fuel_spent`、`minimum_base_temperature` 等） | 否 | — | 否 |
| Oracle 路径/用例 | 否 | — | 否 |

证据：`src/agent_arena/v8/prompts.py` 的 `_VOCABULARY["MAP-10"]`（第 183–187 行）只列动作名与 `load_fuel` 的 1..5，不含任何代价、来源或位置限制；`system_prompt()`（第 356–381 行）只拼接 `goal`、动作契约与词表；`map10.py::_public()`（第 98–111 行）只发状态。设计侧常量只存在于 `worlds/v4/MAP-10/map_spec.yaml`（第 31、39 行：`heater_consumes_from: fuel_depot_B`、`generator_fuel_source: carried_fuel`）与 `map10.py` 类常量，**均为设计材料，不是运行时公开面**。

## 4. 可解性与可观察性

- Oracle：2 个用例，`walk_keep_fuel` 5 动作、`snowmobile_shortcut` 6 动作；`replay_all` 重放均 `scenario_success / TRANSMISSION_COMPLETE`。
- **仅凭公开信息是否存在可执行策略**：存在。思路只用公开字段：B 处 `carried_fuel=0` 且 `carry_capacity=5` → 装满（`quantity=min(5,12)=5`）→ `walk B_E` → `activate_generator` → `walk E_T` → `transmit`。实测 5 决策成功，`fuel_consumed=8`、`key_task_fuel_efficiency=0.25`、最低温 5。该策略不需要知道“门槛是 3”，因为容量 5 ≥ 3。
- 但“必须先装载”本身**不可由公开文本推导**：模型只能靠“带燃料出门”的通用先验，或靠一次失败（而失败是终局）。因此本图属于“**可解但不可推导**”，不是“必死”。按模板口径，只就“未公开的致死门槛”这一子机制标 `INTERFACE_BLOCKED`，不把整图判为不可解。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `walk_keep_fuel` | 5 | `TRANSMISSION_COMPLETE` | consumed 8；efficiency 0.25 |
| Oracle `snowmobile_shortcut` | 6 | `TRANSMISSION_COMPLETE` | consumed 9；efficiency 0.222… |
| 公开启发式 | 5 | `TRANSMISSION_COMPLETE` | consumed 8；efficiency 0.25；min guarantee 2 |
| 消融 `no_key_mechanism`（不装载） | 2 | `GENERATOR_FUEL_SHORTAGE` | consumed 2；efficiency 0.0 |
| V8 MiMo R0/R2 | 2 | `GENERATOR_FUEL_SHORTAGE` | consumed 2；efficiency 0.0 |
| V8 MiMo R1 | 5 | `GENERATOR_FUEL_SHORTAGE` | consumed 7；efficiency 0.0 |

`legal_random` 20 seed：0 成功；终局分布 `BASE_FROZEN` 17、`decision_budget_reached` 2、`GENERATOR_FUEL_SHORTAGE` 1；平均决策 24.1；schema 非法 0。随机策略大量触发 `BASE_FROZEN`，说明“空耗油库直到冻结”是另一条真实失败路径，但需要 12 次供暖结算（约 tick 24），与 MiMo 的 2 决策早失败完全不同。

**判定：不是预算不够。** 成功只需 5 步，预算 30；MiMo 在 2 步内就停在隐藏门槛上。

燃料总量复算（用真实环境逐步结算，审计侧读取 judge 只为核对，不进入策略）：

| 路线 | 供暖次数 | 发电机 | 雪地车 | 总消耗 | 余量 | 完成 tick | 最低温 |
|---|---|---|---|---|---|---|---|
| 步行 `load 3` | 5 | 3 | 0 | 8 | 4（油库） | 10 | 5 |
| 步行 `load 5` | 5 | 3 | 0 | 8 | 4（油库 2 + 随身 2） | 10 | 5 |
| 捷径 `load 5` | 4 | 3 | 2 | 9 | 3 | 8 | 5 |

**结论：初始 12 单位绰绰有余。** 完成“启动发电机 + 发报 + 基地不冻结”的最低消耗是 **8**，余量 **4**（为最低消耗的 50%）。因此问题不在资源总量，而在“资源在错误的位置、且失败不可恢复”。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map10.base_frozen` | `terminal_reason==BASE_FROZEN` | episode | 0/0/0 | 无 N/A |
| `map10.fuel_consumed` | 12 −（油库 + 随身） | episode | 2/7/2 | 无 N/A |
| `map10.key_task_fuel_efficiency` | 已完成必需任务 / 燃料消耗 | 燃料消耗 | 0.0/0.0/0.0 | 分母 2/7/2 均 >0，无 N/A |
| `map10.minimum_base_temperature` | 逐 tick 最低温 | episode | 5/5/5 | 无 N/A |
| `map10.minimum_task_guarantee` | 发电机 + 发报完成数 | 固定 2 | 0/0/0 | 无 N/A |

- 未通关仍有意义的连续主指标：`fuel_consumed`（2 与 7 区分了“走一步就死”与“往返后才死”）与 `key_task_fuel_efficiency`（0.0 vs Oracle 0.25）。
- 三局无 `not_applicable`/`censored`；`valid=5/5`。
- 区分能力：Oracle（0.25 / guarantee 2）vs MiMo（0.0 / 0）可区分；消融与 MiMo 指标**完全相同**（consumed 2、efficiency 0.0、temp 5、guarantee 0），说明该消融精确复现了真实失败。
- `base_frozen` 与 `minimum_base_temperature` 在 3 条真实轨迹、2 个 Oracle、启发式与消融中恒为 0/5 → 对这组对照 **LOW_DISCRIMINATION**；随机基线另有 17/20 局 `BASE_FROZEN`，说明该护栏不是全局常量，只是对“会成功或早失败”的策略都不敏感。

## 7. 三次轨迹归因

### R0（`V8-MAP-10-R0-20261017T081851Z-1441712c`，2 决策，`GENERATOR_FUEL_SHORTAGE`）

- 决策 1 `{"edge_id":"B_E","tool":"walk"}` → `WALKING:E`；观察变化 `{"fuel_depot":10,"location":"E","tick":4,"visible_edges":["B_E","E_T","E_W_SNOWMOBILE"]}`。
- 决策 2 `{"tool":"activate_generator"}` → `GENERATOR_FUEL_CHECK_FAILED`；观察变化 `{"terminal":true,"terminal_reason":"GENERATOR_FUEL_SHORTAGE","tick":5}`。
- 首次偏离：决策 1 出发时 `carried_fuel` 仍为 0（公开可见），模型没有把“身上没有燃料”当作出发前置。
- 失败链：未装载 → 到 E 后随身 0 < 3 → 检查失败 → 同 tick 终局。
- 替代解释：接口误导（B/C，阈值与来源未公开且失败不可恢复）与策略错误（E，未做资源前置检查）都成立；**不是**预算（2/30）或环境随机（本图无随机）。

### R1（`V8-MAP-10-R1-20261017T081925Z-e76dcf0a`，5 决策，`GENERATOR_FUEL_SHORTAGE`）

- 决策 1 `{"edge_id":"B_E","tool":"walk"}` → `WALKING:E`；观察变化 `{"fuel_depot":10,"location":"E","tick":4,"visible_edges":["B_E","E_T","E_W_SNOWMOBILE"]}`。
- 决策 2 `{"quantity":5,"tool":"load_fuel"}` → `INVALID_LOCATION`；观察变化 `{"tick":5}`（燃料账本未变，说明该拒绝是“软失败”）。
- 决策 3 `{"edge_id":"B_E","tool":"walk"}` → `WALKING:B`；观察变化 `{"fuel_depot":8,"location":"B","tick":9,"visible_edges":["B_E","B_W"]}`。
- 决策 5 `{"tool":"activate_generator"}` → `GENERATOR_FUEL_CHECK_FAILED`；观察变化 `{"fuel_depot":5,"terminal":true,"terminal_reason":"GENERATOR_FUEL_SHORTAGE","tick":14}`。
- 首次偏离：决策 2 在 E 尝试装载。模型其实“想到了要装燃料”，但不知道 `load_fuel` 只在 B；得到 `INVALID_LOCATION` 后回到 B，却**没有重新装载**就再次出发。
- 失败链：错地点装载 → 软拒绝 → 往返两趟（油库 8→5）→ 仍空手到 E → 终局。
- 替代解释：这条轨迹最能反驳“纯粹不知道要带燃料”——模型有装载意图；真正缺的是“位置规则 + 拒绝语义”。同时它证明“位置错误可恢复、燃料检查错误不可恢复”的不对称没有公开。

### R2（`V8-MAP-10-R2-20261017T081940Z-134cae46`，2 决策）

- 与 R0 逐步相同：决策 1 `{"edge_id":"B_E","tool":"walk"}` → `WALKING:E`，观察变化 `{"fuel_depot":10,"location":"E","tick":4,"visible_edges":["B_E","E_T","E_W_SNOWMOBILE"]}`；决策 2 `{"tool":"activate_generator"}` → `GENERATOR_FUEL_CHECK_FAILED`，观察变化 `{"terminal":true,"terminal_reason":"GENERATOR_FUEL_SHORTAGE","tick":5}`。

**重复证据有限**：R0 与 R2 是同一失败序列，R1 只多了一次错地点装载；n=3 无法区分“个体差异”与“固定陷阱”。从证据看更像固定陷阱：三局都在同一隐藏前置条件处终止。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | B 公开信息不足（发电机燃料来源与 3 单位门槛未公开，失败即终局） | E 策略（未做资源前置）；C 接口（终止码不区分燃料仓） | B 高 / E 中 / C 高（事实） | 决策 1–2；`map10.py:190–201`；prompt 词表 |
| R1 | B（`load_fuel` 位置限制未公开） | E（回到 B 后未重新装载）；C（`INVALID_LOCATION` 与致死检查语义不对称） | B 高 / E 高 | 决策 2、3、5 |
| R2 | 同 R0 | 同 R0 | 同 R0 | 决策 1–2 |

排除：A（规则本身自洽、无随机、Oracle 通过）、D（预算 30，成功 5 步）、H（0 非法动作、0 provider 错误）、I（证据完整）。

## 9. 标签

- `MEASUREMENT_VALID`：存在 5 步公开启发式成功；消融精确复现 MiMo 的 2 决策失败；主指标可区分成功/失败。
- `INTERFACE_BLOCKED`（限定于“未公开的致死燃料门槛/来源”）：`map_spec.yaml` 与 `map10.py` 中的三条硬规则在运行时 prompt 与 Observation 中均不存在。

不选 `RULE_DEFECT`（规则自洽）、不选 `BUDGET_BLOCKED`、不选 `METRIC_DEFECT`（指标可算且可区分，只是两项护栏常量无区分度）。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：规则不改；公开面缺 4 条硬信息，终止码 `GENERATOR_FUEL_SHORTAGE` 不指明“随身仓”。
- 证据与根因：R0/R2 决策 2、R1 决策 5；prompt 词表无代价表；`map10.py:195–197` 只检查 `carried_fuel`。
- 候选 A（优先，补公开信息，不改规则）：在 `_VOCABULARY["MAP-10"]` 增加一行公开规则：“供暖每 2 tick 从油库扣 1；`load_fuel` 只在 B；发电机启动消耗 3 随身燃料；雪地车每程消耗 2 随身燃料；燃料检查失败即终局。”预期：模型可从事前规划而非先验；失败将更能归因于资源规划能力。反例/回归：R1 表明“知道要装”仍可能不装，信息补充未必带来天花板；若成功率从 0/3 跳到 3/3，则本图在简单层失去区分度，需要 Batch 6 决定是否保留。
- 候选 B（只改命名，不改规则与数值）：`GENERATOR_FUEL_SHORTAGE` → `GENERATOR_CARRIED_FUEL_SHORTAGE`，`SNOWMOBILE_FUEL_CHECK_FAILED` 同理；代价是 `rule_hash` 与所有旧 Trace 的终止码失效，必须新建 DCR 并重跑。建议只在 A 通过后再做。
- 不建议：增加燃料、延长 horizon、把失败改成软拒绝（会改变机制与构念）。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-10.json`：

| 类别 | 结果 |
|---|---|
| Oracle | 2/2 成功（5 / 6 动作） |
| `legal_random`（20 seed） | 0 成功；`BASE_FROZEN` 17、`decision_budget_reached` 2、`GENERATOR_FUEL_SHORTAGE` 1；平均 24.1 决策；schema 非法 0 |
| `public_heuristic` | 成功，5 决策，5 指标全 valid |
| 消融 `no_key_mechanism` | 失败，2 决策，`GENERATOR_FUEL_SHORTAGE`，指标与 MiMo R0/R2 完全一致 |

独立复算（不使用 `Map10Environment.metrics()`，只读 `actions[].observation_after` 的公开字段）：
`fuel_consumed = 12 − (fuel_depot + carried_fuel) = 12 − (2 + 2) = 8`；`completed_tasks = generator_online + transmission_complete = 2`；`efficiency = 2/8 = 0.25`；`min_temperature = 5`；`base_frozen = 0`。与 extractor 输出逐项一致。对三局 MiMo 用同一公式复算：R0 `12 − (10 + 0) = 2`、R1 `12 − (5 + 0) = 7`、R2 `12 − (10 + 0) = 2`，与 `judge_metrics` 的 2/7/2 一致。

**基线可复现性**：`ShapeSampler.from_environment` 当前对 tool 与动作形状都显式排序（`src/agent_arena/v9/baselines.py:136–144`），两个独立进程复算得到**相同**的 362 个被拒动作，`legal_random` 可重放。本审计过程中曾观察到未排序版本在两次进程间给出 362 与 353；该问题在当前实现中已消除，本文以当前值（362）为准，不再登记修复候选。

## 12. V9 状态

`NEEDS_REDESIGN`（P1）。理由：地图可解、指标可区分，但“发电机只吃随身燃料 + 3 单位门槛 + 失败即终局”完全未公开，导致 0/3 无法区分“资源规划失败”与“没被告知规则”；最小修复是补公开信息（候选 A），不需要改规则。
