# V7 Pilot-001 预登记：六图 12 局配对探针

> 状态：已预登记并已执行；首次执行结果见 [`pilot-001-report.md`](pilot-001-report.md)，同一矩阵在独立新账本上的 12/12 完整重跑见 [`pilot-001r-report.md`](pilot-001r-report.md)。本文件保留预登记原文，不回填结果。
> 登记日期：2026-10-17。
> 运行基底：V6 六图运行时的只读 V7 指标层；不修改 V4/V5/V6 规则、Action 契约、Trace 写出器或历史账本。
> 30 张 V7 设计卡已于 2026-10-17 由用户复核，记录为 `human_approved`；12 条 `V7-DCR` 仍为 `proposed`，本 pilot 不据此修改规则。

## 1. 目的

本 pilot 的目的不是给 30 图排名，也不是验证 24 张无运行时地图，而是：

1. 在**人工复核后的六张运行图**上，首次用新登记的 V7 指标读取真实 MiMo 轨迹；
2. 用 2 局/图的配对探针检查指标是否出现可解释的差异或缺失态；
3. 为后续正式 V7 矩阵提供停止规则、成本基线和字段稳定性证据。

因此本 pilot 的结论级别是 **E3-pilot**：只做描述性报告，不做显著性、跨模型或跨世界能力推断。

## 2. 预登记假设

| 编号 | 地图 | 条件对 | 方向性假设（不设显著性） |
|---|---|---|---|
| H1 | MAP-08 | `no_hypothesis_table` → `hypothesis_table` | 假设表应提高 `diagnosis_accuracy`，或减少无效探针；若两者相同，记录天花板。 |
| H2 | MAP-16 | `react` → `constraint_table` | 约束表应降低 `makespan_gap` 或减少 `node_capacity_conflicts`；L3 可能仍为 `N/A`。 |
| H3 | MAP-18 | `alert_off` → `alert_on` | 公开告警应提高 `service_rate`；若故障未触发，改线指标保持 `N/A`。 |
| H4 | MAP-22 | `history5` → `history5_graph_memory` | 图记忆应降低 `path_gap`，或提高返回目标点的成功率。 |
| H5 | MAP-26 | `free_diagnosis` | 自由诊断应至少产生一次有效修复；若 0 修复，记录为地板候选。 |
| H6 | MAP-30 | `history5_casebook` | casebook 应提高证据链覆盖率或降低重复调查；若 1/1，记录为天花板候选。 |

假设只用于解释方向，不用于筛选结果；所有 12 局都会报告，包括失败、截尾和缺失态。

## 3. 预登记矩阵（12 局）

| # | instance_id | condition_id | seed | 选入理由 |
|---|---|---|---|---|
| 1 | `map08_l1_two_candidate` | `no_hypothesis_table` | 0 | MAP-08 简单基线 |
| 2 | `map08_l3_original` | `hypothesis_table` | 0 | MAP-08 困难 + 完整假设表 |
| 3 | `map16_l1_single_train` | `react` | 0 | MAP-16 简单基线 |
| 4 | `map16_l3_original` | `constraint_table` | 0 | MAP-16 困难 + 约束表 |
| 5 | `map18_l2_alt_segment_r2b2` | `alert_off` | 0 | MAP-18 中等闭塞，无告警 |
| 6 | `map18_l3_original` | `alert_on` | 0 | MAP-18 困难 + 公开告警 |
| 7 | `map22_l1_short_return` | `history5` | 0 | MAP-22 简单基线 |
| 8 | `map22_l3_original` | `history5_graph_memory` | 0 | MAP-22 困难 + 图记忆 |
| 9 | `map26_l3_software_fault` | `free_diagnosis` | 0 | MAP-26 困难自由诊断 |
| 10 | `map26_recovery_power` | `recovery_full` | 0 | MAP-26 恢复条件 |
| 11 | `map30_l3_original` | `history5_casebook` | 0 | MAP-30 困难 + 纯召回 casebook |
| 12 | `map30_recall_original` | `history5_casebook` | 0 | MAP-30 纯召回对照 |

所有 episode 使用 `seed=0`，与 V6 注册矩阵一致；本 pilot 不新增 seed，不做重复测量。

## 4. 指标与读出

- 指标定义以 `src/agent_arena/v7/metrics/registry.py` 的 154 条 `MetricSpec` 为准；
- 六图 extractor 的 44 条 implemented 指标全部报告；
- 缺失值保持五态：`valid / not_applicable / censored / unavailable / invalid_trace`，不补 0；
- 每个 episode 的原始 `agent_trace.jsonl` 与 `judge_metrics.json` 保留在本地 `runs/v7/`，报告只引用路径与哈希；
- 报告不包含 API 密钥、完整 prompt 或私有真值。

## 5. 预算与停止规则

| 项目 | 预登记上限 |
|---|---|
| episode 数 | 12 |
| 每局决策上限 | 100 |
| 每局请求尝试上限 | 101（含 1 次重试） |
| 全局请求尝试硬上限 | 1,000（沿用 V6 账本硬上限） |
| 操作预算上限 | CNY 2.00（driver 在每局开始前检查已预留成本） |
| 账本硬上限 | CNY 11.00（`V6BudgetLedger` 内置，作为最后防线） |
| 单局墙钟 | 12 分钟 |
| 全局 provider 墙钟 | 180 分钟 |

停止条件：

1. 12 局全部完成 → 正常停止并写报告；
2. 任一局出现 `provider_error`、`provider_error_limit`、`unknown_provider_spend`、`input_context_limit`、`episode_timeout`、`global_provider_timeout`、`incomplete` 或 `invalid_action_schema_limit` → 立即停止，不再启动后续局；
3. 连续 3 次 provider 错误或账本判定未知花费 → 立即停止并关闭账本；
4. 已预留成本超过 CNY 1.80 或账本硬上限 → 立即停止；
5. 任何 API 密钥、provider 端点或冻结门禁校验失败 → 拒绝启动，不产生付费请求。

## 6. 预登记分析

- 主报告按地图分组，逐局列出 `status`、`decision_count`、V7 指标值/状态和失败分类；
- 配对条件只做方向性并列，不做显著性检验；
- 若某指标在 2 局中均为 `not_applicable` 或 `censored`，报告为“本 pilot 未提供证据”，不推断能力；
- 任何与 V6 post-hoc 复算不同的结果，必须同时报告，不覆盖旧报告；
- 本 pilot 不更新 30 卡的设计值，也不把 DCR 标成已批准。

## 7. 运行前检查

- [ ] 30 卡 `review_status = human_approved`；
- [ ] 冻结门禁通过，且 `runtime_commit` 与当前 HEAD 一致；
- [ ] 本地 provider 为 `openai`，模型为 `mimo-v2.6-flash`，端点为 `https://api.xiaomimimo.com/v1`；
- [ ] 新账本位于 `runs/v7/ledgers/`，不复用 V6 账本；
- [ ] 新的 V7 registry 位于 `runs/v7/pilot_registry.json`，与 V6 registry 隔离；
- [ ] 12 个 episode 均在 `registered_v6_matrix()` 中可解析；
- [ ] 本文件在付费请求前已提交。

## 8. 与历史资产的关系

- 不重开 V2/V5/V6 账本；
- 不修改 V6 的 29 个实例、V6 pilot registry 或原始 trace；
- 不复用 V6 的“47 局”结果充当本 pilot 数据；
- 本 pilot 是 V7 的新预登记实验，但不是 30 图正式矩阵，也不是 24 图运行时验证。
