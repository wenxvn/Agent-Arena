# MAP-01｜飞船｜简单｜破损的曙光号

```yaml
map_id: MAP-01
world: spaceship
nominal_level: 简单
capability_primary: dependency_planning
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 6fa24c7950f14e8086db97b5a877ba61b7bd88c876c54162a95e8b73c48fe3b3
source_design_hash: 66da1da5ed6fb68209860209c6520fa3539edbeadb5b029608e717dace1f6ee6
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“前置依赖 + 总负荷上限下的互斥供电”。供氧连续性与维修臂争用同一电池（基础负荷 3 + 支路 2 + 支路 2 > 容量 6），因此**先修补后供氧不可交换**；船壳完整后才开放 `W-P` 服务边，主电源复位又必须在船壳完整之后。成功不是“拿齐三件物品”，而是按安全顺序完成生命支持、修补、复位、气闸检查与舰桥确认。

## 2. 真实规则字段

- 初始：`location=B, oxygen_reserve=18, oxygen_output=off, oxygen_off_ticks=0, battery_load_limit=6, fixed_load=3, routed_branch=none, hull_intact=false, main_bus=off, airlock_sealed=true, pressure_test=not_done, patch_at=W`。
- 动作：`move(edge_id)`、`inspect(target_id)`、`pickup(item_id)`、`interact(target_id, choice)`、`wait(1)`、`note(text)`；前五类各耗 1 tick，`note` 不推进时钟且裁判不读。
- 供氧：每 tick 结束若 `oxygen_output=off`，`oxygen_reserve -= 1` 且 `oxygen_off_ticks += 1`；恢复供氧当 tick 先生效再结算，因此可避免最后一次扣减。
- 硬失败：`oxygen_reserve=0`、`oxygen_off_ticks>3`、船壳未完整时复位主电源（`BUS_RESET_WITH_HULL_OPEN`）。
- 成功：`hull_intact && main_bus=on && pressure_test=pass && terminal_confirmed_at_B`。
- 公开字段：位置、相邻边、可见物、氧气余量、供氧输出、已路由支路、船壳、主母线、气闸状态、公开目标。`oxygen_off_ticks` **不在公开字段**，只能由供氧输出序列复算。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map01.dependency_satisfaction_rate` | primary | 按合法先后完成的必需依赖边 / 6 | 比例 / 高 | 6 条必需边 | 无终局 → CENSORED |
| `map01.longest_oxygen_outage_ticks` | primary | 最长连续 `oxygen_output=False` tick | tick / 低 | episode | 无观测 → UNAVAILABLE |
| `map01.oxygen_guardrail_violations` | guardrail | `1[OXYGEN_SUPPLY_INTERRUPTION_LIMIT]+1[OXYGEN_RESERVE_EXHAUSTED]` | 次 / 低 | episode | 终局缺失 → CENSORED |
| `map01.dependency_violations` | diagnostic | 明确尝试违反前置关系的次数（未供氧取片/未持片修补/未修壳复位/双支路超载） | 次 / 低 | episode | 0 合法 |
| `map01.completion_ticks` | diagnostic | 成功终局 tick | tick / 低 | 成功局 | 失败/截尾 → N/A/CENSORED |

必需边（6）：`oxygen_on→patch_pickup`、`patch_hold→route_arm`、`arm_on→hull_patch`、`hull_intact→bus_reset`、`bus_on→pressure_test`、`pressure_test→bridge_confirm`。普通走错路不计依赖违例。

## 4. 能力混淆分析

- 高分可能只反映“会读配电图”，不反映依赖规划；必须同时报告 `dependency_violations` 与断供峰值。
- 低分可能由 `EDGE_LOCKED_HULL_OPEN` 的探索性尝试造成；该尝试不应算依赖违例，但会耗 tick。
- 通关率无法区分“顺序对但绕路”与“顺序错但运气好”：两条手算轨迹可以同通关、不同 `dependency_satisfaction_rate`（见 §5 边界）。
- `note` 不计时、不被裁判读取，不能把“写了很多笔记”当作能力。

## 5. 两条手算轨迹

**成功（Oracle，18 tick）**：B→H 启供氧（断供 0）→H→W 取修补片→本地切维修臂（断供 1）→修船壳→立即回切供氧（断供 2）→经 `W-P` 服务边到 P 复位主母线→H→A 做压力检查→H→B 确认。指标：依赖满足 6/6 = 1.0；最长断供 2 tick；违例 0；完成 18 tick。

**失败（顺序错，断供 4 tick）**：B→H→W 取片→切维修臂（断供 1）→修补船壳（2）→继续检查工具（3）→再切供氧（4）→在动作结算时 `oxygen_off_ticks=4>3`，`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`。指标：依赖满足 3/6 = 0.5；最长断供 4；guardrail 1；完成 tick N/A。

## 6. 三个机制特有失败

1. `EDGE_LOCKED_HULL_OPEN`：船壳未修就走 `W-P`，耗 1 tick 且暴露服务边依赖。
2. `POWER_CAPACITY_CONFLICT`：供氧与维修臂同时接通（3+2+2=7>6），动作被拒但仍耗 tick，可能把断供推过 3。
3. `BUS_RESET_WITH_HULL_OPEN`：修好壳体但未恢复主母线前就复位，立即硬失败；与“氧气耗尽”是不同归因。

## 7. 两个边界

- **断供 3 vs 4**：`oxygen_off_ticks=3` 仍安全（规则是 `>3` 才失败）；第 4 个连续断供 tick 结算即失败。必须用同一动作序列只改一个等待动作来验证分界。
- **修好壳体但未复位动力**：`hull_intact=true` 但 `main_bus=off`，去 B 确认得到 `REPAIR_INCOMPLETE`；依赖满足 4/6，完成 tick N/A。这是“部分完成但不是成功”的边界，不得记满分。

## 8. 信息泄漏负例

若 Observation 公开 `oxygen_off_ticks` 的精确值、或 prompt 提示“先修壳再复位”，Agent 可以直接照做而不需要从供氧输出推断断供风险。V7 只允许公开“当前供氧是否开启”和“余量”，不得公开未来事件、依赖计数器或 Oracle 路线。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 18 tick 手算成功链；`failure_traces/cases.yaml` 有三条失败；`acceptance.md` 只完成纸面自审，运行时回放、hash、Observation 泄漏测试均未执行。**没有独立求解器证明 18 tick 最优**；只能声称“存在可行解”。

## 10. 与同世界另两图差异

**vs MAP-02**：MAP-02 的核心是第 4 个动作触发泄漏后的在线重排；它的失败来自 `NAV_CORE_FLOODED` 与 `CREW_PRESSURE_LOST`，状态变量是泄漏扩散计数与船员压力预算。MAP-01 没有突发事件，失败来自供氧连续性与电路互斥；两张图的动作因果和不可逆失败模式不同。MAP-01 的“先供氧再修壳”是静态依赖，MAP-02 的“先锁闸还是先救人”是事件后目标重排，不能互相替代。

**vs MAP-03**：MAP-03 的主要负担是跨五阶段保持目标与一次性 K7 的远期召回，失败模式是漏阶段、样本冷藏窗口过期、航线窗错过。MAP-01 的跨度只有 18 tick，且没有一次性远期事实；即使把 MAP-01 的路线拉长，也不会产生“记住早期标签”的需求。两图的记忆维度（MAP-01 M=1，MAP-03 M=3）和成功谓词均不同。

## 11. 可计算性来源

运行时接入后需要：`location`、`oxygen_reserve`、`oxygen_output`、`routed_branch`、`hull_intact`、`main_bus`、`pressure_test`、`terminal_reason` 的逐 tick 快照；依赖边完成事件由 `interact` 结果派生。`oxygen_off_ticks` 用 `oxygen_output` 的连续 False 段复算，不需要新增私有事件。`note` 不得进入 trace 的判分字段。

## 12. 难度定位与对照

D=(0,2,0,2,1,1)。相对同世界基线，本图只考察少量前置依赖；不加随机故障伪装难度。预登记对照：**同信息量依赖图 vs 自行从配电日志推导**；保持电量、路线、动作成本相同。若依赖图额外给出顺序答案，标为“信息可用性实验”，不能称纯能力提升。

## 13. 未决

`bridge_confirmation` 的确认动作/公开结果语义未在 spec 明示（见 `V7-DCR-001`）；`oxygen_off_ticks` 是否公开需人工决定。未决前 `runtime_status=design_only`。
