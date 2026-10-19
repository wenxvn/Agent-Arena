# MAP-24｜丛林 · 消失的道路（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-14`
- `rule_hash`：`79dea80fcdc552b3bee85cf793a3eba4f6b613c7dc259f91faa636524875401e`
- `metric_hash`：`ff8f11d2c94f4c1cd03907802cea4b741bd29fd71f4df879dbc0b4562cf6f342`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：山路拉长、封路时刻隐藏且不瞬杀、公开 collapse_observed；两条 primary 重定义；no_replan 0/4（replan_success 0）、mountain_only 记为 N/A 合法替代

- 主指标：`map24.v10.replan_success`
  - `map24.v10.replan_success`：观察到封路后完成且不再尝试断边（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 路网：A-B-C-D-E-A 环 + A-F-C 山路；A-B 与 B-C 是桥，C-D、D-E、E-A 是地面/潮道。
2. 任务：把 relic_C（在 C）与 supply_case_D（在 D）都带回 A；两者都要。
3. 桥会在**未知时刻**永久断开；站在桥上会被推回岸边并多耗 2 tick。
4. D-E 潮道每 4 tick 开 2 tick，相位隐藏；measure_tide 在 D 或 E 读出下一 tick 的状态。
5. probe_bridge 只能在 B 用，耗 2 tick，读出桥是否已断。
6. 山路 A-F-C 比桥路慢：桥路 2 tick 到 C，山路 6 tick。
7. tick 18 前把两件物资带回 A 即成功。

### Observation 公开字段

`bridge_probe_result`、`carried_items`、`collapse_observed`、`deadline_tick`、`goal`、`latest_local_tide_reading`、`local_connections`、`location`、`route_notes`、`tick`、`tide_rule`、`visible_item_here`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`deadline_tick`、`label`、`max_bridge_route_ticks`、`mountain_route_ticks`、`tide`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`collapse_tick`、`deadline`、`label`、`phase_offset`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `measure_tide` | {tool} |
| `move` | {to,tool} |
| `probe_bridge` | {tool} |
| `record_route` | {tool} |
| `take` | {item_id,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `02357895deddcaaa` |
| 1 | `5b9ec38d57ffa546` |
| 2 | `d10a80fac6f74d0c` |
| 3 | `080db7e16df92603` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map24.v10.replan_success` | primary | higher | 观察到封路后完成且不再尝试断边 | 观察到封路的局（1） | 从未观察到封路 → NOT_APPLICABLE（截尾 → CENSORED） | 截尾 → CENSORED | ratio | (0.0, 1.0) |
| `map24.v10.replan_latency` | secondary | lower | 观察封路后的第一个移动 tick − 观察 tick | 观察到封路的局（1） | 从未观察到封路 → NOT_APPLICABLE（截尾 → CENSORED） | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (-5.0, 30.0) |
| `map24.v10.collapsed_edge_attempts_after_observation` | guardrail | lower | 观察到封路后仍尝试断边的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 40.0) |
| `map24.v10.route_cost_ratio` | guardrail | lower | 观察封路后到交付的实际移动成本 / 同点最短可行成本 | 观察到封路且最短成本 > 0 的局（1） | 最短成本为 0 或未观察 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map24.v10.tide_failed_moves` | diagnostic | lower | 潮道关闭时仍尝试通过的次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 40.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `mountain_only` | 4/4 | — |
| `no_replan` | 0/4 | 0.0 |
| `waste_opening` | 2/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.0）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ALL_ITEMS_DELIVERED`、`DEADLINE_EXCEEDED`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-24-S0-ext` | ALL_ITEMS_DELIVERED（success） | 9 | 1 | 0.006371 | 是 |
| 1 | `V10-MAP-24-S1-ext` | ALL_ITEMS_DELIVERED（success） | 9 | 1 | 0.00286568 | 是 |
| 2 | `V10-MAP-24-S2-ext` | ALL_ITEMS_DELIVERED（success） | 9 | 1 | 0.00282396 | 是 |

- 有效局成功：3/3
- 结算成本合计 CNY 0.01206064（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 4：山路拉长、封路时刻隐藏且不瞬杀、公开 collapse_observed；两条 primary 重定义；no_replan 0/4（replan_success 0）、mountain_only 记为 N/A 合法替代
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-14.md`
- `runs/v10/baselines/MAP-24.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

