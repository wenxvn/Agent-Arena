# MAP-19 定稿：温度临界点

| 字段 | 值 |
|---|---|
| 世界 | volcano |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `5c9491adac611088209ce6c37b98c1a421bc49e039adeed54398a6ce34db96f8` |
| rule_hash | `28b181b4b82e63005302789504eb74fb4a81f1186fb808ba3b1ced749b88328d` |
| prompt_hash | `4750ba4b14041503f7026658e420ce4c43d1746fdf4768e445a6690b753c49e2` |
| metric_schema_hash | `04755621dae6661ae0bbf1e99f2727d8a1ddc2f7f6f51ab9be6777913d6de3fd` |
| oracle_hash | `ce9e138b4dafc6e04a684a939935341d928ac3061727c603833522ac021704e3` |
| commit | `223e532ed9b9613ba96e06d129b41fb1f52b37bc` |

## 1. 设计意图与独特机制

此图把挑战压在“今天发出的冷却命令，到两tick后才成为有效冷却”这一条时间因果上。A、B、C三片热交换区起温相近但安全余量不同；玩家要用逐区实测、延迟队列和负荷控制推算下一次热状态，连续维持12tick并累计至少20点产能。它没有地图移动、故障倒计时或随机温度事件。

MAP-19｜温度临界点：三片独立热区、两 tick 冷却延迟与前馈负荷控制。

本图与同世界另两图的机制差异：MAP-20 是带 20% 损耗的互联管网、控制无延迟；
MAP-21 是隐藏喷发时刻下的风险决策。本图没有移动、没有随机事件、也没有跨区
热传导，主机制是“今天下达的冷却阀向量到 tick+2 才有效”这一条固定时间因果，
玩家必须提前两 tick 预判三区温度并用负荷档位交换产能。

指标口径（与 V7 卡片一致）：
- ``temperature_exceedance_area``：Σ_zone Σ_tick ``max(0, T - 8)``，只累计已结算
  tick；熔断 tick 的温度也记录并累计，之后不再增加。
- ``oscillation_count``：三区各自相邻非零 ``dT`` 的符号变化次数之和。
- ``critical_overheat_ticks``：已记录状态中 ``T > 10`` 的区·tick 数。
- ``coolant_exhausted``：``terminal_reason == COOLANT_EXHAUSTED`` 的 0/1。当前
  运行时不设冷却剂池，该原因码不可达，因此合法结果为 0。

## 2. 与同世界另两图的区别

- **MAP-20**（中等）：本图与同世界另两图的机制差异：MAP-19 是三片互不传导的独立回路、共享总阀量且命令延迟两 tick；MAP-21 是隐藏喷发时刻下的风险决策。本图没有时滞与随机事件，主机制是“水源 60 刻度 + 单支管 25 刻度 + 区间旁路必损 20% + 区阀 4/4/3”，玩家必须同时决定直供、旁路方向/流量和负荷档，用邻区余量给热点续命。
- **MAP-21**（困难）：本图与同世界另两图的机制差异：MAP-19/20 都是确定性的热/水控制题；本图没有温度或流量，主机制是“喷发时刻只可能是 12/16/20 且不可见，唯一信息动作是一次耗时 2 tick 的有噪测量”。玩家要在“多取一档样品”和“赶上最早喷发”之间停手。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`active_cooling`, `current_load_levels`, `goal`, `last_temperature_reading`, `pending_cooling_commands`, `production_points`, `production_target`, `temperature_bands`, `tick`, `ticks_remaining`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`active_cooling`, `counters`, `deltas`, `forecast_errors`, `loads`, `pending`, `production`, `settled_states`, `status`, `temperatures`, `terminal_reason`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `adjust_loads`：`adjust_loads`
- `forecast_next`：`forecast_next`
- `read_temperature`：`station`
- `set_cooling`：`set_cooling`
- `wait`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：冷却命令延迟 2 tick 生效；三区独立；负荷档交换产能；越界面积按已结算 tick 累计。

- 成功码：`PRODUCTION_TARGET_MET`
- 失败码：`PRODUCTION_BELOW_20`, `THERMAL_RUNAWAY`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map19.coolant_exhausted` | diagnostic | lower_is_better | 1 if terminal_reason==COOLANT_EXHAUSTED else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.critical_overheat_ticks` | guardrail | lower_is_better | count(T > critical_limit) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.oscillation_count` | primary | lower_is_better | count(sign changes of dT/dt within band) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map19.temperature_exceedance_area` | primary | lower_is_better | Σ max(0, T_t - T_safe) × Δt | 有效 tick 数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：early_cooling（27 步）, exact_production_boundary（27 步）
- 手算 fixture：early_cooling_area_and_production（27 步）, production_exactly_twenty_succeeds（27 步）, valve_budget_rejected_atomically（1 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-19` → `MAP-19: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | missing | None | None | — | None | `None` | — |
| 1 | missing | None | None | — | None | `None` | — |
| 2 | missing | None | None | — | None | `None` | — |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

越界面积按裁判侧精确温度计算；V7 卡片的 20 为笔误，实测早期冷却路径为 22。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
