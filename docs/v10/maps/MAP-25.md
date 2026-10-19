# MAP-25｜月球 · 第一次出舱（简单）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`DCR-V10-33`
- `rule_hash`：`24f54a32117db874e36cb0e3ffaf46335d59971593335d92d7fef3d6186e3418`
- `metric_hash`：`c126d69dae6c760c9cc4725a7a64a1657e6d6ea8359e0c2625f9a614f3ad1393`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 9f：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含出舱依赖链与工具组合

- 主指标：`map25.v10.mission_success`
  - `map25.v10.mission_success`：按依赖顺序完成准备、出舱、诊断与维修并安全返舱（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 4/4。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. H（居住舱）—T（装备间）—A（气闸）为舱内通路；A 之外是阵列 S。
2. 在 T 穿 EVA 服、取诊断单元与扳手并检查装备；在 A 挂安全绳；排压后才能出舱（未穿服/未挂绳/未排压都会失败）。
3. 在 S 先检查阵列、再用诊断单元诊断，维修必须带齐诊断单元与扳手并给出诊断码。
4. 维修后依次返回 A、增压、经 T 回 H；回到 H 且维修完成才算成功。
5. 氧气只在舱外消耗（出舱、检查、诊断、维修、返舱各计费），本实例的起始位置与氧气预算见 Observation。

### Observation 公开字段

`airlock_pressure`、`array_repaired`、`array_surface_symptom`、`carried_tools`、`diagnosis_code_if_obtained`、`goal`、`inner_hatch_locked`、`location`、`oxygen_remaining`、`suit_worn`、`tether_attached`、`tick`、`visible_equipment_here`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`label`、`oxygen`、`start`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`eva`、`oxygen`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `depressurize` | {tool} |
| `diagnose` | {device_id,tool} |
| `equip` | {item_id,target,tool} ｜ {item_id,tool} |
| `eva_exit` | {tool} |
| `inspect` | {target,tool} |
| `move` | {to,tool} |
| `pressurize` | {tool} |
| `repair` | {diagnosis_code,target_id,tool,tool_ids} ｜ {target_id,tool,tool_ids} |
| `return_to_A` | {tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3`（4 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`4`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `2248539a017c0130` |
| 1 | `37bb657e70246cc2` |
| 2 | `7db8bd70585ddeb7` |
| 3 | `159a38fb0327afad` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map25.v10.mission_success` | primary | higher | 按依赖顺序完成准备、出舱、诊断与维修并安全返舱 | 1 | NOT_APPLICABLE | 截尾 → CENSORED；装备/顺序/氧气终局 → VALID 0 | ratio | (0.0, 1.0) |
| `map25.v10.required_check_coverage` | secondary | higher | 已完成的必需步骤 / 7 | 7 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map25.v10.dependency_order_correctness` | secondary | higher | 前置满足的必需步骤 / 已尝试必需步骤 | 已尝试的必需步骤 | 未尝试任何必需步骤 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map25.v10.unsafe_eva_attempts` | guardrail | lower | 未穿服或未挂绳的出舱尝试次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 20.0) |
| `map25.v10.oxygen_shortfall` | guardrail | lower | 因氧气耗尽终局（1 表示失败） | 1 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map25.v10.completion_ticks` | diagnostic | lower | 成功时的完成 tick | 成功局（1） | 未成功 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `no_diagnosis` | 0/4 | 0.0 |
| `no_tether` | 0/4 | 0.0 |
| `skip_array_inspection` | 0/4 | — |
| `wrong_tools` | 0/4 | — |

- Oracle：4/4（机制触发 4/4）
- 公开启发式：4/4（主指标均值 1.0）
- legal_random：0/80（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`ALL_OBJECTIVES_COMPLETE`、`OXYGEN_DEPLETED`、`UNSAFE_UNTETHERED_EVA`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-25-S0-p2` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.01587828 | 是 |
| 1 | `V10-MAP-25-S1-p2` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.01240108 | 是 |
| 2 | `V10-MAP-25-S2-p2` | decision_budget_exhausted（decision_budget_exhausted） | 30 | None | 0.01385012 | 是 |

- 有效局成功：0/3
- 结算成本合计 CNY 0.04212948（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V10 原生 4 seed：起始位置（H/T）与氧气预算（12/10）随 seed 变化
- 当前裁定：Batch 9f：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含出舱依赖链与工具组合
- 剩余风险：公式级独立复算（第二套实现重算分子分母）未按图完成；现有检查为规格驱动五态核对 + 可复现回放。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-33.md`
- `runs/v10/baselines/MAP-25.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

