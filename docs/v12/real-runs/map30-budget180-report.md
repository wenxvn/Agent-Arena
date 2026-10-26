# 实验报告：v12-map30-budget-180

- `experiment_id`：`lab-20261025T155152Z-93b31b11`
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
> 原因：预算扩展：MAP-30 九局单局请求上限 90 → 180（原 8/9 局截尾，属未测完）。
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
| 预算截尾（`budget_censored`） | 5 |
| 机制失败（`mechanism_failure`） | 4 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 112.3333 | 112.3333 | 0.1022 | 3 | 7 | 0 |
| memory.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 89 | 89 | 0.1179 | 3 | 8 | 0 |
| planning.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 109.3333 | 110.3333 | 0.1463 | 3 | 1 | 0 |

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
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| — | 该图没有可聚合指标 | — | — | — | — |

### MAP-30

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×1, NOT_APPLICABLE×2 | — | — |
| basic.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0.6667 | — |
| basic.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.9167 | 0.9167 |
| basic.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| basic.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0.6667 | — |
| basic.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 3.3333 | — |
| memory.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×1, NOT_APPLICABLE×2 | — | — |
| memory.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0.6667 | — |
| memory.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.8333 | 0.8333 |
| memory.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| memory.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0.6667 | — |
| memory.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 4 | — |
| planning.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×3 | — | — |
| planning.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0.3333 | — |
| planning.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.8333 | 0.8333 |
| planning.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| planning.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 2 | — |


### 指标命名空间

- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。
- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、
  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。

## 6. 代表性轨迹与证据

- 共 43 条诊断（critical 4 / warning 34）。
- `MAP-30` / `web-20261025T155152Z-7c8494ed` · `unsupported_accusation`：指控被拒：证据链不完整或引用了未记录的条目。（证据：step-81；建议核查：先补齐四个条目与交叉索引，再在法庭节点提交。）
- `MAP-30` / `web-20261025T155434Z-e29c01e5` · `unsupported_accusation`：指控被拒：证据链不完整或引用了未记录的条目。（证据：step-102；建议核查：先补齐四个条目与交叉索引，再在法庭节点提交。）
- `MAP-30` / `web-20261025T162006Z-162e26a2` · `unsupported_accusation`：指控被拒：证据链不完整或引用了未记录的条目。（证据：step-109；建议核查：先补齐四个条目与交叉索引，再在法庭节点提交。）
- `MAP-30` / `web-20261025T162508Z-6f12e2fb` · `unsupported_accusation`：指控被拒：证据链不完整或引用了未记录的条目。（证据：step-52；建议核查：先补齐四个条目与交叉索引，再在法庭节点提交。）
- `MAP-30` / `web-20261025T155152Z-7c8494ed` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-5, step-6, step-7；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-30` / `web-20261025T155152Z-7c8494ed` · `repeated_action_loop`：连续 4 步重复同一动作，期间没有新的动作选择：move。（证据：step-24, step-25, step-26, step-27；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-30` / `web-20261025T155152Z-7c8494ed` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-31, step-32, step-33；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-30` / `web-20261025T155152Z-7c8494ed` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：move。（证据：step-42, step-43, step-44；建议核查：对照启用记忆/反思臂后重复是否减少。）

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

实验目录：`runs/lab/lab-20261025T155152Z-93b31b11/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
