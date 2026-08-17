# Agent Arena 工程上下文

## 当前状态

- 项目处于规划阶段，尚未创建应用代码和技术架构 spec。
- 产品总设计在 `总纲.md`，仅在需要追溯完整需求时阅读，不作为每次对话的必读文件。
- 当前模块结构见 `docs/architecture.md`，交付顺序和进度见 `docs/scope/scope.md`。
- 当前第一项任务是 `/architect 项目技术架构`。完成技术决策后，先实现并测试可手动通关的确定性 Spaceship Escape 环境，再接入 LLM。

## 技术与模型配置

- **语言与运行时**：Python，具体版本和依赖管理方式由项目技术架构 spec 决定。
- **LLM 平台**：阿里云百炼，使用 OpenAI 兼容 API。
- **默认模型**：`qwen3.7-plus`。
- **本地配置**：`.env` 只保留在本机。新机器从 `.env.example` 创建它。密钥不得提交、打印、写入源码、日志、trace、文档、测试或 prompt。
- **环境变量**：`OPENAI_BASE_URL` 为百炼兼容地址，`OPENAI_API_KEY` 为运行时密钥，`DASHSCOPE_API_KEY` 为同一密钥的供应商别名，`OPENAI_MODEL` 为模型名。
- **验证命令**：修改本地密钥、端点或模型后，运行 `bash scripts/verify_model.sh`。脚本只显示模型名和最终文本。

## 开发策略

Skateboard。先交付一个真正可运行的最小闭环：确定性环境、基线 Agent Loop、Episode Trace 和可重复结果。Memory、benchmark 分析和 UI 在该闭环稳定后再增加。

## 分层上下文加载

目标是用架构和状态文档恢复上下文，不在每次任务开始时扫描或读取全仓库。

### 新对话必读

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/scope/scope.md`
4. 当前任务对应的 `docs/specs/` 文件，没有 spec 时只读取与任务直接相关的需求段落
5. `git status --short --branch`，以及当前改动的文件列表和 diff 摘要

### 按需读取代码

- `/develop`、`/test`、`/debug` 和 `/check` 只读取当前 spec 指向的目录、入口文件、直接依赖、相邻测试和当前 diff。
- 使用 `rg` 精确定位符号和调用点，先读小范围上下文，再按调用链向外扩展。
- 不因熟悉项目而读取全部源文件、全部测试、全部历史或 `总纲.md`。
- 只有以下情况可以进行全仓库扫描：`/audit`、跨模块架构重构、无法从架构文档判断责任边界，或用户明确要求。

### 任务结束时写回状态

- 交付进度写入 `docs/scope/`，由 `/scope`、`/develop`、`/test` 或 `/sync` 按各自职责更新。
- 技术决策写入 `docs/specs/`，由 `/architect` 创建或更新。
- 稳定模块边界和数据流变化写入 `docs/architecture.md`，不记录易变的实现细节。
- 全局约定写入本文件，由 `/audit` 或 `/sync` 维护。
- 每次完成后运行适用的验证和 `/sync`，再提交和推送预期文件。新对话只依赖这些持久文件，不依赖聊天记录。

## 9 个 Skill 的调用规则

| 情况 | 调用 | 读取范围 | 产物或结果 |
|---|---|---|---|
| 规划产品、下个里程碑或调整优先级 | `/scope` | 本文件、scope、相关需求 | 创建或协调 `docs/scope/scope.md` |
| 技术栈、模型客户端、环境规则、数据模型或其他关键决策未定 | `/architect <功能>` | 本文件、架构摘要、目标 scope 和相关需求 | 在 `docs/specs/` 创建或更新决策 spec |
| 缺少项目约定或新增一个有独立规则的代码区域 | `/audit` 或 `/audit <区域>` | 全仓库或指定区域 | 创建或补全 `AGENTS.md` 上下文 |
| 已有批准设计，或任务没有未决关键设计 | `/develop <功能>` | 目标 spec、架构摘要、受影响目录和测试 | 实现功能并推进构建状态 |
| 行为异常、验证失败或测试失败原因不明确 | `/debug <问题>` | 错误路径、相关测试和最小调用链 | 复现、定位、最小修复和验证 |
| 为未提交代码补充行为测试 | `/test <功能>` | 当前 diff、目标 spec、受影响代码 | 写入回归、边界和错误处理测试 |
| 证明功能在真实运行环境满足验收条件 | `/check verify <功能>` | spec 验收条件、运行入口和受影响路径 | 验证功能行为 |
| 重要提交或 PR 前进行独立代码审查 | `/check review` | 当前 diff、相关 spec 和局部调用链 | 输出按优先级排序的审查发现 |
| 需要 PR、changelog、release note 或复盘文档 | `/document <类型>` | 真实 commit、diff 和已有结果 | 输出面向人的变更文档 |
| 功能完成、合并后或持久文档可能落后于代码时 | `/sync` | 当前 diff、相关 scope、spec 和 AGENTS | 协调 scope、spec 状态和工程上下文 |

## 默认流程

新功能：`/scope` → 有关键决策时 `/architect` → `/develop` → `/check verify` → `/test` → 重要改动运行 `/check review` → `/sync` → commit 和 push。

缺陷：`/debug` → `/test` → `/check verify` → `/sync`。只写变更说明时，在已有 commit 或 diff 后运行 `/document`。

## 项目约束

- Agent 只能接收 `Observation`，不得接收完整 `WorldState`。
- Environment、agents、模型客户端、evaluation 和 UI 必须保持独立边界。
- 环境必须确定且先有规则测试，随后 benchmark 才可信。
- 全项目只保留一种 Action schema，所有 LLM 输出在执行前必须校验。
- 每局运行保存一个 JSON Episode Trace，trace 中不能包含密钥或完整思维链。
- 首个 MVP 不引入 LangChain、向量数据库、多 Agent 编排、RAG、数据库存储或复杂 UI。
- `runs/` 和 `results/` 是本地生成物，默认不纳入 Git，除非未来 scope 明确改变该规则。

_这是新 Agent 和新对话的持久入口。工程级事实改变时，用 `/audit` 或 `/sync` 更新本文件。_
