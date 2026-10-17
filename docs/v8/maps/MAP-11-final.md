# MAP-11 定稿：失联的小队

| 字段 | 值 |
|---|---|
| 世界 | polar |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `bc26ce92ed45beb82b407c4970bf7174986a8b74edc5348dbadedd5d16a9d296` |
| rule_hash | `86334e9a3fa67b50ad93d3962a6b64b3a1bf20a52611747701b400edaaaa0e88` |
| prompt_hash | `d8def691ba3268f36ca281939bff8f1571ed229d6152bb9f6a98db7ec4f126ad` |
| metric_schema_hash | `416566d683ef3d73bc57a04842ff14e8be40bfeba6249a584a6d69a7ef832fc8` |
| oracle_hash | `d10e23484f8db925aa5c407f6ff2fbf1f5ad22e1ce8e1720a24ab859b594de04` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

这是一道有噪声预报的风险策略题：山口短路能更早抵达队员，但四次穿越都要付补给并抽取冻伤事件；经补给站和气象站的长路免受暴风抽签，却慢得多。侦察只改变对未来暴风的概率判断，不揭开本 seed 的暴风序列。救到人以后，返程每一段都因负重多花1 tick。

MAP-11｜失联的小队：带噪天气下的短线风险与长线安全路线选择。

本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池、发电机缺油/
基地冻结），MAP-12 是 30 天跨期库存与劳动槽排程（无空间搜索、无风暴抽签）；
本图是短时（≤25 tick）空间搜救，核心变量是四次相关风暴抽签、队员生命窗、
侦察后验与负重返程每段 +1 tick。三图的失败码与资源账本互不重叠。

指标口径（与 docs/v7/maps/MAP-11.md 一致）：

- ``map11.rescue_count``：成功带回 B 的队员数，0/1；未终局或救援后失败均为 0。
- ``map11.resource_cost_per_rescue``：已耗补给 / 获救人数；分母 0 → N/A。
- ``map11.rescuer_hypothermia``：``BODY_HEAT_DEPLETED`` 终局计数，0/1。
- ``map11.abandoned_reachable_targets``：终局时队员未获救且生命仍 >0 的人数，0/1。
- ``map11.first_clue_delay``：首次 ``scout`` 结果落地 tick；未侦察 → None。

隐藏真值（气象态、逐段风暴掩码）只进 ``judge_state()``；公开面只有已走过的
天气、噪声信号与递推后验。

## 2. 与同世界另两图的区别

- **MAP-10**（简单）：本图与同世界另两图的机制差异：MAP-11 是带噪天气下的搜索与队员生命窗，MAP-12 是30 天跨期库存与劳动槽排程；本图是单期（最长十余 tick）燃料分仓问题——基地油库只能烧给暖气，随身燃料只能用于雪地车与发电机，两者不能互相挪用，且偶数 tick 的供暖结算让“走多快”直接影响基地热量。这里没有 MAP-09 式的故障连锁。
- **MAP-12**（困难）：本图与同世界另两图的机制差异：MAP-10 是单期燃料分仓（同一油池的一次性分配），MAP-11 是短时空间搜救与带噪风暴抽签；本图没有空间移动、风暴或救援对象，核心是每日两个劳动槽在供暖、温室连续供能、零件两段转运、四次控制器磨损与四轮三日研究串之间的争用，加上燃料/口粮库存安全垫。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`agent_heat`, `carried_supply`, `carried_supply_capacity`, `current_storm`, `forecast_storm_probability_per_short_crossing`, `goal`, `last_scout_signal`, `loaded_return_required`, `location`, `posterior_unstable_probability_belief`, `short_crossings_resolved`, `supply_depot_B`, `teammate_heat`, `teammate_life_remaining`, `teammate_rescued`, `tick`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`agent_heat`, `carried`, `depot`, `hidden_regime`, `hidden_scout_signal`, `hidden_storm_mask`, `location`, `min_agent_heat`, `min_teammate_heat`, `posterior_unstable`, `rescue_tick`, `rests`, `scout_signal`, `scout_tick`, `short_crossings`, `storm_hits`, `supply_spent`, `teammate_heat`, `teammate_life`, `teammate_rescued`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `move`：`direction`, `edge_id`, `loaded_return`
- `move`：`edge_id`, `loaded_return`
- `move`：`edge_id`
- `rescue`：无附加字段
- `rest`：无附加字段
- `resupply`：`quantity`
- `scout`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：四次相关风暴抽签；队员生命窗与负重返程逐段结算；侦察后验只影响风险估计。

- 成功码：`FULL_SAFE_RETURN`
- 失败码：`BODY_HEAT_DEPLETED`, `SUPPLY_SHORTAGE`, `TEAM_LIFE_EXPIRED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map11.abandoned_reachable_targets` | diagnostic | lower_is_better | count(reachable but abandoned survivors) | 初始可救援人数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.first_clue_delay` | diagnostic | lower_is_better | tick(first scout result); no scout -> N/A | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.rescue_count` | primary | higher_is_better | count(rescued survivors) | 失联人数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.rescuer_hypothermia` | guardrail | lower_is_better | count(RESCUER_HYPOTHERMIA) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map11.resource_cost_per_rescue` | primary | lower_is_better | resource_spent / rescued_count | 获救人数；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：quick_short_seed0（6 步）, scout_then_short_seed0（7 步）, scout_then_long_seed7（9 步）
- 手算 fixture：quick_short_success_eight_supplies（6 步）, seven_supplies_cannot_close_short_loop（6 步）, false_negative_scout_two_storms（7 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-11` → `MAP-11: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | SUPPLY_SHORTAGE | 2 | 0.001328 | `V8-MAP-11-R0-20261017T081943Z-1fac09c9` | `abandoned_reachable_targets`=1; `first_clue_delay`=2; `rescue_count`=0; `rescuer_hypothermia`=0 |
| 1 | failure | False | SUPPLY_SHORTAGE | 2 | 0.00077152 | `V8-MAP-11-R1-20261017T081949Z-88d39115` | `abandoned_reachable_targets`=1; `first_clue_delay`=2; `rescue_count`=0; `rescuer_hypothermia`=0 |
| 2 | failure | False | SUPPLY_SHORTAGE | 2 | 0.00029976 | `V8-MAP-11-R2-20261017T081958Z-6bd77165` | `abandoned_reachable_targets`=1; `first_clue_delay`=2; `rescue_count`=0; `rescuer_hypothermia`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

公开后验与基础概率，属信息使用条件；不把它当作模型自主推断的证据。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
