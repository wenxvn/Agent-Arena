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
