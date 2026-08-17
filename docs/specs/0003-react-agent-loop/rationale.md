# ReactAgent、Episode Runner 与 Trace 依据

## Context

Spaceship Escape 已有确定规则和严格的 Action/Observation 边界。下一层需要把不可信模型输出接到该环境，同时保留可重复测试、明确失败原因与不会泄露密钥的观察记录。

## Decision

将 provider 调用放在 ReactAgent，将循环控制、Action 校验和 trace 持久化放在 evaluation。Runner 不保存原始模型内容：只有通过严格校验的短决策说明和 Action 才进入执行步骤；无效候选和 provider 异常仅以固定事件保存。

## Alternatives

直接让 Environment 解析模型输出会破坏世界规则与模型调用的边界。让 Agent 自己调用 `Environment.step` 会使终止、trace 和测试难以统一。保存原始响应虽然便于调试，却违反 trace 数据最小化与 reasoning 隔离约束。

## Tradeoffs

Trace 不足以恢复无效模型的原文，但保留了对实验有用的失败类别和计数。真实 provider 的结构化响应仍可能失败，因此显式修正和上限终止比无限重试更适合作为实验基线。
