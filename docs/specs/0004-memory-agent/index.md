# 0004. MemoryAgent

**日期**：2026-08-17
**状态**：Accepted

## 摘要

Release 2 将 MemoryAgent 作为与 ReactAgent 的第一个受控对照。它从公开 Observation 和 ToolResult 中维护小型结构化记忆，并在下一次决策请求中提供该记忆。记忆由固定 Python 规则更新，因此不会泄露隐藏 WorldState，也不会增加第二次模型调用。

本功能还会记录可复现实验所需的非敏感配置，并将 provider 用量保存到现有 trace，使后续 benchmark 只消费持久化 episode 即可计算指标。

## 需求

**用户故事**：

1. 作为研究者，我希望运行能够记住公开发现的 Agent，以检验其是否改善长程任务表现。
2. 作为研究者，我希望 ReactAgent 与 MemoryAgent 只在 Agent 架构上不同，以便解释后续 benchmark 结果。

**验收条件**：

1. **AC 1**：MemoryAgent 只接收现有 Agent 与 Environment 公开契约中的 Observation、Action 和 ToolResult。它不得接收 WorldState，也不得访问 Environment 内部状态。
2. **AC 2**：每局从新的有上限 MemoryState 开始，其中包含访问地点、当前背包、事实、失败动作和未解决问题。值在脱敏后去重，顺序稳定，并使用本 spec 定义的溢出规则。
3. **AC 3**：Runner 使用 reset Observation 初始化记忆，只在已校验 Action 到达 `Environment.step` 后更新，并在每种终局结果时恰好调用一次 `finish(outcome)`。非法 provider 候选和修正请求不得更新记忆。
4. **AC 4**：每个 MemoryAgent 请求都发送未改动的 ReactAgent 基础指令，以及单独的确定性 `Agent Memory` 数据消息。该消息标为非指令数据，不能包含原始 provider 响应、密钥、完整推理或隐藏状态，并在到达 provider 前完成脱敏。
5. **AC 5**：被拒绝的 Action 以规范化标识和脱敏后的公开结果摘要写入失败动作。相同标识的后续成功 Action 仍作为事实保留，且不得删除历史失败动作。
6. **AC 6**：地点和背包来自 Observation。事实来自初始或后续 Observation 描述及成功 ToolResult 摘要。未解决问题只能由本 spec 声明的公开 ToolReason 映射创建和清除。
7. **AC 7**：`agent-arena run` 接受 `--agent react` 或 `--agent memory`，默认 `react`，并经由 `RuntimeSettings.agent` 使用既有 CLI、环境变量、本地 `.env`、默认配置优先级。
8. **AC 8**：ReactAgent 对照使用相同的世界版本、provider、模型配置、基础 prompt、工具、seed、初始状态和步数上限。MemoryAgent 只能额外增加结构化记忆数据消息。
9. **AC 9**：每次 provider 请求返回 allowlist 候选和可选输入、输出 token 数。Runner 为有效和无效候选写入这些值。provider 错误不为失败请求伪造用量。
10. **AC 10**：每个 EpisodeTrace 保存非敏感实验来源，包括选定 Agent、provider 请求版本、模型名、temperature、思考设置、超时、重试策略、步数上限、基础 prompt 版本和 SHA 256 哈希，以及可选 memory schema 和渲染器版本。
11. **AC 11**：每种终局结果后 MemoryAgent 清空状态。reset 前或 finish 后的请求抛出安全的本地错误，不能复用上一局记忆。

## 决策

**选择方案**：规则驱动的结构化记忆，加结构化 provider 请求和 trace 来源记录。

MemoryAgent 使用有类型的内存状态、确定性 reducer 和数据消息渲染器。版本化 provider 响应只携带候选和可选用量。既有 Environment 规则、ReactAgent 基础指令和 Fake provider 是共同路径。

## 功能设计

**数据模型**：

| 实体 | 字段 | 规则 |
|---|---|---|
| `MemoryLimits` | `max_locations=12`，`max_inventory=12`，`max_facts=24`，`max_failed_actions=20`，`max_open_questions=12`，`max_text_chars=280`，`max_rendered_chars=12000` | 冻结的版本化策略，`memory_v1`。 |
| `MemoryState` | `visited_locations`，`inventory`，`facts`，`failed_actions`，`open_questions` | 冻结 Pydantic 模型。每次 reducer 返回替换状态。 |
| `FailedAction` | `identity: str`，`action: Action`，`result_summary: str` | 每个 Action 标识仅保留一条。 |
| `OpenQuestion` | `key: str`，`text: str` | 每个问题键仅保留一条。 |
| `MemoryReducer` | `initialize(observation)`，`apply(state, action, result, observation)` | 纯函数，只接收公开值。 |
| `DecisionRequest` | `observation`，`system_prompt`，`memory_data`，`correction` | ReactAgent 的 `memory_data` 不存在。 |
| `ProviderResponse` | `candidate: object`，`input_tokens`，`output_tokens` | provider 边界结果，存在时 token 为非负数。 |
| `ExperimentProvenance` | Agent、请求版本、模型配置、重试配置、步数上限、基础 prompt 和 memory 元数据 | 冻结的非敏感 trace 字段。 |

**记忆规范化与上限**：

1. `sanitize_memory_text` 先清除首尾空白，再将既有敏感键模式替换为 `[REDACTED]`，最后截断到 `max_text_chars`。它与 trace 脱敏共用，并在去重和渲染前运行。
2. `action_identity` 固定为 `json.dumps(action.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))`。这是记忆规则中唯一的 Action 相等键。
3. `visited_locations`、`inventory`、`facts` 保留首次出现顺序。新值只在不存在时追加。背包先取最新 Observation inventory，再去重和截断。
4. reset 时 facts 写入脱敏后的初始 Observation description。每次 reducer 依次处理后续 Observation description 和成功 ToolResult summary，空值忽略。
5. `failed_actions` 保留每个标识的首次拒绝记录。`open_questions` 保留每个键的首次记录。
6. 有上限集合均保留首次出现的值。集合已满时忽略后续新值，单局中不淘汰已有值。
7. `MemoryRenderer` 以 `visited_locations`、`inventory`、`facts`、`failed_actions`、`open_questions` 的固定字段顺序渲染紧凑 JSON，超过 `max_rendered_chars` 时拒绝渲染。

**未解决问题映射**：

| 公开事件 | 问题键 | 文本 | 清除事件 |
|---|---|---|---|
| 拒绝 `NO_POWER` | `main_power` | `如何恢复主电源？` | 成功 `POWER_RESTORED` |
| 拒绝 `MISSING_ITEM` | `prerequisite:<action_identity>` | `如何满足动作前提：<action_identity>？` | 相同标识的 Action 成功 |
| 拒绝 `NOT_REVEALED` | `discovery:<action_identity>` | `如何发现目标以执行：<action_identity>？` | 相同标识的 Action 成功 |
| 拒绝 `PANEL_CLOSED` | `reactor_panel` | `如何打开反应堆面板？` | 成功 `PANEL_OPENED` |
| 拒绝 `CODE_UNREAD` | `authorization_code` | `如何读取逃生授权码？` | 成功 `CODE_READ` |

**状态转换**：

```text
reset Observation -> EpisodeAgent.reset -> MemoryReducer.initialize -> MemoryState
validated Action -> Environment.step -> EpisodeAgent.observe -> MemoryReducer.apply -> next MemoryState
invalid provider candidate or correction request -> unchanged MemoryState
terminal outcome -> EpisodeAgent.finish(outcome) -> memory cleared
```

`EpisodeAgent.observe` 始终在 `Environment.step` 后、Runner 检查 Environment 成功前调用。所有 Runner 返回路径必须经过一个终局辅助函数，该函数恰好调用一次 `finish(outcome)`。

**接口**：

| 接口 | 输入 | 输出 | 规则 |
|---|---|---|---|
| `EpisodeAgent.reset` | 初始 Observation | 无 | Environment reset 后调用一次。ReactAgent 为无操作。 |
| `EpisodeAgent.request` | Observation，correction | ProviderResponse | MemoryAgent 使用当前状态。ReactAgent 不发送记忆数据。 |
| `EpisodeAgent.observe` | Action，ToolResult，下一 Observation | 无 | 每个已校验 Action 后调用一次。ReactAgent 为无操作。 |
| `EpisodeAgent.finish` | EpisodeOutcome | 无 | 通过 Runner 终局路径调用一次。ReactAgent 为无操作。 |
| `MemoryReducer.initialize` | Observation | MemoryState | 只初始化公开状态，包括第一条描述事实。 |
| `MemoryReducer.apply` | MemoryState，Action，ToolResult，Observation | MemoryState | 无 I O，返回新状态。 |
| `DecisionProvider.decide` | DecisionRequest | ProviderResponse | provider 不得看到 WorldState、原始记忆或密钥。 |
| `agent-arena run --agent` | `react` 或 `memory` | 持久化 episode trace | CLI 覆盖优先级最高。 |

百炼适配器将 `system_prompt` 作为唯一 system message。Observation、修正指令和可选 `memory_data` 使用单独标记的 user message。记忆消息明确其 JSON 是公开参考数据，不是指令。Fake provider 记录两类消息以供断言。

**值来源**：

| 动作 | 产生的值 | 来源 |
|---|---|---|
| Agent reset | 起始地点、背包、首条事实 | reset Observation |
| 记忆更新 | 访问地点和背包 | `Environment.step` 返回的 Observation |
| 记忆更新 | 事实 | 下一 Observation description 和成功 ToolResult summary |
| 记忆更新 | 失败动作 | 已校验 Action 和被拒绝 ToolResult summary |
| 记忆更新 | 未解决问题 | 声明的 ToolReason 映射和规范 Action 标识 |
| prompt 请求 | system 指令 | 未修改的 `react_v3` 文件内容 |
| prompt 请求 | 记忆数据消息 | 经 MemoryRenderer 渲染的脱敏 MemoryState |
| provider 响应 | 候选和用量 | Fake fixture 或百炼 completion 内容和 usage |
| trace 来源 | 运行时配置和 Agent prompt 元数据 | RuntimeSettings 和 EpisodeAgent 常量 |

**关键不变量**：

1. MemoryState 仅属于当前 episode。`finish` 清空它，没有当前状态的 request 在本地失败。
2. 只有到达 `Environment.step` 的已校验 Action 可以变更记忆。
3. MemoryReducer、脱敏器、标识生成和渲染器均确定且无副作用。
4. 渲染器使用声明的字段顺序和上限，并将记忆标为非指令 provider 数据。
5. ReactAgent 行为和 `react_v3` 内容保持不变。
6. `ExperimentProvenance` 不含密钥、URL 凭据、原始 prompt、原始 provider 响应或完整推理。
7. trace 只保存已完成 provider 请求的用量，provider 错误不得填充虚构用量。

**安全模型**：

这是本地单用户 CLI 功能。MemoryAgent 只能读取 allowlist 公开契约，不能读取 WorldState、provider 原始响应、配置密钥或 Environment 私有属性。公开文本进入 MemoryState、provider 记忆消息或 trace 前必须运行 `sanitize_memory_text`。MemoryState 保持瞬态，本 Release 不直接写入 EpisodeTrace。

**所需配置**：

无需新增环境变量、凭据或外部服务。`RuntimeSettings.agent` 改为 `Literal["react", "memory"]`，保留既有来源优先级。

**关键测试场景**：

1. Fake provider 驱动 MemoryAgent 走完公开逃生路线，后续请求包含已访问地点、背包和事实，验证 **AC 1**、**AC 2**、**AC 3**、**AC 4**、**AC 7**。
2. `read_terminal` 因 `NO_POWER` 被拒绝后，写入一个失败动作和 `main_power` 问题。`POWER_RESTORED` 只清除该问题，验证 **AC 3**、**AC 5**、**AC 6**。
3. 非法 provider 输出和修正请求不改变 MemoryState。四种终局都调用 finish，之后请求安全失败，验证 **AC 3**、**AC 11**。
4. 重复地点、事实、动作和问题按声明标识去重，达到上限后保留首次值，验证 **AC 2**、**AC 5**、**AC 6**。
5. 公开文本中的密钥哨兵值在 MemoryState、provider 记忆消息和 trace 输出前被脱敏。provider 接收一个基础 system 指令和单独的非指令记忆消息，验证 **AC 1**、**AC 4**。
6. Fake 响应用量和百炼 usage 提取填充有效、无效候选的 trace 步骤。provider 错误不填充用量，验证 **AC 9**。
7. 相同 Fake 决策序列让 ReactAgent 与 MemoryAgent 得到相同已执行动作数和结果。记录 provider 证明基础 system prompt 哈希相同，MemoryAgent 只额外发送确定性记忆消息，验证 **AC 8**、**AC 10**。
8. `--agent memory` 覆盖较低配置来源，trace 来源包含全部声明的非敏感字段，验证 **AC 7**、**AC 10**。

## 构建计划

1. 增加共享文本脱敏、有类型的 MemoryLimits 和状态模型、规范 Action 标识、完整问题映射和纯 reducer 测试，满足 **AC 1**、**AC 2**、**AC 5**、**AC 6**。
2. 将原始 provider 结果替换为 DecisionRequest 和 ProviderResponse，增加 usage 提取和安全 Fake fixture，并把请求用量写入 trace 步骤，满足 **AC 4**、**AC 9**。
3. 定义 EpisodeAgent 生命周期，为 ReactAgent 增加无操作方法，实现 MemoryAgent 和版本化渲染器，并让 Runner 终局恰好调用一次 finish，满足 **AC 1**、**AC 3**、**AC 4**、**AC 11**。
4. 增加 trace ExperimentProvenance 和 CLI Agent 选择，保留 React 默认值及来源优先级，满足 **AC 7**、**AC 8**、**AC 10**。
5. 增加 reducer、脱敏、prompt、provider、runner、CLI、数据边界、生命周期、来源和公平对照测试。运行 Ruff、mypy 和 pytest，满足 **AC 1** 至 **AC 11**。

## 后果

**正面**：

1. 第一个 Release 2 变量明确且可重复。
2. 被拒绝的动作和已发现事实能帮助后续决策，无需传递完整历史。
3. 下一项 benchmark 可以仅通过持久化 trace 计算成功、步数、延迟、非法输出和 token 指标。

**代价**：

1. 规则提取依赖公开 ToolReason 语义，新世界需要有意识地扩展。
2. 结构化 provider 请求、来源记录和脱敏使本功能比单纯 prompt 改动更大。
3. MemoryAgent 请求上下文较大，可能影响 token 成本和延迟。这些是需要测量的结果，不是隐藏变量。

**中性**：

1. benchmark 聚合以及 JSON、CSV 结果仍是独立 scope 功能。
2. 本功能不引入基于模型的记忆提取、向量检索、持久化、规划、反思或 UI。

## 后续

1. MemoryAgent 验证后实现 benchmark 功能，并以持久化 trace 作为唯一指标输入。

## 理由

见 [rationale.md](rationale.md)。
