# MAP-12 定稿：极夜三十天

| 字段 | 值 |
|---|---|
| 世界 | polar |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `5d942a953707ad85e978b4c36a7364ed6d1e6f326c4cd25f79977c4eefe702be` |
| rule_hash | `ec0b473f08d1aa5f2ce6e7288b7877ab07ba66fe8123c772e91f69f216d76bba` |
| prompt_hash | `fee5dd65ba07390484be5a8c8e8aceb4f23b7c7b5c0271d10a5d899f5c3a213b` |
| metric_schema_hash | `a550eb48e76727fe4fafaf2ab67e09cb5d03d5fc02ed0bf644b0dca73e860a06` |
| oracle_hash | `3b9bceac95c40e9bdfeb166f2cc82cf15ec2f74b846da61e44a8f4c0b1f18ea3` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

本图不是一次性把资源凑齐，而是把30天按顺序排班：燃料要先留给每天的供暖，再负担温室的连续供能；食物收成必须沿站点逐段送回居住舱；零件要提前从仓库运到能源站，赶上每7天的控制器磨损；实验室还要连续做满四轮三日研究。每天只有两个劳动动作槽，维修、转运和研究会直接争同一份日历。

MAP-12｜极夜三十天：30 天库存、维修与连续研究串的跨期排程。

本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池的一次性分配），
MAP-11 是短时空间搜救与带噪风暴抽签；本图没有空间移动、风暴或救援对象，核心是
每日两个劳动槽在供暖、温室连续供能、零件两段转运、四次控制器磨损与四轮三日
研究串之间的争用，加上燃料/口粮库存安全垫。

动作契约：每天恰好两个劳动槽，每个动作（含被拒绝的动作）消耗 1 tick / 1 槽；
``wait`` 是空转槽。当日第二个动作之后的 ``_after_tick`` 执行一次日结算，因此
论文 ``oracle_trace.jsonl`` 的“每日 0–2 条行动”可直接展平为逐步动作，日号 =
``(tick_count + 1) // 2``。

指标口径（与 docs/v7/maps/MAP-12.md 一致）：

- ``map12.survival_days``：日结算时供暖与口粮均正常的天数 / 30；提前失败照实计。
- ``map12.minimum_safety_margin``：``min_t(fuel_E_t−1, food_H_t−1)``，t 取每日
  结算快照；尚无快照 → None（UNAVAILABLE）。
- ``map12.heating_outage_days``：当日供暖关闭或无燃料即记 1 天。
- ``map12.plan_breach_days``：出现被拒绝的劳动动作，或磨损日结束时控制器仍离线
  的天数（每类同日只记 1 天）。
- ``map12.fuel_consumed``：``40 − fuel_E``（当前账本，含供暖与温室燃料）。

## 2. 与同世界另两图的区别

- **MAP-10**（简单）：本图与同世界另两图的机制差异：MAP-11 是带噪天气下的搜索与队员生命窗，MAP-12 是30 天跨期库存与劳动槽排程；本图是单期（最长十余 tick）燃料分仓问题——基地油库只能烧给暖气，随身燃料只能用于雪地车与发电机，两者不能互相挪用，且偶数 tick 的供暖结算让“走多快”直接影响基地热量。这里没有 MAP-09 式的故障连锁。
- **MAP-11**（中等）：本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池、发电机缺油/基地冻结），MAP-12 是 30 天跨期库存与劳动槽排程（无空间搜索、无风暴抽签）；本图是短时（≤25 tick）空间搜救，核心变量是四次相关风暴抽签、队员生命窗、侦察后验与负重返程每段 +1 tick。三图的失败码与资源账本互不重叠。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`consecutive_food_shortage_days`, `consecutive_heat_shortage_days`, `controller_online`, `day`, `fuel_E`, `goal`, `greenhouse_crop_planted`, `greenhouse_powered`, `greenhouse_powered_streak`, `heater_on`, `labor_actions_used`, `labor_slots_remaining`, `maintenance_today`, `node_inventories`, `research_points`, `research_streak`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`breach_days`, `controller_online`, `crop_planted`, `day`, `food`, `food_consumed`, `food_streak`, `fuel_E`, `greenhouse_fuel_spent`, `greenhouse_powered`, `greenhouse_streak`, `harvested_food`, `heat_fuel_spent`, `heat_outage_days`, `heat_streak`, `heater_on`, `parts`, `repairs`, `research_points`, `research_streak`, `snapshots`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `plant_batch`：无附加字段
- `repair_controller`：无附加字段
- `research`：无附加字段
- `set_heating`：`choice`
- `start_greenhouse_power`：无附加字段
- `transfer`：`commodity`, `edge_id`, `from_node`, `quantity`, `to_node`
- `wait`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：每日 2 个劳动槽；顺序为动作→资源→欠供判定→日推进；连续欠供触发失败。

- 成功码：`SURVIVED_AND_RESEARCHED`
- 失败码：`FOOD_SHORTAGE_STREAK`, `HEAT_SHORTAGE_STREAK`, `RESEARCH_TARGET_MISSED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map12.fuel_consumed` | diagnostic | lower_is_better | 40 - fuel_E_30 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.heating_outage_days` | guardrail | lower_is_better | count(heating outage days) | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.minimum_safety_margin` | primary | higher_is_better | min_t(inventory_t - safety_stock_t) | 各日结算点 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.plan_breach_days` | diagnostic | lower_is_better | count(days with missed planned action) | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map12.survival_days` | primary | higher_is_better | days_with_all_survival_constraints / 30 | 30 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：research_priority（60 步）, safety_buffer（60 步）
- 手算 fixture：research_priority_plan_a（60 步）, heating_off_two_days_with_full_fuel（4 步）, rejected_repair_is_a_plan_breach（4 步）, thirty_days_passive_research_target_missed（60 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-12` → `MAP-12: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | RESEARCH_TARGET_MISSED | 60 | 0.03977192 | `V8-MAP-12-R0-20261017T113334Z-e36d02ca` | `fuel_consumed`=33; `heating_outage_days`=0; `minimum_safety_margin`=-1; `plan_breach_days`=25 |
| 1 | failure | False | RESEARCH_TARGET_MISSED | 60 | 0.04074212 | `V8-MAP-12-R1-20261017T114002Z-8090aae0` | `fuel_consumed`=35; `heating_outage_days`=0; `minimum_safety_margin`=-1; `plan_breach_days`=23 |
| 2 | failure | False | RESEARCH_TARGET_MISSED | 60 | 0.03448492 | `V8-MAP-12-R2-20261017T114556Z-d7fef335` | `fuel_consumed`=35; `heating_outage_days`=0; `minimum_safety_margin`=-1; `plan_breach_days`=25 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

日结算顺序已冻结（动作→资源→欠供→日推进）；连续欠供阈值由 V8-DCR-007 固定。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
