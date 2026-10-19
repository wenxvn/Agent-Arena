# MAP-10｜极地 · 燃料运输（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-20`
- `rule_hash`：`aa2df0ee7a8634eb327790a0712189f24e7dabfe4c80ec696de682d56e1dd910`
- `metric_hash`：`cbb416e19cf4cf928b663f058eb15d81c533337190387a3ee005c6f79da8d036`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5：油耗 = burn_base + ceil(cargo/2)、容量与库存双约束；max_load 1/4（烧光油）、underload 0/4（货不够）、no_move 0/4

- 主指标：`map10.v10.mission_success`
  - `map10.v10.mission_success`：抵达补给站且 cargo ≥ 必需量（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. A 到补给站 D 一次移动；油耗 = burn_base + ceil(cargo / 2)，burn_base 与容量、库存公开。
2. load(quantity)：装载量 ≤ capacity 且 ≤ 站点库存；可以分多次装。
3. move：燃料不足即 OUT_OF_FUEL，货物一并损失。
4. 抵达时必须 cargo ≥ required_delivery 才算成功；unload 只是把货卸到站点。

### Observation 公开字段

`burn_base`、`burn_formula`、`capacity`、`cargo`、`delivered`、`fuel`、`goal`、`load_retries`、`location`、`required_delivery`、`station_stock`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`burn_base`、`capacity`、`initial_fuel`、`label`、`required_delivery`、`station_stock`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`best_load`、`label`、`required`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `load` | {quantity,tool} |
| `move` | {to,tool} |
| `unload` | {quantity,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `17e91caf6f387ac7` |
| 1 | `21bdc4ef6cc15930` |
| 2 | `6a75efc16bf98b0f` |
| 3 | `ac380607e7aaf138` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map10.v10.mission_success` | primary | higher | 抵达补给站且 cargo ≥ 必需量 | 1 | NOT_APPLICABLE | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map10.v10.delivered_ratio` | secondary | higher | 交付量 / 必需量（截断到 1） | 必需量 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map10.v10.fuel_left` | secondary | higher | 抵达后剩余燃料 | 抵达过的局（1） | 未抵达 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | fuel | (0.0, 40.0) |
| `map10.v10.load_retries` | diagnostic | lower | 重复装载次数（多付一次决策） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 10.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `max_load` | 1/4 | 0.25 |
| `no_move` | 0/4 | — |
| `underload` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`DELIVERED_IN_FULL`、`DELIVERY_SHORT`、`OUT_OF_FUEL`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-10-S0-interface` | DELIVERED_IN_FULL（success） | 2 | 1 | 0.000791 | 是 |
| 1 | `V10-MAP-10-S1-interface` | DELIVERED_IN_FULL（success） | 2 | 1 | 0.000787 | 是 |
| 2 | `V10-MAP-10-S2-interface` | DELIVERED_IN_FULL（success） | 2 | 1 | 0.00054012 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.00211812（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 5：油耗 = burn_base + ceil(cargo/2)、容量与库存双约束；max_load 1/4（烧光油）、underload 0/4（货不够）、no_move 0/4
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-20.md`
- `runs/v10/baselines/MAP-10.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

