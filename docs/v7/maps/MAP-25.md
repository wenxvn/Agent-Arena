# MAP-25｜月球｜简单｜第一次出舱

```yaml
map_id: MAP-25
world: moon
nominal_level: 简单
capability_primary: dependency_ordered_procedure
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: f20327d215855561de9a7bafe075ca530e99724d83a79622bd1d97556f076b57
source_design_hash: 533bd978e29b6c89122177f9694eb61cec1c7cfb01f08897c73e9a4205cb07b9
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“严格依赖顺序的舱外作业”。拓扑 `H—T—A—S`：H 出发，T 装备工具，A 挂安全绳并排压，`eva_exit` 到 S，诊断阵列、用精确工具 ID 维修，再返 A、增压、回 H。这不是“收集物品”：穿服、挂绳、排压、检查、诊断、维修、返舱之间存在**不可交换的前置关系**，漏一步就有专属失败码；氧气 12 点只在 S 段逐 tick 消耗，返舱动作可从 1 氧启动并在 A 归零。

## 2. 真实规则字段

- 拓扑：`H—T—A—S`；`H-T`、`T-A` 各 1 tick 且不耗便携氧；`A-S` 只能 `eva_exit`/`return_to_A`，不能用普通 `move`。
- 初始：H，氧气 12/12；气闸增压、内外门关闭；EVA 服/诊断仪/扳手套件在 T；安全绳固定在 A 锚点但未挂接；无额外氧源。
- 装备：`equip(item_id)` 只接受 `eva_suit / diagnostic_unit / wrench / safety_tether`；前三件只能在 T，绳只能在 A 挂 `anchor`。
- 检查：`inspect(equipment)` 在 T 返回可用清单；`inspect(array)` 在 S 只返回 `ARRAY_OUTPUT_ZERO`。
- 诊断：`diagnose(device_id=diagnostic_unit)` 需已检查阵列并携带诊断仪，返回 `FUSE_BANK_B_OPEN`。
- 维修：`repair(target_id=array_fuse_B, tool_ids=[diagnostic_unit,wrench], diagnosis_code=FUSE_BANK_B_OPEN)`，ID/成员/诊断码必须精确匹配。
- 氧气：出舱 1、表面检查 1、诊断 1、维修 2、返 A 1；维修开始时至少 3 氧；余 2 时 `OXYGEN_RESERVE_REQUIRED_FOR_RETURN` 且不开始维修；S 降到 0 立即终止。
- 动作：`move`、`equip`、`inspect`、`diagnose`、`depressurize`、`eva_exit`、`repair`、`return_to_A`、`repressurize`。
- 失败：`UNSUITED_EVA`、`UNSAFE_UNTETHERED_EVA`、`DIAGNOSIS_REQUIRED`、`MISSING_REQUIRED_TOOL:*`、`INVALID_TOOL_ID`、`OXYGEN_DEPLETED`、`OXYGEN_RESERVE_REQUIRED_FOR_RETURN`、`OBJECTIVE_INCOMPLETE_AT_H`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map25.required_check_coverage` | primary | 已完成的必需检查/装备步骤 / 7 | 比例 / 高 | 7（4 件装备 + T 清单 + S 检查 + 诊断） | 未进入流程 → 0（合法）；缺动作账 → UNAVAILABLE |
| `map25.dependency_order_correctness` | primary | 前置条件满足的已尝试步骤 / 已尝试步骤 | 比例 / 高 | 已尝试步骤；0 → N/A | 0 步 → N/A |
| `map25.unsafe_eva_attempts` | guardrail | `count(UNSUITED_EVA) + count(UNSAFE_UNTETHERED_EVA)` | 次 / 低 | episode | 0 合法 |
| `map25.oxygen_shortfall` | diagnostic | `1[terminal_reason==OXYGEN_DEPLETED]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |

实现状态：**未实现**（`implemented=False`）。注册表公式写的是 `count(EVA_BEFORE_SAFE)` 与 `OXYGEN_SHORTFALL`，但设计/环境的真实原因码是 `UNSUITED_EVA`/`UNSAFE_UNTETHERED_EVA` 与 `OXYGEN_DEPLETED`；接入时必须显式映射，不能因码名不同而恒报 0。

## 4. 能力混淆分析

- 高覆盖率可能来自“把所有装备都点了但没排压”：`dependency_order_correctness` 会把“未挂绳就出舱”判错；两指标必须并列。
- `dependency_order_correctness=1.0` 可能只因为“只做了一步”：分母是已尝试步骤，0 步为 N/A；必须同时报覆盖率。
- `unsafe_eva_attempts=0` 不代表流程正确：F03 全程安全出舱，却因浪费氧气导致 `OBJECTIVE_INCOMPLETE_AT_H`。
- `oxygen_shortfall=0` 也不代表氧气管好：F03 在 A 归零但人已安全，缺的是任务完成；只有 S 段降到 0 才是短供。
- 工具错误要分层：`INVALID_TOOL_ID` 是 schema 拒绝（零成本），`MISSING_REQUIRED_TOOL` 是有效 typed call（耗 2 氧），不能合并成“工具错误率”。

## 5. 两条手算轨迹

**A. 检查优先（17 tick 回 H，耗氧 6）**：`H→T`(1)；`inspect(equipment)`(2)；按诊断仪、扳手、EVA 服次序 `equip`(3–5)；`T→A`(6)；`equip(safety_tether)`(7)；`depressurize`(8)；`eva_exit`(9)；`inspect(array)`(10)；`diagnose`(11)；`repair`(12–13)；`return_to_A`(14)；`repressurize`(15)；`A→T→H`(16–17)。指标：覆盖率 **7/7=1.0**；顺序正确率 **7/7=1.0**；`unsafe_eva_attempts=0`；`oxygen_shortfall=0`；余氧 6。

**B. 服装优先（同样 17 tick，耗氧 6）**：`H→T`；先 `equip(eva_suit)`，再取扳手、诊断仪，最后 `inspect(equipment)`；其余安全步骤与工具链同 A。指标：覆盖率 1.0；顺序正确率 1.0（四件装备彼此无前置约束，检查清单可后置）；`unsafe=0`；余氧 6。

> 两条轨迹**装备顺序不同但都正确**，说明 `dependency_order_correctness` 不能把“固定顺序”当唯一正解；它只检查真实前置关系（绳必须先于 `eva_exit`、诊断必须先于维修等）。

## 6. 三个机制特有失败

1. **F01 未穿服出舱**：`H→T→A` 后直接 `eva_exit` → `UNSUITED_EVA`，不开始舱外段、不虚扣氧气。这是“准备步骤缺失”，不是“氧气不足”。
2. **F02 穿服但未挂绳**：正确装备三件套并排压，跳过 `equip(safety_tether)` 直接出舱 → `UNSAFE_UNTETHERED_EVA`。排压与挂绳是**两个独立前置**，不能互相替代。
3. **F03 不读反馈地浪费氧气**：出舱并检查表面后，未诊断就维修一次（`DIAGNOSIS_REQUIRED`，耗 2 氧）；随后正确诊断，却三次只用 `tool_ids=[wrench]`（每次缺诊断仪、耗 2 氧）；余 1 氧安全返 A，A 处归零，增压回 H 但阵列未修 → `OBJECTIVE_INCOMPLETE_AT_H`。

## 7. 两个边界

- **S 剩 1 氧可返舱（B01）vs 剩 0 氧不可（B02）**：返舱动作可从 1 氧启动并在 A 归零；S 剩 0 不能启动，原地 `OXYGEN_DEPLETED`。这是“归零发生在安全舱口”与“归零发生在舱外”的区别。
- **未知 `spanner`（B03）vs 已知但不足的 `[wrench]`（B04）**：前者 schema 层拒绝、零耗时零耗氧；后者是有效 typed call、执行后返回缺工具码并耗 2 氧。两者不能都记成“一次工具错误”。

## 8. 信息泄漏负例

若 Observation 提前给出 `FUSE_BANK_B_OPEN`、正确工具组合或“下一步该挂绳”，依赖顺序题被替代。V7 只允许公开当前位置、氧气、装备状态、门/压力状态、已执行动作结果与公开枚举；诊断码只有在 `diagnose` 成功后才可见。Oracle 不得含私有故障字段或未调用工具的未来结果。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 保存一条完整 EVA 闭环（检查优先路线）；`planning/` 与 `failure_traces/cases.yaml` 有 F01–F03 与 B01–B04。**没有运行时、没有独立最优求解器、没有真实模型实验**；离线自审只证明流程、API 枚举、氧气账与反例自洽。

## 10. 与同世界另两图差异

**vs MAP-26**：MAP-26 有诊断反馈与备件预算，核心是“错了以后能否修正”；MAP-25 的故障是**固定且单一**的，核心是“别在准备阶段漏步”。MAP-25 没有备件消耗、没有 rollback。

**vs MAP-27**：MAP-27 是多主体协同（中继/采样/救援），核心是任务分配与通信；MAP-25 是单 Agent 的单线程流程。MAP-25 的指标是覆盖率/顺序正确率，MAP-27 是协同完成率/关键路径延误。

## 11. 可计算性来源

需要的字段：`current_location`、`oxygen`、`equipped_items`、`hatch/pressure` 状态、每次 `inspect/diagnose/equip/depressurize/eva_exit/repair/return_to_A` 的动作与结果码、`terminal_reason`。覆盖率由“7 个必需步骤中已完成者”计数；顺序正确率由“每步执行时其前置是否已满足”判定；unsafe 由两个出舱失败码计数；shortfall 由 `OXYGEN_DEPLETED` 判定。全部可由公开动作账重算。

## 12. 难度定位与对照

D=(1,2,0,1,1,1)。本世界基线：单 Agent、单线程、无事件；难度来自**前置依赖链**（D=2）与固定工具枚举。V=1（诊断码需主动获取）、R=1（只有氧气一种资源）。

预登记对照：**显式前置清单 vs 只给目标描述**。若清单组顺序正确率显著更高，说明构念测“按依赖执行”而非“猜目标”；两组共享拓扑、氧气、工具枚举与失败码。另需 **检查清单可后置 vs 必须前置** 对照，确认装备顺序本身不应被计错。

## 13. 未决

- `map25.unsafe_eva_attempts` 与 `map25.oxygen_shortfall` 的注册表公式使用了不存在的码名（`EVA_BEFORE_SAFE`/`OXYGEN_SHORTFALL`），接入前必须映射到 `UNSUITED_EVA`+`UNSAFE_UNTETHERED_EVA` 与 `OXYGEN_DEPLETED`，否则指标恒 0。
- `required_check_coverage` 的分母 7 是 V7 的定义（4 装备 + 2 检查 + 1 诊断）；若未来把“排压”也算必需步骤，分母会变，需版本化。
- 无运行时、无真实模型结果；所有数值为纸面流程审计值。状态 `human_approved`。
