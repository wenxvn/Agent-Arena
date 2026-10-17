# MAP-27 逐图审计：月面联合行动

> 本文件由 V9 Batch 1 依据 Trace、证据包、源码与本次离线复算重新推导；不复制 `docs/v8` 结论，不声称人工审核。V8 文件保持只读。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-27 月面联合行动 / lunar / 困难 |
| condition | `default` |
| `rule_hash` | `b993858b9d0b62305ac1950e6f3a1e5cd1a8f3c479606e1aa1f8a2850e255cf7` |
| `scenario_hash` | `e7ef2cee45fafd8627d10609ca78d157d075634645e28e370dbb3c97506d23d1` |
| 决策预算 | 46 |
| V8 三局 | 0/3 成功；`VEHICLE_STRANDED` ×3；决策 8 / 10 / 6 |
| 主指标 | `joint_task_completion_rate` = 0.0 / 0.0 / 0.0（0/3 协同任务）；`critical_path_delay` = N/A / N/A / N/A；`communication_blackout_ticks` = 13 / 12 / 14；`resource_conflicts` = 0 / 0 / 0 |

数据来源：`runs/v9/evidence/MAP-27.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-27.json`、`docs/v8/maps/MAP-27-final.md`、`worlds/v4/MAP-27/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map27.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v9/policies/world_lunar.py`。

## 1. 能力构念

**一句话**：在“两格货舱互斥、14 电与 18 氧按道路原子扣减、唯一电芯只能充一次”的条件下，能否排出“先稳定伤员 → 再修中继 → 远程撤离 → 封存样本 → 回基地”的全目标路线，并在每一段移动后仍留有回程电量。

- 成功行为：在 B `submit` 时同时满足 `sample_sealed=true`、`survivor_rescued=true`、`relay_online=true`、`crew_alive=true`、`oxygen>0`。
- 明确反例：把“到过 P/E”当成完成（三局都是这样）；走 P–E 四 tick 远路而不留回程电（R0/R1/R2 全部 `VEHICLE_STRANDED`）；把货舱塞满再 `charge`（`RESOURCE_CONFLICT`）。
- 递进位置：本图是 lunar 三图里唯一的**多目标、长程、载具资源**题。MAP-25 是单人顺序合规，MAP-26 是隐藏故障纠错；本图没有隐藏故障（`relay_state=OFFLINE` 公开），难度来自“货舱两格 × 四条道路 × 一次性电芯 × 两阶段救援”的组合约束。

## 2. 机制与因果链

起始状态（tick 0）：`location=B`、`battery=14/14`、`oxygen=18`、`cargo=[]`、`cargo_capacity=2`、`charger_cells_remaining=null`（不在 S）、`relay_state=OFFLINE`、`sample_state=UNSAMPLED`、`survivor_state=UNSUPPORTED`、`visible_edges=["B_S"]`、`supplies_here={"sample_container":1}`。

必需观察 → 关键决策 → 立即后果 → 终局（较快的 B 方案，16 决策 / 20 tick / 余电 2 / 余氧 6）：

1. B：`load sample_container`（1 tick，占 1 格）。
2. `drive S`（1 tick / 1 电 / 1 氧，`battery=13`，出现 `S_E` 1、`S_R` 2 两条边与两种备件）。
3. S：`load medical_kit`（货舱 2/2）。
4. `drive E`（走 1 tick 的近路），`rescue(field_stabilize, medical_kit)` → `survivor_state=STABILIZED`，医疗包被消耗（货舱回到 1）。
5. `drive S` → `load relay_repair_kit`（货舱 2/2）→ `drive R`（2）→ `repair_relay`（2 tick，永久 ONLINE，消耗维修盒）→ `rescue(remote_evacuation)`（R 可用，需中继在线 + 已稳定）。
6. `drive P`（2）→ `sample(sample_container)` → `sample_state=SEALED`（容器仍占 1 格）。
7. `drive R`（2）→ `drive S`（2）→ `drive B`（1）→ `submit`。

- 可绕过核心机制的动作：**有，但都会被资源约束反噬**。① `charge` 可在 S 补 4 电（2 tick，唯一电芯，硬顶 14），但**需要 1 格空货舱**，且电芯只有 1 枚；② 走 `P_E`（4 tick）可少一次折返，但 14 电只够 A 方案（25 tick、余电 0），任何多一点折返就 `VEHICLE_STRANDED`；③ 可以先修中继再稳定伤员（A 方案），但必须用掉唯一电芯。
- 机制是否在三条真实轨迹中实际触发：**否**。三局都没有 `load medical_kit`、没有 `load relay_repair_kit`、没有 `rescue`、没有 `repair_relay`、没有成功 `sample`（R0 决策 6 与 R1 决策 4 的 `sample` 在 E 返回 `INVALID_LOCATION`）。`joint_task_completion_rate` 恒 0.0 正是“一个目标都没完成”。
- 触发所需最小动作数：**16**（B 方案）；A 方案 17（多一次 `charge`、多一段 S–R 折返）。两条都由模块内 `ORACLE_CASES` 在真实环境重放为 `ALL_OBJECTIVES_COMPLETE`（tick 20 / 25）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `tick` / `battery` / `battery_capacity` / `oxygen` | 是（Observation） | tick 0 起 | 是（可逐步记账） |
| `local_edges`（含 `to`/`ticks`/`battery`/`oxygen`） | 是（Observation） | 每到一个节点就给出该点的全部相邻边与成本 | 是；全部 5 条边可由 4 次移动看全 |
| `cargo` / `cargo_capacity` / `supplies_here` | 是（Observation） | tick 0 起 | 是（B 有样本容器，S 有医疗包与维修盒） |
| `charger_cells_remaining` | 是（Observation），但**只在 S 非 null** | 到 S 时 | 可反推“充电在 S”（B/E/P/R 均为 `null`） |
| `relay_state` / `sample_state` / `survivor_state` / `crew_alive` / `objectives` | 是（Observation） | tick 0 起 | 是（四个目标逐项可见） |
| 目标文本 | 是（Observation `goal` + system prompt） | tick 0 起 | 是（B 提交、四项条件） |
| 动作名、`item_id`、`operation` 词表 | 是（prompt 动作契约 + `_VOCABULARY["MAP-27"]`） | 每步 | 是（三种物品、两种救援操作都列出了） |
| **动作地点表**：`charge` 只在 S、`sample` 只在 P、`repair_relay` 只在 R、`field_stabilize` 只在 E | **否** | 只能靠 `INVALID_LOCATION` 逐步试 | 可试（拒绝 0 tick），但 3 次试错占用决策；本审计的公开启发式就用了 3 次 |
| **受困判定**：每次移动后若“回 B 的最低电量 > 剩余电量”立即 `VEHICLE_STRANDED` | **否** | 只有触发时才知道，且随即终局 | 不能事前从文本推导；必须自己用 `local_edges` 成本算回程 |
| `charge` 需要空货舱格（`RESOURCE_CONFLICT`） | **否** | 只有塞满货舱去充电时才暴露 | 可反推（本图三局未触发） |
| 货舱两格与“样本容器封存后仍占 1 格” | 部分：`cargo_capacity=2` 与 `cargo` 可见，但“封存后仍占格”未说明 | 需要试 | 影响 S 取第二件工具的顺序 |
| `judge_state`（`stock`、`violations`、`objective_ticks`、`blackout_ticks`） | 否 | — | 否 |
| Oracle 路径/用例 | 否 | — | 否 |

结论：解题必需的状态与成本全部公开；缺的是“动作地点表”与“受困判定”两条**可由拒绝/终局反馈学习**的规则。它们在 46 步预算内可被试探（3 次零成本探测 + 一次终局），因此**不构成阻塞**，但会显著抬高“第一次就排对”的门槛。

## 4. 可解性与可观察性

- Oracle：2 个用例（`relay_first_remote_road` 17 动作、`stabilize_first_short_road` 16 动作），重放均 `scenario_success / ALL_OBJECTIVES_COMPLETE`（tick 25 / 20）。`runs/v9/baselines/MAP-27.json` 记 `oracle_ok=2 / oracle_cases=2`。
- **仅凭公开信息是否存在可执行策略：存在。** 本次实现的 `Map27Heuristic` 只读 Observation（图、成本、库存、电量、氧气、目标）：
  1. B 装样本容器 → 走到 S（`supplies_here` 出现两种备件）；
  2. 装医疗包 → 用零成本 `rescue(field_stabilize)` 探测出伤员点（E）；
  3. 回 S 装维修盒 → 用 `repair_relay` 探测并修复 R → 在 R 远程撤离；
  4. 到 P（用 `sample` 探测）封存样本 → 沿已学图回 B → `submit`。
- 实测：**19 决策成功**（其中 3 次是零成本地点探测：S 的 `field_stabilize`、S 的 `repair_relay`、R 的 `sample`），tick 20，`joint_task_completion_rate=3/3`、`critical_path_delay=0`、`communication_blackout_ticks=11`、`resource_conflicts=0`、余电 2、余氧 6。
- 该策略**没有使用 `charge`**，也不需要知道“受困判定”；它只依赖“每段路先算回程”的通用约束。充电与远路都是可选分支，不是通关必需品。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `stabilize_first_short_road` | 16 | `ALL_OBJECTIVES_COMPLETE` | 3/3、delay 0、blackout 11、tick 20、余电 2、余氧 6 |
| Oracle `relay_first_remote_road` | 17 | `ALL_OBJECTIVES_COMPLETE` | 3/3、delay 5、blackout **9**、tick 25、余电 0、余氧 3 |
| 公开启发式 `Map27Heuristic` | 19 | `ALL_OBJECTIVES_COMPLETE` | 3/3、delay 0、blackout 11、余电 2、余氧 6 |
| V8 R0 / R1 / R2 | 8 / 10 / 6 | `VEHICLE_STRANDED` ×3 | 3/3 → 0/3；blackout 13 / 12 / 14 |
| `legal_random`（20 seed） | 1–28 | `OBJECTIVES_INCOMPLETE_AT_BASE` ×20 | 0/3；blackout 0–1 |

`legal_random`：0 成功，20/20 首步或前几步就 `submit`（该动作在 B 起手合法），因此随机基线在本图**几乎不探索**；`invalid_actions=0`，被拒动作合计 62（该计数受 `ShapeSampler` 的 set 迭代顺序影响，跨进程可能变化）。这不是“随机也走不动”，而是“随机立刻交卷”，对本图的路线能力没有信息量。

**判定：不是预算不够。** 正确路线 16–17 步、公开策略 19 步，预算 46；三局 V8 分别只用了 8 / 10 / 6 步就因电量终止。真正的瓶颈是**每段移动后的回程电量**，不是决策数。

电量/氧气经济是否可行（本次用真实环境逐步结算复核）：

| 路线 | 电量消耗序列 | 合计 | 余电 | 氧气合计 | 余氧 | tick |
|---|---|---|---|---|---|---|
| B 方案（无充电） | 1,1,1,2,2,2,2,1 | 12 | 2 | 12 | 6 | 20 |
| A 方案（充一次电） | 1,(+4→14),2,2,2,2,4,1,1 | 15 消耗 −4 充入 = 净 11 | 0 | 15 | 3 | 25 |

结论：**不充电也够**（B 方案余 2 电），充电只是 A 方案的补偿手段；`charge` 不是通关必需，也不是“电池经济不可行”的证据。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map27.joint_task_completion_rate` | `(relay_online + survivor_rescued + sample_sealed)/3` | 固定 3 | 0.0 / 0.0 / 0.0 | 三局 valid |
| `map27.critical_path_delay` | 成功终局 tick − 20 | 参考关键路径 | N/A / N/A / N/A | **只在 `is_success` 时计算**；三局都是失败 → `metrics()` 返回 `None` |
| `map27.communication_blackout_ticks` | 中继 OFFLINE 期间推进的 tick | episode | 13 / 12 / 14 | valid |
| `map27.resource_conflicts` | `cargo_errors + resource_conflict_errors` | episode | 0 / 0 / 0 | valid |

- **`critical_path_delay=None` 的原因**：`map27.py:408-410` 的 `delay` 初始为 `None`，只有 `if self.is_success:` 才赋值。三局都以 `VEHICLE_STRANDED` 失败，所以它从未被赋值；V8 投影按 `outcome="failure"` 把 `None` 记为 `not_applicable`。这是**设计上“只在成功时定义”**，不是投影把 `censored` 降级（本图三局不是预算截尾）。
- **未通关仍有意义的连续主指标**：`joint_task_completion_rate`（0/3 与 Oracle 的 3/3 直接可比；冻结 fixture 还给出 2/3 的中间值）与 `communication_blackout_ticks`（13/12/14 vs Oracle 9（A）/ 11（B））。
- 三局没有 `censored`；`critical_path_delay` 的 3 个 `not_applicable` 是唯一缺失，已在上文说明。
- 区分能力：Oracle / 启发式（3/3、delay 0）vs V8 / 随机（0/3）可区分；`resource_conflicts` 在三局、两个 Oracle、启发式与随机中**全为 0** → `LOW_DISCRIMINATION`（只有冻结 fixture 的“货舱塞满再充电”能到 2）。
- 指标缺口（不是缺陷）：本图的“失败有多接近成功”目前只能由 `joint_task_completion_rate` 的 0/3、1/3、2/3 三档表达，无法区分“差一枚医疗包”和“差一半电池”。

## 7. 三次轨迹归因

### R0（`V8-MAP-27-R0-20261017T103727Z-7d22e4e5`，8 决策，`VEHICLE_STRANDED`）

- 决策 1 `{"tool":"load","item_id":"sample_container"}` → `LOAD_SUCCEEDED:sample_container`；观察变化 `{"cargo":[{"item_id":"sample_container","slots":1}],"supplies_here":{"sample_container":0},"tick":1}`。
- 决策 2 `{"tool":"drive","to":"S"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":13,"charger_cells_remaining":1,"location":"S","oxygen":17,"tick":2,"supplies_here":{"medical_kit":1,"relay_repair_kit":1}}`。
- 决策 3 `{"tool":"drive","to":"R"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":11,"location":"R","oxygen":15,"tick":4}`。
- 决策 4 `{"tool":"drive","to":"P"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":9,"location":"P","oxygen":13,"tick":6}`。
- 决策 5 `{"tool":"drive","to":"E"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":5,"location":"E","oxygen":9,"tick":10}`。
- 决策 6 `{"tool":"sample","item_id":"sample_container"}` → `INVALID_LOCATION`；观察变化 `{}`（在 E 采样）。
- 决策 7 `{"tool":"drive","to":"S"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":4,"location":"S","oxygen":8,"tick":11}`。
- 决策 8 `{"tool":"drive","to":"R"}` → `VEHICLE_STRANDED`；观察变化 `{"battery":2,"location":"R","oxygen":6,"terminal":true,"terminal_reason":"VEHICLE_STRANDED","tick":13}`。

首次偏离：决策 2——到 S 后 `supplies_here` 明明列出 `medical_kit` 与 `relay_repair_kit`，模型却没有 `load`，直接奔向 R/P/E。它的目标被简化成“到 P 采样、回 B”，忽略了 `objectives` 里三项全是 `false`。
失败链：没取工具 → 无法稳定/修中继/撤离 → 走 P–E 远路 → 电 14→2 → 在 R 处回程需 3 电 → 受困。氧气尚有 6，说明**不是氧气不足**。
替代解释：模型可能把 `sample` 当成“在任何地点都能做”，所以先跑 E 再回 P；但 `sample` 在 E 返回 `INVALID_LOCATION` 后它也没回 P，而是继续回 S/R——说明路线是先验固定、没有按目标重规划。

### R1（`V8-MAP-27-R1-20261017T103810Z-8a598271`，10 决策，`VEHICLE_STRANDED`）

- 决策 2 `{"tool":"drive","to":"S"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":13,"charger_cells_remaining":1,"location":"S","oxygen":17,"tick":2,"supplies_here":{"medical_kit":1,"relay_repair_kit":1}}`。
- 决策 3 `{"tool":"drive","to":"E"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":12,"location":"E","oxygen":16,"tick":3}`。
- 决策 4 `{"tool":"sample","item_id":"sample_container"}` → `INVALID_LOCATION`；观察变化 `{}`。
- 决策 5 `{"tool":"drive","to":"S"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":11,"location":"S","oxygen":15,"tick":4}`。
- 决策 6 `{"tool":"drive","to":"R"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":9,"location":"R","oxygen":13,"tick":6}`。
- 决策 7 `{"tool":"drive","to":"P"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":7,"location":"P","oxygen":11,"tick":8}`。
- 决策 8 `{"tool":"drive","to":"E"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":3,"location":"E","oxygen":7,"tick":12}`。
- 决策 9 `{"tool":"charge"}` → `INVALID_LOCATION`；观察变化 `{}`。
- 决策 10 `{"tool":"drive","to":"P"}` → `BATTERY_INSUFFICIENT`；观察变化 `{"terminal":true,"terminal_reason":"VEHICLE_STRANDED"}`。

首次偏离：决策 3 到 E 后不取医疗包、不 `rescue`，只试了一次 `sample`；以及决策 8 在只剩 3 电时仍走 P→E（需 4 电，实际由 `BATTERY_INSUFFICIENT` 拦下）。
`charge()` 为什么 `INVALID_LOCATION`：`map27.py:251-253` 的 `_charge()` 第一行就是 `if self.node != "S": return "INVALID_LOCATION"`。决策 9 时 `location=E`，所以是**地点不对**，不是电芯用完（`CHARGER_EMPTY`）、也不是电量已满（`BATTERY_ALREADY_FULL`）、更不是货舱冲突（`RESOURCE_CONFLICT`）。公开面其实给了提示：`charger_cells_remaining` 在 E 是 `null`，只有在 S 才是 `1`（R0 决策 2 的观察即为证）。模型没有把这个 null/非 null 当作地点信号。
失败链：两趟 P–E 远路（4+4）→ 电 14→3 → 在 E 充电被拒 → 连去 P 的 4 电都不够 → 受困。氧气 7，仍不是缺氧。
替代解释：模型把 `charge` 当成“随处可用的补电”，说明“一次性电芯在 S”这条事实没有公开；但它同时也忽略了 `charger_cells_remaining` 的地點线索。

### R2（`V8-MAP-27-R2-20261017T103905Z-0f942fc4`，6 决策，`VEHICLE_STRANDED`）

- 决策 2 `{"tool":"drive","to":"S"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":13,"charger_cells_remaining":1,"location":"S","oxygen":17,"tick":2,"supplies_here":{"medical_kit":1,"relay_repair_kit":1}}`。
- 决策 3 `{"tool":"drive","to":"R"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":11,"location":"R","oxygen":15,"tick":4}`。
- 决策 4 `{"tool":"drive","to":"P"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":9,"location":"P","oxygen":13,"tick":6}`。
- 决策 5 `{"tool":"drive","to":"E"}` → `DRIVE_SUCCEEDED`；观察变化 `{"battery":5,"location":"E","oxygen":9,"tick":10}`。
- 决策 6 `{"tool":"drive","to":"P"}` → `VEHICLE_STRANDED`；观察变化 `{"battery":1,"location":"P","oxygen":5,"tick":14,"terminal":true,"terminal_reason":"VEHICLE_STRANDED"}`。

首次偏离：决策 2 同样没有取 S 的两种备件；决策 5 在 E 只剩 5 电时仍走 P–E 折返。
失败链：`objectives` 三项始终 `false`，模型只做“巡逻式”往返；电 14→1，在 P 回程需 5 电，触发受困。
**重复证据有限**：三局都是同一骨架（B→S→…→P–E 远路→电尽），差异只在折返次数（R0 走到 R、R1 多一次 charge 尝试、R2 少一次）。n=3 不能区分个体差异与固定陷阱，但三局**都没有装载任何备件/医疗包**，更像固定陷阱：模型把“到达样本点”当成任务终点。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | F 资源管理：走 P–E 远路且不留回程电（14→2） | E 策略：在 S 不装载医疗包/维修盒，忽略三项目标；B 公开信息不足（受困判定、动作地点表） | F 高 / E 高 / B 中 | 决策 2、5、8；`map27.py:230-249` |
| R1 | F（两趟 P–E，14→3） | E（同 R0）+ C 接口（`charge` 地点未公开，却能用 `charger_cells_remaining` 反推） | F 高 / E 高 / C 中 | 决策 3、4、8、9、10 |
| R2 | F（P–E 折返，14→1） | E（巡逻式路线） | F 高 / E 高 | 决策 2、5、6 |

排除：A（规则自洽；两个 Oracle 通过；受困判定与设计一致）、D（预算 46，Oracle 16–17、启发式 19，三局 6–10 步即终止）、G（没有记忆/推理链证据）、H（0 非法动作、0 provider 错误）、I（证据完整）。

## 9. 标签

- `MEASUREMENT_VALID`：Oracle 2/2、公开启发式 19 步成功、随机 0/20；`joint_task_completion_rate` 与 `communication_blackout_ticks` 能区分成功与失败，且 `submit` 的部分完成（fixture 2/3）可表达。
- 不选 `INTERFACE_BLOCKED`：动作地点表与受困判定未公开，但都能用零成本拒绝或一次终局学到，且 46 步预算足够（启发式 19 步内含 3 次探测）。
- 不选 `BUDGET_BLOCKED`、`RULE_DEFECT`、`CONSTRUCT_BYPASS`（没有绕过路径；充电与远路都被资源约束封死）。
- `METRIC_DEFECT` 不成立：`critical_path_delay` 的 N/A 是“只在成功时定义”，语义正确；只是主指标在失败局无连续值，记为设计缺口而非缺陷。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：`_VOCABULARY["MAP-27"]` 只列 `drive(to)；charge()` 等动作名，不含地点；`map_spec.yaml` 的 `charging.location: S`、`strand_condition: minimum_battery_path_to_B_exceeds_remaining_battery`、`sample.location: P` 均未进入 prompt。
- 证据与根因：R1 决策 9 在 E `charge` → `INVALID_LOCATION`；R0/R1/R2 分别在电 2/3/1 时受困；公开启发式 19 步成功证明规则本身不阻塞。
- **候选 A（推荐，只补公开信息，不改规则与数值）**：在 `_VOCABULARY["MAP-27"]` 增加一行：“`load`：样本容器在 B、医疗包/维修盒在 S；`charge` 只在 S（一次性电芯，+4，需 1 格空货舱）；`sample` 只在 P；`repair_relay` 只在 R；`field_stabilize` 只在 E；每次 `drive` 后若剩余电量不足回到 B，立即 `VEHICLE_STRANDED`。”预期：把失败从“猜地点/不知道受困规则”移向“排程与电量预算”。反例/风险：R0/R2 连 S 的备件都不取，说明“不看目标”是独立问题；若成功率从 0/3 跳到 3/3，需 Batch 6 评估本图是否仍属困难层。
- **候选 B（只改指标，不改规则）**：为失败局补一个可算的连续量，例如 `battery_margin_at_terminal = battery − min_cost_to_B`（可为负）或 `objectives_completed` 已由 `joint_task_completion_rate` 覆盖。预期：能区分“差一步受困”与“一步没做”；风险：新增指标需登记 `MetricSpec`、`valid_range` 与 extractor，并重算历史值。
- **候选 C（文案）**：把 `goal` 从“在 B 提交：……”扩成“需要先稳定伤员、修复中继、封存样本，再回 B 提交”，避免模型把“到 P”当终点。这是纯 prompt 修改，但会改变 `prompt_hash`。
- 不建议：加电量、加氧气、把 `charge` 改成随处可用、把 `VEHICLE_STRANDED` 改成软失败——都会改变本图的核心构念。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-27.json`：

| 类别 | 结果 |
|---|---|
| Oracle | 2/2 成功（17 / 16 动作，tick 25 / 20） |
| `legal_random`（20 seed） | 0 成功；20/20 `OBJECTIVES_INCOMPLETE_AT_BASE`（多为第 1 步 `submit`）；决策 1–28 |
| `public_heuristic` | 成功，19 决策，3/3、delay 0、blackout 11、conflicts 0、余电 2、余氧 6 |
| 消融 | 无（本图未登记消融） |

独立复算（不使用 `map27.metrics()`，只读 `actions[].observation_after` 的公开字段与 `local_edges` 成本）：

1. R0 电量：14 −(B→S 1) −(S→R 2) −(R→P 2) −(P→E 4) −(E→S 1) −(S→R 2) = **2**；在 R 回 B 最低需 `S_R 2 + B_S 1 = 3 > 2` → 受困。与末态 `battery=2`、`VEHICLE_STRANDED` 一致。
2. R1 电量：14 −1 −1 −1 −2 −2 −4 = **3**；下一步 P 需 4 > 3 → `BATTERY_INSUFFICIENT`。氧气 18 −1 −1 −1 −2 −2 −4 = **7**，与末态 7 一致 → 不是缺氧。
3. R2 电量：14 −1 −2 −2 −4 −4 = **1**；在 P 回 B 最低需 `R_P 2 + S_R 2 + B_S 1 = 5 > 1` → 受困。氧气 18 −1 −2 −2 −4 −4 = **5**，与末态 5 一致。
4. 启发式电量：14 −1 −1 −1 −2 −2 −2 −2 −1 = **2**；tick = 1(load)+1+1+1+1+2+2+2+2+1+1(submit 0)=20 → `critical_path_delay = 20 − 20 = 0`。
5. `joint_task_completion_rate`：`(relay ONLINE) + (survivor RESCUED) + (sample SEALED)`，三局终态三项均 false → 0/3；启发式终态三项均 true → 3/3。

## 12. V9 状态

`VALIDATED`（P2）。理由：地图规则自洽、Oracle 2/2、公开启发式 19 步可通关、随机 0/20，失败原因是可归因的电量预算与目标误解，不是接口或预算阻塞；建议只补公开的动作地点表与受困判定（候选 A），并把 `critical_path_delay` 在失败局无值记为已知设计缺口。
