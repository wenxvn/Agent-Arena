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
| `src/agent_arena/ui/` | 本地网页平台：地图大厅、挑战配置、运行监控、结果回放、历史对照；保留只读研究视图 | 世界规则、模型调用细节、账本实现 |
| `src/agent_arena/web/` | V11 服务层：RunService、持久化、预算、catalog、导出、自检；不依赖 Streamlit | Streamlit 渲染、地图规则 |
| `src/agent_arena/lab/` | V12 Lab：策略契约与注册表、受控模型网关、单局 Runner、父实验与队列、配对比较、证据级诊断、六图 view-model、导出与报告、SDK | 修改 V10 规则、直接调 Provider、读写 V8/V9/V10 账本 |
| `src/agent_arena/lab/v13/` | V13 深化层（**只读**）：可比性画像与单变量检查、重复稳定性、消融模板与证据包、六图构念效度与 MAP-30 阶梯、七层失败归因、六维机制画像、模板化报告、账本审计与账单对账、SDK 自检、压力测试 | 创建环境、发 Provider 请求、改历史文件或账本 |
| `src/agent_arena/web/index.py` | V13 只读历史索引：懒加载首页、mtime 增量刷新、服务端分页与聚合（有界内存） | 事件/回放读取、写 manifest |

## 当前闭环

1. 用公开工具手动完成十世界三十图（V10 起为 30 张原生运行时）。
2. 用环境规则测试固定该世界行为；V10 起有 154+172 条指标与公式级复算。
3. 接入 Agent（Legacy React/Memory/Planning，或 V12 `basic/memory/planning/reflection`），运行受预算限制的循环。
4. 保存 JSON Episode Trace 与 `result.json`。
5. 离线复算指标、配对对照与失败归因；V11 网页可启动/回放/导出单局，V12 Lab 可跑多架构矩阵，V13 在其上加**重复稳定性、可比性协议、消融模板、构念效度、分层归因、机制画像、模板报告与账本审计**。

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
- 核心实验仍通过本地 CLI 运行并输出 JSON/CSV。研究阶段另有只读 Streamlit MVP，读取本地 `runs/`、`results/`，不访问 `.env` 或调用 Provider；V11 起新增可操作的本地网页平台，通过 `web/RunService` 启动单局、持久化状态、取消与导出。

## V11 网页平台边界

- `src/agent_arena/web/` 是独立服务层：`RunService` 负责提交、排队、单 worker 执行、取消、恢复与查询；`RunStore` 负责 `runs/web/<run_id>/` 的原子 manifest、append-only JSONL 与 result；`RunBudget` 负责请求/token/费用门禁。
- Streamlit 只做展示与操作，不直接创建环境或调用 Provider；任务事实来源始终是磁盘 manifest，不是 `st.session_state`。
- 离线演示使用公开启发式规则策略，元数据显式标记 `public_heuristic_policy`，不得冒充模型挑战。
- 真实模式复用 V10 `create_environment`、带类型公开契约、`scenario_v4` 请求语义与 MiMo 价格口径；每局独立预算，不读写 V10 账本。
- 状态机：`CREATED -> QUEUED -> RUNNING -> {SUCCEEDED, FAILED, BUDGET_REACHED, CANCELLED, PROVIDER_ERROR, INTERRUPTED}`；指标五态独立显示。
- 默认只监听 `127.0.0.1`；API Key 只从本机 `.env` 读取，网页不回显，不接受自定义 URL。
- 30 图 ID、V10 规则、指标、Oracle 与历史冻结账本保持只读；展示难度只存在于 `web/catalog.py`。

## V12 Lab 边界

- `src/agent_arena/lab/` 是第二阶段实验层，与 `web/` 并列而非替代：父实验 `ExperimentService` 只编排，真正执行仍由 `RunService` 承担。
- 一条运行链路：`ExperimentSpec` → `preflight`（零请求）→ 父实验队列 → 子局 `RunConfig` → `AgentRunnerV12` → V10 Environment；动作一律经 `V8Action` 与 `environment.accepts`。
- `AgentPolicy` 只拿到 `PublicObservation` / `AgentContext`；`DecisionGateway` 是唯一模型出口，Planner / Reflection 的额外请求共享同一 `RunBudget` 并计入账本。
- 三种执行通道严格隔离：`OFFLINE`（公开启发式，V11 语义不变）、`SIMULATED`（确定性脚本 Provider，零费用、不写付费账本）、`LIVE`（真实模型，需显式 `LiveApproval`）。
- 分析层只读已落盘 trace：`compare.py` 做分母与配对，`diagnostics.py` 出证据级 `Finding`，`visualization.py` 出六图 view-model，`report.py` 出可读报告与 CSV/JSON。
- 不修改 `v10/`、`worlds/scenario_v8/`、V8/V9/V10 账本与历史 trace；`runs/lab/` 为新增输出目录，`runs/web/` 只新增可选 provenance 字段。

## V3 Scenario 边界

- V3 的 30 个 allowlist selector 由 `worlds/scenario/catalog.py` 注册，定义、十家族规则与只读公开 Oracle 位于 `worlds/scenario/`。旧世界和 V2 seeded 定义保持原有 selector 与行为。
- `arena/scenario_models.py` 定义 V3 专用 `ScenarioAction`、`ScenarioObservation`、结果和终态。Scenario Environment 私有持有完整状态，只将当前房间、可行出口、可见互动、背包和公开状态事实返回给 Agent。
- Runner 根据显式 `world_version` 选择 `legacy_v1` 或 `scenario_v3` Action contract；V3 Episode Trace 以可选字段保留兼容读取，提交答案在持久化 Trace 中脱敏。UI 只显示 Trace 中已保存的公开数据。
- V3 当前 ReactAgent 使用版本化 `prompts/react_scenario_v3.txt`。候选动作、Memory/Planning 的未声明 V3 行为会被拒绝；离线 Oracle 只用于确定性验收，真实 Provider 对照须另立实验。

## V7 指标层边界

- `src/agent_arena/v7/metrics/` 是只读评测层：输入是已持久化 Episode Trace 与可选离线 judge artefact，输出是带五态状态的 `MetricValue`；不启动环境、不调用 Provider、不写账本。
- 六张已有运行时的地图各自实现独立 extractor；跨图共享仅限 `schema.py`、`common.py` 的算术和 `references.py` 的冻结离线常量，不共享同一评分公式。
- 每条 `MetricSpec` 带显式 `valid_range`、缺失/截尾规则；六图 extractor 有 36 条真实环境手算 fixture，覆盖成功、机制失败、边界、截尾与 N/A。
- 24 张设计态地图只注册 `MetricSpec`（`implemented=False`），`compute_metrics` 必须抛 `NotImplementedError`；缺失、截尾、不适用和非法 trace 不得补 0。每张设计态图有独立的 `docs/v7/pending-runtime/MAP-XX.md` 记录阻塞项与接入门槛。
- `scripts/check_v7_leakage.py` 静态检查 V7 只读边界；V7 不得导入 runner/prompt/provider/environment 模块，不得写文件或读取凭据。

## V9 审计与定标层边界

- `src/agent_arena/v9/` 是只读审计与有界验证层：`audit.py` 复算 V8 90 局，`evidence.py` 生成逐图证据包，`metric_checks/` 提供 120 条独立指标复算，`policies/` 提供 30 个公开启发式与消融。
- V9 不修改 `worlds/scenario_v8/`、V4 适配层、V7 extractor 或 V8 账本；公开信息补充只存在于 `v9/prompts.py` 的 `v9_fixed` 臂，`v8_compat` 臂与 V8 prompt 逐字一致。
- `v9/metrics.py` 按 V7 登记的 censor 规则重新投影 `decision_budget_reached`；`v9/metric_overlay.py` 新增/修正有证据的指标，旧值保留在 `runs/v9/rescore/`。
- `v9/budget.py` 是独立 append-only 账本（¥10 硬上限、请求前预留、unknown spend 封账）；`v9/runner.py` 记录 `arm`、`prompt_hash`、`overlay_schema_hash`，与 V8 结果分开报告。
- 30 份逐图审计在 `docs/v9/maps/`，DCR 在 `docs/v9/dcr/`；`human_approved` 只能由用户确认，执行 Agent 只标 `agent_reviewed`。V8 的 `worlds/scenario_v8/` 与 `v8/` 层同理保持只读。

## V10 运行时与指标层边界

- `src/agent_arena/v10/` 是 30 图原生运行时与冻结指标层：`runtime/` 保存逐图环境与类型化公开动作契约，`metrics/` 保存 154 旧 + 172 新指标，`freeze.py`/`recompute.py`/`independent_check.py` 提供冻结与两套独立复算。
- 每张图的 `create_environment(map_id)` 是唯一入口；Agent 只能拿到公开 Observation，动作必须通过该图的 `accepts`/`step`。
- V10 账本与冻结 manifest 是只读历史资产：新增实验只能另开目录与命名空间（V11 `runs/web/`、V12 `runs/lab/`），不得回写。
- V12 研究投影指标放在 `lab/metrics_v12.py` 的 `v12.projection.*` 命名空间，与 `map*.v10.*` 并列导出，不覆盖、不并入 V10 均值。

## 更新规则

- 新功能开始前先读取本文件和对应 spec，再读取相关代码。
- 模块职责、核心数据流或稳定契约变化时更新本文件，并用 `/architect` 更新相应 spec。
- 函数实现、局部重构和临时调试信息不写入本文件。
