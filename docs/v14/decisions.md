# V14 决策记录

记录 V14 实施过程中对协议、口径、版本的**实质**决定。每条包含：背景、决定、影响、可回滚性。

## D-V14-001 · 只修口径，不改冻结资产

- 背景：V13 交付了 `docs/v13/` 与 V8/V9/V10 冻结账本、trace。
- 决定：V14 的所有修正只落在**分析层与报告层**（`lab/v13/*` 的纯展示函数、新增 `lab/v14/*`、
  `docs/v14/*`），不修改 `worlds/scenario_v8`、`v10/runtime`、历史 trace、历史账本。
- 影响：`docs/v13/map-validity.md` 会被修正并加注"由 V14 修正"，因为它是由代码生成的
  **展示产物**而不是源数据；源数据（`docs/v12/real-runs/*.csv`）只读。
- 可回滚：是（纯文档/展示层）。

## D-V14-002 · `UNKNOWN` 与 `0` 必须在数据模型里分开

- 背景：历史 CSV 没有 `mechanism_triggered` 列，V13 的 markdown 直接打印 `0/N`。
- 决定：`map_validity()` 输出三个互斥计数 `observed_true / observed_false / unknown` 与
  `mechanism_triggered_observed` 分母；只有 `observed_*` 才可写 `x/n_observed`，
  全未知写 `UNKNOWN (0 observed)`。保留旧字段 `mechanism_triggered_runs` 以兼容 V13 调用方，
  但新增 `mechanism_triggered_status` 枚举（`OBSERVED_TRUE` / `OBSERVED_FALSE` / `UNKNOWN` / `MIXED`）。
- 影响：UI/CSV/JSON/Markdown 共用同一语义。
- 可回滚：是（新增字段，不改旧字段类型）。

## D-V14-003 · 观测条件身份与 `condition_key` 并存

- 背景：V12 的 `condition_key = map|seed|agent` 不含 config hash；V13 的
  `comparable_group_id` 含预算但不含采样画像。
- 决定：V14 新增 `observation_condition_id`（8 元组：
  map / environment_seed / agent_id / config_hash / contract_version /
  effective_prompt_version / budget_profile / sampling_profile），
  **不改** 冻结的 `condition_key` 字段，只在分析层用它做分组与拒绝判定。
- 影响：旧 trace 仍可读；新分析可以拒绝跨预算/跨采样配对。
- 可回滚：是。

## D-V14-004 · `SUPPORTED` 只描述证据形式

- 背景：V13 四级结论 `SUPPORTED / TENTATIVE / INSUFFICIENT / NOT_TESTED` 容易被读成"策略有效"。
- 决定：V14 在报告与 UI 上把结论拆成三个独立字段：
  `evidence_level`（证据形式）、`mechanism_exposure`（干预是否真的发生）、
  `effect_direction`（描述性方向）。`SUPPORTED` 永不等价于"显著改善"或"因果证实"。
- 可回滚：是（新增字段，旧 `level` 保留）。

## D-V14-005 · 未获批不产生任何付费请求

- 决定：V14 全部 LIVE 相关代码路径默认 `PLANNED_ONLY`，`--submit` 需要显式 `LiveApproval`；
  文档中所有真实模型效果一律写 `LIVE_PENDING`。本轮新增外部付费请求 **0**。

## DCR-V14-01 · 历史 CSV 无法在数据层区分契约版本

- **发现**：`docs/v12/real-runs/*.csv` 的列里没有 `prompt_hash`、`contract_version`、
  `agent_config`。MAP-22 的 contract-1 与 contract-2（DCR-V12-01/02 的修复前后）
  在 `rule_hash` / `metric_hash` / `agent_version` 上**完全相同**，只有来源文件不同。
- **影响**：任何“跨契约版本合并”或“按契约版本排除”的分析，都无法仅凭 CSV 证明；
  V13 的 21 局 MAP-22 分母里混了 contract-1、contract-2 与 route_log 消融三类。
- **处理**：V14 的 `protocol_group()` 用 `(experiment_kind, source_file, 指纹)` 分组，
  多组并存时标 `POOLED_ACROSS_PROTOCOLS` 并禁止合并求均值；不删数据、不改历史。
- **后续要求**：V14 之后的新 trace 必须落 `prompt_hash` 与 `contract_version`，
  否则同类问题会重现。
- **可回滚**：不适用（只读分析层）。

## DCR-V14-02 · 预算申请文档的算术错误

- **发现**：`docs/v13/live-budget-proposal.md`（2026-10-26）逐行子局合计 221，正文写 229；
  方案 B 写“150 局 / ¥4.19”（实为 186 局）；方案 A 写“¥1.68”（实为 ¥2.11）；
  E2-d/E4/E5 的“预估”未统一使用文档自己声明的 1.5 倍余量公式。
- **处理**：`lab/v14/data_audit.budget_proposal_check()` 从 Markdown 解析逐行数字并用
  真实 V12 单价重算；修正后的文档与 `docs/v14/budget-audit.md` 一致。
- **影响**：修正后逐行预估 ¥10.97（原 ¥9.08），方案 B ¥5.60（原 ¥4.19）；
  建议批准上限不变（A ¥5.00 / B ¥8.00 / C ¥15.00）。
- **后续要求**：任何 LIVE 申请前必须先跑 `scripts/audit_v14_data.py` 并确认
  `declared_total_matches = true`。

## DCR-V14-03 · `memory.v2.bottleneck()` 在 `env_write` 下用错分母

- **发现**：`memory.v2.bottleneck()` 在 `env_write` 模式把 `write_accepted`（写入**次数**）
  与 `route_length`（方位**个数**）比较。一次写入可以包含整段路线，于是"每次写入都完整"
  的臂会被判成 `RECORDED_TOO_SHORT`（离线 probe 实测：`write_accepted=2`、路线 4 步）。
- **影响**：V13 的 `memory-study.md` 里"记录过短"这一诊断标签在 `env_write` 臂上可能误报，
  会让人误以为策略记录不足，实际是分母口径错误。
- **处理**：V14 在分析层新增 `memory_bottleneck_v14()`，`env_write` 按"已写入方位数"
  判定；`memory.v2` 源码**未修改**（改它会牵动 `agent_config_hash` 之外的诊断输出与
  V13 报告，风险大于收益）。报告同时给出 `bottleneck_v13` 与投影值。
- **可回滚**：是（纯分析层）。
