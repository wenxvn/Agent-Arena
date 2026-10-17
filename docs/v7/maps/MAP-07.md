# MAP-07｜深海｜简单｜逆流阀门

```yaml
map_id: MAP-07
world: deep_sea
nominal_level: 简单
capability_primary: causal_consequence_prediction
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: b7b9c6716d57f34ebb5e1512465290a308b1cf14892ec807b0369eb04842105d
source_design_hash: f2ec9e0092d138bc8252090f153db9ea992775cf1ca5599de5ecd57f35ef5086
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“对串接阀门联合影响的因果方向推理”。水路不是 Agent 的行走图：整个任务在控制台 P 远程完成。`v1 A→B`、`v2 B→C`、`v3 C→D`、`v4 C→A` 在同一 tick 内按**固定顺序**结算，水可以在一 tick 内经过多个依次开放的阀；`v4` 是单向回流而不是泄压口。局部“给本舱降压”可能把水推向远端并造成远端升压。成功要求 A/B/C 连续两个流水 tick 都 `≤2`，且全程没有舱室 `>8`。

## 2. 真实规则字段

- 初始：`A=6, B=2, C=4, D=0`；溢流阈值 8（等于 8 安全，`>8` 失败）；四阀全闭、泵关闭。
- 每 tick 顺序：`v1` 至多 2 → `v2` 至多 2（可收到同 tick 前一步流入 B 的水）→ `v3` 至多 2 → `v4` 至多 1 → 泵从 D 排至多 2（耗 2 功率）。每步按可用水量转移，不产生负水位。
- 动作：`inspect(water_levels)`、`inspect(pipe_diagram)`、`interact(control_panel, ...)`、`wait`；均耗 1 tick 并触发一轮流水。
- 预测动作：`interact(control_panel, predict_next_levels, {A,B,C,D})` 耗 1 tick，裁判对提交值与真实结算值计算绝对误差；**不是成功条件**，不读取 `note` 或思维链。
- 成功：A/B/C 连续两次流水均 `≤2`。没有全局倒计时。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map07.excess_water_integral` | primary | `Σ_t Σ_{c∈{A,B,C}} max(0, level_c,t − 2)` | 水位·tick / 低 | 有效流水 tick | 无读数 → UNAVAILABLE |
| `map07.correct_direction_rate` | primary | 使 A/B/C 总超额水量下降（或保持 0）的阀门操作数 / 可判定阀门操作数 | 比例 / 高 | 可判定阀门操作数 | 0 次 → N/A |
| `map07.overpressure_ticks` | guardrail | 任一舱 `>8` 的 tick 数 | tick / 低 | episode | 0 合法 |
| `map07.illegal_valve_combo` | diagnostic | `count(INVALID_VALVE / INVALID_CONTROL)` | 次 / 低 | episode | 0 合法 |
| `map07.interventions` | diagnostic | 阀门开/关 + 泵启停的动作数 | 次 / 低 | episode | 0 合法 |

`excess_water_integral` 把“成功带上限 2”作为目标水位，只惩罚高于 2 的水量；低于 2 不罚，因为过度排水无害。这是对提纲“目标流量偏差”的保守实现：本图没有独立目标流量曲线，只有低水成功带。

## 4. 能力混淆分析

- 低 `excess_water_integral` 可能只因为“先开所有阀”碰巧排空，不代表理解顺序；必须与 `overpressure_ticks` 和失败轨迹一起看。
- 高 `correct_direction_rate` 可能只做了一步正确操作就停；分母是“可判定阀门操作”，必须报操作次数。
- 低分可能由“泵耗电/功率”误解造成，但本图没有总电量上限；泵只耗 2 功率/tick，不影响成功。不要把能耗当失败原因。
- 关闭 `v2` 而开 `v1/v4` 会让 B 升到 10；这是“局部降压、远端升压”的核心反例，不能被平均水位掩盖。

## 5. 两条手算轨迹

**策略 A（先排下游，泵全程运行，6 tick）**：启动泵（1）→开 `v3`（2）→开 `v2`（3）→开 `v1`（4）→等待（5）→等待（6，连续低水窗口 tick5–6 成立）。指标：C 峰值 4（初始值，未升）；泵运行 6 tick = 12 功率；成功 6 tick；`interventions`=4（泵 + 3 阀）；`overpressure_ticks`=0。

**策略 B（上游暂存，再启泵，8 tick）**：开 `v1`（1）→开 `v2`（2）→开 `v3`（3）→启动泵（4）→等待 4 tick（5–8，低水窗口 tick7–8 成立）。指标：C 峰值 6（仍 <8）；泵运行 5 tick = 10 功率；成功 8 tick；`interventions`=4；`overpressure_ticks`=0。A 比 B 快 2 tick 但多耗 2 功率；B 的 C 峰值更高，两者在“时间/能耗/峰值”上可比较。

## 6. 三个机制特有失败

1. **只开 v4 回流**：A 被回流推到 9，`>8`，A 溢流；证明 v4 不是泄压口。
2. **开 v1/v2 但忘记 v3**：水从 A→B→C 累积，C 升到 10，C 溢流；这是“下游出口未开”的因果错误。
3. **开 v1/v4 但关闭 v2**：B 只进不出，升到 10；这是“跳过中间舱”的因果错误。

## 7. 两个边界

- **水位 8 vs 9**：`=8` 安全，`=9` 立即失败；必须用同一动作序列只改一个初始水量或等待 tick 验证。
- **低水窗口 1 vs 2 tick**：只达到一次 `≤2` 不算成功；下一次流水若任一舱回到 3，稳定计数清零。边界用于验证“连续两次”而非累计。

## 8. 信息泄漏负例

若 prompt 给出“先 v3 再 v2 再 v1”的推荐顺序，或 Observation 直接给下一步最优阀组合，因果推理被替代。V7 只允许公开当前水位、阀态、泵态与管线图；不公开预测答案或最优序列。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `downstream_first`（6 tick）与上游暂存（8 tick）两条手写成功；`failure_traces/cases.yaml` 有三条溢流失败（分别锁 A/C/B）。**没有运行时或独立求解器**证明 6 tick 最优；只能证明两策略可行且非支配。

## 10. 与同世界另两图差异

**vs MAP-08**：MAP-08 的隐藏漏点需要主动测试来缩小候选集，动作改变的是“假设集合”；MAP-07 的水位完全可见，动作直接改变物理水量，失败由溢流阈值触发。MAP-08 的核心指标是诊断准确率与信息增益，MAP-07 是超额水量与因果方向率；把 MAP-07 的漏点藏起来会变成另一张图，而不是同一机制。

**vs MAP-09**：MAP-09 是电力、泵、氧气、通信的跨系统耦合，局部修复可能诱发级联；MAP-07 只有单一流体网络内部的顺序转移，没有氧气/电池/通信预算。MAP-09 的失败是短路、氧耗尽或发报电量不足，MAP-07 的失败是舱室溢流；两者不共享资源循环。

## 11. 可计算性来源

需要逐 tick 的 `A/B/C/D` 水位、四阀状态、泵状态、`terminal_reason`，以及 `predict_next_levels` 的提交值与裁判真值（仅离线）。`excess_water_integral` 与 `correct_direction_rate` 都可用公开水位序列复算；预测误差只在裁判侧。

## 12. 难度定位与对照

D=(1,1,1,2,1,2)。以因果方向为主，低于 MAP-09 的多故障耦合。预登记对照：**因果管线图 vs 仅公开仪表读数**；不披露最佳阀门序列。若管线图额外给顺序，标为信息可用性实验。

## 13. 未决

无规则冲突。运行时接入前需固定“同 tick 级联顺序”与“低水连续计数”的结算点，并确认预测动作不改变胜利谓词。
