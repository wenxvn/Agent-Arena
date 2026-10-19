# MAP-01｜飞船 · 破损的曙光号（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-31`
- `rule_hash`：`49951ca491bd0a573fd8ecee271a52421d28968b93184e345356d84d518ac09b`
- `metric_hash`：`994de84ec19f38ea3fa01873290e8ebe0e58cbfcbdfc4c0fa29a4e4a82f589b0`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9e：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含互斥供电与船壳依赖链

- 主指标：`map01.v10.mission_success`
  - `map01.v10.mission_success`：修复船壳、恢复供氧与主电源、完成气闸检查并在舰桥确认（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 舰内拓扑：B（舰桥）—H（中枢）—W（船壳/配电）、H—P（反应堆）、H—A（气闸）；W—P 服务通道只在船壳修补后才能通行。
2. 供氧继电器可在 B/H 启动供氧；启动后若把配电切到维修臂，供氧会中断，断供期间氧气储备每 tick 递减，超过容错上限立即失败。
3. 修补船壳的顺序：先取 patch_kit（需供氧稳定）→ 在 W 把配电切到维修臂 → patch 船壳 → 切回供氧。
4. 母线重置必须在船壳修补后；气闸压力测试要求供氧与母线同时在线；最后回 B 在舰桥确认。
5. 公开配电参数（容量/固定负载/供氧/维修臂）见 inspect(power_diagram)；本实例的氧气储备与断供容错以 Observation 的 oxygen_reserve 与规则为准。

### Observation 公开字段

`airlock_sealed`、`goal`、`hull_intact`、`inventory`、`location`、`main_bus`、`oxygen_output`、`oxygen_reserve`、`pressure_test`、`repair_arm`、`routed_branch`、`service_edge_open`、`visible_edges`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`label`、`loads`、`off_limit`、`oxygen_reserve`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`life_support`、`off_limit`

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
| 0 | `2b7e5276473a1c5b` |
| 1 | `bf36ef9220c95452` |
| 2 | `c45e90cc6d71250d` |
| 3 | `82947c5754a8514e` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map01.v10.mission_success` | primary | higher | 修复船壳、恢复供氧与主电源、完成气闸检查并在舰桥确认 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；氧气/断供终局 → VALID 0 | ratio | (0.0, 1.0) |
| `map01.v10.dependency_satisfaction_rate` | secondary | higher | 已满足的依赖前置数 / 6（供氧→取件→断电→修壳→母线→气闸→确认） | 6 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map01.v10.longest_oxygen_outage_ticks` | guardrail | lower | 最长断供连续 tick | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |
| `map01.v10.oxygen_guardrail_violations` | guardrail | lower | 因氧气耗尽/断供超限导致的终局（1 表示失败） | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map01.v10.dependency_violations` | guardrail | lower | 违反依赖顺序的动作次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map01.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `arm_before_pickup` | 0/4 | — |
| `early_confirm` | 0/4 | 0.0 |
| `no_support_restore` | 0/4 | 0.0 |
| `skip_bus` | 0/4 | — |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`、`REPAIR_CONFIRMED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-01-S0-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT（failure） | 4 | 0 | 0.002585 | 是 |
| 1 | `V10-MAP-01-S1-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT（failure） | 4 | 0 | 0.002582 | 是 |
| 2 | `V10-MAP-01-S2-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT（failure） | 5 | 0 | 0.0011418 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.00630880（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：氧气储备/断供容错/公开配电参数随 seed 变化；15 动作方案在四实例都可行
- 当前裁定：Batch 9e：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含互斥供电与船壳依赖链
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-31.md`
- `runs/v10/baselines/MAP-01.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

