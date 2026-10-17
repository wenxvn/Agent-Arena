# MAP-17｜地铁｜中等｜早高峰

```yaml
map_id: MAP-17
world: metro
nominal_level: 中等
capability_primary: multi_objective_schedule_optimization
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: da028ad6bd76a751b9cfacf0c13a2b7cdada0d697d19fa604c6d01ce1e4fa339
source_design_hash: 259ab66b150fcbc42b174ba6e006aa859b5fbccfabde6312df51e52bafb3f978
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“多目标运力/能耗的 Pareto 取舍”。环线 `A-B-C-D-A` 挂支线 `B-E-F`，4 列车 `T_A@A / T_C@C / T_D@D / T_F@F` 每 tick 提交一行全局时刻表；10 名乘客 5 组 OD 在 tick0 到齐，12 tick 结算，能耗上限 18。核心不是“跑得越多越好”，而是在**唯一双向共用区段 B-C**上分配运力，同时保持准点交付、压低乘客等待并控制能耗——三项指标可以互不支配地交换，不存在单一最优调度。

## 2. 真实规则字段

- 拓扑：环线节点 `A,B,C,D`，边 `AB,BC,CD,DA`；支线 `B,E,F`，边 `BE,EF`；每段 1 tick。
- `B-C` 是唯一物理区段，**双向合并容量 1**；各站至多 2 列车；每车座位 3。
- 初始 `T_A@A, T_C@C, T_D@D, T_F@F`；固定客流 `A→C 2, B→E 2, C→F 2, D→B 2, F→A 2`。
- 时间窗 tick0–tick11 共 12 个结算 tick；能耗上限 18；无随机延误、无隐藏需求（seed0）。
- 动作：`set_timetable(current_tick, joint_operations)` 每日一行；行内 `release(train,next)` 耗 1 能量占本 tick 区段，`stop(train,manifest)` 停 1 tick 装载，`switch_line(train,ring|branch,manifest)` 仅在 B 可换线且不耗能，`delay` 原地空等。
- 事件序：验证相邻站/区段预约/双向容量/站台终态泊位/登车清单/剩余能量 → 冲突则整批失败且位置、能耗、tick 全不变 → tick 开始仍在站台的乘客各 +1 等待 → 同步移动 → 抵站自动卸客 → 按清单装客 → tick+1。
- 成功：无冲突、`energy ≤ 18`、tick12 前送达 ≥ 8/10。
- 失败码：`SHARED_SEGMENT_CONFLICT`、`PLATFORM_CAPACITY`、`ENERGY_BUDGET_EXCEEDED`、`DEADLINE_SERVICE_BELOW_80`、`INVALID_LINE_SWITCH`、`INVALID_BOARDING_MANIFEST`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map17.service_rate` | primary | 实际在目的站下车人数 / 10（按 OD 权重，不按上车数） | 比例 / 高 | 总客流权重 10 | 提前终止仍按 10 计分母，未送达计未服务 |
| `map17.cumulative_wait_person_ticks` | primary | Σ 每位乘客在站台的 tick 数（含登车前与换乘等待） | 人·tick / 低 | 已发生等待的乘客 | 无乘客上车且未结算 → 该乘客计至 tick12 |
| `map17.energy_per_passenger` | diagnostic | `energy_used / delivered_passengers` | 能量/人 / 低 | 已送达人数；0 → N/A | 0 送达 → N/A，不补 0 |
| `map17.overcapacity_events` | guardrail | `count(PLATFORM_CAPACITY) + count(SHARED_SEGMENT_CONFLICT)` | 次 / 低 | episode | 0 合法 |

实现状态：**未实现**（`implemented=False`），`compute_metrics("MAP-17", ...)` 抛 `NotImplementedError`。设计口径来自冻结的 `map_spec.yaml`；接入运行时后由 `passenger_ledger` / `energy_ledger` / `terminal_reason` 逐条重算。

`service_rate`、`wait`、`energy` 三项**必须并列报告**。本图不提供加权总分；参考距离 `non_dominated_distance` 在设计中定义，但 V7 不注册为独立 metric，避免把“离参照点近”误读为“能力强”。

## 4. 能力混淆分析

- 高服务率可能来自“开满 12 tick 空跑 + 少量载客”，能耗随之上升；必须与 `energy_per_passenger` 并列，否则分不清运力效率与运力堆叠。
- 低等待可能来自“少接人”：节能参照正是如此（等待 38 人·tick，服务 8/10）；低等待必须与 `service_rate` 同报。
- 低能耗可能只是“少发车”：F03 只排两班车，能耗 6 但服务 6/10，未过 80% 门槛；`energy_per_passenger` 在低送达时会被放大，不能单独当效率证据。
- `PLATFORM_CAPACITY` 与 `SHARED_SEGMENT_CONFLICT` 是两种不同因果（站台泊位 vs 双向单段），合成“冲突率”会掩盖 B-C 瓶颈是否被正确使用。

## 5. 两条手算轨迹

**准点优先（12 行时刻表，服务 10/10）**：tick0 四车各 `stop` 接起点 2 人 → tick1 `A→B / C→B / D→C / F→E` → tick2 `B→C`（T_A 独占 B-C）/ `B 换支线` / `delay` / `E→B` → tick3 `hold / B→E / C→B / B→A` → tick4–5 补齐 B→E 剩余 1 人与 F→A。指标：`service_rate = 10/10 = 1.0`；`wait = 16` 人·tick；`energy = 11` → `energy_per_passenger = 1.1`；`overcapacity = 0`。

**节能优先（省略 T_F 班次，服务 8/10）**：同一客流表上只服务 `A→C / C→F / D→B / B→E` 共 8 人，F 站 2 人留候至 tick12。指标：`service_rate = 0.8`（恰好等于门槛）；`wait = 38`；`energy = 8` → `energy_per_passenger = 1.0`；`overcapacity = 0`。

> 两点**互不支配**：准点表服务更高且等待更少，节能表能耗更低。`energy_per_passenger` 在两点分别为 1.1 与 1.0，说明“每人能耗”本身不足以区分优劣——它必须与 `service_rate` 一起读。本图不声称这两点是全局最优前沿。

## 6. 三个机制特有失败

1. **F01 双向交换**：tick2 让 `T_A` 走 `B→C` 同时 `T_C` 走 `C→B`，触发 `SHARED_SEGMENT_CONFLICT`；整行拒绝、位置/能耗/tick 全不变。这是本图唯一瓶颈的特有摩擦，单线图上不会出现。
2. **F02 站台超容**：B 站已有 `T_A,T_C` 两车时仍令 `T_F` 从 E 驶入 B，tick 末 3 车 > 2 泊位，`PLATFORM_CAPACITY`。合法区段预约不等于合法站台。
3. **F03 服务不足**：只排 `T_C,T_D` 两班，送达 6/10、能耗仅 6，仍因 `< 80%` 触发 `DEADLINE_SERVICE_BELOW_80`。低能耗不能抵消低服务。

## 7. 两个边界

- **8/10 恰好达标 vs 7/10 失败**：`success_predicate` 是 `>= 8`，节能表与 B01 用例都在端点上；7/10 即使能耗更低也失败。指标侧 `service_rate=0.8` 必须显示为成功，不能因“未满 100%”被误判。
- **B-C 单段容量的 tick 级判定**：同一 tick 内两车**同向**也不得同时占用 B-C（物理区段证据容量 1，不是按方向拆分）。边界用例必须包含“同向双车”与“反向双车”两种拒绝，避免把规则误读成只禁相向。

## 8. 信息泄漏负例

若 Observation 直接给出参照时刻表、Pareto 前沿、每 tick 应派哪列车或未来乘客流，多目标取舍被替代。V7 只允许公开拓扑、客流矩阵、车位置/座位、在车乘客、待运需求、已交付、能耗/剩余能量、累计等待与终止状态；`planning/hand_traces.json`、`pareto_reference.json`、`schedule_audit.py` 只在离线裁判侧。12 tick 之后的“未来需求”不存在，也不得以提示形式暗示。

## 9. Oracle/求解状态

V4 有两份**手工** 12 行时刻表（`planning/hand_traces.json`）与 `schedule_audit.py` 的逐 tick 复核，输出 `pareto_reference.json`：准点 10/10、等待 16、能耗 11；节能 8/10、等待 38、能耗 8；`points_mutually_non_dominated=true`、`global_optimal_front_proven=false`。`oracle_trace.jsonl` 记录当前公开状态与当前 tick 计划。**没有运行时、没有真实模型实验**；审计只证明两份表内部自洽与互不支配，不证明存在或不存在更优调度。

## 10. 与同世界另两图差异

**vs MAP-16**：MAP-16 是 2 列车固定起终点的 makespan/死锁题，成功条件是确定的位置交换；MAP-17 是 4 列车 + 乘客流的多目标题，成功是“服务率门槛内的一组向量”，没有唯一终点。MAP-16 的 `makespan_gap` 在 MAP-17 没有对应物（这里没有单一最优 makespan）。

**vs MAP-18**：MAP-18 有闭塞故障、三线六车与在线恢复，故障窗口会改变可用区段；MAP-17 无故障、无时刻表扰动，B-C 瓶颈是**静态**容量。MAP-18 的核心是恢复延迟与服务率，MAP-17 的核心是等待/能耗的 Pareto 交换；把 MAP-17 加上故障会变成 MAP-18 的构念。

## 11. 可计算性来源

需要公开并进入 trace 的：`demand_matrix`、`train_positions`、`onboard_passengers`、`waiting_demand`、`delivered_by_od`、`energy_consumed/energy_remaining`、`passenger_wait_person_ticks`、`terminal_reason`，以及每 tick 提交的联合时刻表行（含被拒原因）。`service_rate` 由 `delivered_by_od` 求和 / 10；`wait` 优先用环境累计账，退化时按 `passenger_ledger` 逐人重算；`energy_per_passenger` = `energy_consumed / delivered`；`overcapacity_events` 从结果码计数。全部可由 trace 确定性重算，不需要隐藏真值。

## 12. 难度定位与对照

D=(1,3,1,3,2,3)。相对 MAP-16 提升 **D↑（多阶段调度链）与 R↑（区段/泊位/座位/能量四类资源同时争用）**；V 不变（拓扑与客流全公开），E 仅到“时窗”级（无随机故障）。这不会与 MAP-16 混淆，因为 MAP-16 的构念是死锁避免，指标是 makespan/冲突；MAP-17 的构念是 Pareto 交换，指标是服务/等待/能耗三元组。

预登记对照：**显式多目标表（三指标并列）vs 单一“效率分”提示**。两组使用相同实例、相同 12 tick 预算；若单一分提示导致模型压低服务率换能耗，应记录为度量界面效应，而不是能力差异。另需一条**手工参照锚点可见性**对照：给/不给 `pareto_reference.json` 的两个条件不得混为同一实验。

## 13. 未决

- 运行时实现前需固定 `stop` 的 `transfer_manifest` 语义（设计文档写“换乘至少等 1 tick”，但两份参照表均不使用换乘），否则 `cumulative_wait_person_ticks` 的分母口径会漂移。
- `energy_per_passenger` 在 `delivered=0` 时为 N/A；需在运行时确认 `0/0` 不会被写成 0。
- V4 设计未定义“同 tick 同向双车占 B-C”的独立失败码（目前并入 `SHARED_SEGMENT_CONFLICT`）；V7 记录为 `V7-DCR` 候选，不改规则。
- 无运行时、无真实模型结果；本卡所有数值为**纸面/离线审计值**，不构成能力结论。状态保持 `pending_human_review`。
