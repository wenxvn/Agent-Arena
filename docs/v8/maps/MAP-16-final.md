# MAP-16 定稿：单线会车

| 字段 | 值 |
|---|---|
| 世界 | subway |
| 难度 | 简单 |
| 条件 | `constraint_table` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `b1224ccd52a712c7bf60d51797633f345b304ae620b876225250179e1a3fb8bf` |
| rule_hash | `47548b6c5585a6d0d82b8de082d1ce1f99009e4e9bd9639f0957ed623b0b8048` |
| prompt_hash | `50cdea891e4cd0991657a50680082fecc1f79fe895fb8a67301ecf13af38e43d` |
| metric_schema_hash | `1fca8c5b91c939b9b8bfab0d71e0512c1f2c50c947576f782eb27dcc675a27e0` |
| oracle_hash | `5c7ff1f46860a037cc0b835351db138fbf215d6342f0b266952632e887086cb9` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

本关只研究两列反向列车怎样共享一条单线和一个避让站；线路图与两套等长时刻表均为本图手工指定。先完成MAP-16的完整纸面审计与验收材料，再进入MAP-17。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-17**（中等）：本图与同世界另两图的机制差异：MAP-16 是两列车固定起终点的 makespan/死锁题；MAP-18 有闭塞故障与在线恢复；本图没有故障与随机延误，主机制是同一张 10 人 OD 客流表上“服务率、乘客等待、能耗/人、最后交付 tick”四个目标互不支配的联合调度。每个 tick 提交一行``set_timetable{tick, operations}``，四列车同步执行各自的一个操作。
- **MAP-18**（困难）：本图设计为在线恢复调度场景；六列车分布在三条线路、两列红线对向班次共用R2-R3、另有列车占据R2换乘泊位。t5开始R2-R3停运五个tick。处理重点是收到不含位置的告警后是否先把T_X从R2送上跨线绕行、如何让T_R1进站而不挤爆R2、红线班次如何等修复错峰恢复，以及是否取消一班后折返空车。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`node_capacities`, `occupied_nodes`, `pending_route_reservations`, `segment_capacities`, `tick`, `topology`, `train_goals`, `train_positions`, `train_route_directions`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`conflicts`, `map_id`, `pending`, `positions`, `seed`, `status`, `terminal_reason`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect_network`：无附加字段
- `move_train`：无附加字段
- `occupy_siding`：`next_node`, `train_id`
- `release_section`：`section_id`, `train_id`
- `set_route`：`next_node`, `train_id`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：两列车联合预约；同 tick 节点/区间容量冲突即失败；makespan 由 V7 extractor 计算。

- 成功码：`GATE_OPENED`
- 失败码：`NODE_CAPACITY_CONFLICT`, `HEAD_ON_SWAP`, `SECTION_CONFLICT`, `DEADLOCK`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map16.committed_ticks` | diagnostic | lower_is_better | count(MOVES_COMMITTED or GATE_OPENED) | episode | 0 → 合法 0 | 按已提交 tick 计算 |
| `map16.deadlock` | guardrail | lower_is_better | 1 if terminal_reason==DEADLOCK else 0 | episode | 无终局 → CENSORED | 截尾且未进入死锁 → CENSORED |
| `map16.head_on_conflicts` | guardrail | lower_is_better | count(result==HEAD_ON_SWAP) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map16.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map16.legal_reservation_rate` | primary | higher_is_better | ROUTE_RESERVED / (set_route + occupy_siding submissions) | 提交的预约动作数；0 则 N/A | 没有预约动作 → N/A | 过程量按已提交动作计算，不因截尾删除 |
| `map16.makespan_gap` | primary | lower_is_better | committed_ticks - BFS_optimum(instance) | 成功终局的 episode | 实例无冻结最优 → UNAVAILABLE；已失败 → N/A | step-limit 截尾 → CENSORED |
| `map16.node_capacity_conflicts` | guardrail | lower_is_better | count(result==NODE_CAPACITY_CONFLICT) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map16.section_conflicts` | guardrail | lower_is_better | count(result==SECTION_RESERVATION_CONFLICT) | episode | 0 次为合法 0 | 按已发生事件计数 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-16-solver-success（17 步）
- 手算 fixture：node-capacity-conflict（7 步）, l3-two-train-success（17 步），补充冻结后失败用例 `head-on-swap-failure`（10 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-16` → `MAP-16: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | DEADLOCK | 6 | 0.0037252 | `V8-MAP-16-R0-20261017T091223Z-53fd210b` | `committed_ticks`=2; `deadlock`=1; `head_on_conflicts`=0; `legal_action_rate`=1.0 |
| 1 | failure | False | NODE_CAPACITY_CONFLICT | 24 | 0.01343676 | `V8-MAP-16-R1-20261017T091303Z-0a5e0822` | `committed_ticks`=3; `deadlock`=0; `head_on_conflicts`=0; `legal_action_rate`=0.583333 |
| 2 | failure | False | NODE_CAPACITY_CONFLICT | 15 | 0.00612656 | `V8-MAP-16-R2-20261017T091445Z-e1cb5211` | `committed_ticks`=3; `deadlock`=0; `head_on_conflicts`=0; `legal_action_rate`=0.8 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

复用 V6 `map16_l3_original`；`makespan_gap` 依赖 BFS 基线，不与其他图横比。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `8/8`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
