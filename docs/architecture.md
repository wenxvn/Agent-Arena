# Agent Arena 架构摘要

**状态：** 技术架构已确认，详见 [0001-project-architecture](specs/0001-project-architecture/index.md)。

本文件是新对话恢复工程上下文的架构入口。它只保存稳定边界、数据流和模块职责，不复制完整实现细节。

## 核心数据流

```text
Goal -> Agent -> Action -> Environment -> Observation -> Agent
                         |
                         v
                   Episode Trace -> Evaluation
```

Environment 保存完整世界状态并执行规则。Agent 只接收 Observation，生成经过校验的 Action。Runner 驱动循环，Trace 记录每一步，Evaluation 只消费 Trace 计算指标。

## 模块边界

| 模块 | 职责 | 不应承担的职责 |
|---|---|---|
| `src/agent_arena/arena/` | Action、Observation、WorldState、工具执行和终止规则 | LLM 调用、Agent 策略和 UI |
| `src/agent_arena/worlds/` | 具体世界配置、房间、物品、谜题和胜利条件 | 通用 Agent Loop |
| `src/agent_arena/agents/` | 基线策略、Memory 和未来的 Planning 或 Reflection | 世界规则和持久化格式细节 |
| `src/agent_arena/llm/` | DecisionProvider、OpenAI-compatible/Ollama/Fake 适配器 | 环境状态和业务规则 |
| `src/agent_arena/evaluation/` | Episode Runner、Trace 持久化、指标和 benchmark | 修改 Agent 决策或世界规则 |
| `prompts/` | 版本化的 Agent 指令模板 | 密钥和运行时配置 |
| `src/agent_arena/ui/` | Release 3 展示世界、Trace 和指标 | 直接修改 Environment 内部状态 |

## 当前 MVP 闭环

1. 用公开工具手动完成一个 Spaceship Escape 世界。
2. 用环境规则测试固定该世界行为。
3. 接入 ReactAgent，运行受步数限制的 Agent Loop。
4. 保存 JSON Episode Trace。
5. 输出基础指标；MemoryAgent 和 benchmark 对比属于 Release 2。

## 稳定契约

- `Action` 是 Agent 到 Environment 的唯一命令载体。
- `Observation` 是 Environment 到 Agent 的唯一信息载体。
- `Environment.step(action)` 返回结果和新的 Observation，不泄露完整 WorldState。
- Runner 通过 `DecisionProvider` Protocol 注入 Fake、百炼或本地 Ollama 实现，Agent 和 Environment 不直接依赖 OpenAI SDK。
- Trace 记录简短 `decision_reason`、Action、结果、token 和延迟，不保存完整思维链或密钥。
- `RuntimeSettings` 从 CLI、环境变量/`.env` 和 `config/runtime.defaults.json` 合并运行配置；Ollama 默认使用本地 `qwen2.5:7b`，OpenAI-compatible relay 使用 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`。Ollama 适配器调用原生 `/api/chat`，OpenAI-compatible 适配器调用 `/v1/responses`，两者均使用结构化 JSON 输出。
- 第一版只提供本地 CLI 与 JSON/CSV 文件输出；Streamlit 延后到 Release 3。

## 更新规则

- 新功能开始前先读取本文件和对应 spec，再读取相关代码。
- 模块职责、核心数据流或稳定契约变化时更新本文件，并用 `/architect` 更新相应 spec。
- 函数实现、局部重构和临时调试信息不写入本文件。
