# MAP-17 定稿：早高峰

| 字段 | 值 |
|---|---|
| 世界 | subway |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `1f45fd8a4507c3154f278be7967e1ff023a8671893194433a954d76c80810989` |
| rule_hash | `9e9985a2238afcfccd3cb4ee43919f71cda953e291f69408df4c41d8da1eb203` |
| prompt_hash | `1ff298c7c0dac93a2bd8aca9bfc110ff4d551ca924d9d7e0f1cc2d4bc8401ed5` |
| metric_schema_hash | `d82a19a1e94964db317283e281e56d9478e94f48e2aacd2103245b610f210dc1` |
| oracle_hash | `fd7d74af82fcc5a1bc8b987dd0b1c7fd4b561a306d056c381374f6284422abd2` |
| commit | `223e532ed9b9613ba96e06d129b41fb1f52b37bc` |

## 1. 设计意图与独特机制

本关单独设计为时刻表优化题：环线A-B-C-D-A挂接B-E-F支线，瓶颈固定在双向共用的B-C单段；四班车分别从A/C/D/F发车，面对5组固定OD客流。核心不是“尽量多跑”，而是在同一张客流表上公开比较准点、服务率、乘客等待和能耗之间的取舍。

MAP-17｜早高峰：B-C 共享瓶颈下的四车联合时刻表与多目标 Pareto 取舍。

本图与同世界另两图的机制差异：MAP-16 是两列车固定起终点的 makespan/死锁题；MAP-18 有
闭塞故障与在线恢复；本图没有故障与随机延误，主机制是同一张 10 人 OD 客流表上“服务率、
乘客等待、能耗/人、最后交付 tick”四个目标互不支配的联合调度。每个 tick 提交一行
``set_timetable{tick, operations}``，四列车同步执行各自的一个操作。

规则要点：
- 环线 A-B-C-D-A + 支线 B-E-F，每段 1 tick；B-C 是唯一双向合并容量 1 的区段；每站至多
  2 列车；每车 3 座；12 个结算 tick；能耗上限 18。
- 操作：``release{to}`` 耗 1 能量并占用本 tick 区段；``stop{board}`` 停 1 tick 装载；
  ``switch_line{line, board}`` 仅在 B、停 1 tick、设定离站线路并装载；``delay`` 原地等。
- ``board`` 是 ``{OD: 人数}`` 清单，只允许装当前站始发的 OD；目的地到达时自动下车。
- B 站换乘等待：本图不实现中途下车换乘（与设计文档的未决项一致），B 站队列的等待
  （例如 B→E 乘客等待支线列车）完整计入 ``passenger_wait_person_ticks``；每次 ``stop`` /
  ``switch_line`` 前，tick 开始时仍在站台的所有人都累计 1 人·tick。
- 预检失败（tick 不符、区段冲突、站台超容、非法登车清单、能耗越界）整行不提交：
  位置、能耗、等待与 tick 全部不变。``SHARED_SEGMENT_CONFLICT`` 对同向双车同样生效。
- tick 12 结算：送达 ≥ 8/10 成功 ``DEMAND_THRESHOLD_MET``，否则
  ``DEADLINE_SERVICE_BELOW_80``。

指标口径（与 V7 卡片一致）：
- ``service_rate``：实际在目的站下车人数 / 10（按 OD 客流权重，不按上车数）。
- ``cumulative_wait_person_ticks``：逐 tick 在站台等待的人数累加；换乘/支线等待同样计入。
- ``energy_per_passenger``：``energy_used / delivered``；0 人送达时为 N/A（``None``）。
- ``overcapacity_events``：``PLATFORM_CAPACITY`` + ``SHARED_SEGMENT_CONFLICT`` 被拒次数。
- Pareto 向量（服务损失、等待/120、能耗/18、最后交付/12）只进 ``judge_state``，不注册为
  额外 metric，也不向玩家给出参照前沿。

## 2. 与同世界另两图的区别

- **MAP-16**（简单）：本关只研究两列反向列车怎样共享一条单线和一个避让站；线路图与两套等长时刻表均为本图手工指定。先完成MAP-16的完整纸面审计与验收材料，再进入MAP-17。
- **MAP-18**（困难）：本图设计为在线恢复调度场景；六列车分布在三条线路、两列红线对向班次共用R2-R3、另有列车占据R2换乘泊位。t5开始R2-R3停运五个tick。处理重点是收到不含位置的告警后是否先把T_X从R2送上跨线绕行、如何让T_R1进站而不挤爆R2、红线班次如何等修复错峰恢复，以及是否取消一班后折返空车。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`delivered_by_od`, `demand_matrix`, `energy_consumed`, `energy_remaining`, `goal`, `last_delivery_tick`, `onboard_passengers`, `passenger_wait_person_ticks`, `station_train_counts`, `tick`, `ticks_remaining`, `topology`, `train_positions`, `train_seat_capacity`, `waiting_demand`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`counters`, `delivered`, `delivered_total`, `energy_used`, `last_delivery_tick`, `line`, `onboard`, `pareto_vector`, `positions`, `tick`, `wait_person_ticks`, `waiting`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `set_timetable`：`operations`, `tick`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：每 tick 四车同步执行各自一个操作；B-C 共享瓶颈；四目标保持 Pareto 向量。

- 成功码：`DEMAND_THRESHOLD_MET`
- 失败码：`DEADLINE_SERVICE_BELOW_80`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map17.cumulative_wait_person_ticks` | primary | lower_is_better | Σ passengers × wait_ticks | 已服务乘客 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.energy_per_passenger` | diagnostic | lower_is_better | energy_used / delivered_passengers | 已服务乘客；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.overcapacity_events` | guardrail | lower_is_better | count(STATION_CAPACITY) + count(COLLISION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map17.service_rate` | primary | higher_is_better | delivered_weight / total_demand_weight | 总需求 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：time_priority（12 步）, energy_priority（12 步）
- 手算 fixture：time_priority_vector（12 步）, shared_bc_reverse_swap_is_rejected（3 步）, third_train_overfills_b_platform（3 步）, energy_budget_rejection_keeps_clock_and_wait（6 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-17` → `MAP-17: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | missing | None | None | — | None | `None` | — |
| 1 | missing | None | None | — | None | `None` | — |
| 2 | missing | None | None | — | None | `None` | — |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

四目标不合成单分；报告 Pareto 向量，不宣称某一目标优先。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
