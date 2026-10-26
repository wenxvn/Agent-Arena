# 实验报告：v12-ablation-reflection-on

- `experiment_id`：`lab-20261026T040533Z-447523e3`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-16
- 环境 seed：[0, 1]
- 实验臂：reflection.v1
- 运行时版本：`v12-lab-1+agent_policy_v1+v12-contract-2`
- 子局：2 / 2（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 1 图 × 2 seed × 1 实验臂 = 2 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

## 2. 不可比声明与数据口径

- 配对比较判定：`INCOMPARABLE`
  - 不可比原因：少于两个实验臂，无法做架构对照
- 有效分母只含：完成且成功、机制失败、预算截尾；Provider 错误、取消、中断、策略异常**不计入**能力分母。
- 指标五态（VALID/CENSORED/NOT_APPLICABLE/INVALID_TRACE/UNAVAILABLE）原样保留，缺失不补 0、不跨版本求均值。
- 每对实验臂的配对键是 `(map_id, environment_seed)`；seed 不同不构成配对。

## 3. 单局类别分布

| 类别 | 局数 |
|---|---:|
| 完成且成功（`completed_success`） | 1 |
| 机制失败（`mechanism_failure`） | 1 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| reflection.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 10 | 10 | 0.0024 | 2 | 0 | 0 |

## 5. 逐图指标（五态）

### MAP-16

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| reflection.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×2 | 5 | — |
| reflection.v1 | `map16.v10.deadlock_count` | guardrail | VALID×2 | 0.5 | — |
| reflection.v1 | `map16.v10.legal_action_rate` | secondary | VALID×2 | 1 | — |
| reflection.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×1, VALID×1 | 2 | — |
| reflection.v1 | `map16.v10.mission_success` | primary | VALID×2 | 0.5 | — |
| reflection.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×2 | 0 | — |


### 指标命名空间

- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。
- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、
  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。

## 6. 代表性轨迹与证据

- 共 2 条诊断（critical 0 / warning 1）。
- `MAP-16` / `web-20261026T041003Z-d631bc8c` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1, step-2, step-3, step-4, step-5, step-6；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）

## 7. 六图可视化可用性

| 地图 | 专属视图 |
|---|---|
| MAP-08 | 本次未纳入 |
| MAP-16 | 可用（occupancy_timeline） |
| MAP-18 | 本次未纳入 |
| MAP-22 | 本次未纳入 |
| MAP-26 | 本次未纳入 |
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

实验目录：`runs/lab/lab-20261026T040533Z-447523e3/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
