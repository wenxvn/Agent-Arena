# 实验报告：v12-map22-contract-fixed

- `experiment_id`：`lab-20261025T134724Z-fa696780`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30
- 环境 seed：[0, 1, 2]
- 实验臂：basic.v1, memory.v1, planning.v1
- 子局：9 / 9（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 6 图 × 3 seed × 3 实验臂 = 9 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

> **补充实验**：来源 `lab-20261025T120807Z-3aaedd0f`；只重跑 9 个需要补充的条件。
> 原因：DCR-V12-01 接口修复后重跑 MAP-22 九局：facts 契约补丁 v12-contract-1。与主矩阵 v1 prompt 跨版本不配对。
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
| 完成且成功（`completed_success`） | 4 |
| 机制失败（`mechanism_failure`） | 5 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 3 | 3 | 1 | 0.3333 | 57.3333 | 57.3333 | 0.0223 | 3 | 0 | 0 |
| memory.v1 | 1.0.0 | 3 | 3 | 1 | 0.3333 | 45.6667 | 45.6667 | 0.026 | 3 | 0 | 2 |
| planning.v1 | 1.0.0 | 3 | 3 | 2 | 0.6667 | 37.3333 | 38.3333 | 0.0237 | 3 | 0 | 0 |

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
| basic.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 2.6667 | — |
| basic.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0.3333 | — |
| basic.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| basic.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 30.6667 | — |
| memory.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0.3333 | — |
| memory.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 1 | — |
| memory.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0.3333 | — |
| memory.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| memory.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 29.3333 | — |
| planning.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 1.3333 | — |
| planning.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0.6667 | — |
| planning.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| planning.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 21.3333 | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-30

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

## 6. 代表性轨迹与证据

- 共 51 条诊断（critical 0 / warning 51）。
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 5 步重复同一动作，期间没有新的动作选择：move。（证据：step-3, step-4, step-5, step-6, step-7；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-15, step-16, step-17；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 6 步重复同一动作，期间没有新的动作选择：move。（证据：step-21, step-22, step-23, step-24, step-25, step-26；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-28, step-29, step-30；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-34, step-35, step-36；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 5 步重复同一动作，期间没有新的动作选择：move。（证据：step-40, step-41, step-42, step-43, step-44；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 4 步重复同一动作，期间没有新的动作选择：move。（证据：step-48, step-49, step-50, step-51；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-22` / `web-20261025T134724Z-b0f051ac` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-56, step-57, step-58；建议核查：对照启用记忆/反思臂后重复是否减少。）

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

实验目录：`runs/lab/lab-20261025T134724Z-fa696780/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
