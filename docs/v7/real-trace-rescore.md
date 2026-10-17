# V7 六图真实 MiMo trace 的二次复算

- 日期：2026-10-17
- 数据源：`runs/v6/experiments/pilot_20261016T043238Z_6971b08563ca491593af6ba13c04cf8b`
- 原始实验 ID：`729f50b7-2d0a-4023-9687-c175a75d45c2`
- 模型：`mimo-v2.6-flash`
- 原始运行设置：`temperature=0`、reasoning 关闭、`json_object`、每局最多 100 决策
- 原始规模：47/47 局完成，17/47 成功，492 次请求，报告费用 CNY ¥0.29230284，provider 墙钟 2169.045 秒
- 本次复算：47 条 trace，47 条 `computed`，0 条 `design_only`，0 条 `invalid_trace`
- 本次新增付费调用：**0 次**
- 本次新增账本：**0 个**
- 本次写入 `runs/` 或 `results/`：**0 个**

## 1. 证据等级与边界

这是对已有 V6 真实 MiMo trace 的**确定性二次分析**，不是新的 V7 主实验。按提纲的证据分级，原始 trace 属于 E3，本报告的 V7 数值是 **E3-post-hoc**：

- 真实 API trace 已存在，V7 extractor 只读复算；
- V6 条件不是 V7 预注册条件；
- 每个条件只有 1 局，不能做显著性、排名或跨模型推断；
- 30 张 V7 卡已由用户于 2026-10-17 复核并记录为 `human_approved`；但这不把本报告变成新的预注册 API 实验；
- 因此本报告不能替代“V7 真实 API 主实验”，也不能宣称 24 张设计图已有运行时。

本次没有重新调用 MiMo。原因是：V7 协议要求真实实验在卡片冻结后单独登记预算、样本与停止规则；直接用现有 trace 复算既不增加费用，也不会把未预注册的新运行伪装成主实验。

## 2. 复算方法

```powershell
.venv\Scripts\python.exe scripts\report_v7_metrics.py `
  "runs/v6/experiments/pilot_20261016T043238Z_6971b08563ca491593af6ba13c04cf8b" `
  --json <temporary-json>
```

`report_v7_metrics.py` 只读取 `agent_trace.jsonl` 和可选的 `judge_metrics.json`，不启动环境、不调用 provider、不写账本。47 条 trace 全部解析成功；没有用 0 填补任何缺失态。

## 3. 六图汇总

| 图 | 原始成功 | 关键主指标（有效局/状态） | 观察 |
|---|---:|---|---|
| MAP-08 | 6/6 | `candidate_reduction` 均值 0.611（0.500–0.667）；`diagnosis_accuracy` 全为 1.0 | 天花板；有/无假设表没有差异；`peak_core_water` 4–6，`wrong_repair` 全 0 |
| MAP-16 | 2/6 | `legal_reservation_rate` 0.667–1.0；`makespan_gap` 仅 2 局有效且均为 0，4 局 N/A | L1 两条件均成功；L2/L3 均有 `node_capacity_conflicts=1`；失败局的 makespan 记 N/A，不记 0 |
| MAP-18 | 0/10 | `service_rate` 0–0.333（9 有效，1 censored）；`delay_person_ticks` 9 局为 0，1 局 censored | 完整地板；`first_reroute_delay` / `recovery_delay` 10 局全 N/A；`collision_violations` 4/10 非零，`station_capacity_violations` 5/10 非零 |
| MAP-22 | 5/6 | `return_success` 均值 0.833；`path_gap` 0–3（5 有效，1 N/A） | L3 `history5` 失败、`path_gap=N/A`；L3 `graph_memory` 成功、`path_gap=3`；L1 出现反向差异（见 §4） |
| MAP-26 | 3/13 | `diagnosis_accuracy` 均值 0.692；`repair_success` 均值 0.231；`recovery_latency` 3–4（10 有效） | `free_diagnosis` 3/4 修复成功；`recovery_*` 0/9 修复成功；恢复延迟可测但未转化为修复 |
| MAP-30 | 1/6 | `evidence_chain_coverage` 4 有效（3 个 0、1 个 1）；2 局 unavailable | 完整调查 0/3 覆盖率为 0；纯召回 `history5_casebook` 1/1 完整；`history5` / `history_full` 的 casebook 不可见，记 unavailable |

原始成功的计数来自 V6 pilot 报告；本表的主指标来自 V7 extractor。两者不能互相替代：成功是结果，指标是能力/约束/过程量。

## 4. 逐图读法

### MAP-08：诊断天花板，条件无差异

6 局全部成功，`diagnosis_accuracy` 全为 1.0，`wrong_repair` 全为 0。`candidate_reduction` 没有被假设表条件拉开：`l1` 两条件都是 0.5，`l2` / `l3` 两条件都是 0.666667。这说明当前样本下 MAP-08 更像“接口熟悉度 + 基础诊断”的天花板，而不是能区分假设表机制的地图。`peak_core_water` 最大为 6，仍需结合合法范围判断是否接近安全边界。

### MAP-16：L1 成功，L2/L3 失败，N/A 不是 0

`map16_l1_single_train` 的 ReAct 与约束表两条件都成功，`makespan_gap=0`，`legal_reservation_rate=1.0`。`l2` / `l3` 四局全部失败，`node_capacity_conflicts=1`，`makespan_gap` 记为 N/A，而不是 0。这个区分很重要：失败局没有可比较的完成时间，不能把“没到达终局”误算成“最优完成”。

`legal_reservation_rate` 在 L2/L3 为 0.667–1.0，说明失败并非全部来自非法预留；节点容量冲突和任务未完成是更直接的归因。

### MAP-18：服务率地板，恢复指标没有触发

10 局全部失败，`service_rate` 只有 9 局可计算，均值 0.037，最高 0.333；1 局因预算截尾记 censored。`delay_person_ticks` 在 9 局为 0，但这不是“没有延误”的能力证据，而是没有完成足够的乘客运输来产生可计延误。`first_reroute_delay` 和 `recovery_delay` 全为 N/A：当前 trace 中没有“已提交但未成功改线”的时刻表，不能把它们补成 0。

安全侧更敏感：`collision_violations` 有 4/10 非零，`station_capacity_violations` 有 5/10 非零。MAP-18 目前是完整地板，预警条件也没有把服务率拉起来。

### MAP-22：L3 出现条件差异，但单局不能当因果结论

`map22_l3_original` 是唯一出现清晰方向差异的实例：

| 条件 | `return_success` | `path_gap` | `repeated_public_edge_rate` | `memory_facts_written` |
|---|---:|---:|---:|---:|
| `history5` | 0 | N/A | 0.333333 | 0 |
| `history5_graph_memory` | 1 | 3 | 0.0 | 9 |

这说明在该局中，图记忆条件至少让 Agent 完成了返程，并把重复公开边率从 0.333333 降到 0.0；但只有 1 局，不能把它写成“图记忆提升返程能力”的因果结论。反向例子也存在：`map22_l1_short_return` 的 `history5` 为 `path_gap=0`、重复率 0.0，`history5_graph_memory` 为 `path_gap=2`、重复率 0.166667，单局下图记忆反而多走了 2 步并多重复了一条边。L2 两条件都是 `path_gap=2`、重复率 0.166667。这三组应作为后续多实例配对实验的靶子，而不是当前排名。

所有 6 局的 `illegal_bearing_actions=0`、`memory_grounding_violations=0`，说明这次 MiMo 运行没有出现非法方位或凭空写记忆的安全违例；但这只是本次 trace 的事实。

### MAP-26：自由诊断近天花板，恢复条件仍是地板

`free_diagnosis` 4 局中 3 局修复成功；唯一失败的是 `map26_l3_software_fault`，`diagnosis_accuracy=0`、`repair_success=0`、`recovery_latency=4`。`recovery_*` 9 局全部修复失败，`spares_remaining=0`，`recovery_latency` 为 3–4。也就是说，恢复流程并非完全“没开始”：延迟可以计算，但最终没有修复成功。`repeat_error_rate` 在恢复局为 0–0.667，说明重复错误存在，但不是唯一失败原因。

这支持 V6 报告中的判断：自由诊断接近天花板，恢复是地板；不能通过增加备件把恢复失败“修好”。

### MAP-30：完整调查是流程地板，纯召回是另一条路径

3 个完整调查实例（`history5_casebook`）全部 `evidence_chain_coverage=0`，没有形成可复算的证据链；`accusation_claim_precision` 和 `q4_recall_accuracy` 因没有 `formal_accuse` 记 N/A，而不是 0。纯召回实例 `map30_recall_original` 中：

- `history5_casebook` 成功完成，`evidence_chain_coverage=1.0`、`q4_recall_accuracy=1`、`accusation_claim_precision=1`；
- `history5` 和 `history_full` 的 `evidence_chain_coverage` 为 unavailable，因为该条件没有公开 casebook，不能把空 casebook 当成“记录为零”。

这正好把“完整调查流程”和“已解锁身份的纯召回”分开：前者还没有形成证据链，后者在 casebook 可见时可以完成。

## 5. 对 V7 指标的含义

这次复算验证了六图 extractor 在真实 MiMo trace 上可以工作，并且保留了五态缺失：

- 失败局的 `makespan_gap` 是 N/A，不是 0；
- 没有改线事件的 MAP-18 是 N/A，不是 0 tick；
- 预算截尾的 MAP-18 是 censored；
- 没有公开 casebook 的 MAP-30 是 unavailable，不是空列表 0；
- 24 张 design-only 图没有出现在本次复算中，也不会被伪造分数。

同时，这次结果也暴露了下一轮实验该看什么：MAP-08 已经天花板，MAP-16 的 L2/L3 失败集中在节点容量，MAP-18 需要先解决服务率地板，MAP-22 需要多实例配对，MAP-26 需要把“有延迟但修复失败”拆开，MAP-30 需要把调查流程和召回分开。

## 6. 不能下的结论

- 不能把 17/47 当作 V7 总分；不同地图的原始成功率和成本不能直接相加。
- 不能把单局条件差异写成显著性、模型排名或跨模型结论。
- 不能把本报告称为“新的 V7 API 主实验”；它是已有 V6 trace 的 post-hoc 复算。
- 不能把 24 张设计图说成已有运行时；它们仍只有设计卡和 `pending-runtime/MAP-XX.md`。
- 不能把 30 卡的人工复核记录等同于新的 V7 API 主实验；`review_status` 已是 `human_approved`，但本报告仍是 V6 trace 的 post-hoc 复算。

## 7. 如果要跑新的 V7 API 实验

按 `experiment-protocol.md`，新运行至少需要：

1. 人工冻结 30 张卡的主指标、对照、预算与停止规则；
2. 重新冻结运行时门禁，确认 V6/V4 文件和 prompt 哈希未变；
3. 登记新的预算、样本量、seed 策略和费用上限；
4. 选择六图中的切片或多实例配对矩阵；
5. 运行前确认不重开已关闭账本，不创建 `BUDGET-04`；
6. 运行后先用 `report_v7_metrics.py` 复算，再写结果报告。

在上述条件满足前，本报告的定位是“已有真实 trace 的 V7 二次分析”，不是新的付费实验。
