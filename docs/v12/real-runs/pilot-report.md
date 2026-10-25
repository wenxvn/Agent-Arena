# 实验报告：v12-pilot-001

- `experiment_id`：`lab-20261025T120139Z-f9b93d5a`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-22, MAP-26
- 环境 seed：[0]
- 实验臂：basic.v1, memory.v1, planning.v1
- 子局：6 / 6（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 2 图 × 1 seed × 3 实验臂 = 6 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

## 2. 不可比声明与数据口径

- 配对比较判定：`COMPARABLE`
  - 说明：配对样本为 3（每个配对键一局）；这是描述性对照，不构成显著性结论。
- 有效分母只含：完成且成功、机制失败、预算截尾；Provider 错误、取消、中断、策略异常**不计入**能力分母。
- 指标五态（VALID/CENSORED/NOT_APPLICABLE/INVALID_TRACE/UNAVAILABLE）原样保留，缺失不补 0、不跨版本求均值。
- 每对实验臂的配对键是 `(map_id, environment_seed)`；seed 不同不构成配对。

## 3. 单局类别分布

| 类别 | 局数 |
|---|---:|
| 预算截尾（`budget_censored`） | 3 |
| 完成且成功（`completed_success`） | 3 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 21.5 | 21.5 | 0.0116 | 2 | 0 | 0 |
| memory.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 21.5 | 21.5 | 0.0189 | 2 | 0 | 0 |
| planning.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 21 | 22.5 | 0.0193 | 2 | 0 | 0 |

## 5. 逐图指标（五态）

### MAP-22

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 1 | — |
| basic.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 0 | — |
| basic.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| basic.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1 | — | — |
| basic.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 25 | — |
| memory.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 0 | — |
| memory.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 2 | — |
| memory.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| memory.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1 | — | — |
| memory.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 24 | — |
| planning.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 1 | — |
| planning.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 3 | — |
| planning.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| planning.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1 | — | — |
| planning.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 19 | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 1 | — |
| basic.v1 | `map26.v10.mission_success` | primary | VALID×1 | 1 | — |
| basic.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 0 | — |
| basic.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 1 | — |
| basic.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 0 | — |
| memory.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 1 | — |
| memory.v1 | `map26.v10.mission_success` | primary | VALID×1 | 1 | — |
| memory.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 0 | — |
| memory.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 1 | — |
| memory.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 0 | — |
| planning.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.mission_success` | primary | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 0 | — |
| planning.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 0 | — |

## 6. 代表性轨迹与证据

- 共 22 条诊断（critical 0 / warning 16）。
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `repeated_action_loop`：连续 17 步重复同一动作，期间没有新的动作选择：move。（证据：step-1, step-2, step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11, step-12, step-13, step-14, step-15, step-16, step-17；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `repeated_action_loop`：连续 6 步重复同一动作，期间没有新的动作选择：move。（证据：step-19, step-20, step-21, step-22, step-23, step-24；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-28, step-29, step-30；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `repeated_action_loop`：连续 8 步重复同一动作，期间没有新的动作选择：move。（证据：step-33, step-34, step-35, step-36, step-37, step-38, step-39, step-40；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `key_action_attempted_rejected`：机制动作被尝试过，但全部被环境拒绝（前置条件未满足）。（证据：step-31, step-32；建议核查：对照公开前置条件，检查是否缺少必要的准备动作。）
- `MAP-22` / `web-20261025T120139Z-23d0a60e` · `memory_not_used`：整局没有写入任何公开记忆；返程只能依赖 5 步历史窗口。（证据：无单步证据；建议核查：对照启用记忆的臂，看 wasted_moves 与返程成功率。）
- `MAP-22` / `web-20261025T120321Z-aa66cdf9` · `repeated_action_loop`：连续 6 步重复同一动作，期间没有新的动作选择：move。（证据：step-3, step-4, step-5, step-6, step-7, step-8；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T120321Z-aa66cdf9` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-10, step-11, step-12；建议核查：对照启用记忆/反思臂后重复是否减少。）

## 7. 六图可视化可用性

| 地图 | 专属视图 |
|---|---|
| MAP-08 | 本次未纳入 |
| MAP-16 | 本次未纳入 |
| MAP-18 | 本次未纳入 |
| MAP-22 | 可用（exploration_graph） |
| MAP-26 | 可用（maintenance_chain） |
| MAP-30 | 本次未纳入 |

## 8. 局限

- 每个配对键通常只有 1 局；这是描述性对照，**不作显著性断言**。
- 架构新增的记忆/计划/反思上下文是唯一被操纵的变量；提示词基线与动作契约保持不变。
- Planner/Reflection 的额外请求已计入请求数、token 与费用；费用未知的局不参与成本对比。
- 真实模型输出不可完全复现；只保证环境 seed 配对。

## 9. 复现方式

```bash
# 零 API：跑同一矩阵的离线模拟
uv run python scripts/demo_v12.py
# 一键验收（含 Lab 契约、预算、父子状态、导出复算）
uv run python scripts/verify_v12.py
```

实验目录：`runs/lab/lab-20261025T120139Z-f9b93d5a/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
