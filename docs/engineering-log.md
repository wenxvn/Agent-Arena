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

## 2026-08-17 百炼 Action 格式修复

事件：真实百炼运行曾连续输出带 `args` 包装的动作，现已通过 `react_v3` prompt 改为直接在 `action` 内提供工具参数。

原因：严格 Action schema 正确拒绝了非约定格式，但旧 prompt 只给出无参数工具示例，模型稳定选择了通用包装格式。

改动：升级 prompt 版本并列出六种工具的完整扁平 JSON 示例，明确禁止 `args`、`arguments` 和 `parameters` 包装字段；增加 prompt 约束回归测试。

验证：Ruff、mypy 和 31 项 pytest 通过。真实百炼运行从 3 次非法输出、0 个执行动作变为 0 次非法输出、30 个有效动作；该局因反复探索无电控制终端达到步数上限，说明格式问题已修复，而基线策略仍是后续 MemoryAgent 的研究对象。

下一步：设计 MemoryAgent，用结构化记忆降低重复观察和重复失败动作。

关联提交：待提交。

## 2026-08-17 Release 2 MemoryAgent 完成

事件：完成规则驱动的结构化 MemoryAgent，并建立与 ReactAgent 的可复现单局对照。

原因：在 benchmark 前先固定唯一实验变量，避免完整历史、隐藏状态或第二次模型调用影响结果。

改动：增加公开记忆 reducer、脱敏、失败动作与问题映射、Agent 生命周期、结构化 provider 请求与响应、token 用量、trace 实验来源和 CLI `--agent` 选择。

验证：Ruff、mypy 和 33 项 pytest 全部通过。ReactAgent 与 MemoryAgent 的 Fake CLI 均在 20 步成功逃生，Memory trace 包含版本化来源字段。

下一步：实现 benchmark 命令，使用持久化 trace 输出 ReactAgent 和 MemoryAgent 的 JSON、CSV 指标对照。

关联提交：待提交。

## 2026-08-17 Release 2 Benchmark 与指标完成

事件：完成多局 benchmark 命令，以及基于持久化 trace 的 JSON、CSV 指标输出。

原因：MemoryAgent 需要与 ReactAgent 在相同世界、seed 和预算下进行可复现对照，才能解释后续实验结果。

改动：新增 benchmark 行和聚合计算、原子 JSON/CSV 写入、trace 重读校验；CLI 支持单 Agent 或默认双 Agent 对照。

验证：Ruff、mypy 和 36 项 pytest 通过。`agent-arena benchmark --episodes 1` 使用 Fake provider 生成两份 trace，CSV 按 React、Memory 顺序输出，JSON 聚合成功率为 1.0。

下一步：在 benchmark 结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 Benchmark 反馈与文件命名改进

事件：为 episode trace 和 benchmark 结果加入可读文件名，并让 benchmark 实时显示运行进度。

原因：原始 UUID 文件名难以按实验辨认；真实百炼 benchmark 默认运行 React 与 Memory 两组，原 CLI 在所有局完成前没有任何输出，容易被误判为卡住。

改动：输出名称包含 UTC 时间、Agent、seed 或局数和短 ID；真实模型会在每次决策请求前输出当前步数，benchmark 还会输出开始、每局开始和每局结束状态。

验证：Fake provider 端到端运行确认新名称和进度输出。`uv run ruff check .`、`uv run mypy src` 和 37 项 pytest 全部通过。

下一步：以小局数真实 benchmark 观察新进度信息和实际响应时长，再在结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 本地 Ollama 与逐步复盘支持

事件：将真实实验工作流扩展为本地 Ollama `qwen3:4b`，并在终端逐步显示简短理由、动作、环境结果和对应 trace 路径。

原因：百炼的 3 seed React、Memory 对照均达到步数上限。Trace 显示 React 重复读取无电终端，Memory 虽减少拒绝动作但在维修室和反应堆室之间循环；原 benchmark 终端未展示已记录的步骤，难以直接诊断。

改动：新增 `ollama` provider、无密钥本地验证、独立 Ollama 配置、`react_v4` 探索规则和逐步终端回显。完整步骤继续存入 `runs/`，`results/` 保持指标职责。

验证：Ollama 服务可访问但模型列表为空，因此真实本地模型验证明确失败，未伪造通过结果。Ruff、mypy 和 39 项 pytest 全部通过；Fake benchmark 验证逐步输出和 trace 路径。

下一步：在本机下载 `qwen3:4b` 后运行 `verify-model --provider ollama`，再以单局和同 seed 对照检验 `react_v4` 的真实模型表现。

关联提交：待提交。
