# MAP-24｜丛林｜困难｜消失的道路

```yaml
map_id: MAP-24
world: jungle
nominal_level: 困难
capability_primary: stale_map_replanning
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: eacb2d29835b0bd0c0ee95c25f5b77ae40315b5d51bda7bf10c5bc276b1d32e6
source_design_hash: 2c788c3f6b491c3ade654cb5bd02c4d591c7d2a1521924b04e5bbffd741cf15f
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“过期地图的在线改路”。出发时 `A-B-C` 桥环可通，tick8 后桥永久消失；`D-E` 潮道每 4 拍开 2 拍，且开窗相位是 seed 私有（seed0 偏移 0）；`A-F-C` 山路始终可走但更慢。Agent 必须把 C 遗迹与 D 河岸两件物资都带回 A，且不晚于 tick24。核心不是“找一条路”，而是**当笔记与世界不一致时，是否愿意承认旧笔记过期并改走更慢的可行路**。

## 2. 真实规则字段

- 图：6 节点、7 条双向边；`A-B-C` 桥环、`D-E` 潮道、`A-F-C` 山路（每段 2 拍）。
- 桥：tick8 事件结算后永久移除 `A-B`、`B-C`；事件在该 tick 动作完成**之后**结算，所以 tick7 发起的 1 拍移动可以完成。
- B 节点保留；若事件结算时 Agent 在 B，B 无出口 → `STRANDED_ON_BRIDGE`。
- 潮道：1 拍可过，周期 4、连续开 2；`(出发tick + 相位) mod 4 ∈ {0,1}`，seed0 相位 0；关闭时过道仍耗 1 拍并 `MOVE_FAILED_EDGE_CLOSED`。
- 测水：仅 D/E 可用，1 拍，返回本站开/闭读数，不含未来窗口表。
- `record_route`：1 拍，只把**动作开始时本站可见邻边**抄进 Agent 笔记；不探测远方，笔记不自动更新。
- 观察：只在当前位置给邻边状态；远处桥的变化不会全局推送。
- 交付：两件物资（C、D）都到 A；tick24 到达仍算成功，tick25 超时。
- 失败：`STRANDED_ON_BRIDGE`、`MOVE_FAILED_EDGE_CLOSED`、`DEADLINE_MISSED`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map24.replanning_latency` | primary | 首个改路移动的**发起 tick** − 坍塌公开 tick(8) | tick / 低 | 坍塌实际发生且发生改路 | 坍塌不公开 / 无需改路 → N/A；截尾 → CENSORED |
| `map24.route_cost_ratio` | primary | 首次本地观察断边后的实际剩余成本（含失败尝试）/ 同点最短可行成本 | 比值 ≥1 / 低 | 坍塌后最短可行成本 | 未观察断边 / 已交付 → N/A |
| `map24.collapsed_edge_attempts` | guardrail | `count(move onto collapsed edge)` | 次 / 低 | episode | 0 合法 |
| `map24.rescue_failure` | diagnostic | `1[终局时两件物资未到 A]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |

实现状态：**未实现**（`implemented=False`）。`route_cost_ratio` 的“同点”指 Agent **首次本地看到断边**的位置与 tick；分母用当前已知封闭 + 当前潮窗约束下的最短路。`replanning_latency` 用动作**发起** tick 而非到达 tick，避免把路段长度混入反应时间。

## 4. 能力混淆分析

- 低延迟可能只是“恰好走在山路上、根本不需要改路”：山路策略在 tick8 时身处 D，桥坍塌与它无关，此时 latency 应为 **N/A**，不是 0。
- `route_cost_ratio=1.0` 可能只因为“断边就在终点旁”：必须同时报 `collapsed_edge_attempts` 与交付 tick。
- 零 `collapsed_edge_attempts` 不代表没有过时笔记：Agent 可能只是**没走到**那条边；要结合 `record_route` 的写入内容与观察时序。
- 交付早可能靠“放弃 D 物资”：`rescue_failure` 与交付 tick 必须一起看，不能只报“按时到 A”。

## 5. 两条手算轨迹

**A. 探桥后更新路线（tick14 交付）**：`A→B`(1)，在 B 探桥 2 拍并把当时仍通的桥边写进笔记（3），经 C 取 C 物资、`C→D` 取 D 物资；桥在 Agent 位于 D 时于 tick8 消失；`D→C` 后 tick9 在 C 观察本地断边，覆盖旧笔记，再 `C→F→A`，tick14 交付。指标：`replanning_latency = 10 − 8 = 2`（tick9 观察 + 1 拍 record_route，tick10 发起 C→F）；`route_cost_ratio = 4/4 = 1.0`；`collapsed_edge_attempts=0`；`rescue_failure=0`。

**B. 过时笔记恢复对照（tick15 交付）**：复用 A 的前缀，tick9 的 C 仍按旧笔记尝试 `C→B`，失败耗 1 拍；随后读取当前本地断边、覆盖笔记、走 F 返营。指标：`replanning_latency = 11 − 8 = 3`（错走 + 覆盖 + 再移动）；`route_cost_ratio = (1+4)/4 = 1.25`；`collapsed_edge_attempts=1`；`rescue_failure=0`。

> 两条轨迹只差“是否先信旧笔记”：交付差 1 tick、成本比 1.0 vs 1.25、断边尝试 0 vs 1。设计明确把“正常更新=2、过时恢复=3”作为可见代价。

## 6. 三个机制特有失败

1. **F01 桥上记路被隔断**：带着两件物资由 C 跨到 B，在 B 做 1 拍 `record_route`，动作完成到 tick8 桥坍塌，`A-B`、`B-C` 都被移除，B 无出口 → `STRANDED_ON_BRIDGE`。正确选择是 tick7 从 B 继续往 A 离开。
2. **F02 旧图拒绝更新**：从 D 返回 C 后 tick9 已看到 `B-C` 断，仍反复尝试 C→B 直到越过 tick24；每次 1 拍，约 16 次无效移动，最终带两件物资仍在 C 超时。
3. **F03 把测水当等待**：取完两件物资后从 tick7 起连续测水 18 次，不据读数决定过道或回路；最后一次测量推进到 tick25，物资仍在 D，超时。测水是**决策输入**，不是消磨时间的安全动作。

## 7. 两个边界

- **tick24 成功 vs tick25 失败**：deadline 包含端点；`route_cost_ratio` 的分母也必须按“能在 24 前完成”的可行路计算，否则会出现 <1 的荒谬值。
- **tick7 出发 vs tick8 出发（B-A / B-C）**：tick7 发起的 1 拍移动在事件结算前完成，安全；tick7 从 B 出发到 C、tick8 抵达则事件已结算，可能被孤立。事件序“先完成再坍塌”是硬边界。

## 8. 信息泄漏负例

若 Observation 或 prompt 给出 `bridge_collapse_tick`、潮位相位偏移、全局未来事件表或“下一条安全路线”，过期地图题被替代。V7 只允许公开当前邻边状态、自己测得的潮位读数、自己写的笔记、已走 tick 与交付状态；`private_seed_reference`、Oracle、事件表只在离线侧。远处桥的变化也不得被全局推送。

## 9. Oracle/求解状态

`planning/hand_traces.json` 有四条手写策略（桥环抢运 7 tick、探桥更新 14、山路+潮窗 11、过时笔记恢复 15），`failure_traces/cases.yaml` 有 F01–F03；离线审计核对桥事件/潮窗相位/交付 tick。**没有运行时、没有独立最优求解器、没有真实模型实验**；手算只证明四条策略在 seed0 上可行，不证明全图最优。

## 10. 与同世界另两图差异

**vs MAP-22**：MAP-22 的图**永远不变**，难度来自局部观测；MAP-24 的图会在 tick8 改变，难度来自“世界与笔记不一致”。MAP-22 的指标是返程成功/路径差，MAP-24 是改路延迟/成本比。

**vs MAP-23**：MAP-23 的路网已知、不确定性在“哪个入口为真”，核心是信息值 vs 补给；MAP-24 的入口/目标全已知，不确定性在“路是否还在”，核心是过期事实的更新。两者都需要“信息→行动”，但 MAP-23 买信息，MAP-24 修正信息。

## 11. 可计算性来源

需要的字段：`location`、当前可见邻边状态、`recorded_route_notes`（含写入 tick）、`tide_readings`、`carried_items`、`tick`、`terminal_reason`，以及每次 `move` 的目标与结果码。`replanning_latency` 用首次 `collapse` 公开后的首个“目标边不在封闭集”的 `move` 的发起 tick；`route_cost_ratio` 用首次观察到封闭边的 tick 起算剩余动作成本（失败移动也计 1）；`collapsed_edge_attempts` 从 `MOVE_FAILED_EDGE_CLOSED` 或“目标为已封闭边”计。

## 12. 难度定位与对照

D=(2,3,3,2,2,3)。相对 MAP-23 提升 **D↑（多阶段：取两件物资 + 返程改路）与 E↑（桥坍塌事件 + 潮窗周期）**；R 保持 2（时间/潮窗而非多资源）。不会与 MAP-23 混淆：MAP-23 没有事件改变拓扑，MAP-24 没有补给经济。

预登记对照：**桥坍塌预告 vs 无预告**。若预告组 latency 显著更低，说明构念确实测“在线更新”而非“预先规划”；两组共享拓扑、tick8 坍塌、潮窗与 deadline。另需 **笔记可用 vs 禁用** 对照，区分“记忆过期”与“无记忆”。

## 13. 未决

- `route_cost_ratio` 的分母依赖“当前潮窗约束下的最短路”，但潮窗相位是 seed 私有；运行时必须用**公开读数 + 已知周期**推导可行路，不能用私有相位。
- `replanning_latency` 在“无需改路”的轨迹（山路策略）应为 N/A，需要一个专门用例固化，避免被误算成 0。
- 设计文档中“过时笔记恢复”与“正常更新”的动作序号差（2 vs 3）已给出，但未注册为独立 metric；V7 不新增，避免与 latency 重复计数。
- 无运行时、无真实模型结果；所有数值为纸面/离线审计值。状态 `pending_human_review`。
