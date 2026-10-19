# MAP-23｜丛林 · 迷雾中的遗迹（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-13`
- `rule_hash`：`82922e4cad90d704ee89bbbc845df2efc9182cffe9bf7a49a19bb8f61c2ad767`
- `metric_hash`：`59bd67e0af0f86b2f7de2f5f944bb53d376950bde51f61586e5b72494efc0051`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：出手需要已购线索 + 相容 mark；4 入口 × 3 侦察站使线索价格与信息量错开；no_scout 0/4（V9 为 12 决策成功）、ignore_counterevidence 0/4、scout_everything 0/4、single_clue 2/4

- 主指标：`map23.v10.clue_utilization`
  - `map23.v10.clue_utilization`：最强单条已购线索缩减的候选比例 (n − |supports|) / (n − 1)（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. A 是枢纽，直连 N/R/H（侦察站）与 X/Y/Z/W（入口）；move(to) 扣路费。
2. scout 只在侦察站可用、每站一次，费用 {'N': 2, 'R': 2, 'H': 3}；返回该站的 supports （该线索认为可能的入口集合）。
3. investigate 必须先 mark 声明候选，且必须**至少买过一条线索**，并且候选不能被已购线索排除；否则被拒并记 unjustified。
4. 调查费用 {'X': 2, 'Y': 2, 'Z': 3, 'W': 3}；真入口 + 扣费后补给 > 0 即成功。
5. A 的补给箱一次性补满到 16。

### Observation 公开字段

`actions_taken`、`agent_marked_candidate`、`available_scout_stations`、`clues_received`、`entrances`、`goal`、`investigation_cost`、`location`、`neighbors`、`resupply_cache_available`、`scout_cost`、`searched_false_entrances`、`supply_remaining`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`edges`、`entrances`、`investigation_cost`、`scout_cost`、`scout_stations`、`supply_initial`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`signals`、`true_entrance`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `investigate` | {entrance,tool} |
| `mark` | {choice,tool} |
| `move` | {to,tool} |
| `resupply` | {tool} |
| `scout` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `c3842d196067e6c7` |
| 1 | `f4dd53aea436b4c6` |
| 2 | `5aff0eb1a3249aee` |
| 3 | `0467d3a122a3de35` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map23.v10.clue_utilization` | primary | higher | 最强单条已购线索缩减的候选比例 (n − |supports|) / (n − 1) | 买过线索的局（1） | 未侦察 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map23.v10.spent_ratio` | secondary | lower | 花费补给 / 初始补给 | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map23.v10.unjustified_investigations` | guardrail | lower | 缺少 mark / 线索 / 与线索矛盾的调查尝试次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map23.v10.repeated_invalid_exploration` | guardrail | lower | 对已排除入口再次调查的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map23.v10.ignored_counterevidence` | guardrail | lower | 最终调查入口是否已被已购线索排除 | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `ignore_counterevidence` | 0/4 | 0.6667 |
| `no_scout` | 0/4 | — |
| `scout_everything` | 0/4 | 0.8333 |
| `single_clue` | 2/4 | 0.6667 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 0.6667）
- legal_random：0/80（主指标均值 0.6667）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`SUPPLY_DEPLETED`、`TRUE_ENTRANCE_FOUND`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-23-S0-ext` | TRUE_ENTRANCE_FOUND（success） | 9 | 0.666667 | 0.006146 | 是 |
| 1 | `V10-MAP-23-S1-ext` | TRUE_ENTRANCE_FOUND（success） | 13 | 0.666667 | 0.0053098 | 是 |
| 2 | `V10-MAP-23-S2-ext` | TRUE_ENTRANCE_FOUND（success） | 6 | 0.666667 | 0.0027226 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.01417840（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 入口 4 真值
- 当前裁定：Batch 4：出手需要已购线索 + 相容 mark；4 入口 × 3 侦察站使线索价格与信息量错开；no_scout 0/4（V9 为 12 决策成功）、ignore_counterevidence 0/4、scout_everything 0/4、single_clue 2/4
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-13.md`
- `runs/v10/baselines/MAP-23.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

