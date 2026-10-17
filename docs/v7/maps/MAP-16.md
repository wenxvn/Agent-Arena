# MAP-16｜地铁｜简单｜单线会车

```yaml
map_id: MAP-16
world: metro
nominal_level: 简单
capability_primary: deadlock_avoidance
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 387e4dcba46e38acfbad5044644cbd1bcf1c22ae033123e423b15825f59b1389
source_design_hash: aa8ef5365fe8a11de4d9f51e846ca593be6499f7f5d623f15687d898b0fc6f09
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“同步预约与死锁避免”。两列车 a/b 在 `A—X—M—Y—B` 主线相向而行，`M—D` 是避让侧线；区段容量 1、节点容量 1，`B-C` 式的共享区段不能同时被两车预约。Agent 每 tick 先提交 `set_route/occupy_siding`，再 `move_train` 原子提交；同段预约、相向交换、节点/避让站容量冲突都会立即失败，死锁检测在移动后运行。核心不是“走得快”，而是让两车在正确时点使用避让站，避免不可恢复的占用。

## 2. 真实规则字段

- 节点 `A,X,M,Y,B,D`；方向表限制每列车可走的下一节点；所有边 1 tick。
- 初始 `a@A, b@B`；目标 `a@B, b@A`。
- 区段容量 `AX/XM/MY/YB/MD = 1`；节点容量均 1；避让站 `D`。
- 预约：`set_route(train,next)` / `occupy_siding(train,next)` 只登记 pending，不移动；同段重复预约 → `SECTION_RESERVATION_CONFLICT` 或 `HEAD_ON_SWAP`（相向交换，立即失败）。
- 提交：`move_train` 原子检查重复区段、节点占用、目标站容量；任一冲突 → `NODE_CAPACITY_CONFLICT` / `SIDING_CAPACITY_CONFLICT` / `HEAD_ON_SWAP`；全部通过才推进 tick。
- 死锁：移动后若从新状态无法到达目标，立即 `DEADLOCK`。
- 公开：tick、拓扑、方向表、车位置/目标、区段/节点容量、占用节点、待定预约、终止原因。
- 成功：`a_at_B && b_at_A && 无冲突`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map16.legal_reservation_rate` | primary | `ROUTE_RESERVED` / 提交的预约动作 | 比例 / 高 | 预约提交数；0 → N/A | 0 预约 → N/A |
| `map16.makespan_gap` | primary | 实际 commits − 同实例 BFS 最优 makespan | tick / 低 | 成功终局 | 失败 → N/A；截尾 → CENSORED |
| `map16.deadlock` | guardrail | `1[DEADLOCK]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map16.node_capacity_conflicts` | guardrail | `count(NODE_CAPACITY_CONFLICT)` | 次 / 低 | episode | 0 合法 |
| `map16.head_on_conflicts` | guardrail | `count(HEAD_ON_SWAP)` | 次 / 低 | episode | 0 合法 |
| `map16.section_conflicts` | guardrail | `count(SECTION_RESERVATION_CONFLICT)` | 次 / 低 | episode | 0 合法 |
| `map16.committed_ticks` | diagnostic | `MOVES_COMMITTED/GATE_OPENED` 次数 | tick / 低 | episode | 0 合法 |
| `map16.legal_action_rate` | diagnostic | 接受决策 / 提交决策 | 比例 / 高 | 模型决策数 | 0 → N/A |

实现：`src/agent_arena/v7/metrics/map16.py`；最优值来自冻结表（L1=3、L2a=4、L2b=5、L3=6），或 `judge_metrics` 的 `optimality_gap`。

## 4. 能力混淆分析

- 高合法预约率可能只提交一次预约就停手；必须与 `makespan_gap` 并列。
- 低 gap 可能只因为 L1 单列车（3 tick）；V6 L1 2/2 不能宣称会车能力，L2/L3 必须分报。
- 失败局的 `committed_ticks` 少不代表高效；`makespan_gap` 在失败局是 N/A，不能补 0。
- 相向交换、节点容量、区段容量是三种不同因果；合成一个“冲突率”会掩盖死锁风险。

## 5. 两条手算轨迹

**L1 单列车成功（3 个 commit，7 个决策）**：`inspect_network`（1）→`set_route a A→X`（2）→`move_train`（3，commit1）→`set_route a X→M`（4）→`move_train`（5，commit2）→`set_route a M→B`（6）→`move_train`（7，commit3，`GATE_OPENED`）。指标：预约 3/3=1.0；committed 3；BFS 最优 3；gap 0；冲突/死锁 0；合法动作 7/7=1.0。

**L3 双车成功（6 commits）**：BFS 组合状态最优 6；求解器给出的 6 tick 调度逐动作回放成功。指标：预约率 1.0；committed 6；gap 0；死锁 0；节点/相向/区段冲突 0；合法动作率 1.0。该轨迹**不是**“服务率最优”证明，只证明 makespan 与 BFS 一致。

**失败（节点容量，1 commit）**：a A→X、b B→Y 各 commit 一次（positions X/Y）→a `set_route X→M`、b `set_route Y→M` 均 accepted →`move_train` 两车同时以 M 为目标，`NODE_CAPACITY_CONFLICT`。指标：预约 4/4=1.0；committed 1；gap N/A；节点冲突 1；死锁 0。

## 6. 三个机制特有失败

1. `NODE_CAPACITY_CONFLICT`：两车同 tick 进入同一站；合法预约不等于安全提交。
2. `HEAD_ON_SWAP`：两车在同一区段相向交换预约，立即失败；与节点容量不是同一规则。
3. `DEADLOCK`：两车占用侧线与主线形成不可恢复状态；移动本身合法，但已无安全完成路径。

## 7. 两个边界

- **单列车 L1 vs 双列车 L3**：L1 只需 3 commit、无避让；L3 需要 6 commit、含同步避让。L1 的 100% 不能外推；必须分开报告。
- **失败 vs 截尾的 gap**：失败局 `makespan_gap=N/A`；step-limit 截尾 `CENSORED`。只有成功终局才计算 gap，避免把未完成当“最优”。

## 8. 信息泄漏负例

若 prompt/Observation 直接给 BFS 最优调度、下一 tick 应占哪个节点或未来列车位置，同步预约被替代。V7 只允许公开当前拓扑、车位置、目标、容量与 pending 预约；`route_audit.json`/BFS 只在离线裁判侧。

## 9. Oracle/求解状态

V4 `oracle_trace.jsonl` 有 a/b 两套 6 tick 手写方案、8 个无碰撞位置状态枚举、1 个不可恢复死锁；V6 用组合状态 BFS 得最小 makespan（L1=3、L2a=4、L2b=5、L3=6），`validate_v6_instances.py` 逐步回放通过。真实 API 6 局：L1 2/2（makespan=3=最优）、L2a/L3 0/4（`NODE_CAPACITY_CONFLICT`），条件无差异。**单次结果，不能外推。**

## 10. 与同世界另两图差异

**vs MAP-17**：MAP-17 是 4 列车、环线+支线、乘客等待与能耗的多目标 Pareto 优化，没有“相向交换立即失败”的单线死锁规则；MAP-16 的核心是同步预约与避让站容量。MAP-17 的成功允许多个互不支配解，MAP-16 的成功是固定目标位置；两者的状态变量与目标函数不同。

**vs MAP-18**：MAP-18 是三线六车、闭塞故障、站台泊位与在线恢复调度，故障窗口会改变可用区段；MAP-16 没有故障或时间窗，只有静态容量与死锁。MAP-18 的核心指标是服务率/恢复延迟，MAP-16 是 makespan/死锁；把 MAP-16 加长不会产生 MAP-18 的在线恢复。

## 11. 可计算性来源

`map16.py` 从 `result` 原因码、`pending_route_reservations`、`tick`、`terminal_reason` 计算；预约分母是 `set_route/occupy_siding` 提交数。最优 makespan 来自冻结实例表或离线 `judge_metrics`，不进入 Agent 输入。

## 12. 难度定位与对照

D=(1,2,0,1,1,2)。本世界入门但已具多实体约束。预登记对照：**ReAct vs 同信息约束表**；严格配对实例与预算。V6 中条件无差异，属天花板/地板混合，需要更多重复或加难度后再判断。

## 13. 未决

V6 的 L2b、部分 L2/L3 条件未跑真实 API；L1 天花板未解除前不作能力结论。所有实例仍 `pending_human_review`。
