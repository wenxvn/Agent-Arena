# V7 Pilot-001R 执行报告（12/12 完整重跑）

> 状态：**completed / 12 局全部完整结束**。
> 日期：2026-10-17。
> 关系：本次是 [`pilot-001-report.md`](pilot-001-report.md) 所记录的中断 pilot 的**独立重跑**；原 pilot-001 账本保持关闭、未追加、未改写，本次使用新的 `runs/v7` 账本与运行目录。
> 预登记：沿用 [`pilot-001-registration.md`](pilot-001-registration.md) 的同一 12 局矩阵、同一预算上限与同一停止规则；用户明确授权继续完成该矩阵。本次不是新的假设筛选，也不是 30 图正式主实验。
> 运行基底：V6 六图 runtime + V7 只读指标层；未修改 V4/V5/V6 规则、Action 契约、Trace 写出器或历史账本。
> 结论级别：**E3-pilot，描述性；不是 V7 主实验，也不是 30 图矩阵。**

## 1. 执行摘要

| 项目 | 结果 |
|---|---|
| 预登记局数 | 12 |
| 实际启动 | 12 |
| 完整结束 | 12 |
| 中断 / 未启动 | 0 / 0 |
| 运行状态 | `completed`（manifest `stage=complete`） |
| 实际费用 | CNY `0.08521648` |
| 预留费用 | CNY `1.11616` |
| 费用上限 | 操作上限 CNY `2.00`；账本硬上限 CNY `11.00` |
| 请求尝试 | 109（109 settled，0 failed） |
| Token 使用 | 83,556 input / 10,740 output |
| Provider 墙钟 | 558.349 秒 |
| 实验 ID | `77ad5559-c8c0-44f0-bac5-b3c67d0aa5a4` |
| 账本 | `runs/v7/ledgers/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2.jsonl` |
| 运行目录 | `runs/v7/experiments/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2` |
| 冻结 gate | `5da2640ea50738c0be0f436452b9b98b2504e90347197fde234b9fcd9ba08402` |
| 运行时 commit | `e67fe0baf662033671c016910df88e80d8fc429d` |

本次 12 局按预登记顺序执行，未触发成本停止或 provider 停止条件。账本没有因 `unknown_provider_spend` 关闭；`runs/v7/pilot_registry.json` 已记录 `status=completed`、`stage=complete`、`completed_episode_count=12`。

## 2. 逐局结果

`status` 来自 `judge_metrics.json`；`cost` 来自账本结算。关键读数只列该局的主要、护栏和机制特有指标，完整 44 条 implemented 指标见 `v7_metrics_all.json`。

| # | 地图 | 实例 / 条件 | 状态 | 决策 | 费用 CNY | 关键 V7 读数 |
|---|---|---|---|---|---:|---|
| 1 | MAP-08 | `map08_l1_two_candidate` / `no_hypothesis_table` | success | 7 | 0.00574800 | `candidate_reduction=0.5`，`diagnosis_accuracy=1`，`information_gain_bits=1.0`，`legal_action_rate=1`，`peak_core_water=5`，`tests_run=1`，`wrong_repair=0` |
| 2 | MAP-08 | `map08_l3_original` / `hypothesis_table` | success | 6 | 0.00355176 | `candidate_reduction=0.666667`，`diagnosis_accuracy=1`，`information_gain_bits=1.584963`，`legal_action_rate=0.833333`，`peak_core_water=4`，`wrong_repair=0`；1 次 `INVALID_ACTION` |
| 3 | MAP-16 | `map16_l1_single_train` / `react` | success | 6 | 0.00253188 | `committed_ticks=3`，`makespan_gap=0`，`legal_reservation_rate=1`，`deadlock=0`，`node_capacity_conflicts=0`，`section_conflicts=0` |
| 4 | MAP-16 | `map16_l3_original` / `constraint_table` | failure | 8 | 0.00794100 | `committed_ticks=2`，`makespan_gap=N/A`，`legal_reservation_rate=0.8`，`legal_action_rate=0.875`，`node_capacity_conflicts=1`，`deadlock=0`；`INVALID_ACTION` + `SAFETY_VIOLATION` |
| 5 | MAP-18 | `map18_l2_alt_segment_r2b2` / `alert_off` | failure | 1 | 0.00133600 | `service_rate=0`（0/18），`station_capacity_violations=1`，`collision_violations=0`，`first_reroute_delay=N/A`，`recovery_delay=N/A`；首步即 `STATION_CAPACITY_EXCEEDED` |
| 6 | MAP-18 | `map18_l3_original` / `alert_on` | failure | 4 | 0.00533700 | `service_rate=0.333333`（6/18），`collision_violations=1`，`station_capacity_violations=0`，`first_reroute_delay=N/A`，`recovery_delay=N/A`；`HEAD_ON_COLLISION` |
| 7 | MAP-22 | `map22_l1_short_return` / `history5` | success | 4 | 0.00242700 | `path_gap=0`，`return_success=1`，`legal_action_rate=1`，`memory_facts_written=0`，`memory_grounding_violations=0`，`repeated_public_edge_rate=0` |
| 8 | MAP-22 | `map22_l3_original` / `history5_graph_memory` | success | 8 | 0.00762892 | `path_gap=1`，`return_success=1`，`legal_action_rate=1`，`memory_facts_written=10`，`memory_grounding_violations=0`，`illegal_bearing_actions=0` |
| 9 | MAP-26 | `map26_l3_software_fault` / `free_diagnosis` | failure | 11 | 0.00515092 | `diagnosis_accuracy=0`，`repair_success=0`，`recovery_latency=4`，`tests_run=0`，`spares_remaining=0`，`repeat_error_rate=0`；`RESOURCE_EXHAUSTION` |
| 10 | MAP-26 | `map26_recovery_power` / `recovery_full` | failure | 9 | 0.00474636 | `diagnosis_accuracy=1`，`repair_success=0`，`recovery_latency=3`，`tests_run=1`，`spares_remaining=0`，`legal_action_rate=0.888889`；`INVALID_ACTION` + `RESOURCE_EXHAUSTION` |
| 11 | MAP-30 | `map30_l3_original` / `history5_casebook` | failure | 44 | 0.03693264 | `evidence_chain_coverage=0.25`，`investigation_progress=0.25`，`chain_reconciled=0`，`unsupported_accusations=0`，`legal_action_rate=0.909091`，`q4_recall_accuracy=N/A`；`TIMEOUT` + `INVALID_ACTION` |
| 12 | MAP-30 | `map30_recall_original` / `history5_casebook` | success | 1 | 0.00188500 | `evidence_chain_coverage=1`，`investigation_progress=1`，`chain_reconciled=1`，`accusation_claim_precision=1`，`q4_recall_accuracy=1`，`unsupported_accusations=0` |

完整样本的成功计数为 6/12。该数字只用于核对矩阵完整性，**不是**六图能力排名：每图只有 1–2 局，且多数条件对使用不同实例。

## 3. 逐图读法

### MAP-08

两局均成功，`diagnosis_accuracy=1`，`wrong_repair=0`。L3 的 `candidate_reduction=0.666667`、`information_gain_bits=1.584963` 高于 L1，但两局实例不同，不能把差异归因于假设表；L3 另有 1 次 `INVALID_ACTION`，`legal_action_rate=0.833333`，仍完成诊断。该图继续表现为天花板候选，而不是条件效应证据。

### MAP-16

L1 `react` 成功，`makespan_gap=0`（BFS 最优 3 tick），无冲突。L3 `constraint_table` 失败：8 次决策、`committed_ticks=2`、`makespan_gap=N/A`、`node_capacity_conflicts=1`，并出现 `INVALID_ACTION` 与 `SAFETY_VIOLATION`。方向与 V6 L3 的失败一致，但本 pilot 没有同实例 `react` 对照，不能判断是约束表无效还是 L3 实例难度导致。

### MAP-18

两局均失败，但失败位置不同。`alert_off` 在第 1 次决策后即以 `STATION_CAPACITY_EXCEEDED` 终止，`service_rate=0`，`station_capacity_violations=1`；`alert_on` 交付 6/18 个任务后在 tick 3 发生 `HEAD_ON_COLLISION`，`service_rate=0.333333`、`collision_violations=1`。两局都没有可计算的首次改线延迟或恢复延迟（N/A），不能把 `alert_on` 的服务率差归因于告警条件；它只说明本局在告警开启时多走了一段才触发安全违例。

### MAP-22

L1 `history5` 成功，`path_gap=0`，4 次决策。L3 `history5_graph_memory` 成功，`path_gap=1`，8 次决策，写入 10 条记忆事实，`memory_grounding_violations=0`、`illegal_bearing_actions=0`。L3 的成功与 V6 post-hoc 中 graph memory 成功的方向一致，但本 pilot 只跑了 graph memory 一侧，没有同实例 `history5` 对照，不能据此声称图记忆带来了因果改善。

### MAP-26

两局均失败，且都不是 provider 中断。`free_diagnosis` 在 11 次决策后 `SPARES_EXHAUSTED`：`diagnosis_accuracy=0`、`repair_success=0`、`tests_run=0`、`spares_remaining=0`。`recovery_full` 在 9 次决策后同样 `SPARES_EXHAUSTED`：`diagnosis_accuracy=1`、`repair_success=0`、`recovery_latency=3`，并出现 1 次 `INVALID_ACTION`。这与 V6 post-hoc 中 recovery 0/9 修复的地板方向一致；free diagnosis 本次为 0 修复，说明该图在单局条件下仍无稳定正证据。

### MAP-30

`map30_l3_original` 在 44 次决策后 `DEADLINE_REACHED`，`evidence_chain_coverage=0.25`、`investigation_progress=0.25`、`chain_reconciled=0`，没有正式指控，因此 `accusation_claim_precision` 与 `q4_recall_accuracy` 为 N/A。`map30_recall_original` 在 1 次决策内完成正式指控并成功，`evidence_chain_coverage=1`、`q4_recall_accuracy=1`、`unsupported_accusations=0`。两者是不同实例；本 pilot 复现了 V6 中“纯召回容易、完整调查困难”的方向，但不能把差异归因于 casebook 条件本身。

## 4. 与 Pilot-001、V6 post-hoc 的关系

| 地图 | Pilot-001（中断版） | Pilot-001R（本次完整版） | V6 post-hoc | 读法 |
|---|---|---|---|---|
| MAP-08 | 两局成功 | 两局成功 | 6/6 成功、诊断全 1 | 方向一致；仍是天花板候选 |
| MAP-16 | L1 成功、L3 失败 | L1 成功、L3 失败 | L1 成功、L2/L3 失败 | 方向一致；L3 仍无 `makespan_gap` |
| MAP-18 | 两局失败，服务率 0–0.166667 | 两局失败，服务率 0–0.333333 | 服务率 0–0.333、9 有效/1 censored | 方向一致；两次运行的失败机制不同 |
| MAP-22 | L1 成功、L3 成功 `path_gap=3` | L1 成功、L3 成功 `path_gap=1` | L3 graph memory 成功 `path_gap=3` | 方向一致；单局波动明显 |
| MAP-26 | free 成功；recovery 中断 | free 失败；recovery 失败 | free 3/4 修复；recovery 0/9 | free 方向相反；recovery 地板一致 |
| MAP-30 | 无数据 | 完整调查失败、纯召回成功 | 完整调查 0/3；纯召回 1/1 | 方向一致；首次有两局完整数据 |

本次重跑和 Pilot-001 使用同一模型、同一温度（0）、同一 12 局矩阵，但多次结果发生方向性变化：MAP-16 L3 的决策数与失败分类、MAP-18 两局的失败机制、MAP-22 L3 的 `path_gap`、MAP-26 free 的成败、MAP-30 的运行时长都不相同。**这说明单局结果不稳定，不能把一次成功或失败写成条件效应或模型能力结论。** 正式 V7 主实验必须使用同实例多 seed 或重复配对，并预登记方差/停止规则。

## 5. 边界与未完成

1. **仍是 E3-pilot，不是主实验**：12 局完整只代表矩阵执行完整，不代表 30 图矩阵或六图能力结论。每图只有 1–2 局，不能计算稳定的成功率、均值、置信区间或显著性。
2. **单 seed、单局/条件**：所有 episode 为 `seed=0`；没有重复测量，也没有跨模型复现。
3. **多数条件对不是同实例配对**：MAP-08、MAP-16、MAP-18、MAP-22 的条件对使用不同实例或不同难度，条件差异与实例差异混在一起。
4. **MAP-18 改线指标为 N/A**：两局都没有可计算的首次改线/恢复延迟，不能记 0。
5. **MAP-30 两局不同实例**：完整调查失败与纯召回成功不能直接构成 casebook 的因果对照。
6. **24 图仍无运行时**：本 pilot 只使用 MAP-08/16/18/22/26/30 的 V6 runtime；MAP-01–07、09–15、17、19–21、23–25、27–29 仍为 `design_only`。
7. **12 条 DCR 仍为 `proposed`**：本 pilot 没有修改 V4 规则，也没有把 DCR 标成已批准。
8. **不是 V7 30 图正式矩阵**：没有多 seed、没有跨模型、没有 30 图可视化或完整基线运行器。
9. **历史账本未被改写**：Pilot-001 的旧账本、旧 registry 归档副本、V2/V5/V6 账本与 registry 均未追加或改写。

## 6. 证据与复算

| 证据 | 路径 / 值 |
|---|---|
| 运行目录 | `runs/v7/experiments/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2` |
| 账本 | `runs/v7/ledgers/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2.jsonl` |
| 运行 manifest | `run_manifest.json`，SHA-256 `28d2241b262b8278a75e88b8d5da169fc3951b0545c1a3769fce34bedc385a6b` |
| V7 复算 JSON | `v7_metrics_all.json`，SHA-256 `5390ab8e43a6168ea25c06bb2069b0646e24f9ea5dfb1a2d1e50a80e9ed673c1` |
| 账本 SHA-256 | `ea8158ec60e37f3492c277cefd11118ccdb63258c4a8c3e26b863936d87525f5` |
| Trace 数 | 12（全部完整） |
| V7 复算 | 12 `computed`、0 `design_only`、0 `invalid_trace` |
| Pilot-001 旧 registry 归档 | `runs/v7/archived/pilot_registry.pilot-001.json` |

复算命令：

```powershell
.venv\Scripts\python.exe scripts\report_v7_metrics.py `
  runs\v7\experiments\v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2 `
  --json runs\v7\experiments\v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2\v7_metrics_all.json
```

`report_v7_metrics.py` 处理 12 条 trace 全部成功；没有用 0 填补 N/A、censored 或 unavailable。

## 7. 安全与泄漏

- 未在 `runs/v7/` 中发现 API 密钥、Bearer 授权头、密钥环境变量赋值或常见密钥前缀的文本（本地扫描 0 hits）。
- trace 未包含完整 prompt、隐藏真值或未来事件；V7 指标只读取公开 trace 与离线 judge 字段。
- 账本不含密钥；stdout 只含进度、费用和 episode 状态。
- 历史 V6 账本与 registry 未被打开、追加或改写；Pilot-001 的旧账本同样保持原样。

## 8. 结论

Pilot-001R 在独立新账本上完成了 Pilot-001 预登记的 **12/12 局**，实际费用 CNY `0.08521648`，109 次请求，无未知花费或中断。它补上了 Pilot-001 缺失的 MAP-30 两局和 MAP-26 recovery 完整局，使六图都有完整的 V7 指标读数。

但本次仍只是 **E3-pilot**：单 seed、每条件 1 局、多数条件对不是同实例配对，且同一矩阵的两次运行已出现方向性波动。正确处理是：把 Pilot-001 与 Pilot-001R 分开保留，把本次作为“矩阵执行完整、描述性指标可复算”的证据，而不是 V7 主实验、30 图能力排名或 24 图运行时验证。
