# MAP-02｜飞船 · 双重警报（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`—`
- `rule_hash`：`9fda51e14de1ee140618c1fbb0764379349f5bc4ba6745b29d9f5f4e02dceb55`
- `metric_hash`：`cf339673be702ebae9a9514219524aec6a5f2282a3c7d2acb0b49ddbd356c13c`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录

- 主指标：`map02.v10.mission_success`
  - `map02.v10.mission_success`：泄漏后同时保住导航核心并把乘员送入逃生舱（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

- （未声明 `public_rules()`，回退到运行时的 Observation 描述）

### Observation 公开字段

`center_gate`、`crew_escorted`、`crew_in_escape_pod`、`crew_location`、`crew_pressure_ticks`、`deadline_tick`、`goal`、`leak_active`、`leak_location`、`location`、`nav_core_location`、`nav_core_secured`、`navigation_alarm`、`repair_pack_available`、`spread_contained`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`crew_pressure_ticks`、`global_deadline`、`label`、`leak_trigger_index`、`spread_ticks`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`deadline`、`event_order_seed`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target,tool} |
| `interact` | {choice,target,tool} |
| `move` | {edge_id,tool} |
| `pickup` | {item_id,tool} |
| `wait` | {tool,turns} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `c4700fddb130e1fe` |
| 1 | `2990b619abe86949` |
| 2 | `eb53782d9d2d44b3` |
| 3 | `4747561d46880c00` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map02.v10.mission_success` | primary | higher | 泄漏后同时保住导航核心并把乘员送入逃生舱 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；泄漏扩散/压力归零 → VALID 0 | ratio | (0.0, 1.0) |
| `map02.v10.event_response_latency` | secondary | lower | 泄漏公告后第一个有效动作的延迟 tick | 发生泄漏的局（1） | 未泄漏 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map02.v10.dual_objective_completion` | secondary | higher | （导航核心已固定 + 乘员已在逃生舱）/ 2 | 2 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map02.v10.stale_plan_actions_after_leak` | guardrail | lower | 泄漏后仍按旧计划前往受威胁区域的动作数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map02.v10.crew_decompression` | guardrail | lower | 乘员压力是否归零终局（1 表示失败） | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map02.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `crew_only` | 0/4 | 0.0 |
| `late_react` | 0/4 | 0.0 |
| `nav_only` | 0/4 | 0.0 |
| `no_gate` | 1/4 | 0.25 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`CREW_PRESSURE_LOST`、`DUAL_OBJECTIVE_COMPLETE`、`NAV_CORE_FLOODED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-02-S0-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.002918 | 是 |
| 1 | `V10-MAP-02-S1-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.00223008 | 是 |
| 2 | `V10-MAP-02-S2-l2` | NAV_CORE_FLOODED（failure） | 6 | 0 | 0.00266712 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.00781520（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V8 实例对 seed 不敏感（3-seed 未达标，见 validated-regression.md）
- 当前裁定：Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。

## 9. 证据索引

- 无 DCR（沿用 V9 规则）
- `runs/v10/baselines/MAP-02.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

