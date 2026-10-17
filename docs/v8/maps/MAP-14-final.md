# MAP-14 定稿：说谎的祭司

| 字段 | 值 |
|---|---|
| 世界 | pyramid |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `61267f92369922d2d30914a51cf765ff6cc500fe18845137751827b0fa7393d0` |
| rule_hash | `1c352a0fd891f588c267746134491cfdd74c53489846547b4754d2d1154b80a2` |
| prompt_hash | `e7bd106cf4984266d975356902274932050725e1c012bf9f058dfe0de0327806` |
| metric_schema_hash | `87e805885613bafae1ce9f81dd0fbf78611589ba6439449d65cde98a956f6673` |
| oracle_hash | `292f0dc0038a59cccc545a24d1f2095cb75b21fb5c0301314eb5dd1da2510b5e` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

这是一个有限真值逻辑关卡。三名祭司不是自由对话 NPC：每人只持两条固定命题，提问只返回 Yes/No；恰有一名祭司在任何命题上如实回答，另外两人永远反报。玩家需从档案、答案与唯一诚实者假设中找出门锁配置。

MAP-14｜说谎的祭司：三锁型 × 三诚实者的九态真值推理与问询预算。

本图与同世界另两图的机制差异：MAP-13 的碑文全部为真、约束静态；MAP-15 的规则随
全局 tick 奇偶切换；本图规则静态，但六条证词只有恰一名祭司全局如实、另外两人逐命题
反报。玩家要在 4 问预算内维护“锁型 × 诚实者”九态一致假设，再到审判门承担最终验证。
共享严格模型把 ``configuration`` / ``configuration_candidate`` 定义为整数列表，故本图
用 ``choice`` 携带锁型候选、用 ``person_id`` 携带诚实者候选、用 ``support_evidence_ids``
携带已观察证据 ID；``claim_id`` 携带命题 ID。

指标口径（与 V7 卡片一致）：
- ``globally_consistent_hypothesis_rate``：每次 ``compare_evidence`` 封存一个
  “锁型 × 诚实者”假设时，按当时已公开的答复、档案与“恰一名诚实者”假设重算该完整
  九态假设是否仍可解释全部陈述；分子为一致假设数，分母为封存假设总数，无封存记
  0/0（N/A）。只评锁型而不评诚实者会把“兼容 A/甲”的歧义藏起来，故本图评完整配对。
- ``minimum_query_gap``：已问数 − 该隐藏状态在冻结六命题真值表上的最少问询数；最少问
  询数由模块在导入时对 9 态 × 全部命题子集穷举得到。欠问时按 0 截尾（登记表要求 ≥ 0）。
- ``query_budget_overruns``：第 5 问及以后被 ``QUERY_BUDGET_EXCEEDED`` 拒绝的次数；
  重复问另记 ``DUPLICATE_QUERY``，不并入本指标。
- ``contradiction_missed``：任一最终提交锁型与已知公开证据矛盾时记 1，否则 0。
- ``queries_used``：实际记入账本的 ``ask`` 次数。

## 2. 与同世界另两图的区别

- **MAP-13**（简单）：本图与同世界另两图的机制差异：MAP-14 的陈述有真假与说谎者，需在锁型×诚实者假设中找一致解；MAP-15 的规则随 tick 奇偶变化，需要归纳与迁移；本图五条信息全部为真、规则静态，核心是把星形移动拓扑与碑文阅读序 `N→E→S→W` 分开，逐条传播约束到唯一排列，并在最多两次错误开门内完成。失败码与状态变量与另两图不重叠。
- **MAP-15**（困难）：本图与同世界另两图的机制差异：MAP-13 的碑文约束静态且全真；MAP-14 的规则静态、难点是不可靠证词与问询预算；本图没有证词，规则本身随全局 tick 奇偶切换——偶数 tick 目标色等于墙符号色，奇数 tick 等于其互补色（红↔蓝、金↔绿），同一面墙在不同相位要求不同门。玩家须从 A/B/C 三间训练室的成功样例迁移到 T 的四色未见布局。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`archive_record_if_read`, `comparison_record`, `gate_open`, `goal`, `location`, `public_statement_cards`, `question_answers`, `questions_remaining`, `questions_used`, `tick`, `visible_edges`, `wrong_submissions`, `wrong_submissions_remaining`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`answers`, `archive_read`, `asked_claim_ids`, `comparison_record`, `configuration`, `counters`, `gate_open`, `location`, `minimum_queries`, `sealed_hypotheses`, `submissions`, `truthful_priest`, `wrong_submissions`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `ask`：`claim_id`
- `compare_evidence`：`choice`, `person_id`, `support_evidence_ids`
- `move`：`edge_id`
- `read_archive`：无附加字段
- `submit_configuration`：`choice`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：4 问预算；维护九态一致假设；第五问被拒绝且不耗 tick；最终错误提交限次。

- 成功码：`GATE_OPENED`
- 失败码：`WRONG_SUBMISSION_LIMIT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map14.contradiction_missed` | diagnostic | lower_is_better | 1 if submit contains known contradiction else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.globally_consistent_hypothesis_rate` | primary | higher_is_better | consistent_hypotheses / submitted_hypotheses | 提交假设数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.minimum_query_gap` | primary | lower_is_better | queries_used - minimum_queries(instance) | 实例最少问询数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.queries_used` | diagnostic | lower_is_better | count(ask) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map14.query_budget_overruns` | guardrail | lower_is_better | count(QUERY_BUDGET_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：archive_then_ask（11 步）, adaptive_without_archive（8 步）
- 手算 fixture：adaptive_three_questions_success（8 步）, archive_exclusion_ignored_then_submit_c（6 步）, fifth_question_is_refused_without_tick（5 步）, correct_lock_with_wrong_priest_still_opens_gate（8 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-14` → `MAP-14: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 38 | 0.02326660 | `V8-MAP-14-R0-20261017T084136Z-c801fa6a` | `contradiction_missed`=0; `minimum_query_gap`=0; `queries_used`=0; `query_budget_overruns`=0 |
| 1 | decision_budget_reached | False | None | 38 | 0.02225512 | `V8-MAP-14-R1-20261017T084459Z-a2091da8` | `contradiction_missed`=0; `minimum_query_gap`=0; `queries_used`=0; `query_budget_overruns`=0 |
| 2 | decision_budget_reached | False | None | 38 | 0.01866248 | `V8-MAP-14-R2-20261017T084729Z-e554717a` | `contradiction_missed`=0; `minimum_query_gap`=0; `queries_used`=0; `query_budget_overruns`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

配置以整数列表表达；第五问被拒绝且不耗 tick 是冻结语义。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
