# MAP-29｜古堡｜中等｜不可靠的证人

```yaml
map_id: MAP-29
world: castle
nominal_level: 中等
capability_primary: unreliable_testimony_triage
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 3c2e67f37b5de11bf388e476d78634bdee4b5b670bf5db759b82d74af9e6e378
source_design_hash: c59ac4582d0743486b5cc9fc6f81527ca6ee93c3ede1728bce868fbb11d5cec4
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“有限问询预算下的证词分诊”。四位 NPC 各有固定知识边界/偏差：甲把停钟当事件钟（记忆锚定，误报 00:05）、乙**故意**把地点说成书房（说谎）、丙只听到音型且诚实 `UNKNOWN`、丁要用 `ARCHIVE_CROSS_INDEX` 才给文书事实。8 次提问预算、5 个模板、答案由 seed 固定渲染。核心不是“问出真相”，而是**判断谁不可靠、谁只是不知道**，并用物证/档案交叉验证后再提交 23:40 / Y。

## 2. 真实规则字段

- 事件：庭院 Y 的银铃在 23:40 响过一次。
- 证人位置：甲 L、乙 K、丙 Y、丁 G；有效提问需在该 NPC 固定位置。
- 模板：`OPEN_ACCOUNT / TIME_BASIS / LOCATION_BASIS / ARCHIVE_CROSS_INDEX / SOUND_PATTERN`；超出知识范围固定返回 `NO_ADDITIONAL_KNOWLEDGE`。
- 预算：每次 `ask` 耗 1 预算 + 1 tick；重复同一 NPC/模板仍耗预算但返回相同 answer ID 与文本；预算归零后 `QUESTION_BUDGET_EXHAUSTED`，不扣 tick/预算。
- 现场证据：`STUDY_CLOCK_STOPPED_0000`（L，停钟实物）、`YARD_BELL_MARK_2340`（Y，机械撞针）、`ARCHIVE_EVENT_2340_Y`（丁的文书来源）。
- 比对：`compare_testimony` 只接受已听到的 answer ID 与已发现证据 ID；可判“甲时间不可靠”“乙地点不可靠”；丙的知识限制不得被标成说谎。
- 提交：需给出准确事件时刻 23:40 与地点 Y，并指出至少一位**经规则证明**不可靠的 NPC；错误提交一次终结且不泄漏正确答案。
- 失败：终局拒绝（错误提交）；无全局倒计时。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map29.contradiction_detection_rate` | primary | 被正确记录的植入矛盾数 / 2 | 比例 / 高 | 2（甲时间、乙地点） | 未比对 → 0（合法） |
| `map29.evidence_supported_testimony_ratio` | primary | 最终采信且被物证/档案支持的证词数 / 采信证词数 | 比例 / 高 | 采信证词数；0 → N/A | 无提交 → N/A |
| `map29.query_budget_overruns` | guardrail | `count(QUESTION_BUDGET_EXHAUSTED)` | 次 / 低 | episode | 0 合法 |
| `map29.single_witness_trust` | diagnostic | 采信**单一证人**（<2 独立来源）的次数 | 次 / 低 | episode | 0 合法 |

实现状态：**未实现**（`implemented=False`）。`contradiction_detection_rate` 的分母固定为 2；两条手写成功策略都只比对出甲的时间矛盾，因此都是 **0.5**，不是 1.0——本图不要求“全矛盾识别”才算成功。

## 4. 能力混淆分析

- 高检测率可能只因为“把丙也标成说谎”：丙是**诚实但不知道**，误标会抬高“检测”但降低证据支持比；两指标必须并列。
- `evidence_supported_testimony_ratio=1.0` 可能只因为“只采信丁的档案”：采信数少也可得 1.0；必须报采信条数与覆盖率。
- `query_budget_overruns=0` 不代表问得高效：广泛询问策略 7 问、优先策略 3 问，都能 0 超支；预算效率要与 tick 并列。
- `single_witness_trust=0` 不代表没有采信错误：F02 采信了乙的地点，但有撞针反证，属于“明知矛盾仍照抄”，不一定计入单证人。
- 重复问同一模板会消耗预算但不增加信息；`unique-answer` 计数不是本卡注册指标，不应拿“问得多”当努力。

## 5. 两条手算轨迹

**A. 广泛询问再收敛（19 tick / 7 问）**：依次拜访甲、乙、丙、丁各一次 `OPEN_ACCOUNT`（4 问）→ 丁 `ARCHIVE_CROSS_INDEX`（5）→ 甲 `TIME_BASIS`（6）→ 丙 `SOUND_PATTERN`（7）；查书房停钟与庭院撞针；`compare_testimony` 判甲时间不可靠；回 H 提交 23:40/Y。指标：`contradiction_detection_rate = 1/2 = 0.5`；采信档案 + 撞针 → `evidence_supported_testimony_ratio = 1.0`；超支 0；单证人采信 0。

**B. 高信息问题优先（13 tick / 3 问）**：G 对丁 `ARCHIVE_CROSS_INDEX`（1，得 23:40/Y）→ L 对甲 `OPEN_ACCOUNT`（2）与 `TIME_BASIS`（3）→ 停钟 + 档案核出记忆偏差 → Y 查撞针复核。指标：检测率 **0.5**（只判甲）；证据支持比 1.0；超支 0；单证人 0。

> A 覆盖全部证人但把预算花在丙的声音限制上；B 只用 3 问就得到同一结论。两者检测率相同（0.5），说明“问得多”不等于“矛盾识别多”。

## 6. 三个机制特有失败

1. **F01 把甲的记忆当钟表**：问甲开放叙述与时间依据，查到停钟停在 00:00 却仍提交 00:05；地点 Y 正确也因事件时间错误被拒。采信了无物证支持的单一证词。
2. **F02 明知矛盾仍照抄乙的地点**：丁给 23:40/Y，乙说书房 L，撞针比对已证明乙隐瞒；仍提交 L → 拒绝。证据判断与答案自相矛盾。
3. **F03 把丙的有限知识当不可靠**：只问丙的双音，未取得时间/地点、也未做证据比对，就把丙指为撒谎者并猜位置 → 拒绝。诚实 `UNKNOWN` ≠ 说谎。

## 7. 两个边界

- **第 8 问有效 vs 第 9 问拒绝（B01/B02）**：第 8 问仍返回确定回答；第 9 问 `QUESTION_BUDGET_EXHAUSTED` 且不耗 tick/预算。预算是包含端点。
- **重复模板（B03）**：同一 NPC 同一问题重复返回相同 answer ID/载荷，但仍消耗预算，unique-answer 不增加；不能靠重复问“刷”证据。

## 8. 信息泄漏负例

若 Observation/prompt 直接给 `private_answer_tables.yaml`、真人名/真时刻或“乙在说谎”，证词分诊被替代。V7 只允许公开 NPC 位置、模板、已听到的 answer ID/文本、已发现证据、预算与比对结果；偏差规则与完整答案表只在离线裁判侧。`UNKNOWN` 不得被渲染成“拒绝回答”而暗示有隐情。

## 9. Oracle/求解状态

`planning/private_answer_tables.yaml` 固定四人答案表与偏差；`oracle_trace.jsonl`（seed0，14 行，SHA-256 `8D0B3CD1…C931`）有两条手写成功（19 tick/7 问、13 tick/3 问）；`failure_traces/cases.yaml` 有 F01–F03 与 B01–B06。**没有运行时、没有真实模型实验**；离线审计证明答案固定、重复问不变、物证独立。

## 10. 与同世界另两图差异

**vs MAP-28**：MAP-28 只有一条错误人名、证据链短且来源类别明确；MAP-29 有**两种不同偏差**（记忆锚定 vs 故意说谎）与一个“诚实无知”的对照，核心是分诊。MAP-28 的指标是时间线满足率，MAP-29 是矛盾检测率/证据支持比。

**vs MAP-30**：MAP-30 有长间隔召回、多事件案卷与审慎指控；MAP-29 是单事件、8 问预算内的证词选择。MAP-29 的失败是误信/误标，MAP-30 的失败常是漏召回或错误指控。

## 11. 可计算性来源

需要的字段：`asked_questions`（NPC/模板/answer ID）、`heard_answers`、`discovered_evidence`、`comparison_records`、`question_budget_remaining`、`submit` 的时刻/地点/不可靠 NPC、`terminal_reason`。检测率由“比对记录中被规则证实的矛盾数 / 2”；证据支持比由提交采信的每条证词是否至少有一个独立物证/档案来源；超支由 `QUESTION_BUDGET_EXHAUSTED` 计数；单证人由提交时的来源数 < 2 计数。

## 12. 难度定位与对照

D=(3,2,1,1,2,3)。相对 MAP-28 提升 **V↑（证词不可靠且有偏差类型）与 B↑（问谁/问什么/何时停的组合选择）**；R 保持 1（只有问询预算）。不会与 MAP-28 混淆：MAP-28 的证据都可靠，MAP-29 的核心是判断可靠性。

预登记对照：**给偏差类型提示 vs 只给 NPC 档案**。若提示组检测率显著更高，说明构念测“按偏差分诊”而非“多问”；两组共享答案表、预算、证据与提交接口。另需 **8 问 vs 无限问** 对照，确认预算约束真实生效。

## 13. 未决

- `contradiction_detection_rate` 的分母 2 是否应随“实际可比对的矛盾”变化：若 Agent 从未听到乙的地点，乙的矛盾不可检测，固定分母会低估；本卡按“本局可检测数”应为 2（两条都可听到），但需运行时确认。
- `single_witness_trust` 与 `evidence_supported_testimony_ratio` 在 F02 上可能重叠计数；需固定“采信”的操作定义（提交字段 vs 比对记录）。
- `UNKNOWN` 的渲染必须与“不知道”一致，不能暗示隐瞒；否则会把丙误标为不可靠。
- 无运行时、无真实模型结果；所有数值为纸面审计值。状态 `pending_human_review`。
