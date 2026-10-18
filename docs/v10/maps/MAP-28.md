# MAP-28｜古堡 · 消失的王冠（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-06`
- `rule_hash`：`2f5237a2530c8870e257c26bee6efd6c58aaf1f2b3dd7d6e1127ff4f2ea15703`
- `metric_hash`：`ee73687b1c61fe511e44ddf34381737f4f852e2c8516a2e2f075286fd0911417`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 3：公开 person/path 枚举；4 案卷依赖图不同；引用自洽规则；no_record 0/4、single_source 0/4、blind_submit 0/4、cite_all 3/4

- 主指标：`map28.v10.timeline_constraint_satisfaction`
  - `map28.v10.timeline_constraint_satisfaction`：值等于真值且引用 ≥2 个不同来源类别的字段数 / 4（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 六室环路 H—V—G—K—S—V 加 A—G 档案支线；move(to) 沿公共边移动，1 tick。
2. 取证动作：investigate(vault_lock_events)（V）、investigate(footprint_trail)（S）、read_record(key_registry)（A）、interview(kitchen_cook)（K）。
3. record(clue_id) 只能记录**已观察**的具体证据 ID；观察过但没记录的证据不能作为来源。
4. submit 一次终局：claims 四个字段 person_id / entry_path_id / entry_time / exit_time，citations_by_claim 为每个字段的已记录证据 ID 列表。
5. person_id 合法值仅：ADA, BASIL, CELINE；entry_path_id 合法值仅：BANQUET_H_V, GUARD_G_V, SECRET_S_V；时间格式 HH:MM。
6. 每个字段必须由**至少两种不同来源类别**（instrument_log / physical_trace / documentary_register / testimony）支持，且值必须正确。
7. 失败码：引用未记录/未观察的证据 → EVIDENCE_MISSING；值被已记录证据排除 → CLAIM_CONTRADICTS_RECORDED_EVIDENCE；值可能正确但来源类别 <2 → ACCUSATION_WITHOUT_TWO_SOURCES；终局拒绝统一为 CASE_REJECTED。

### Observation 公开字段

`case_label`、`entry_paths`、`goal`、`local_neighbors`、`location`、`observed_evidence`、`persons`、`recorded_evidence_ids`、`required_key_evidence`、`tick`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`case_label`、`entry_paths`、`persons`、`required_key_evidence`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`label`、`truth`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `interview` | {tool,witness_id} |
| `investigate` | {target_id,tool} |
| `move` | {to,tool} |
| `read_record` | {record_id,tool} |
| `record` | {clue_id,tool} |
| `submit` | {citations_by_claim,claims,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `120b88e5b503b8ba` |
| 1 | `82005fc4f50e419a` |
| 2 | `abebecaf91064c7f` |
| 3 | `e442d80bb048df3b` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map28.v10.timeline_constraint_satisfaction` | primary | higher | 值等于真值且引用 ≥2 个不同来源类别的字段数 / 4 | 已提交的局（1） | 未提交 → NOT_APPLICABLE（截尾 → CENSORED） | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map28.v10.record_coverage` | secondary | higher | 已 record 的关键证据数 / 4（过程量，截尾仍 VALID） | 4 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map28.v10.submission_attempted` | diagnostic | none | 是否发生过 submit | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 1.0) |
| `map28.v10.unsupported_accusations` | guardrail | lower | 提交时任一字段来源类别 <2 | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map28.v10.time_contradictions` | guardrail | lower | 被已记录证据排除的时间字段数 + 时序矛盾 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 4.0) |
| `map28.v10.missing_evidence_citations` | diagnostic | lower | 提交引用中未记录/未观察的证据数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_submit` | 0/4 | 0.0 |
| `cite_all` | 3/4 | 0.9375 |
| `no_record` | 0/4 | 0.0 |
| `single_source` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ALL_CLAIMS_SUPPORTED_AND_CORRECT`、`CASE_REJECTED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-28-S0-castle` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.03482488 | 是 |
| 0 | `V10-MAP-28-S0-i2` | ALL_CLAIMS_SUPPORTED_AND_CORRECT（success） | 20 | 1.0 | 0.01538112 | 是 |
| 1 | `V10-MAP-28-S1-castle` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.02478312 | 是 |
| 1 | `V10-MAP-28-S1-i2` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.0254828 | 是 |
| 2 | `V10-MAP-28-S2-castle` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.01862644 | 是 |
| 2 | `V10-MAP-28-S2-i2` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.02358332 | 是 |

- 有效局成功：1/6
- 结算成本合计 CNY 0.14268168（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 案卷
- 当前裁定：Batch 3：公开 person/path 枚举；4 案卷依赖图不同；引用自洽规则；no_record 0/4、single_source 0/4、blind_submit 0/4、cite_all 3/4
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-06.md`
- `runs/v10/baselines/MAP-28.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

