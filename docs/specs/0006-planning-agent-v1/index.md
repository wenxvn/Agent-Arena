# 0006. PlanningAgent v1

**状态：** Accepted

## 目标

在不改变 Environment、Observation、Action schema 和 Executor 校验边界的前提下，引入一个通用的、事件触发的高层 PlanningAgent。它维护一个 episode-local `PlanState`，由 Planner 生成和更新子目标，由 Executor 选择单个 Action，由 PlanMonitor 根据公开证据判断是否继续或重新规划。

## 决策

1. Planner 只能接收 `Observation`、公开 `ToolResult`、当前 `PlanState` 和受限公开历史；不得接收 `WorldState`，不得直接调用 `Environment.step`，不得返回 Action。
2. `PlanState`、`PlannerDecision`、`PlanSignal` 使用 Pydantic 结构化模型；Planner 输出只允许计划字段。
3. PlanningAgent 复用 `ReactAgent` 的 Action 解析和 Runner 执行边界。Executor 请求通过 `DecisionRequest(output_contract="action", plan_data=...)` 接收计划上下文。
4. Planner 采用事件触发策略：episode 开始、子目标完成、连续三次公开无进展、同一公开状态下相同失败重复时调用；单次失败不触发。
5. PlanMonitor 只比较公开进度投影和公开结果。无法由公开证据证明的 success criteria 不得被猜测为完成。
6. Trace 只保存计划生命周期的 allowlisted 摘要：`plan_id`、`plan_version`、`current_subgoal`、Planner 调用、重规划原因、监控信号、子目标完成和 Planner/Executor 成本；不保存完整 reasoning 或原始 provider response。
7. Benchmark 继续从持久化 Trace 计算指标，并额外报告 Planner 调用、重规划、子目标完成率、无进展/重复失败以及 Planner/Executor token 和 latency。
8. `planning` 是独立 CLI Agent；`planner_assisted` 保持独立，不得把规则路线辅助结果并入 PlanningAgent 的模型自主结论。

## 非目标

- 不实现 ReflectionAgent、Planning Tree、多 Planner、Memory+Planning 消融或 Streamlit UI。
- 不把 Spaceship Escape 路线写入 PlanningAgent、Planner prompt 或 PlanMonitor。
- 不改变统一 Action schema，也不允许 Runner 代替模型执行 Planner 建议。

## 验收条件

- [x] PlanningAgent 可通过 Fake provider 完整运行并在每局 reset 时清空 PlanState。
- [x] Planner 与 Executor 是不同的 provider request，Planner request 的 output contract 不包含 Action。
- [x] PlanMonitor 覆盖 `continue`、`subgoal_completed`、`no_progress` 和 `repeated_failure`。
- [x] 所有 Executor Action 仍由既有 Action schema 和 EpisodeRunner 执行。
- [x] Trace 可复盘初始计划、计划保持、子目标完成和事件重规划。
- [x] CLI 支持 `--agent planning`，Benchmark 支持 Planning 指标。
- [x] pytest、Ruff、mypy 通过；Fake provider 固定 5 seeds 可重复完成 20 步公共路径。
- [ ] 真实模型 5 seeds 的研究结论：需要在本地模型服务可用时单独运行，不能用 Fake 结果替代。
