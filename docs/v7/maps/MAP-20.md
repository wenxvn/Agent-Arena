# MAP-20｜火山｜中等｜冷却网络

```yaml
map_id: MAP-20
world: volcano
nominal_level: 中等
capability_primary: multi_node_resource_allocation
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: e35ac16b9e02881753f19a39438eafd5da2d38b6432c4c8f16bdd3679d51797e
source_design_hash: 6c306808efd61d0b11f4dda5aafc0eb999b8c733d4325d38d16091e8aaf159c8
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“多节点共享水量的跨 tick 分配”。每 tick 只有 6 单位来水（60 刻度），三条直供支管各限 2.5 单位，`A-B`、`B-C` 两条旁路可把水转给邻区但**必损 20%**。四个约束同时作用：水源总量、支管计量、区阀接收上限（4/4/3）、过热线 10.0。核心不是“给最热的区多倒水”（直供上限让这不可能），而是决定直供/旁路/负荷档三者如何在 tick 间交换，用邻区余量给热点续命。

## 2. 真实规则字段

- 管网：`S` 分三直供支管到 `A/B/C`；`A-B`、`B-C` 可双向旁路；同 tick 不得两头相向。
- 计量：1 单位 = 10 刻度；源 ≤ 60 刻度/tick；每支管 ≤ 25 刻度；旁路输入按 5 刻度递增、每条 ≤ 20 刻度；固定损失 20%（下游收输入的 4/5）。
- 区阀接收上限：`A=4, B=4, C=3`；接收量必须非负且不超上限，否则整帧原子拒绝。
- 起温 `A=7.0, B=6.0, C=5.0`；过热线**严格高于 10.0**。
- 负荷档与热/产能：满载 `[4,3,2]`、降载 `[2,2,1]`、停机 `[0,0,0]`（数组顺序 A/B/C）。
- 转移：`T_next = max(0, T_now + 热负荷 − 实际收到水量)`，三区先同时求值；任一 `>10.0` → `THERMAL_OVERHEAT`，本 tick 不计产能。
- 时间：tick0–9 共 10 tick；总产能 `>= 15` 成功，否则 `PRODUCTION_BELOW_20` 类失败（设计文档写作“至少 15”）。水量每 tick 重置，不储存。
- 动作：`read_temperature(zone)`（每帧一次，返回当前精确值 + 上一 tick 差分）、`set_supply`、`set_bypass`、`adjust_loads`、`wait`。控制无 tick 延迟。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map20.max_node_exceedance` | primary | `max_node max_t max(0, T_node,t − T_safe)`，`T_safe=10.0` | 温度单位 / 低 | 关键节点 3 | 缺精确温度 → UNAVAILABLE；截尾只累计已结算 tick |
| `map20.safe_node_ticks` | primary | Σ_node Σ_tick `1[T_node,t ≤ 10.0]` | 节点·tick / 高 | 3 × 有效 tick | 未结算 tick 不计入分母；缺读数 → UNAVAILABLE |
| `map20.flow_conservation_violations` | guardrail | `count(FLOW_CONSERVATION_VIOLATION)`（含源/支管/区阀/相向旁路整帧拒绝） | 次 / 低 | episode | 0 合法 |
| `map20.key_node_runaway` | diagnostic | `1[任一关键节点 > 硬上限 10.0]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |

实现状态：**未实现**（`implemented=False`）。`safe_node_ticks` 的“有效 tick”指已结算的安全 tick；熔断 tick 本身是否计分母需在运行时冻结（当前设计按“该 tick 不计产能、温度仍记录”处理）。精确温度口径同 `V7-DCR-010`：Agent 只看带，指标允许用裁判侧精确值并须标注。

## 4. 能力混淆分析

- 高 `safe_node_ticks` 可能来自“全程降载/停机”：温度低但产能不足；必须与产能并列判定成功。
- 低 `max_node_exceedance` 在熔断局可能只因为“很早就失败、只累计了 2 tick”；必须与 `key_node_runaway` 和发生 tick 一起报。
- `flow_conservation_violations=0` 只说明流量账合法，不说明分配好：F01 的 `[2,2,2]` 无旁路完全合法，仍在 tick1 过热。
- 两条成功策略产能 56 vs 59、旁路损失 0.4 vs 0.8；差异是“多产 3 点换双倍旁路损耗”，不能压成单一效率分。

## 5. 两条手算轨迹

**A 区优先保护（产能 56）**：tick0/1 直供 `[2,2,2]`，开 B→A 旁路 1 单位，负荷 `[满,降,满]`；到区水 `[2.8,1,2]`，温度 `[7,6,5]→[8.2,7,5]→[9.4,8,5]`；tick2 起关旁路、直供 `[2,2,1]`、三区降载，温度保持。指标：`max_node_exceedance = 0`（峰 9.4 < 10）；`safe_node_ticks = 30/30`；流量违例 0；失控 0；产能 56。

**动态轮换负荷（产能 59）**：满载按 `C→A→B→A→C→B→C` 轮换，A 满载时从 B 转水、B 满载时从 C 转水、C 满载时直供；tick6/8/9 三区降载。指标：`max_node_exceedance = 0`（峰 9.4）；`safe_node_ticks = 30/30`；流量违例 0；失控 0；产能 59、旁路损失 0.8。

> 两点互不支配：动态表多 3 点产能，但多耗 5 单位直供水、旁路损失翻倍。设计给出线性松弛上界 `P ≤ 72`（`Σ(10−初温)=12`，水源 `6×10=60`），**不是整数最优证明**。

## 6. 三个机制特有失败

1. **F01 忽略支管上限**：三区满载、无旁路直供 `[2,2,2]`，A 在 tick1 升到 11.0 → `THERMAL_OVERHEAT`。流量账合法，热账失败。
2. **F02 超源预算**：tick0 直供 7 单位，整帧 `FLOW_CONSERVATION_VIOLATION` 拒绝且时钟不动。这不是“浪费一 tick”，而是完全没有推进。
3. **F03 把旁路当无损**：每 tick 认 B→A 无损、A 满载、B/C 降载，实际 A 依次 8.2、9.4、10.6，tick2 过热。旁路损耗是 20%，不是 0。

## 7. 两个边界

- **源水恰 6 单位可接受（B01）**：`60` 刻度是包含端点，不是“必须小于”。同理支管恰 25 刻度合法。
- **区阀 3.2 > 3（B03）**：源预算合法但 C 收水 3.2 超区阀 3，整帧原子失败；不得部分放行。另 B02 用三区降载 3 tick 后停机，产能恰好 15 仍成功，验证 `>=15` 的包含端点。

## 8. 信息泄漏负例

若 Observation 给出未来温度、最优直供/旁路向量或“应该给哪个区多供水”，跨 tick 分配被替代。V7 只允许公开热负荷规则、源/支管/区阀限制、当前温度带、当 tick 操作账与累计产能，以及 Agent 自己读到的当前精确温度和差分；`hand_traces.json`、`failure_traces/` 与松弛上界只在离线裁判侧。

## 9. Oracle/求解状态

`planning/hand_traces.json` 有两条手写安全策略（56/59）与逐 tick 流量账；`failure_traces/cases.yaml` 有 F01–F03；设计还给出 `P ≤ 72` 的线性松弛上界（明确不是最优证明）。**没有运行时、没有独立整数求解器、没有真实模型结果**；纸面回放只证明两条策略在方程下可复现。

## 10. 与同世界另两图差异

**vs MAP-19**：MAP-19 是三片**独立**回路共享一个总阀预算，命令有 2 tick 延迟，无旁路；MAP-20 是**互联**管网，水可在区之间转移且损失 20%，控制无延迟。MAP-19 的核心是时间因果，MAP-20 的核心是空间分配与损耗。

**vs MAP-21**：MAP-21 是不确定性下的风险决策（隐藏时限、撤离），MAP-20 完全确定、无随机事件，也没有“是否冒险”的选择；MAP-20 的失败是流量/热账越界，MAP-21 的失败是错过撤离窗口或虚假安全承诺。

## 11. 可计算性来源

需要的字段：每 tick 三区精确温度（或裁判侧精确值）、各支管直供刻度、旁路方向/输入刻度、区阀接收量、负荷档、产能、`terminal_reason`。`max_node_exceedance` 与 `safe_node_ticks` 由逐 tick 温度矩阵直接算；`flow_conservation_violations` 从 `set_supply`/`set_bypass` 的拒绝结果计数；`key_node_runaway` 由终局/温度矩阵判定。全部无需隐藏真值，但需保留被拒帧的操作账。

## 12. 难度定位与对照

D=(1,2,0,3,1,2)。相对 MAP-19 提升 **D↑（两阶段分配：直供→旁路→负荷）与 R↑（源/支管/区阀/旁路损耗四重约束）**；E 保持 0（无时滞、无随机），V 保持 1（精确温度需主动读取）。不会与 MAP-19 混淆：MAP-19 的指标是超阈面积与振荡，MAP-20 的指标是节点越限量与安全节点·tick，且 MAP-20 没有延迟队列。

预登记对照：**旁路可用 vs 旁路禁用（仅直供）**。若禁用后成功率显著下降，说明构念确实依赖跨区转移而非单纯负荷调节；两组共享水源、支管、初温与产能阈值。另需 **精确读数 vs 仅温度带** 的信息条件，避免把“读数能力”当成“分配能力”。

## 13. 未决

- 设计文档写“总产能至少 15 才成功”，而 `map_spec` 的成功谓词需在接入时逐字核对（`PRODUCTION_BELOW_20` 的命名与 15 不一致，属命名遗留）。卡片以 15 为准并标注冲突。
- `source-audit.md` 的机制摘要写旁路“10% 损耗”，而 `DESIGN.md` 与 `map_spec.yaml` 均写 **20%**（下游收 4/5）。本卡按 20% 计算；接入前必须确认哪一处是权威，避免所有流量账偏差。
- `safe_node_ticks` 的熔断 tick 是否进分母未冻结；两种口径会在失败局产生 1 tick 差异，接入前必须固定。
- 精确温度在私有字段（`V7-DCR-010`）；指标口径需声明“裁判精确值”还是“带下界”。
- 无运行时、无真实模型结果；所有数值为纸面/离线审计值。状态 `human_approved`。
