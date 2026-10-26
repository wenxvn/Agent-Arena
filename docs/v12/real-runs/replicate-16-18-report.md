# 实验报告：v12-replicate-map16-18

- `experiment_id`：`lab-20261026T012103Z-47f6701c`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-16, MAP-18
- 环境 seed：[0, 1, 2]
- 实验臂：basic.v1, memory.v1, planning.v1
- 运行时版本：`v12-lab-1+agent_policy_v1+v12-contract-2`
- 子局：18 / 18（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 2 图 × 3 seed × 3 实验臂 = 18 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

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
| 机制失败（`mechanism_failure`） | 14 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 6 | 6 | 2 | 0.3333 | 9.5 | 9.5 | 0.0063 | 6 | 3 | 0 |
| memory.v1 | 1.0.0 | 6 | 6 | 0 | 0 | 9.8333 | 9.8333 | 0.0107 | 6 | 5 | 0 |
| planning.v1 | 1.0.0 | 6 | 6 | 2 | 0.3333 | 16.3333 | 18 | 0.019 | 6 | 14 | 0 |

## 5. 逐图指标（五态）

### MAP-16

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 4 | — |
| basic.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0.3333 | — |
| basic.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×2, VALID×1 | 4 | — |
| basic.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0.3333 | — |
| basic.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 0.3333 | — |
| memory.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 1.6667 | — |
| memory.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| memory.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×3 | — | — |
| memory.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0 | — |
| memory.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 8 | — |
| planning.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×1, VALID×2 | 5.5 | — |
| planning.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0.6667 | — |
| planning.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 0.3333 | — |

### MAP-18

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 0.3333 | — |
| basic.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 0.6667 | — |
| basic.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 12 | — |
| basic.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×2, VALID×1 | 8 | — |
| basic.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 0.6667 | — |
| basic.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.7778 | 0.7778 |
| basic.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 1 | — |
| memory.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 5 | — |
| memory.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 0.3333 | — |
| memory.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×3 | — | — |
| memory.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 1 | — |
| memory.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.5556 | 0.5556 |
| memory.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 1.6667 | — |
| planning.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 2.3333 | — |
| planning.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×3 | — | — |
| planning.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.5 | 0.5 |
| planning.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 0 | — |


### 指标命名空间

- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。
- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、
  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。

## 6. 代表性轨迹与证据

- 共 36 条诊断（critical 0 / warning 29）。
- `MAP-16` / `web-20261026T012103Z-53a0bcd6` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1, step-2, step-3, step-4, step-5, step-6；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-16` / `web-20261026T012237Z-b5df98ab` · `no_progress_window`：连续 4 步公开进度没有变化。（证据：step-2, step-3, step-4, step-5；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-16` / `web-20261026T012237Z-b5df98ab` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1, step-2, step-3, step-6, step-7, step-8, step-9, step-10；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-16` / `web-20261026T012309Z-5dbccf62` · `frame_mismatch`：没有先登记路由就 move_train（整帧提交缺少内容）。（证据：step-11；建议核查：set_route/occupy_siding 登记下一跳后，再用 move_train 整帧提交。）
- `MAP-16` / `web-20261026T012527Z-83560ccf` · `repeated_action_loop`：连续 4 步重复同一动作，期间没有新的动作选择：inspect_network。（证据：step-5, step-6, step-7, step-8；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-16` / `web-20261026T012527Z-83560ccf` · `no_progress_window`：连续 8 步公开进度没有变化。（证据：step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-16` / `web-20261026T012527Z-83560ccf` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-2, step-3, step-4, step-9, step-10, step-11；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-16` / `web-20261026T012620Z-202bb46c` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1, step-2, step-3；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）

## 7. 六图可视化可用性

| 地图 | 专属视图 |
|---|---|
| MAP-08 | 本次未纳入 |
| MAP-16 | 可用（occupancy_timeline） |
| MAP-18 | 可用（recovery_gantt） |
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

实验目录：`runs/lab/lab-20261026T012103Z-47f6701c/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
