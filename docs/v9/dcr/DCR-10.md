# DCR-10：MAP-06 使用已注册的 10-seed cohort，而不是单一 seed=0

- 状态：`requires_user_decision`（评测协议变更；不改规则）
- 地图：MAP-06
- 关联审计：`docs/v9/maps/MAP-06-audit.md`
- 影响面：instance seed 选择与聚合口径；不改变 `rule_hash`/`scenario_hash`
- 证据：V8 三局全部 `seed=0`；`WEATHER[0]="short"`，长风暴 tick 0/0/0、风险 0/0/0、加固 0/0/0、预报读取 0/0/0。消融 `shortcut`（只走 `Q_P` + 修复）在 seed 0 成功，在 seed 5–9 全部 `RESOURCE_EXHAUSTED`。

## 1. 问题

MAP-06 的机制是“80% 条件预报 + 风险预算”，但注册实例 seed=0 恰好落在无风暴分支；三局 2–3 决策直达成功，核心机制一次未触发。这不是规则 bug，而是**采样设计**使构念未被测量。

## 2. 候选

| 方案 | 改动 | 收益 | 风险 |
|---|---|---|---|
| A（推荐） | 评测按 `WEATHER`/`FORECAST` 的 10 个 seed 等权 cohort 报告，不把 seed 0 当唯一实例 | 机制进入测量；可直接复用已注册的 10-seed 表 | 需要重跑或至少重算 10 个实例；V8 90 局不可比 |
| B | 把正式实例改为 seed=5（长风暴） | 成本最低 | 只换一个单点，仍无法覆盖 80% 预报的概率结构 |
| C | 改规则让 seed 0 也有风暴 | 修改已冻结规则 | 禁止；会破坏 V8 与 Oracle |

## 3. 指标

`map06.value_of_information` 在代码里硬编码 `None`；设计稿注册的 cohort 效用也未实现。若采用 A，必须同时实现配对 VOI，否则 cohort 仍无主指标。

## 4. 结论

V9 只做**离线 cohort 诊断**（10 seed × 公开启发式 / shortcut / forecast_trusting），不修改正式实例，也不把结果并入 V8 成功率。是否把 MAP-06 正式评测改为 cohort，交给用户裁定。
