# 实验报告：v12-map22-route-hint

- `experiment_id`：`lab-20261025T153447Z-f5830789`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30
- 环境 seed：[0, 1, 2]
- 实验臂：basic.v1, memory.v1, planning.v1
- 运行时版本：`v12-lab-1+agent_policy_v1+v12-contract-2`
- 子局：9 / 9（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 6 图 × 3 seed × 3 实验臂 = 9 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

> **补充实验**：来源 `lab-20261025T120807Z-3aaedd0f`；只重跑 9 个需要补充的条件。
> 原因：DCR-V12-02 口径对齐：v12-contract-2 公开 bearing/path_state 建议 + V12 研究投影 route_recall。与 v1/v2 均不配对。
> 原始实验的记录与账本未被修改；补跑产生新的 run_id，不覆盖历史。

## 2. 不可比声明与数据口径

- 配对比较判定：`COMPARABLE`
  - 说明：配对样本为 9（每个配对键一局）；这是描述性对照，不构成显著性结论。
- 有效分母只含：完成且成功、机制失败、预算截尾；Provider 错误、取消、中断、策略异常**不计入**能力分母。
- 指标五态（VALID/CENSORED/NOT_APPLICABLE/INVALID_TRACE/UNAVAILABLE）原样保留，缺失不补 0、不跨版本求均值。
- 每对实验臂的配对键是 `(map_id, environment_seed)`；seed 不同不构成配对。

## 3. 单局类别分布

| 类别 | 局数 |
|---|---:|
| 机制失败（`mechanism_failure`） | 9 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 53.6667 | 53.6667 | 0.0175 | 3 | 0 | 0 |
| memory.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 50.6667 | 50.6667 | 0.027 | 3 | 0 | 1 |
| planning.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 59 | 60 | 0.0351 | 3 | 0 | 0 |

## 5. 逐图指标（五态）

### MAP-08

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-16

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-18

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-22

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 0.3333 | — |
| basic.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0 | — |
| basic.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×2, VALID×1 | 0.0227 | 0.0227 |
| basic.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 32.6667 | — |
| memory.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0.3333 | — |
| memory.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 0.6667 | — |
| memory.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0 | — |
| memory.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1, VALID×2 | 0.0114 | 0.0114 |
| memory.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 32.6667 | — |
| planning.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0.6667 | — |
| planning.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 0.6667 | — |
| planning.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0 | — |
| planning.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1, VALID×2 | 0.0341 | 0.0341 |
| planning.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 32.6667 | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-30

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### V12 研究投影（不覆盖 V10 指标）

| 地图 | 指标 | 五态分布 | 有效均值 | 合并比值 | 口径版本 |
|---|---|---|---|---|---|
| MAP-22 | `v12.projection.route_recall` | NOT_APPLICABLE×4, VALID×5 | 0.0217 | 0.0218 | v12-projection-1 |

> 这些是 V12 为弥补公开信息缺口而新增的**研究投影**（键名宽容），
> 用于回答「记忆是否被用于返程」；它们不参与任何 V10 指标均值，也不写入 V10 账本。


### 指标命名空间

- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。
- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、
  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。

## 6. 代表性轨迹与证据

- 共 49 条诊断（critical 0 / warning 49）。
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `repeated_action_loop`：连续 11 步重复同一动作，期间没有新的动作选择：move。（证据：step-1, step-2, step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `repeated_action_loop`：连续 10 步重复同一动作，期间没有新的动作选择：move。（证据：step-14, step-15, step-16, step-17, step-18, step-19, step-20, step-21, step-22, step-23；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `repeated_action_loop`：连续 6 步重复同一动作，期间没有新的动作选择：move。（证据：step-25, step-26, step-27, step-28, step-29, step-30；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-36, step-37, step-38；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `key_action_attempted_rejected`：机制动作被尝试过，但全部被环境拒绝（前置条件未满足）。（证据：step-13, step-24, step-32, step-35, step-41, step-56, step-58；建议核查：对照公开前置条件，检查是否缺少必要的准备动作。）
- `MAP-22` / `web-20261025T153457Z-7b0f4175` · `memory_not_used`：整局没有写入任何公开记忆；返程只能依赖 5 步历史窗口。（证据：无单步证据；建议核查：对照启用记忆的臂，看 wasted_moves 与返程成功率。）
- `MAP-22` / `web-20261025T153631Z-794503d6` · `repeated_action_loop`：连续 27 步重复同一动作，期间没有新的动作选择：move。（证据：step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11, step-12, step-13, step-14, step-15, step-16, step-17, step-18, step-19, step-20, step-21, step-22, step-23, step-24, step-25, step-26, step-27, step-28, step-29；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T153631Z-794503d6` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-31, step-32, step-33；建议核查：对照启用记忆/反思臂后重复是否减少。）

## 7. 六图可视化可用性

| 地图 | 专属视图 |
|---|---|
| MAP-08 | 可用（diagnosis_funnel） |
| MAP-16 | 可用（occupancy_timeline） |
| MAP-18 | 可用（recovery_gantt） |
| MAP-22 | 可用（exploration_graph） |
| MAP-26 | 可用（maintenance_chain） |
| MAP-30 | 可用（evidence_chain） |

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

实验目录：`runs/lab/lab-20261025T153447Z-f5830789/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
