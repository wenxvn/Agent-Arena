# V7 Pilot-001 执行报告（按停止规则封账）

> 状态：**stopped / 未完成 12 局**。12 局预登记中，10 局启动、9 局完整结束、1 局因 provider 连接错误中断、2 局未启动。
> 日期：2026-10-17。
> 预登记：[`pilot-001-registration.md`](pilot-001-registration.md)。
> 运行基底：V6 六图 runtime + V7 只读指标层；未修改 V4/V5/V6 规则、Action 契约、Trace 写出器或历史账本。
> 结论级别：**E3-pilot，描述性，不是 V7 主实验，也不是 30 图矩阵。**

## 1. 执行摘要

| 项目 | 结果 |
|---|---|
| 预登记局数 | 12 |
| 实际启动 | 10 |
| 完整结束 | 9 |
| 中断 | 1（MAP-26 `recovery_full`，第 8 次决策） |
| 未启动 | 2（MAP-30 两局） |
| 停止原因 | `APIConnectionError`，`unknown_spend=true`，账本按 `UNKNOWN_PROVIDER_SPEND` 关闭 |
| 是否续跑 | 否；账本已关闭，未创建 successor ledger |
| 实际费用 | CNY `0.05086048` |
| 预留费用 | CNY `0.68608` |
| 费用上限 | 操作上限 CNY `2.00`；账本硬上限 CNY `11.00` |
| 请求尝试 | 67（66 settled + 1 failed） |
| Token 使用 | 46,044 input / 7,614 output（含中断局已结算部分） |
| Provider 墙钟 | 398.718 秒 |
| 账本 | `runs/v7/ledgers/v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53.jsonl` |
| 运行目录 | `runs/v7/experiments/v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53` |

中断发生在 MAP-26 `map26_recovery_power__recovery_full__seed_0` 的第 8 次请求：请求等待 12,619 ms 后返回 `APIConnectionError`，provider 未给出可确认的结算信息，V6 账本将 `unknown_spend` 记为真并立即关闭。V7 driver 按预登记停止规则不再启动 MAP-26 后续局和 MAP-30 两局。

## 2. 逐局结果

`status` 来自 `judge_metrics.json`；`cost` 来自账本结算；第 10 局为中断局，不计入“完整结束”样本。

| # | 地图 | 实例 / 条件 | 状态 | 决策 | 费用 CNY | 关键 V7 读数 |
|---|---|---|---|---|---|---:|---|
| 1 | MAP-08 | `map08_l1_two_candidate` / `no_hypothesis_table` | success | 7 | 0.00403256 | `candidate_reduction=0.5`，`diagnosis_accuracy=1`，`tests_run=1`，`peak_core_water=5` |
| 2 | MAP-08 | `map08_l3_original` / `hypothesis_table` | success | 6 | 0.00553780 | `candidate_reduction=0.666667`，`diagnosis_accuracy=1`，`information_gain_bits=1.58496`，`legal_action_rate=0.833333`，`peak_core_water=4` |
| 3 | MAP-16 | `map16_l1_single_train` / `react` | success | 6 | 0.00277948 | `makespan_gap=0`（BFS 最优 3 tick），`legal_reservation_rate=1`，`deadlock=0`，`node_capacity_conflicts=0` |
| 4 | MAP-16 | `map16_l3_original` / `constraint_table` | failure | 6 | 0.00408916 | `makespan_gap=N/A`，`node_capacity_conflicts=1`，`deadlock=0`，`legal_reservation_rate=1` |
| 5 | MAP-18 | `map18_l2_alt_segment_r2b2` / `alert_off` | failure | 6 | 0.00709160 | `service_rate=0.166667`（3/18），`recovery_delay=censored`，`collision_violations=1`，`station_capacity_violations=0` |
| 6 | MAP-18 | `map18_l3_original` / `alert_on` | failure | 1 | 0.00123712 | `service_rate=0`（0/18），`recovery_delay=N/A`（本局无公开封锁），`station_capacity_violations=1` |
| 7 | MAP-22 | `map22_l1_short_return` / `history5` | success | 4 | 0.00178980 | `path_gap=0`（BFS 最优 4 moves），`return_success=1`，`legal_action_rate=1`，`memory_facts_written=0` |
| 8 | MAP-22 | `map22_l3_original` / `history5_graph_memory` | success | 11 | 0.01212232 | `path_gap=3`（BFS 最优 8 moves），`return_success=1`，`legal_action_rate=0.818182`，`memory_facts_written=9`，`illegal_bearing_actions=1` |
| 9 | MAP-26 | `map26_l3_software_fault` / `free_diagnosis` | success | 12 | 0.00775860 | `diagnosis_accuracy=1`，`repair_success=1`，`tests_run=3`，`legal_action_rate=0.916667`，`spares_remaining=1` |
| 10 | MAP-26 | `map26_recovery_power` / `recovery_full` | unknown_provider_spend | 7 | 0.00442204 | `diagnosis_accuracy=0`，`recovery_latency=3`，`repair_success=censored`；中断局，不纳入完整样本 |
| — | MAP-30 | 两局 `history5_casebook` | 未启动 | — | — | 无数据 |

## 3. 逐图读法

### MAP-08

两局均成功。L1 无假设表 7 次决策，L3 有假设表 6 次决策；L3 的 `candidate_reduction=0.666667`、`information_gain_bits=1.58496`，但两局实例不同，不能把差异归因于假设表。L3 出现 1 次 `INVALID_ACTION`，`legal_action_rate=0.833333`，仍完成诊断；这与 V6 的 MAP-08 天花板一致，但本 pilot 没有同实例配对。

### MAP-16

L1 `react` 成功且 `makespan_gap=0`；L3 `constraint_table` 失败，`node_capacity_conflicts=1`，`makespan_gap=N/A`。约束表在本局没有阻止节点容量冲突；因为只有 1 局且实例不同，不能判断是条件无效还是实例难度。该结果与 V6 L3 的失败方向一致。

### MAP-18

两局均失败。`alert_off` 的 `service_rate=0.166667`，`recovery_delay=censored`，并出现 1 次碰撞；`alert_on` 仅 1 次决策即失败，`service_rate=0`，`station_capacity_violations=1`，且本局没有公开封锁，所以 `first_reroute_delay` 与 `recovery_delay` 都是 `N/A`。两局实例不同，`alert_on` 也没有触发封锁，不能把它当作“告警条件无效”的证据。

### MAP-22

L1 `history5` 成功，`path_gap=0`，4 次决策；L3 `history5_graph_memory` 成功，`path_gap=3`，11 次决策，写入 9 条记忆事实，并有 1 次非法方位动作。L3 的成功与 V6 post-hoc 中“`history5` 失败、`history5_graph_memory` 成功”的方向一致，但本 pilot 只跑了 graph memory 一侧，没有同实例 `history5` 对照，不能据此声称因果。

### MAP-26

`free_diagnosis` 成功，`diagnosis_accuracy=1`、`repair_success=1`、3 次测试；与 V6 free 条件的方向一致。`recovery_full` 是中断局：7 次决策后 provider 连接错误，`repair_success=censored`，不能作为恢复能力证据。

### MAP-30

两局均未启动，因此本 pilot 没有为 V6 post-hoc 的 casebook 1/1 覆盖率提供新证据，也没有更新任何 MAP-30 结论。

## 4. 与 V6 post-hoc 复算的关系

| 地图 | 本 pilot | V6 post-hoc | 读法 |
|---|---|---|---|
| MAP-08 | 两局成功 | 6/6 成功、`diagnosis_accuracy=1` | 方向一致；本 pilot 未增加天花板证据 |
| MAP-16 | L1 成功、L3 失败 | L1 成功、L2/L3 失败且 `makespan_gap=N/A` | 方向一致 |
| MAP-18 | 两局失败、低服务率 | 服务率 0–0.333、9 有效/1 censored | 方向一致；`alert_on` 未触发封锁 |
| MAP-22 | L3 graph memory 成功、`path_gap=3` | L3 `history5` 失败、graph memory 成功、`path_gap=3` | 方向一致，但缺同实例对照 |
| MAP-26 | free 成功；recovery 中断 | free 3/4 修复；recovery 0/9 | free 方向一致；recovery 无新证据 |
| MAP-30 | 无数据 | 完整调查 0/3；纯召回 casebook 1/1 | 未复现、未反驳 |

本 pilot 不覆盖 30 图，也不覆盖 24 张 design-only 地图；不能把上表的“方向一致”写成统计复现。

## 5. 边界与未完成

1. **不是 12/12 完成局**：只有 9 局完整结束；第 10 局为 `unknown_provider_spend`，后 2 局未启动。任何成功率、均值或排名都缺少完整样本。
2. **单 seed、单局/条件**：没有重复测量，不能做显著性、置信区间或跨模型比较。
3. **不是同实例配对**：MAP-08、MAP-16、MAP-18、MAP-22 的条件对使用不同实例或不同难度，不能把差异归因于条件本身。
4. **MAP-18 alert_on 未触发公开封锁**：改线指标为 `N/A`，不是 0。
5. **MAP-26 recovery 中断**：`repair_success=censored`，不纳入完整样本；provider 错误不是地图失败。
6. **24 图仍无运行时**：本 pilot 只使用 MAP-08/16/18/22/26/30 的 V6 runtime；没有为 MAP-01–07、09–15、17、19–21、23–25、27–29 生成运行时或真实结果。
7. **12 条 DCR 仍为 `proposed`**：本 pilot 没有修改 V4 规则，也没有把 DCR 标成已批准。
8. **Pilot 使用的 gate 与当前 gate 分离**：pilot 运行时 gate 绑定 `877dc01`（`5d97a589…`）；报告提交后已按当前 HEAD 重新冻结 gate，但新 gate 不回溯认证本次 pilot。后续任何新付费实验仍必须重新登记预算与停止规则，不能复用本账本续跑。

## 6. 证据与复算

| 证据 | 路径 / 值 |
|---|---|
| 预登记提交 | `877dc01` |
| 运行时 gate | `5d97a5898549a81f7a06e53ade18d86b3c564834f45bcab05fab8cb43d03deb3` |
| 运行时 commit | `877dc0145d87178c65aa3ce0596df10b7762ec47` |
| 运行目录 | `runs/v7/experiments/v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53` |
| 账本 | `runs/v7/ledgers/v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53.jsonl` |
| 运行 manifest | `run_manifest.json`，SHA-256 `60c76a6640aa4bec62a549499899cc39a76d49f6bbfd7db25ed33b2be9b66891` |
| V7 复算 JSON | `v7_metrics_all.json`，SHA-256 `b6b2574cc21c68765dcd92353abb4e6413181abb806ced73a92e938c64d8d754` |
| 账本 SHA-256 | `1fa7367bd14c8bb390b984af98a2d2e17c6b4cca101f4d0f2ce004ce33e899cb` |
| Trace 数 | 10（9 完整 + 1 中断） |

复算命令：

```powershell
.venv\Scripts\python.exe scripts\report_v7_metrics.py `
  runs\v7\experiments\v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53 `
  --json runs\v7\experiments\v7_pilot_001_20261017T043642Z_4d170907819b4b558be652765ac3ee53\v7_metrics_all.json
```

脚本处理 10 条 trace：10 `computed`、0 `design_only`、0 `invalid_trace`；其中第 10 局是中断局，相关指标按 `censored` 处理，不补 0。

## 7. 安全与泄漏

- 未在 `runs/v7/` 中发现 API 密钥、Bearer 授权头、密钥环境变量赋值或常见密钥前缀的文本（本地扫描 0 hits）。
- trace 未包含完整 prompt、隐藏真值或未来事件；V7 指标只读取公开 trace 与离线 judge 字段。
- 账本不含密钥；`pilot_stdout.log` 只含进度、费用和 episode 状态。
- 历史 V6 账本与 registry 未被打开、追加或改写；V2/V5 账本同样未触碰。

## 8. 结论

本 pilot 按预登记完成了**部分**六图真实 API 探针，而不是完整 12 局实验：9 局完整、1 局因 `unknown_spend` 安全停止、2 局未启动。它提供了 MAP-08/16/18/22/26 的 V7 指标真实轨迹读数，但没有提供 MAP-30 新数据，也不能据此完成六图能力结论。

正确处理是：保留该账本为已关闭的 pilot 证据，不续跑；先修复或确认 provider 连接稳定性，再以新的预登记、新的预算和新的冻结 gate 重新运行完整矩阵。24 图运行时、30 图正式矩阵和 12 条 DCR 的规则变更仍不在本报告完成范围内。
