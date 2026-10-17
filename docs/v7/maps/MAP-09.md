# MAP-09｜深海｜困难｜深海连锁故障

```yaml
map_id: MAP-09
world: deep_sea
nominal_level: 困难
capability_primary: cross_system_causal_control
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 1ebe942cc5423c031c5c65b32b6efb48c7c5b1a1d0069031c3e737cd5c35d2bf
source_design_hash: 8aafad5f9ed9c5d6191c7835735a2b19c5c9c78c0c841ad391876354af6aa5de
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“多系统耦合下的诊断与稳定控制”。漏水短路、供氧中断、有限电量、通信恢复四条链互相依赖：P-E 水路会把泵房水推向动力舱 E；泵能保住 P 却消耗刚好够发报的电量；弃置 P 则通过 E-C 应急廊更快恢复供氧和通信。正确的“修泵”可能把水推向 E 并短路；正确的“先稳供电/先封舱”可能牺牲非关键舱。成功是供氧恢复且完整求救包发送，不是逐个修好三个按钮。

## 2. 真实规则字段

- 拓扑：`E-P-O-C-E` 主环 + `E-C` 应急廊；各边 1 tick，Agent 从 E 出发。
- 初始：`battery=5, water_P=5, water_E=3, oxygen_reserve=12`；E-P 闸开、发电主线断、供氧机关闭、泵关闭。
- 动作与顺序：控制动作效果在耗时首个 tick 前提交；每 tick 依序：若 E-P 闸开，P→E 流 1；若动作为 `pump_once`，P 抽 2；更新氧储备/稳定；检查短路与氧耗尽。
- `isolate_compartment(P-E, preserve|sacrifice)`：1 tick；`preserve` 可进 P 修泵，`sacrifice` 永久弃置 P（P 水量保留但不可达）；两种都从动作结束 tick 起止漏。
- `pump_once`：1 tick、耗 1 电、`P=max(0,P−2)`；可在 P=0 空转耗电。
- 修复主线：E，1 tick，要求 `water_E<=4`；成功后外部发电机可供氧，但电池不回充。
- 供氧：关闭时氧储备每 tick −1，到 0 失败；主线修好后 O `restart_oxygen`；`replenish_oxygen` 补满 12（需供氧已开）。
- 发报：C；完整包要求供氧稳定计数 ≥2 且电池 ≥3；门槛在调用开始时检查。不足 3 时启动 1 tick 失败校验，之后 `INSUFFICIENT_TRANSMIT_POWER`，不扣电。满足时一次扣 3，连续传输 2 tick，期间保持供氧开启/稳定。
- 成功：`external_generator_online && oxygen_support_on && packet_complete`。硬失败：`water_E>4`、`oxygen_reserve<=0`、发报电量不足。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map09.stable_time_ratio` | primary | 满足 `water_E<=4 && oxygen_reserve>0` 的 tick / 有效 tick | 比例 / 高 | 有效 tick | 无 tick → UNAVAILABLE |
| `map09.fault_propagation_scale` | primary | 首个故障后进入不安全/不可达状态的子系统数（E 短路、氧耗尽、P 弃置） | 个 / 低 | 3 | 无故障 → N/A |
| `map09.hard_threshold_breaches` | guardrail | `1[water_E>4]+1[oxygen<=0]+1[INSUFFICIENT_TRANSMIT_POWER]` | 次 / 低 | episode | 0 合法 |
| `map09.repair_dependency_violations` | diagnostic | 未满足前置的修复/开机/发报尝试次数 | 次 / 低 | episode | 0 合法 |
| `map09.repair_actions` | diagnostic | 修线、开氧、补氧、抽水、封舱动作数 | 次 / 低 | episode | 0 合法 |

## 4. 能力混淆分析

- 高稳定占比可能只因为“一开始就弃舱、走最短路线”，不代表会协调多系统；必须同时报 `fault_propagation_scale` 与是否发送完整包。
- 低稳定占比可能由“弃置 P 后水留在 P”被误判为不安全；P 弃置是有意的代价，不是 E 短路。指标只把 E 水位/氧储备算安全域。
- 电量是精确预算：保泵路线两次抽水耗 2、发报扣 3，5 格刚好耗尽；多抽一次只剩 2，无法发报。不能把“电池还有 2”当成成功。
- 通信恢复需要稳定计数 ≥2；只开机不等待会失败，不能把“供氧开”当“可发报”。

## 5. 两条手算轨迹

**方案 A（保泵，13 tick）**：E `isolate(preserve)`（1）→E→P（2）→`pump_once`（3，P 5→3，电 4）→`pump_once`（4，P 3→1，电 3）→P→E（5）→修主线（6，`water_E<=4`）→E→C 应急廊（7）→C→O（8）→`restart_oxygen`（9）→`replenish_oxygen`（10）→O→C（11）→`send_distress_packet`（12–13，扣 3，稳定计数≥2）。指标：稳定 13/13；传播 0（P 保留）；硬违例 0；修复动作 5；完成 13；电池 5−1−1−3=0。

**方案 B（弃舱，9 tick）**：E `isolate(sacrifice)`（1）→E→C 应急廊（2）→C→O（3）→`restart_oxygen`（4）→`replenish_oxygen`（5）→O→C（6）→`send_distress_packet`（7–8）？按设计结束 tick 9（含发电主线？弃舱后仍需外部发电机；E 主线修复在 E，需先回 E）。实际顺序：E 封舱（1）→修主线（2）→E→C（3）→C→O（4）→开氧（5）→补氧（6）→O→C（7）→发报（8–9）。指标：稳定 9/9；传播 1（P 弃置）；硬违例 0；修复动作 3；完成 9；电池 5−3=2。

> 两条轨迹都成功，但 B 少 4 tick、保留 2 电，代价是 P 永久损失；A 保留 P 但电池耗尽。指标必须同时呈现“完成时间/电量/传播规模”，不能只按 tick 排序。

## 6. 三个机制特有失败

1. **漏闸持续两 tick**：E-P 闸未封，P→E 使 `water_E` 从 3 涨到 5，短路失败；这是“先修泵不封舱”的级联。
2. **多抽一次泵**：保泵路线抽 3 次，电从 3 降到 2；到 C 发报时门槛不足，`INSUFFICIENT_TRANSMIT_POWER`；不是氧或水失败。
3. **弃舱后不开氧**：P 已弃置但供氧机一直关闭，氧储备在 tick 12 归零，`OXYGEN_DEPLETED`；弃舱本身不是失败，忘记恢复生命支持才是。

## 7. 两个边界

- **water_E=4 vs 5**：`=4` 安全，`=5` 立即短路；必须用同一封舱时点只改一个等待 tick 验证。
- **电池 3 vs 2**：`=3` 可启动发报并扣到 0；`=2` 触发 1 tick 失败校验后终止。两者只差一次抽水，必须分开归因。

## 8. 信息泄漏负例

若 prompt 直接建议“弃置 P 更快”或公开故障因果链/最优隔离模式，跨系统权衡被替代。V7 只允许公开当前水位、电池、氧储备、供氧状态与通信状态；`preserve/sacrifice` 的后果必须由 Agent 从规则推导。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `preserve_and_pump`（13 tick）与 `sacrifice`（9 tick）两条手写成功；`failure_traces/cases.yaml` 有三条动作级失败；`acceptance.md` 只完成纸面推演。**没有运行时或独立求解器**证明 9 tick 最优；两条轨迹只证明多策略可行。

## 10. 与同世界另两图差异

**vs MAP-07**：MAP-07 只有单一流体网络的顺序转移，所有水位可见，动作直接改变水量；MAP-09 有四条跨系统链（漏水→短路、泵→电量、断电→氧储备、供氧稳定→通信），局部修复可能诱发另一系统故障。MAP-07 的失败是舱室溢流，MAP-09 是短路/氧耗尽/发报电量不足；两者的状态变量与资源循环不同。

**vs MAP-08**：MAP-08 是隐藏漏点的主动诊断，动作改变假设集合；MAP-09 的故障位置与水位公开，难点是跨系统耦合与资源预算。MAP-08 的主指标是诊断准确率/信息增益，MAP-09 是稳定时间占比/传播规模；把 MAP-09 的故障藏起来会变成另一张诊断图，而不是同一机制。

## 11. 可计算性来源

需要逐 tick 的 `battery`、`water_P`、`water_E`、`bulkhead_state`、`p_sacrificed`、`oxygen_reserve`、`oxygen_support_on`、`oxygen_stable_ticks`、`packet_complete`、`terminal_reason`。`fault_propagation_scale` 需要只读事件“子系统进入不安全态”；当前只能从公开状态近似（`V7-DCR-006`）。

## 12. 难度定位与对照

D=(2,3,3,3,2,3)。相对 MAP-08 提升 D（跨系统依赖）、E（级联事件）与 R（电池/氧/水耦合）。预登记对照：**完整耦合图 vs 局部仪表图**；两者共享初态、动作与预算。若耦合图额外给 preserve/sacrifice 的建议，标为信息可用性实验。

## 13. 未决

故障传播规模需要新增只读 instrumentation（`V7-DCR-006`）；当前公式只用公开状态近似。运行时接入前需固定“控制效果先于流水/氧更新”的结算顺序。
