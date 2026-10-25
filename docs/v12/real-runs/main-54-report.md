# 实验报告：v12-main-54-001

- `experiment_id`：`lab-20261025T120807Z-3aaedd0f`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30
- 环境 seed：[0, 1, 2]
- 实验臂：basic.v1, memory.v1, planning.v1
- 子局：54 / 54（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 6 图 × 3 seed × 3 实验臂 = 54 局。
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
| 预算截尾（`budget_censored`） | 10 |
| 已取消（`cancelled`） | 1 |
| 完成且成功（`completed_success`） | 24 |
| 机制失败（`mechanism_failure`） | 19 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 18 | 18 | 7 | 0.3889 | 30.2222 | 30.2222 | 0.0205 | 18 | 103 | 0 |
| memory.v1 | 1.0.0 | 18 | 17 | 8 | 0.4706 | 27.4444 | 27.4444 | 0.0331 | 18 | 85 | 0 |
| planning.v1 | 1.0.0 | 18 | 18 | 9 | 0.5 | 24.7222 | 26.0556 | 0.0282 | 18 | 20 | 1 |

## 5. 逐图指标（五态）

### MAP-08

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map08.v10.hypothesis_reduction` | secondary | VALID×3 | 1 | 1 |
| basic.v1 | `map08.v10.mission_success` | primary | VALID×3 | 1 | — |
| basic.v1 | `map08.v10.tests_used` | diagnostic | VALID×3 | 1.3333 | — |
| basic.v1 | `map08.v10.unjustified_repairs` | guardrail | VALID×3 | 0 | — |
| basic.v1 | `map08.v10.wrong_repairs` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map08.v10.hypothesis_reduction` | secondary | VALID×3 | 1 | 1 |
| memory.v1 | `map08.v10.mission_success` | primary | VALID×3 | 1 | — |
| memory.v1 | `map08.v10.tests_used` | diagnostic | VALID×3 | 1.6667 | — |
| memory.v1 | `map08.v10.unjustified_repairs` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map08.v10.wrong_repairs` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map08.v10.hypothesis_reduction` | secondary | VALID×3 | 1 | 1 |
| planning.v1 | `map08.v10.mission_success` | primary | VALID×3 | 1 | — |
| planning.v1 | `map08.v10.tests_used` | diagnostic | VALID×3 | 1.6667 | — |
| planning.v1 | `map08.v10.unjustified_repairs` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map08.v10.wrong_repairs` | guardrail | VALID×3 | 0 | — |

### MAP-16

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 2.6667 | — |
| basic.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0.3333 | — |
| basic.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×3 | — | — |
| basic.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0 | — |
| basic.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 0.6667 | — |
| memory.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 0.6667 | — |
| memory.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| memory.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×3 | — | — |
| memory.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0 | — |
| memory.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map16.v10.committed_ticks` | diagnostic | VALID×3 | 8.6667 | — |
| planning.v1 | `map16.v10.deadlock_count` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map16.v10.legal_action_rate` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map16.v10.makespan_gap` | secondary | NOT_APPLICABLE×1, VALID×2 | 5.5 | — |
| planning.v1 | `map16.v10.mission_success` | primary | VALID×3 | 0.6667 | — |
| planning.v1 | `map16.v10.node_capacity_conflicts` | guardrail | VALID×3 | 0.3333 | — |

### MAP-18

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 0.3333 | — |
| basic.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 1 | — |
| basic.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 0 | — |
| basic.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 0.6667 | — |
| basic.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×3 | — | — |
| basic.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 0.6667 | — |
| basic.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.5556 | 0.5556 |
| basic.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 0.3333 | — |
| memory.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 24 | — |
| memory.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 1.6667 | — |
| memory.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×1, VALID×2 | 7.5 | — |
| memory.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 2.3333 | — |
| memory.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.8889 | 0.8889 |
| memory.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 2 | — |
| planning.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map18.v10.plan_changes` | secondary | VALID×3 | 1.3333 | — |
| planning.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×3 | — | — |
| planning.v1 | `map18.v10.rejected_rows` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map18.v10.service_rate` | primary | VALID×3 | 0.5556 | 0.5556 |
| planning.v1 | `map18.v10.window_violations` | guardrail | VALID×3 | 0 | — |

### MAP-22

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0.6667 | — |
| basic.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 1.3333 | — |
| basic.v1 | `map22.v10.mission_success` | primary | CENSORED×1, VALID×2 | 0.5 | — |
| basic.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| basic.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 20.6667 | — |
| memory.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0 | — |
| memory.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 0.3333 | — |
| memory.v1 | `map22.v10.mission_success` | primary | CENSORED×2, VALID×1 | 0 | — |
| memory.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| memory.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 13.3333 | — |
| planning.v1 | `map22.v10.goal_recorded` | secondary | VALID×3 | 0.3333 | — |
| planning.v1 | `map22.v10.memory_writes` | diagnostic | VALID×3 | 0.6667 | — |
| planning.v1 | `map22.v10.mission_success` | primary | VALID×3 | 0.3333 | — |
| planning.v1 | `map22.v10.route_recall` | secondary | NOT_APPLICABLE×3 | — | — |
| planning.v1 | `map22.v10.wasted_moves` | guardrail | VALID×3 | 23.3333 | — |

### MAP-26

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map26.v10.mission_success` | primary | VALID×3 | 1 | — |
| basic.v1 | `map26.v10.rollbacks` | guardrail | VALID×3 | 0 | — |
| basic.v1 | `map26.v10.spares_used` | secondary | VALID×3 | 1 | — |
| basic.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×3 | 1 | — |
| memory.v1 | `map26.v10.mission_success` | primary | VALID×3 | 1 | — |
| memory.v1 | `map26.v10.rollbacks` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map26.v10.spares_used` | secondary | VALID×3 | 1 | — |
| memory.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map26.v10.diagnosis_precision` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map26.v10.mission_success` | primary | VALID×3 | 1 | — |
| planning.v1 | `map26.v10.rollbacks` | guardrail | VALID×3 | 0 | — |
| planning.v1 | `map26.v10.spares_used` | secondary | VALID×3 | 1 | — |
| planning.v1 | `map26.v10.wrong_swaps` | guardrail | VALID×3 | 0 | — |

### MAP-30

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×3 | — | — |
| basic.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0.3333 | — |
| basic.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.8333 | 0.8333 |
| basic.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| basic.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0 | — |
| basic.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 0 | — |
| memory.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×3 | — | — |
| memory.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0 | — |
| memory.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.75 | 0.75 |
| memory.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| memory.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0 | — |
| memory.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 0 | — |
| planning.v1 | `map30.v10.accusation_claim_precision` | primary | CENSORED×2, NOT_APPLICABLE×1 | — | — |
| planning.v1 | `map30.v10.chain_reconciled` | secondary | VALID×3 | 0.6667 | — |
| planning.v1 | `map30.v10.evidence_chain_coverage` | primary | VALID×3 | 0.9167 | 0.9167 |
| planning.v1 | `map30.v10.q4_recall_accuracy` | secondary | CENSORED×3 | — | — |
| planning.v1 | `map30.v10.unsupported_accusations` | guardrail | VALID×3 | 0.3333 | — |
| planning.v1 | `map30.v10.window_pressure_events` | diagnostic | VALID×3 | 0 | — |

## 6. 代表性轨迹与证据

- 共 139 条诊断（critical 5 / warning 101）。
- `MAP-22` / `web-20261025T122153Z-7e38291a` · `memory_payload_rejected`：8/12 次 write_memory 因 facts 结构不合规被拒（接口问题，不是记忆能力）。（证据：step-27, step-28, step-29, step-30, step-31, step-32, step-33, step-34；建议核查：核对公开契约是否把嵌套字段名写清楚（DCR-V12-01）；修好后应另立实验，不与旧版本配对。）
- `MAP-22` / `web-20261025T122520Z-cf621a41` · `memory_payload_rejected`：71/71 次 write_memory 因 facts 结构不合规被拒（接口问题，不是记忆能力）。（证据：step-19, step-20, step-21, step-22, step-23, step-24, step-25, step-26；建议核查：核对公开契约是否把嵌套字段名写清楚（DCR-V12-01）；修好后应另立实验，不与旧版本配对。）
- `MAP-22` / `web-20261025T122826Z-60d296a4` · `memory_payload_rejected`：5/5 次 write_memory 因 facts 结构不合规被拒（接口问题，不是记忆能力）。（证据：step-3, step-4, step-5, step-6, step-8；建议核查：核对公开契约是否把嵌套字段名写清楚（DCR-V12-01）；修好后应另立实验，不与旧版本配对。）
- `MAP-22` / `web-20261025T123042Z-0d9cd8de` · `memory_payload_rejected`：88/88 次 write_memory 因 facts 结构不合规被拒（接口问题，不是记忆能力）。（证据：step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10；建议核查：核对公开契约是否把嵌套字段名写清楚（DCR-V12-01）；修好后应另立实验，不与旧版本配对。）
- `MAP-30` / `web-20261025T132740Z-90ace8a1` · `unsupported_accusation`：指控被拒：证据链不完整或引用了未记录的条目。（证据：step-35；建议核查：先补齐四个条目与交叉索引，再在法庭节点提交。）
- `MAP-16` / `web-20261025T121005Z-9fc0657c` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-1, step-2, step-3, step-4, step-5, step-6；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）
- `MAP-16` / `web-20261025T121015Z-833c5066` · `no_progress_window`：连续 7 步公开进度没有变化。（证据：step-4, step-5, step-6, step-7, step-8, step-9, step-10；建议核查：检查是否在等待错误的前置条件或陷入无效探索。）
- `MAP-16` / `web-20261025T121015Z-833c5066` · `key_action_used_no_trigger`：机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。（证据：step-2, step-3, step-4, step-8, step-9, step-10；建议核查：检查机制阈值与顺序，而不是只看是否调用了工具。）

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

实验目录：`runs/lab/lab-20261025T120807Z-3aaedd0f/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
