# MAP-29｜古堡 · 不可靠的证人（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-06`
- `rule_hash`：`90fd7560d39362ae27543af35098335844220c3de085826f533e013b931f5b7b`
- `metric_hash`：`0a70dc1c8022e1e49f95a00deb1674588598891cbd9527079be7927594dd3a78`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 3：公开 compare 语义；角色分配随 seed 轮换且不公开；部分真实证人；四消融 0/4，启发式 8–9 问 4/4

- 主指标：`map29.v10.contradiction_detection_rate`, `map29.v10.evidence_supported_testimony_ratio`
  - `map29.v10.contradiction_detection_rate`：被固定比对规则证明并记录的植入矛盾数 / 该案卷植入矛盾数（方向：higher）
  - `map29.v10.evidence_supported_testimony_ratio`：最终采信的三项（时刻/地点/被指认证人）中被独立来源支持的条目数 / 3（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. H 是中枢，直连 L/K/Y/G；move(to) 沿公共边移动，1 tick。
2. ask(npc_id, question_template_id) 必须在该 NPC 所在房间；有效提问扣 1 预算与 1 tick。预算 12；预算耗尽返回 QUESTION_BUDGET_EXHAUSTED，不扣 tick。
3. investigate(target_id) 取物证（study_clock / bell_trace），1 tick，不占提问预算。
4. compare_testimony(npc_id, statement_ids, against_evidence_ids)：两个列表都只能引用已听到的 answer/source ID 与已发现的物证。返回 INSUFFICIENT（证据不够）、CONTRADICTED_AND_EXPLAINED（可证伪且给出解释）、TESTIMONY_PARTIALLY_SUPPORTED（部分真实）、TESTIMONY_CONSISTENT（无关但可信）。
5. submit 只能在 H，一次终局：提交时刻、地点、被指认的不可靠 NPC，以及支持证据与“不可靠证明”引用；被指认者必须已被比对规则证明。
6. 模板：OPEN_ACCOUNT / TIME_BASIS / LOCATION_BASIS / ARCHIVE_CROSS_INDEX / SOUND_PATTERN。不同 NPC 只掌握其中一部分；证人可能记错、隐瞒或诚实但不知道。

### Observation 公开字段

`comparison_results`、`goal`、`heard_answers`、`local_neighbors`、`location`、`npc_labels`、`npc_locations`、`physical_evidence`、`questions_remaining`、`questions_used`、`scenario_label`、`tick`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`has_partial_witness`、`npc_locations`、`planted_contradictions`、`scenario_label`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`event_location`、`event_time`、`label`、`planted`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `ask` | {npc_id,question_template_id,tool} |
| `compare_testimony` | {against_evidence_ids,npc_id,statement_ids,tool} |
| `investigate` | {target_id,tool} |
| `move` | {to,tool} |
| `submit` | {event_location,event_time,support_ids,tool,unreliability_proof_ids,unreliable_npc_id} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `ce2a8166f2edf1b2` |
| 1 | `1fe2d14779123111` |
| 2 | `f1be3675310f64c5` |
| 3 | `06014f1b9cd0a8c2` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map29.v10.contradiction_detection_rate` | primary | higher | 被固定比对规则证明并记录的植入矛盾数 / 该案卷植入矛盾数 | 该案卷植入矛盾数（2） | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map29.v10.evidence_supported_testimony_ratio` | primary | higher | 最终采信的三项（时刻/地点/被指认证人）中被独立来源支持的条目数 / 3 | 已提交的局（1） | 未提交 → NOT_APPLICABLE（截尾 → CENSORED） | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map29.v10.partial_truth_classified` | secondary | higher | 部分真实证人被判为 TESTIMONY_PARTIALLY_SUPPORTED | 该案卷存在部分真实证人（1） | 案卷无部分真实证人 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map29.v10.query_budget_overruns` | guardrail | lower | QUESTION_BUDGET_EXHAUSTED 次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 30.0) |
| `map29.v10.single_witness_trust` | guardrail | lower | 采信条目中独立非证词来源 <2 的条目数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 3.0) |
| `map29.v10.questions_used` | diagnostic | lower | 消耗的提问预算 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 8.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_accuse` | 0/4 | 0.0 |
| `no_compare` | 0/4 | 0.0 |
| `skip_archive` | 0/4 | 0.0 |
| `trust_first` | 0/4 | 0.5 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 0.5）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ALL_OBJECTIVES_COMPLETE`、`CASE_REJECTED`

## 7. MiMo 证据（含重复运行；单 seed 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-29-S0-castle` | decision_budget_exhausted（decision_budget_exhausted） | 38 | 0.0 | 0.0365772 | 是 |
| 1 | `V10-MAP-29-S1-castle` | decision_budget_exhausted（decision_budget_exhausted） | 38 | 0.0 | 0.03658588 | 是 |
| 2 | `V10-MAP-29-S2-castle` | decision_budget_exhausted（decision_budget_exhausted） | 38 | 0.0 | 0.03359748 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.10676056（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 案卷
- 当前裁定：Batch 3：公开 compare 语义；角色分配随 seed 轮换且不公开；部分真实证人；四消融 0/4，启发式 8–9 问 4/4
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-06.md`
- `runs/v10/baselines/MAP-29.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

