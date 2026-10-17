# MAP-18｜地铁｜困难｜故障传播

```yaml
map_id: MAP-18
world: metro
nominal_level: 困难
capability_primary: online_uncertain_fault_replanning
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 40a862b1f3d1eb06ebca99049272f9d5071d49b88a7de76ddc65826f142e7985
source_design_hash: 009b29912cc021278bf0fe415ffd31bc4ca9ee12c9940ed969b0bca0b258ebe5
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“收到不含位置的告警后，在线重构联合时刻表”。六列车分布在红线 `R1-R2-R3`、蓝线 `B1-B2-B3`、绿线 `G1-G2-G3`，通过两条容量 1 的联络段 `R2-B2`、`B3-G2` 跨线；t5 起真值区段 `R2-R3` 闭塞 5 tick，tick4 只有一条**不含区段 ID 与时长**的 `NETWORK_DISRUPTION_WATCH`。核心不是“知道哪里断了”，而是在信息不完整时决定：是否提前把 `T_X` 放上跨线绕行、如何让 `T_R1` 进站而不挤爆 R2、是否取消一班以保住其余 15 人。成功门槛 13/18，因此“取消”是合法但昂贵的策略，不是自动失败。

## 2. 真实规则字段

- 网络：红线 `R1,R2,R3`、蓝线 `B1,B2,B3`、绿线 `G1,G2,G3`；联络段 `R2-B2`、`B3-G2`，各容量 1。
- 每站 2 泊位；每段每 tick 至多 1 列车，**双向合并**，禁止同 tick 相向交换；闭塞检查先于普通区段占用。
- 初态：`T_R1@R1→R2`、`T_R2@R2→R3`、`T_R3@R3→R2`、`T_B@B1→B3`、`T_G@G1→G3`、`T_X@R2→G2`；共 18 人，每组 3 人。
- 公开计划到达：`T_R1=6、T_R2=6、T_R3=7、T_B=2、T_G=2、T_X=7`；红线计划发车 tick5/tick6，本来就错峰。
- 动作：`release(next)` 1 tick/段；`temporary_stop` 1 tick；`detour(next)` 只走一段已连接联络；`turnback(reverse_toward)` 锁 2 个完整 tick 后掉头；`cancel_service(task_id)` 立即取消、乘客计入服务损失、空车可调位。
- 故障：`fault_window=(5,10)`（t5–t9 关闭，t10 操作前恢复）；`alert_tick=4`；`fault_edge` 属裁判私有，t5 前不进入 Observation。
- 成功：horizon 12 内 `delivered_passengers >= 13`。
- 失败码：`STATION_CAPACITY_EXCEEDED`、`HEAD_ON_COLLISION`、`SEGMENT_CAPACITY`、`TRACK_CLOSED`、`COMPLETED_TRAIN_MOVED`、`INVALID_LINK`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map18.service_rate` | primary | `delivered_passengers / 18` | 比例 / 高 | 18 | 缺字段 → UNAVAILABLE；未到 horizon 截尾 → CENSORED（值仍报已交付） |
| `map18.delay_person_ticks` | primary | Σ `人数 × max(实际到达 tick − 公开计划 tick, 0)` | 人·tick / 低 | 已交付任务 | 无交付 → 0（合法）；截尾只累计已观察交付并标 CENSORED |
| `map18.first_reroute_delay` | primary | 首个合法非封闭移动的 tick − 封锁首次公开 tick | tick / 低 | 实际发生封锁的 episode | 无封锁/封锁后无移动型时刻表 → N/A；提交了但未成功改线 → CENSORED |
| `map18.recovery_delay` | primary | 首个红线任务（封锁后）交付 tick − 封锁公开 tick | tick / 低 | 封锁且红线未在封锁前交付 | 红线已提前交付 → N/A；未恢复且截尾 → CENSORED |
| `map18.station_capacity_violations` | guardrail | `count(STATION_CAPACITY_EXCEEDED)` | 次 / 低 | episode | 0 合法 |
| `map18.collision_violations` | guardrail | `count(HEAD_ON_COLLISION) + count(SEGMENT_CAPACITY)` | 次 / 低 | episode | 0 合法；合并值须保留分项 |
| `map18.completed_train_moves` | guardrail | `count(COMPLETED_TRAIN_MOVED)` | 次 / 低 | episode | 0 合法 |
| `map18.legal_action_rate` | diagnostic | 被接受的 `set_timetable` / 提交数 | 比例 / 高 | 提交数；0 → N/A | 0 提交 → N/A |

实现：`src/agent_arena/v7/metrics/map18.py`，共 8 条 `implemented=True`。冻结常量（18 人、计划到达、红线任务集）在 `references.py`。

## 4. 能力混淆分析

- `service_rate=1.0` 可能靠“全员提前交付”规避故障（V6 离线报告已指出 t5 前完成则闭塞不约束），此时 `first_reroute_delay`/`recovery_delay` 为 N/A；不许把 N/A 当 0 计入“完美恢复”。
- `delay_person_ticks=0` 不能与“取消后没人迟到”混谈：取消的 3 人根本不产生到达延误，必须同时看 `service_rate` 与 `canceled_tasks`。
- `first_reroute_delay` 小可能只是“封锁后随手动了一列车”，与“恢复红线服务”不同；必须与 `recovery_delay` 并列。
- 三类 guardrail 因果不同：站台泊位（`STATION_CAPACITY_EXCEEDED`）、区段/相向（`HEAD_ON_COLLISION`/`SEGMENT_CAPACITY`）、任务语义（`COMPLETED_TRAIN_MOVED`）；合并成“违规率”会掩盖策略缺陷类型。
- `TRACK_CLOSED` 是“硬闯已封闭区段”，本卡片不计入碰撞类 guardrail，需在失败归因中单列（`V7-DCR` 候选：是否新增独立 metric）。

## 5. 两条手算轨迹

**A. 告警后预先绕行（18/18，延误 30 人·tick）**：tick0–1 `T_B`、`T_G` 各走两段抵 B3/G3；tick4 `T_X` 从 R2 走到 B2（此时尚未公开封锁）；tick5 `T_X B2→B3` 与 `T_R1 R1→R2` 同 tick 原子交班，R2 仍为 `T_R2/T_R1` 两车；tick6 `T_X B3→G2`；`T_R2` 等到 t10 修复后通过，`T_R3` t11 反向通过。指标：`service_rate=1.0`；`delay_person_ticks = 3×5(T_R2) + 3×5(T_R3) = 30`；`recovery_delay` 从 t5 到 t12 最后受影响班次解决 = 7 tick；`station/collision/completed=0`。

**B. 无告警、故障后再绕行（18/18，延误 33 人·tick）**：tick0–3 与 A 完全相同；tick4 等待；tick5 观察到 `closed_segments` 后才让 `T_X` 出 R2，其余恢复次序相同。指标：`service_rate=1.0`；`delay = 30 + 3×1 = 33`；`recovery_delay` 仍为 7 tick；guardrail 全 0。**A 与 B 的唯一差值 3 人·tick 就是“预警信息”的可测收益**，不能外推为普遍因果。

**C. 取消一班（15/18，延误 15 人·tick）**：tick5 取消 `T_R2` 的 3 人任务并在 R2 折返，`T_R3` 修复后回 R2。指标：`service_rate=15/18≈0.8333`（仍过 13 人门槛）；`delay = 3×4(T_R3 计划 7→实际 11) + 3×1(T_X 7→8) = 15`；`recovery_delay=6`。服务率下降但延误更低——这正是“取消换准点”的取舍，必须与 service 并列读。

## 6. 三个机制特有失败

1. **F01 早发对穿**：tick4 让 `T_R2`、`T_R3` 相向预约 `R2-R3`，`HEAD_ON_COLLISION`；整批不动。告警存在也不能消除共享区段的相向约束。
2. **F02 硬闯闭塞**：t5–t9 反复对 `R2-R3` 发 `release`，每次 `TRACK_CLOSED`；t10 修复后又同 tick 对穿，`SEGMENT_CAPACITY`。持续失败会耗尽 action 预算（V6 中即为 action-limit 截尾）。
3. **F03 双取消**：故障发生时把 `T_R2`、`T_R3` 同时取消，最终 `12/18=66.7% < 13`，服务门槛失败。取消不是“无损折返”。

## 7. 两个边界

- **tick9 关闭 vs tick10 重开**：B01 检查 t9 仍在 `closed_segments`、t10 已恢复；早一 tick 通行会被 `TRACK_CLOSED` 拒绝，晚一 tick 则白等。修复边界是 tick 级的，不是“大约”。
- **13/18 门槛**：`success_threshold=13`。取消一班（15/18）成功、取消两班（12/18）失败；`service_rate` 在 0.7222 与 0.6667 之间是成功/失败分界。指标不得用“高于 0.5 即通过”之类自造阈值。

## 8. 信息泄漏负例

若 Observation 直接给 `fault_edge`、`fault_window` 或“R2-R3 将关闭 5 tick”，在线不确定性消失，本图退化为 MAP-16 式静态调度。V7 只允许公开告警文本（不含区段/时长）、当前 `closed_segments`、车位置/锁定、任务与已交付、泊位与计划到达；`fault_edge/fault_window/fault_enabled` 只在 `judge_state`。另：`runs/` 中的实例 manifest 含私有真值哈希，不得作为 Agent 输入。

## 9. Oracle/求解状态

V4 `oracle_trace.jsonl` 与 `planning/hand_traces.json` 有 A/B/C 三份逐 tick 手写方案，`schedule_audit.py` 复核 18/18 可行；V6 `solvers.py` 用构造法证明每个实例存在 18/18 交付方案，但**未证明最优**（V6 验证报告已列出该缺口）。V6 真实 API 10 局：**0/10**，服务率 0–0.33，失败为 `STATION_CAPACITY_EXCEEDED`/`HEAD_ON_COLLISION`/`COMPLETED_TRAIN_MOVED` 或 action-limit 截尾；alert 开/关无差异。**这是地板，不是能力为零的证据**（`V7-DCR-009`）。

## 10. 与同世界另两图差异

**vs MAP-16**：MAP-16 静态容量、2 列车、固定终点、以 makespan 与死锁为核心；MAP-18 有 6 列车、跨线联络、动态闭塞与取消语义，核心是在线恢复。MAP-16 没有“告警”这一信息动作，也没有 `cancel_service`。

**vs MAP-17**：MAP-17 是 4 列车 + 静态客流的多目标 Pareto；MAP-18 的故障窗口会改变可用区段与可行服务集，核心指标是恢复延迟与恢复后服务率。MAP-17 的 B-C 是**永久**单段瓶颈，MAP-18 的 R2-R3 是**时间窗**闭塞；前者可规划，后者必须在线反应。

## 11. 可计算性来源

需要的公开字段：`tick, task_passenger_counts, delivered_tasks, canceled_tasks, delivered_passengers, station_berths, closed_segments, published_dispatch_windows, current_train_locks, alert_message_if_any, recovery_status`，以及每次 `set_timetable` 的 `operations` 与结果码。`delay_person_ticks` 由首个交付事件 tick 与冻结计划表复算；`first_reroute_delay` 判定“非封闭区段移动”使用 `observation_before.train_positions` 与 `observation_after.closed_segments` 的**有向/无序边**交集；`recovery_delay` 只统计 `TASK_R2_R3`/`TASK_R3_R2`。全部无需私有真值。

## 12. 难度定位与对照

D=(2,3,3,2,2,3)。相对 MAP-17 提升 **V↑（真值故障隐藏，只有无位置告警）与 E↑（动态闭塞窗口）**；D 保持 3，R 反而从 3 降到 2（资源类型少但时序更强）。不会与 MAP-17 混淆：MAP-17 没有故障/取消，MAP-18 没有 Pareto 参照表。

预登记对照：**`alert_on` vs `alert_off`**（V6 机制），两条件共享实例、初态、预算与动作契约，t0–t3 完全相同，差异只在 tick4 是否多一条无位置告警。另需 **L1 无故障 vs L2 已知故障 vs L3 在线** 分层报告——L1 只是接口与静态调度基线。

## 13. 未决

- `V7-DCR-009`：当前 fault 载荷在“t5 前完成红线任务”时不构成约束，且 13/18 允许取消两班；未解决前不宜把 0/10 解释为“在线恢复能力为零”。
- `TRACK_CLOSED` 目前未进入任何 guardrail，是否新增独立 metric 待定。
- `first_reroute_delay` 对“封锁前已提前绕行”的策略只测到封锁后的首个合法移动，预警收益主要体现在 `delay_person_ticks`；card 已注明，但需要一个专门边界用例固化。
- 6 个 V6 实例（L1/L2 短闭塞/L3 原/L3 长闭塞/L2 R2-B2/L3 B3-G2）均 `pending_human_review`；真实 API 仅 10 局、单次。
