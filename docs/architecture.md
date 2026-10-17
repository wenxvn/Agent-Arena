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
| `src/agent_arena/agents/` | 基线策略、Memory、Planning 和未来的 Reflection | 世界规则和持久化格式细节 |
| `src/agent_arena/llm/` | DecisionProvider、OpenAI-compatible/Ollama/Fake 适配器 | 环境状态和业务规则 |
| `src/agent_arena/evaluation/` | Episode Runner、Trace 持久化、公开进展/事实、失败分析、指标和 benchmark | 修改 Agent 决策或世界规则 |
| `prompts/` | 版本化的 Agent 指令模板 | 密钥和运行时配置 |
| `src/agent_arena/ui/` | 只读回放 Trace、矩阵指标、错误热点和条件对照 | 启动 Episode/Benchmark、直接修改 Environment 内部状态 |

## 当前 MVP 闭环

1. 用公开工具手动完成十个世界的三十张难度图。
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
- `RuntimeSettings` 从 CLI、环境变量/`.env` 和 `config/runtime.defaults.json` 合并运行配置；Ollama 默认使用本地 `qwen2.5:7b`，OpenAI-compatible relay 使用 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`。Ollama 适配器调用原生 `/api/chat`，OpenAI-compatible 适配器调用 `/v1/responses`；默认使用兼容性更广的 JSON object，若 relay 支持可显式启用共享 Action JSON Schema。
- Runner 将非法候选分类为不含原文的安全类别，并可独立启用只根据当前公开 Observation 生成的动作候选提示；这些提示和推理强度都写入 trace provenance，不能与纯自主结果混合。
- `PlanningAgent` 在 `src/agent_arena/planning/` 中维护 episode-local `PlanState`。Planner 只接收公开 Observation、公开结果、计划状态和受限历史，输出非执行性的 `PlannerDecision`；Executor 复用统一 Action contract，`PlanMonitor` 只根据公开进度判断继续、子目标完成、无进展或重复失败。
- Planning Trace 记录 `plan_id`、当前子目标、Planner 调用、重规划原因、监控信号、子目标完成和 Planner/Executor 成本。`planner_assisted` 仍是独立的规则路线辅助模式，不与 `planning` 结果合并。
- Evaluation v2 在 `evaluation/progress.py` 中将公开状态变化与 episode-local 公共事实分开计数；`evaluation/failures.py` 只用规则生成自动失败信号，并保留人工标注入口。`planning/criteria.py` 负责结构化 `SuccessCriterion`，同时兼容 Planning v1 字符串条件。
- Trace schema v2 为已执行步骤记录 `ProgressEvent`，旧 trace 缺失字段时仍可读取，但对应指标必须标记为不可用；失败分析 CLI 输出独立的 JSON/CSV 报告。
- 核心实验仍通过本地 CLI 运行并输出 JSON/CSV。研究阶段另有只读 Streamlit MVP，读取本地 `runs/`、`results/`，不访问 `.env` 或调用 Provider；可配置并启动实验的完整界面仍属于 Release 3。

## V3 Scenario 边界

- V3 的 30 个 allowlist selector 由 `worlds/scenario/catalog.py` 注册，定义、十家族规则与只读公开 Oracle 位于 `worlds/scenario/`。旧世界和 V2 seeded 定义保持原有 selector 与行为。
- `arena/scenario_models.py` 定义 V3 专用 `ScenarioAction`、`ScenarioObservation`、结果和终态。Scenario Environment 私有持有完整状态，只将当前房间、可行出口、可见互动、背包和公开状态事实返回给 Agent。
- Runner 根据显式 `world_version` 选择 `legacy_v1` 或 `scenario_v3` Action contract；V3 Episode Trace 以可选字段保留兼容读取，提交答案在持久化 Trace 中脱敏。UI 只显示 Trace 中已保存的公开数据。
- V3 当前 ReactAgent 使用版本化 `prompts/react_scenario_v3.txt`。候选动作、Memory/Planning 的未声明 V3 行为会被拒绝；离线 Oracle 只用于确定性验收，真实 Provider 对照须另立实验。

## V7 指标层边界

- `src/agent_arena/v7/metrics/` 是只读评测层：输入是已持久化 Episode Trace 与可选离线 judge artefact，输出是带五态状态的 `MetricValue`；不启动环境、不调用 Provider、不写账本。
- 六张已有运行时的地图各自实现独立 extractor；跨图共享仅限 `schema.py`、`common.py` 的算术和 `references.py` 的冻结离线常量，不共享同一评分公式。
- 24 张设计态地图只注册 `MetricSpec`（`implemented=False`），`compute_metrics` 必须抛 `NotImplementedError`；缺失、截尾、不适用和非法 trace 不得补 0。

## 更新规则

- 新功能开始前先读取本文件和对应 spec，再读取相关代码。
- 模块职责、核心数据流或稳定契约变化时更新本文件，并用 `/architect` 更新相应 spec。
- 函数实现、局部重构和临时调试信息不写入本文件。
