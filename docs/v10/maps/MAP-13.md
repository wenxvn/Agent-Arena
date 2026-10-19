# MAP-13｜金字塔 · 四神之门（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-15`
- `rule_hash`：`4254acd048e79dea177a099917fc3d4faf87351e5b53abf1fc606b0353414889`
- `metric_hash`：`7851b54fe9147a1cc2991cbdc5ab920089044eb0f36838777019e8ecf3c5204c`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：记录成为出手前提（试排需 ≥1 条、验证需 ≥4 条）；no_record 0/4（V9 为 15 步满分）、blind_guess/record_only_nail 0/4；no_direction_nail 4/4 但 ratio 恒 0.8

- 主指标：`map13.v10.constraint_satisfaction_ratio`
  - `map13.v10.constraint_satisfaction_ratio`：（最后一次试排满足的房间谓词数 + 方向钉是否已读）/ 5（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 星形拓扑：营地 C 直连 N/E/S/W 四间外室，外室之间没有直连。
2. read_inscription(room) 只能读**自己所在**的房间；每条碑文只能读一次同一内容。
3. record_constraint(clue_id) 只能在 C，且只能记录**已读**的碑文。
4. set_trial_layout 在 C，必须恰含 N/E/S/W 四槽且四符号各一次；**至少记录过 1 条约束**才能试排。
5. verify_layout 在 C；**至少记录过 4 条约束**才能验证（观察≠记录）。
6. 错排会清空试排；累计 3 次错排即失败。

### Observation 公开字段

`current_tick`、`gate_open`、`goal`、`incorrect_attempts`、`location`、`observed_clues`、`recorded_clue_ids`、`remaining_incorrect_attempts`、`required_recorded_for_layout`、`required_recorded_for_verify`、`symbols`、`trial_layout`、`visible_edges`、`visible_neighbors`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`clue_count`、`max_incorrect_attempts`、`required_recorded_for_layout`、`required_recorded_for_verify`、`slots`、`symbols`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`roles`、`target_layout`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `move` | {edge_id,tool} |
| `read_inscription` | {room,tool} |
| `record_constraint` | {clue_id,tool} |
| `set_trial_layout` | {layout_by_room,tool} |
| `verify_layout` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `0c57e2ed947c2afe` |
| 1 | `fcb29e705caf4864` |
| 2 | `11695579d3a847e0` |
| 3 | `30309287c49bb940` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map13.v10.constraint_satisfaction_ratio` | primary | higher | （最后一次试排满足的房间谓词数 + 方向钉是否已读）/ 5 | 试排过的局（1） | 从未试排 → NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map13.v10.correct_sequence` | secondary | higher | 最后一次试排是否等于唯一解 | 试排过的局（1） | 从未试排 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map13.v10.recorded_clues` | secondary | higher | 已记录的约束条数 / 5 | 5 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map13.v10.wrong_layout_attempts` | guardrail | lower | 错排导致的 STATE_RESET 次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |
| `map13.v10.illegal_verify_without_layout` | guardrail | lower | 未成型试排就 verify 的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `blind_guess` | 0/4 | — |
| `no_direction_nail` | 4/4 | 0.8 |
| `no_record` | 0/4 | — |
| `record_only_nail` | 0/4 | — |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`GATE_OPENED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-13-S0-ext` | INCORRECT_ATTEMPT_LIMIT（failure） | 24 | 0.2 | 0.017325 | 是 |
| 1 | `V10-MAP-13-S1-ext` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.0185638 | 是 |
| 2 | `V10-MAP-13-S2-ext` | INCORRECT_ATTEMPT_LIMIT（failure） | 24 | 0.2 | 0.0160576 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.05194640（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 道不同约束题；方向钉仍为 OPTIONAL（质量 4/5）
- 当前裁定：Batch 5：记录成为出手前提（试排需 ≥1 条、验证需 ≥4 条）；no_record 0/4（V9 为 15 步满分）、blind_guess/record_only_nail 0/4；no_direction_nail 4/4 但 ratio 恒 0.8
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-15.md`
- `runs/v10/baselines/MAP-13.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

