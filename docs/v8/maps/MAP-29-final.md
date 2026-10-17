# MAP-29 定稿：不可靠的证人

| 字段 | 值 |
|---|---|
| 世界 | castle |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `6ea1b4f0f4812258081c15ad2f062c3c3bf81141748c25a3216894d13007d5da` |
| rule_hash | `9549fbc011f9d9aa9352e3ad12219700d08ac6c22a060dac3a297d642753d3e8` |
| prompt_hash | `22cad66d69fd90646dfca500e985430544b84bbdc55e63543a5c8519e6891ec6` |
| metric_schema_hash | `02f9dba16f750cb03255c6ce8a667a2a267280222783b0a1be8784d744460641` |
| oracle_hash | `712d90fc974acfeb44094e4774ca67b92eca27b8faadaaba4ab2d96e7bf99a9c` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

本图考察8次提问预算里的主动信息选择：四位固定NPC各有不同知识边界/偏差，玩家必须决定问谁、用哪种模板、何时停问并转去查物证。NPC回答全部由seed固定的知识表和偏差规则渲染；严禁用自由LLM生成、临场改口或按Agent措辞猜真相。

MAP-29｜不可靠的证人：8 问预算下的证词分诊与物证交叉。

本图与同世界另两图的机制差异：MAP-28 的证据都可靠，难点是四字段双来源交叉；
MAP-30 是长间隔召回与多事件案卷。本图固定四名 NPC、四种不同的知识边界/偏差，
核心是**在有限问询预算里区分“记错”“故意隐瞒”“诚实但不知道”**，并只在物证或
档案交叉验证后才采信时地结论。

案情（裁判侧）：庭院 Y 的银铃在 23:40 响过一次。固定偏差：
- 甲（L）把停在 00:00 的书房钟当成事件钟，误报 00:05（记忆锚定）。
- 乙（K）知道 23:40，却每次都说地点在书房 L（故意隐瞒）。
- 丙（Y）只听到“低后高”双音，时间和地点都 `UNKNOWN`（诚实但知识受限）。
- 丁（G）保管事件簿；泛问只说“有一份铃声档案”，用 `ARCHIVE_CROSS_INDEX`
  才给出文书事实 23:40 / Y。

动作契约：
- ``move(to)``：H 为中枢，H 连接 L/K/Y/G；1 tick。
- ``ask(npc_id, question_template_id)``：必须在该 NPC 的固定位置；有效提问扣 1 预算
  和 1 tick。重复同一 NPC/模板照样扣预算，但返回完全相同的 answer ID 与文本。
  预算为 0 时返回 ``QUESTION_BUDGET_EXHAUSTED``，**不扣 tick、不扣预算**。
- ``investigate(target_id)``：``study_clock``（L）或 ``courtyard_bell_trace``（Y）；
  1 tick，不占提问预算。
- ``compare_testimony(npc_id, statement_ids, against_evidence_ids)``：只接受已听到的
  answer/source ID 与已发现的物证/档案 ID；比对结果写入公开的 comparison_results。
- ``submit(event_time, event_location, unreliable_npc_id, support_ids,
  unreliability_proof_ids)``：只能在 H，单次终局；拒绝是 truth-neutral 的
  ``CASE_REJECTED``。

失败码：``INVALID_NPC_ID``、``INVALID_QUESTION_TEMPLATE``、``INVALID_LOCATION``、
``QUESTION_BUDGET_EXHAUSTED``、``NO_ADDITIONAL_KNOWLEDGE``、
``COMPARE_INSUFFICIENT_EVIDENCE``、``EVIDENCE_NOT_OBSERVED``、
``INVALID_STATEMENT_ID``、``CASE_REJECTED``。越预算只计 ``query_budget_overruns``，
不改写任何答案。

指标口径（与 ``docs/v7/maps/MAP-29.md`` 一致）：
- ``map29.contradiction_detection_rate``：被规则证实并记录的植入矛盾数 / 2
  （甲的时间矛盾、乙的地点矛盾）；未比对 → 0，合法。
- ``map29.evidence_supported_testimony_ratio``：最终采信且被物证/档案支持的条目数 /
  采信条目数。采信条目固定为 3 项：事件时刻、事件地点、被指认的不可靠证人；没有
  提交 → ``None``（N/A）。
- ``map29.query_budget_overruns``：``QUESTION_BUDGET_EXHAUSTED`` 次数。
- ``map29.single_witness_trust``：提交时采信条目的独立**非证词**来源少于 2 个的
  次数（0–3）。

## 2. 与同世界另两图的区别

- **MAP-28**（简单）：本图与同世界另两图的机制差异：MAP-29 的证词**不可靠且有植入矛盾**，核心是分诊（判断谁记错、谁说谎、谁只是不知道）；MAP-30 有长间隔召回与多事件案卷。本图只有一条短证据链和一处人名误认，难点在**每个正式主张都必须由至少两种不同来源类别交叉支持**，并把“猜中真相”与“证明真相”分开：即使四个字段值全对，只要某一栏只引用单一来源类别，提交仍被拒绝。
- **MAP-30**（困难）：NPC不会靠随机改口制造线索；只有出示已经记录的上游证据，固定回答表才会解锁下一段记忆。三件事件的物证都只写暗码 M-4，早期档案 Q4 是把暗码解回玛拉·维恩的必需证据。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`comparison_results`, `goal`, `heard_answers`, `local_neighbors`, `location`, `npc_locations`, `physical_evidence`, `questions_remaining`, `questions_used`, `tick`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`comparison_results`, `heard_answer_ids`, `judge_reason`, `location`, `overruns`, `physical_evidence_ids`, `questions_remaining`, `questions_used`, `repeated_questions`, `single_witness_count`, `submitted`, `truth`, `unique_answers`, `unreliable_proven`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `ask`：`npc_id`, `question_template_id`
- `compare_testimony`：`against_evidence_ids`, `npc_id`, `statement_ids`
- `investigate`：`target_id`
- `move`：`to`
- `submit`：`event_location`, `event_time`, `support_ids`, `unreliability_proof_ids`, `unreliable_npc_id`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：8 问预算；四名 NPC 知识边界不同；第九问免费拒绝；物证交叉后才采信时地结论。

- 成功码：`ALL_OBJECTIVES_COMPLETE`
- 失败码：`CASE_REJECTED`
- 机制失败路径：
  - 第九问超预算 → 免费拒绝
  - 已证伪的位置谎言仍提交 → `CASE_REJECTED`
  - 未交叉物证即采信 → 低精度

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map29.contradiction_detection_rate` | primary | higher_is_better | detected_contradictions / planted_contradictions | 植入矛盾数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.evidence_supported_testimony_ratio` | primary | higher_is_better | supported_adopted_testimony / adopted_testimony | 采信证词数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.query_budget_overruns` | guardrail | lower_is_better | count(QUERY_BUDGET_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map29.single_witness_trust` | diagnostic | lower_is_better | count(adopt testimony with <2 independent sources) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：high_information_first（13 步）, broad_then_narrow（23 步）
- 手算 fixture：broad_route_success_seven_questions（23 步）, proven_location_lie_still_submitted（11 步）, ninth_question_is_refused_free（10 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-29` → `MAP-29: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 38 | 0.04048732 | `V8-MAP-29-R0-20261017T105544Z-260b1802` | `contradiction_detection_rate`=0.0; `query_budget_overruns`=0; `single_witness_trust`=0 |
| 1 | decision_budget_reached | False | None | 38 | 0.04046624 | `V8-MAP-29-R1-20261017T105936Z-ec83d220` | `contradiction_detection_rate`=0.0; `query_budget_overruns`=0; `single_witness_trust`=0 |
| 2 | decision_budget_reached | False | None | 38 | 0.03567872 | `V8-MAP-29-R2-20261017T110340Z-482b3e69` | `contradiction_detection_rate`=0.0; `query_budget_overruns`=0; `single_witness_trust`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

矛盾计数只统计已问询且可交叉验证的命题。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
