# MAP-19｜火山｜简单｜温度临界点

```yaml
map_id: MAP-19
world: volcano
nominal_level: 简单
capability_primary: delayed_control_thermal_margin
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 50ee8a132fc079b1f8f09cba0b508a901d5a948078af5f0b1ca72dcdcfc94bf1
source_design_hash: 9883b7e893339d853261dc664c61ccb27b86296927962e129084e2d5d65e3b43
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“两 tick 控制延迟下的热余量管理”。三个热交换区 `HX_A/HX_B/HX_C` 起温 `6/5/4`、安全上限 10；冷却阀命令在提交后 **tick+2 才生效**，而 `wait` 立即结算本 tick 热量。Agent 必须提前两 tick 预判温度、在“总阀量 ≤ 4”的预算内分配冷却，并用负荷档位换产能（负荷同时是热源与产能点）。核心不是“把温度压到最低”，而是在延迟因果下维持 12 tick 安全且产能 ≥ 20。

## 2. 真实规则字段

- 拓扑：`C_CTRL` 分别直连 `HX_A/HX_B/HX_C` 与冷却站 `P`；热区之间无传导，故障不传播。
- seed0 起温 `A=6, B=5, C=4`；初始负荷均为 2；当前有效冷却均为 0。
- 转移：`next_T = max(0, T + load - active_cooling)`；三区同步求值。
- 阀：每区 0–2，**总和 ≤ 4**；`set_cooling(A,B,C)` 在 tick+2 生效并保持到被新命令替换；超预算**整条向量原子拒绝**。
- 负荷：0 停机 / 1 降载 / 2 满载；`adjust_loads` 立即生效；负荷值即本 tick 产能点（仅当三区均安全时计入）。
- 动作：`read_temperature(zone)` 每 tick 每区最多一次、零时间，返回当前值与上一 tick 差分；`forecast_next` 提交下一 tick 三区预测；`wait` 推进结算。
- 终止：任一区 `next_T > 10` 立即 `THERMAL_RUNAWAY`（该 tick 不计产能）；温度恰为 10 安全；tick0–11 走完后产能 `< 20` → `PRODUCTION_BELOW_20`。
- 公开：温度带、当前有效阀量、已排队命令与到期 tick、当前负荷、已有产能；**不公开**未来温度与裁判 Forecast。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map19.temperature_exceedance_area` | primary | Σ 区 Σ_tick `max(0, T − T_safe) × Δt`，`T_safe = 8` | °C·tick / 低 | 有效 tick 数 | 缺精确温度 → UNAVAILABLE；截尾只累计已结算 tick 并标 CENSORED |
| `map19.oscillation_count` | primary | 带内 `dT/dt` 符号变化次数（三区合计，0 值不计） | 次 / 低 | episode | 无变化 → 0（合法） |
| `map19.critical_overheat_ticks` | guardrail | `count(T > 10)` 的区·tick 数 | 区·tick / 低 | episode | 0 合法；熔断后不再累计 |
| `map19.coolant_exhausted` | diagnostic | `1[terminal_reason==COOLANT_EXHAUSTED]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |

实现状态：**未实现**（`implemented=False`），`compute_metrics("MAP-19", ...)` 抛 `NotImplementedError`。精确温度口径见 `V7-DCR-010`：Agent 只看温度带，指标计算允许使用裁判侧精确值，但必须在报告中标注；若只能从 `read_temperature` 的重放取精确值，则未读 tick 用带下界，此时该 metric 标 `UNAVAILABLE` 而非补 0。

## 4. 能力混淆分析

- 低超阈面积可能来自“全程停机”：负荷 0 时温度下降，产能也归零；必须与产能/成功谓词并列。
- 低振荡可能只是“从不调整阀”：命令一直不变时 `dT/dt` 恒定，振荡 0；必须同时看是否在 tick0 就设对阀。
- 高产能不能证明热管理好：提前冷却方案产能 48、峰值 10；保守方案产能 30、峰值 6。两者都成功，但“压着上限跑”和“留余量运行”是不同策略，不能合成单一效率分。
- `THERMAL_RUNAWAY` 与 `PRODUCTION_BELOW_20` 是两类失败：前者是安全越界，后者是保守过度；只用成功率会把两种相反的错误混在一起。

## 5. 两条手算轨迹

**提前冷却保产能（产能 48）**：tick0 读 A 得 6，设阀 `[2,1,1]`（总量恰 4）、负荷 `[2,1,1]`；tick1 温度 `[8,6,5]`；tick2 温度 `[10,7,6]`，命令成熟后逐区相抵并保持；tick0–11 产能 48。指标：超阈面积 = A 在 tick2–11 共 10 tick × (10−8) = **20 °C·tick**（tick1 的 8 记 0）；振荡 0；临界过热 0；`coolant_exhausted=0`。

**负荷先收、冷却到位再运行（产能 30）**：tick0 设阀 `[1,1,1]`、负荷 `[0,0,0]`，给执行器留满两 tick；tick2 成熟后负荷改 `[1,1,1]` 降载运行，温度保持 `[6,5,4]`。指标：超阈面积 **0**；振荡 0；临界过热 0；产能 30。该轨迹少用 1 单位冷却、产能更低，但不依赖 A 压上限。

> 两条轨迹都成功且都不振荡，差异只在“峰值余量 vs 产能”。第三份手写表 `[2,0,0]` 冷却只给 A、满载十 tick 后停机，产能恰好 20、峰值 10，用于验证 `>= 20` 的包含端点。

## 6. 三个机制特有失败

1. **F01 迟设阀**：tick1 才设 `[2,1,1]`，命令 tick3 才生效；A 于 tick2 从 10 升至 12，`THERMAL_RUNAWAY`。同 tick 生效假设会直接漏掉这类失败。
2. **F02 冷却量不足**：tick0 给 `[1,1,1]` 却让 A 满载 2；t2 首个冷却 tick 仍使 A 10→11。有冷却 ≠ 冷却足够。
3. **F03 阀预算与负荷失配**：`[2,1,1]` 本身合法，但让 B 也满载 2；B 在 tick2 恰好 10，tick3 升到 11。总量合法不等于分区配平。

## 7. 两个边界

- **恰为 10 安全 vs 11 熔断**：B01 与 F02/F03 共用同一方程，只差 1°C；`critical_overheat_ticks` 必须按 `> 10` 严格判定，不能把 10 计入。
- **产能恰 20 成功 vs 19 失败**：B02 的 `[2,0,0]` 表恰好 20，验证 `>=`；`PRODUCTION_BELOW_20` 只在 `<20` 触发。此外 `[2,1,2]` 总量 5 被整体拒绝（B03），不得出现“部分排阀”。

## 8. 信息泄漏负例

若 Observation 直接给未来温度、下一 tick 的最优阀向量或裁判 Forecast，两 tick 因果被消除。V7 只允许公开温度带、当前有效阀量、排队命令与到期 tick、当前负荷、已有产能，以及 Agent 自己 `read_temperature` 取得的当前精确值与差分；`planning/hand_traces.json`、Oracle 与裁判 MAE 只在离线侧。

## 9. Oracle/求解状态

`planning/hand_traces.json` 有三份手写表（提前冷却 48、保守 30、恰好 20）与逐 tick 读数、Forecast；专属纸面回放器复核温度账、产能账与失败原因。**没有运行时、没有独立最优求解器、没有真实模型实验**；审计证明三份表在方程下自洽，不证明它们是全局最优控制。

## 10. 与同世界另两图差异

**vs MAP-20**：MAP-20 是多节点冷却分配 + 单回路时滞，资源在节点间争用、需要跨节点调度；MAP-19 是三片**互不传导**的独立回路，共享的只有总阀量 4。MAP-19 的失败是单区越界，MAP-20 的失败可以来自分配顺序。

**vs MAP-21**：MAP-21 有隐藏时限与风险决策（喷发窗口、撤离），核心是不确定性下的取舍；MAP-19 完全确定、无随机事件，核心是固定两 tick 延迟下的前馈控制。MAP-19 没有任何“是否冒险”的选择。

## 11. 可计算性来源

需要的公开/trace 字段：每 tick 的三区温度读数（或裁判侧精确温度）、有效阀量、排队命令与到期 tick、负荷、产能、`terminal_reason`。超阈面积按区按 tick 累加；振荡由连续 `dT` 符号变化计数；临界过热按 `>10` 计；`coolant_exhausted` 目前只在设计失败码中出现，运行时需确认该原因码是否真实存在（否则恒为 0，须标 `UNAVAILABLE` 而不是假 0）。

## 12. 难度定位与对照

D=(1,1,1,2,1,1)。本世界基线：单回路时滞 + 单一共享资源（总阀量）。V=1（精确温度需主动读取）、E=1（固定周期延迟）、B=1（无分支策略）。

预登记对照：**显式两 tick 延迟提示 vs 只给“命令将稍后生效”**。两组温度方程、初温、阀预算与负荷完全相同；若弱提示组把命令当同 tick 生效，应归因为因果模型缺失，而不是“控制能力差”。另需一条 `read_temperature` 预算对照（每 tick 每区读 vs 不读），确认精确读数是否实质改变策略。

## 13. 未决

- `V7-DCR-010`：精确温度在私有字段，超阈面积存在“裁判精确值”与“带下界”两种口径，运行时 extractor 必须声明使用哪一种。
- `COOLANT_EXHAUSTED` 在 `map_spec` 失败码中存在，但设计文档未给出触发条件（总阀量超预算只是整条拒绝）；接入前需确认该码是否可达，否则 `map19.coolant_exhausted` 恒 0，应改报 `UNAVAILABLE`。
- 无运行时、无真实模型结果；所有数值为纸面回放值。状态 `pending_human_review`。
