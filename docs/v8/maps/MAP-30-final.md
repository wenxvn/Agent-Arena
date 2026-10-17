# MAP-30 定稿：30 午夜审判

| 字段 | 值 |
|---|---|
| 世界 | castle |
| 难度 | 困难 |
| 条件 | `history5_casebook` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `a6826866eba03a4ab06a4b81d35120c537d97ca35db20658fa7ee2b445fa5914` |
| rule_hash | `f53fe656d63daa23fc2dea7aefa765bf8a4272104aa9b300b7a69ac60f6af810` |
| prompt_hash | `55732022598689c2a18e164776df961dfe9237c61609f96c2e2ea140b1b0b504` |
| metric_schema_hash | `e5331bbc8a0c4968c03d1c5c4bb654af8e1932c10ee39579a9f89d019e8e51b5` |
| oracle_hash | `8c3bfa120e346b1e12980cdb5fdc39492aa1dc50f0894fd9079694275cc0c600` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

本图单独考察长间隔证据记忆、跨来源一致性、时间顺序复原和谨慎指控。它与 MAP-29 的固定证人可信度题不同：NPC不会靠随机改口制造线索；只有出示已经记录的上游证据，固定回答表才会解锁下一段记忆。三件事件的物证都只写暗码 M-4，早期档案 Q4 是把暗码解回玛拉·维恩的必需证据。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-28**（简单）：本图与同世界另两图的机制差异：MAP-29 的证词**不可靠且有植入矛盾**，核心是分诊（判断谁记错、谁说谎、谁只是不知道）；MAP-30 有长间隔召回与多事件案卷。本图只有一条短证据链和一处人名误认，难点在**每个正式主张都必须由至少两种不同来源类别交叉支持**，并把“猜中真相”与“证明真相”分开：即使四个字段值全对，只要某一栏只引用单一来源类别，提交仍被拒绝。
- **MAP-29**（中等）：本图与同世界另两图的机制差异：MAP-28 的证据都可靠，难点是四字段双来源交叉；MAP-30 是长间隔召回与多事件案卷。本图固定四名 NPC、四种不同的知识边界/偏差，核心是**在有限问询预算里区分“记错”“故意隐瞒”“诚实但不知道”**，并只在物证或档案交叉验证后才采信时地结论。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`casebook`, `current_hypothesis`, `current_node`, `current_tick`, `local_neighbors`, `public_alert`, `recent_action_window`, `unsupported_formal_accusations`, `visible_local_evidence`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`casebook`, `chain_reconciled`, `map_id`, `node`, `recent_events`, `seed`, `seen_evidence`, `status`, `terminal_reason`, `tick`, `unsupported_formal_accusations`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `compare_records`：`entry_ids`
- `formal_accuse`：`cited_entry_ids`, `event_claims`, `person_id`
- `inspect`：`evidence_id`
- `interview`：`npc_id`, `shown_casebook_entry_ids`, `shown_evidence_ids`, `topic_id`
- `move`：`to`
- `record`：`entry_id`, `evidence_ids`
- `submit_intermediate_hypothesis`：`candidate_person`, `confidence`, `event_ids_known`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：复用 V6 规则：长间隔 Q4 召回、多事件案卷、正式指控需事件主张与引用条目。

- 成功码：`ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN`
- 失败码：`ACCUSATION_LIMIT_EXCEEDED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map30.accusation_claim_precision` | primary | higher_is_better | max(0, matched_expected - extra) / expected_claim_count | 冻结案情的应提交事件数 | 无指控 → N/A；无冻结案情 → UNAVAILABLE | 无指控且截尾 → CENSORED |
| `map30.chain_reconciled` | diagnostic | higher_is_better | 1 if any result==CHAIN_COHERENT else 0 | episode | 无 compare_records → 0（合法） | 按已发生事件计算 |
| `map30.evidence_chain_coverage` | primary | higher_is_better | entries with required_evidence ⊆ recorded / len(entry_order) | 该案卷条目总数（3 或 4） | casebook 字段缺失 → UNAVAILABLE | 过程量按已记录条目计算 |
| `map30.investigation_progress` | diagnostic | higher_is_better | len(recorded entries) / len(entry_order) | 案卷条目总数 | casebook 缺失 → UNAVAILABLE | 按已记录条目计算 |
| `map30.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map30.q4_recall_accuracy` | primary | higher_is_better | 1 if person==culprit and code_entry cited in formal_accuse else 0 | 提交过 formal_accuse 的 episode | 无最终指控 → N/A；无冻结案情 → UNAVAILABLE | 因 deadline/step-limit 未提交 → CENSORED |
| `map30.unsupported_accusations` | guardrail | lower_is_better | final unsupported_formal_accusations | episode | 字段缺失 → UNAVAILABLE | 按已发生指控计数 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-30-solver-success（25 步）
- 手算 fixture：two-unsupported-accusations（5 步）, full-chain-success（25 步），补充冻结后失败用例 `missing-q4-recall-failure`（19 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-30` → `MAP-30: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 46 | 0.03396008 | `V8-MAP-30-R0-20261017T110714Z-a635ed01` | `chain_reconciled`=0; `evidence_chain_coverage`=0.0; `investigation_progress`=0.0; `legal_action_rate`=0.804348 |
| 1 | decision_budget_reached | False | None | 46 | 0.04683228 | `V8-MAP-30-R1-20261017T111157Z-c722a70c` | `chain_reconciled`=0; `evidence_chain_coverage`=0.0; `investigation_progress`=0.5; `legal_action_rate`=0.804348 |
| 2 | decision_budget_reached | False | None | 46 | 0.04502456 | `V8-MAP-30-R2-20261017T111639Z-e8be28b2` | `accusation_claim_precision`=0.666667; `chain_reconciled`=0; `evidence_chain_coverage`=0.0; `investigation_progress`=0.5 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

复用 V6 `map30_l3_original`；Q4 召回与调查完整度分开报告。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `7/7`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
