# MAP-21｜火山 · 喷发倒计时（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-05`
- `rule_hash`：`a73f51094dde4c07e3331d221666559b145132b9e4a41830245f352f7b7c4b78`
- `metric_hash`：`54e1ce05f44653336ed8ce310e7c26ead30f57ea9b34d0e4bb4c7ac3965a4917`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高

- 主指标：`map21.v10.overall_utility`, `map21.v10.safety_success`
  - `map21.v10.overall_utility`：safety_success × (0.5 + 0.5 × science_completion)（方向：higher）
  - `map21.v10.safety_success`：喷发前抵 E（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 10/10。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 地图：O—R(1)—W(2)—S(2)—E(2)，另有 O—E 直达(6)；括号为耗时 tick。move 在途中自动推进，抵达前其他动作被拒。到达 E 即安全撤离并结算。
2. 喷发时刻隐藏，只可能是 12/16/20，先验 0.2/0.5/0.3。喷发 tick 时仍未抵 E 即死亡，失去全部科研。同 tick 抵 E 视为安全。
3. measure 只能在 O 用一次，耗 2 tick，返回 EARLY_WARNING 或 LATE_WARNING；P(EARLY | 12/16/20) = 0.8/0.3/0.1；后验在 posterior_over_eruption_ticks 公开。
4. 样品（只能带一件）：R_SURFACE_ASH 在 R 采集耗 1 tick 得 5 分；W_LAYERED_CORE 在 W 耗 5 tick 得 12 分（加固后 20）；S_DEEP_ISOTOPE 在 S 耗 6 tick 得 40 分（加固后 50）。reinforce_sample_case 只能在 W 或 S 用一次，耗 1 tick，对当地样品生效。
5. 测量记录也算 5 分科研。科研分只有安全撤离才计入。被拒动作耗 1 tick。
6. 评分：安全撤离为前提，overall = 0.5 + 0.5 × 科研完成度；死亡为 0。立即撤离是合法且安全的选择，但科研完成度为 0。

### Observation 公开字段

`available_edges`、`carried_sample`、`elapsed_tick`、`goal`、`in_transit_edge`、`location`、`measurement_available`、`posterior_over_eruption_ticks`、`reinforced_site`、`reinforcement_kit_available`、`returned_measurement`、`sample_catalog`、`science_points_carried`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`eruption_candidates`、`prior`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`eruption_tick`、`measurement`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `collect_and_carry_sample` | {sample_id,tool} |
| `measure` | {tool} |
| `move` | {edge_id,tool} |
| `reinforce_sample_case` | {tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5, 6, 7, 8, 9`（10 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`10`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `d8e3f7320412f3c7` |
| 1 | `5e8e262f7ddef67c` |
| 2 | `b06bf8f20cc82e4d` |
| 3 | `8d384d6aff197dff` |
| 4 | `9ffe87107ae3180d` |
| 5 | `fd02f4e68ec8579a` |
| 6 | `32abe6b70f71e2fb` |
| 7 | `5ad20c1567b51662` |
| 8 | `46e406dfa5171259` |
| 9 | `1970570ef48fed2f` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map21.v10.overall_utility` | primary | higher | safety_success × (0.5 + 0.5 × science_completion) | 1 | NOT_APPLICABLE | 运行中截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map21.v10.safety_success` | primary | higher | 喷发前抵 E | 1 | NOT_APPLICABLE | 运行中截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map21.v10.science_completion` | secondary | higher | 安全带回的(样品分 + 测量 5) / 该 seed 真值可得最大科研分 | 1 | NOT_APPLICABLE | 未撤离 → 0（失去全部科研）；截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map21.v10.catastrophe` | guardrail | lower | FATAL_ERUPTION | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map21.v10.risk_exposure_integral` | guardrail | lower | Σ_tick P(T ≤ t | 公开后验)，抵 E 前 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | probability_ticks | (0.0, 30.0) |
| `map21.v10.safety_margin_ticks` | diagnostic | none | 最早仍可能喷发时刻(后验>0) − 抵 E tick | 安全撤离局 | 未撤离 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (-10.0, 20.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `always_collect` | 7/10 | 0.6682 |
| `always_evac` | 10/10 | 0.5 |
| `measure_then_evac` | 10/10 | 0.5943 |

- Oracle：10/10（机制触发 10/10）
- 公开启发式：10/10（主指标均值 0.6886）
- legal_random：0/200（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`EVACUATED_BEFORE_ERUPTION`、`FATAL_ERUPTION`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-21-S0-p0` | EVACUATED_BEFORE_ERUPTION（success） | 7 | 0.654546 | 0.00589824 | 是 |
| 1 | `V10-MAP-21-S1-p0` | EVACUATED_BEFORE_ERUPTION（success） | 6 | 0.916667 | 0.00438948 | 是 |
| 2 | `V10-MAP-21-S2-p0` | EVACUATED_BEFORE_ERUPTION（success） | 6 | 0.590909 | 0.00232772 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.01261544（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；安全/科研分离评分
- 当前裁定：Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-05.md`
- `runs/v10/baselines/MAP-21.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

