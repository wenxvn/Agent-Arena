# 实验报告：v12-map18-seed3-4

- `experiment_id`：`lab-20261026T010001Z-47a8741a`
- 状态：`COMPLETED`
- 执行通道：**LIVE（真实模型）**：结论受样本量与 Provider 稳定性限制。
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 地图：MAP-18
- 环境 seed：[3, 4]
- 实验臂：basic.v1, memory.v1, planning.v1
- 运行时版本：`v12-lab-1+agent_policy_v1+v12-contract-2`
- 子局：6 / 6（未执行 0）

## 1. 问题与实验矩阵

研究问题：**在同一张地图、同一 seed、同一模型与预算下，更换 Agent 架构后，行为、成功率、成本与失败原因有哪些可验证差异？**

- 矩阵 = 1 图 × 2 seed × 3 实验臂 = 6 局。
- 执行方式：单 worker 串行；每局独立请求/token/费用门禁。

## 2. 不可比声明与数据口径

- 配对比较判定：`COMPARABLE`
  - 说明：配对样本为 6（每个配对键一局）；这是描述性对照，不构成显著性结论。
- 有效分母只含：完成且成功、机制失败、预算截尾；Provider 错误、取消、中断、策略异常**不计入**能力分母。
- 指标五态（VALID/CENSORED/NOT_APPLICABLE/INVALID_TRACE/UNAVAILABLE）原样保留，缺失不补 0、不跨版本求均值。
- 每对实验臂的配对键是 `(map_id, environment_seed)`；seed 不同不构成配对。

## 3. 单局类别分布

| 类别 | 局数 |
|---|---:|
| 完成且成功（`completed_success`） | 3 |
| 机制失败（`mechanism_failure`） | 3 |

## 4. 实验臂汇总

| 实验臂 | 版本 | 局数 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 已知费用局 | 拒绝动作 | 非法动作 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| basic.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 10 | 10 | 0.0099 | 2 | 2 | 0 |
| memory.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 9 | 9 | 0.0127 | 2 | 1 | 0 |
| planning.v1 | 1.0.0 | 2 | 2 | 1 | 0.5 | 8.5 | 9.5 | 0.0125 | 2 | 0 | 0 |

## 5. 逐图指标（五态）

### MAP-18

| 实验臂 | 指标 | 角色 | 五态分布 | 有效均值 | 合并比值 |
|---|---|---|---|---|---|
| basic.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×2 | 0.5 | — |
| basic.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×2 | 0.5 | — |
| basic.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×2 | 6 | — |
| basic.v1 | `map18.v10.plan_changes` | secondary | VALID×2 | 1 | — |
| basic.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×1, VALID×1 | 6 | — |
| basic.v1 | `map18.v10.rejected_rows` | guardrail | VALID×2 | 1 | — |
| basic.v1 | `map18.v10.service_rate` | primary | VALID×2 | 0.8333 | 0.8333 |
| basic.v1 | `map18.v10.window_violations` | guardrail | VALID×2 | 0.5 | — |
| memory.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×2 | 0 | — |
| memory.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×2 | 0.5 | — |
| memory.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×2 | 7.5 | — |
| memory.v1 | `map18.v10.plan_changes` | secondary | VALID×2 | 0.5 | — |
| memory.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×1, VALID×1 | 5 | — |
| memory.v1 | `map18.v10.rejected_rows` | guardrail | VALID×2 | 0.5 | — |
| memory.v1 | `map18.v10.service_rate` | primary | VALID×2 | 0.8333 | 0.8333 |
| memory.v1 | `map18.v10.window_violations` | guardrail | VALID×2 | 0.5 | — |
| planning.v1 | `map18.v10.closed_entry_attempts` | guardrail | VALID×2 | 0.5 | — |
| planning.v1 | `map18.v10.conflict_terminal` | guardrail | VALID×2 | 0.5 | — |
| planning.v1 | `map18.v10.delay_person_ticks` | secondary | VALID×2 | 4.5 | — |
| planning.v1 | `map18.v10.plan_changes` | secondary | VALID×2 | 1.5 | — |
| planning.v1 | `map18.v10.recovery_delay_ticks` | primary | NOT_APPLICABLE×1, VALID×1 | 5 | — |
| planning.v1 | `map18.v10.rejected_rows` | guardrail | VALID×2 | 0 | — |
| planning.v1 | `map18.v10.service_rate` | primary | VALID×2 | 0.8333 | 0.8333 |
| planning.v1 | `map18.v10.window_violations` | guardrail | VALID×2 | 0 | — |


### 指标命名空间

- `v10`：V10 冻结指标，历史可比；V12 不改其公式或取值。
- `v12.projection`：V12 研究投影（当前仅 MAP-22 `route_recall`），键名宽容、
  用于弥补公开信息缺口；**不与 v10 混算**，也不写入任何账本。

## 6. 代表性轨迹与证据

- 共 11 条诊断（critical 0 / warning 9）。
- `MAP-18` / `web-20261026T011307Z-1a69cec6` · `repeated_action_loop`：连续 4 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-6, step-7, step-8, step-9；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-18` / `web-20261026T011307Z-1a69cec6` · `window_violation`：在公开发车窗口之前让列车离开起点，整行被拒。（证据：step-5；建议核查：对照 published_dispatch_windows 的 release_tick 再提交。）
- `MAP-18` / `web-20261026T011328Z-c348044b` · `repeated_action_loop`：连续 4 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-1, step-2, step-3, step-4；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-18` / `web-20261026T011328Z-c348044b` · `repeated_action_loop`：连续 3 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-6, step-7, step-8；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-18` / `web-20261026T011328Z-c348044b` · `window_violation`：在公开发车窗口之前让列车离开起点，整行被拒。（证据：step-5；建议核查：对照 published_dispatch_windows 的 release_tick 再提交。）
- `MAP-18` / `web-20261026T011348Z-8c0465af` · `repeated_action_loop`：连续 7 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-1, step-2, step-3, step-4, step-5, step-6, step-7；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-18` / `web-20261026T011418Z-e5842729` · `repeated_action_loop`：连续 11 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-1, step-2, step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10, step-11；建议核查：对照启用记忆/反思臂后重复是否减少。）
- `MAP-18` / `web-20261026T011437Z-4b80b768` · `repeated_action_loop`：连续 10 步重复同一动作，期间没有新的动作选择：set_timetable。（证据：step-1, step-2, step-3, step-4, step-5, step-6, step-7, step-8, step-9, step-10；建议核查：对照启用记忆/反思臂后重复是否减少。）

## 7. 六图可视化可用性

| 地图 | 专属视图 |
|---|---|
| MAP-08 | 本次未纳入 |
| MAP-16 | 本次未纳入 |
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

实验目录：`runs/lab/lab-20261026T010001Z-47a8741a/`；子局仍在 `runs/web/<run_id>/`（V11 结构）。
