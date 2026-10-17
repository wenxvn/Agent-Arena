# MAP-15 定稿：会变化的迷宫

| 字段 | 值 |
|---|---|
| 世界 | pyramid |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `99b6ee5cd8aa556143afd35c095fc319d448a8c0c14864704246c005326c9e90` |
| rule_hash | `7d8322b90d7c67cf77d8cd39bc98bc8327c56097de34c5ffa35310fa3cf12e4f` |
| prompt_hash | `54fa0fb08673fd5eb63b412fc0fabc2c68c317b577ee658dbf0db9e498da4efc` |
| metric_schema_hash | `5294368961d55a133851ae06f72438a2b6ea9cab0a233795436af1e9e8173f44` |
| oracle_hash | `0744583b34ca7836cb9e485564d03fb269bb47e1bcfc3d16f5fdecdb1656b446` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

本图把训练样例与测试迁移拆开：A/B/C逐室给三个不同的门色排列，只有一次成功通行会形成一条有标签样例；T把门色扩为四种且重排，不回到训练区。玩家要迁移“墙符号色 × 全局 tick 奇偶”的规则，而不是背门号或训练序列。

MAP-15｜会变化的迷宫：四色互补规则、奇偶相位切换与未见状态迁移。

本图与同世界另两图的机制差异：MAP-13 的碑文约束静态且全真；MAP-14 的规则静态、难点
是不可靠证词与问询预算；本图没有证词，规则本身随全局 tick 奇偶切换——偶数 tick 目标色
等于墙符号色，奇数 tick 等于其互补色（红↔蓝、金↔绿），同一面墙在不同相位要求不同门。
玩家须从 A/B/C 三间训练室的成功样例迁移到 T 的四色未见布局。

动作契约：
- ``choose_door{slot_index}``：按动作开始时的 tick 判定；通过则前进 A→B→C→T→EXIT，
  错误留在原区域、扣 1 枚资源并推进 1 tick。
- ``inspect_symbols{area}``：0 tick，只公开当前区域墙色与临时槽位门色。
- ``record_rule{rule_id, supporting_sample_ids}``：0 tick，只记录玩家假设，不判对错。
- ``predict_transition{answer}``：0 tick，只在 T 可用，提交“当前 tick 目标门色”的预测；
  下一次 T 的 ``choose_door`` 结算该预测。若整局没有显式预测，则用 T 的首次选择作为
  “未见状态预测”代理（与 V7 卡片一致）。

指标口径（与 V7 卡片一致）：
- ``unseen_transition_accuracy``：已结算的 T 预测中正确数 / 已结算预测数；显式预测优先，
  否则以 T 首次选择为代理；未进入 T 记 0/0（N/A）。
- ``probes_to_target``：成功前的 ``choose_door`` 次数；失败局按卡片记 N/A（``None``）。
- ``invalid_transitions``：错误门选择次数，结果码 ``INVALID_TRANSITION``。
- ``loop_states``：同一区域、同一动作前奇偶下重复出现错误选择的次数。
- ``reset_losses``：每次错误同时损失 1 枚资源与 1 个额外 tick，故为
  ``资源损失 + 额外 tick = 2 × 错误次数``；资源先耗尽时优先 ``RESOURCE_DEPLETED``。

## 2. 与同世界另两图的区别

- **MAP-13**（简单）：本图与同世界另两图的机制差异：MAP-14 的陈述有真假与说谎者，需在锁型×诚实者假设中找一致解；MAP-15 的规则随 tick 奇偶变化，需要归纳与迁移；本图五条信息全部为真、规则静态，核心是把星形移动拓扑与碑文阅读序 `N→E→S→W` 分开，逐条传播约束到唯一排列，并在最多两次错误开门内完成。失败码与状态变量与另两图不重叠。
- **MAP-14**（中等）：本图与同世界另两图的机制差异：MAP-13 的碑文全部为真、约束静态；MAP-15 的规则随全局 tick 奇偶切换；本图规则静态，但六条证词只有恰一名祭司全局如实、另外两人逐命题反报。玩家要在 4 问预算内维护“锁型 × 诚实者”九态一致假设，再到审判门承担最终验证。共享严格模型把 ``configuration`` / ``configuration_candidate`` 定义为整数列表，故本图用 ``choice`` 携带锁型候选、用 ``person_id`` 携带诚实者候选、用 ``support_evidence_ids``携带已观察证据 ID；``claim_id`` 携带命题 ID。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`area`, `current_door_colors_in_ephemeral_slot_order_if_inspected`, `current_tick`, `current_tick_parity`, `current_wall_symbol_color_if_inspected`, `gate_open`, `goal`, `inspected_current_area`, `recorded_rule_hypothesis`, `test_wrong_attempts`, `test_wrong_attempts_remaining`, `training_sample_log`, `wrong_attempt_resources`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`area`, `door_choices`, `gate_open`, `inspected_area`, `invalid_transitions`, `judge_target_color`, `loop_states`, `pending_prediction`, `predictions`, `recorded_rule`, `resource_losses`, `resources`, `samples`, `test_errors`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `choose_door`：`slot_index`
- `inspect_symbols`：`area`
- `predict_transition`：`answer`
- `record_rule`：`rule_id`, `supporting_sample_ids`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：规则随全局 tick 奇偶切换；测试错误限 2 次；资源耗尽与测试上限分开。

- 成功码：`GATE_OPENED`
- 失败码：`RESOURCE_DEPLETED`, `TEST_WRONG_LIMIT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map15.invalid_transitions` | guardrail | lower_is_better | count(INVALID_TRANSITION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.loop_states` | diagnostic | lower_is_better | count(visited state re-entered) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.probes_to_target` | primary | lower_is_better | count(probe actions before target) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.reset_losses` | diagnostic | lower_is_better | resource_units_lost + extra_ticks | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map15.unseen_transition_accuracy` | primary | higher_is_better | correct_unseen_predictions / evaluable_unseen_predictions | 可评估未见预测数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：explicit_rule_zero_error（9 步）, implicit_one_test_error_recovery（9 步）
- 手算 fixture：zero_error_with_recorded_rule（9 步）, one_test_error_then_recalculate_parity（7 步）, explicit_unseen_prediction_is_scored（6 步）, second_test_error_hits_test_wrong_limit（5 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-15` → `MAP-15: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | success | True | GATE_OPENED | 11 | 0.00648664 | `V8-MAP-15-R0-20261017T090948Z-551115e9` | `invalid_transitions`=1; `loop_states`=0; `probes_to_target`=5; `reset_losses`=2 |
| 1 | success | True | GATE_OPENED | 12 | 0.00656380 | `V8-MAP-15-R1-20261017T091043Z-8ae2681f` | `invalid_transitions`=1; `loop_states`=0; `probes_to_target`=5; `reset_losses`=2 |
| 2 | success | True | GATE_OPENED | 14 | 0.00750916 | `V8-MAP-15-R2-20261017T091131Z-9d9d9075` | `invalid_transitions`=3; `loop_states`=0; `probes_to_target`=7; `reset_losses`=6 |

三次重复成功 3/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

未见状态预测用“首次选择”作代理，不能区分“预测对但执行错”。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
