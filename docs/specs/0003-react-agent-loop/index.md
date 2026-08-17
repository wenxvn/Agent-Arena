# 0003. ReactAgent、Episode Runner 与 Trace

**Date**: 2026-08-17
**Status**: Accepted

## Summary

Release 1 将 ReactAgent、受限 Episode Runner 和 JSON Episode Trace 作为一个可运行闭环交付。Agent 只接收 `Observation`，通过注入的 `DecisionProvider` 生成短决策说明和严格 `Action`；Runner 在执行前验证输出、处理修正与终止条件，并持久化只包含 allowlist 字段的 trace。

## Requirements

1. **AC-1**: `ReactAgent` 只向 provider 传递 `Observation`、版本化 prompt 和 `correction` 标记；它不读取 `WorldState`，也不直接调用 Environment。
2. **AC-2**: 有效决策是严格对象 `{ "decision_reason": str, "action": Action }`。`decision_reason` 最长 280 字符，未知字段、缺少字段或无效 Action 都视为非法模型输出。
3. **AC-3**: Runner reset 世界后循环请求决策、验证 Action、调用 `Environment.step`，在环境成功、达到 `step_limit`、连续三次非法输出或 provider 错误时终止。环境拒绝是正常一步，不计为非法输出。
4. **AC-4**: 首次非法输出只针对同一 Observation 请求一次修正；修正仍非法时开始新的决策周期。仅有效 Action 才将连续非法计数清零。
5. **AC-5**: 每局生成一个原子写入的 JSON Trace，包含 UUID、世界版本、seed、agent、provider、终止 outcome、计数和步骤事件。有效动作步骤记录 allowlisted Observation、短决策说明、Action、ToolResult、状态和延迟。
6. **AC-6**: Trace 不保存原始 provider 请求/响应、异常正文、完整 reasoning、API key 或 `WorldState`。文本字段有长度上限并按敏感键模式脱敏。
7. **AC-7**: `agent-arena run` 使用 Fake provider 默认 fixture 运行一个完整的 Spaceship Escape episode；`--provider bailian` 只在显式指定且本地配置有效时创建真实 provider。CLI 对任何已持久化 terminal outcome 返回 0。

## Decision

`agents/` 负责 prompt 与 provider 调用，`evaluation/` 负责循环、输出验证、终止与 trace，`llm/` 负责 Fake 或百炼适配。Action 验证仍使用 `arena.action_adapter`，Environment 保持不知晓模型输出和 trace。

`StepTrace` 同时记录执行步骤和不执行环境的事件。非法输出仅记录固定事件名称和 allowlisted Observation，绝不记录模型原始候选；provider 失败只记录固定安全摘要。这样能复盘控制流，又不会把不可信模型文本带进持久化数据面。

## Public Contracts

| 类型 | 字段或行为 |
|---|---|
| `AgentDecision` | `decision_reason: str`，`action: Action`；严格校验 |
| `ReactAgent.request` | 输入 `Observation` 与 correction，返回 provider 的原始候选；不做世界操作 |
| `EpisodeRunner.run` | reset、处理每轮请求/修正、执行有效 Action，并返回 `EpisodeTrace` |
| `EpisodeOutcome` | `success`、`step_limit`、`invalid_action_limit`、`provider_error` |
| `EpisodeTrace` | episode header、计数、总延迟与 `StepTrace` 列表 |
| `write_episode_trace` | 同目录临时文件加原子 rename；写入脱敏 JSON |

## State transitions

```text
reset -> primary decision -> valid Action -> Environment.step -> next decision
                       |-> invalid -> one correction -> valid Action
                                                 |-> invalid -> next primary decision

success | step limit | third consecutive invalid | provider error -> persisted terminal trace
```

有效 Action 后，如果 Environment 返回 rejected，Runner 记录 `action_rejected` 并继续。step limit 按 Environment 已执行的 Action 计数，非法输出不消耗环境步数。

## Build Plan

1. 定义 ReactAgent 决策模型和 `react_v2` prompt，并实现百炼结构化响应适配。
2. 实现 trace allowlist、脱敏原子写入和 Episode Runner 状态机。
3. 用完整 Fake 响应序列驱动 Spaceship Escape，替换 CLI scaffold episode。
4. 覆盖成功、修正、非法输出上限、环境拒绝、provider 失败、脱敏和 CLI 行为。

## Consequences

Release 1 得到可重复的单局实验闭环，Release 2 可以只消费 Trace 构建 benchmark 与 MemoryAgent 对照。当前不实现 benchmark、记忆、规划、反思或 UI。
