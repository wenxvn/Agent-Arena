# MAP-18 定稿：故障传播

| 字段 | 值 |
|---|---|
| 世界 | subway |
| 难度 | 困难 |
| 条件 | `alert_on` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `52cde32f9e044815df6763b2feb13b840ef009520866edab51c4b3598a04d88a` |
| rule_hash | `aa446dfaa631197cd1f46b66e5c481eef6a68da694f76776afd4567cd75c5d8e` |
| prompt_hash | `b474c6d1fec3c2dc83a9f6b2915449c47c3d2d3050630e4fe4b7ed9265bcaca7` |
| metric_schema_hash | `cadd9063303d73b9287c81940fb56e43a5866d0be42e32306d98a0e38f5572e2` |
| oracle_hash | `3dd5305e90c49d2fe49d40ebbb477cea05384a59c08fab3074f9c6833e6486d1` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图设计为在线恢复调度场景；六列车分布在三条线路、两列红线对向班次共用R2-R3、另有列车占据R2换乘泊位。t5开始R2-R3停运五个tick。处理重点是收到不含位置的告警后是否先把T_X从R2送上跨线绕行、如何让T_R1进站而不挤爆R2、红线班次如何等修复错峰恢复，以及是否取消一班后折返空车。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-16**（简单）：本关只研究两列反向列车怎样共享一条单线和一个避让站；线路图与两套等长时刻表均为本图手工指定。先完成MAP-16的完整纸面审计与验收材料，再进入MAP-17。
- **MAP-17**（中等）：本图与同世界另两图的机制差异：MAP-16 是两列车固定起终点的 makespan/死锁题；MAP-18 有闭塞故障与在线恢复；本图没有故障与随机延误，主机制是同一张 10 人 OD 客流表上“服务率、乘客等待、能耗/人、最后交付 tick”四个目标互不支配的联合调度。每个 tick 提交一行``set_timetable{tick, operations}``，四列车同步执行各自的一个操作。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`alert_message_if_any`, `canceled_passengers`, `canceled_tasks`, `closed_segments`, `current_train_locks`, `delivered_passengers`, `delivered_tasks`, `published_dispatch_windows`, `recovery_status`, `station_berths`, `task_passenger_counts`, `tick`, `ticks_remaining`, `topology`, `train_positions`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`alert_enabled`, `canceled`, `delay_person_ticks`, `delivered`, `headings`, `locks`, `map_id`, `positions`, `seed`, `status`, `task_status`, `terminal_reason`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `set_timetable`：`operations`, `tick`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：每 tick 提交整张时刻表；闭塞故障窗口 (5,10)；碰撞与站台容量分别失败。

- 成功码：见运行时
- 失败码：`由终局 `verdict`/动态码表达，见失败路径`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map18.collision_violations` | guardrail | lower_is_better | count(HEAD_ON_COLLISION) + count(SEGMENT_CAPACITY) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map18.completed_train_moves` | guardrail | lower_is_better | count(result==COMPLETED_TRAIN_MOVED) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map18.delay_person_ticks` | primary | lower_is_better | Σ_task passengers × max(arrival_tick - planned_arrival_tick, 0) | 已交付任务；未交付不计入（另报 service_rate） | 无交付 → 0（合法） | 未到 horizon 截尾时只累计已观察交付并标 CENSORED |
| `map18.first_reroute_delay` | primary | lower_is_better | tick(first non-closed release/detour committed) - tick(closure first public) | closure 实际发生的 episode | 从未观察到封锁，或封锁后没有任何移动型时刻表 → N/A | 封锁后提交了移动但未成功改线 → CENSORED（延迟无上界） |
| `map18.legal_action_rate` | diagnostic | higher_is_better | accepted set_timetable / submitted set_timetable | 提交的时刻表动作数；0 则 N/A | 0 次 → N/A | 按已提交动作计算 |
| `map18.recovery_delay` | primary | lower_is_better | tick(first red-line task delivered after closure) - tick(closure first public) | closure 实际发生的 episode | 无封锁，或红线任务已在封锁前交付 → N/A | 封锁后红线任务未恢复交付且 episode 截尾 → CENSORED |
| `map18.service_rate` | primary | higher_is_better | delivered_passengers / 18 | 总需求 18 人 | 无公开 delivered_passengers → UNAVAILABLE | 未到 horizon 的 step-limit 截尾 → CENSORED（值仍为已交付比例） |
| `map18.station_capacity_violations` | guardrail | lower_is_better | count(result==STATION_CAPACITY_EXCEEDED) | episode | 0 次为合法 0 | 按已发生事件计数 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-18-solver-success（12 步）
- 手算 fixture：head-on-collision（1 步）, observed-recovery（12 步），补充冻结后失败用例 `station-capacity-failure`（1 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-18` → `MAP-18: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

复用 V6 `map18_l3_original`；静态调度地板仍在，故障窗口 (5,10) 已提供在线约束。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `8/8`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
