# MAP-28 定稿：消失的王冠

| 字段 | 值 |
|---|---|
| 世界 | castle |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `42ae98aa24e90202b931fa381b4fc6d953abcbc3ab74755b74a8f524f642648b` |
| rule_hash | `ce443167b19df2c528eaeff66adb7196129eb116d15d59f1e933afeb13a612ee` |
| prompt_hash | `d9936c02ab7c0e49f65b24c2f6d7c10274869a11131e35cdc58d587531894b63` |
| metric_schema_hash | `b3ea6a921cfd4d391b9ed7d10d4060f42dad2b2f09c1bffcfc7780aad836d9cf` |
| oracle_hash | `d532d11ebdedceee0c464d7961609bc14378b16bb8dfeac3e77a09fbfc9ab815` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图只检验一件案子的证据推理：王冠失窃后，三名嫌疑人都尚未排除，Agent要分别提交人物、跨过宝库哪一道门、进入时刻和离开时刻。成功不是把证据“收集齐”就结束；四个事实字段各自都必须有至少两种独立来源支持，而且最终结构化断言要全部正确。

MAP-28｜消失的王冠：四字段双来源交叉的证据时间线重建。

本图与同世界另两图的机制差异：MAP-29 的证词**不可靠且有植入矛盾**，核心是分诊
（判断谁记错、谁说谎、谁只是不知道）；MAP-30 有长间隔召回与多事件案卷。本图只有
一条短证据链和一处人名误认，难点在**每个正式主张都必须由至少两种不同来源类别
交叉支持**，并把“猜中真相”与“证明真相”分开：即使四个字段值全对，只要某一栏只
引用单一来源类别，提交仍被拒绝。

地形与真相（裁判侧）：``H—V—G—K—S—V`` 环路加 ``A—G`` 档案支线。唯一真相是
Celine 于 21:06 从 ``S-V`` 密道门进入、21:14 从同一门离开。V 有三个真实入口：
``BANQUET_H_V``、``GUARD_G_V``、``SECRET_S_V``，路径枚举严格匹配，不接受近义词。

四类来源：仪器锁芯日志（V 调查）、物证脚印（S 调查）、档案钥匙登记（A 阅读）、
厨房目击（K 访谈）。厨师把深色衣服误认成 Basil，但目击对**路径与时间窗**仍是
有效来源；它不能单独支持任何人名。

动作契约：
- ``move(to)``：沿六室边移动，1 tick。
- ``investigate(target_id)``：``vault_lock_events``（V）或 ``footprint_trail``（S）。
- ``read_record(record_id)``：``key_registry``（A）。
- ``interview(witness_id)``：``kitchen_cook``（K）。
- ``record(clue_id)``：只能记录**已观察**的具体证据 ID（V8Action 的单值字段名是
  ``clue_id``），不创建也不改写证据。
- ``submit(claims, citations_by_claim)``：``claims`` 是
  ``[{"claim_id": ..., "value": ...}]``，四个 claim_id 为 ``person_id`` /
  ``entry_path_id`` / ``entry_time`` / ``exit_time``；``citations_by_claim`` 是
  ``{claim_id: [evidence_id, ...]}``。一次提交终局，拒绝不泄漏正确答案，也不给重试。

失败码：``CASE_REJECTED``（终局拒绝的 terminal_reason，truth-neutral）、
``ACCUSATION_WITHOUT_TWO_SOURCES``（提交动作结果：任一字段的支持来源类别少于 2，
同时写入违规账）、``CLAIM_CONTRADICTS_RECORDED_EVIDENCE`` 造成的拒绝仍以
``CASE_REJECTED`` 作为动作结果、``EVIDENCE_NOT_OBSERVED``、``INVALID_EVIDENCE_ID``、
``TARGET_NOT_VISIBLE``、``EDGE_NOT_ADJACENT``、``INVALID_ACTION_ENUM``（路径/人物/
时间格式非法，0 tick，不消耗唯一提交）、``EVIDENCE_ALREADY_RECORDED``。

指标口径（与 ``docs/v7/maps/MAP-28.md`` 一致）：
- ``map28.timeline_constraint_satisfaction``：同时满足“值等于真相 + 至少 2 个不同
  来源类别”的字段数 / 4；未提交 → 0/4。
- ``map28.key_evidence_coverage``：已记录的关键证据数 / 4（K3 登记、K3 锁日志、
  C7 脚印、厨师证词）；未调查 → 0，合法。
- ``map28.unsupported_accusations``：提交时任一字段无两类来源记 1，否则 0；单次提交
  至多 1。
- ``map28.time_contradictions``：被**已记录**证据排除的提交时间字段数（entry/exit
  分别计数）；另加“进入时刻不早于离开时刻”的时序矛盾计数。

## 2. 与同世界另两图的区别

- **MAP-29**（中等）：本图与同世界另两图的机制差异：MAP-28 的证据都可靠，难点是四字段双来源交叉；MAP-30 是长间隔召回与多事件案卷。本图固定四名 NPC、四种不同的知识边界/偏差，核心是**在有限问询预算里区分“记错”“故意隐瞒”“诚实但不知道”**，并只在物证或档案交叉验证后才采信时地结论。
- **MAP-30**（困难）：NPC不会靠随机改口制造线索；只有出示已经记录的上游证据，固定回答表才会解锁下一段记忆。三件事件的物证都只写暗码 M-4，早期档案 Q4 是把暗码解回玛拉·维恩的必需证据。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`goal`, `local_neighbors`, `location`, `observed_evidence`, `recorded_evidence_ids`, `tick`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`judge_reason`, `location`, `observed_evidence_ids`, `recorded_evidence_ids`, `satisfied_fields`, `submitted`, `time_contradictions`, `truth`, `unsupported_accusations`, `violations`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `interview`：`witness_id`
- `investigate`：`target_id`
- `move`：`to`
- `read_record`：`record_id`
- `record`：`clue_id`
- `submit`：`citations_by_claim`, `claims`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：四字段双来源交叉；窗口猜测与锁分钟矛盾；未观察记录不可作为正式引用。

- 成功码：见运行时
- 失败码：`由终局 `verdict`/动态码表达，见失败路径`
- 机制失败路径：
  - 窗口猜测与锁分钟矛盾 → `CASE_REJECTED`
  - 未观察记录作为引用 → 拒绝
  - 路径别名非法 → 拒绝

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map28.key_evidence_coverage` | primary | higher_is_better | verified_key_evidence / required_key_evidence | 必需关键证据数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.time_contradictions` | diagnostic | lower_is_better | count(submitted timeline contradiction) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.timeline_constraint_satisfaction` | primary | higher_is_better | satisfied_timeline_constraints / total_timeline_constraints | 时间线约束数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map28.unsupported_accusations` | guardrail | lower_is_better | count(accusation without two sources) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：evidence_first_two_source（20 步）
- 手算 fixture：four_fields_two_sources_success（20 步）, window_guess_contradicts_lock_minute（9 步）, unobserved_record_and_invalid_path_alias（7 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-28` → `MAP-28: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

无独立失败码，终局拒绝由 `verdict` 表达；四字段双来源规则不变。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
