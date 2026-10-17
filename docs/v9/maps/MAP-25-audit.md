# MAP-25 逐图审计：第一次出舱

> 本文件由 V9 Batch 1 依据 Trace、证据包、源码与本次离线复算重新推导；不复制 `docs/v8` 结论，不声称人工审核。V8 文件保持只读。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-25 第一次出舱 / lunar / 简单 |
| condition | `default` |
| `rule_hash` | `51e3acc1edab3736d0300c112d96539ec316601e0b7c12feab99a9cb96a15065` |
| `scenario_hash` | `f6aa408b1bc55347ca6e9ab2a856ee264255208246e14d0a2ee62a5b231b744a` |
| 决策预算 | 30（冻结清单；`docs/v9/baseline-audit.md` 无 MAP-25 预算例外） |
| V8 三局 | 0/3 成功；`decision_budget_reached` ×2、`OXYGEN_DEPLETED` ×1；决策 30 / 29 / 30 |
| 主指标 | `required_check_coverage` = 3/7（0.428571）、3/7、7/7；`dependency_order_correctness` = 5/11（0.454545）、5/9、9/13；`oxygen_shortfall` = 0 / 1 / 0；`unsafe_eva_attempts` = 0 / 0 / 0 |

数据来源：`runs/v9/evidence/MAP-25.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-25.json`、`docs/v8/maps/MAP-25-final.md`、`worlds/v4/MAP-25/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map25.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v9/policies/world_lunar.py`。

## 1. 能力构念

**一句话**：在“舱外每一步都烧氧、且维修必须在一次出舱内完成”的条件下，能否把准备阶段（穿服、取两件工具、挂绳、排压）一次做对，而不是靠反复出舱试错。

- 成功行为：`array_repaired=true` 后回到 H（`ALL_OBJECTIVES_COMPLETE`）。氧气只在舱外扣减。
- 明确反例：漏取 `diagnostic_unit`/`wrench` 就先出舱；把 `diagnose(device_id)` 填成 `array`；在 A 直接 `move H`（H 与 A 不相邻）。
- 递进位置：本图是 lunar 三图里唯一的**单人、单线程、无隐藏故障**题。MAP-26 把同一“通信中断”扩成隐藏故障 + 反馈纠错，MAP-27 换成多目标载具调度。本图只考“准备阶段的一次性顺序”，不考纠错或长程资源。

## 2. 机制与因果链

起始状态（tick 0）：`location=H`、`oxygen_remaining=12`、`airlock_pressure=PRESSURIZED`、`suit_worn=false`、`tether_attached=false`、`carried_tools=[]`、`visible_equipment_here=[]`。

必需观察 → 关键决策 → 立即后果 → 终局：

1. H 无装备（`visible_equipment_here=[]`），必须找到装备所在节点（T）。
2. 在 T `equip eva_suit|diagnostic_unit|wrench`；每件 +1 tick、0 氧。
3. 到 A `equip safety_tether` → `depressurize`（`airlock_pressure=VACUUM`）→ `eva_exit`（首次扣 1 氧，`location=S`）。
4. S 处 `inspect(target=array)` 得 `array_surface_symptom=ARRAY_OUTPUT_ZERO`（扣 1 氧）；`diagnose(device_id=diagnostic_unit)` 得 `diagnosis_code_if_obtained=FUSE_BANK_B_OPEN`（扣 1 氧）。
5. `repair(target_id=array_fuse_B, tool_ids=[diagnostic_unit,wrench], diagnosis_code=…)`：2 tick、扣 2 氧；缺工具或未诊断时**仍然扣 2 氧**（`_repair` 在检查前已设 `_cost=2,_oxygen_cost=2`）。
6. `return_to_A`（扣 1 氧）→ `pressurize` → `move T` → `move H` 才结算成功。

- 可绕过核心机制的动作：**没有**。`repair` 只认 `array_fuse_B` + 两件精确工具 + 已诊断；`pressurize` 是 A→T 的硬前置（`_move` 对 `VACUUM` 返回 `AIRLOCK_NOT_PRESSURIZED`）。
- 机制是否在三条真实轨迹中实际触发：**否**。三局都只走到 `inspect(array)`；`diagnose` 共 7 次全部返回 `INVALID_TOOL_ID`（R0 决策 9/17/22、R1 决策 20、R2 决策 9/22/30），`repair` 一次都没执行。也就是说，这张图的“诊断 → 维修 → 返舱”核心链路在三局里**从未被真正激活**。
- 触发所需最小动作数：**15**（跳过不计入成功判定的 `inspect(equipment)`）；官方 Oracle 带该检查为 16。本次用真实环境逐步结算确认：15 步 `ALL_OBJECTIVES_COMPLETE`、余氧 6、`required_check_coverage=6/7`。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `tick` / `oxygen_remaining` / `airlock_pressure` / `inner_hatch_locked` | 是（Observation） | tick 0 起 | 足以跟踪位置与氧气账本（每步差值可见） |
| `suit_worn` / `tether_attached` / `carried_tools` / `visible_equipment_here` | 是（Observation） | tick 0 起；装备清单只在 T 非空 | 足以判断“还缺哪件、当前节点有没有装备” |
| `array_surface_symptom` / `diagnosis_code_if_obtained` / `array_repaired` | 是（Observation） | 检查 / 诊断 / 修复后 | 足以决定下一步是检查、诊断还是维修 |
| 目标文本 | 是（Observation `goal` + system prompt） | tick 0 起 | 给出“穿服→A 挂绳排压→出舱→检查诊断→精确工具维修→返回 H” |
| 动作名、字段形状、节点词表 | 是（prompt 动作契约 + `_VOCABULARY["MAP-25"]`） | 每步 | 词表明确写了 `target_id=array_fuse_B`、`tool_ids 需含 diagnostic_unit 与 wrench`、`diagnose(device_id): diagnostic_unit` |
| **节点邻接关系（H–T–A–S 线性）** | **否**（只列出四个节点名，不列边） | 只能由 `MOVED:x` / `NOT_ADJACENT` 反馈推断 | 可推断但要多花决策：三局共 8 次 `NOT_ADJACENT` |
| **每次舱外动作的耗氧量**（exit/inspect/diagnose=1、repair=2、return=1） | **否** | 只能由 `oxygen_remaining` 差值反推 | 可推断；但本图只有一次出舱的余量，反推晚一步就会耗尽 |
| “缺工具时 `repair` 仍扣 2 氧” | **否** | 只有执行后由 `MISSING_REQUIRED_TOOL:*` + 氧减反馈 | 不可事前推导（本图未触发） |
| `judge_state`（`required_done`、`required_attempted`、`diagnosed`、`tools`） | 否 | — | 否 |
| Oracle 路径/用例 | 否 | — | 否 |

结论：解题**必需**的信息（工具集合、`array_fuse_B`、诊断仪设备名、返回 H）都在公开面；缺的只是“邻接表 + 每步耗氧”这两类可由反馈反推的效率信息。故本图不是 `INTERFACE_BLOCKED`。

## 4. 可解性与可观察性

- Oracle：2 个用例（`inspect_then_equip`、`suit_first`），各 16 动作，重放均 `scenario_success / ALL_OBJECTIVES_COMPLETE`，完成 tick 17、余氧 6。`runs/v9/baselines/MAP-25.json` 记 `oracle_ok=2 / oracle_cases=2`。
- **仅凭公开信息是否存在可执行策略：存在**。本次实现的 `Map25Heuristic` 只用 Observation 与词表：H→T 取三件装备 → 检查清单 → A 挂绳 → 排压 → 出舱 → 检查 → 诊断 → 精确工具维修 → 返舱 → 增压 → T → H，**16 决策成功**，指标 `required_check_coverage=7/7`、`dependency_order_correctness=7/7`、`oxygen_shortfall=0`、`unsafe_eva_attempts=0`。邻接关系用“H–T–A–S 线性舱段”的通用布局假设 + `NOT_ADJACENT` 反馈修正，不读取任何隐藏真值。
- 公开策略不需要知道“氧气 12”或“单趟 6 氧”，只需要不在 S 反复进出；这正是本图要测的能力。
- 未标 `INTERFACE_BLOCKED`：公开面虽无邻接表与耗氧表，但两者都能由动作结果反推，且 30 步预算留有 14 步余量。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `inspect_then_equip` / `suit_first` | 16 / 16 | `ALL_OBJECTIVES_COMPLETE` | 覆盖 7/7、依赖 1.0、余氧 6 |
| 手算最短路线（跳过 `inspect(equipment)`） | 15 | `ALL_OBJECTIVES_COMPLETE` | 覆盖 **6/7**、依赖 1.0、余氧 6 |
| 公开启发式 `Map25Heuristic` | 16 | `ALL_OBJECTIVES_COMPLETE` | 覆盖 7/7、依赖 1.0、余氧 6 |
| 消融 `no_tool_collection` | 17 | `OXYGEN_DEPLETED` | 覆盖 3/7、依赖 **13/13=1.0**、`oxygen_shortfall=1` |
| V8 R0 | 30 | `decision_budget_reached` | 覆盖 3/7、依赖 5/11、余氧 3 |
| V8 R1 | 29 | `OXYGEN_DEPLETED` | 覆盖 3/7、依赖 5/9、余氧 0 |
| V8 R2 | 30 | `decision_budget_reached` | 覆盖 **7/7**、依赖 9/13、余氧 4 |

`legal_random`（20 seed，形状合法、语义随机）：0 成功，20/20 `decision_budget_reached`，`invalid_actions=0`，被拒动作合计 278 次（同一代码另一次进程运行为 263；该计数受 `ShapeSampler` 的 set 迭代顺序影响，跨进程可能不同，见 §11）；覆盖率恒为 0/7，`unsafe_eva_attempts` 恒 0——随机策略从未凑齐“穿服 + 挂绳 + 排压”三件套，因此连舱外都没出去过。

**判定：不是预算不够。** 成功只需 15–16 步，预算 30。R0/R2 用满 30 步的原因不是“路太长”，而是把决策花在**重复出舱与无效移动**上：

- R0：3 次 `eva_exit`（决策 7/15/21）+ 3 次 `return_to_A`（10/18/25），另有 4 次 `move H` 与 1 次 `move S` 被 `NOT_ADJACENT` 拒绝（11/13/19/26/28），且**从未回到 T 取工具**。
- R2：3 次 `eva_exit`（7/15/28）+ 2 次 `return_to_A`（10/17），中途两次在 A 尝试 `equip diagnostic_unit`（12）和 `move H`（13/19）浪费决策；真正取到工具已是决策 21/24。
- R1：5 次 `eva_exit` + 4 次 `return_to_A` + 3 次 `inspect(array)` = 12 氧全部烧完，**决策 29 时氧 0**。

因此 R0/R2 是“预算刚好够一次正确路线、但被 3 次错误出舱吃掉”；R1 是“氧气预算被 5 次出舱吃光”。两者都不是“30 步不够走完正确路线”。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map25.required_check_coverage` | `len(required_done)/7`（4 装备 + T 清单 + S 检查 + 诊断） | 固定 7 | 3/7、3/7、**7/7** | 无 N/A（三局全 valid） |
| `map25.dependency_order_correctness` | `required_correct/required_attempted` | 已尝试必需步骤数 | 5/11、5/9、9/13 | R0–R2 分母 9–13 均 >0；随机 1 seed 分母 0 → N/A |
| `map25.oxygen_shortfall` | `1 if terminal_reason==OXYGEN_DEPLETED` | episode | 0、1、0 | 无 |
| `map25.unsafe_eva_attempts` | `UNSUITED_EVA + UNSAFE_UNTETHERED_EVA` 次数 | episode | 0、0、0 | 无 |

- **未通关仍有意义的连续主指标**：`dependency_order_correctness` 与 `oxygen_shortfall`。R0（5/11）与 R2（9/13）确实区分了“一步都没走对”与“取到工具但顺序错”。
- 三局没有 `not_applicable` / `censored`（`metric_status_counts` 为 `valid: 4`），与 `docs/v9/data-integrity.md` §4.2 一致。
- **区分能力：`required_check_coverage` 与 `dependency_order_correctness` 均 `LOW_DISCRIMINATION`，且可被错误动作刷满。** 本次独立复算（只调用公开 `step`，不读 judge 写入）：

  ```text
  在 S 且 held=[diagnostic_unit,wrench]、array_inspected=true：
  step({"tool":"diagnose","device_id":"array"}) -> INVALID_TOOL_ID
  before: coverage 6/7, dependency 6/6
  after : coverage 7/7, dependency 7/7
  judge : diagnosed=False, diagnosis_code_if_obtained=None
  ```

  原因在 `map25.py:262-268`：`correct` 的判定条件只含 `node=="S" and array_inspected and "diagnostic_unit" in tools and oxygen>=1`，**不含 `action.device_id=="diagnostic_unit"`**，而 `_record_required("diagnosed", …, done=correct)` 在字段校验（第 269 行）之前执行。于是 R2 的“覆盖 7/7”是在 `diagnosed=False`、`diagnosis_code=None` 的状态下取得的。
- 另一个口径问题：`map_spec.yaml` 明确 `inspect_equipment_required_for_success: false`，但 `REQUIRED_STEPS` 把 `equipment_inspected` 计入分母；15 步成功路线因此只能得 6/7。分母定义与成功条件不一致（见 §10 候选 B）。
- `unsafe_eva_attempts` 在 Oracle、启发式、消融、随机 20 seed 与三局 V8 中**全为 0** → 对本组对照完全无区分度（`LOW_DISCRIMINATION`）；它只在“不穿服/不挂绳就出舱”时才非零，而本图的三次失败都不是安全违规。

## 7. 三次轨迹归因

### R0（`V8-MAP-25-R0-20261017T100410Z-8a64cbdd`，30 决策，`decision_budget_reached`）

- 决策 1 `{"tool":"equip","item_id":"eva_suit"}` → `EQUIPMENT_NOT_AVAILABLE_HERE`；观察变化 `{}`（位置仍在 H）。
- 决策 2 `{"tool":"move","to":"T"}` → `MOVED:T`；观察变化 `{"location":"T","tick":1,"visible_equipment_here":["eva_suit","diagnostic_unit","wrench"]}`。
- 决策 3 `{"tool":"equip","item_id":"eva_suit"}` → `SUIT_EQUIPPED`；观察变化 `{"suit_worn":true,"tick":2}`。**此后只带走了 EVA 服**，诊断仪与扳手留在 T。
- 决策 8 `{"tool":"inspect","target":"array"}` → `ARRAY_OUTPUT_ZERO`；观察变化 `{"array_surface_symptom":"ARRAY_OUTPUT_ZERO","oxygen_remaining":10,"tick":7}`。
- 决策 9 `{"tool":"diagnose","device_id":"array"}` → `INVALID_TOOL_ID`；观察变化 `{}`。
- 决策 11 `{"tool":"move","to":"H"}` → `NOT_ADJACENT`；观察变化 `{}`（模型不知道 A 与 H 不相邻）。
- 决策 30 `{"tool":"depressurize"}` → `AIRLOCK_DEPRESSURIZED`；观察变化 `{"airlock_pressure":"VACUUM","inner_hatch_locked":true,"tick":19}`（预算在此耗尽，仍在 A）。

首次偏离：决策 3 之后离开 T 时 `carried_tools=[]`，与公开的 `repair 需含 diagnostic_unit 与 wrench` 直接冲突，但模型没有回头。
失败链：只穿服 → 缺工具 → `diagnose` 永远 `INVALID_TOOL_ID` → 无法维修 → 三次出舱烧氧（12→3）→ 30 步耗尽。**从未回到 T** 是这条链的关键：整个 30 步里没有一次 `move T`（除决策 2 的 H→T）。
替代解释：接口（邻接与耗氧未公开，B/C）会放大浪费，但不是首因——模型在决策 2 已经看到 T 有全部三件装备却只取一件。

### R1（`V8-MAP-25-R1-20261017T100614Z-d408f23c`，29 决策，`OXYGEN_DEPLETED`）

- 决策 2 `{"tool":"move","to":"A"}` → `NOT_ADJACENT`；观察变化 `{}`（H 不邻 A）。
- 决策 4 `{"tool":"move","to":"T"}` → `MOVED:T`；观察变化 `{"location":"T","tick":1,"visible_equipment_here":["eva_suit","diagnostic_unit","wrench"]}`。
- 决策 9 `{"tool":"eva_exit"}` → `EVA_STARTED`；观察变化 `{"location":"S","oxygen_remaining":11,"tick":6}`。
- 决策 10 `{"tool":"inspect","target":"array"}` → `ARRAY_OUTPUT_ZERO`；观察变化 `{"array_surface_symptom":"ARRAY_OUTPUT_ZERO","oxygen_remaining":10,"tick":7}`。
- 决策 11 `{"tool":"return_to_A"}` → `RETURNED_TO_A`；观察变化 `{"location":"A","oxygen_remaining":9,"tick":8}`。
- 决策 12 `{"tool":"eva_exit"}` → `EVA_STARTED`；观察变化 `{"location":"S","oxygen_remaining":8,"tick":9}`（**刚回舱就再次出舱**）。
- 决策 13 `{"tool":"inspect","target":"equipment"}` → `EQUIPMENT_NOT_AVAILABLE_HERE`；观察变化 `{}`（在 S 找装备）。
- 决策 29 `{"tool":"inspect","target":"array"}` → `ARRAY_OUTPUT_ZERO`；观察变化 `{"oxygen_remaining":0,"terminal":true,"terminal_reason":"OXYGEN_DEPLETED","tick":19}`。

首次偏离：决策 12——在 `oxygen_remaining=9` 且没有任何新工具、没有新信息的情况下立刻二次出舱；这是纯浪费。
失败链：只穿服（决策 5）→ 5 次 `eva_exit` + 4 次 `return_to_A` + 3 次 `inspect(array)` = 12 氧 → 决策 29 在 S 归零。这是本图唯一一局 `OXYGEN_DEPLETED`。
替代解释：模型把“回舱”当成“重新开始一次出舱”，而不是“结束任务”；这既是策略错误（E），也被“没有公开的耗氧表”放大（B）。注意最后一次 `inspect` 的**结果码仍是 `ARRAY_OUTPUT_ZERO`**，只有 `terminal_reason` 才说明是缺氧致死——结果码本身不提示致命性（C 级接口问题，见 §10 候选 C）。

### R2（`V8-MAP-25-R2-20261017T100747Z-74246a3f`，30 决策，`decision_budget_reached`，覆盖 7/7）

- 决策 8 `{"tool":"inspect","target":"array"}` → `ARRAY_OUTPUT_ZERO`；观察变化 `{"array_surface_symptom":"ARRAY_OUTPUT_ZERO","oxygen_remaining":10,"tick":7}`。
- 决策 9 `{"tool":"diagnose","device_id":"array"}` → `INVALID_TOOL_ID`；观察变化 `{}`。
- 决策 12 `{"tool":"equip","item_id":"diagnostic_unit"}` → `EQUIPMENT_NOT_AVAILABLE_HERE`；观察变化 `{}`（在 A 取工具）。
- 决策 20 `{"tool":"move","to":"T"}` → `MOVED:T`；观察变化 `{"location":"T","tick":15,"visible_equipment_here":["eva_suit","diagnostic_unit","wrench"]}`。
- 决策 21 `{"tool":"equip","item_id":"diagnostic_unit"}` → `TOOL_EQUIPPED:diagnostic_unit`；观察变化 `{"carried_tools":["diagnostic_unit"],"tick":16,"visible_equipment_here":["eva_suit","wrench"]}`。
- 决策 24 `{"tool":"equip","item_id":"wrench"}` → `TOOL_EQUIPPED:wrench`；观察变化 `{"carried_tools":["diagnostic_unit","wrench"],"tick":18,"visible_equipment_here":["eva_suit"]}`。
- 决策 28 `{"tool":"eva_exit"}` → `EVA_STARTED`；观察变化 `{"location":"S","oxygen_remaining":5,"tick":21}`。
- 决策 30 `{"tool":"diagnose","device_id":"array"}` → `INVALID_TOOL_ID`；观察变化 `{}`（预算耗尽；`judge` 侧 `diagnosed=False`，但覆盖被记成 7/7）。

首次偏离：决策 9 的 `device_id="array"`——词表写的是 `diagnose(device_id): diagnostic_unit`，模型把“被诊断对象”当成了设备名。这个错误在三局里重复了 7 次。
失败链：错误设备名 → 无诊断码 → 无法维修；同时前 20 步已经用掉 2 次出舱 + 2 次返舱 + 2 次重复检查（氧 12→6），取到工具后（决策 24）只剩 6 氧，再出舱与检查后只剩 4 氧，只够“诊断 1 + 维修 2 + 返舱 1”，没有第二次试错余量。
替代解释：若把预算加到 40，R2 在决策 30 时氧 4、工具齐、位置 S，**确实还够一次正确的“诊断+维修+返舱”**。所以本局的直接原因是“设备名填错 + 前段浪费”，预算只是最后一步的放大器；不是“30 步走不完正确路线”（正确路线 15–16 步）。
**重复证据有限**：R0 与 R2 结构高度相似（只在 T 取部分装备、多次 `move H` 被拒），R1 是“取到服就反复出舱”的变体；n=3 无法区分个体差异与固定陷阱，但三局都没有出现一次 `repair`，更像固定陷阱（对 `diagnose` 参数名的误读）。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | E 策略规划：在 T 只取 EVA 服就离开，违反公开的 `repair` 工具要求 | B 公开信息不足（邻接/耗氧未公开）；C 接口（`NOT_ADJACENT` 不提示正确邻接） | E 高 / B 中 / C 中 | 决策 3、9、11、30；`_VOCABULARY["MAP-25"]` |
| R1 | F 资源管理：5 次出舱 + 4 次返舱 + 3 次重复检查耗光 12 氧 | E 策略（未取工具、把返舱当重启）；B（耗氧表未公开） | F 高 / E 高 | 决策 5、12、29；`map25.py:334-340` |
| R2 | E 策略规划：`diagnose(device_id="array")` 而非 `diagnostic_unit`（重复 7 次中的 3 次） | D 预算（正确动作只剩最后 4 氧，无试错余量）；B（邻接） | E 高 / D 中 | 决策 9、12、21、24、30 |

排除：A（规则自洽、确定性、Oracle 2/2 通过；`required_done` 记账缺陷另见 §6/§10，属指标口径而非致死规则）、H（0 非法动作、0 provider 错误、90 局 trace 完整）、I（证据完整）。

## 9. 标签

- `MEASUREMENT_VALID`（构念可测的部分）：存在 16 步公开启发式成功；Oracle 2/2；`oxygen_shortfall` 能区分 R1。
- `METRIC_DEFECT`：`required_check_coverage` 与 `dependency_order_correctness` 把一次被拒的 `diagnose(device_id="array")` 记为“诊断完成”（§6 复算），使 R2 在 `diagnosed=False` 时拿到 7/7；同时 `unsafe_eva_attempts` 对本组全部对照恒为 0。
- 不选 `INTERFACE_BLOCKED`：工具/目标/诊断设备名都在公开词表里，缺的邻接与耗氧可由反馈反推，且有 14 步余量。
- 不选 `BUDGET_BLOCKED`：正确路线 15–16 步 vs 预算 30。
- 不选 `RULE_DEFECT`：致死规则（12 氧、单趟 6 氧、维修前需诊断）自洽且与设计一致；问题在记账口径。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：`map25.py:262-268` 的 `correct` 判定与 `_record_required("diagnosed", …)`；`REQUIRED_STEPS` 含 `equipment_inspected`；词表不含邻接与耗氧。
- 证据与根因：R2 决策 30（`INVALID_TOOL_ID` 却 coverage 7/7）；本次独立复算（诊断前 6/7 → 诊断后 7/7，`diagnosed=False`）；15 步成功路线只得 6/7。
- **候选 A（推荐，只改指标口径，不改规则）**：`map25.metrics()` 的 coverage 分子改为 `len(required_done - {"diagnosed"}) + int(self.diagnosed)`，依赖正确率的 `diagnosed` 项同理。预期：R2 的 coverage 从 1.0 降到 6/7，Oracle/启发式仍 7/7。风险：`metric_schema_hash` 变化，旧值需 `runs/v9/rescore/` 只读重算；不改变 `rule_hash`/`scenario_hash`，旧 Trace 仍可回放。
- **候选 B（指标分母与设计对齐）**：从 `REQUIRED_STEPS` 移除 `equipment_inspected`（`map_spec.yaml` 明写 `inspect_equipment_required_for_success: false`），分母改 6。预期：15 步路线与 16 步路线同为 1.0，覆盖率和成功判定一致。风险：与 V7 卡片的 7 项口径不一致，需要 DCR 说明。
- **候选 C（只改公开信息，不改规则）**：在 `_VOCABULARY["MAP-25"]` 增加一行“节点邻接 H–T–A–S；舱外每步耗氧 1，维修 2，返舱 1；A 在排压状态下不能直接回 T”。预期：减少 `NOT_ADJACENT` 与重复出舱；测试点从“猜拓扑/记氧气”移向“一次做对准备顺序”。风险：若成功率从 0/3 跳到 3/3，本图在简单层可能失去区分度，需要 Batch 6 评估。
- 不建议：改氧气 12、延长预算、把 `OXYGEN_DEPLETED` 改成软失败、把 `diagnose` 的 `device_id` 放宽为任意值——都会改变构念或把模型错误改成成功。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-25.json`：

| 类别 | 结果 |
|---|---|
| Oracle | 2/2 成功（16 / 16 动作，tick 17，余氧 6） |
| `legal_random`（20 seed） | 0 成功；20/20 `decision_budget_reached`；`invalid_actions=0`；被拒动作 278（另一次进程运行 263）；覆盖恒 0/7 |
| `public_heuristic` | 成功，16 决策；覆盖 7/7、依赖 7/7、`oxygen_shortfall=0` |
| 消融 `no_tool_collection` | 失败，17 决策，`OXYGEN_DEPLETED`；覆盖 3/7、依赖 13/13、`oxygen_shortfall=1` |

独立复算（不使用 `map25.metrics()`，只读 `judge_state` 与真实 `step` 结果）：

1. 氧气账本：Oracle 路线 12 −（exit 1 + inspect 1 + diagnose 1 + repair 2 + return 1）= **6**，与 Trace 末态 `oxygen_remaining=6` 一致。
2. R1：5×exit + 4×return + 3×inspect = **12** → 0，与 `OXYGEN_DEPLETED` 一致。
3. R0：3×exit + 3×return + 3×inspect = 9 → **3**，与末态 `oxygen_remaining=3` 一致（`decision_budget_reached` 而非缺氧）。
4. R2：3×exit + 2×return + 3×inspect = 8 → **4**，与末态 4 一致。
5. 覆盖率口径复算见 §6：`required_done` 的 7 项里 `diagnosed` 来自一次被拒动作；按“实际诊断成功”应是 6/7。

基线可复现性提醒：`legal_random` 的被拒计数（本次 278，另一次进程运行 263）受 `src/agent_arena/v9/baselines.py::ShapeSampler` 用 `set` 保存形状、`rng.choice` 直接索引未排序列表的影响，跨进程可能变化（与 MAP-10 审计记录的 `V9-DCR-BASE-01` 同源）；MAP-25 的 `equip` 有两个形状，故受影响。不影响 Oracle / 启发式 / 消融结论。

## 12. V9 状态

`NEEDS_REDESIGN`（P1）。理由：地图规则与 Oracle 都站得住、公开启发式 16 步可通关，但两项主指标（覆盖率、依赖正确率）会把一次被拒的诊断动作记为“完成”，R2 的 7/7 与 `diagnosed=False` 直接矛盾；最小修复是改指标口径（候选 A）并与设计定义对齐（候选 B），不需要改规则或加预算。
