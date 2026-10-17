# MAP-21 定稿：喷发倒计时

| 字段 | 值 |
|---|---|
| 世界 | volcano |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `9bd77d5dcb8ae60fe9cd78bbc9343e9fd13d316ff46c57e75f1fa96b679085f9` |
| rule_hash | `59675a2c82400a7f571fedecfeed78ebea4f72e963778a0efd58816e4f08439e` |
| prompt_hash | `d1480bc9838f9d5b9f8b9af0e732fa38eef85b4a7ea692b03da6314722df1338` |
| metric_schema_hash | `98f4748000a0c1505103576ce538cda62050a1eb1dda71fd3ae3d87724f69ed9` |
| oracle_hash | `959fd1c97bcd244c681267a8071dbb0b1c97775bb14b79c84be366fc69376322` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

MAP21不是“给玩家一个倒计时，再决定去不去出口”。这张图把危险时间藏在三个有先验概率的离散时刻中，玩家只能花两tick做一次有噪测量，再根据不等同于真相的报告决定停手、取低阶样、加固中阶样品，或赌更高价值的深部样品。短直撤路保人但放弃科研；仓储链线允许边取样边撤离；到S的深部样品价值高，却来不及躲过最早喷发。

MAP-21｜喷发倒计时：隐藏喷发时刻、贝叶斯测量与撤离停手决策。

本图与同世界另两图的机制差异：MAP-19/20 都是确定性的热/水控制题；本图没有
温度或流量，主机制是“喷发时刻只可能是 12/16/20 且不可见，唯一信息动作是一次
耗时 2 tick 的有噪测量”。玩家要在“多取一档样品”和“赶上最早喷发”之间停手。

指标口径（与 V7 卡片一致）：
- ``risk_exposure_integral`` = Σ_tick ``P(T <= t | 当前公开后验)``，只累计仍在 E
  之外且尚未死亡的 tick；抵 E 的 tick 不计，死亡 tick 计入。
- ``evacuation_coverage`` = 已撤出单位 / 已投入单位；单位 = 人员 1 + 已采样品 1
  + 已取得测量记录 1。
- ``false_safety_claims``：现有动作集没有“安全承诺”动作，按 V8-DCR-021 返回
  ``None``（UNAVAILABLE），不报假 0。
- ``late_evacuation``：终局为 ``FATAL_ERUPTION`` 记 1，成功撤离记 0，运行中为
  ``None``。

## 2. 与同世界另两图的区别

- **MAP-19**（简单）：本图与同世界另两图的机制差异：MAP-20 是带 20% 损耗的互联管网、控制无延迟；MAP-21 是隐藏喷发时刻下的风险决策。本图没有移动、没有随机事件、也没有跨区热传导，主机制是“今天下达的冷却阀向量到 tick+2 才有效”这一条固定时间因果，玩家必须提前两 tick 预判三区温度并用负荷档位交换产能。
- **MAP-20**（中等）：本图与同世界另两图的机制差异：MAP-19 是三片互不传导的独立回路、共享总阀量且命令延迟两 tick；MAP-21 是隐藏喷发时刻下的风险决策。本图没有时滞与随机事件，主机制是“水源 60 刻度 + 单支管 25 刻度 + 区间旁路必损 20% + 区阀 4/4/3”，玩家必须同时决定直供、旁路方向/流量和负荷档，用邻区余量给热点续命。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`available_edges`, `carried_sample_tier`, `elapsed_tick`, `goal`, `in_transit_edge`, `location`, `measurement_available`, `posterior_over_eruption_ticks`, `reinforcement_kit_available`, `returned_measurement`, `visible_local_sample_tier`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`carried_sample`, `counters`, `eruption_tick`, `exposure`, `location`, `measurement_outcome`, `posterior`, `reinforced_site`, `sample_points`, `status`, `terminal_reason`, `terminal_score`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `collect_and_carry_sample`：`sample_id`
- `measure`：无附加字段
- `move`：`edge_id`
- `reinforce_sample_case`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：喷发时刻只可能为 12/16/20 且隐藏；测量耗 2 tick 且有噪；停留过久直接致命。

- 成功码：`EVACUATED_BEFORE_ERUPTION`
- 失败码：`FATAL_ERUPTION`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map21.evacuation_coverage` | primary | higher_is_better | evacuated_units / total_units | 总撤离单位 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.false_safety_claims` | guardrail | lower_is_better | count(FALSE_SAFETY_CLAIM) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.late_evacuation` | diagnostic | lower_is_better | 1 if eruption_tick < last_evacuation_tick else 0 | 发生喷发的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map21.risk_exposure_integral` | primary | lower_is_better | Σ_t risk_t × people_at_risk_t | 有效 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：exact_boundary_medium_sample（5 步）, early_evacuation（1 步）, deep_reinforced_sample（6 步）
- 手算 fixture：medium_sample_arrives_at_twelve（5 步）, deep_sample_exposure_until_fourteen（6 步）, staying_past_eruption_is_fatal（7 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-21` → `MAP-21: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | success | True | EVACUATED_BEFORE_ERUPTION | 2 | 0.0010214 | `V8-MAP-21-R0-20261017T094201Z-a4e73f43` | `evacuation_coverage`=1.0; `late_evacuation`=0; `risk_exposure_integral`=0.0 |
| 1 | success | True | EVACUATED_BEFORE_ERUPTION | 1 | 0.00013024 | `V8-MAP-21-R1-20261017T094213Z-3d9c410d` | `evacuation_coverage`=1.0; `late_evacuation`=0; `risk_exposure_integral`=0.0 |
| 2 | success | True | EVACUATED_BEFORE_ERUPTION | 2 | 0.00027476 | `V8-MAP-21-R2-20261017T094219Z-6177107b` | `evacuation_coverage`=1.0; `late_evacuation`=0; `risk_exposure_integral`=0.0 |

三次重复成功 3/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

`false_safety_claims` 无可靠来源，返回 `None`；公开后验提示属信息可用性条件。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
