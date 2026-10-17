# MAP-07 定稿：逆流阀门

| 字段 | 值 |
|---|---|
| 世界 | abyss |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `c18b0b93713e055a2f8bfc162c3befdef1a98de46a15f290767afe38bc2bc81f` |
| rule_hash | `1183d0dea109c7670eb69122eac7bafedf9a0ff3872feb5336d8266dfe336e88` |
| prompt_hash | `7a4bd1042bb5d5c83a333178af6213ac98e11e8c206c288a58296cca5102fac9` |
| metric_schema_hash | `1528fabb3ebbd137674d22701f12bdbb6ebc10802f8cde5e392f6816bc95804e` |
| oracle_hash | `b7a5f5a4edc45f5a35126c5efebcf98a743a3f1f359f59365c272a1d9f2c8a4b` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

本图测 Agent 能否预判一组串接阀门对多个舱室的联合影响。控制顺序很重要：水可以在同一 tick 内经过多个依次开放的阀；旁路 v4 在主线阀之后把剩余水送回 A。错误次序会把水集中到尚未排出的舱，而不是只多花几步。

MAP-07｜逆流阀门：同一 tick 内按 v1→v2→v3→v4→泵 级联的可变水位水路。

本图与同世界另两图的机制差异：MAP-08 用主动测试缩小隐藏漏点的假设集合，
MAP-09 是漏水/电量/供氧/通信的跨系统资源耦合；本图没有行走图，Agent 始终在
控制台 P 远程操作，因果难度来自“一个 tick 内可变水位按固定次序级联”以及
单向回流 v4（C→A）——给 C 降压会把水送回 A，而不是排掉。

指标口径（与 docs/v7/maps/MAP-07.md 一致）：
- ``excess_water_integral``：对每个已完成流水 tick 累加
  ``Σ_{c∈{A,B,C}} max(0, level_c - 2)``；tick 0 不计，流水后立即读数。
- ``correct_direction_rate``：分子是“使总超额水量下降”的成功阀门操作数，
  或总超额水量已为 0 时仍保持 0 的操作；分母是所有成功改变阀门状态、并触发
  随后流水 tick 的操作。平局（>0 且不变）算方向错误。
- ``overpressure_ticks``：A/B/C 任一 ``>8`` 的流水 tick 数。
- ``illegal_valve_combo``：控制台拒绝的“一条命令同时操作多个阀门”的次数
  （``arguments`` 出现 ``valve_id``/``open`` 之外的阀门字段）。真实的水路错误
  组合（例如只开 v1/v4）是合法命令，按设计照常结算并由溢流失败暴露。
- ``interventions``：成功改变状态的阀门开/关与泵启/停次数。

## 2. 与同世界另两图的区别

- **MAP-08**（中等）：本图测 Agent 如何选择能最大幅度缩小故障假设集合的压力实验，并判断何时证据足够、何时应停下实验去修复。三个候选点水位曲线、传感器底噪和房间描述起初完全相同；唯一可分辨来源是主动执行 X/Y 测试。
- **MAP-09**（困难）：本图与同世界另两图的机制差异：MAP-07 只有单一水路内部的顺序转移，水位直接可见、动作只改变水量；MAP-08 用主动测试缩小隐藏漏点假设集。本图没有隐藏故障位置，难点是同一 tick 内的资源循环——E-P 漏水会把泵房水推进动力舱并短路，抽水消耗刚好够发报的电量，断电只影响供氧线路而不回充电池，供氧稳定计数又决定能否发报。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`goal`, `location`, `low_water_streak`, `pipe_diagram`, `pump_active`, `pump_energy`, `pump_power_draw`, `tick`, `valves`, `visible_edges`, `water_levels`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`correct_valve_ops`, `decidable_valve_ops`, `excess_integral`, `illegal_combos`, `interventions`, `location`, `low_water_streak`, `overpressure_ticks`, `prediction_errors`, `pump_active`, `pump_energy`, `valves`, `violations`, `water`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target_id`
- `interact`：`arguments`, `operation`, `target_id`
- `interact`：`operation`, `target_id`
- `wait`：`ticks`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：同一 tick 内按 v1→v2→v3→v4→泵 级联结算；任一舱溢出即失败。

- 成功码：`LOW_WATER_STABLE`
- 失败码：`COMPARTMENT_OVERFLOW_A/B/C（动态舱室码）`
- 机制失败路径：
  - 上游先开导致 A 溢出 → `COMPARTMENT_OVERFLOW_A`
  - v4 单向回流误开 → 回灌 A
  - 合并阀门命令 → 形状拒绝

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map07.correct_direction_rate` | primary | higher_is_better | correct_direction_interventions / decidable interventions | 可判定干预数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.excess_water_integral` | primary | lower_is_better | Σ_t Σ_c max(0, level_c,t - 2) | 有效流水 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.illegal_valve_combo` | diagnostic | lower_is_better | count(INVALID_VALVE_COMBINATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.interventions` | diagnostic | lower_is_better | count(valve open/close) + count(pump start/stop) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map07.overpressure_ticks` | guardrail | lower_is_better | count(pressure > safe_limit) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：downstream_first（6 步）, upstream_staged（8 步）
- 手算 fixture：downstream_first_success（6 步）, bypass_v4_backflow_overflows_A（3 步）, combined_valve_command_is_refused（1 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-07` → `MAP-07: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 30 | 0.02222448 | `V8-MAP-07-R0-20261017T075714Z-beecf3f5` | `excess_water_integral`=180; `illegal_valve_combo`=0; `interventions`=0; `overpressure_ticks`=0 |
| 1 | decision_budget_reached | False | None | 30 | 0.01893456 | `V8-MAP-07-R1-20261017T075858Z-6e19c745` | `excess_water_integral`=180; `illegal_valve_combo`=0; `interventions`=0; `overpressure_ticks`=0 |
| 2 | decision_budget_reached | False | None | 30 | 0.01385244 | `V8-MAP-07-R2-20261017T080115Z-043df7cf` | `excess_water_integral`=180; `illegal_valve_combo`=0; `interventions`=0; `overpressure_ticks`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

溢出失败码带舱室后缀（`COMPARTMENT_OVERFLOW_X`），是同一机制的多实例码。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
