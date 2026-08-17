# Agent Arena 工程事件记录

这份记录只保存重要的工程事件，不替代 scope、spec 或 Git 历史。

记录范围包括：阶段开始或完成、架构决策确认或修改、重要验证结果、阻塞及解决、开发优先级调整。

每条记录使用以下结构：

```text
## 日期 事件名称

事件：发生了什么
原因：为什么做
改动：主要文件或范围
验证：运行了什么，结果如何
下一步：接下来做什么
关联提交：Git commit，若有
```

## 2026-08-17 架构决策确认

事件：项目采用 Python 3.13、uv、本地分层单体、CLI 和本地 JSON 文件作为第一版基础架构。

原因：先建立一个可重复的本地 Agent 研究闭环，避免过早引入服务、数据库和复杂编排。

改动：接受 `docs/specs/0001-project-architecture/`，明确 Environment、Agent、LLM、Evaluation 和 UI 的边界。

验证：架构检查清单已建立，真实模型调用被明确为手动验证，不进入默认 CI。

下一步：完成 Foundation scaffold。

关联提交：`c630729`

## 2026-08-17 Foundation scaffold 完成

事件：项目已经可以安装、运行 CLI、生成 Fake episode，并执行自动质量检查。

原因：为确定性的 Spaceship Escape 环境提供稳定的代码和测试基础。

改动：新增 `pyproject.toml`、`uv.lock`、`src/agent_arena`、RuntimeSettings、Fake provider、CLI、测试和 GitHub Actions。

验证：`uv lock --check`、Ruff、mypy 和 10 项 pytest 全部通过。`uv run agent-arena run` 成功生成 JSON episode，百炼模型验证也成功返回确认文本。

下一步：运行 `/architect Spaceship Escape 环境`，定义房间、工具、物品、非法动作和胜利条件。

关联提交：`fe42515`

## 记录规则建立

事件：增加工程事件记录文件和对应 workflow 规则。

原因：scope 只保留当前状态，spec 只保留技术决策，Git 只保留代码差异，三者无法单独表达重要事件的原因、验证和下一步。

改动：新增本文件，并在根 `AGENTS.md` 中定义记录范围、模板和提交前流程。

验证：`git diff --check` 已通过，工作区只包含预期的 `AGENTS.md` 和本文件改动。

下一步：后续每个重要阶段完成时追加一条简短记录。

## 2026-08-17 Spaceship Escape 环境设计确认

事件：确认第一个确定性世界的地图、公开工具、信息边界、谜题状态和逃生条件。

原因：环境规则必须先稳定，后续 Agent Loop、trace 和 benchmark 才有可信对照。

改动：新增 `docs/specs/0002-spaceship-escape/`，并将 scope 中的 Spaceship Escape 环境改为设计完成和实现中。

验证：完成设计访谈与独立只读交叉检查。九项契约空白已补齐，`git diff --check` 通过。

下一步：运行 `/develop Spaceship Escape 环境`，实现配置、Environment 和规则测试。

关联提交：待提交。

## 2026-08-17 Spaceship Escape 环境完成

事件：完成第一个可手动通关的确定性 Spaceship Escape 环境。

原因：为后续 Agent Loop、Episode Trace 和 benchmark 建立可重复的环境基线。

改动：新增严格 Action 与 Observation 契约、六房间 JSON 定义、环境状态转换和规则测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 25 项 pytest 通过，公开工具路径在 20 步内完成逃生。

下一步：设计 ReactAgent 与 Agent Loop。

关联提交：待提交。

## 2026-08-17 Release 1 Agent Loop 完成

事件：Release 1 的 ReactAgent、受限 Episode Runner、JSON Episode Trace 和 CLI 运行闭环完成。

原因：在进入 Memory 与 benchmark 前，需要一个可重复、可复盘且不会将不可信模型原文写入 trace 的基线 Agent。

改动：新增 `0003-react-agent-loop` spec、`ReactAgent`、百炼结构化决策适配、20 步 Fake 通关路径、Runner 状态机、脱敏原子 trace 写入和端到端测试；CLI `run` 不再生成 scaffold episode。

验证：`uv run ruff check .`、`uv run mypy src` 和 30 项 pytest 通过；`uv run agent-arena run --output-dir <temporary-directory>` 生成 `success` trace，含 20 个已执行动作和 0 个非法输出。

下一步：设计规则驱动的 MemoryAgent，并在固定世界、模型、提示词与步数预算下建立 Release 2 对照。

关联提交：待提交。
