# MAP-27 定稿：月面联合行动

| 字段 | 值 |
|---|---|
| 世界 | lunar |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `e7ef2cee45fafd8627d10609ca78d157d075634645e28e370dbb3c97506d23d1` |
| rule_hash | `b993858b9d0b62305ac1950e6f3a1e5cd1a8f3c479606e1aa1f8a2850e255cf7` |
| prompt_hash | `368928e30727b6d2f663336758f35af070f1e763dbfef400ccf2875a3e97336e` |
| metric_schema_hash | `653c1e4c10afb6246b3b742cf28b4845b114de64bc54cb7a38735c1e51ffe921` |
| oracle_hash | `8963e6494dc7762da6336e295907ca2fe6a28c4c77d1215760c353ad7f7b0b0f` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

这是一张长程联合任务图，关键不是去四处把东西捡齐，而是在两格货舱里安排互斥工具，先后维护中继、稳定并远程撤走伤员、封存样本，再带样本回基地。P–E远路使“先修中继”方案吃满电池预算，S–E近路让“先稳定伤员”方案保留明显余量。

MAP-27｜月面联合行动：两格货舱、一次性电芯与两阶段救援的长程协调。

本图与同世界另两图的机制差异：MAP-25 是单人顺序合规（穿服/挂绳/诊断），没有
货舱、电池和远程救援；MAP-26 是隐藏故障的诊断-反馈-回滚循环。本图没有隐藏故障
（中继 OFFLINE 是公开状态），难度来自两格货舱里互斥工具的先后、14 电与 18 氧按
道路原子并行消耗、P–E 四 tick 远路与 S–E 一 tick 短路的选择，以及“现场稳定 ≠
完成救援”的两阶段救援（稳定 → 中继在线后才可远程撤离）。

动作契约（``SHAPES`` 精确声明）：
- ``load(item_id)``：样本容器只在 B，医疗包与维修盒只在 S；各占 1 格。
- ``drive(to)``：沿 ``EDGES`` 双向道路移动，tick/电池/氧气成本等于道路成本。
- ``charge()``：只在 S，2 tick，补 4 且硬封顶 14，消耗唯一电芯。
- ``repair_relay()``：只在 R，携带维修盒，2 tick，成功后永久在线并消耗维修盒。
- ``sample(item_id)``：只在 P，携带样本容器，1 tick，容器仍占 1 格。
- ``rescue(operation, item_id?)``：``field_stabilize`` 只在 E 且消耗医疗包；
  ``remote_evacuation`` 可在 R 或 E，要求中继在线且伤员已稳定。
- ``submit()``：只在 B，0 tick，按四个目标与正氧气一次性终局。

失败码沿用 ``worlds/v4/MAP-27/map_spec.yaml``：``ITEM_NOT_AVAILABLE_HERE``、
``CARGO_CAPACITY_EXCEEDED``、``EDGE_NOT_ADJACENT``、``BATTERY_INSUFFICIENT``、
``VEHICLE_STRANDED``、``CREW_OXYGEN_DEPLETED``、``CHARGER_EMPTY``、
``BATTERY_ALREADY_FULL``、``RELAY_TOOL_REQUIRED``、``RELAY_ALREADY_ONLINE``、
``SAMPLE_CONTAINER_REQUIRED``、``MEDICAL_KIT_REQUIRED``、``RELAY_OFFLINE``、
``CASUALTY_NOT_STABILIZED``、``OBJECTIVES_INCOMPLETE_AT_BASE``。本运行时按 V7 卡片
的未决项统一了载荷/能源冲突：货舱装满时的 ``load`` 与货舱无空位时的 ``charge`` 都
返回 ``RESOURCE_CONFLICT``（设计中的具体码 ``CARGO_CAPACITY_EXCEEDED`` 与
``CHARGE_SLOT_CONFLICT`` 保存在 ``judge_state()`` 的违规账里，两种冲突都不改动状态）。

指标口径（与 ``docs/v7/maps/MAP-27.md`` 一致）：
- ``map27.joint_task_completion_rate``：分子 = 中继在线 + 伤员 RESCUED + 样本 SEALED
  三项已完成数，分母固定 3；未提交按已完成项计。
- ``map27.critical_path_delay``：成功终局 tick 数 − 手写较快方案 B 的 20 tick；
  未成功 → ``None``（N/A）。
- ``map27.communication_blackout_ticks``：中继 OFFLINE 期间推进的 tick 数；修复动作
  自身的 2 tick 计入，修复完成当 tick 起不再计入。
- ``map27.resource_conflicts``：统一载荷/能源冲突 ``RESOURCE_CONFLICT`` 的次数
  （货舱溢出 + 充电无空货位；V7 卡片公式的两种来源）。

## 2. 与同世界另两图的区别

- **MAP-25**（简单）：本图与同世界另两图的机制差异：MAP-26 有诊断反馈与备件预算、核心是错误后修正；MAP-27 是多主体协同。本图是单 Agent 单线程流程，故障固定且单一，核心是“别在准备阶段漏步”：穿服、挂绳、排压、检查、诊断、维修、返舱之间的前置关系不可交换。
- **MAP-26**（中等）：本图不是“找到一个零件并安装”的收集任务。它把一个同样的通信中断报警，三种互斥故障、粗糙历史日志、可重复但有区别力的台架测试、错误替换反馈、可回滚备件和递增的同类重试成本串成一条自我纠错链。没有全局倒计时；失败来自把仅有的两枚备件消耗在错误部件上。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`battery`, `battery_capacity`, `cargo`, `cargo_capacity`, `charger_cells_remaining`, `crew_alive`, `goal`, `local_edges`, `location`, `objectives`, `oxygen`, `relay_state`, `sample_state`, `supplies_here`, `survivor_state`, `tick`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`battery`, `blackout_ticks`, `cargo`, `cargo_errors`, `charge_cells`, `charge_cells_used`, `crew_alive`, `location`, `objective_ticks`, `objectives`, `oxygen`, `partial_completion`, `relay_state`, `resource_conflict_errors`, `sample_state`, `stock`, `survivor_state`, `violations`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `charge`：无附加字段
- `drive`：`to`
- `load`：`item_id`
- `repair_relay`：无附加字段
- `rescue`：`operation`
- `rescue`：`item_id`, `operation`
- `sample`：`item_id`
- `submit`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：两格货舱互斥；14 电/18 氧按道路原子并行消耗；P–E 四 tick、S–E 一 tick；全目标成功。

- 成功码：`ALL_OBJECTIVES_COMPLETE`
- 失败码：`CREW_OXYGEN_DEPLETED`, `OBJECTIVES_INCOMPLETE_AT_BASE`, `VEHICLE_STRANDED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map27.communication_blackout_ticks` | guardrail | lower_is_better | count(communication == down) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.critical_path_delay` | primary | lower_is_better | actual_critical_path_ticks - reference_critical_path_ticks | 参考关键路径 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.joint_task_completion_rate` | primary | higher_is_better | completed_joint_tasks / required_joint_tasks | 必需协同任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map27.resource_conflicts` | diagnostic | lower_is_better | count(RESOURCE_CONFLICT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：relay_first_remote_road（17 步）, stabilize_first_short_road（16 步）
- 手算 fixture：stabilize_first_full_success（16 步）, cargo_and_charger_slot_conflict（5 步）, remote_road_without_charge_is_stranded（11 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-27` → `MAP-27: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | VEHICLE_STRANDED | 8 | 0.00580636 | `V8-MAP-27-R0-20261017T103727Z-7d22e4e5` | `communication_blackout_ticks`=13; `joint_task_completion_rate`=0.0; `resource_conflicts`=0 |
| 1 | failure | False | VEHICLE_STRANDED | 10 | 0.00448080 | `V8-MAP-27-R1-20261017T103810Z-8a598271` | `communication_blackout_ticks`=12; `joint_task_completion_rate`=0.0; `resource_conflicts`=0 |
| 2 | failure | False | VEHICLE_STRANDED | 6 | 0.00210904 | `V8-MAP-27-R2-20261017T103905Z-0f942fc4` | `communication_blackout_ticks`=14; `joint_task_completion_rate`=0.0; `resource_conflicts`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

成功要求全部目标；部分完成单列，不折算为成功。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
