# PlanningAgent v1 设计理由

PlanningAgent 与 `planner_assisted` 的边界必须保持清楚。`planner_assisted` 是面向 Spaceship Escape 的规则路线辅助；PlanningAgent 的 Planner 只生成公开证据可验证的中间目标，Executor 仍由模型选择 Action，因此两者的实验含义不同。

v1 采用单层 PlanState 而不是 Plan Tree，是为了先测量“持久子目标表示”这个单一变量。Planner 不在每步调用，避免计划漂移和成本混淆；PlanMonitor 只在公开事件发生时触发重新规划。没有公开证据的 success criteria 不自动完成，宁可保持当前计划，也不把未知事实当作已完成。

成本字段分开记录 Planner 与 Executor，是因为 Planning 的研究价值必须与额外 token 和 latency 一起解释。Trace 只保存可复盘的计划摘要，不保存完整推理链。
