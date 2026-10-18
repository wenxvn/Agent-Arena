# MAP-30｜古堡 · 午夜审判（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-07`
- `rule_hash`：`fcddd9502705a9c0d37e2762c4ef386d2d649dd0020f15a9ecc394aee7d8a6fc`
- `metric_hash`：`0200ea5444520a73fc083ba41cd70009ac1338dd0842871031287a1157c49e4b`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 3：公开条目 ID/成对规则/法庭节点/窗口语义；诱饵事件；两处指标偏置纠正；四消融 0/3，window_delay 触发 window_pressure

- 主指标：`map30.v10.evidence_chain_coverage`, `map30.v10.accusation_claim_precision`
  - `map30.v10.evidence_chain_coverage`：已完整的案卷条目数 / 需要的条目数（3 事件 + 1 文书）（方向：higher）
  - `map30.v10.accusation_claim_precision`：被接受的 formal_accuse 中匹配的事件主张数 / 3（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 3/3。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 房间图：H 连 B/J/L；L—K—T—A 为一条走廊。move(to) 1 tick；正式指控 formal_accuse 只能在法庭节点 J。
2. record(entry_id) 的合法条目 ID 仅：EVENT_1_HANDOFF, EVENT_2_WAX, EVENT_3_SIGNAL, Q4_CODEBOOK。
3. 每个事件条目需要**现场记录 + 证人确认**两件证据；Q4_CODEBOOK 只需交叉索引文书。
4. interview 的 topic_id 也用同一套条目 ID；证人分条件作答：需要出示对应物证，通常还需要**更早事件的完整条目**（档案看守要求先归档第一件事件），否则只给泛泛回忆。
5. 档案看守给出的交叉索引把值班代号（duty_code）映射到人名；现场物证同时公开该事件的 time / location / duty_code。
6. 近期动作窗口只保留最近 5 条事件；窗口外只能通过 casebook 引用。
7. compare_records(entry_ids) 返回 CHAIN_COHERENT 需四个条目都完整且交叉索引一致。

### Observation 公开字段

`case_label`、`casebook`、`chain_reconciled`、`courtroom_node`、`entry_ids`、`entry_requirements`、`evidence_locations`、`goal`、`local_neighbors`、`location`、`npc_locations`、`recent_action_window`、`tick`、`visible_edges`、`visible_local_evidence`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`case_label`、`courtroom_node`、`entry_ids`、`recent_window`、`truth_event_entries`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`culprit_code`、`culprit_person`、`doc_id`、`events`、`label`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `compare_records` | {entry_ids,tool} |
| `formal_accuse` | {cited_entry_ids,event_claims,person_id,tool} |
| `inspect` | {evidence_id,tool} |
| `interview` | {npc_id,shown_casebook_entry_ids,shown_evidence_ids,tool,topic_id} |
| `move` | {to,tool} |
| `record` | {entry_id,evidence_ids,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2`（3 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`3`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `8bb3cfe37290dd82` |
| 1 | `85ee61cb206c05e0` |
| 2 | `bdc63f29e80c101b` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map30.v10.evidence_chain_coverage` | primary | higher | 已完整的案卷条目数 / 需要的条目数（3 事件 + 1 文书） | 需要的条目数（4） | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map30.v10.accusation_claim_precision` | primary | higher | 被接受的 formal_accuse 中匹配的事件主张数 / 3 | 已接受指控的局（1） | 无被接受指控 → NOT_APPLICABLE（截尾 → CENSORED） | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map30.v10.q4_recall_accuracy` | secondary | higher | 人名正确且 Q4 条目已记录并被引用 | 已提交指控的局（1） | 未提交指控 → NOT_APPLICABLE（截尾 → CENSORED） | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map30.v10.chain_reconciled` | secondary | higher | compare_records 返回 CHAIN_COHERENT | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map30.v10.window_pressure_events` | diagnostic | lower | 因 5 条近期窗口而过期的 record 尝试次数（长间隔召回证据） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 30.0) |
| `map30.v10.unsupported_accusations` | guardrail | lower | 被拒绝或引用不完整链条的指控次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 5.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `evidence_shuffle` | 0/3 | 1.0 |
| `late_guess` | 0/3 | 0.0 |
| `no_casebook` | 0/3 | 0.0 |
| `window_delay` | 0/3 | 0.25 |

- Oracle：3/3（机制触发 3/3）
- 公开启发式：3/3（主指标均值 1.0）
- legal_random：0/60（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ACCUSATION_REJECTED`、`ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_ADA_SORREL_PROVEN`、`ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_BASIL_ORNE_PROVEN`、`ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-30-S0-castle` | decision_budget_exhausted（decision_budget_exhausted） | 46 | 0.75 | 0.05126152 | 是 |
| 1 | `V10-MAP-30-S1-castle` | decision_budget_exhausted（decision_budget_exhausted） | 46 | 0.5 | 0.0472576 | 是 |
| 2 | `V10-MAP-30-S2-castle` | decision_budget_exhausted（decision_budget_exhausted） | 46 | 0.5 | 0.04976156 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.14828068（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；3 案卷含诱饵；指标偏置已纠
- 当前裁定：Batch 3：公开条目 ID/成对规则/法庭节点/窗口语义；诱饵事件；两处指标偏置纠正；四消融 0/3，window_delay 触发 window_pressure
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-07.md`
- `runs/v10/baselines/MAP-30.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

