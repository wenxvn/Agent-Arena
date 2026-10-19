# MAP-03｜飞船 · 最后的百步（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-01`
- `rule_hash`：`f061aad1ba2a852b3928e037d983a1b2f97a9519e33c930556d324dbf71bae8f`
- `metric_hash`：`483a83c0d97e5ee97a4f022c922e66415e2f59db4440dee186bcd0d039a69ab3`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；三消融 0/6，启发式 6/6

- 主指标：`map03.v10.code_recall_correct`, `map03.v10.phase_completion`
  - `map03.v10.code_recall_correct`：submitted_answer == sealed route_code（方向：higher）
  - `map03.v10.phase_completion`：completed_milestones / 5（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 6/6。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 五阶段必须按 P1 供电(D1 aux_panel/restore_power) → P2 读清单并冷藏样本(实验室 sample_manifest/read_tag 后 cryo_case/stabilize_sample) → P3 EVA 修天线(V antenna/repair) → P4 发遥测(U3 telemetry/transmit) → P5 在 U2 submit route_console 航线码；跳步返回 PHASE_OUT_OF_ORDER。
2. 航线码格式为 1 个大写字母 + 1 个数字；只在首次 read_tag 的结果与紧随其后的一个 Observation 中出现一次。稳定样本后清单封存，之后无法再读；只有 1 次提交机会。
3. 读码后样本开始升温：sample_thermal_ticks 从 4 递减，必须在第 4 个后续动作内完成冷藏。
4. write_memory(facts)：facts 为 [{"key": str, "value": str}]，每次 1 tick，最多保留 3 条（同 key 覆盖），内容原样显示在 agent_notes；环境不校验真伪。这是你唯一能跨越很多步保存信息的通道。
5. antenna_panel_code 与 telemetry_ack_code 与航线码同格式，但不是航线码。
6. EVA：只有 eva_supply=3 时才能从 D3 进入 V；进入 V、在 V 内的每个动作、返回 D3 各消耗 1；在 V 内 eva_supply 归零立即失败。
7. tick 达到 return_window_end_tick 仍未校准航线即失败；每个动作（含被拒动作）耗 1 tick。

### Observation 公开字段

`agent_notes`、`antenna`、`antenna_panel_code`、`aux_power`、`eva_active`、`eva_supply`、`goal`、`location`、`manifest_state`、`milestones`、`milestones_completed`、`note_capacity`、`object_locations`、`return_window_end_tick`、`route_calibrated`、`route_tag_read`、`route_tag_value`、`sample_cold`、`sample_thermal_ticks`、`telemetry`、`telemetry_ack_code`、`tick`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`antenna_panel_code`、`min_ticks`、`return_window_end_tick`、`sample_lab`、`start`、`telemetry_ack_code`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`route_code`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target,tool} |
| `interact` | {choice,target,tool} |
| `move` | {edge_id,tool} |
| `submit` | {answer,target,tool} |
| `wait` | {tool,turns} |
| `write_memory` | {facts,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5`（6 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`6`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `42ad7e3d9d558d4f` |
| 1 | `58b8e28ac06bd356` |
| 2 | `a64fa9750e4c78c6` |
| 3 | `e1573c6c77f79bb1` |
| 4 | `325d7f0b9cbec3f0` |
| 5 | `9b48d1855162150e` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map03.v10.code_recall_correct` | primary | higher | submitted_answer == sealed route_code | 读码且发生提交的局（1） | NOT_APPLICABLE | 读码后预算截尾未提交 → CENSORED；未读码或提交前其他终局 → NOT_APPLICABLE | ratio | (0.0, 1.0) |
| `map03.v10.phase_completion` | primary | higher | completed_milestones / 5 | 5 | NOT_APPLICABLE | 部分进度在截尾时仍 VALID | ratio | (0.0, 1.0) |
| `map03.v10.memory_gap_actions` | secondary | none | submit_action_index - read_action_index | — | NOT_APPLICABLE | 未读码或未提交 → NOT_APPLICABLE / CENSORED | actions | (1.0, 200.0) |
| `map03.v10.tag_read_attempts` | diagnostic | none | count(interact sample_manifest/read_tag) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map03.v10.memory_writes` | diagnostic | none | count(accepted write_memory) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map03.v10.note_holds_code_at_submit` | secondary | higher | agent_notes 在提交时包含航线码 | 发生提交的局（1） | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map03.v10.distractor_submitted` | guardrail | lower | 提交值 ∈ {天线面板码, 遥测回执码} | 发生提交的局（1） | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map03.v10.eva_overspend` | guardrail | lower | EVA 实际消耗 - 3（成功单次出舱的最小消耗） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | units | (-3.0, 3.0) |
| `map03.v10.phase_order_violations` | guardrail | lower | count(PHASE_OUT_OF_ORDER) | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `late_read` | 0/6 | 0.0 |
| `no_memory` | 0/6 | 0.0 |
| `random_guess` | 0/6 | 0.0 |

- Oracle：6/6（机制触发 6/6）
- 公开启发式：6/6（主指标均值 1.0）
- legal_random：0/120（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`RETURN_WINDOW_EXPIRED`、`ROUTE_CALIBRATED`、`ROUTE_KEY_REJECTED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-03-S0-p0` | RETURN_WINDOW_EXPIRED（decision_budget_exhausted） | 39 | None | 0.0816078 | 是 |
| 1 | `V10-MAP-03-S1-p0` | ROUTE_CALIBRATED（decision_budget_exhausted） | 25 | 1 | 0.13510428 | 是 |
| 2 | `V10-MAP-03-S2-p0` | ROUTE_CALIBRATED（decision_budget_exhausted） | 34 | 1 | 0.20872256 | 是 |

- 有效局成功：2/3
- 结算成本合计 CNY 0.42543464（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过
- 当前裁定：Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；三消融 0/6，启发式 6/6
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-01.md`
- `runs/v10/baselines/MAP-03.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

