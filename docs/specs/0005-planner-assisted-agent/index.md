# 0005. 公开规划辅助 Agent

**日期**：2026-08-18
**状态**：Accepted（实验性模式）

## 摘要

`planner_assisted` 是为本地模型通关演示提供的独立 Agent 模式。它从当前公开 `Observation`、已执行 Action、公开 `ToolResult` 和结构化 Memory 推导任务阶段与下一动作建议，再把建议作为最新请求中的公开运行时反馈交给模型。

规划器不能读取 `WorldState`，不能调用 `Environment.step`，不能替模型执行、修正或重放 Action。每一个实际执行的 Action 仍必须由模型返回并通过既有 Action schema 校验。Trace 使用独立 agent 名称和 prompt 版本，不能与纯 ReactAgent 或 MemoryAgent 结果合并。

## 决策

- 使用 `PlannerAssistedAgent` 继承 `MemoryAgent` 的公开记忆能力。
- 规划器只维护公开的阶段标志：修理工具收集、主电源恢复、授权码读取和逃生舱启动。
- 授权码只在公开 `CODE_READ` ToolResult 中提取；基础 prompt 不包含具体谜底。
- 规划建议放在最新 `runtime_feedback` 中，通用循环提醒存在时仍追加阶段建议。
- CLI 通过 `--agent planner_assisted` 显式启用；默认 `react` 和 `memory` 行为保持可区分。

## 验收条件

1. Agent 请求不包含 WorldState、密钥或原始 provider 响应。
2. Fake 公开逃生路线成功，trace 标记 `planner_assisted_v2` 和 `react_v11`。
3. `qwen2.5:7b` 在固定世界、seed 0/1/2 和 30 步预算下真实运行成功，且每局 Action 均来自模型响应。
4. 规划辅助结果单独统计，不作为纯模型自主规划成功率。

## 验证结果

`uv run ruff check .`、`uv run mypy src` 和 48 项 pytest 通过。Ollama 三局 benchmark 为 3/3 成功，平均 19 步、0 次非法输出、0 次环境拒绝。
