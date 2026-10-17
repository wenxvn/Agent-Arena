# MAP-27｜月球｜困难｜月面联合行动

```yaml
map_id: MAP-27
world: moon
nominal_level: 困难
capability_primary: long_horizon_tool_and_resource_coordination
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: b31e01f7dff799262c3aa6ae3e1902d44d7b1de40ba2adcf0111d2bb2d4d3c09
source_design_hash: dd3dd1dbf97c713e6b8cd9d43a01a341ce8b4f83e562f7310247ce951804a266
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“长程联合任务里的工具/资源协调”。5 节点、两格货舱、单一车辆、一次性电芯：样本容器、医疗包、中继维修盒各占一格，而任务要求**修中继 → 稳定并远程撤走伤员 → 封存样本 → 带样回 B**。`P–E` 远路（4 tick/4 电/4 氧）与 `S–E` 短路（1 tick）让“先修中继”和“先救伤员”成为两条成本不同的可行路线。核心不是“捡齐东西”，而是**在货舱两格与电池 14 的约束下安排互斥工具的先后**。

## 2. 真实规则字段

- 图：`B-S-R-P` 主链 + `P-E`（4 tick）+ `S-E`（1 tick）；每段 tick/电池/氧气同值；边双向。
- 初始：B，电量 14/14，氧气 18，货舱 2 格；B 有样本容器；S 有唯一医疗包、唯一维修盒、一次性电芯。
- 中继：R 处初始 `OFFLINE`，携带维修盒 `repair_relay` 2 tick 后永久在线，消耗维修盒。
- 救援：E 处 `rescue(field_stabilize)` 需医疗包、1 tick、消耗之；`rescue(remote_evacuation)` 需中继在线且伤员已稳定，可在 R 或 E 执行、1 tick。未稳定 → `CASUALTY_NOT_STABILIZED`；中继离线 → `RELAY_OFFLINE`。
- 充电：S 处每局一次、2 tick、最多补 4、硬封顶 14，溢出作废；第二次 `CHARGER_EMPTY`。
- 载货：容器/医疗包/维修盒各 1 格；装满再装 → `CARGO_CAPACITY_EXCEEDED` 且状态不变。采样后容器仍占 1 格。
- 失败：`VEHICLE_STRANDED`（最低返 B 电量 > 剩余）、`CREW_OXYGEN_DEPLETED`、`OBJECTIVES_INCOMPLETE_AT_BASE`。
- 成功：`sealed_sample_at_B` + `survivor_RESCUED` + `relay_ONLINE` + `crew_alive` + `oxygen > 0`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map27.joint_task_completion_rate` | primary | 完成的中继/救援/样本任务数 / 3 | 比例 / 高 | 3 | 未提交 → 按已完成任务计；终局缺失 → CENSORED |
| `map27.critical_path_delay` | primary | 实际完成 tick − 参考关键路径 20 | tick / 低 | 成功终局 | 未完成 → N/A；无参考 → UNAVAILABLE |
| `map27.communication_blackout_ticks` | guardrail | 中继 `OFFLINE` 的 tick 数 | tick / 低 | episode | 0 合法（修好后不再离线） |
| `map27.resource_conflicts` | diagnostic | `count(CARGO_CAPACITY_EXCEEDED) + count(RESOURCE_CONFLICT)` | 次 / 低 | episode | 0 合法 |

实现状态：**未实现**（`implemented=False`）。参考关键路径取**较快的手写方案 B = 20 tick**；方案 A = 25 tick，故 A 的 `critical_path_delay = 5`。这是“手写参考”而非全局最优证明。

## 4. 能力混淆分析

- 高完成率可能靠“先修中继再慢慢走远路”：A 完成 3/3 但延误 5、电量恰好 0；必须与 `critical_path_delay` 和电池余量并列。
- 低黑屏 tick 可能只是“先修中继”这一条路线：A 黑屏 9、B 黑屏 11，但 B 反而早 5 tick 完成。黑屏时长与总体效率**不是同向指标**。
- `resource_conflicts=0` 不代表载荷管理好：F01 没带医疗包，不是“冲突”，是**缺件**；工具失败应另报（本卡未注册独立 metric）。
- “完成救援”必须区分稳定与远程撤离：只做 `field_stabilize` 的 F02 完成率只有 1/3，不能被算成“救援完成”。

## 5. 两条手算轨迹

**A. 先修中继，再带医疗包走远路（tick25）**：B 装容器(1)、`B→S`(2)、充电 2 tick 只补 1（4）、取维修盒(5)、`S→R`(7)、修中继 2 tick（9，中继上线）、`R→S`(11)、取医疗包(12)、`S→R`(14)、`R→P`(16)、采样(17)、`P→E`(21)、稳定(22)、远程撤离(23)、`E→S`(24)、`S→B`(25)。指标：完成率 3/3；`critical_path_delay = 25−20 = 5`；`communication_blackout_ticks = 9`；冲突 0；电量 0、氧 3。

**B. 先稳定伤员，再修中继并采样（tick20）**：B 装容器(1)、`B→S`(2)、取医疗包(3)、`S→E`(4)、稳定(5)、`E→S`(6)、取维修盒(7)、`S→R`(9)、修中继 2 tick（11）、远程撤离(12)、`R→P`(14)、采样(15)、`P→R`(17)、`R→S`(19)、`S→B`(20)。指标：完成率 3/3；`critical_path_delay = 0`；`communication_blackout_ticks = 11`；冲突 0；电量 2、氧 6、不用电芯。

> A 与 B 都 3/3，但 A 延误 5、黑屏更短、电量恰好 0；B 不充电、余量更大。**“黑屏短”与“完成快”互不支配**，必须并列报告。

## 6. 三个机制特有失败

1. **F01 没带医疗包就去救人**：照 A 用电芯、修好中继并封样，却没从 S 装医疗包就走 `P–E`；`field_stabilize` 返回 `MEDICAL_KIT_REQUIRED`，回 B 提交时伤员未稳定/撤离 → `OBJECTIVES_INCOMPLETE_AT_BASE`。完成率 2/3。
2. **F02 只稳定就当作完成救援**：先 `S–E` 稳定伤员，再绕 `R–P` 封样回 B；没有维修盒、没修中继、没发远程撤离 → 提交失败。完成率 1/3（只有样本）。
3. **F03 省掉必需充电**：复制 A 路线但首次抵 S 不充电；修中继、取样、走远路后电池仅 1，而 `E–S–B` 最低返程需 2 → `VEHICLE_STRANDED`。氧气仍有余量，失败原因是**电量**，不是时间。

## 7. 两个边界

- **满电封顶 14（B01）**：B→S 后电量 13，充能只补 1 至 14，不得报 18；第二次请求 `CHARGER_EMPTY`。
- **返程余电 2 可走 vs 1 不可（B04）**：E 点剩 2 可 `E–S` 后以 1 电走 `S–B`；剩 1 判无法安全返航。另 B02 货舱恰好 2 格，再装第三件必须先消耗前置物，否则 `CARGO_CAPACITY_EXCEEDED` 且状态不变。

## 8. 信息泄漏负例

若 Observation/prompt 直接给参考计划、最短总耗或“先救后修更省”，长程协调被替代。V7 只允许公开当前位置、道路成本、电量/氧、货舱与本地库存、中继/样本/伤员状态、最近动作结果与终局；`planning/hand_traces.json`、Oracle、参考关键路径只在离线侧。

## 9. Oracle/求解状态

`planning/hand_traces.json` 有两条手写成功（25/20 tick）与逐动作资源账；`failure_traces/cases.yaml` 有 F01–F03 与 B01–B06；`planning/seed_replay.yaml` 固定 seed0 库存与道路成本。**没有运行时、没有独立最优求解器、没有真实模型实验**；手算只证明两条路线可行，不证明 20 tick 是全局最优。

## 10. 与同世界另两图差异

**vs MAP-25**：MAP-25 是单 Agent 的**顺序合规**（穿服/挂绳/诊断），没有货舱、电池、远程救援；MAP-27 是长程资源协调，失败常来自电量/载荷而非漏步骤。

**vs MAP-26**：MAP-26 是诊断-反馈-回滚循环，故障隐藏；MAP-27 的故障（中继离线）是公开的，难度在**任务排序与工具互斥**。MAP-26 的指标是恢复延迟，MAP-27 是完成率/关键路径/黑屏。

## 11. 可计算性来源

需要的字段：`current_tick, current_node, battery_remaining, oxygen_remaining, cargo_ids_and_slots, supply_remaining_here, charger_cells_remaining, relay_state, sample_state, survivor_state, crew_alive, last_action_result, terminal_reason`，以及每次 `drive/load/charge/repair_relay/sample/rescue` 的 tick 与结果。完成率由三个终态布尔量求和；关键路径延误由提交 tick 减 20；黑屏由逐 tick `relay_state==OFFLINE` 计数；冲突由 `CARGO_CAPACITY_EXCEEDED` 等码计数。

## 12. 难度定位与对照

D=(1,3,2,3,2,3)。相对 MAP-26 提升 **D↑（长程多阶段：救援/中继/采样/返程）与 R↑（电量/氧/货舱/一次性电芯）**；V 保持 1（无隐藏故障）、E 到 2（一次性电芯与资源窗口）。不会与 MAP-26 混淆：MAP-26 无货舱/电池，MAP-27 无错误替换反馈。

预登记对照：**“先修中继”参考方案 vs “先稳定伤员”参考方案**（两条公开路线），加上 **工具提示 vs 无提示** 条件。若提示组只学会照抄路线，应视为路线记忆而非协调能力；两组共享地图、资源与目标。

## 13. 未决

- `critical_path_delay` 的参考值 20 来自手写方案 B，不是求解器最优；若未来有 BFS/整数规划最优，应替换并版本化。
- `map27.resource_conflicts` 的公式含 `RESOURCE_CONFLICT`，但 `map_spec` 只列 `CARGO_CAPACITY_EXCEEDED` 等具体码；接入前需确认是否存在统一 `RESOURCE_CONFLICT`，否则只计货舱溢出。
- 黑屏 tick 与完成 tick 不是同向指标（A 黑屏短但慢），报告不得合成单一“效率分”。
- 无运行时、无真实模型结果；所有数值为纸面资源账。状态 `pending_human_review`。
