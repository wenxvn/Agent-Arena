# MAP-20｜火山 · 冷却网络（中等）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-11`
- `rule_hash`：`e677a0acc1d837027281f2d1be6ab0b55835861fc8ddab65a561663c1924002d`
- `metric_hash`：`b80e5ea1790f5ff813676ca4bbd986afb50e55f6370ebc3ae800802a8bf65fa2`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 4：产能与热量解耦、动态热点公开；区阀 C 30→35；static_allocation 0/4、no_bypass 0/4、bypass_overuse 0/4；Oracle bypass_used 10/10 tick

- 主指标：`map20.v10.production_credit`
  - `map20.v10.production_credit`：实得产能 / 目标（覆盖热量的区拿满，缺水的区按比例）（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 三区 A/B/C，每 tick 结算一次：T_next = max(0, T + 本 tick 热量 − 交付水)。
2. 水源每 tick 60；单支管直供上限 25；区阀上限 A/B/C = 40/40/35；交付超过区阀 → 整帧拒绝。
3. set_flow(tenths)：`set_flow_tenths` 是长度为 3 的整数数组，顺序固定为区 A、B、C；每项 0–25，三项之和不超过水源 60，超限整帧拒绝。
4. adjust_loads(loads)：`adjust_loads` 是长度为 3 的字符串数组（顺序 A、B、C），取值只能是 "FULL"、"REDUCED"、"IDLE"；三档的热量分别为 本 tick 热量、本 tick 热量 ×0.5、0。
5. open_bypass(bypasses)：`open_bypasses` 是以链路名为键的对象，链路只能是 "AB" 或 "BC"；值为 {"from": 端点, "to": 另一端点, "input_tenths": 取水档位}，端点取自该链路两端；`input_tenths` 必须是 5 的整数倍且不超过 20（可选 5/10/15/20）。
6. 旁路按 5 一档、单链路上限 20，下游只收到 4/5。
7. **本 tick 三区热量公开**（heat_schedule）；热点区热量会超过单支管上限，必须从邻区经有损旁路调水。
8. 区产量系数 A/B/C = 4/3/2：交付覆盖该区热量才拿满，否则按 交付/热量 折减。
9. 在 10 tick 内累计目标产能且三区不超过 10.0 即成功。

### Observation 公开字段

`bypass_settings`、`current_load_modes`、`current_temperatures_tenths`、`direct_flow_tenths`、`flow_rules`、`goal`、`heat_schedule`、`last_temperature_reading`、`previous_tick_flow_ledger`、`production_base`、`production_points`、`production_target`、`source_water_remaining_this_tick`、`temperature_bands`、`tick`、`ticks_remaining`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`heat_schedule`、`hot_heat`、`hot_sequence`、`idle_heat`、`label`、`production_base`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`horizon`、`initial_temperatures`、`label`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `adjust_loads` | {adjust_loads,tool} |
| `open_bypass` | {open_bypasses,tool} |
| `read_temperature` | {station,tool} |
| `set_flow` | {set_flow_tenths,tool} |
| `wait` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `fa615ee529ebd906` |
| 1 | `6930539428e24d4a` |
| 2 | `8ae3e0e49fced098` |
| 3 | `c8f3fed9682e7156` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map20.v10.production_credit` | primary | higher | 实得产能 / 目标（覆盖热量的区拿满，缺水的区按比例） | 目标产能 | NOT_APPLICABLE | 截尾 → CENSORED；热越界 → VALID 0（按已结算 tick 计） | ratio | (0.0, 1.0) |
| `map20.v10.zones_covered_ticks` | secondary | higher | 交付水覆盖本 tick 热量的 区·tick 数 | 已结算区·tick 数 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map20.v10.bypass_used_ticks` | diagnostic | higher | 旁路实际改变交付向量并帮助覆盖热点的 tick 数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map20.v10.flow_conservation_violations` | guardrail | lower | 非法控制帧次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 40.0) |
| `map20.v10.thermal_exceedance_tenths` | guardrail | lower | Σ max(0, T − 100) / 已结算区·tick 数 | 已结算区·tick 数 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | temperature_tenths | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `bypass_overuse` | 0/4 | 0.451 |
| `no_bypass` | 0/4 | 0.9412 |
| `static_allocation` | 0/4 | 0.9118 |
| `zero_flow` | 0/4 | 0.0 |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 0.3101）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`PRODUCTION_BELOW_TARGET`、`PRODUCTION_TARGET_MET`、`THERMAL_OVERHEAT`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-20-S0-ext` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.05722948 | 是 |
| 0 | `V10-MAP-20-S0-j2` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.01219616 | 是 |
| 1 | `V10-MAP-20-S1-ext` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.05725844 | 是 |
| 1 | `V10-MAP-20-S1-j2` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.00812904 | 是 |
| 2 | `V10-MAP-20-S2-ext` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.0575778 | 是 |
| 2 | `V10-MAP-20-S2-j2` | decision_budget_exhausted（decision_budget_exhausted） | 56 | 0.0 | 0.00999968 | 是 |

- 有效局成功：0/6
- 结算成本合计 CNY 0.20239060（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；4 实例
- 当前裁定：Batch 4：产能与热量解耦、动态热点公开；区阀 C 30→35；static_allocation 0/4、no_bypass 0/4、bypass_overuse 0/4；Oracle bypass_used 10/10 tick
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-11.md`
- `runs/v10/baselines/MAP-20.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

