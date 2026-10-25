# 实验报告：demo-three-architectures

- `experiment_id`：`lab-20261025T105431Z-c3d0c415`
- 状态：`COMPLETED`
- 执行通道：**SIMULATED（离线模拟，不是模型）**：结论只说明调用链、预算与诊断链路可用，不代表任何真实模型能力。
- 模型 / Provider：`simulated-agent-policy` / `simulated_scripted`
- 地图：MAP-10, MAP-22, MAP-26
- 环境 seed：[0]
- 实验臂：basic.v1, memory.v1, planning.v1
- 子局：9 / 9（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 3 图 × 1 seed × 3 实验臂 = 9 局。
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
| 预算截尾（`budget_censored`） | 5 |
| 完成且成功（`completed_success`） | 1 |
| 机制失败（`mechanism_failure`） | 3 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 5.6667 | 5.6667 | 0 | 3 | 0 | 0 |
| memory.v1 | 1.0.0 | 3 | 3 | 1 | 0.3333 | 8.6667 | 8.6667 | 0 | 3 | 4 | 0 |
| planning.v1 | 1.0.0 | 3 | 3 | 0 | 0 | 8.3333 | 10.3333 | 0 | 3 | 7 | 0 |

## 5. 逐图指标（五态）

### MAP-10

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map10.v10.delivered_ratio` | secondary | VALID×1 | 0 | 0 |
| basic.v1 | `map10.v10.fuel_left` | secondary | NOT_APPLICABLE×1 | — | — |
| basic.v1 | `map10.v10.load_retries` | diagnostic | VALID×1 | 0 | — |
| basic.v1 | `map10.v10.mission_success` | primary | VALID×1 | 0 | — |
| memory.v1 | `map10.v10.delivered_ratio` | secondary | VALID×1 | 1 | 1 |
| memory.v1 | `map10.v10.fuel_left` | secondary | VALID×1 | 1 | — |
| memory.v1 | `map10.v10.load_retries` | diagnostic | VALID×1 | 0 | — |
| memory.v1 | `map10.v10.mission_success` | primary | VALID×1 | 1 | — |
| planning.v1 | `map10.v10.delivered_ratio` | secondary | VALID×1 | 0 | 0 |
| planning.v1 | `map10.v10.fuel_left` | secondary | VALID×1 | 4 | — |
| planning.v1 | `map10.v10.load_retries` | diagnostic | VALID×1 | 0 | — |
| planning.v1 | `map10.v10.mission_success` | primary | VALID×1 | 0 | — |

### MAP-22

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 0 | — |
| basic.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 1 | — |
| basic.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| basic.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1 | — | — |
| basic.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 0 | — |
| memory.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 0 | — |
| memory.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 3 | — |
| memory.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| memory.v1 | `map22.v10.route_recall` | secondary | VALID×1 | 1 | 1 |
| memory.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 0 | — |
| planning.v1 | `map22.v10.goal_recorded` | secondary | VALID×1 | 0 | — |
| planning.v1 | `map22.v10.memory_writes` | diagnostic | VALID×1 | 1 | — |
| planning.v1 | `map22.v10.mission_success` | primary | CENSORED×1 | — | — |
| planning.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×1 | — | — |
| planning.v1 | `map22.v10.wasted_moves` | guardrail | VALID×1 | 0 | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 0 | — |
| basic.v1 | `map26.v10.mission_success` | primary | VALID×1 | 0 | — |
| basic.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 0 | — |
| basic.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 3 | — |
| basic.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 2 | — |
| memory.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 0 | — |
| memory.v1 | `map26.v10.mission_success` | primary | CENSORED×1 | — | — |
| memory.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 1 | — |
| memory.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 1 | — |
| memory.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×1 | 0 | — |
| planning.v1 | `map26.v10.mission_success` | primary | CENSORED×1 | — | — |
| planning.v1 | `map26.v10.rollbacks` | guardrail | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.spares_used` | secondary | VALID×1 | 1 | — |
| planning.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×1 | 1 | — |

## 6. 代表性轨迹与证据

- 共 27 条诊断（critical 0 / warning 21）。
- `MAP-10` / `web-20261025T105431Z-a3e1ba0d` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-10` / `web-20261025T105432Z-8f5de247` · `key_action_never_attempted`：核心机制动作 ['load', 'unload'] 一次都没有调用。（证据：无单步证据；建议核查：先确认模型是否读懂了公开目标与动作契约。）
- `MAP-22` / `web-20261025T105432Z-fe5211dc` · `no_progress_window`：连续 8 步公开进度没有变化。（证据：step-5, step-6, step-7, step-8, step-9, step-10, step-11, step-12；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-22` / `web-20261025T105432Z-fe5211dc` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-10；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-22` / `web-20261025T105432Z-fe5211dc` · `memory_not_used`：写过记忆，但没有记录方位（bearing/path_state），无法用于返程。（证据：step-10；建议核查：记忆内容应包含走过的方位序列。）
- `MAP-22` / `web-20261025T105432Z-e5e1ecf9` · `no_progress_window`：连续 10 步公开进度没有变化。（证据：step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11, step-12；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-22` / `web-20261025T105433Z-676d1b6f` · `no_progress_window`：连续 9 步公开进度没有变化。（证据：step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11, step-12；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-22` / `web-20261025T105433Z-676d1b6f` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-9；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）

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
- SIMULATED 模式下策略行为由确定性脚本 Provider 驱动，**不能**用来声称任何架构能力差异。

## 9. 复现方式

```bash
# 零 API：跑同一矩阵的离线模拟
uv run python scripts/demo_v12.py
# 一键验收（含 Lab 契约、预算、父子状态、导出复算）
uv run python scripts/verify_v12.py
```

实验目录：`runs/lab/lab-20261025T105431Z-c3d0c415/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
