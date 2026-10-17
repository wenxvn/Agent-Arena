# MAP-10 定稿：最后一桶燃料

| 字段 | 值 |
|---|---|
| 世界 | polar |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `c181e297e1007c5b20c6c21e2e424080fac3f5a0270ffecde366f0cef83f18a0` |
| rule_hash | `d4bddf5702e6ae32487dbc92692cd9cb303b5a2b2ab9ff98274348e71215f74d` |
| prompt_hash | `9a41e1ad55acab564369ef6b518f668366cad07b4a30280f2b8ce254cc925b41` |
| metric_schema_hash | `404a53fb3f561dd1b3360b7c3d07eacaa01736405b0b19716ebf1d4bf543a3d1` |
| oracle_hash | `ac03fd734bec643647bb18c2233160f1795e053ac1c07a61fe84a21af3fda43d` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

本图把燃料拆成三条彼此争用、位置不同的用途：B 的燃料库维持远端基地供暖；随身燃料要送到 E 点燃发电机；E-W 雪地车捷径也从随身燃料扣款。路线的关键不是“尽可能快”，而是决定哪些燃料先离开基地、用多少时间换运输成本，以及基地热量能维持到什么时候。

MAP-10｜最后一桶燃料：同一 12 单位燃料池的运输位置与时间取舍。

本图与同世界另两图的机制差异：MAP-11 是带噪天气下的搜索与队员生命窗，MAP-12 是
30 天跨期库存与劳动槽排程；本图是单期（最长十余 tick）燃料分仓问题——基地油库只
能烧给暖气，随身燃料只能用于雪地车与发电机，两者不能互相挪用，且偶数 tick 的
供暖结算让“走多快”直接影响基地热量。这里没有 MAP-09 式的故障连锁。

指标口径（与 docs/v7/maps/MAP-10.md 一致）：
- ``fuel_consumed`` = 12 −（终局基地油库 + 随身燃料）；账本始终
  ``fuel_depot + carried_fuel + fuel_spent = 12``。
- ``key_task_fuel_efficiency`` = 完成的必需任务数（发电机启动 + 发报 = 0..2）/
  ``fuel_consumed``；燃料消耗为 0 时分母为 0，即 N/A。
- ``minimum_task_guarantee`` = 上述必需任务完成数（分母固定 2）。
- ``minimum_base_temperature`` = 逐 tick 结算后的最低基地温度（初值 5）。
- ``base_frozen`` = 1 当且仅当 ``terminal_reason == BASE_FROZEN``。

## 2. 与同世界另两图的区别

- **MAP-11**（中等）：本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池、发电机缺油/基地冻结），MAP-12 是 30 天跨期库存与劳动槽排程（无空间搜索、无风暴抽签）；本图是短时（≤25 tick）空间搜救，核心变量是四次相关风暴抽签、队员生命窗、侦察后验与负重返程每段 +1 tick。三图的失败码与资源账本互不重叠。
- **MAP-12**（困难）：本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池的一次性分配），MAP-11 是短时空间搜救与带噪风暴抽签；本图没有空间移动、风暴或救援对象，核心是每日两个劳动槽在供暖、温室连续供能、零件两段转运、四次控制器磨损与四轮三日研究串之间的争用，加上燃料/口粮库存安全垫。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`base_temperature`, `carried_fuel`, `carry_capacity`, `fuel_depot`, `generator_online`, `goal`, `heater_on`, `location`, `tick`, `transmission_complete`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`base_temperature`, `carried_fuel`, `fuel_depot`, `fuel_spent`, `generator_fuel_spent`, `generator_online`, `heater_fuel_spent`, `heater_on`, `location`, `minimum_base_temperature`, `snowmobile_fuel_spent`, `transmission_complete`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `activate_generator`：无附加字段
- `drive_snowmobile`：`direction`, `edge_id`
- `drive_snowmobile`：`edge_id`
- `load_fuel`：`quantity`
- `set_heating`：`choice`
- `transmit`：无附加字段
- `wait`：`ticks`
- `walk`：`edge_id`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：偶数 tick 结算供暖；基地油库与随身燃料不可互挪；超载必须先转运。

- 成功码：`TRANSMISSION_COMPLETE`
- 失败码：`BASE_FROZEN`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map10.base_frozen` | guardrail | lower_is_better | 1 if terminal_reason==BASE_FROZEN else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.fuel_consumed` | diagnostic | lower_is_better | 12 - (fuel_depot + carried_fuel) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.key_task_fuel_efficiency` | primary | higher_is_better | completed_required_tasks / fuel_consumed | 燃料消耗；0 耗则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.minimum_base_temperature` | guardrail | higher_is_better | min_t base_temperature_t | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map10.minimum_task_guarantee` | primary | higher_is_better | count(guaranteed_tasks completed) | 必需保障任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：walk_keep_fuel（5 步）, snowmobile_shortcut（6 步）
- 手算 fixture：walk_route_keeps_base_fuel（5 步）, shortcut_with_four_units_starves_generator（4 步）, over_capacity_load_is_refused_without_transfer（1 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-10` → `MAP-10: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | GENERATOR_FUEL_SHORTAGE | 2 | 0.001246 | `V8-MAP-10-R0-20261017T081851Z-1441712c` | `base_frozen`=0; `fuel_consumed`=2; `key_task_fuel_efficiency`=0.0; `minimum_base_temperature`=5 |
| 1 | failure | False | GENERATOR_FUEL_SHORTAGE | 5 | 0.00193544 | `V8-MAP-10-R1-20261017T081925Z-e76dcf0a` | `base_frozen`=0; `fuel_consumed`=7; `key_task_fuel_efficiency`=0.0; `minimum_base_temperature`=5 |
| 2 | failure | False | GENERATOR_FUEL_SHORTAGE | 2 | 0.00020976 | `V8-MAP-10-R2-20261017T081940Z-134cae46` | `base_frozen`=0; `fuel_consumed`=2; `key_task_fuel_efficiency`=0.0; `minimum_base_temperature`=5 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

单期燃料分仓题，无随机事件；燃料池不可互挪是核心约束。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
